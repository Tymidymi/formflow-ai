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
MAX_OCR_PAGES=12
MAX_TEXT_CHARS=100000
MAX_IMAGE_PIXELS=5_000_000
MAX_PREVIEW_PAGES=12

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

def jpeg_preview(img:Image.Image, page_number:int|None=None)->dict:
    if img.width*img.height>MAX_IMAGE_PIXELS:
        img=prepare_image(img)
    out=io.BytesIO()
    img.convert("RGB").save(out,format="JPEG",quality=68,optimize=True)
    if out.tell()>1_500_000:
        raise PdfExtractionError("Przekroczony limit podglądu strony.",413)
    response={"mime":"image/jpeg","base64":base64.b64encode(out.getvalue()).decode("ascii")}
    if page_number is not None:
        response["page"]=page_number
    return response

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
                previews.append(jpeg_preview(image,page_number=i+1))
        elif include_previews and len(previews)<MAX_PREVIEW_PAGES:
            image=_render_pdf(data,i)
            previews.append(jpeg_preview(image,page_number=i+1))
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
        "preview_page_numbers":[item["page"] for item in previews],
        "vision_incomplete":bool(include_previews and count>len(previews)),
    }

def detect_stitched_image_parts(img:Image.Image)->list[Image.Image]:
    """Split tall concatenated scans at a mid-page blank separator.

    Preserve BOTH regions in OCR; this never discards legal appendices.
    Restrict to a single well-evidenced 2-part layout, avoiding arbitrary
    splitting of normal one-page documents with short empty lines.
    """
    w,h=img.size
    if h<1400 or h<1.8*w:
        return [img]
    gray=img.convert("L")
    if w>700:
        scale=700/w
        thumb=gray.resize((700,int(h*scale)),Image.Resampling.BILINEAR)
    else:
        thumb=gray
    sw,sh=thumb.size
    bitmap=thumb.point(lambda v: 255 if v>=185 else 0).convert("1")
    data=bitmap.tobytes();stride=(sw+7)//8
    rows=[sum(8-b.bit_count() for b in data[y*stride:(y+1)*stride])
          for y in range(sh)]
    start=None;runs=[]
    for y in range(int(sh*.30),int(sh*.78)):
        if rows[y]<=max(10,int(sw*.015)):
            if start is None:start=y
        elif start is not None:
            if y-start>=int(sh*.05):runs.append((start,y))
            start=None
    if start is not None and int(sh*.78)-start>=int(sh*.05):
        runs.append((start,int(sh*.78)))
    if not runs:return [img]
    # Prefer whitespace near the middle of the stitched scan rather than
    # an earlier empty block within the main paper application.
    a,b=min(runs,key=lambda ab:abs((ab[0]+ab[1])/2-sh*.5))
    cut=int((a+b)/2*h/sh)
    if not (int(h*.25)<cut<int(h*.85)):
        return [img]
    return [img.crop((0,0,w,cut)),img.crop((0,cut,w,h))]


def image_extract(data:bytes,extension:str,include_previews:bool=False)->dict:
    try:
        Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS*3
        im=Image.open(io.BytesIO(data))
        im.load()
        if im.width*im.height>MAX_IMAGE_PIXELS*4:
            raise PdfExtractionError("Obraz przekracza maksymalny rozmiar.",413)
        parts=detect_stitched_image_parts(im)
        if len(parts)>1:
            texts=[tesseract_text(part) for part in parts]
            text="\n\n".join(f"[Część {i+1}/{len(parts)}]\n"+v for i,v in enumerate(texts))
        else:
            text=tesseract_text(im)
        previews=[jpeg_preview(im)] if include_previews else []
    except PdfExtractionError:raise
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
        raise PdfExtractionError("Obraz jest uszkodzony lub nieobsługiwany.",422) from exc
    return {
        "engine":"tesseract-pol+eng","format":extension,"text":text[:MAX_TEXT_CHARS],
        "truncated":len(text)>MAX_TEXT_CHARS,"page_count":1,
        "ocr_pages":1,"page_sources":[{"page":1,"method":"tesseract-pol+eng",
            "characters":len(text),"regions":len(parts)}],
        "preview_images":previews,
    }
