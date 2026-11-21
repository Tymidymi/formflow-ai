from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_ready():
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["conversion_ready"] is False


def test_inspect_pdf():
    response = client.post("/api/v1/forms/inspect", files={"file": ("wniosek.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")})
    assert response.status_code == 200
    assert response.json()["document"]["detected_mime"] == "application/pdf"


def test_rejects_bad_mime():
    response = client.post("/api/v1/forms/inspect", files={"file": ("bad.png", b"%PDF-1.7\n", "image/png")})
    assert response.status_code == 415


def test_rejects_invalid_filename():
    response = client.post("/api/v1/forms/inspect", files={"file": ("bad;name.pdf", b"%PDF-1.7\n", "application/pdf")})
    assert response.status_code == 422


def test_conversion_is_not_faked():
    response = client.post("/api/v1/forms/convert", files={"file": ("test.pdf", b"%PDF-1.7\n", "application/pdf")})
    assert response.status_code == 501
    assert response.json()["code"] == "CONVERSION_NOT_IMPLEMENTED"


def test_ui_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "FormFlow AI" in response.text
