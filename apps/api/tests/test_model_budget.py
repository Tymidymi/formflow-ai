"""Truncated output must not trigger an escalating retry cascade."""

import asyncio
import pytest


def test_truncation_stops_without_escalating_completion_budget(monkeypatch):
    from app import ai_provider

    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    budgets = []

    class Response:
        status_code = 200

        def __init__(self, budget):
            self.budget = budget

        def json(self):
            if self.budget == 6500:
                return {
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": '{"pages":['},
                        }
                    ],
                    "usage": {"completion_tokens": 6500},
                    "id": "gen-retry-test-1",
                }
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"title":"Gotowe","pages":[]}'},
                    }
                ],
                "usage": {"completion_tokens": 120},
                "id": "gen-retry-test-2",
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            budget = kwargs["json"]["max_tokens"]
            budgets.append(budget)
            return Response(budget)

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", Client)
    with pytest.raises(ai_provider.AIProviderError) as error:
        asyncio.run(
            ai_provider.generate(
                "Syntetyczna etykieta do formularza rejestracji urządzenia", []
            )
        )
    assert error.value.code == "MODEL_OUTPUT_TRUNCATED"
    assert budgets == [6500]


def test_static_blocks_have_a_distinct_contract():
    from app.ai_provider import decode_json, AIProviderError
    from app.page_inventory import INVENTORY_SCHEMA
    import json

    block = {
        "label": "Informacje",
        "type": "INFO_BLOCK",
        "evidence": "",
        "content": "Treść źródłowa",
    }
    data = {
        "title": "Test",
        "pages": [
            {
                "title": "Strona",
                "sections": [{"title": "Informacje", "fields": [block]}],
            }
        ],
    }
    assert decode_json(json.dumps(data), INVENTORY_SCHEMA) == data
    block["label"] = ""
    with pytest.raises(AIProviderError) as error:
        decode_json(json.dumps(data), INVENTORY_SCHEMA)
    assert error.value.code == "MODEL_SCHEMA_INVALID"


def test_qwen_temperature_zero_passed_to_provider(monkeypatch):
    from app import ai_provider

    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("OPENROUTER_TEMPERATURE", "0")
    monkeypatch.delenv("OPENROUTER_REASONING_EFFORT", raising=False)
    requests = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"title":"Form","pages":[]}'},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
                "id": "gen-synthetic-temperature",
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            requests.append(kwargs["json"])
            return FakeResponse()

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", FakeClient)
    result, metadata = asyncio.run(
        ai_provider.generate("Independent fictional application with the applicant contact address and date fields", [])
    )
    assert result["pages"] == []
    assert requests[0]["temperature"] == 0
    assert requests[0]["model"].startswith("qwen/")
    assert "reasoning" not in requests[0]
    # Same Qwen model, but choose provider by throughput to reduce slow-tail
    # completion times on scanned PDF pages.
    assert requests[0]["provider"]["sort"] == "throughput"


def test_invalid_temperature_fails_without_api_call(monkeypatch):
    from app import ai_provider

    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("OPENROUTER_TEMPERATURE", "NaN")
    with pytest.raises(ai_provider.AIProviderError) as error:
        asyncio.run(ai_provider.generate("Independent fictional application with the applicant contact address and date fields", []))
    assert error.value.code == "MODEL_CONFIG_ERROR"
