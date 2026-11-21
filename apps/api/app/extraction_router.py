"""Choose Docling Office worker when explicitly configured, otherwise local parser.

Only internal Docker endpoint is permitted, never an arbitrary document URL.
The memory-heavy Docling worker is opt-in and isolated from the FastAPI process.
"""
import asyncio
import os
import httpx
from .document_text import extract_document

OFFICE = {".docx", ".xlsx", ".ods"}
INTERNAL_URL = "http://docling-office:8001"

async def extract_with_backend(content: bytes, extension: str) -> tuple[str, list, dict]:
    url = os.environ.get("FORMFLOW_DOCLING_URL", "")
    if extension in OFFICE and url == INTERNAL_URL:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(42.0, connect=3.0), follow_redirects=False
            ) as client:
                resp = await client.post(
                    url + "/extract",
                    files={"file": ("formularz" + extension, content, "application/octet-stream")},
                )
            if resp.status_code == 200:
                payload = resp.json()
                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    return text[:18000], [], {
                        "engine": "docling-office",
                        "tables": payload.get("tables", 0),
                        "source_pages": payload.get("page_count", 0),
                    }
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        text, images = await asyncio.to_thread(extract_document, content, extension)
        return text, images, {"engine": "local-fallback",
                              "warning": "Docling worker nie jest dostępny; użyto parsera lokalnego."}
    text, images = await asyncio.to_thread(extract_document, content, extension)
    return text, images, {"engine": "local"}
