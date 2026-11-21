"""Deterministic semantic form -> COI tabs/questions/flow exporter."""
from __future__ import annotations

import re
import unicodedata
from html import escape
from uuid import NAMESPACE_URL, uuid5
from .coi_validation import validate_coi_form
from .coi_conditions import attach_states

KINDS = {
    "TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER",
    "RADIO", "CHECKBOX", "SELECT", "FILE_UPLOADER", "INFO_BLOCK",
}
# Match only sufficiently explicit field labels. These are suggestions, not legal
# interpretation; never infer required-ness from the mere presence of a field.
VALIDATORS = [
    (re.compile(r"(?i)\bPESEL\b"), "PESEL"),
    (re.compile(r"(?i)\bNIP\b"), "NIP"),
    (re.compile(r"(?i)\bREGON\b"), "REGON"),
    (re.compile(r"(?i)\b(kod pocztowy|pocztowy kod)\b"), "ZIP_CODE"),
    (re.compile(r"(?i)\b(e-mail|email|adres e.?mail)\b"), "EMAIL"),
]
def slug(text: str) -> str:
    raw=unicodedata.normalize("NFKD",text).encode("ascii","ignore").decode("ascii")
    return (re.sub(r"[^a-z0-9]+","_",raw.lower()).strip("_") or "pole")[:55]

def identifier(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "formflow-ai/coi/v1/" + "/".join(str(v) for v in parts)))

def field(label: str, kind: str, name: str, path: str, *,
          children=None, options=None, required=False, description="", validation=None) -> dict:
    return {
        "id":identifier(path), "type":kind, "techName":name, "title":label,
        "description":description, "options":options or [],
        "validation":validation if validation is not None else (["REQUIRED"] if required else []),
        "readOnly":False,"repeatingSectionGrid":children or [],
        "states":[],"questionOrder":0,"tooltipMessage":"",
    }

def wrap(item: dict, y: int, order: int) -> dict:
    item["questionOrder"]=order
    return {"x":0,"y":y,"rows":1,"cols":3,"field":item}

def safe_list(data: dict, key: str) -> list:
    value=data.get(key,[])
    return value if isinstance(value,list) else []

def field_validation(label: str, required: bool) -> list[str]:
    rules=["REQUIRED"] if required else []
    for expression, code in VALIDATORS:
        if expression.search(label):
            rules.append(code)
            break
    return rules

def convert(semantic: dict) -> tuple[dict,dict]:
    pages=safe_list(semantic,"pages")[:6]
    if not pages:raise ValueError("Model nie zidentyfikował stron.")
    title=str(semantic.get("title") or "Formularz urzędowy")[:255]
    tabs=[];used=set();total=0
    for pi,page in enumerate(pages):
        if not isinstance(page,dict): continue
        questions=[];y=0
        for si,section in enumerate(safe_list(page,"sections")[:8]):
            if not isinstance(section,dict):continue
            children=[]
            for fi,data in enumerate(safe_list(section,"fields")[:30]):
                if not isinstance(data,dict): continue
                label=str(data.get("label") or "").strip()[:220]
                if not label:continue
                kind=data.get("type","TEXT_FIELD")
                if kind not in KINDS:kind="TEXT_FIELD"
                name=slug(label);base=name;j=2
                while name in used:
                    name=base[:50]+"_"+str(j);j+=1
                used.add(name)
                raw=data.get("options");opts=[]
                if kind in {"RADIO","CHECKBOX","SELECT"} and isinstance(raw,list):
                    seen=set()
                    for opt in raw[:20]:
                        val=str(opt).strip()[:160]
                        if val and val not in seen:
                            seen.add(val)
                            opts.append({"id":val,"name":val,"techName":slug(val)})
                dictionary = data.get("dictionary_name")
                if dictionary not in ("Kraje", "TERYT_DOWODOWY", "TERYT_4G_DOWODOWY"):
                    dictionary = None
                if kind == "SELECT" and not opts and not dictionary:
                    if slug(label) in ("kraj", "kraj_zamieszkania", "kraj_urodzenia"):
                        dictionary = "Kraje"
                if kind in {"RADIO","SELECT"} and not opts and not dictionary:
                    kind="TEXT_FIELD"
                if kind=="CHECKBOX" and not opts:
                    # An explicit independent yes/no checkbox needs no invented
                    # enumerated choices; fill only if specified by the document.
                    pass
                if kind=="NUMBER" and re.search(r"(?i)\b(PESEL|NIP|REGON|kod pocztowy)\b",label):
                    kind="TEXT_FIELD"  # preserve leading zeros
                validation=field_validation(label,data.get("required") is True)
                item=field(label,kind,name,f"{title}/{pi}/{si}/{fi}/{name}",
                           options=opts,validation=validation)
                if kind=="INFO_BLOCK":
                    content=str(data.get("content",""))[:7000]
                    # Use COI's supported read-only TEXT_BLOCK, not TEXTAREA.
                    item["type"]="TEXT_BLOCK"
                    item["readOnly"]=True
                    item["validation"]=[]
                    item["description"]=(
                        "<html><head></head><body><p>"
                        +escape(content).replace("\n","<br/>")
                        +"</p></body></html>"
                    )
                if kind in {"RADIO","CHECKBOX","SELECT"} and dictionary:
                    item["dictionaryName"] = dictionary
                if isinstance(data.get("show_when"), dict):
                    item["__show_when"] = data["show_when"]
                children.append(wrap(item,len(children),len(children)))
                total+=1
                if total>=80:break
            if not children:continue
            heading=str(section.get("title") or "Dane")[:220]
            item=field(heading,"SECTION",f"sekcja_{pi}_{si}_{slug(heading)}",
                       f"{title}/section/{pi}/{si}/{heading}",children=children,
                       description="<html><head></head><body></body></html>")
            questions.append({"x":0,"y":y,"rows":len(children)+1,"cols":3,
                              "field":{**item,"questionOrder":len(questions)}})
            y+=len(children)+1
            if total>=80:break
        if questions:
            tabs.append({"id":identifier(title,"tab",str(pi)), "title":str(page.get("title") or f"Dane {pi+1}")[:220],
                         "type":"MAIN","questions":questions})
        if total>=80:break
    if not tabs:raise ValueError("Model nie wykrył pól.")
    info=field("","TEXT_BLOCK","tekst_koncowy",f"{title}/finish/text",
               description="<html><head></head><body><p>Sprawdź dane przed wysłaniem wniosku.</p></body></html>")
    finish=field("Podgląd i wysłanie wniosku","SECTION","podglad_wniosku",
                 f"{title}/finish/section",children=[wrap(info,0,0)])
    tabs.append({"id":identifier(title,"finish"),"title":"Strona końcowa","type":"FINISH",
                 "questions":[{"x":0,"y":0,"rows":2,"cols":3,"field":finish}]})
    links=[{"id":identifier(title,"link",a["id"],b["id"]),
            "source":a["id"],"target":b["id"]} for a,b in zip(tabs,tabs[1:])]
    attach_states(tabs)
    coi={"title":title,"tabs":tabs,"flow":{"links":links}}
    return coi,validate_coi_form(coi)
