"""No network/credentials are needed: mocked offline Ollama protocol."""
import asyncio
import json

import pytest
from app.ai_provider import AIProviderError, generate, enabled

def test_offline_provider_does_not_require_external_token(monkeypatch):
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","ollama")
    monkeypatch.delenv("OPENROUTER_API_KEY",raising=False)
    assert enabled() is True

def test_offline_provider_uses_only_private_docker_hostname(monkeypatch):
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL","https://example.com")
    with pytest.raises(AIProviderError,match="prywatnej"):
        asyncio.run(generate("Wniosek o wydanie zaświadczenia"))

def test_offline_qwen_chat_protocol(monkeypatch):
    import app.ollama_provider as module
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL","http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL","qwen3-vl:8b-instruct")
    captured = []
    class Response:
        status_code=200
        def json(self):
            return {"message":{"content":json.dumps({
                "title":"Test","pages":[{"title":"Dane",
                "sections":[{"title":"A","fields":[{"label":"PESEL",
                "type":"TEXT_FIELD","required":False,"options":[]}]}]}]})},
                "prompt_eval_count":21, "eval_count":32}
    class Client:
        def __init__(self,**kwargs):
            assert kwargs.get("follow_redirects") is False
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,json=None):
            captured.append((url,json))
            return Response()
    monkeypatch.setattr(module.httpx,"AsyncClient",Client)
    semantic,meta=asyncio.run(generate("Formularz PESEL",[
        ("image/png",b"\x89PNG\r\n\x1a\nimage")]))
    assert captured[0][0]=="http://ollama:11434/api/chat"
    assert captured[0][1]["stream"] is False
    assert captured[0][1]["messages"][1].get("images")
    assert "Authorization" not in str(captured[0][1])
    assert meta["provider"]=="ollama-offline"
    assert semantic["pages"][0]["sections"][0]["fields"][0]["label"]=="PESEL"
