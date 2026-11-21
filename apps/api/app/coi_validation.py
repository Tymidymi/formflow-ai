"""COI structural checks. Full COI schema integration is a separate stage."""
from uuid import UUID

ALLOWED={"TEXT_FIELD","TEXTAREA","NUMBER","DATEPICKER","RADIO","CHECKBOX","SELECT",
         "FILE_UPLOADER","SECTION","REPEATING_SECTION","INFO_SECTION","TEXT_BLOCK","CONSENT_SECTION"}

def _uuid(v):
    try: UUID(v);return True
    except (ValueError,TypeError,AttributeError): return False

def validate_coi_form(data:object)->dict:
    errors=[];warnings=[];total=0
    def bad(path,code,msg):errors.append({"path":path,"code":code,"message":msg})
    if not isinstance(data,dict):
        bad("$","ROOT","Wymagany obiekt JSON.")
        return {"valid":False,"schema_valid":None,"errors":errors,"warnings":warnings,"summary":{}}
    if not isinstance(data.get("title"),str) or not data["title"].strip():
        bad("$.title","TITLE","Brak tytułu.")
    tabs=data.get("tabs")
    if not isinstance(tabs,list) or len(tabs)<2:
        bad("$.tabs","TABS","Wymagane MAIN i FINISH.")
        tabs=tabs if isinstance(tabs,list) else []
    tab_ids=set()
    for ti,tab in enumerate(tabs):
        path=f"$.tabs[{ti}]"
        if not isinstance(tab,dict):
            bad(path,"TAB","Strona musi być obiektem.");continue
        if not _uuid(tab.get("id")):bad(path+".id","UUID","Niewłaściwe id strony.")
        if tab.get("id") in tab_ids:bad(path+".id","DUP","Duplikat id strony.")
        tab_ids.add(tab.get("id"))
        if tab.get("type") not in ("MAIN","FINISH"):
            bad(path+".type","TYPE","Nieobsługiwany typ strony.")
        if ti==len(tabs)-1 and tab.get("type")!="FINISH":
            bad(path+".type","FINISH","Ostatnia strona musi mieć FINISH.")
        if ti<len(tabs)-1 and tab.get("type")!="MAIN":
            bad(path+".type","MAIN","Wcześniejsze strony muszą mieć MAIN.")
        if not isinstance(tab.get("title"),str) or not tab["title"].strip():
            bad(path+".title","TITLE","Brak nazwy strony.")
        def fields(items,p,level=0):
            nonlocal total
            if not isinstance(items,list) or not items:
                bad(p,"QUESTIONS","Wymagana lista pytań.");return
            for qi,item in enumerate(items):
                q=f"{p}[{qi}]"
                if not isinstance(item,dict):bad(q,"QUESTION","Nieprawidłowe pytanie.");continue
                for x in ("x","y","rows","cols"):
                    v=item.get(x)
                    if type(v)!=int or v<(0 if x in ("x","y") else 1):
                        bad(q+"."+x,"GRID","Nieprawidłowa wartość siatki.")
                f=item.get("field")
                if not isinstance(f,dict):bad(q,"FIELD","Brak field.");continue
                total+=1
                if not _uuid(f.get("id")):bad(q+".field.id","UUID","Nieprawidłowe id pola.")
                if f.get("type") not in ALLOWED:bad(q+".field.type","TYPE","Nieznany typ pola.")
                if not isinstance(f.get("techName"),str) or not f["techName"].strip():
                    bad(q+".field.techName","TECHNAME","Brak nazwy technicznej.")
                for k in ("options","states","validation"):
                    if not isinstance(f.get(k,[]),list):
                        bad(q+".field."+k,"LIST","Wymagana lista.")
                kind=f.get("type")
                if level==0 and kind not in ("SECTION","REPEATING_SECTION"):
                    bad(q+".field.type","SECTION","Pola muszą być w sekcji.")
                if level>0 and kind in ("SECTION","REPEATING_SECTION"):
                    bad(q+".field.type","NESTING","Sekcje nie mogą być zagnieżdżone.")
                if kind in ("SECTION","REPEATING_SECTION"):
                    fields(f.get("repeatingSectionGrid"),q+".field.repeatingSectionGrid",level+1)
                elif tab.get("type")=="FINISH" and kind in ("TEXT_FIELD","TEXTAREA","NUMBER",
                          "DATEPICKER","RADIO","CHECKBOX","SELECT","FILE_UPLOADER"):
                    bad(q,"FINISH_INPUT","Strona końcowa nie może zbierać danych.")
        fields(tab.get("questions"),path+".questions")
    flow=data.get("flow")
    links=flow.get("links") if isinstance(flow,dict) else None
    if not isinstance(links,list):
        bad("$.flow.links","LINKS","Wymagana lista powiązań.");links=[]
    connections={(i.get("source"),i.get("target")) for i in links if isinstance(i,dict)}
    for a,b in zip(tabs,tabs[1:]):
        if isinstance(a,dict) and isinstance(b,dict) and (a.get("id"),b.get("id")) not in connections:
            bad("$.flow.links","FLOW","Brak połączenia między kolejnymi stronami.")
    return {"valid":not errors,"schema_valid":None,"errors":errors,"warnings":warnings,
            "summary":{"tabs":len(tabs),"fields_including_sections":total,"links":len(links)},
            "note":"Walidacja strukturalna; pełny JSON Schema COI jeszcze niepodłączony."}
