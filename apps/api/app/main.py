"""FormFlow AI — source-grounded document extraction and COI exporter."""

from pathlib import Path
from io import BytesIO
import json
import re
from zipfile import ZipFile, ZIP_DEFLATED
import time
import asyncio
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .settings import max_upload_bytes
from .uploads import RejectedFile, validate_filename, detect_mime, inspect_upload
from .ai_provider import AIProviderError, enabled
from .extraction_router import extract_with_backend
from .coi_builder import convert as to_coi
from .canonical_form import canonicalize
from .coi_validation import validate_coi_form
from .page_inventory import assess as assess_quality
from .field_grounding import analyze_grounding
from .conversion_audit import REQUEST_ID, record
from .page_inventory import extract as extract_structured
from .demo_fixture import create_demo

ROOT = Path(__file__).resolve().parent
app = FastAPI(
    title="FormFlow AI",
    version="1.4.0",
    description="COI prototype using OpenRouter API; not compliant with COI no-external-API requirement.",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/documentation", StaticFiles(directory=ROOT / "static" / "documentation", html=True), name="documentation")
app.mount("/projekt", StaticFiles(directory=ROOT / "static" / "project", html=True), name="project")


@app.get("/api/docs", include_in_schema=False)
def api_documentation():
    return RedirectResponse(url="/documentation/api.html", status_code=307)


@app.middleware("http")
async def security(request: Request, call_next):
    request_id = uuid4().hex
    token = REQUEST_ID.set(request_id)
    started = time.monotonic()
    status = 500
    try:
        size = request.headers.get("content-length")
        error_status = None
        if size:
            try:
                n = int(size)
            except ValueError:
                error_status = 400
            else:
                if n < 0 or n > max_upload_bytes() + 1024 * 1024:
                    error_status = 413
        if error_status:
            response = JSONResponse(
                status_code=error_status,
                content={
                    "detail": "Nieprawidłowy lub zbyt duży dokument.",
                    "request_id": request_id,
                },
            )
        else:
            response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self'; img-src 'self' data: blob:; object-src 'none'; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'"
        )
        return response
    except Exception as exc:
        if request.url.path == "/api/v1/forms/convert":
            record("conversion_exception", error_class=type(exc).__name__)
        raise
    finally:
        if request.url.path == "/api/v1/forms/convert":
            record(
                "conversion_http",
                http_status=status,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        REQUEST_ID.reset(token)


@app.exception_handler(RejectedFile)
async def reject_upload(request: Request, exc: RejectedFile):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "formflow-ai-api", "version": "1.4.0"}


@app.get("/readyz")
def ready():
    return {
        "status": "development" if enabled() else "foundation_ready",
        "conversion_ready": enabled(),
        "competition_compliant": False,
    }


@app.get("/api/v1/capabilities")
def capabilities():
    return {
        "inspection": True,
        "conversion": enabled(),
        "preview": True,
        "jsonforms_preview": True,
        "comparison_view": True,
        "coi_structural_validation": True,
        "coi_schema_validation": True,
        "model_provider": (
            "ollama-offline"
            if __import__("os").environ.get("FORMFLOW_AI_PROVIDER") == "ollama"
            else "openrouter-development" if enabled() else "disabled"
        ),
        "docling_office_enabled": __import__("os").environ.get("FORMFLOW_DOCLING_URL")
        == "http://docling-office:8001",
        "pdf_ocr_enabled": __import__("os").environ.get("FORMFLOW_PDF_WORKER_URL")
        == "http://pdf-engine:8002",
        "pdf_vision_enabled": __import__("os").environ.get("FORMFLOW_PDF_VISION")
        == "true",
        "supported_extensions": [
            ".pdf",
            ".doc",
            ".docx",
            ".ods",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
        ],
        "conversion_extensions": [
            ".pdf",
            *(
                [".doc"]
                if __import__("os").environ.get("FORMFLOW_DOCLING_URL")
                == "http://docling-office:8001"
                else []
            ),
            ".docx",
            ".ods",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
        ],
        "max_upload_bytes": max_upload_bytes(),
        "pipeline": "source-page-v2",
        "office_normalization_engine": "libreoffice-pdf+docling-slim-source",
        "note": "Development uses external AI. Office retains original structural evidence from Docling Slim alongside rendered PDF pages.",
    }


@app.post("/api/v1/forms/inspect")
async def inspect(file: UploadFile = File(...)):
    return {"status": "validated", "document": await inspect_upload(file)}


@app.post("/api/v1/forms/extract-preview")
async def extract_preview(file: UploadFile = File(...)):
    """Local-only preview: does NOT call OpenRouter or any external API."""
    ext = validate_filename(file.filename)
    try:
        content = await file.read(max_upload_bytes() + 1)
    finally:
        await file.close()
    if not content:
        raise RejectedFile("Pusty dokument.", 422)
    if len(content) > max_upload_bytes():
        raise RejectedFile("Przekroczono limit pliku.", 413)
    mime = detect_mime(content, ext)
    text, images, meta = await extract_with_backend(content, ext)
    return {
        "external_api_used": False,
        "filename": file.filename,
        "mime": mime,
        "extraction": {k: v for k, v in meta.items() if k != "source_sections"},
        "characters": len(text),
        "text_preview": text[:4000],
        "images_for_vision": len(images),
    }


@app.get("/api/v1/demo/convert")
def demo_form():
    """Static, synthetic COI form: no external API call and no user data."""
    return create_demo()


@app.post("/api/v1/forms/validate-json")
async def validate_json(request: Request):
    try:
        data = await request.json()
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Nieprawidłowy JSON."})
    return validate_coi_form(data)


@app.post("/api/v1/forms/batch/export", include_in_schema=True)
async def export_reviewed_batch(request: Request):
    """Package already reviewed COI JSON definitions, without storing inputs.

    Conversion itself is processed sequentially by the browser using the
    existing /convert endpoint, to avoid multi-document timeouts and RAM spikes.
    """
    payload = await request.body()
    if len(payload) > 5 * 1024 * 1024:
        return JSONResponse(status_code=413, content={"detail": "Zbyt duża paczka JSON."})
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        return JSONResponse(status_code=400, content={"detail": "Nieprawidłowy JSON."})
    items = data.get("forms") if isinstance(data, dict) else None
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        return JSONResponse(status_code=422, content={"detail": "Paczka wymaga od 1 do 5 formularzy."})
    archive = BytesIO()
    names = set()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=5) as zf:
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict) or not isinstance(item.get("form"), dict):
                return JSONResponse(status_code=422, content={"detail": "Brak definicji COI."})
            form = item["form"]
            report = validate_coi_form(form)
            if not report["valid"] or not report["schema_valid"] or report["summary"]["input_fields"] < 1:
                return JSONResponse(status_code=422, content={
                    "detail": f"Formularz {index} nie przeszedł walidacji COI."
                })
            candidate = str(item.get("filename") or f"formularz-{index}")
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate.rsplit(".", 1)[0])[:80].strip(".-_")
            base = safe or f"formularz-{index}"
            name = f"{base}.json"
            counter = 2
            while name in names:
                name = f"{base}-{counter}.json"
                counter += 1
            names.add(name)
            zf.writestr(name, json.dumps(form, ensure_ascii=False, indent=2))
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="formflow-formularze.zip"'},
    )


async def _convert_form(
    file: UploadFile = File(...),
    x_external_ai_consent: str | None = Header(default=None),
    mode: Literal["coi", "diagnostic"] = Query(default="coi"),
    vision: Literal["auto", "on", "off"] = Query(default="auto"),
):
    if not enabled():
        await file.close()
        return JSONResponse(
            status_code=503,
            content={
                "detail": "AI wyłączone. Uruchom compose.dev.yaml.",
                "code": "AI_DISABLED",
            },
        )
    if (
        __import__("os").environ.get("FORMFLOW_AI_PROVIDER") == "openrouter"
        and x_external_ai_consent != "true"
    ):
        await file.close()
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Wymagana świadoma zgoda na wysłanie dokumentu do zewnętrznego API.",
                "code": "EXTERNAL_API_CONSENT_REQUIRED",
            },
        )
    ext = validate_filename(file.filename)
    try:
        content = await file.read(max_upload_bytes() + 1)
    finally:
        await file.close()
    if not content:
        raise RejectedFile("Nie można przesłać pustego pliku.")
    if len(content) > max_upload_bytes():
        raise RejectedFile("Przekroczony limit.", 413)
    mime = detect_mime(content, ext)
    record(
        "conversion_start",
        file_extension=ext,
        file_bytes=len(content),
        vision_mode=vision,
    )
    try:
        text, images, extraction_meta = await extract_with_backend(
            content, ext, vision_mode=vision
        )
        record(
            "document_extracted",
            stage="extraction",
            page_count=extraction_meta.get("pages"),
            images_sent=len(images),
        )
        extraction_meta["vision_requested"] = vision
        semantic, inventory_meta, page_reports = await extract_structured(
            text,
            images,
            image_page_numbers=extraction_meta.get("vision_page_numbers"),
            pages_expected=extraction_meta.get("pages"),
            source_sections=extraction_meta.pop("source_sections", None),
            source_title=extraction_meta.get("document_title"),
        )
        extraction_meta["model_images_sent"] = inventory_meta["images_sent"]
        extraction_meta["source_pages_processed"] = inventory_meta["pages_processed"]
        extraction_meta["independently_checked_pages"] = inventory_meta[
            "rechecked_pages"
        ]
        semantic = canonicalize(semantic)
        result, validation = to_coi(semantic)
        quality = assess_quality(
            text,
            semantic,
            pages=page_reports,
            pages_expected=inventory_meta.get("pages_expected"),
            vision_incomplete=bool(extraction_meta.get("vision_incomplete")),
            truncated=bool(extraction_meta.get("truncated")),
        )
        grounding = analyze_grounding(
            text, semantic, images_count=inventory_meta["images_sent"]
        )
        quality["ocr_evidence_coverage"] = grounding["support_ratio"]
        quality["ocr_evidence_unverified"] = grounding["requires_review"]
        if grounding["requires_review"]:
            quality["possible_missing"].append(
                "Część pól nie ma niezależnego potwierdzenia w warstwie OCR; "
                "wymagana kontrola obrazu źródłowego."
            )
            quality["ok"] = False
        quality["legacy_doc_layout_unverified"] = bool(
            extraction_meta.get("legacy_doc_review_required")
        )
        quality["manual_review_recommended"] = bool(
            quality.get("manual_review_recommended")
            or grounding["requires_review"]
            or extraction_meta.get("legacy_doc_review_required")
        )
        normalization = []
        info = {
            "model": inventory_meta.get("model", "unknown"),
            "usage": inventory_meta.get("usage", {}),
            "provider": inventory_meta.get("provider", "openrouter-development"),
        }
        evidence_map = [
            {
                "label": str(field.get("label", ""))[:220],
                "section": str(section.get("title", ""))[:130],
                "source_page": field.get("source_page"),
                "source_quote": str(field.get("evidence", ""))[:240],
            }
            for page in semantic.get("pages", [])
            for section in page.get("sections", [])
            for field in section.get("fields", [])
            if field.get("type") not in ("INFO_BLOCK", "TEXT_BLOCK")
        ]
        inventory_report = {
            "pages": page_reports,
            "summary": inventory_meta,
            "source_map": evidence_map,
        }
    except RejectedFile as exc:
        record("conversion_failed", stage="extraction", error_code="DOCUMENT_REJECTED")
        return JSONResponse(
            status_code=exc.status,
            content={
                "detail": str(exc),
                "code": "DOCUMENT_REJECTED",
                "request_id": REQUEST_ID.get(),
            },
        )
    except AIProviderError as exc:
        record("conversion_failed", stage="ai", error_code=exc.code)
        return JSONResponse(
            status_code=502,
            content={
                "detail": str(exc),
                "code": exc.code,
                "request_id": REQUEST_ID.get(),
            },
        )
    except ValueError as exc:
        record(
            "conversion_failed",
            stage="normalization",
            error_code="INVALID_SEMANTIC_FORM",
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Wynik AI ma nieprawidłową strukturę pól lub stron.",
                "code": "INVALID_SEMANTIC_FORM",
                "request_id": REQUEST_ID.get(),
            },
        )
    record(
        "conversion_processed",
        stage="coi",
        schema_valid=bool(validation.get("schema_valid")),
        quality_ok=bool(quality.get("ok")),
        page_count=extraction_meta.get("pages"),
        images_sent=extraction_meta.get("model_images_sent"),
    )
    if mode == "coi":
        if not validation["valid"] or not quality["ok"]:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Wygenerowana konfiguracja wymaga ręcznej weryfikacji.",
                    "code": "COI_REVIEW_REQUIRED",
                    "validation": validation,
                    "quality": quality,
                },
            )
        return result
    return {
        "request_id": REQUEST_ID.get(),
        "status": (
            "generated"
            if validation["valid"]
            and quality["ok"]
            and not quality.get("manual_review_recommended")
            else "needs_review"
        ),
        "provider": info.get("provider", "openrouter-development"),
        "model": info["model"],
        "usage": info.get("usage", {}),
        "document": {
            "filename": file.filename,
            "size_bytes": len(content),
            "detected_mime": mime,
            "extraction": extraction_meta,
        },
        "form": result,
        "validation": validation,
        "quality": quality,
        "normalization": normalization,
        "grounding": grounding,
        "inventory": inventory_report,
        "warning": (
            "Ollama działa lokalnie, ale kompletnej zgodności konkursowej nie potwierdzono."
            if info.get("provider") == "ollama-offline"
            else "Tryb developerski wysyła zawartość formularza do OpenRouter. Nie jest wersją konkursową."
        ),
    }


CONVERSION_TIMEOUT_SECONDS = 240
CONVERSION_SLOTS = asyncio.Semaphore(2)


# A wall-clock deadline includes normalization, every model call and verification.
# Disconnect cancellation reaches httpx and cancels all outstanding child tasks.
@app.post("/api/v1/forms/convert")
async def convert_form(
    request: Request,
    file: UploadFile = File(...),
    x_external_ai_consent: str | None = Header(default=None),
    mode: Literal["coi", "diagnostic"] = Query(default="coi"),
    vision: Literal["auto", "on", "off"] = Query(default="auto"),
):
    async def disconnected():
        while not await request.is_disconnected():
            await asyncio.sleep(0.5)

    async def bounded_conversion():
        async with CONVERSION_SLOTS:
            return await _convert_form(file, x_external_ai_consent, mode, vision)

    work = asyncio.create_task(bounded_conversion())
    closed = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait(
            {work, closed},
            timeout=CONVERSION_TIMEOUT_SECONDS,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if work in done:
            return work.result()
        code = "CLIENT_DISCONNECTED" if closed in done else "CONVERSION_TIMEOUT"
        record("conversion_failed", stage="budget", error_code=code)
        return JSONResponse(
            status_code=499 if closed in done else 504,
            content={
                "code": code,
                "detail": "Przerwano konwersję; przekroczony czas lub rozłączony klient.",
                "request_id": REQUEST_ID.get(),
            },
        )
    finally:
        for task in (work, closed):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, closed, return_exceptions=True)
