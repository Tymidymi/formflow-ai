"""Regressions for physical source slots, information zones, and choice merging.

These scenarios use unrelated generic domains to prevent sample-form-specific
production logic.
"""

import asyncio
from io import BytesIO
from PIL import Image


def test_api_crops_readonly_notice_and_exports_clean_coi(monkeypatch):
    """One full JPEG conversion flow without a sample-form-specific dictionary."""
    from fastapi.testclient import TestClient
    from PIL import ImageDraw
    from app.main import app
    import app.main as api

    im = Image.new("RGB", (900, 1800), "white")
    draw = ImageDraw.Draw(im)
    draw.text((40, 55), "APPLICATION", fill="black")
    draw.text((40, 260), "Name ..........", fill="black")
    draw.text((40, 390), "Date .........", fill="black")
    draw.text((40, 1430), "INFORMATION", fill="black")
    raw = BytesIO()
    im.save(raw, format="JPEG", quality=85)
    picture = raw.getvalue()
    body = (
        "WNIOSEK o wydanie decyzji. Dane wnioskodawcy. "
        "Nazwa .................................. "
    ) * 3
    tail = "INFORMACJE:\n" + (
        "Instrukcja tylko do przeczytania, bez pól odpowiedzi. " * 6
    )
    source = body + "\n" + tail
    seen = []

    async def fake_extract(content, extension, **kwargs):
        return (
            source,
            [("image/jpeg", picture)],
            {
                "engine": "synthetic-ocr",
                "pages": 1,
                "vision_page_numbers": [1],
                "vision_incomplete": False,
                "truncated": False,
            },
        )

    async def fake_model(text, images, **kwargs):
        size = Image.open(BytesIO(images[0][1])).size
        seen.append(size)
        return (
            {
                "title": "Rejestracja",
                "pages": [
                    {
                        "title": "Dane",
                        "sections": [
                            {
                                "title": "Dane źródłowe",
                                "fields": [
                                    {
                                        "label": "Nazwa",
                                        "type": "TEXT_FIELD",
                                        "evidence": "Nazwa",
                                    }
                                ],
                            },
                            {
                                "title": "INFORMACJE",
                                "fields": [
                                    {
                                        "label": "Instrukcja tylko do przeczytania",
                                        "type": "TEXT_FIELD",
                                        "evidence": "Instrukcja tylko do przeczytania",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {
                "images_sent": 1,
                "pages_processed": 1,
                "rechecked_pages": 0,
                "pages_expected": 1,
            },
            [
                {
                    "source_page": 1,
                    "blank_slots": 0,
                    "detected_fields": 2,
                    "source_evidence_count": 1,
                    "with_image": True,
                    "audit_issues": ["Instrukcja została zamieniona w pytanie."],
                }
            ],
        )

    async def fake_actions(text):
        return [], {}

    monkeypatch.setattr(api, "extract_with_backend", fake_extract)
    monkeypatch.setattr(api, "extract_structured", fake_model)
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-test-key")
    response = TestClient(app).post(
        "/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent": "true"},
        files={"file": ("test.jpg", picture, "image/jpeg")},
    )
    assert response.status_code == 200, response.text[:700]
    result = response.json()
    assert result["validation"]["valid"]
    assert not result["quality"]["ok"]
    assert result["status"] == "needs_review"
    assert seen and seen[0][1] == im.height
