"""Partition administrative form input from separate read-only legal notices.

Legal notices (RODO/information clauses) can be longer than the actual form.
We must never ask a language model to interpret those legal paragraphs as
user-input controls. No legal content is silently discarded: the full notice is
preserved in a read-only COI TEXT_BLOCK after extraction.
"""
from __future__ import annotations
import io
import re
from dataclasses import dataclass
from PIL import Image, ImageOps

LEGAL_HEADER = re.compile(
    r"(?im)^\s*(?:KLAUZULA\s+(?:INFORMACYJNA|RODO)|"
    r"INFORMACJ[AE]\s+O\s+PRZETWARZANIU\s+DANYCH\s+OSOBOWYCH|"
    r"KLAUZULA\s+O\s+OCHRONIE\s+DANYCH)\b[^\n]{0,90}$"
)
# Short, standalone advisory sections at the END of an application are
# informational, even when they are not explicitly GDPR disclosures.
ADVISORY_HEADER = re.compile(
    r"(?im)^\s*(?:INFORMACJE(?:\s+DODATKOWE)?|POUCZENIE|"
    r"OBJAŚNIENIA|OBJAŚNIENIE)\s*:?\s*$"
)
LEGAL_PARAGRAPHS = re.compile(
    r"(?i)\b(?:RODO|przetwarzani[ae]\s+danych\s+osobowych|"
    r"administratorem\s+(?:p[ań]stwa\s+)?danych|"
    r"inspektor(?:a|em)?\s+ochrony\s+danych)\b"
)
OPERATIVE = re.compile(
    r"(?i)\b(?:wniosek|wnosz[eę]|wnioskodawca|dzia[lł]ki|"
    r"nieruchomo[sś]ci|dotycz[aą]cy|prosz[eę])\b"
)
HTML_BLOCK_MAX = 7000

@dataclass(frozen=True)
class Zones:
    body: str
    legal: str
    was_split: bool
    reason: str = ""

def split_legal_notice(text: str) -> Zones:
    if not isinstance(text, str) or not text.strip():
        return Zones("", "", False)
    for match in LEGAL_HEADER.finditer(text):
        body = text[:match.start()].rstrip()
        legal = text[match.start():].strip()
        if len(body) >= 45 and OPERATIVE.search(body) and len(legal) >= 120:
            return Zones(body, legal, True, "explicit_legal_heading")
    # GDPR information may start directly with a legal citation, without
    # a separate "KLAUZULA INFORMACYJNA" heading. Keep it read-only.
    article13=re.compile(r"(?im)^\s*zgodnie\s+z\s+art\.?\s*13\b[^\n]*$")
    for match in article13.finditer(text):
        body=text[:match.start()].rstrip()
        appendix=text[match.start():].strip()
        if (len(body)>=100 and len(appendix)>=160 and OPERATIVE.search(body)
                and LEGAL_PARAGRAPHS.search(appendix[:1100])):
            return Zones(body,appendix,True,"gdpr_legal_citation")
    for match in ADVISORY_HEADER.finditer(text):
        body=text[:match.start()].rstrip()
        appendix=text[match.start():].strip()
        # Avoid cutting "INFORMACJE" sections that are actual questions in
        # the middle of a form: only a final advisory heading is recognized.
        if (len(body)>=130 and match.start()>=len(text)*0.34 and
                OPERATIVE.search(body) and len(appendix)>=110 and
                not re.search(r"(?im)^\s*WNIOSEK\b",appendix)):
            return Zones(body,appendix,True,"supplement_information_heading")
    return Zones(text, "", False)

def _ink_rows(img: Image.Image) -> list[int]:
    # Fast 1-bit threshold avoids numpy. Bound input dimensions before use.
    thumb = img.convert("L")
    if thumb.width > 900:
        thumb.thumbnail((900, 6000), Image.Resampling.LANCZOS)
    pixels = thumb.point(lambda n: 255 if n >= 190 else 0).convert("1")
    w, h = pixels.size
    data = pixels.tobytes()
    stride = (w + 7) // 8
    # A sparse line of text has many nonwhite pixels, unlike white page gutters.
    result = []
    for y in range(h):
        line = data[y * stride : (y + 1) * stride]
        nonwhite = sum(8 - b.bit_count() for b in line)
        result.append(nonwhite)
    return result

def primary_image_crop(content: bytes, extension: str, zones: Zones) -> tuple[bytes, dict]:
    """Crop a tall stitched scan at a sizeable whitespace gap before the notice.

    Restrict to explicit legal headings in source OCR. Never crop other images,
    and never remove the source content from the local extraction or original.
    This crop is only the visual evidence submitted to the language model.
    """
    if not zones.was_split or extension not in (".png", ".jpg", ".jpeg"):
        return content, {"vision_cropped": False}
    with Image.open(io.BytesIO(content)) as raw:
        raw.load()
        w,h = raw.size
        if h < 1000 or h < 1.7*w or w*h > 8_000_000:
            return content, {"vision_cropped": False}
        rows = _ink_rows(raw)
        scale = h / len(rows)
        low=int(len(rows)*0.23);high=int(len(rows)*0.78)
        runs=[];start=None
        for y in range(low,high):
            if rows[y] <= max(10,int(w*0.015)):
                if start is None:start=y
            elif start is not None:
                runs.append((start,y))
                start=None
        if start is not None:runs.append((start,high))
        # Prefer gap around body/notice boundary, not page footer blank margins.
        candidates=[(b-a,a,b) for a,b in runs if (b-a)*scale>=72]
        if not candidates:return content,{"vision_cropped":False}
        length,start,end=max(candidates)
        cut=int((start+end)/2*scale)
        if cut<=int(h*.25) or cut>=int(h*.85):
            return content,{"vision_cropped":False}
        im=ImageOps.autocontrast(raw.convert("RGB").crop((0,0,w,cut)))
        if im.width < 1000:
            factor=min(1.6,1400/im.width)
            im=im.resize((int(im.width*factor),int(im.height*factor)),
                         Image.Resampling.LANCZOS)
        out=io.BytesIO()
        im.save(out,format="JPEG",quality=82,optimize=True)
        return out.getvalue(),{
            "vision_cropped":True,
            "vision_crop_height":cut,
            "vision_original_height":h,
            "vision_crop_reason":"separate_legal_notice",
        }


def suppress_readonly_source_controls(semantic:dict, body:str, notice:str)->int:
    """Drop model-invented inputs that originate only inside read-only text.

    Match page/section/field evidence to the actual split source zones, never
    to an administrative form title, municipality, or a known field list.
    Fields also grounded in the operative part are retained.
    """
    if not notice.strip():
        return 0
    from .field_grounding import norm
    active=norm(body)
    passive=norm(notice)
    def unique_notice_phrase(value:object)->bool:
        phrase=norm(str(value or '')).strip().strip(' .:;')
        return (len(phrase)>=5 and phrase!='image-only'
                and phrase in passive and phrase not in active)
    removed=0
    for page in semantic.get('pages',[]):
        for section in page.get('sections',[]):
            section_only=unique_notice_phrase(section.get('title'))
            kept=[]
            for field in section.get('fields',[]):
                source=field.get('evidence') or ''
                field_only=unique_notice_phrase(source) or unique_notice_phrase(field.get('label'))
                active_evidence=source and norm(str(source)).strip() in active
                if (field.get('type') not in ('INFO_BLOCK','TEXT_BLOCK')
                    and not active_evidence and (field_only or section_only)):
                    removed+=1
                    continue
                kept.append(field)
            section['fields']=kept
        page['sections']=[s for s in page.get('sections',[]) if s.get('fields')]
    return removed
