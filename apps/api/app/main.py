"""FormFlow AI — source-grounded document extraction and COI exporter."""
from pathlib import Path
from difflib import SequenceMatcher
import time
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .settings import max_upload_bytes
from .uploads import RejectedFile, validate_filename, detect_mime, inspect_upload
from .ai_provider import AIProviderError, enabled
from .extraction_router import extract_with_backend
from .coi_builder import convert as to_coi
from .canonical_form import canonicalize
from .coi_validation import validate_coi_form
from .quality_gate import assess as assess_quality
from .field_grounding import analyze_grounding,norm
from .conversion_audit import REQUEST_ID,record
from .document_zones import split_legal_notice, primary_image_crop, suppress_readonly_source_controls
from .structured_extraction import extract as extract_structured, response_slot_count
from .legal_actions import extract_actions
from .demo_fixture import create_demo

ROOT=Path(__file__).resolve().parent
app=FastAPI(title="FormFlow AI",version="1.3.0",
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
    return {"status":"ok","service":"formflow-ai-api","version":"1.3.0"}

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
            "conversion_extensions":[".pdf",*([".doc"] if __import__("os").environ.get("FORMFLOW_DOCLING_URL")=="http://docling-office:8001" else []),".docx",".ods",".xlsx",".jpg",".jpeg",".png"],
            "max_upload_bytes":max_upload_bytes(),
            "note":"OpenRouter is used despite the COI external-API ban. Legacy DOC uses text-only antiword extraction; full Docling PDF and visual Office layout remain pending."}

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
        extraction_meta["legal_notice_detected"]=zones.was_split
        extraction_meta["main_text_characters"]=len(zones.body)
        extraction_meta["legal_text_characters"]=len(zones.legal)
        if zones.was_split and ext in (".jpeg",".jpg",".png") and images:
            cropped,crop_meta=primary_image_crop(content,ext,zones)
            extraction_meta.update(crop_meta)
            if crop_meta.get("vision_cropped"):
                images=[("image/jpeg",cropped)]
        semantic,inventory_meta,page_reports=await extract_structured(
            zones.body,images,
            image_page_numbers=extraction_meta.get("vision_page_numbers"),
            pages_expected=extraction_meta.get("pages"),
            source_sections=extraction_meta.get("source_sections"),
            source_title=extraction_meta.get("document_title"))
        extraction_meta["model_images_sent"]=inventory_meta["images_sent"]
        extraction_meta["source_pages_processed"]=inventory_meta["pages_processed"]
        extraction_meta["independently_checked_pages"]=inventory_meta["rechecked_pages"]
        # Classify field provenance against the operative text separately
        # from any read-only notice, regardless of the model's page layout.
        readonly_phantoms=suppress_readonly_source_controls(
            semantic,zones.body,zones.legal)
        extraction_meta["readonly_phantom_fields_rejected"]=readonly_phantoms
        # The quality report must be based on fields that actually survive
        # source-zoning, not on earlier model claims that were discarded.
        if readonly_phantoms:
            for source_report in page_reports:
                page_no=source_report.get("source_page")
                surviving={"pages":[{"sections":[{"fields":[
                    f for p in semantic.get("pages",[])
                    for section in p.get("sections",[])
                    for f in section.get("fields",[])
                    if f.get("source_page")==page_no
                    and f.get("type") not in ("INFO_BLOCK","TEXT_BLOCK")
                ]}]}]}
                source_report["detected_fields"]=len(surviving["pages"][0]["sections"][0]["fields"])
                source_report["detected_slots"]=response_slot_count(surviving)
        # The original legal appendix is retained verbatim as ONE read-only
        # text block. Never turn individual legal paragraphs into questions.
        # This is a document-wide safety rule, not a form-specific patch.
        if zones.legal:
            responses,_=await extract_actions(zones.legal)
            legal_sections=[
                {"title":"Informacja prawna","fields":[{
                    "label":"Treść informacji","type":"INFO_BLOCK",
                    "content":zones.legal}]}
            ]
            if responses:
                # A VLM may see a consent at the foot of a full-page image,
                # while legal OCR was separated from the main body. Merge
                # identical actions by wording, not by a form-specific rule.
                existing=[
                    norm(str(f.get("label",""))).strip(" .,:;![]")
                    for page in semantic["pages"]
                    for section in page.get("sections",[])
                    for f in section.get("fields",[])
                    if f.get("type") not in ("INFO_BLOCK","TEXT_BLOCK")]
                filtered=[]
                for response in responses:
                    label=norm(response["label"]).strip(" .,:;![]")
                    if any(
                        other and (label in other and len(label)>15
                         or (len(label)>20 and
                             SequenceMatcher(None,label,other).ratio()>=0.82))
                        for other in existing):
                        continue
                    filtered.append(response)
                    existing.append(label)
                if filtered:
                    legal_sections.append({"title":"Oświadczenia i zgody",
                                           "fields":filtered})
            semantic["pages"].append({
                "title":"Informacje dla wnioskodawcy",
                "sections":legal_sections})
        semantic=canonicalize(semantic)
        result,validation=to_coi(semantic)
        quality=assess_quality(
            zones.body,semantic,pages=page_reports,
            pages_expected=inventory_meta.get("pages_expected"),
            vision_incomplete=bool(extraction_meta.get("vision_incomplete")),
            truncated=bool(extraction_meta.get("truncated")))
        grounding=analyze_grounding(
            zones.body,semantic,images_count=inventory_meta["images_sent"])
        quality["ocr_evidence_coverage"]=grounding["support_ratio"]
        quality["ocr_evidence_unverified"]=grounding["requires_review"]
        quality["legal_notice_readonly"]=bool(zones.legal)
        quality["legacy_doc_layout_unverified"]=bool(extraction_meta.get("legacy_doc_review_required"))
        quality["manual_review_recommended"]=bool(
            quality.get("manual_review_recommended")
            or grounding["requires_review"]
            or inventory_meta.get("rechecked_pages")
            or extraction_meta.get("legacy_doc_review_required"))
        normalization=[]
        info={"model":__import__("os").getenv(
                 "OPENROUTER_MODEL","qwen/qwen3-vl-30b-a3b-instruct"),
              "usage":{},"provider":"openrouter-development"}
        evidence_map=[
            {"label":str(field.get("label",""))[:220],
             "section":str(section.get("title",""))[:130],
             "source_page":field.get("source_page"),
             "source_quote":str(field.get("evidence",""))[:240]}
            for page in semantic.get("pages",[])
            for section in page.get("sections",[])
            for field in section.get("fields",[])
            if field.get("type") not in ("INFO_BLOCK","TEXT_BLOCK")
        ]
        inventory_report={"pages":page_reports,"summary":inventory_meta,
                          "source_map":evidence_map}
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
            "inventory":inventory_report,
            "warning":("Ollama działa lokalnie, ale kompletnej zgodności konkursowej nie potwierdzono."
                       if info.get("provider")=="ollama-offline"
                       else "Tryb developerski wysyła zawartość formularza do OpenRouter. Nie jest wersją konkursową.")}
