"""Regressions for physical source slots, information zones, and choice merging.

These scenarios use unrelated generic domains to prevent sample-form-specific
production logic.
"""
import asyncio
from io import BytesIO
from PIL import Image

from app.document_zones import suppress_readonly_source_controls
from app import visual_choices, source_slot_audit
from app.structured_extraction import Page, _sanitize_page, _fields


def test_read_only_notice_does_not_generate_duplicate_applicant_controls():
    body="Wniosek o rejestrację. Nazwisko ................\nOpis ............"
    notice=("INFORMACJE:\n1. Opłata wynosi 20 zł. "
            "2. Zapłać przelewem do urzędu. ")
    semantic={"pages":[{"title":"Dane","sections":[
        {"title":"Dane","fields":[
            {"label":"Nazwisko","type":"TEXT_FIELD","evidence":"Nazwisko ................"}]},
        {"title":"INFORMACJE","fields":[
            {"label":"Opłata wynosi 20 zł","type":"TEXT_FIELD",
             "evidence":"Opłata wynosi 20 zł"},
            {"label":"Telefon","type":"TEXT_FIELD",
             "evidence":"image-only"}]},
    ]}]}
    assert suppress_readonly_source_controls(semantic,body,notice)==2
    assert [f["label"] for f in _fields(semantic)]==["Nazwisko"]


def test_duplicated_choice_options_and_text_detail_merge_across_sections():
    options=["przesyłki krajowej","przesyłki zagranicznej",
             "odbioru osobistego","inna forma"]
    doc={"pages":[{"title":"Wysyłka","sections":[
        {"title":"Prośba o odbiór przesyłki", "fields":[
            *[{"label":name,"type":"CHECKBOX","options":[],"required":False,
                "evidence":name} for name in options[:-1]],
            {"label":"inna forma","type":"TEXTAREA","evidence":"inna forma ........"}
        ]},
        {"title":"Podsumowanie wyboru", "fields":[{
            "label":"Proszę o odbiór przesyłki:", "type":"CHECKBOX",
            "options":options[:3],"required":False,
            "evidence":"Proszę o odbiór przesyłki:"
        }]}
    ]}]}
    detected={"label":"Proszę o odbiór przesyłki:", "kind":"CHECKBOX",
      "evidence":"Proszę o odbiór przesyłki:",
      "options":[{"label":label,"evidence":label,
                  "has_detail_blank":label=="inna forma",
                  "detail_label":"opis"} for label in options],
      "needs_visual_review":False}
    result=visual_choices.merge_choices(doc,[detected],1)
    assert result["choice_groups"]==0
    assert result["detail_inputs_added"]==0
    fields=_fields(doc)
    assert len(fields)==2,fields
    assert fields[0]["options"]==options
    assert fields[1]["label"]=="inna forma"
    assert fields[1]["show_when"]["value"]=="inna forma"
    assert len(doc["pages"][0]["sections"])==1


def test_not_unifying_distinct_checkboxes_without_source_context():
    doc={"pages":[{"title":"Dane","sections":[
       {"title":"Różne oświadczenia","fields":[
           {"label":"Tak","type":"CHECKBOX","options":[]},
           {"label":"Nie","type":"CHECKBOX","options":[]}]},
       {"title":"Pytanie osobne","fields":[
           {"label":"Pytanie osobne","type":"RADIO","options":["Tak","Nie"]}]}
    ]}]}
    detected={"label":"Pytanie osobne","kind":"RADIO",
      "evidence":"Pytanie osobne",
      "options":[{"label":"Tak","has_detail_blank":False},
                 {"label":"Nie","has_detail_blank":False}],
      "needs_visual_review":False}
    visual_choices.merge_choices(doc,[detected],1)
    assert len(_fields(doc))==3


def test_short_printed_date_slot_is_covered_by_focused_visual_audit(monkeypatch):
    source="Miasto, dnia..\nDane podmiotu\nImię i nazwisko"
    sem={"pages":[{"title":"Strona","sections":[{"title":"Dane","fields":[
        {"label":"Imię i nazwisko","type":"TEXT_FIELD",
         "evidence":"Imię i nazwisko","source_line":3}]}]}]}
    assert [x["line"] for x in source_slot_audit.uncovered_short_blanks(source,sem)]==[1]
    image=Image.new("RGB",(600,850),"white")
    bio=BytesIO()
    image.save(bio,format="JPEG")
    calls=[]
    async def model(text,images,prompt):
        calls.append((text,images[0][0]))
        return {"title":"Strona","pages":[{"title":"Strona","sections":[{"title":"Pola",
            "fields":[{"label":"Data sporządzenia","type":"DATEPICKER",
              "required":False,"options":[],"evidence":"Miasto, dnia.."}]}]}]},{}
    monkeypatch.setattr(source_slot_audit,"generate",model)
    count,candidates=asyncio.run(source_slot_audit.recover_uncovered_slots(
        source,("image/jpeg",bio.getvalue()),sem,
        lambda data:_sanitize_page(data,Page(1,source,None))))
    assert count==1
    assert calls and "line 1:" in calls[0][0]
    assert len(_fields(sem))==2
    date=next(f for f in _fields(sem) if f["type"]=="DATEPICKER")
    assert date["source_line"]==1 and date["source"]=="source_slot_visual_audit"
    assert source_slot_audit.uncovered_short_blanks(source,sem)==[]


def test_only_exact_ocr_evidence_can_be_added_by_visual_slot_audit(monkeypatch):
    source="Miasto, dnia..\nNazwa ................"
    sem={"pages":[{"title":"Strona","sections":[{"title":"Dane","fields":[
        {"label":"Nazwa","type":"TEXT_FIELD","source_line":2}]}]}]}
    im=Image.new("RGB",(500,600),"white")
    stream=BytesIO();im.save(stream,format="JPEG")
    async def fabricated(*args,**kwargs):
        return {"title":"Dane","pages":[{"title":"Strona","sections":[{"title":"Dane",
          "fields":[{"label":"Nr licencji","type":"TEXT_FIELD",
                    "evidence":"nieistniejący wiersz formularza"}]}]}]},{}
    monkeypatch.setattr(source_slot_audit,"generate",fabricated)
    recovered,_=asyncio.run(source_slot_audit.recover_uncovered_slots(
        source,("image/jpeg",stream.getvalue()),sem,
        lambda data:_sanitize_page(data,Page(1,source,None))))
    assert recovered==1  # sourced date blank, not fabricated model label
    assert all(f["label"]!="Nr licencji" for f in _fields(sem))
    assert sum(f["type"]=="DATEPICKER" for f in _fields(sem))==1


def test_duplicate_vision_question_groups_with_same_three_options_removed():
    names=["Dostarcz kurierem","Odbiór osobisty","Wyślij paczkomatem","Inne"]
    doc={"pages":[{"title":"Dostawa","sections":[
      {"title":"Rodzaj dostawy","fields":[{"label":"Rodzaj dostawy:",
          "type":"CHECKBOX","options":names[:3],"evidence":"Rodzaj dostawy"}]},
      {"title":"Rodzaj dostawy — wybór","fields":[{
          "label":"Rodzaj dostawy", "type":"CHECKBOX","options":names,
          "source_choice_ref":"choice_1_2","evidence":"Rodzaj dostawy"}]}
    ]}]}
    assert visual_choices.deduplicate_overlapping_choice_groups(doc)==1
    fields=_fields(doc)
    assert len(fields)==1
    assert fields[0]["options"]==names
    assert fields[0]["source_choice_ref"]=="choice_1_2"


def test_unrelated_questions_with_three_shared_options_not_merged():
    choices=["Opcja A","Opcja B","Opcja C"]
    doc={"pages":[{"title":"Dane","sections":[{"title":"Różne pytania","fields":[
      {"label":"Wybór pakietu", "type":"RADIO","options":choices},
      {"label":"Wybór dodatkowego sprzętu", "type":"CHECKBOX","options":choices}
    ]}]}]}
    assert visual_choices.deduplicate_overlapping_choice_groups(doc)==0
    assert len(_fields(doc))==2


def test_api_crops_readonly_notice_and_exports_clean_coi(monkeypatch):
    """One full JPEG conversion flow without a sample-form-specific dictionary."""
    from fastapi.testclient import TestClient
    from PIL import ImageDraw
    from app.main import app
    import app.main as api

    im=Image.new("RGB",(900,1800),"white")
    draw=ImageDraw.Draw(im)
    draw.text((40,55),"APPLICATION",fill="black")
    draw.text((40,260),"Name ..........",fill="black")
    draw.text((40,390),"Date .........",fill="black")
    draw.text((40,1430),"INFORMATION",fill="black")
    raw=BytesIO();im.save(raw,format="JPEG",quality=85)
    picture=raw.getvalue()
    body=("WNIOSEK o wydanie decyzji. Dane wnioskodawcy. "
          "Nazwa .................................. ")*3
    tail="INFORMACJE:\n"+("Instrukcja tylko do przeczytania, bez pól odpowiedzi. "*6)
    source=body+"\n"+tail
    seen=[]
    async def fake_extract(content,extension,**kwargs):
        return source,[("image/jpeg",picture)],{"engine":"synthetic-ocr",
               "pages":1,"vision_page_numbers":[1],
               "vision_incomplete":False,"truncated":False}
    async def fake_model(text,images,**kwargs):
        size=Image.open(BytesIO(images[0][1])).size
        seen.append(size)
        return {"title":"Rejestracja","pages":[{"title":"Dane","sections":[
          {"title":"Dane źródłowe","fields":[
           {"label":"Nazwa","type":"TEXT_FIELD","evidence":"Nazwa"}]},
          {"title":"INFORMACJE","fields":[
           {"label":"Instrukcja tylko do przeczytania","type":"TEXT_FIELD",
            "evidence":"Instrukcja tylko do przeczytania"}]}
        ]}]}, {"images_sent":1,"pages_processed":1,"rechecked_pages":0,"pages_expected":1}, [
          {"source_page":1,"blank_slots":0,"detected_fields":2,
           "source_evidence_count":1,"with_image":True}]
    async def fake_actions(text):return [],{}
    monkeypatch.setattr(api,"extract_with_backend",fake_extract)
    monkeypatch.setattr(api,"extract_structured",fake_model)
    monkeypatch.setattr(api,"extract_actions",fake_actions)
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","fake-test-key")
    response=TestClient(app).post("/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent":"true"},
        files={"file":("test.jpg",picture,"image/jpeg")})
    assert response.status_code==200,response.text[:700]
    result=response.json()
    assert result["validation"]["valid"]
    assert result["document"]["extraction"]["vision_cropped"] is True
    assert result["document"]["extraction"]["readonly_phantom_fields_rejected"]==1
    assert seen and seen[0][1]<im.height