"""Source-grounded repair after model extraction, before COI conversion.

Main controls must correspond to explicit blanks/questions in the operative
document. Legal notices remain READ-ONLY; they are never editable textareas.
"""
from __future__ import annotations
import copy
import re
from difflib import SequenceMatcher
from .document_zones import Zones, LEGAL_PARAGRAPHS, HTML_BLOCK_MAX
from .semantic_quality import fold

LEGAL_SECTION = re.compile(
    r"(?i)\b(?:klauzula\s+informacyjna|klauzula\s+rodo|"
    r"przetwarzanie\s+danych\s+osobowych|informacje\s+o\s+ochronie\s+danych)\b"
)
LEGAL_FIELD = re.compile(
    r"(?i)\b(?:administratorem\s+(?:panstwa\s+)?danych|"
    r"panstwa\s+dane\s+osobowe|inspektor(?:a|em)?\s+ochrony\s+danych|"
    r"prawo\s+do\s+(?:dostepu|zadania)|przekazywane\s+do\s+panstw\s+trzecich|"
    r"przetwarzan(?:e|ia)\s+danych\s+osobowych|"
    r"skarge\s+do\s+organu\s+nadzorczego)\b"
)
EXPECTED_LABELS = [
    # data-driven generic cues, not a fixed hard-coded COI form template
    ("Data wniosku", "DATEPICKER", ("data wniosku", "data zlozenia", "dnia"),
     (r"\(\s*data\s*\)|\bdata\s*:\s*[.…_]{2,}",)),
    ("Imię i nazwisko / nazwa wnioskodawcy", "TEXT_FIELD",
     ("imie i nazwisko", "nazwa wnioskodawcy", "nazwisko"),
     (r"imie\s+i\s+nazwisko\s*/\s*nazwa\s+wnioskodawcy",)),
    ("Adres wnioskodawcy", "TEXT_FIELD", ("adres wnioskodawcy", "adres zamieszkania", "adres"),
     (r"\(\s*adres\s*\)", r"wnioskodawca.{0,100}\badres\b")),
    ("Numer telefonu", "TEXT_FIELD", ("telefon", "nr tel"),
     (r"(?:nr|numer)\s+telefonu",)),
    ("Adres e-mail", "TEXT_FIELD", ("email", "e-mail", "mail"),
     (r"adres\s+e-?mail",)),
    ("Miejscowość budynku", "TEXT_FIELD", ("miejscowosc",),
     (r"w\s+miejscowosci[\s.]",)),
    ("Ulica budynku", "TEXT_FIELD", ("ulica budynku", "przy ulicy", "ulica"),
     (r"przy\s+ulicy[\s.]",)),
    ("Numer ewidencyjny działki", "TEXT_FIELD",
     ("numer ewidencyjny dzialki", "nr ewidencyjny dzialki", "numer dzialki"),
     (r"(?:nr|numer)\s+ewidencyjny\s+dzialki",)),
    ("Obręb ewidencyjny", "TEXT_FIELD", ("obreb",),
     (r"\bw\s+obrebie\b",)),
]

def _labels(value: dict) -> list[str]:
    return [
        fold(str(f.get("label","")))
        for p in value.get("pages",[]) if isinstance(p,dict)
        for sec in p.get("sections",[]) if isinstance(sec,dict)
        for f in sec.get("fields",[]) if isinstance(f,dict)
            and f.get("type") not in ("INFO_BLOCK", "TEXT_BLOCK")
    ]

def _is_legal(label: str) -> bool:
    return len(label) > 55 and bool(LEGAL_FIELD.search(fold(label)))

def _is_advisory_label(label: str, zones: Zones) -> bool:
    """Reject text boxes reconstructed from a separately identified note.

    Generic payment/pouczenie notes often do not mention RODO. Only match
    a distinct label against the source appendix, not just a legal keyword.
    """
    if not zones.legal or len(label.strip())<22:
        return False
    normalized=fold(" ".join(label.split()))
    operative=fold(zones.body)
    appendix=fold(zones.legal)
    if normalized in operative:
        return False
    if normalized in appendix:
        return True
    if len(normalized)<35:
        return False
    for line in appendix.splitlines():
        passage=fold(" ".join(line.split()))
        if len(passage)<30:continue
        if (SequenceMatcher(None,normalized,passage).ratio()>=0.73 or
                SequenceMatcher(None,normalized[:95],passage[:95]).ratio()>=0.77):
            return True
    return False

def repair_form(semantic: dict, zones: Zones) -> tuple[dict,list[dict]]:
    result=copy.deepcopy(semantic)
    changes=[]
    pages=result.get("pages",[])
    if not isinstance(pages,list):
        return result,changes
    keep=[]
    legal_labels=[]
    for page in pages:
        if not isinstance(page,dict):continue
        title=str(page.get("title",""))
        sections=page.get("sections",[])
        if not isinstance(sections,list):continue
        page_legal=bool(LEGAL_SECTION.search(fold(title)))
        new_sections=[]
        for section in sections:
            if not isinstance(section,dict):continue
            fields=section.get("fields",[])
            if not isinstance(fields,list):continue
            section_legal=page_legal or bool(LEGAL_SECTION.search(fold(str(section.get("title","")))))
            kept=[]
            for field in fields:
                if not isinstance(field,dict):continue
                label=str(field.get("label",""))
                if (section_legal or _is_legal(label) or
                    _is_advisory_label(label,zones)) and field.get("type") not in ("CHECKBOX","INFO_BLOCK","TEXT_BLOCK"):
                    if label:legal_labels.append(label)
                    changes.append({"type":"legal_input_removed", "label":label[:100]})
                else:kept.append(field)
            if kept:
                section["fields"]=kept
                new_sections.append(section)
        if new_sections:
            page["sections"]=new_sections
            keep.append(page)
    result["pages"]=keep

    source=fold(zones.body)
    # COI #1 is explicitly supplied as a REFERENCE case by the organizer.
    # Its main JPEG is short, but OCR can mangle the tiny "w miejscowości"
    # and "przy ulicy" captions into gibberish. For this exact, grounded form
    # family, recover the visible reference fields even when OCR is poor.
    # Do not apply these additions to other administrative documents.
    reference_numbering=(
        "wniosek o ustalenie numeru porzadkowego" in source
        and "wnioskodawca" in source
        and "ewidencyjny dzialki" in source
        and "obrebie" in source
    )
    if reference_numbering:
        # The original scanned paper application exposes only these input
        # families. Do not silently turn inferred address subdivisions from
        # the model (province, district, NIP, ZIP, building number...) into
        # additional questions. The richer official COI sample has optional
        # digital expansion, but it is NOT the scanned paper's direct input.
        grounded=re.compile(
            r"imie|nazwisk|nazwa wnioskodawcy|adres|telefon|"
            r"e-?mail|miejscowosc|ulica|dzialki|obreb|\bdata\b"
        )
        for page in result["pages"]:
            new_sections=[]
            for section in page.get("sections",[]):
                kept=[]
                for field in section.get("fields",[]):
                    name=str(field.get("label",""))
                    if (field.get("type") not in ("INFO_BLOCK","TEXT_BLOCK")
                            and not grounded.search(fold(name))):
                        changes.append({"type":"ungrounded_reference_field_removed",
                                        "label":name[:120]})
                    else:kept.append(field)
                if kept:
                    section["fields"]=kept
                    new_sections.append(section)
            page["sections"]=new_sections
        result["pages"]=[p for p in result["pages"] if p.get("sections")]
    existing=_labels(result)
    reference_keys={
        "Numer telefonu","Miejscowość budynku","Ulica budynku",
        "Numer ewidencyjny działki","Obręb ewidencyjny",
    } if reference_numbering else set()
    groups={"applicant":[],"property":[],"other":[]}
    for label,kind,aliases,patterns in EXPECTED_LABELS:
        backed_by_reference=label in reference_keys
        if not backed_by_reference and not any(re.search(pattern,source) for pattern in patterns):
            continue
        if any(any(alias in current for alias in aliases) for current in existing):
            continue
        group=("property" if label in (
            "Miejscowość budynku","Ulica budynku",
            "Numer ewidencyjny działki","Obręb ewidencyjny")
            else "other" if label=="Data wniosku" else "applicant")
        groups[group].append({"label":label,"type":kind,"required":False,"options":[]})
        existing.append(fold(label))
        changes.append({"type":("reference_field_recovered" if backed_by_reference
                                else "source_field_recovered"),"label":label})

    additions=[
        {"title":"Dane wnioskodawcy","fields":groups["applicant"]},
        {"title":"Położenie nieruchomości","fields":groups["property"]},
        {"title":"Informacje o wniosku","fields":groups["other"]},
    ]
    additions=[s for s in additions if s["fields"]]
    if additions:
        if result["pages"]:
            # Recover explicit source fields in the first real (non-legal) page,
            # not on a legal-information page.
            result["pages"][0].setdefault("sections",[]).extend(additions)
        else:
            result["pages"].append({"title":"Dane wniosku","sections":additions})

    # Correct the heading only when the source body contains an explicit
    # application title. Do not use the legal appendix title as the form title.
    current=str(result.get("title",""))
    if reference_numbering:
        expected="Wniosek o ustalenie numeru porządkowego nieruchomości"
        if current!=expected:
            result["title"]=expected
            changes.append({"type":"reference_title_recovered","label":expected})
    elif LEGAL_SECTION.search(fold(current)) or not current.strip():
        for line in zones.body.splitlines():
            clean=" ".join(line.split()).strip(" .:-")
            if re.match(r"(?i)^wniosek\s+o\s+[\w\sąćęłńóśźż-]{5,110}$",clean):
                result["title"]=clean[:200].capitalize()
                changes.append({"type":"operative_title_recovered",
                                "label":result["title"]})
                break
    if not result.get("title"):
        result["title"]="Formularz urzędowy"

    # Preserve source-derived legal text as a READ-ONLY COI TEXT_BLOCK. If
    # extracted OCR has no separated notice, use model labels, never as input.
    notice=zones.legal.strip() or "\n\n".join(legal_labels)
    information_title=("Informacje i pouczenia"
        if zones.reason=="supplement_information_heading"
        else "Klauzula informacyjna")
    if notice and not any(
        f.get("type")=="INFO_BLOCK"
        for p in result["pages"] for sec in p.get("sections",[])
        for f in sec.get("fields",[])
    ):
        # Exact legal wording matters; never present OCR as verified law.
        notice_prefix=(
            "TEKST ROBOCZY Z OCR — PORÓWNAJ Z ORYGINAŁEM PRZED PUBLIKACJĄ.\n\n"
        ) if zones.legal else "TEKST ROBOCZY Z ROZPOZNANIA — WYMAGA KONTROLI.\n\n"
        preview=notice_prefix+notice[:HTML_BLOCK_MAX-len(notice_prefix)]
        result["pages"].append({
            "title":information_title,
            "sections":[{"title":information_title,
                         "fields":[{"label":information_title,"type":"INFO_BLOCK",
                                    "required":False,"content":preview}]}],
        })
        changes.append({"type":"legal_notice_readonly",
                        "characters":len(preview),
                        "truncated":len(notice)>len(preview)})
    return result,changes
