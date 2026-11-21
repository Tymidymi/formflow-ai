"""FormFlow AI v0.7.0 — official COI Schema validation and deterministic exporter."""
from pathlib import Path
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
from .semantic_quality import normalize_semantic
from .conditional_rules import apply_conditions

ROOT=Path(__file__).resolve().parent
app=FastAPI(title="FormFlow AI",version="0.7.0",
    description="COI prototype. OpenRouter is development ONLY, not competition-compliant.",
    docs_url="/api/docs",redoc_url=None,openapi_url="/api/openapi.json")
app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")

@app.middleware("http")
async def security(request:Request, call_next):
    size=request.headers.get("content-length")
    if size:
        try: n=int(size)
        except ValueError:
            return JSONResponse(status_code=400,content={"detail":"Błędny Content-Length."})
        if n<0 or n>max_upload_bytes()+1024*1024:
            return JSONResponse(status_code=413,content={"detail":"Przekroczono limit uploadu."})
    response=await call_next(request)
    response.headers["X-Request-ID"]=str(uuid4())
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.exception_handler(RejectedFile)
async def reject_upload(request:Request,exc:RejectedFile):
    return JSONResponse(status_code=exc.status,content={"detail":str(exc)})

@app.get("/",include_in_schema=False)
def home():
    return FileResponse(ROOT/"static"/"index.html")

@app.get("/healthz")
def health():
    return {"status":"ok","service":"formflow-ai-api","version":"0.7.0"}

@app.get("/readyz")
def ready():
    return {"status":"development" if enabled() else "foundation_ready",
            "conversion_ready":enabled(),"competition_compliant":False}

@app.get("/api/v1/capabilities")
def capabilities():
    return {"inspection":True,"conversion":enabled(),"preview":True,
            "coi_structural_validation":True,"coi_schema_validation":True,
            "model_provider":("ollama-offline" if __import__("os").environ.get("FORMFLOW_AI_PROVIDER")=="ollama"
                              else "openrouter-development" if enabled() else "disabled"),
            "docling_office_enabled":__import__("os").environ.get("FORMFLOW_DOCLING_URL")=="http://docling-office:8001",
            "pdf_ocr_enabled":__import__("os").environ.get("FORMFLOW_PDF_WORKER_URL")=="http://pdf-engine:8002",
            "pdf_vision_enabled":__import__("os").environ.get("FORMFLOW_PDF_VISION")=="true",
            "supported_extensions":[".pdf",".doc",".docx",".ods",".xlsx",".jpg",".jpeg",".png"],
            "conversion_extensions":[".pdf",".docx",".ods",".xlsx",".jpg",".jpeg",".png"],
            "max_upload_bytes":max_upload_bytes(),
            "note":"OpenRouter DEV or optional local Ollama (not yet E2E tested). PDF layout/OCR and Docling Office available; legacy DOC and full Docling PDF pending."}

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

@app.post("/api/v1/forms/validate-json")
async def validate_json(request:Request):
    try: data=await request.json()
    except ValueError:
        return JSONResponse(status_code=400,content={"detail":"Nieprawidłowy JSON."})
    return validate_coi_form(data)

@app.post("/api/v1/forms/convert")
async def convert_form(file:UploadFile=File(...),x_external_ai_consent:str|None=Header(default=None),
                       mode: Literal["coi","diagnostic"]=Query(default="coi")):
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
    try:
        text,images,extraction_meta=await extract_with_backend(content,ext)
        semantic,info=await generate(text,images)
        semantic,normalization=normalize_semantic(text,semantic)
        semantic,conditions=apply_conditions(text,semantic)
        normalization.extend(conditions)
        result,validation=to_coi(semantic)
        quality=assess_quality(text,semantic)
        if extraction_meta.get("truncated"):
            quality["ok"]=False
            quality.setdefault("possible_missing",[]).append("Źródło przekroczyło limit tekstu")
    except AIProviderError as exc:
        return JSONResponse(status_code=502,content={"detail":str(exc),"code":"AI_PROVIDER_ERROR"})
    except ValueError as exc:
        return JSONResponse(status_code=422,content={"detail":str(exc),"code":"INVALID_SEMANTIC_FORM"})
    if mode=="coi":
        if not validation["valid"] or not quality["ok"]:
            return JSONResponse(status_code=422,content={
                "detail":"Wygenerowana konfiguracja wymaga ręcznej weryfikacji.",
                "code":"COI_REVIEW_REQUIRED","validation":validation,"quality":quality})
        return result
    return {"status":"generated" if validation["valid"] and quality["ok"] else "needs_review",
            "provider":info.get("provider","openrouter-development"),"model":info["model"],"usage":info.get("usage",{}),
            "document":{"filename":file.filename,"size_bytes":len(content),"detected_mime":mime,"extraction":extraction_meta},
            "form":result,"validation":validation,"quality":quality,
            "normalization":normalization,
            "warning":("Ollama działa lokalnie, ale kompletnej zgodności konkursowej nie potwierdzono."
                       if info.get("provider")=="ollama-offline"
                       else "Tryb developerski wysyła zawartość formularza do OpenRouter. Nie jest wersją konkursową.")}
