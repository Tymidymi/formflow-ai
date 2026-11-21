"""Source-derived conversion completeness checks, independent of form category.

No example-specific fields. A correct COI JSON Schema is not evidence that the
underlying paper form has been faithfully digitized.
"""
from __future__ import annotations

from .structured_extraction import blank_hints

NON_INPUT={"INFO_BLOCK","TEXT_BLOCK"}

def all_fields(semantic:dict)->list[dict]:
    return [f for page in semantic.get("pages",[]) if isinstance(page,dict)
            for section in page.get("sections",[]) if isinstance(section,dict)
            for f in section.get("fields",[]) if isinstance(f,dict)
            and f.get("type") not in NON_INPUT]

def assess(source:str,semantic:dict,*,pages:list[dict]|None=None,
           pages_expected:int|None=None,
           vision_incomplete:bool=False,
           truncated:bool=False) -> dict:
    fields=all_fields(semantic)
    stats=blank_hints(source)
    seen_pages=pages or []
    if seen_pages:
        expected=sum(p.get("blank_slots",0) for p in seen_pages)
        detected=sum(p.get("detected_fields",0) for p in seen_pages)
        evidence=sum(p.get("source_evidence_count",0) for p in seen_pages)
        sourced=sum(p.get("source_blank_slots",0) for p in seen_pages)
        visual_seen=sum(bool(p.get("with_image")) for p in seen_pages)
        page_count=len(seen_pages)
    else:
        expected=stats["blank_slots"]
        detected=len(fields)
        evidence=0
        sourced=expected
        visual_seen=0
        page_count=0
    # Blank-run count is a lower-bound *indicator*, not a legal requirement
    # for exact one-to-one fields. Fail a major omission; a small mismatch
    # remains a review note rather than silently proclaiming success.
    ratio=(detected/expected) if expected else None
    major_omission=bool(expected>=5 and detected<0.72*expected)
    minor_gap=bool(expected>=5 and detected<0.93*expected)
    incomplete=bool(pages_expected is not None and page_count<pages_expected)
    issues=[]
    if not fields:
        issues.append("Nie wykryto żadnych pytań do wypełnienia.")
    if major_omission:
        issues.append("Wykryto znacznie mniej pól niż pustych miejsc w dokumencie.")
    elif minor_gap:
        issues.append("Część pustych miejsc może nie mieć odpowiednika w formularzu.")
    if vision_incomplete or incomplete:
        issues.append("Nie przeanalizowano obrazowo wszystkich stron źródła.")
    if truncated:
        issues.append("Tekst wejściowy został ucięty.")
    # Source evidence may be visible only in images and impossible to match in
    # noisy OCR. Expose it, but never fabricate additional fields from it.
    return {
        "ok": bool(fields) and not major_omission and not incomplete
              and not vision_incomplete and not truncated,
        "input_fields":len(fields),
        "source_blank_slots":expected,
        "blank_coverage_ratio":round(ratio,3) if ratio is not None else None,
        "matched_source_quotes":evidence,
        "page_count":page_count,
        "visually_seen_pages":visual_seen,
        "manual_review_recommended":minor_gap or bool(issues),
        "possible_missing":issues,
        "note":"Source-blank and per-page completeness signals; not proof of semantic accuracy."
    }
