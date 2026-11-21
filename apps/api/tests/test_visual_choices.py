"""Cross-domain choice-audit regressions: no vocabulary of any real form."""
from __future__ import annotations

import asyncio

from app import structured_extraction as inventory
from app import visual_choices
from app.coi_builder import convert
from app.quality_gate import assess


def test_visual_choice_group_and_option_bound_details():
    source = (
        "Typ sprzętu: ☐ ręczny ☐ automatyczny\n"
        "Sposób identyfikacji / nr: \n"
        "□ Kod QR ..............................\n"
        "□ Etykieta ..............................\n"
        "□ Brak\n"
    )
    data={"pages":[{"title":"Urządzenia","sections":[{"title":"Rodzaj",
        "fields":[{"label":"Typ sprzętu","type":"RADIO",
                   "options":["ręczny","automatyczny"],"required":False}]}]}]}
    groups=[{"label":"Typ sprzętu","kind":"CHECKBOX",
             "evidence":"Typ sprzętu",
             "options":[{"label":opt,"evidence":opt,"has_detail_blank":False,"detail_label":""}
                        for opt in ("ręczny","automatyczny")],
             "needs_visual_review":False},
            {"label":"Sposób identyfikacji / nr","kind":"CHECKBOX",
             "evidence":"Sposób identyfikacji / nr",
             "options":[{"label":opt,"evidence":opt,
                         "has_detail_blank":opt!="Brak",
                         "detail_label":"nr"} for opt in ("Kod QR","Etykieta","Brak")],
             "needs_visual_review":False}]
    stats=visual_choices.merge_choices(data,groups,1)
    assert stats["choice_groups"]==1
    assert stats["choice_options"]==5
    assert stats["detail_inputs_added"]==2
    fields=inventory._fields(data)
    assert [x["type"] for x in fields]==["RADIO","CHECKBOX","TEXT_FIELD","TEXT_FIELD"]
    assert fields[0]["options"]==["ręczny","automatyczny"]
    assert fields[1]["options"]==["Kod QR","Etykieta","Brak"]
    assert inventory.response_slot_count(data)==7
    assert assess(source,data)["ok"]
    coi,validation=convert({"title":"Identyfikacja","pages":data["pages"]})
    assert validation["schema_valid"] and validation["valid"]
    children=[entry["field"] for section in coi["tabs"][0]["questions"]
              for entry in section["field"]["repeatingSectionGrid"]]
    assert len(children)==4
    assert all(child["states"] and child["states"][0]["type"]=="SHOW"
               for child in children[-2:])


def test_focus_detector_uses_source_words_not_a_case_dictionary(monkeypatch):
    source=("☐ Dostawa kurierska ...........\n"
            "☐ Odbiór osobisty\n"
            "☐ Skrytka ............")
    async def fake_generate(txt,images,prompt):
        return {"pages":[{"choice_groups":[{
            "label":"Sposób dostarczenia",
            "kind":"CHECKBOX",
            "options":[
                {"label":"Dostawa kurierska","has_detail_blank":True,
                 "detail_label":"numer przesyłki"},
                {"label":"Odbiór osobisty","has_detail_blank":False},
                {"label":"Skrytka","has_detail_blank":True,
                 "detail_label":"kod"}]
        }]}]},{}
    monkeypatch.setattr(visual_choices,"generate",fake_generate)
    groups=asyncio.run(visual_choices.detect_choices(source,("image/jpeg",b"fake")))
    assert len(groups)==1
    assert groups[0]["ocr_grounded_options"]==3
    assert not groups[0]["needs_visual_review"]
    doc={"pages":[]}
    stats=visual_choices.merge_choices(doc,groups,1)
    assert stats["choice_groups"]==1 and stats["detail_inputs_added"]==2
    assert inventory.response_slot_count(doc)==5
    assert [x["label"] for x in inventory._fields(doc)][0]=="Sposób dostarczenia"


def test_choice_review_does_not_erase_other_unrelated_checkbox():
    base={"pages":[{"title":"Zgłoszenie","sections":[
        {"title":"Potwierdzenie","fields":[
            {"label":"Brak","type":"CHECKBOX","options":[],"required":False}]}
    ]}]}
    group={"label":"Rodzaj dostępu","kind":"CHECKBOX",
           "options":[{"label":"Zdalny","has_detail_blank":False,"detail_label":""},
                      {"label":"Brak","has_detail_blank":False,"detail_label":""}],
           "evidence":"Rodzaj dostępu","needs_visual_review":False}
    visual_choices.merge_choices(base,[group],1)
    assert len([x for x in inventory._fields(base) if x["label"]=="Brak"])==1
    assert len(inventory._fields(base))==2


def test_missing_visual_audit_marks_quality_unverified(monkeypatch):
    async def fake_generate(text,images,prompt):
        return {"title":"Wybór","pages":[{"title":"Formularz","sections":[{
            "title":"Dane","fields":[{"label":"Id","type":"TEXT_FIELD",
                                     "evidence":"Id","required":False}]}]}]},{}
    async def fake_no_table(*args,**kwargs):return []
    async def fake_failed_choices(*args,**kwargs):
        from app.ai_provider import AIProviderError
        raise AIProviderError("provider unavailable")
    monkeypatch.setattr(inventory,"generate",fake_generate)
    monkeypatch.setattr(inventory,"visually_detect",fake_no_table)
    monkeypatch.setattr(inventory,"detect_choices",fake_failed_choices)
    source="[Strona 1/1]\nId ............"
    semantic,stats,reports=asyncio.run(inventory.extract(
        source,[("image/jpeg",b"fake")],pages_expected=1))
    assert reports[0]["choice_audit_error"]
    q=assess(source,semantic,pages=reports,pages_expected=1)
    assert not q["ok"]
    assert any("kontroli grup wyboru" in x for x in q["possible_missing"])


def test_end_to_end_missing_choices_are_restored_without_new_document_assumptions(monkeypatch):
    source=("[Strona 1/1]\nTyp sprzętu: ☐ ręczny ☐ automatyczny\n"
            "Identyfikator: \n"
            "☐ Kod QR ...........\n☐ Etykieta ...........\n☐ Brak")
    async def fake_page_model(txt,images,prompt):
        return {"title":"Identyfikacja","pages":[{"title":"Dane","sections":[{
            "title":"Typ","fields":[{"label":"Typ sprzętu","type":"RADIO",
                    "options":["ręczny","automatyczny"],"evidence":"Typ sprzętu",
                    "required":False}]}]}]},{}
    async def fake_no_tables(*args,**kwargs):return []
    async def focused_choices(*args,**kwargs):
        return [{"label":"Identyfikator","kind":"CHECKBOX",
            "evidence":"Identyfikator",
            "options":[
                {"label":"Kod QR","has_detail_blank":True,"detail_label":"numer","evidence":"Kod QR"},
                {"label":"Etykieta","has_detail_blank":True,"detail_label":"numer","evidence":"Etykieta"},
                {"label":"Brak","has_detail_blank":False,"detail_label":"","evidence":"Brak"}],
            "needs_visual_review":False}]
    monkeypatch.setattr(inventory,"generate",fake_page_model)
    monkeypatch.setattr(inventory,"visually_detect",fake_no_tables)
    monkeypatch.setattr(inventory,"detect_choices",focused_choices)
    sem,stats,reports=asyncio.run(inventory.extract(
        source,[("image/jpeg",b"synthetic")],pages_expected=1))
    assert reports[0]["choice_options"]==3
    assert reports[0]["detail_inputs_added"]==2
    assert reports[0]["detected_slots"]==7
    q=assess(source,sem,pages=reports,pages_expected=1)
    assert q["ok"],q
    coi,validation=convert(sem)
    assert validation["schema_valid"] and validation["valid"]
    fields=inventory._fields(sem)
    assert len(fields)==4
    assert {f["label"] for f in fields if f["type"]=="TEXT_FIELD"}=={
        "Identyfikator — Kod QR: numer","Identyfikator — Etykieta: numer"}

def test_generic_consolidation_of_first_pass_option_rows_then_focus_merge():
    """Replay the shape of a real Qwen response, but in an unrelated domain."""
    root={"pages":[{"title":"Dane","sections":[{"title":"Wyposażenie","fields":[
        {"label":"Typ urządzenia: mechaniczny","type":"CHECKBOX", "options":[],
         "evidence":"Typ urządzenia: ☐ mechaniczny ☐ elektroniczny"},
        {"label":"Typ urządzenia: elektroniczny","type":"CHECKBOX", "options":[],
         "evidence":"Typ urządzenia: ☐ mechaniczny ☐ elektroniczny"},
        {"label":"Oznaczenie / numer: kod QR","type":"CHECKBOX","options":[],
         "evidence":"Oznaczenie / numer: ☐ kod QR ........"},
        {"label":"Oznaczenie / numer: kod QR — numer","type":"TEXT_FIELD","options":[],
         "evidence":"Oznaczenie / numer: ☐ kod QR ........"},
        {"label":"Oznaczenie / numer: etykieta","type":"CHECKBOX","options":[],
         "evidence":"Oznaczenie / numer: ☐ etykieta ........"},
        {"label":"Oznaczenie / numer: etykieta — numer","type":"TEXT_FIELD","options":[],
         "evidence":"Oznaczenie / numer: ☐ etykieta ........"},
        {"label":"Oznaczenie / numer: brak","type":"CHECKBOX","options":[],
         "evidence":"Oznaczenie / numer: ☐ brak"},
    ]}]}]}
    n=visual_choices.consolidate_choice_fields(root)
    assert n==2
    group={"label":"Oznaczenie / numer:","kind":"CHECKBOX",
           "evidence":"Oznaczenie / numer:","needs_visual_review":False,
           "options":[{"label":label,"evidence":label,
                       "has_detail_blank":label!='brak',"detail_label":"numer"}
                      for label in ('kod QR','etykieta','brak')]}
    m=visual_choices.merge_choices(root,[group],1)
    assert m["choice_groups"]==0 and m["detail_inputs_added"]==0
    fields=inventory._fields(root)
    assert len(fields)==4,fields
    assert [f["type"] for f in fields]==[
        "CHECKBOX","CHECKBOX","TEXT_FIELD","TEXT_FIELD"]
    assert len(fields[0]["options"])==2
    assert len(fields[1]["options"])==3
    assert all("show_when" in f for f in fields[-2:])
    output,check=convert({"title":"Rejestr","pages":root["pages"]})
    assert check["valid"],check
    child=[f["field"] for q in output["tabs"][0]["questions"]
           for f in q["field"]["repeatingSectionGrid"]]
    assert sum(bool(f["states"]) for f in child)==2

def test_focus_rechecks_uncounted_physical_squares_in_cropped_page(monkeypatch):
    """The first vision pass may miss a horizontal row above a vertical list."""
    from io import BytesIO
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(500,720),'white');d=ImageDraw.Draw(im)
    for x,y in [(80,100),(250,100),(80,360),(80,450),(80,540)]:
        d.rectangle((x,y,x+23,y+23),outline='black',width=3)
    stream=BytesIO();im.save(stream,format='PNG')
    image=('image/png',stream.getvalue())
    assert len(visual_choices._visual_square_locations(image))==5
    calls=[]
    async def fake_model(text,images,prompt):
        calls.append(images[0][0])
        if images[0][0]=='image/png':
            return {"pages":[{"choice_groups":[{
                "label":"Sposób potwierdzenia","kind":"CHECKBOX",
                "options":[{"label":x,"has_detail_blank":False}
                           for x in ('Przesyłka','Potwierdzenie','Brak')]
            }]}]},{}
        return {"pages":[{"choice_groups":[{
            "label":"Tryb","kind":"RADIO",
            "options":[{"label":"Automatyczny","has_detail_blank":False},
                       {"label":"Ręczny","has_detail_blank":False}]
        }]}]},{}
    monkeypatch.setattr(visual_choices,"generate",fake_model)
    groups=asyncio.run(visual_choices.detect_choices('Tryb i sposób potwierdzenia',image))
    assert len(groups)==2
    assert sum(len(g['options']) for g in groups)==5
    assert calls==['image/png','image/jpeg']


def test_repeated_choice_caption_on_separate_pages_uses_scoped_state_references():
    pages=[]
    for page_num in (1,2):
        data={"pages":[{"title":f"Osoba {page_num}","sections":[]}]}
        options=[{"label":"Tak","evidence":"Tak","has_detail_blank":True,
                  "detail_label":"numer"},
                 {"label":"Nie","evidence":"Nie","has_detail_blank":False,
                  "detail_label":""}]
        visual_choices.merge_choices(data,[{
            "label":"Czy posiada identyfikator","kind":"RADIO",
            "options":options,"evidence":"Czy posiada identyfikator",
            "needs_visual_review":False}],page_num)
        pages.extend(data["pages"])
    coi,validation=convert({"title":"Wieloczęściowy formularz","pages":pages})
    assert validation["valid"],validation
    mapped=[]
    for tab in coi["tabs"][:-1]:
        items=[q["field"] for section in tab["questions"]
               for q in section["field"]["repeatingSectionGrid"]]
        assert len(items)==2
        mapped.append((items[0]["techName"],items[1]["states"][0]["query"]))
    assert mapped[0][0]!=mapped[1][0]
    assert mapped[0][0] in mapped[0][1]
    assert mapped[1][0] in mapped[1][1]