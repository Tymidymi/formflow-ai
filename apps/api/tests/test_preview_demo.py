"""v0.8.0 demo and self-hosted React / JSON Forms integration smoke tests."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.demo_fixture import create_demo

client = TestClient(app)

def test_demo_coi_structure_and_conditions():
    fixture = create_demo()
    assert fixture["status"] == "demo"
    assert fixture["validation"]["schema_valid"] is True
    assert fixture["validation"]["valid"] is True
    assert len(fixture["form"]["tabs"]) == 3
    fields=[
        x["field"] for tab in fixture["form"]["tabs"]
        for question in tab["questions"]
        for x in question["field"].get("repeatingSectionGrid", [])
    ]
    assert len(fields) > 10
    assert any(f["type"] == "RADIO" and
        {choice["name"] for choice in f["options"]} == {"Wnioskodawca","Inna osoba"}
        for f in fields)
    hidden = [f for f in fields if f.get("states")]
    assert len(hidden) >= 2
    assert all(f["states"][0]["type"] == "SHOW" for f in hidden)

def test_demo_endpoint_is_local_only(monkeypatch):
    import app.ai_provider as ai
    async def impossible(*args, **kwargs):
        raise AssertionError("Demo must not contact model")
    monkeypatch.setattr(ai,"generate",impossible)
    response=client.get("/api/v1/demo/convert")
    assert response.status_code==200,response.text
    assert response.json()["provider"]=="synthetic-local-fixture"

def test_react_bundle_and_styles_are_self_hosted():
    r=client.get("/")
    assert r.status_code==200
    assert "coi-preview-root" in r.text
    assert "preview.bundle.js" in r.text
    assert "preview.bundle.css" in r.text
    assert "load-demo" in r.text
    assert "NIE spełnia konkursowego zakazu" in r.text
    js=client.get("/static/preview.bundle.js")
    css=client.get("/static/preview.bundle.css")
    assert js.status_code==200 and len(js.content)>100000
    assert css.status_code==200 and len(css.content)>2000
    assert "frame-src 'self' blob:" in r.headers["content-security-policy"]
    assert r.headers["cache-control"]=="no-store"

def test_capabilities_show_preview_enabled():
    r=client.get("/api/v1/capabilities")
    assert r.status_code==200
    assert r.json()["jsonforms_preview"] is True
    assert r.json()["comparison_view"] is True
