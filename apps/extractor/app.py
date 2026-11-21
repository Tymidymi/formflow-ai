"""Internal-only, memory-bounded Docling Office extractor.

This optional worker extracts DOCX/XLSX/ODS. CPU PDF/OCR is a separate,
larger worker and is NOT implied by this service.
"""
from io import BytesIO
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="FormFlow Docling Office Worker", docs_url=None, openapi_url=None)
FORMATS = {".doc": "DOC", ".docx": "DOCX", ".xlsx": "XLSX", ".ods": "ODS"}
MAX_UPLOAD = 15 * 1024 * 1024

@lru_cache(maxsize=1)
def converter():
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    return DocumentConverter(allowed_formats=[
        InputFormat.DOCX, InputFormat.XLSX, InputFormat.ODS])

@app.get("/healthz")
def health():
    return {"status": "ok", "engine": "docling-slim", "formats": list(FORMATS)}

@app.post("/extract")
def extract(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = "." + filename.rsplit(".", 1)[-1].lower()
    if extension not in FORMATS:
        raise HTTPException(status_code=415, detail="Format poza zakresem workera Docling.")
    data = file.file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Pusty lub zbyt duży plik.")
    if extension == ".doc":
        from legacy_doc import extract_doc,LegacyDocError
        try:
            text=extract_doc(data)
        except LegacyDocError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc
        return {"engine":"antiword-legacy-doc", "format":extension,
                "text":text[:50000],"page_count":0,"tables":0,
                "layout_fidelity":"text_only",
                "warning":"Stary DOC: możliwa utrata graficznych pól i tabel; wymagana kontrola wyniku.",
                "truncated":len(text)>50000}
    from docling.datamodel.base_models import DocumentStream
    try:
        result = converter().convert(DocumentStream(name=filename, stream=BytesIO(data)))
        markdown = result.document.export_to_markdown()
        if not markdown.strip():
            raise ValueError("Pusta ekstrakcja.")
        return {"engine": "docling-slim", "format": extension,
                "text": markdown[:50000],
                "page_count": len(result.document.pages),
                "tables": len(result.document.tables)}
    except (ValueError, RuntimeError, AttributeError, ImportError, KeyError) as exc:
        # Keep the upstream error out of API responses to avoid leaking documents.
        raise HTTPException(status_code=422,
                            detail="Nie udało się wydobyć treści dokumentu przez Docling.") from exc