from io import BytesIO
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.coi_builder import convert

client = TestClient(app)


def test_health():
    assert client.get("/healthz").json()["version"] == "1.4.0"


def test_project_landing_has_demo_repo_and_honest_placeholders():
    response = client.get("/projekt/")
    assert response.status_code == 200
    html = response.text
    assert 'href="/"' in html
    assert "github.com/Tymidymi/formflow-ai" in html
    assert "Prezentacja PDF" in html
    assert "Film demonstracyjny" in html
    assert 'href="/documentation/"' in html
    assert client.get("/static/project.css").status_code == 200


def test_technical_documentation_is_self_hosted():
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/documentation/"' in home.text

    page = client.get("/documentation/")
    assert page.status_code == 200
    assert "FormFlow AI" in page.text
    assert "Architektura" in page.text
    assert '/static/documentation/docs.css' in page.text
    assert "cdn.jsdelivr.net" not in page.text

    css = client.get("/static/documentation/docs.css")
    assert css.status_code == 200
    assert "--navy:#091735" in css.text

    for slug in ("api", "deployment", "testing", "licenses"):
        result = client.get(f"/documentation/{slug}.html")
        assert result.status_code == 200
        assert "<main" in result.text

    api = client.get("/api/docs", follow_redirects=False)
    assert api.status_code == 307
    assert api.headers["location"] == "/documentation/api.html"
    assert client.get("/api/openapi.json").status_code == 200


def test_validation_pdf_signature():
    r = client.post(
        "/api/v1/forms/inspect",
        files={"file": ("test.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")},
    )
    assert r.status_code == 200


def test_bad_content_rejected():
    r = client.post(
        "/api/v1/forms/inspect",
        files={"file": ("bad.pdf", b"not pdf", "application/pdf")},
    )
    assert r.status_code == 415


def test_ai_off_by_default(monkeypatch):
    monkeypatch.delenv("FORMFLOW_AI_PROVIDER", raising=False)
    r = client.post(
        "/api/v1/forms/convert",
        files={"file": ("test.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert r.status_code == 503


def test_external_consent_required(monkeypatch):
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")
    r = client.post(
        "/api/v1/forms/convert",
        files={"file": ("test.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert r.status_code == 403


def test_builder_generates_valid_coi():
    semantic = {
        "title": "Wniosek o zaświadczenie",
        "pages": [
            {
                "title": "Dane",
                "sections": [
                    {
                        "title": "Wnioskodawca",
                        "fields": [
                            {
                                "label": "Imię",
                                "type": "TEXT_FIELD",
                                "required": True,
                                "options": [],
                            },
                            {
                                "label": "Rodzaj",
                                "type": "RADIO",
                                "options": ["A", "B"],
                                "required": False,
                            },
                        ],
                    }
                ],
            }
        ],
    }
    form, check = convert(semantic)
    assert check["valid"], check["errors"]
    assert len(form["tabs"]) == 2
    assert form["flow"]["links"][0]["source"] == form["tabs"][0]["id"]
    assert form["tabs"][-1]["type"] == "FINISH"


def test_mocked_conversion(monkeypatch):
    import app.main as api

    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")

    async def fake_structured(text, images, **kwargs):
        return (
            {
                "title": "Wniosek testowy",
                "pages": [
                    {
                        "title": "Dane",
                        "sections": [
                            {
                                "title": "Wnioskodawca",
                                "fields": [
                                    {
                                        "label": "Nazwisko",
                                        "type": "TEXT_FIELD",
                                        "required": False,
                                        "options": [],
                                        "evidence": "Nazwisko",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "images_sent": 0,
                "pages_processed": 1,
                "rechecked_pages": 0,
                "pages_expected": 1,
            },
            [
                {
                    "source_page": 1,
                    "blank_slots": 0,
                    "detected_fields": 1,
                    "source_evidence_count": 1,
                    "with_image": True,
                    "audit_issues": [],
                }
            ],
        )

    monkeypatch.setattr(api, "extract_structured", fake_structured)

    async def fake_rendered_source(*args, **kwargs):
        return (
            "Nazwisko",
            [("image/jpeg", b"fixture")],
            {"engine": "test-render", "pages": 1, "vision_incomplete": False},
        )

    monkeypatch.setattr(api, "extract_with_backend", fake_rendered_source)

    d = Document()
    d.add_paragraph("Wniosek o zaświadczenie")
    d.add_paragraph("Nazwisko")
    stream = BytesIO()
    d.save(stream)
    r = client.post(
        "/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent": "true"},
        files={
            "file": (
                "wniosek.docx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r.status_code == 200, r.text
    output = r.json()
    assert output["status"] == "generated"
    assert output["validation"]["valid"]
    assert output["form"]["title"] == "Wniosek testowy"


def test_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "Przygotuj formularz" in r.text
    assert "Dodaj dokument" in r.text
    assert "Sprawdź i popraw" in r.text
    assert "Pobierz formularz" in r.text
    assert 'id="step-review" hidden' in r.text
    assert 'id="step-finish" hidden' in r.text
    assert 'id="file-consent" hidden' in r.text


def test_unexpected_conversion_exception_returns_structured_json(monkeypatch):
    """Worker failures must not become a blank HTTP 500 for the browser."""
    from app import main as main_module

    async def broken_conversion(*args, **kwargs):
        raise RuntimeError("simulated internal document parser failure")

    monkeypatch.setattr(main_module, "_convert_form", broken_conversion)
    response = client.post(
        "/api/v1/forms/convert?mode=diagnostic",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%test\n", "application/pdf")},
    )
    assert response.status_code == 500
    data = response.json()
    assert data["code"] == "CONVERSION_INTERNAL_ERROR"
    assert "simulated" not in data["detail"]
    assert len(data["request_id"]) == 32


def test_project_landing_is_compact_jury_link_index():
    response = client.get("/projekt/")
    assert response.status_code == 200
    html = response.text
    assert 'href="/"' in html
    assert "github.com/Tymidymi/formflow-ai" in html
    assert 'href="/documentation/"' in html
    assert 'href="/api/docs"' in html
    assert html.count('class="link-row') == 6
    assert html.count('class="link-row pending"') == 2
    assert "Prezentacja PDF" in html and "Film demonstracyjny" in html
    assert "Cyfryzacja w trzech krokach" not in html
