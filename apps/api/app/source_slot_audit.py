"""Independent review of short printed answer slots omitted by the first page pass.

Looks for actual dotted/underlined writable regions in OCR, including short
runs missed by the old (5+-dots) completeness counter. It asks a VLM to
confirm the printed slot on a focused image crop; never manufactures an input
from a domain dictionary or from inferred legal obligations.
"""
from __future__ import annotations

from collections import Counter
from io import BytesIO
import re
from PIL import Image

from .ai_provider import generate
from .field_grounding import norm

SHORT_BLANK=re.compile(r"(?:\.{2,}|…+|_{2,}|﹏{2,})")
MAX_MISSING=10
# Type inference depends on printed date-language/format and a REAL OCR blank,
# not any municipality, application category, or sampled field label.
PRINTED_DATE=re.compile(r"(?i)\b(?:data|dnia|date|dd[. ]mm[. ](?:rrrr|yyyy))\b")
AUDIT_PROMPT="""Audit SOURCE WIDGETS, not semantics or administrative requirements.
The supplied cropped scan is the physical evidence. OCR includes numbered
candidate lines with short dotted blanks; a previous full-page model missed
these candidate answer regions. Find ONLY physically writable blanks.
A line may have a short dotted suffix, a long dotted line, or a printed
caption BELOW the blank. Include an actual date entry at a document header.
Do not turn signatures, address blocks, instructions, legal notices, printed
units or descriptive text into user input controls.
If a candidate is an actual DATE response, use DATEPICKER, otherwise the
appropriate existing type. Never add a field without pointing to an EXACT
candidate line from the supplied OCR in 'evidence'. Never duplicate a
question from the already extracted field inventory.
Return the same {title,pages:[{title,sections:[{title,fields:[{label,type,
required:false,options:[],evidence}]}]}]} structure with ONLY missing fields,
not the previously found fields. If none, return empty sections. JSON only."""


def _fields(semantic:dict)->list[dict]:
    return [f for p in semantic.get("pages",[]) for section in p.get("sections",[])
            for f in section.get("fields",[]) if isinstance(f,dict)
            and f.get("type") not in {"INFO_BLOCK","TEXT_BLOCK"}]


def uncovered_short_blanks(text:str,semantic:dict)->list[dict]:
    """Match OCR physical blank locations to source-line-grounded fields."""
    lines=text.splitlines()
    seen=Counter()
    for field in _fields(semantic):
        line_no=field.get("source_line")
        if not isinstance(line_no,int) or not (1<=line_no<=len(lines)):
            evidence=norm(str(field.get("evidence") or "")).strip()
            if len(evidence)>=4 and evidence!="image-only":
                for i,line in enumerate(lines,1):
                    if evidence in norm(line):
                        line_no=i;break
        if isinstance(line_no,int) and line_no>=1:
            seen[line_no]+=1
    result=[]
    for i,line in enumerate(lines,1):
        matches=list(SHORT_BLANK.finditer(line))
        if not matches or not re.search(r"[\wĄąĆćĘęŁłŃńÓóŚśŹźŻż]",line):
            continue
        # Hand-written signatures are intentionally not digital input fields.
        if re.search(r"(?i)\bpodpis\b",line) and len(matches)==1:
            continue
        if len(matches)>seen[i]:
            result.append({"line":i,"text":line.strip()[:240],
                           "uncovered":len(matches)-seen[i]})
    return result[:MAX_MISSING]


def _crop_for_line(image:tuple[str,bytes],i:int,total:int)->tuple[str,bytes]|None:
    """One high-resolution crop of a page region selected by OCR order."""
    if total<2:return image
    try:
        with Image.open(BytesIO(image[1])) as src:
            src.load()
            im=src.convert("RGB")
            w,h=im.size
            if h<350:return image
            frac=(i-1)/max(1,total-1)
            if frac<.40: top,bottom=0,int(h*.52)
            elif frac>.65: top,bottom=int(h*.45),h
            else: top,bottom=int(h*.22),int(h*.82)
            stream=BytesIO()
            im.crop((0,top,w,bottom)).save(stream,format="JPEG",quality=86,optimize=True)
            if 0<len(stream.getvalue())<=4_000_000:
                return "image/jpeg",stream.getvalue()
    except (ValueError,TypeError,OSError):
        return None
    return image


def _quote_matches_line(evidence:str,line:str)->bool:
    quote=norm(str(evidence)).strip().strip(" .:")
    source=norm(line).strip().strip(" .:")
    return len(quote)>=4 and (quote in source or (len(source)>6 and source in quote))


async def recover_uncovered_slots(text:str,image:tuple[str,bytes]|None,
                                   semantic:dict, sanitize, *,source_page:int=1)->tuple[int,list[dict]]:
    candidates=uncovered_short_blanks(text,semantic)
    if not candidates or image is None:
        return 0,candidates
    lines=text.splitlines()
    primary=candidates[0]
    crop=_crop_for_line(image,primary["line"],len(lines))
    if crop is None:return 0,candidates
    prompt_input="UNACCOUNTED SOURCE OCR LINES:\n"+ "\n".join(
        f'line {x["line"]}: {x["text"]}' for x in candidates)
    prompt_input+="\nALREADY EXTRACTED FIELD LABELS:\n"+ "\n".join(
        str(f.get("label",""))[:160] for f in _fields(semantic)[:90])
    proposal,_=await generate(prompt_input,[crop],prompt=AUDIT_PROMPT)
    new=sanitize(proposal)
    new_fields=_fields(new)
    accepted=[]
    used=Counter()
    candidates_by_line={x["line"]:x for x in candidates}
    for f in new_fields:
        evidence=str(f.get("evidence") or "")
        source_line=next((i for i in candidates_by_line
                          if _quote_matches_line(evidence,lines[i-1])),None)
        if source_line is None:continue
        if used[source_line]>=candidates_by_line[source_line]["uncovered"]:
            continue
        label=norm(str(f.get("label",""))).strip()
        if any(norm(str(existing.get("label",""))).strip()==label
               and existing.get("source_line")==source_line
               for existing in _fields(semantic)):
            continue
        f["source_line"]=source_line
        f["source_page"]=source_page
        left=lines[source_line-1].split(SHORT_BLANK.search(lines[source_line-1]).group(),1)[0]
        if PRINTED_DATE.search(norm(left)) and f.get("type")=="TEXT_FIELD":
            f["type"]="DATEPICKER"
        f["source"]="source_slot_visual_audit"
        accepted.append(f)
        used[source_line]+=1
    # Conservative OCR-based date fallback for a genuine, unresolved printed
    # date blank. The source phrase is copied verbatim, with no known form
    # names or preconfigured question list. The model audit already ran.
    for line_no,row in candidates_by_line.items():
        if used[line_no]>=row["uncovered"]:
            continue
        line=lines[line_no-1]
        blank=SHORT_BLANK.search(line)
        if blank is None or not PRINTED_DATE.search(norm(line[:blank.start()])):
            continue
        label=line[:blank.start()].strip(" .:_-")
        if len(label)<4:continue
        accepted.append({"label":label[:220],"type":"DATEPICKER",
            "required":False,"options":[],"evidence":line[:260],
            "source_line":line_no,"source_page":source_page,
            "source":"source_ocr_date_slot"})
        used[line_no]+=1
    if accepted:
        if not semantic.get("pages"):
            semantic["pages"]=[{"title":"Dokument źródłowy","sections":[]}]
        # Reuse the nearest existing physical section if its fields occur
        # within a small OCR-line distance. Otherwise create a new section.
        # Do not make every fallback into another generic fieldset.
        sections=semantic["pages"][0].setdefault("sections",[])
        orphan=[]
        for value in accepted:
            candidates=[]
            for section in sections:
                line_nos=[f.get("source_line") for f in section.get("fields",[])
                          if isinstance(f.get("source_line"),int)]
                if line_nos:
                    candidates.append((min(abs(value["source_line"]-line)
                                           for line in line_nos),section))
            nearest=min(candidates,key=lambda x:x[0]) if candidates else None
            if nearest and nearest[0]<=5:
                nearest[1]["fields"].append(value)
                nearest[1]["fields"].sort(key=lambda f:f.get("source_line",10**6))
            else:
                orphan.append(value)
        if orphan:
            sections.append({"title":"Pola z dokumentu źródłowego",
                             "fields":orphan})
        def first_line(section):
            return min((f.get("source_line",10**6)
                        for f in section.get("fields",[])),default=10**6)
        sections.sort(key=first_line)
    return len(accepted),candidates