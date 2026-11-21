import asyncio
from io import BytesIO
from docx import Document
from app.extraction_router import extract_with_backend

def sample_docx():
    doc=Document(); doc.add_paragraph("Imię i nazwisko"); doc.add_paragraph("Miejsce zamieszkania")
    io=BytesIO(); doc.save(io); return io.getvalue()

def test_no_worker_local_extractor(monkeypatch):
    monkeypatch.delenv("FORMFLOW_DOCLING_URL",raising=False)
    text,images,metadata=asyncio.run(extract_with_backend(sample_docx(),".docx"))
    assert metadata["engine"]=="local"
    assert "Imię i nazwisko" in text and images==[]

def test_remote_worker_response_used(monkeypatch):
    monkeypatch.setenv("FORMFLOW_DOCLING_URL","http://docling-office:8001")
    import app.extraction_router as router
    class Response:
        status_code=200
        def json(self):
            return {"text":"# Dane wnioskodawcy\n\n| Imię | Nazwisko |",
                    "engine":"docling-slim","tables":1,"page_count":1}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr(router.httpx,"AsyncClient",Client)
    text,images,metadata=asyncio.run(router.extract_with_backend(sample_docx(),".docx"))
    assert metadata["engine"]=="docling-office"
    assert metadata["tables"]==1
    assert "| Imię | Nazwisko |" in text and images==[]

def test_failed_worker_falls_back(monkeypatch):
    monkeypatch.setenv("FORMFLOW_DOCLING_URL","http://docling-office:8001")
    import app.extraction_router as router
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            raise router.httpx.ConnectError("Worker unavailable")
    monkeypatch.setattr(router.httpx,"AsyncClient",Client)
    text,images,metadata=asyncio.run(router.extract_with_backend(sample_docx(),".docx"))
    assert metadata["engine"]=="local-fallback"
    assert "Imię i nazwisko" in text
