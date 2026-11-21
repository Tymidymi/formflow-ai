"""Privacy-safe conversion telemetry and actionable model failure diagnostics."""
import asyncio
import json
import re

import pytest
from fastapi.testclient import TestClient

from app import ai_provider, conversion_audit
from app.ai_provider import AIProviderError, decode_json
from app.main import app

def test_audit_redacts_unknown_strings_and_keys(monkeypatch):
    emitted=[]
    monkeypatch.setattr(conversion_audit.logger,"info",emitted.append)
    token=conversion_audit.REQUEST_ID.set("deadcafe"*4)
    try:
        conversion_audit.record("model_response",status="ok",
                                file_extension=".pdf",prompt_tokens=123,
                                filename="PRYWATNE DANE PESEL",
                                request_body="super-secret",
                                model="model user@example.com")
    finally:
        conversion_audit.REQUEST_ID.reset(token)
    assert len(emitted)==1
    entry=json.loads(emitted[0])
    assert entry["request_id"]=="deadcafe"*4
    assert entry["prompt_tokens"]==123
    assert entry["file_extension"]==".pdf"
    assert "PRYWATNE" not in emitted[0]
    assert "secret" not in emitted[0]
    assert "example.com" not in emitted[0]

def fake_model(monkeypatch,output,finish_reason="stop",tokens=700):
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","synthetic-test-key")
    class Response:
        status_code=200
        def json(self):
            return {"id":"gen-abc-123",
                    "choices":[{"finish_reason":finish_reason,
                                "message":{"content":output}}],
                    "usage":{"prompt_tokens":340,"completion_tokens":tokens,
                             "total_tokens":340+tokens}}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr(ai_provider.httpx,"AsyncClient",Client)

def test_invalid_json_records_position_and_model_finish_reason(monkeypatch):
    fake_model(monkeypatch,'{"pages":[{"title":"x" bad}]}',finish_reason="stop")
    logged=[]
    monkeypatch.setattr(conversion_audit.logger,"info",logged.append)
    with pytest.raises(AIProviderError) as caught:
        asyncio.run(ai_provider.generate("Imię nazwisko PESEL data / numer telefonu",[]))
    assert caught.value.code=="MODEL_INVALID_JSON"
    events=[json.loads(x) for x in logged]
    broken=next(x for x in events if x["event"]=="model_invalid_json")
    assert broken["finish_reason"]=="stop"
    assert broken["response_chars"]>10
    assert broken["json_error_line"]>=1
    assert broken["json_error_column"]>=1
    assert all('"title":"x"' not in x for x in logged)

def test_finish_reason_length_accurately_classifies_truncation(monkeypatch):
    fake_model(monkeypatch,'{"pages":[{"title":"x"',finish_reason="length",tokens=6500)
    logged=[]
    monkeypatch.setattr(conversion_audit.logger,"info",logged.append)
    with pytest.raises(AIProviderError,match="ucięta") as caught:
        asyncio.run(ai_provider.generate("Imię nazwisko PESEL data / numer telefonu",[]))
    assert caught.value.code=="MODEL_OUTPUT_TRUNCATED"
    events=[json.loads(x) for x in logged]
    assert any(x.get("max_tokens")==6500 for x in events)
    assert any(x.get("completion_tokens")==6500 for x in events)
    assert any(x.get("finish_reason")=="length" for x in events)

def test_valid_json_still_working(monkeypatch):
    fake_model(monkeypatch,'{"title":"Wniosek","pages":[]}')
    form,info=asyncio.run(ai_provider.generate("Imię nazwisko PESEL data / numer telefonu",[]))
    assert form["pages"]==[]
    assert info["usage"]["prompt_tokens"]==340

def test_browser_error_gets_same_request_id_as_server_audit(monkeypatch):
    import app.main as api
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","synthetic-test-key")
    async def extracted(*_args,**_kwargs):
        return "Imię i nazwisko\nTelefon\nPESEL\nMiejscowość",[],{"engine":"synthetic","pages":1}
    async def structured(*_args,**_kwargs):
        raise AIProviderError("Model nie zwrócił poprawnego JSON.",
                              code="MODEL_INVALID_JSON")
    monkeypatch.setattr(api,"extract_with_backend",extracted)
    monkeypatch.setattr(api,"extract_structured",structured)
    seen=[]
    monkeypatch.setattr(conversion_audit.logger,"info",seen.append)
    response=TestClient(app).post("/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent":"true"},
        files={"file":("fake.pdf",b"%PDF-1.7\n%synthetic","application/pdf")})
    assert response.status_code==502
    detail=response.json()
    assert detail["code"]=="MODEL_INVALID_JSON"
    request_id=detail["request_id"]
    assert re.fullmatch("[0-9a-f]{32}",request_id)
    assert response.headers["X-Request-ID"]==request_id
    audit=[json.loads(msg) for msg in seen]
    assert any(x["event"]=="conversion_failed" and x["request_id"]==request_id
               for x in audit)
    assert any(x["event"]=="conversion_http" and x["http_status"]==502
               for x in audit)
    assert all("fake.pdf" not in msg for msg in seen)

def test_failed_document_is_classified_as_document_not_ai_failure(monkeypatch):
    import app.main as api
    from app.uploads import RejectedFile
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","synthetic-test-key")
    async def bad_document(*_args,**_kwargs):
        raise RejectedFile("PDF jest uszkodzony.",422)
    monkeypatch.setattr(api,"extract_with_backend",bad_document)
    logged=[]
    monkeypatch.setattr(conversion_audit.logger,"info",logged.append)
    response=TestClient(app).post("/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent":"true"},
        files={"file":("synthetic.pdf",b"%PDF-1.7\\nsynthetic","application/pdf")})
    assert response.status_code==422
    assert response.json()["code"]=="DOCUMENT_REJECTED"
    assert "uszkodzony" in response.json()["detail"]
    assert response.json()["request_id"]==response.headers["X-Request-ID"]
    assert any(json.loads(x).get("error_code")=="DOCUMENT_REJECTED" for x in logged)
    assert not any(json.loads(x).get("error_code")=="INVALID_SEMANTIC_FORM" for x in logged)
