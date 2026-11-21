"""FormFlow AI v1.2.0 — official COI Schema validation and deterministic exporter."""
from pathlib import Path
import time
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .settings import max_upload_bytes
from .uploads import RejectedFile, validate_filename, detect_mime, inspect_upload
from .ai_provider import AIProviderError, enabled, generate
from .extraction_router import extract_with_backend
from .coi_builder import convert as to_coi
from .coi_validation import validate_coi_form
from .quality_gate import assess as assess_quality
from .field_grounding import analyze_grounding
from .conversion_audit import REQUEST_ID,record
from .semantic_quality import normalize_semantic
from .conditional_rules import apply_conditions
from .document_zones import split_legal_notice, primary_image_crop
from .form_repair import repair_form
from .demo_fixture import create_demo

ROOT=Path(__file__).resolve().parent
app=FastAPI(title="FormFlow AI",version="1.2.0",
    description="COI prototype using OpenRouter API; not compliant with COI no-external-API requirement.",
    docs_url="/api/docs",redoc_url=None,openapi_url="/api/openapi.json")
app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")

@app.middleware("http")
async def security(request:Request, call_next):
    request_id=uuid4().hex
    token=REQUEST_ID.set(request_id)
    started=time.monotonic()
    status=500
    try:
        size=request.headers.get("content-length")
        error_status=None
        if size:
            try: n=int(size)
            except ValueError: error_status=400
            else:
                if n<0 or n>max_upload_bytes()+1024*1024:
                    error_status=413
        if error_status:
            response=JSONResponse(status_code=error_status,content={
                "detail":"Nieprawidłowy lub zbyt duży dokument.",
                "request_id":request_id})
        else:
            response=await call_next(request)
        status=response.status_code
        response.headers["X-Request-ID"]=request_id
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Cache-Control"]="no-store"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self'; img-src 'self' data: blob:; object-src 'none'; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'"
        return response
    except Exception as exc:
        if request.url.path=="/api/v1/forms/convert":
            record("conversion_exception",error_class=type(exc).__name__)
        raise
    finally:
        if request.url.path=="/api/v1/forms/convert":
            record("conversion_http",http_status=status,
                   elapsed_ms=round((time.monotonic()-started)*1000))
        REQUEST_ID.reset(token)

@app.exception_handler(RejectedFile)
async def reject_upload(request:Request,exc:RejectedFile):
    return JSONResponse(status_code=exc.status,content={"detail":str(exc)})

@app.get("/",include_in_schema=False)
def home():
    return FileResponse(ROOT/"static"/"index.html")

@app.get("/healthz")
def health():
    return {"status":"ok","service":"formflow-ai-api","version":"1.2.0"}

@app.get("/readyz")
def ready():
    return {"status":"development" if enabled() else "foundation_ready",
            "conversion_ready":enabled(),"competition_compliant":False}

@app.get("/api/v1/capabilities")
def capabilities():
    return {"inspection":True,"conversion":enabled(),"preview":True,"jsonforms_preview":True,"comparison_view":True,
            "coi_structural_validation":True,"coi_schema_validation":True,
            "model_provider":("ollama-offline" if __import__("os").environ.get("FORMFLOW_AI_PROVIDER")=="ollama"
                              else "openrouter-development" if enabled() else "disabled"),
            "docling_office_enabled":__import__("os").environ.get("FORMFLOW_DOCLING_URL")=="http://docling-office:8001",
            "pdf_ocr_enabled":__import__("os").environ.get("FORMFLOW_PDF_WORKER_URL")=="http://pdf-engine:8002",
            "pdf_vision_enabled":__import__("os").environ.get("FORMFLOW_PDF_VISION")=="true",
            "supported_extensions":[".pdf",".doc",".docx",".ods",".xlsx",".jpg",".jpeg",".png"],
            "conversion_extensions":[".pdf",".docx",".ods",".xlsx",".jpg",".jpeg",".png"],
            "max_upload_bytes":max_upload_bytes(),
            "note":"OpenRouter used for prototype and planned submission despite COI external-API ban. JSON Forms preview enabled; old DOC and full Docling PDF pending."}

@app.post("/api/v1/forms/inspect")
async def inspect(file:UploadFile=File(...)):
    return {"status":"validated","document":await inspect_upload(file)}

@app.post("/api/v1/forms/extract-preview")
async def extract_preview(file:UploadFile=File(...)):
    """Local-only preview: does NOT call OpenRouter or any external API."""
    ext=validate_filename(file.filename)
    try:
        content=await file.read(max_upload_bytes()+1)
    finally:
        await file.close()
    if not content:raise RejectedFile("Pusty dokument.",422)
    if len(content)>max_upload_bytes():raise RejectedFile("Przekroczono limit pliku.",413)
    mime=detect_mime(content,ext)
    text,images,meta=await extract_with_backend(content,ext)
    return {"external_api_used":False,"filename":file.filename,"mime":mime,
            "extraction":meta,"characters":len(text),
            "text_preview":text[:4000],"images_for_vision":len(images)}

@app.get("/api/v1/demo/convert")
def demo_form():
    """Static, synthetic COI form: no external API call and no user data."""
    return create_demo()

@app.post("/api/v1/forms/validate-json")
async def validate_json(request:Request):
    try: data=await request.json()
    except ValueError:
        return JSONResponse(status_code=400,content={"detail":"Nieprawidłowy JSON."})
    return validate_coi_form(data)

@app.post("/api/v1/forms/convert")
async def convert_form(file:UploadFile=File(...),x_external_ai_consent:str|None=Header(default=None),
                       mode: Literal["coi","diagnostic"]=Query(default="coi"),
                       vision: Literal["auto","on","off"]=Query(default="auto")):
    if not enabled():
        await file.close()
        return JSONResponse(status_code=503,content={"detail":"AI wyłączone. Uruchom compose.dev.yaml.",
                                                      "code":"AI_DISABLED"})
    if __import__("os").environ.get("FORMFLOW_AI_PROVIDER")=="openrouter" and x_external_ai_consent!="true":
        await file.close()
        return JSONResponse(status_code=403,content={"detail":"Wymagana świadoma zgoda na wysłanie dokumentu do zewnętrznego API.",
                                                      "code":"EXTERNAL_API_CONSENT_REQUIRED"})
    ext=validate_filename(file.filename)
    try:content=await file.read(max_upload_bytes()+1)
    finally:await file.close()
    if not content:raise RejectedFile("Nie można przesłać pustego pliku.")
    if len(content)>max_upload_bytes():raise RejectedFile("Przekroczony limit.",413)
    mime=detect_mime(content,ext)
    record("conversion_start",file_extension=ext,file_bytes=len(content),
           vision_mode=vision)
    try:
        text,images,extraction_meta=await extract_with_backend(content,ext,vision_mode=vision)
        record("document_extracted",stage="extraction",
               page_count=extraction_meta.get("pages"),
               images_sent=len(images))
        extraction_meta["vision_requested"]=vision
        zones=split_legal_notice(text)
        model_images=images
        if zones.was_split and ext in (".jpg",".jpeg",".png") and images:
            cropped,crop_meta=primary_image_crop(content,ext,zones)
            model_images=[("image/jpeg" if crop_meta.get("vision_cropped") else images[0][0],cropped)]
            extraction_meta.update(crop_meta)
        extraction_meta["legal_notice_detected"]=zones.was_split
        extraction_meta["main_text_characters"]=len(zones.body)
        extraction_meta["legal_text_characters"]=len(zones.legal)
        semantic,info=await generate(zones.body,model_images)
        extraction_meta["model_images_sent"]=info.get("images_sent",len(model_images))
        semantic,repair_changes=repair_form(semantic,zones)
        semantic,normalization=normalize_semantic(zones.body,semantic)
        normalization=repair_changes+normalization
        semantic,conditions=apply_conditions(zones.body,semantic)
        normalization.extend(conditions)
        result,validation=to_coi(semantic)
        quality=assess_quality(zones.body,semantic)
        grounding=analyze_grounding(zones.body,semantic,images_count=len(model_images))
        quality["ocr_evidence_coverage"]=grounding["support_ratio"]
        quality["ocr_evidence_unverified"]=grounding["requires_review"]
        quality["legal_notice_readonly"]=bool(zones.legal)
        quality["manual_review_recommended"]=any(
            c["type"] in ("reference_field_recovered",
                          "ungrounded_reference_field_removed","legal_input_removed")
            for c in repair_changes
        )
        quality["removed_noninput_fields"]=sum(1 for c in repair_changes
            if c["type"] in ("ungrounded_reference_field_removed","legal_input_removed"))
        quality["recovered_fields"]=sum(1 for c in repair_changes if c["type"] in
            ("source_field_recovered","reference_field_recovered"))
        if extraction_meta.get("truncated"):
            quality["ok"]=False
            quality.setdefault("possible_missing",[]).append("Źródło przekroczyło limit tekstu")
        if extraction_meta.get("vision_incomplete"):
            quality["manual_review_recommended"]=True
            quality.setdefault("possible_missing",[]).append(
                "Wizualnie przeanalizowano tylko część stron PDF. Sprawdź pozostałe strony.")
        if len(model_images)>extraction_meta.get("model_images_sent",len(model_images)):
            quality["manual_review_recommended"]=True
            quality.setdefault("possible_missing",[]).append(
                "Co najmniej jeden obraz został pominięty ze względu na limit rozmiaru modelu.")
        if extraction_meta.get("vision_rejected_pages"):
            quality["manual_review_recommended"]=True
            quality.setdefault("possible_missing",[]).append(
                "Nie wszystkie obrazy stron zmieściły się w limicie API.")
    except RejectedFile as exc:
        record("conversion_failed",stage="extraction",
               error_code="DOCUMENT_REJECTED")
        return JSONResponse(status_code=exc.status,content={
            "detail":str(exc),"code":"DOCUMENT_REJECTED",
            "request_id":REQUEST_ID.get()})
    except AIProviderError as exc:
        record("conversion_failed",stage="ai",error_code=exc.code)
        return JSONResponse(status_code=502,content={
            "detail":str(exc),"code":exc.code,"request_id":REQUEST_ID.get()})
    except ValueError as exc:
        record("conversion_failed",stage="normalization",
               error_code="INVALID_SEMANTIC_FORM")
        return JSONResponse(status_code=422,content={
            "detail":"Wynik AI ma nieprawidłową strukturę pól lub stron.",
            "code":"INVALID_SEMANTIC_FORM","request_id":REQUEST_ID.get()})
    record("conversion_processed",stage="coi",
           schema_valid=bool(validation.get("schema_valid")),
           quality_ok=bool(quality.get("ok")),
           page_count=extraction_meta.get("pages"),
           images_sent=extraction_meta.get("model_images_sent"))
    if mode=="coi":
        if not validation["valid"] or not quality["ok"]:
            return JSONResponse(status_code=422,content={
                "detail":"Wygenerowana konfiguracja wymaga ręcznej weryfikacji.",
                "code":"COI_REVIEW_REQUIRED","validation":validation,"quality":quality})
        return result
    return {"request_id":REQUEST_ID.get(),
            "status":"generated" if validation["valid"] and quality["ok"]
            and not quality.get("manual_review_recommended") else "needs_review",
            "provider":info.get("provider","openrouter-development"),"model":info["model"],"usage":info.get("usage",{}),
            "document":{"filename":file.filename,"size_bytes":len(content),"detected_mime":mime,"extraction":extraction_meta},
            "form":result,"validation":validation,"quality":quality,
            "normalization":normalization,
            "grounding":grounding,
            "warning":("Ollama działa lokalnie, ale kompletnej zgodności konkursowej nie potwierdzono."
                       if info.get("provider")=="ollama-offline"
                       else "Tryb developerski wysyła zawartość formularza do OpenRouter. Nie jest wersją konkursową.")}
