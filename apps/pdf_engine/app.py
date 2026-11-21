"""Internal PDF/OCR worker: offline only, no public port and no persistent files."""
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from engine import PdfExtractionError, pdf_extract, image_extract

app=FastAPI(title="FormFlow PDF/OCR",docs_url=None,redoc_url=None,openapi_url=None)
SUPPORTED={".pdf",".png",".jpg",".jpeg"}
MAX_UPLOAD=15*1024*1024

@app.get("/healthz")
def health():
    return {"status":"ok","engine":"pdf-layout-ocr","formats":sorted(SUPPORTED),
            "ocr":"tesseract pol+eng","offline":True}

@app.post("/extract")
def extract(file:UploadFile=File(...), previews:bool=Query(default=False)):
    name=file.filename or ""
    ext="."+name.rsplit(".",1)[-1].lower()
    if ext not in SUPPORTED:raise HTTPException(status_code=415,detail="Nieobsługiwany format.")
    raw=file.file.read(MAX_UPLOAD+1)
    if not raw or len(raw)>MAX_UPLOAD:
        raise HTTPException(status_code=413,detail="Nieprawidłowy rozmiar pliku.")
    if ext==".pdf" and not raw.startswith(b"%PDF-"):
        raise HTTPException(status_code=415,detail="Brak sygnatury PDF.")
    if ext==".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415,detail="Brak sygnatury PNG.")
    if ext in (".jpg",".jpeg") and not raw.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415,detail="Brak sygnatury JPEG.")
    try:
        return pdf_extract(raw,previews) if ext==".pdf" else image_extract(raw,ext,previews)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=exc.code,detail=str(exc)) from exc
