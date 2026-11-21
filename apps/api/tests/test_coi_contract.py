"""Official COI schema and supplement rule regression tests."""
import copy
import hashlib
import json
from io import BytesIO
from pathlib import Path
from docx import Document
from fastapi.testclient import TestClient
from app.main import app
from app.coi_validation import SCHEMA_PATH, validate_coi_form
from app.coi_builder import convert, field_validation

client=TestClient(app)

def semantic():
    return {
        "title":"Wniosek o wydanie zaświadczenia",
        "pages":[{"title":"Dane wnioskodawcy","sections":[{
            "title":"Wnioskodawca","fields":[
                {"label":"Numer PESEL","type":"NUMBER","required":True},
                {"label":"Adres e-mail","type":"TEXT_FIELD","required":False},
                {"label":"Kod pocztowy","type":"TEXT_FIELD","required":False},
                {"label":"Cel wydania zaświadczenia","type":"TEXTAREA","required":False},
            ]
        }]}]
    }

def test_original_coi_schema_integrity():
    assert hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()=="6486974a7e6debb67675e879e5ae240b4903993015ed83c2a93dc9fd5785c7d2"

def test_generated_form_passes_official_and_structure():
    form,report=convert(semantic())
    assert report["schema_valid"] is True
    assert report["valid"] is True, report
    assert report["summary"]["input_fields"]==4
    assert form["tabs"][-1]["type"]=="FINISH"

def test_identical_input_yields_stable_uuid():
    a,_=convert(semantic())
    b,_=convert(semantic())
    assert a==b

def test_validation_inference_and_identifiers():
    form,report=convert(semantic())
    children=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    assert children[0]["field"]["type"]=="TEXT_FIELD" # PESEL must preserve leading 0
    assert children[0]["field"]["validation"]==["REQUIRED","PESEL"]
    assert children[1]["field"]["validation"]==["EMAIL"]
    assert children[2]["field"]["validation"]==["ZIP_CODE"]
    assert field_validation("Numer NIP",False)==["NIP"]
    assert field_validation("REGON",True)==["REQUIRED","REGON"]
    assert form["tabs"][-1]["questions"][0]["field"]["type"]=="SECTION"

def test_schema_rejects_invalid_options_type():
    form,_=convert(semantic())
    form["tabs"][0]["questions"][0]["field"]["options"]="not a list"
    report=validate_coi_form(form)
    assert report["schema_valid"] is False
    assert report["valid"] is False
    assert any(err["code"]=="COI_JSON_SCHEMA" for err in report["errors"])

def test_schema_is_deliberately_permissive_but_rules_are_not():
    report=validate_coi_form({"title":"A"})
    assert report["schema_valid"] is True
    assert report["valid"] is False

def test_reference_style_non_uuid_link_is_warning():
    form,_=convert(semantic())
    form["flow"]["links"][0]["id"]="a16ec"  # supplied COI reference #5 has this
    report=validate_coi_form(form)
    assert report["schema_valid"] is True
    assert report["valid"] is True
    assert any(w["code"]=="LINK_ID_NON_UUID" for w in report["warnings"])

def test_finish_not_reachable():
    form,_=convert(semantic())
    form["flow"]["links"]=[]
    report=validate_coi_form(form)
    assert report["schema_valid"] is True
    assert report["valid"] is False
    assert any(err["code"]=="UNREACHABLE_FINISH" for err in report["errors"])

def test_json_validation_endpoint():
    form,_=convert(semantic())
    response=client.post("/api/v1/forms/validate-json",json=form)
    assert response.status_code==200
    assert response.json()["schema_valid"] is True

def test_api_default_returns_only_coi_json(monkeypatch):
    import app.main as api
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","fake-token")
    async def fake_gen(text,images):
        return semantic(), {"model":"mock", "usage":{}}
    monkeypatch.setattr(api,"generate",fake_gen)
    doc=Document()
    doc.add_paragraph("Wniosek o wydanie zaświadczenia")
    stream=BytesIO();doc.save(stream)
    response=client.post("/api/v1/forms/convert",headers={"X-External-AI-Consent":"true"},
      files={"file":("test.docx",stream.getvalue(),
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert response.status_code==200, response.text
    output=response.json()
    assert set(output)=={"title","tabs","flow"}
    assert len(output["tabs"])>=2
