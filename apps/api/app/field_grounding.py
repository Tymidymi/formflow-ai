"""Conservative, OCR-grounded evidence report for generated form questions.

This is a REVIEW signal, never a claim that absent OCR means hallucination:
small printed labels may be visible to a VLM despite OCR corruption.
No data leaves the server during this deterministic grounding pass.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata

STOP={"wniosek","wnioskodawcy","wnioskodawca","pole","podaj","prosze","dane",
      "informacje","informacja","numer","numery","adres","wpisz","dotyczace",
      "potwierdzenie","inne","osoby","osoba","zgloszenia","wnosze","wybor"}
PAGE=re.compile(r"(?m)^\[(?:Strona|Część)\s+(\d+)/\d+\]")
WORD=re.compile(r"[a-z0-9]{2,}")
def norm(value:str)->str:
    return unicodedata.normalize("NFKD",str(value).translate(
        str.maketrans("Łł","Ll"))).encode("ascii","ignore").decode("ascii").lower()
def terms(value:str)->set[str]:
    result=set()
    for word in WORD.findall(norm(value)):
        if word in STOP:continue
        # A light comparison stem handles "dzialki"/"dzialka" without
        # rewriting original source or making legal equivalence claims.
        result.add(word if len(word)<6 else word[:5])
    return result
def lines_with_pages(text:str)->list[tuple[int,str]]:
    page=1
    output=[]
    for line in text.splitlines():
        marker=PAGE.match(line)
        if marker:
            page=int(marker.group(1));continue
        clean=" ".join(line.split())
        if clean:output.append((page,clean[:280]))
    return output
def score(label:str,source:str)->float:
    l=norm(label);s=norm(source)
    if l in s or s in l and len(s)>5:
        return 1.0
    a,b=terms(label),terms(source)
    if not a or not b:return 0.0
    overlap=len(a&b)/len(a)
    fuzzy=SequenceMatcher(None,l,s).ratio()
    # Single-word labels e.g. PESEL must be found literally.
    if len(a)==1:
        return 0.94 if a<=b else 0.0
    return max(overlap,0.67*fuzzy)
def analyze_grounding(text:str,semantic:dict,images_count:int=0)->dict:
    lines=lines_with_pages(text)
    fields=[item for page in semantic.get("pages",[]) if isinstance(page,dict)
            for section in page.get("sections",[]) if isinstance(section,dict)
            for item in section.get("fields",[]) if isinstance(item,dict)
            and item.get("type") not in ("INFO_BLOCK","TEXT_BLOCK")]
    report=[]
    for field in fields:
        label=str(field.get("label","")).strip()
        if not label:continue
        choices=sorted(((score(label,line),page,line) for page,line in lines),
                       reverse=True,key=lambda x:x[0])
        best=choices[0] if choices else (0.0,None,"")
        matched=best[0]>=0.78
        report.append({"label":label[:220],"type":field.get("type"),
                       "evidence":"ocr_match" if matched else
                           ("requires_visual_review" if images_count else "unverified"),
                       "source_page":best[1] if matched else None,
                       "source_excerpt":best[2][:160] if matched else None,
                       "ocr_similarity":round(best[0],3)})
    grounded=sum(x["evidence"]=="ocr_match" for x in report)
    return {"fields_total":len(report),"ocr_supported":grounded,
            "requires_review":len(report)-grounded,
            "support_ratio":round(grounded/len(report),3) if report else 0.0,
            "items":report,"note":"OCR evidence only; lack of text match is not proof that a visually visible field is invented."}
