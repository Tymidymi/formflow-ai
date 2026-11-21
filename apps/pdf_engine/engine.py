"""Memory-bounded local PDF layout extraction and Polish OCR (no external API).

Text PDF -> pypdf layout mode, preserving line layout and checkbox markers.
Scanned PDF / PNG / JPG -> PDFium/Pillow render + Tesseract pol+eng.
Returns page provenance and explicit truncation state.
"""
from __future__ import annotations

import base64
import io
import re
import subprocess
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

MAX_PAGES=25
MAX_OCR_PAGES=4
MAX_TEXT_CHARS=18000
MAX_IMAGE_PIXELS=5_000_000
MAX_PREVIEW_PAGES=2

class PdfExtractionError(Exception):
    def __init__(self, message: str, code: int=422):
        super().__init__(message)
        self.code=code

def normalize_text(value:str)->str:
    value=value.replace("\uf0f0","☐").replace("\u25a1","☐")
    value=value.replace("\u2610","☐").replace("\r","\n").replace("\x00","")
    # Preserve indentation/line breaks; only trim unreasonably wide blank runs.
    return re.sub(r"[ \t]{180,}", " "*10, value).strip()

def prepare_image(img:Image.Image)->Image.Image:
    if img.width*img.height>MAX_IMAGE_PIXELS:
        scale=(MAX_IMAGE_PIXELS/(img.width*img.height))**0.5
        img=img.resize((max(1,int(img.width*scale)),max(1,int(img.height*scale))),
                       Image.Resampling.LANCZOS)
    return ImageOps.autocontrast(img.convert("L"))

def jpeg_preview(img:Image.Image)->dict:
    if img.width*img.height>MAX_IMAGE_PIXELS:
        img=prepare_image(img)
    out=io.BytesIO()
    img.convert("RGB").save(out,format="JPEG",quality=68,optimize=True)
    if out.tell()>1_500_000:
        raise PdfExtractionError("Przekroczony limit podglądu strony.",413)
    return {"mime":"image/jpeg","base64":base64.b64encode(out.getvalue()).decode("ascii")}

def tesseract_text(img:Image.Image)->str:
    converted=prepare_image(img)
    out=io.BytesIO()
    converted.save(out,format="PNG",optimize=True)
    try:
        process=subprocess.run(
            ["tesseract","stdin","stdout","--dpi","170","-l","pol+eng","--psm","6"],
            input=out.getvalue(),capture_output=True,timeout=20,
            env={"PATH":"/usr/bin:/bin","OMP_THREAD_LIMIT":"1","LC_ALL":"C.UTF-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise PdfExtractionError("Przekroczono limit OCR strony.",422) from exc
    except OSError as exc:
        raise PdfExtractionError("Lokalny silnik OCR jest niedostępny.",503) from exc
    if process.returncode != 0:
        raise PdfExtractionError("Nie udało się odczytać strony przez OCR.",422)
    return normalize_text(process.stdout.decode("utf-8",errors="replace"))

def _render_pdf(data:bytes,index:int)->Image.Image:
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(data)
    try:
        page=doc[index]
        image=page.render(scale=1.9).to_pil().convert("RGB")
        page.close()
        return image
    finally:
        doc.close()

def pdf_extract(data:bytes, include_previews:bool=False)->dict:
    try:
        pdf=PdfReader(io.BytesIO(data),strict=False)
        if pdf.is_encrypted:
            raise PdfExtractionError("PDF jest zaszyfrowany.",422)
        count=len(pdf.pages)
        if count>MAX_PAGES:raise PdfExtractionError("PDF ma zbyt wiele stron.",413)
        if count<1:raise PdfExtractionError("PDF nie zawiera stron.",422)
    except PdfExtractionError:raise
    except Exception as exc:
        raise PdfExtractionError("Nie można otworzyć PDF.",422) from exc
    pages=[];blocks=[];previews=[];ocr=0
    for i,page in enumerate(pdf.pages):
        try:
            raw=page.extract_text(extraction_mode="layout") or ""
        except Exception:
            raw=""
        raw=normalize_text(raw)
        layout_chars=len(raw)
        method="pypdf-layout"
        if len(re.sub(r"\W","",raw))<12:
            if ocr>=MAX_OCR_PAGES:
                raise PdfExtractionError("Zbyt wiele stron wymagających OCR.",413)
            image=_render_pdf(data,i)
            raw=tesseract_text(image)
            method="tesseract-pol+eng"
            ocr+=1
            if include_previews and len(previews)<MAX_PREVIEW_PAGES:
                previews.append(jpeg_preview(image))
        elif include_previews and len(previews)<MAX_PREVIEW_PAGES:
            image=_render_pdf(data,i)
            previews.append(jpeg_preview(image))
        pages.append({"page":i+1,"method":method,"characters":len(raw),
                      "checkboxes":raw.count("☐"),"source_text_chars":layout_chars})
        blocks.append(f"[Strona {i+1}/{count}]\n"+raw)
    all_text="\n\n".join(blocks)
    if not all_text.strip():
        raise PdfExtractionError("Nie udało się rozpoznać tekstu PDF.",422)
    return {
        "engine":"pdf-layout-ocr","format":".pdf","text":all_text[:MAX_TEXT_CHARS],
        "truncated":len(all_text)>MAX_TEXT_CHARS,"page_count":count,
        "ocr_pages":ocr,"page_sources":pages,"preview_images":previews,
    }

def image_extract(data:bytes,extension:str,include_previews:bool=False)->dict:
    try:
        Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS*3
        im=Image.open(io.BytesIO(data))
        im.load()
        if im.width*im.height>MAX_IMAGE_PIXELS*4:
            raise PdfExtractionError("Obraz przekracza maksymalny rozmiar.",413)
        text=tesseract_text(im)
        previews=[jpeg_preview(im)] if include_previews else []
    except PdfExtractionError:raise
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
        raise PdfExtractionError("Obraz jest uszkodzony lub nieobsługiwany.",422) from exc
    return {
        "engine":"tesseract-pol+eng","format":extension,"text":text[:MAX_TEXT_CHARS],
        "truncated":len(text)>MAX_TEXT_CHARS,"page_count":1,
        "ocr_pages":1,"page_sources":[{"page":1,"method":"tesseract-pol+eng","characters":len(text)}],
        "preview_images":previews,
    }
