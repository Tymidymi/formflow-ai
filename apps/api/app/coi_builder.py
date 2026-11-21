"""Deterministically map compact semantic fields to the exact COI tab/section JSON."""
import re
import unicodedata
from uuid import uuid4
from .coi_validation import validate_coi_form

KINDS={"TEXT_FIELD","TEXTAREA","NUMBER","DATEPICKER","RADIO","CHECKBOX","SELECT","FILE_UPLOADER"}

def slug(text:str)->str:
    raw=unicodedata.normalize("NFKD",text).encode("ascii","ignore").decode("ascii")
    return (re.sub(r"[^a-z0-9]+","_",raw.lower()).strip("_") or "pole")[:55]

def field(label:str,kind:str,name:str,*,children=None,options=None,required=False,description="")->dict:
    return {"id":str(uuid4()),"type":kind,"techName":name,"title":label,
            "description":description,"options":options or [],
            "validation":["REQUIRED"] if required else [],"readOnly":False,
            "repeatingSectionGrid":children or [],"states":[],
            "questionOrder":0,"tooltipMessage":""}

def wrap(item:dict, y:int, order:int)->dict:
    item["questionOrder"]=order
    return {"x":0,"y":y,"rows":1,"cols":3,"field":item}

def safe_list(data:dict,key:str)->list:
    value=data.get(key,[])
    return value if isinstance(value,list) else []

def convert(semantic:dict)->tuple[dict,dict]:
    pages=safe_list(semantic,"pages")[:4]
    if not pages: raise ValueError("Model nie zidentyfikował stron.")
    tabs=[]; used=set(); total=0
    for pi,page in enumerate(pages):
        if not isinstance(page,dict): continue
        questions=[]; y=0
        for si,section in enumerate(safe_list(page,"sections")[:6]):
            if not isinstance(section,dict): continue
            children=[]
            for data in safe_list(section,"fields")[:30]:
                if not isinstance(data,dict): continue
                label=str(data.get("label") or "").strip()[:220]
                if not label: continue
                kind=data.get("type","TEXT_FIELD")
                if kind not in KINDS:kind="TEXT_FIELD"
                name=slug(label); base=name; i=2
                while name in used:
                    name=base[:50]+"_"+str(i);i+=1
                used.add(name)
                raw=data.get("options")
                opts=[]
                if kind in ("RADIO","CHECKBOX","SELECT") and isinstance(raw,list):
                    for opt in raw[:20]:
                        v=str(opt).strip()[:160]
                        if v:opts.append({"id":v,"name":v,"techName":slug(v)})
                if kind in ("RADIO","CHECKBOX","SELECT") and not opts:kind="TEXT_FIELD"
                item=field(label,kind,name,options=opts,required=data.get("required") is True)
                children.append(wrap(item,len(children),len(children)))
                total+=1
                if total>=70:break
            if not children:continue
            title=str(section.get("title") or "Dane")[:220]
            item=field(title,"SECTION",f"sekcja_{pi}_{si}_{slug(title)}",children=children)
            questions.append({"x":0,"y":y,"rows":len(children)+1,"cols":3,
                              "field":{**item,"questionOrder":len(questions)}})
            y+=len(children)+1
            if total>=70:break
        if questions:
            tabs.append({"id":str(uuid4()),"title":str(page.get("title") or f"Dane {pi+1}")[:220],
                         "type":"MAIN","questions":questions})
        if total>=70:break
    if not tabs:
        raise ValueError("Model nie wykrył pól.")
    info=field("","TEXT_BLOCK","tekst_koncowy",
               description="<html><body><p>Sprawdź dane przed wysłaniem.</p></body></html>")
    finish=field("Podgląd wniosku","SECTION","podglad_wniosku",children=[wrap(info,0,0)])
    tabs.append({"id":str(uuid4()),"title":"Strona końcowa","type":"FINISH",
                 "questions":[{"x":0,"y":0,"rows":2,"cols":3,"field":finish}]})
    links=[{"id":str(uuid4()),"source":a["id"],"target":b["id"]} for a,b in zip(tabs,tabs[1:])]
    coi={"title":str(semantic.get("title") or "Formularz urzędowy")[:240],
         "tabs":tabs,"flow":{"links":links}}
    return coi,validate_coi_form(coi)
