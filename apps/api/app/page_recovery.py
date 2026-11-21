"""Bounded recovery for source page JSON that exceeds a model output budget.

The failure is independent of file format. Do not drop rows, fabricate fields
or repair a document from prior example templates.
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image

from .ai_provider import generate, AIProviderError

RECOVERY_PARTS=(2,4,8)
MIN_TEXT_PART_CHARS=120


def split_source_text(text:str,parts:int)->list[str]:
    """Partition text in reading order without dropping a source character."""
    if not text:
        return ["" for _ in range(parts)]
    import math
    lines=text.splitlines(keepends=True)
    if len(lines)>=parts:
        target=max(1,math.ceil(len(text)/parts))
        groups=[]; current=""
        for line in lines:
            if current and len(groups)<parts-1 and len(current)+len(line)>target:
                groups.append(current);current=""
            current+=line
        groups.append(current)
        # Preserve text exactly; never manufacture a form field here.
        return groups
    # Extremely long OCR lines, or a single line of tabular source.
    # Split at spaces where possible, otherwise at a fixed character boundary.
    chunks=[];remaining=text
    for index in range(parts-1):
        left=parts-index
        length=max(1,(len(remaining)+left-1)//left)
        if length>=len(remaining):
            break
        limit=min(len(remaining),length+min(90,length//3))
        boundary=remaining.rfind(" ",max(1,length//2),limit)
        cut=boundary+1 if boundary>0 else length
        chunks.append(remaining[:cut])
        remaining=remaining[cut:]
    chunks.append(remaining)
    return chunks


def split_source_image(image:tuple[str,bytes]|None,parts:int)->list[tuple[str,bytes]|None]:
    """Create bounded vertical source crops, instead of reusing full page."""
    if image is None:
        return [None for _ in range(parts)]
    try:
        with Image.open(BytesIO(image[1])) as opened:
            opened.load()
            canvas=opened.convert("RGB")
            width,height=canvas.size
            if height<max(120,parts*70):
                # Too small for cropping; do not ask an LLM to infer
                # a crop's fields from the full page multiple times.
                return [image]+[None for _ in range(parts-1)]
            result=[]
            for index in range(parts):
                y0=round(index*height/parts)
                y1=round((index+1)*height/parts)
                buffer=BytesIO()
                canvas.crop((0,y0,width,y1)).save(buffer,format="JPEG",quality=86)
                result.append(("image/jpeg",buffer.getvalue()))
            return result
    except (OSError,TypeError,ValueError):
        return [image]+[None for _ in range(parts-1)]


async def generate_page_with_recovery(text:str,
                                      image:tuple[str,bytes]|None,
                                      *,prompt:str,
                                      page_number:int=1,
                                      source_text:str|None=None,
                                      model_generate=None,
                                      force_parts:int=0)->tuple[dict,dict]:
    """Retry a truncated page in smaller source-based units.

    If a chunk is also truncated, start over with more chunks.
    A chunk failure never silently drops source content.
    """
    model=model_generate or generate
    images=[image] if image else []
    if not force_parts:
        try:
            return await model(text,images,prompt=prompt)
        except AIProviderError as exc:
            if exc.code not in {"MODEL_OUTPUT_TRUNCATED","MODEL_TIMEOUT"}:
                raise
    for parts in RECOVERY_PARTS:
        if parts<force_parts:
            continue
        text_fragments=split_source_text(
            source_text if source_text is not None else text,parts)
        image_fragments=split_source_image(image,parts)
        if len(text_fragments)<parts:
            text_fragments.extend([""]*(parts-len(text_fragments)))
        accumulated=[]; model_calls=0; usage_total={}
        try:
            for index in range(parts):
                snippet=text_fragments[index].strip()
                crop=image_fragments[index]
                if not snippet and crop is None:
                    continue
                # A portion of OCR may be too small alone, but must not be
                # discarded if a corresponding image fragment exists.
                segmented=(f"ŹRÓDŁO STRONA {page_number}, CZĘŚĆ "
                           f"{index+1}/{parts}. Analizuj WYŁĄCZNIE "
                           "dostarczony fragment tekstu i ewentualny "
                           "wycinek strony. NIE powtarzaj pól spoza "
                           "fragmentu.\n\n"+snippet)
                sub,info=await model(segmented,[crop] if crop else [],prompt=prompt)
                if not isinstance(sub.get("pages"),list):
                    raise AIProviderError("Niepoprawna część odpowiedzi modelu.",
                                          code="INVALID_PAGE_INVENTORY")
                accumulated.extend(
                    sec for pg in sub.get("pages",[]) if isinstance(pg,dict)
                    for sec in pg.get("sections",[]) if isinstance(sec,dict)
                )
                model_calls+=1
                for key,val in (info.get("usage") or {}).items():
                    if isinstance(val,int):
                        usage_total[key]=usage_total.get(key,0)+val
            if accumulated:
                return {
                    "title":"Formularz",
                    "pages":[{"title":f"Strona źródłowa {page_number}",
                              "sections":accumulated}]
                },{"images_sent":sum(bool(x) for x in image_fragments),
                   "recovered_fragments":model_calls,
                   "usage":usage_total}
            # Blank pages must be valid; no fabricated fallback controls.
            return {"title":"Formularz","pages":[{"title":f"Strona źródłowa {page_number}",
                                                   "sections":[]}]},{
                       "images_sent":sum(bool(x) for x in image_fragments),
                       "recovered_fragments":model_calls,"usage":usage_total}
        except AIProviderError as exc:
            if exc.code not in {"MODEL_OUTPUT_TRUNCATED","MODEL_TIMEOUT"} or parts==RECOVERY_PARTS[-1]:
                raise
    raise AIProviderError("Nie można podzielić odpowiedzi modelu.",
                          code="MODEL_OUTPUT_TRUNCATED")