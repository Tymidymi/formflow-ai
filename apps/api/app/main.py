"""FormFlow AI — phase 1: safe upload inspection and self-hosted frontend."""

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import max_upload_bytes
from .uploads import RejectedFile, inspect_upload

ROOT = Path(__file__).resolve().parent
app = FastAPI(
    title="FormFlow AI",
    description="COI HackNation – etap 1: walidacja dokumentów; konwersja JSON COI jeszcze niedostępna.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def security_and_upload_limit(request: Request, call_next):
    correlation_id = str(uuid4())
    limit = max_upload_bytes()
    length = request.headers.get("content-length")
    if length:
        try:
            declared_size = int(length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Błędny Content-Length."})
        if declared_size < 0 or declared_size > limit + 1024 * 1024:
            return JSONResponse(status_code=413, content={"detail": "Przekroczono limit przesyłania."})
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.exception_handler(RejectedFile)
async def rejected_file_handler(_request: Request, exc: RejectedFile):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "formflow-ai-api", "version": "0.1.0"}


@app.get("/readyz")
async def readyz():
    return {"status": "foundation_ready", "conversion_ready": False}


@app.get("/api/v1/capabilities")
async def capabilities():
    return {
        "inspection": True,
        "conversion": False,
        "preview": False,
        "supported_extensions": [".pdf", ".doc", ".docx", ".ods", ".xlsx", ".jpg", ".jpeg", ".png"],
        "max_upload_bytes": max_upload_bytes(),
        "note": "Silnik Docling / Ollama / eksport COI zostaną dodane w kolejnych etapach.",
    }


@app.post("/api/v1/forms/inspect")
async def inspect(file: UploadFile = File(...)):
    return {"status": "validated", "document": await inspect_upload(file)}


@app.post("/api/v1/forms/convert")
async def convert(file: UploadFile = File(...)):
    await file.close()
    return JSONResponse(status_code=501, content={
        "detail": "Konwersja nie jest jeszcze wdrożona. Wymaga wzorcowego schematu JSON COI i lokalnego silnika AI.",
        "code": "CONVERSION_NOT_IMPLEMENTED",
    })
