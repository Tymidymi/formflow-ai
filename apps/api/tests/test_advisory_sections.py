"""Document type #3 regression: legal/payment information is not a question."""
from app.document_zones import split_legal_notice
from app.form_repair import repair_form
from app.semantic_quality import normalize_semantic
from app.coi_builder import convert

SAMPLE=(
    "Wniosek o wydanie zaświadczenia\n"
    "Młynary, dnia........\n"
    "Wnioskodawca: imię i nazwisko ...................\n"
    "Adres zamieszkania ..........................\n"
    "PESEL ..........................\n"
    "Proszę o wydanie zaświadczenia o:\n"
    "☐ ilości posiadanych użytków\n"
    "☐ okresie posiadania gospodarstwa\n"
    "Zaświadczenie potrzebne jest celem przedłożenia w ...........\n"
    "/podpis/\n"
    "INFORMACJE:\n"
    "1. Opłata za wydanie zaświadczenia wynosi 17 zł od każdego egzemplarza.\n"
    "2. Opłatę skarbową należy wnieść przed złożeniem wniosku. "
    "Rachunek bankowy Urzędu Miejskiego znajduje się na oficjalnej stronie urzędu.\n"
    "3. Zwolnienie z opłaty skarbowej określają przepisy ustawy. "
    "Dokumenty do wglądu są dostępne w biurze obsługi mieszkańców.\n"
)
BAD={"title":"Wniosek o wydanie zaświadczenia","pages":[{
    "title":"Dane","sections":[{"title":"Wnioskodawca","fields":[
        {"label":"Imię i nazwisko","type":"TEXT_FIELD","options":[]},
        {"label":"PESEL","type":"TEXT_FIELD","options":[]},
        {"label":"/podpis/","type":"TEXT_FIELD","options":[]},
        {"label":"1. Opłata za wydanie zaświadczenia wynosi 17 zł od egzemplarza",
         "type":"TEXTAREA","options":[]},
    ]}]}]}
def test_advisory_end_is_separate_readonly_page():
    z=split_legal_notice(SAMPLE)
    assert z.was_split and z.reason=="supplement_information_heading"
    assert "INFORMACJE" not in z.body
    fixed,changes=repair_form(BAD,z)
    fixed,normalized=normalize_semantic(z.body,fixed)
    main=[f for pg in fixed["pages"] if pg["title"]!="Informacje i pouczenia"
          for sc in pg["sections"] for f in sc["fields"]]
    assert all(not f["label"].startswith("1. Opłata") for f in main)
    assert all("podpis" not in f["label"].lower() for f in main)
    legal=next(pg for pg in fixed["pages"] if pg["title"]=="Informacje i pouczenia")
    assert legal["sections"][0]["fields"][0]["type"]=="INFO_BLOCK"
    out,validation=convert(fixed)
    assert validation["valid"] and validation["schema_valid"]
    assert any(c["type"]=="paper_signature_removed" for c in normalized)

def test_midform_information_heading_is_not_cut_automatically():
    content="Wniosek\nInformacje:\nTelefon: ____________\nData: ____________"
    z=split_legal_notice(content)
    assert not z.was_split
    assert z.body==content

def test_short_advisory_section_not_automatically_cut():
    content="WNIOSEK O WYDANIE DECYZJI\nDane wnioskodawcy: _____\nINFORMACJE:\nUwaga."
    z=split_legal_notice(content)
    assert not z.was_split
