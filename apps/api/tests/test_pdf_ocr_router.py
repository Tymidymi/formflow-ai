"""PDF OCR routing tests without calling external APIs or using real secrets."""

import asyncio
import base64
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.extraction_router import extract_with_backend
from app.uploads import RejectedFile


class Response:
    def __init__(self, status_code, payload, request=None):
        self.status_code = status_code
        self.payload = payload
        self.request = request or httpx.Request(
            "POST", "http://pdf-engine:8002/extract"
        )

    def json(self):
        return self.payload


def pdf_dummy():
    return b"%PDF-1.4\n" + b"x" * 80


def fake_client(monkeypatch, response):
    import app.extraction_router as router

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr(router.httpx, "AsyncClient", Client)


def test_pdf_worker_returns_page_provenance(monkeypatch):
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", "http://pdf-engine:8002")
    fake_client(
        monkeypatch,
        Response(
            200,
            {
                "text": "[Strona 1/1]\nImię i nazwisko\nPESEL",
                "engine": "pdf-layout-ocr",
                "page_count": 1,
                "ocr_pages": 0,
                "truncated": False,
                "page_sources": [{"page": 1, "method": "pypdf-layout"}],
            },
        ),
    )
    text, images, meta = asyncio.run(extract_with_backend(pdf_dummy(), ".pdf"))
    assert meta["engine"] == "pdf-layout-ocr" and meta["pages"] == 1
    assert meta["page_sources"][0]["method"] == "pypdf-layout"
    assert images == [] and "PESEL" in text


def test_pdf_worker_previews_for_vision(monkeypatch):
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", "http://pdf-engine:8002")
    monkeypatch.setenv("FORMFLOW_PDF_VISION", "true")
    fake_client(
        monkeypatch,
        Response(
            200,
            {
                "text": "[Strona 1/1]\nPESEL",
                "engine": "pdf-layout-ocr",
                "page_count": 1,
                "ocr_pages": 0,
                "preview_images": [
                    {
                        "mime": "image/jpeg",
                        "base64": base64.b64encode(b"\xff\xd8\xffmock").decode(),
                    }
                ],
            },
        ),
    )
    text, images, meta = asyncio.run(extract_with_backend(pdf_dummy(), ".pdf"))
    assert images == [("image/jpeg", b"\xff\xd8\xffmock")]
    assert meta["vision_pages"] == 1


def test_pdf_worker_invalid_doc_is_rejected_not_silently_fallen_back(monkeypatch):
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", "http://pdf-engine:8002")
    fake_client(monkeypatch, Response(422, {"detail": "Zaszyfrowany PDF"}))
    with pytest.raises(RejectedFile) as e:
        asyncio.run(extract_with_backend(pdf_dummy(), ".pdf"))
    assert e.value.status == 422


def test_image_kept_for_visual_model_when_ocr_extracts_text(monkeypatch):
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL", "http://pdf-engine:8002")
    fake_client(
        monkeypatch,
        Response(
            200,
            {
                "text": "WNIOSEK Nazwisko",
                "engine": "tesseract-pol+eng",
                "page_count": 1,
                "ocr_pages": 1,
                "truncated": False,
                "page_sources": [],
            },
        ),
    )
    from PIL import Image

    stream = BytesIO()
    Image.new("RGB", (100, 141), "white").save(stream, format="PNG")
    text, images, meta = asyncio.run(extract_with_backend(stream.getvalue(), ".png"))
    assert meta["normalization_engine"] == "image-page-slices"
    assert meta["original_extension"] == ".png"
    assert meta["ocr_pages"] == 1


def test_local_preview_does_not_call_openrouter(monkeypatch):
    import app.main as api

    async def extraction(content, extension):
        return "Imię i nazwisko\nPESEL", [], {"engine": "mock", "pages": 1}

    monkeypatch.setattr(api, "extract_with_backend", extraction)
    r = TestClient(app).post(
        "/api/v1/forms/extract-preview",
        files={"file": ("test.pdf", pdf_dummy(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["external_api_used"] is False
    assert "PESEL" in r.json()["text_preview"]
