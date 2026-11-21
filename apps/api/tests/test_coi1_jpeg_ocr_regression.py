"""Real OCR excerpt from user-supplied 724 x 2048 JPEG (COI #1).

The earlier model ignored the operative page and created editable RODO textareas.
This fixture retains key OCR mistakes verbatim, to ensure template fallback
does not depend on perfect recognition of tiny captions.
"""
from app.document_zones import split_legal_notice
from app.form_repair import repair_form
from app.semantic_quality import normalize_semantic
from app.coi_builder import convert
from app.quality_gate import assess

ACTUAL_OCR = """(data)
Wnioskodawca: Adresat:
(imię i nazwisko/nazwa wnioskodawcy) Wójt Gminy Elbląg
O ONA 82-300 Elbląg
(adres)
(nr telefonwadres e-mail)
WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO
Wnoszę o ustalenie numeru porządkowego budynkowi zlokalizowanemu
W MCO WOŚ wazy wizowe PRZ UO zawod
mr ewidencyjny działki .............W OBRĘbIE eee saeeeeroezen
(podpis wnioskodawcy)
* | Dane nieobowiązkowe.
KLAUZULA INFORMACYJNA
umracja porządkowa nieruchomości
Zgodnie z an. ust. | 2 Roporządzei Pułamenu Europejskiego Rady (UE).
1. Administra Puta duch owcbonych jes Gina Eig
2. Wyznmyiiny Isola Ołesy Dazych.
3. łatwa din robo tly para w el usa powierzenia mune poządkoweo
4. Państ dane oxbowe możemy przekazywać uprawnionym podmiotom.
5. Polana don orkowie będą ...
6. Pasta dine osobowe będą przetwarzane.
7. Mają Państwo prawo ...
8. Podania dah wymaga ...
9. Przysłje prawo skargi do organu nadzorczego.
10. Państwa dane nie będą przetwarzane w sposób zautomatyzowany.
"""
FAILED_RESULT = {"title":"Klauzula informacyjna","pages":[{
  "title":"Klauzula informacyjna",
  "sections":[{"title":"Informacje o przetwarzaniu danych osobowych",
    "fields":[{"label":str(i)+". Państwa dane osobowe będą przetwarzane...",
               "type":"TEXTAREA","required":False,"options":[]}
              for i in range(1,11)]}]}]}

def test_imperfect_real_ocr_still_recovers_core_form_not_rodo():
    z=split_legal_notice(ACTUAL_OCR)
    assert z.was_split and "KLAUZULA" not in z.body
    repaired,fixes=repair_form(FAILED_RESULT,z)
    final,_=normalize_semantic(z.body,repaired)
    fields=[f for p in final["pages"] for sec in p["sections"] for f in sec["fields"]]
    interactive=[f for f in fields if f["type"]!="INFO_BLOCK"]
    labels={x["label"] for x in interactive}
    assert len(interactive)>=9,labels
    for label in ("Numer telefonu","Miejscowość budynku","Ulica budynku",
                  "Numer ewidencyjny działki","Obręb ewidencyjny",
                  "Data wniosku","Adres e-mail"):
        assert label in labels,(label,labels)
    assert len([f for f in fields if f["type"]=="INFO_BLOCK"])==1
    assert all(x["type"]!="TEXTAREA" for x in interactive)
    result,validation=convert(final)
    assert validation["schema_valid"] and validation["valid"],validation
    assert assess(z.body,final)["ok"]
    assert any(c["type"]=="reference_field_recovered" for c in fixes)

def test_no_reference_fallback_for_other_applications():
    source="WNIOSEK O WYDANIE ZAŚWIADCZENIA\nWnioskodawca:\n(adres)"
    model={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"A","fields":[{"label":"Opis","type":"TEXTAREA"}]}]}]}
    out,changes=repair_form(model,split_legal_notice(source))
    labels=[f["label"] for p in out["pages"] for sec in p["sections"] for f in sec["fields"]]
    assert not {"Miejscowość budynku","Ulica budynku","Obręb ewidencyjny"} & set(labels)
    assert all(x["type"]!="reference_field_recovered" for x in changes)

def test_model_invented_administrative_address_fields_are_removed():
    input_labels=[
        "Imię i nazwisko/nazwa wnioskodawcy",
        "Adres",
        "Numer telefonu",
        "Adres e-mail",
        "Miejscowość",
        "Województwo",
        "Powiat",
        "Gmina",
        "Kod pocztowy",
        "Ulica",
        "Numer budynku",
        "Numer lokalu",
        "Numer ewidencyjny działki",
    ]
    model={"title":"Wniosek o ustalenie numeru porządkowego","pages":[
        {"title":"Dane","sections":[{"title":"A","fields":[
            {"label":label,"type":"TEXT_FIELD","required":False,"options":[]}
            for label in input_labels]}]}]}
    zones=split_legal_notice(ACTUAL_OCR)
    fixed,changes=repair_form(model,zones)
    labels=[f["label"] for p in fixed["pages"] for s in p["sections"]
            for f in s["fields"] if f["type"]!="INFO_BLOCK"]
    for unwanted in ("Województwo","Powiat","Gmina","Kod pocztowy",
                     "Numer budynku","Numer lokalu"):
        assert unwanted not in labels
    assert len(labels)==9,labels
    assert fixed["title"]=="Wniosek o ustalenie numeru porządkowego nieruchomości"
    assert sum(x["type"]=="ungrounded_reference_field_removed" for x in changes)==6
    coi,validation=convert(fixed)
    assert validation["schema_valid"] and validation["valid"]
