"""Optional offline Open-Weight Qwen adapter for Ollama private Docker network.

This path is not considered competition-ready until actual hardware,
model, OCR, network isolation and license verification are demonstrated.
"""

from __future__ import annotations
import base64
import os
import httpx

OLLAMA_URL = "http://ollama:11434"


async def generate_offline(
    text: str,
    images: list[tuple[str, bytes]] | None = None,
    *,
    prompt=None,
    response_schema=None,
):
    from .ai_provider import PROMPT, AIProviderError, decode_json

    base = os.environ.get("OLLAMA_BASE_URL", OLLAMA_URL).rstrip("/")
    if base != OLLAMA_URL:
        raise AIProviderError(
            "Ollama musi działać we wskazanej prywatnej sieci Docker."
        )
    model = os.environ.get("OLLAMA_MODEL", "qwen3-vl:8b-instruct")
    if not model.startswith(("qwen3-vl:", "qwen2.5vl:")):
        raise AIProviderError("Nieobsługiwana rodzina modelu offline.")
    if not text.strip() and not images:
        raise AIProviderError("Brak treści dokumentu.")
    media = [
        base64.b64encode(content).decode("ascii")
        for mime, content in (images or [])[:3]
        if mime in ("image/jpeg", "image/png") and len(content) <= 4 * 1024 * 1024
    ]
    data = {
        "model": model,
        "stream": False,
        "format": response_schema or "json",
        "options": {"temperature": 0.1, "num_predict": 4000},
        "messages": [
            {"role": "system", "content": prompt or PROMPT},
            {
                "role": "user",
                "content": "Dokument urzędowy:\n" + text,
                **({"images": media} if media else {}),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(180, connect=5), follow_redirects=False
        ) as client:
            response = await client.post(base + "/api/chat", json=data)
    except httpx.TimeoutException as exc:
        raise AIProviderError("Lokalny Qwen nie odpowiedział w limicie czasu.") from exc
    except httpx.HTTPError as exc:
        raise AIProviderError("Nie można połączyć się z lokalnym Ollama.") from exc
    if response.status_code != 200:
        raise AIProviderError(
            f"Lokalna inferencja zwróciła HTTP {response.status_code}."
        )
    try:
        payload = response.json()
        content = payload["message"]["content"]
        semantic = decode_json(content, response_schema)
    except (KeyError, TypeError, ValueError) as exc:
        raise AIProviderError("Błędna odpowiedź lokalnego modelu.") from exc
    return semantic, {
        "model": model,
        "usage": {
            "prompt_tokens": payload.get("prompt_eval_count", 0),
            "completion_tokens": payload.get("eval_count", 0),
        },
        "provider": "ollama-offline",
    }
