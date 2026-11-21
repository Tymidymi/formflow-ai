"""Regression: COI #1 JPEG must not become ten RODO textareas."""
import asyncio
from io import BytesIO

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app
from app.document_zones import split_legal_notice, primary_image_crop
from app.form_repair import repair_form
from app.semantic_quality import normalize_semantic
from app.coi_builder import convert
from app.quality_gate import assess

# Source transcription from supplied blank application image, not private data.
SOURCE = """Wnioskodawca:
(imię i nazwisko/nazwa wnioskodawcy)
(adres)
(nr telefonu/adres e-mail)
( data )
Adresat: Wójt Gminy Elbląg
WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO
Wnoszę o ustalenie numeru porządkowego budynkowi zlokalizowanemu
w miejscowości........... przy ulicy................
nr ewidencyjny działki ......... w obrębie ........
(podpis wnioskodawcy)
KLAUZULA INFORMACYJNA
numeracja porządkowa nieruchomości
Zgodnie z art. 13 RODO w związku z przetwarzaniem danych osobowych.
1. Administratorem Państwa danych osobowych jest Gmina Elbląg.
2. Wyznaczyliśmy Inspektora Ochrony Danych.
3. Państwa dane osobowe będą przetwarzane w celu ...
4. Państwa dane możemy udostępniać podmiotom uprawnionym.
5. Państwa dane nie będą przekazywane do państw trzecich.
6. Państwa dane będą przetwarzane przez okres ...
7. Mają Państwo prawo do żądania dostępu do danych.
8. Mają Państwo prawo żądać sprostowania i usunięcia danych.
9. Przysługuje Państwu prawo skargi.
10. Państwa dane nie będą przetwarzane automatycznie.
"""
BAD_MODEL={
    "title":"Klauzula informacyjna",
    "pages":[{"title":"Klauzula informacyjna",
        "sections":[{"title":"Informacje o przetwarzaniu danych osobowych",
            "fields":[
                {"label":"1. Administratorem Państwa danych osobowych jest Gmina Elbląg.",
                 "type":"TEXTAREA","required":False,"options":[]},
                {"label":"2. Inspektor Ochrony Danych zajmuje się sprawami...",
                 "type":"TEXTAREA","required":False,"options":[]},
                {"label":"3. Państwa dane osobowe będą przetwarzane w celu...",
                 "type":"TEXTAREA","required":False,"options":[]},
                {"label":"4. Państwa dane możemy przekazywać uprawnionym podmiotom.",
                 "type":"TEXTAREA","required":False,"options":[]},
                {"label":"5. Państwa dane nie będą przekazywane do państw trzecich.",
                 "type":"TEXTAREA","required":False,"options":[]},
            ]}]}],
}

def test_clauses_are_readonly_and_real_application_fields_recovered():
    zones=split_legal_notice(SOURCE)
    assert zones.was_split
    assert "wniosek" in zones.body.lower()
    assert "Administratorem" not in zones.body
    corrected,changes=repair_form(BAD_MODEL,zones)
    corrected,more=normalize_semantic(zones.body,corrected)
    labels=[f for p in corrected["pages"] for sec in p["sections"] for f in sec["fields"]]
    input_labels=[f["label"] for f in labels if f["type"]!="INFO_BLOCK"]
    for expected in (
        "Data wniosku",
        "Imię i nazwisko / nazwa wnioskodawcy",
        "Adres wnioskodawcy",
        "Numer telefonu",
        "Adres e-mail",
        "Miejscowość budynku",
        "Ulica budynku",
        "Numer ewidencyjny działki",
        "Obręb ewidencyjny",
    ):
        assert expected in input_labels, (expected,input_labels)
    assert "Klauzula informacyjna" in [p["title"] for p in corrected["pages"]]
    assert len([f for f in labels if f["type"]=="INFO_BLOCK"]) == 1
    assert all("administratorem" not in label.lower() for label in input_labels)
    assert all(f["type"]!="TEXTAREA" for f in labels)
    result,check=convert(corrected)
    assert check["schema_valid"] and check["valid"],check
    real_fields=[c["field"] for tab in result["tabs"] if tab["type"]=="MAIN"
                 for section in tab["questions"]
                 for c in section["field"].get("repeatingSectionGrid",[])]
    assert len([f for f in real_fields if f["type"]=="TEXT_BLOCK"])==1
    assert len([f for f in real_fields if f["type"]=="TEXT_FIELD"])>=7
    assert any(f["type"]=="DATEPICKER" for f in real_fields)
    assert all(f["type"]!="TEXTAREA" for f in real_fields)
    assert assess(zones.body,corrected)["ok"]
    again,changes2=repair_form(corrected,zones)
    assert again==corrected
    assert changes2==[]

def test_only_legal_text_is_not_graded_as_valid_application():
    zones=split_legal_notice(SOURCE)
    a={"title":"Klauzula informacyjna","pages":[{
        "title":"Klauzula informacyjna",
        "sections":[{"title":"RODO","fields":[
            {"label":"Administratorem państwa danych...","type":"INFO_BLOCK",
             "content":zones.legal}]}]}]}
    result=assess(zones.body,a)
    assert not result["ok"]
    assert result["input_fields"]==0

def test_unrelated_form_is_preserved():
    body="Zgłoszenie awarii\nOpis zgłoszenia:"
    a={"title":"Zgłoszenie","pages":[{"title":"Dane","sections":[{
        "title":"Dane","fields":[{"label":"Opis zgłoszenia","type":"TEXTAREA"}]}]}]}
    out,changes=repair_form(a,split_legal_notice(body))
    assert out==a and changes==[]

def test_real_checkbox_consent_not_removed():
    src="WNIOSEK\nWnioskodawca...\nKLAUZULA INFORMACYJNA\nAdministratorem danych jest gmina. "+("RODO "*70)
    val={"title":"Zgłoszenie","pages":[{"title":"Dane","sections":[{"title":"Zgody",
      "fields":[{"label":"Zapoznałem się z informacją RODO","type":"CHECKBOX","options":[]}]}]}]}
    out,_=repair_form(val,split_legal_notice(src))
    labels=[f["label"] for p in out["pages"] for s in p["sections"] for f in s["fields"]]
    assert "Zapoznałem się z informacją RODO" in labels

def test_image_crop_only_when_legal_zone_detected():
    im=Image.new("RGB",(724,2048),"white")
    pen=ImageDraw.Draw(im)
    for y in (130,180,220,460,520,580,900,1150,1220,1300,1420,1500):
        pen.text((40,y),"Example source line TEST",fill="black")
    b=BytesIO(); im.save(b,format="JPEG",quality=85)
    zones=split_legal_notice(SOURCE)
    processed,meta=primary_image_crop(b.getvalue(),".jpeg",zones)
    assert meta["vision_cropped"] and meta["vision_crop_height"]<2048
    from PIL import Image as P
    with P.open(BytesIO(processed)) as preview:
        assert preview.height>350
    _,not_cropped=primary_image_crop(b.getvalue(),".jpeg",split_legal_notice("Opis zgłoszenia"))
    assert not not_cropped["vision_cropped"]
