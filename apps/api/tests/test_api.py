from io import BytesIO
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.coi_builder import convert

client=TestClient(app)

def test_health():
    assert client.get("/healthz").json()["version"]=="1.1.0"

def test_validation_pdf_signature():
    r=client.post("/api/v1/forms/inspect",files={"file":("test.pdf",b"%PDF-1.7\n%%EOF\n","application/pdf")})
    assert r.status_code==200

def test_bad_content_rejected():
    r=client.post("/api/v1/forms/inspect",files={"file":("bad.pdf",b"not pdf","application/pdf")})
    assert r.status_code==415

def test_ai_off_by_default(monkeypatch):
    monkeypatch.delenv("FORMFLOW_AI_PROVIDER",raising=False)
    r=client.post("/api/v1/forms/convert",files={"file":("test.pdf",b"%PDF-1.7\n","application/pdf")})
    assert r.status_code==503

def test_external_consent_required(monkeypatch):
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","fake-key-for-test")
    r=client.post("/api/v1/forms/convert",files={"file":("test.pdf",b"%PDF-1.7\n","application/pdf")})
    assert r.status_code==403

def test_builder_generates_valid_coi():
    semantic={"title":"Wniosek o zaświadczenie","pages":[{"title":"Dane",
      "sections":[{"title":"Wnioskodawca","fields":[{"label":"Imię","type":"TEXT_FIELD","required":True,"options":[]},
      {"label":"Rodzaj","type":"RADIO","options":["A","B"],"required":False}]}]}]}
    form,check=convert(semantic)
    assert check["valid"],check["errors"]
    assert len(form["tabs"])==2
    assert form["flow"]["links"][0]["source"]==form["tabs"][0]["id"]
    assert form["tabs"][-1]["type"]=="FINISH"

def test_mocked_conversion(monkeypatch):
    import app.main as api
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","fake-key-for-test")
    async def fake_model(text,images):
        return {"title":"Wniosek testowy","pages":[{"title":"Dane",
          "sections":[{"title":"Wnioskodawca","fields":[{"label":"Nazwisko","type":"TEXT_FIELD","required":False,"options":[]}]}]}]}, {
          "model":"mock-qwen","usage":{"total_tokens":3}}
    monkeypatch.setattr(api,"generate",fake_model)
    d=Document();d.add_paragraph("Wniosek o zaświadczenie");d.add_paragraph("Nazwisko")
    stream=BytesIO();d.save(stream)
    r=client.post("/api/v1/forms/convert?mode=diagnostic",headers={"X-External-AI-Consent":"true"},
                  files={"file":("wniosek.docx",stream.getvalue(),"application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code==200,r.text
    output=r.json()
    assert output["status"]=="generated"
    assert output["validation"]["valid"]
    assert output["form"]["title"]=="Wniosek testowy"

def test_ui():
    r=client.get("/")
    assert r.status_code==200
    assert "Przygotuj formularz" in r.text
    assert "Dodaj dokument" in r.text
    assert "Sprawdź i popraw" in r.text
    assert "Pobierz formularz" in r.text
    assert 'id="step-review" hidden' in r.text
    assert 'id="step-finish" hidden' in r.text
    assert 'id="file-consent" hidden' in r.text
