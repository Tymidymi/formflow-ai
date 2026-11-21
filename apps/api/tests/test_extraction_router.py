import pytest
import asyncio
from io import BytesIO
from docx import Document
from app.extraction_router import extract_with_backend


def sample_docx():
    doc = Document()
    doc.add_paragraph("Imię i nazwisko")
    doc.add_paragraph("Miejsce zamieszkania")
    io = BytesIO()
    doc.save(io)
    return io.getvalue()


@pytest.mark.parametrize("extension", [".doc", ".docx", ".xlsx", ".ods", ".pdf"])
def test_missing_worker_fails_explicitly(monkeypatch, extension):
    from app.uploads import RejectedFile

    monkeypatch.delenv("FORMFLOW_DOCLING_URL", raising=False)
    monkeypatch.delenv("FORMFLOW_PDF_WORKER_URL", raising=False)
    with pytest.raises(RejectedFile) as error:
        asyncio.run(extract_with_backend(b"source", extension))
    assert error.value.status == 503


def test_remote_worker_response_used(monkeypatch):
    import base64
    import app.extraction_router as router

    monkeypatch.setenv("FORMFLOW_DOCLING_URL", router.DOCLING_URL)
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", router.PDF_URL)
    calls = []

    async def request(url, extension, content, **kw):
        calls.append((url, extension))
        if url == router.DOCLING_URL:
            return {"pdf_base64": base64.b64encode(b"%PDF-source").decode()}
        assert content.startswith(b"%PDF-") and kw["previews"]
        return {
            "text": "[Strona 1/1]\nImię i nazwisko",
            "page_count": 1,
            "preview_images": [
                {
                    "page": 1,
                    "mime": "image/jpeg",
                    "base64": base64.b64encode(b"image").decode(),
                }
            ],
        }

    monkeypatch.setattr(router, "_request", request)
    monkeypatch.setattr(
        router, "check_visible_text", lambda data: {"material_clipping": False}
    )
    text, images, meta = asyncio.run(
        router.extract_with_backend(sample_docx(), ".docx")
    )
    assert calls == [(router.DOCLING_URL, ".docx"), (router.PDF_URL, ".pdf")]
    assert meta["normalization_engine"] == "libreoffice-pdf"
    assert meta["original_extension"] == ".docx" and images == [
        ("image/jpeg", b"image")
    ]
    assert "nazwisko" in text


def test_failed_worker_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("FORMFLOW_DOCLING_URL", "http://docling-office:8001")
    import app.extraction_router as router

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            raise router.httpx.ConnectError("Worker unavailable")

    monkeypatch.setattr(router.httpx, "AsyncClient", Client)
    from app.uploads import RejectedFile

    with pytest.raises(RejectedFile) as error:
        asyncio.run(router.extract_with_backend(sample_docx(), ".docx"))
    assert error.value.status == 503


def test_mirrored_xlsx_pages_are_rejected_before_creating_form(monkeypatch):
    import base64
    import app.extraction_router as router
    from app.uploads import RejectedFile

    monkeypatch.setenv("FORMFLOW_DOCLING_URL", router.DOCLING_URL)
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", router.PDF_URL)
    repeated = "Form columns and responses for the applicant. " * 25

    async def request(url, extension, content, **kwargs):
        if url == router.DOCLING_URL:
            return {"pdf_base64": base64.b64encode(b"%PDF-source").decode()}
        return {
            "text": "[Strona 1/2]\n" + repeated + "\n[Strona 2/2]\n" + repeated,
            "page_count": 2,
            "preview_images": [
                {
                    "page": page,
                    "mime": "image/jpeg",
                    "base64": base64.b64encode(b"image").decode(),
                }
                for page in (1, 2)
            ],
        }

    monkeypatch.setattr(router, "_request", request)
    monkeypatch.setattr(
        router, "check_visible_text", lambda data: {"material_clipping": False}
    )
    with pytest.raises(RejectedFile) as error:
        asyncio.run(router.extract_with_backend(b"mock xlsx content", ".xlsx"))
    assert error.value.status == 422
    assert "niemal identyczne" in str(error.value)


def test_off_canvas_pdf_text_is_rejected_before_model_and_ocr(monkeypatch):
    import base64
    import app.extraction_router as router
    from app.uploads import RejectedFile

    monkeypatch.setenv("FORMFLOW_DOCLING_URL", router.DOCLING_URL)
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", router.PDF_URL)
    calls = []

    async def worker(url, extension, content, **kwargs):
        calls.append(url)
        assert url == router.DOCLING_URL
        return {"pdf_base64": base64.b64encode(b"%PDF-source").decode()}

    monkeypatch.setattr(router, "_request", worker)
    monkeypatch.setattr(
        router, "check_visible_text",
        lambda data: {"material_clipping": True, "off_page_glyphs": 600},
    )
    with pytest.raises(RejectedFile, match="poza widocznym") as error:
        asyncio.run(router.extract_with_backend(b"an office document", ".xlsx"))
    assert error.value.status == 422
    assert calls == [router.DOCLING_URL]  # no OCR/model on lossy source
