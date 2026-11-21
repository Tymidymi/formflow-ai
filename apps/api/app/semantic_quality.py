"""Conservative, source-grounded semantic normalization before exporting COI JSON.

This does NOT infer legal obligation, consent, conditional JSONata rules, or
values absent in the original document. All automatic edits are recorded.
"""
from __future__ import annotations

import copy
import re
import unicodedata

def fold(value:str)->str:
    return unicodedata.normalize("NFKD",value.translate(str.maketrans("Łł", "Ll"))).encode("ascii","ignore").decode("ascii").lower()

SIGNATURE=re.compile(r"^(?:czytelny\s+)?podpis(?:\s+wnioskodawcy)?$",re.I)

def _fields(data:dict)->list[dict]:
    return [f for p in data.get("pages",[]) if isinstance(p,dict)
            for sec in p.get("sections",[]) if isinstance(sec,dict)
            for f in sec.get("fields",[]) if isinstance(f,dict)]

def normalize_semantic(source:str,semantic:dict)->tuple[dict,list[dict]]:
    value=copy.deepcopy(semantic)
    changes=[]
    if not isinstance(value.get("pages"),list) or not value["pages"]:
        return value,changes
    src=fold(source)
    sections=[sec for p in value["pages"] if isinstance(p,dict)
              for sec in p.get("sections",[]) if isinstance(sec,dict)]
    if not sections:return value,changes
    first=sections[0]

    # Exclude paper-only ink signature placeholders from interactive eForms.
    for sec in sections:
        collection=sec.get("fields",[])
        if not isinstance(collection,list):continue
        kept=[]
        for item in collection:
            if isinstance(item,dict) and SIGNATURE.fullmatch(fold(str(item.get("label",""))).strip()):
                changes.append({"type":"paper_signature_removed","label":item["label"]})
            else:
                kept.append(item)
        sec["fields"]=kept

    # Explicit applicant labels rendered beneath their dotted lines in PDFs.
    rules=[
        ("Imię i nazwisko",r"(?m)^\s*[/\(]\s*imie i nazwisko\b",("imie i nazwisko","nazwisko")),
        ("Adres",r"(?m)^\s*[/\(]\s*adres(?:\s+zamieszkania)?\b",("adres","zamieszkania")),
        ("PESEL",r"(?m)^\s*[/\(]\s*pesel\b",("pesel",)),
        ("Nr telefonu",r"(?m)^\s*[/\(]\s*(?:nr\s+)?telefonu?\b",("telefon","tel")),
    ]
    for label,pattern,aliases in rules:
        if not re.search(pattern,src):continue
        current=[fold(str(f.get("label",""))) for f in _fields(value)]
        if any(any(alias in lab for alias in aliases) for lab in current):continue
        first.setdefault("fields",[]).append(
            {"label":label,"type":"TEXT_FIELD","required":False,"options":[]})
        changes.append({"type":"explicit_label_recovered","label":label,"source_pattern":pattern})

    # Split a composite place/date label first; it should yield exactly one
    # date, not two duplicate submission dates.
    for f in list(_fields(value)):
        label=fold(str(f.get("label","")))
        if "miejscowosc i data" in label:
            f["label"]="Miejscowość"
            f["type"]="TEXT_FIELD"
            first.setdefault("fields",[]).append(
                {"label":"Data wniosku","type":"DATEPICKER","required":False,"options":[]})
            changes.append({"type":"split_place_and_date","label":label})
            break
    all_fields=_fields(value)
    has_date=any(f.get("type")=="DATEPICKER" for f in all_fields)
    if not has_date and (re.search(r"\bdnia.{0,35}[.…]{2,}",source,flags=re.I) or
                         re.search(r"\(miejscowosc i data\)",src)):
        first.setdefault("fields",[]).append(
            {"label":"Data złożenia wniosku","type":"DATEPICKER","required":False,"options":[]})
        changes.append({"type":"date_placeholder_recovered","label":"Data złożenia wniosku"})

    # Numerically meaningful input should be NUMBER, preserving names/formatting.
    for f in _fields(value):
        lab=fold(str(f.get("label","")))
        if re.search(r"(?:liczba|ilosc|przewidywana ilosc)\s+(?:uczestnik|osob)",lab):
            if f.get("type")=="TEXT_FIELD":
                f["type"]="NUMBER"
                changes.append({"type":"numeric_type_corrected","label":f.get("label")})

    # Paper 'wynajem/użyczenie' explicitly offers two choices; require a choice
    # field, without rewriting the location where the hall is requested.
    if re.search(r"wynajem/uzyczenie|wynajecie/uzyczenie",src):
        fields=_fields(value)
        has_choice=any(
            f.get("type") in ("RADIO","SELECT") and
            {fold(str(o)) for o in f.get("options",[])} & {"wynajem","uzyczenie"}
            for f in fields
        )
        if not has_choice:
            first.setdefault("fields",[]).append(
                {"label":"Forma udostępnienia świetlicy","type":"RADIO",
                 "required":False,"options":["wynajem","użyczenie"]})
            changes.append({"type":"explicit_alternatives_recovered",
                            "label":"Forma udostępnienia świetlicy"})

    # A submission date must not count as start or end of a rental period.
    if re.search(r"terminie\s+od\b.{0,140}\bdo\b",src,flags=re.S):
        date_labels=[fold(str(f.get("label",""))) for f in _fields(value)
                     if f.get("type")=="DATEPICKER"]
        has_start=any(re.search(r"\b(?:od|start|rozpoczec\w*|poczatek)\b",lab)
                      for lab in date_labels)
        has_end=any(re.search(r"\b(?:do|koniec|zakoncz\w*)\b",lab)
                    for lab in date_labels)
        for missing,label in [(not has_start,"Data rozpoczęcia wynajmu"),
                              (not has_end,"Data zakończenia wynajmu")]:
            if missing:
                first.setdefault("fields",[]).append(
                    {"label":label,"type":"DATEPICKER","required":False,"options":[]})
                changes.append({"type":"date_range_recovered","label":label})

    return value,changes
