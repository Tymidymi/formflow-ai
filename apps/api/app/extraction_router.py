"""Route extraction to isolated private Docker workers with safe fallback.

PDF/JPG/PNG: local PDFium/pypdf layout + Tesseract pol+eng worker.
DOCX/XLSX/ODS: docling-slim Office worker.
All URLs are fixed hostnames on an internal Docker network (no SSRF).
"""
from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import httpx
from .document_text import extract_document
from .uploads import RejectedFile

OFFICE={".docx",".xlsx",".ods"}
PDF_INPUTS={".pdf",".png",".jpg",".jpeg"}
DOCLING_URL="http://docling-office:8001"
PDF_URL="http://pdf-engine:8002"

async def _request(url:str, extension:str, content:bytes, *, previews:bool=False)->dict:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(65.0,connect=3.0),follow_redirects=False
    ) as client:
        response=await client.post(
            url+"/extract",
            params={"previews":"true"} if previews else {},
            files={"file":("input"+extension,content,"application/octet-stream")},
        )
    if response.status_code in (413,415,422):
        try: detail=response.json().get("detail","Błąd ekstrakcji pliku.")
        except (ValueError,TypeError): detail="Błąd ekstrakcji pliku."
        raise RejectedFile(str(detail),response.status_code)
    if response.status_code!=200:
        raise httpx.HTTPStatusError("Worker unavailable",request=response.request,response=response)
    payload=response.json()
    if not isinstance(payload,dict) or not isinstance(payload.get("text"),str):
        raise ValueError("Worker returned invalid response")
    return payload

async def extract_with_backend(content:bytes,extension:str)->tuple[str,list,dict]:
    pdf_enabled=os.environ.get("FORMFLOW_PDF_WORKER_URL")==PDF_URL
    docling_enabled=os.environ.get("FORMFLOW_DOCLING_URL")==DOCLING_URL
    pdf_vision=os.environ.get("FORMFLOW_PDF_VISION","false").lower() in ("true","1","yes")
    if pdf_enabled and extension in PDF_INPUTS:
        try:
            payload=await _request(PDF_URL,extension,content,previews=pdf_vision)
            source_text=payload["text"][:18000]
            images=[]
            if extension in (".jpg",".jpeg",".png"):
                mime="image/png" if extension==".png" else "image/jpeg"
                images.append((mime,content))
            if extension==".pdf" and pdf_vision:
                for entry in payload.get("preview_images",[])[:2]:
                    if entry.get("mime")!="image/jpeg":
                        continue
                    raw=base64.b64decode(entry.get("base64",""),validate=True)
                    if 0<len(raw)<1_500_000:
                        images.append(("image/jpeg",raw))
            return source_text,images,{
                "engine":payload.get("engine","pdf-layout-ocr"),
                "pages":payload.get("page_count"),
                "ocr_pages":payload.get("ocr_pages"),
                "page_sources":payload.get("page_sources",[]),
                "truncated":payload.get("truncated",False),
                "vision_pages":len(images) if extension==".pdf" else 1,
            }
        except RejectedFile:raise
        except (httpx.HTTPError,ValueError,TypeError,KeyError,base64.binascii.Error):
            # Transparent fallback to the previous local parser.
            text,images=await asyncio.to_thread(extract_document,content,extension)
            return text,images,{"engine":"pdf-local-fallback","warning":"PDF/OCR worker unavailable"}
    if extension in OFFICE and docling_enabled:
        try:
            payload=await _request(DOCLING_URL,extension,content)
            text=payload["text"]
            if text.strip():
                return text[:18000],[],{"engine":"docling-office","tables":payload.get("tables",0),
                    "source_pages":payload.get("page_count",0),
                    "truncated":len(text)>18000}
        except RejectedFile:raise
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            text,images=await asyncio.to_thread(extract_document,content,extension)
            return text,images,{"engine":"local-fallback","warning":"Docling worker unavailable"}
    text,images=await asyncio.to_thread(extract_document,content,extension)
    return text,images,{"engine":"local"}
