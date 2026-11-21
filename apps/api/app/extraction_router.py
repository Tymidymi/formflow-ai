"""Route extraction to isolated private Docker workers with safe fallback.

PDF/JPG/PNG: local PDFium/pypdf layout + Tesseract pol+eng worker.
DOCX/XLSX/ODS: docling-slim Office worker. Legacy DOC: antiword text-only.
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

OFFICE={".doc",".docx",".xlsx",".ods"}
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

async def extract_with_backend(content:bytes,extension:str,*,vision_mode:str="auto")->tuple[str,list,dict]:
    if vision_mode not in {"auto","on","off"}:
        raise ValueError("Nieprawidłowy tryb vision.")
    pdf_enabled=os.environ.get("FORMFLOW_PDF_WORKER_URL")==PDF_URL
    docling_enabled=os.environ.get("FORMFLOW_DOCLING_URL")==DOCLING_URL
    pdf_vision=(vision_mode=="on" or (vision_mode=="auto" and
                os.environ.get("FORMFLOW_PDF_VISION","false").lower() in ("true","1","yes")))
    if pdf_enabled and extension in PDF_INPUTS:
        try:
            payload=await _request(PDF_URL,extension,content,previews=pdf_vision)
            source_text=payload["text"][:100000]
            images=[]
            if extension in (".jpg",".jpeg",".png"):
                mime="image/png" if extension==".png" else "image/jpeg"
                images.append((mime,content))
            page_numbers=[]
            rejected_images=[]
            if extension==".pdf" and pdf_vision:
                for entry in payload.get("preview_images",[])[:12]:
                    page=entry.get("page")
                    if entry.get("mime")!="image/jpeg":
                        rejected_images.append(page)
                        continue
                    raw=base64.b64decode(entry.get("base64",""),validate=True)
                    if 0<len(raw)<1_500_000:
                        images.append(("image/jpeg",raw))
                        page_numbers.append(page)
                    else:
                        rejected_images.append(page)
            count=payload.get("page_count") or 0
            return source_text,images,{
                "engine":payload.get("engine","pdf-layout-ocr"),
                "pages":count,
                "ocr_pages":payload.get("ocr_pages"),
                "page_sources":payload.get("page_sources",[]),
                "truncated":payload.get("truncated",False) or len(payload["text"])>100000,
                "vision_enabled":bool(pdf_vision) if extension==".pdf" else True,
                "vision_pages":len(images) if extension==".pdf" else 1,
                "vision_page_numbers":page_numbers if extension==".pdf" else [1],
                "vision_rejected_pages":rejected_images,
                "vision_incomplete":bool(extension==".pdf" and pdf_vision and
                                          (len(page_numbers)<count or rejected_images)),
            }
        except RejectedFile:raise
        except (httpx.HTTPError,ValueError,TypeError,KeyError,base64.binascii.Error):
            # Transparent fallback to the previous local parser.
            text,images=await asyncio.to_thread(extract_document,content,extension)
            return text,images,{"engine":"pdf-local-fallback",
                "warning":"PDF/OCR worker unavailable",
                "vision_enabled":pdf_vision,
                "vision_incomplete":bool(extension==".pdf" and pdf_vision),
                "vision_pages":len(images),
                "vision_page_numbers":list(range(1,len(images)+1)),
                "truncated":False}
    if extension in OFFICE and docling_enabled:
        try:
            payload=await _request(DOCLING_URL,extension,content)
            text=payload["text"]
            if text.strip():
                legacy=extension==".doc"
                return text[:100000],[],{
                    "engine":payload.get("engine","antiword-legacy-doc") if legacy else "docling-office",
                    "tables":payload.get("tables",0),
                    "source_pages":payload.get("page_count",0),
                    "truncated":payload.get("truncated",False) or len(text)>100000,
                    "layout_fidelity":payload.get("layout_fidelity","structured"),
                    "legacy_doc_review_required":legacy,
                    **({"warning":payload.get("warning",
                        "Stary DOC wymaga kontroli układu.")} if legacy else {}),
                }
        except RejectedFile:raise
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            if extension==".doc":
                raise RejectedFile("Moduł odczytu starego formatu DOC jest niedostępny.",503)
            text,images=await asyncio.to_thread(extract_document,content,extension)
            return text,images,{"engine":"local-fallback","warning":"Docling worker unavailable"}
    if extension==".doc":
        raise RejectedFile("Obsługa DOC wymaga izolowanego workera dokumentów.",503)
    text,images=await asyncio.to_thread(extract_document,content,extension)
    return text,images,{"engine":"local"}
