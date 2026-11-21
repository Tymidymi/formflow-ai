"""Conservative source-grounded corrections; no hallucinated fields or values."""
from app.semantic_quality import normalize_semantic
from app.coi_builder import convert

def model(*fields):
    return {"title":"Wniosek", "pages":[{"title":"Dane","sections":[
        {"title":"Wnioskodawca","fields":[
            {"label":name,"type":kind,"required":False,"options":[]} for name,kind in fields]}]}]}

SOURCE3="""Młynary, dnia……………………
………….
/ imię i nazwisko /
………….
/ adres /
………….
/ PESEL /
………….
/ nr telefonu /
Proszę o wydanie zaświadczenia o:
Zaświadczenie potrzebne jest celem przedłożenia w.
Podpis
"""

SOURCE4="""(miejscowość i data)
(imię i nazwisko wnioskodawcy)
(adres zamieszkania)
(nr telefonu)
Proszę o wynajem/użyczenie* świetlicy wiejskiej w ...
wraz z wyposażeniem w terminie od ………. do ……….
Przewidywana ilość uczestników: ...
Osoba odpowiedzialna ...
(Czytelny podpis wnioskodawcy)
"""

def flatten(semantic):
    return [f for p in semantic["pages"] for sec in p["sections"] for f in sec["fields"]]

def test_recovers_explicit_fields_and_date():
    src=model(("Inne","TEXT_FIELD"),("Podpis","TEXT_FIELD"))
    out,changes=normalize_semantic(SOURCE3,src)
    labels=[f["label"] for f in flatten(out)]
    assert "Imię i nazwisko" in labels
    assert "Adres" in labels
    assert "PESEL" in labels
    assert "Nr telefonu" in labels
    assert "Data złożenia wniosku" in labels
    assert "Podpis" not in labels
    assert any(x["type"]=="date_placeholder_recovered" for x in changes)
    assert all(x["label"]!="PESEL" for x in flatten(src)) # Does not mutate model
    result,validation=convert(out)
    assert validation["schema_valid"] and validation["valid"],validation

def test_recovers_rent_loan_and_two_date_range_with_idempotence():
    src=model(("miejscowość i data","TEXT_FIELD"),
              ("Przewidywana ilość uczestników","TEXT_FIELD"),
              ("Czytelny podpis wnioskodawcy","TEXT_FIELD"))
    out,changes=normalize_semantic(SOURCE4,src)
    fs=flatten(out)
    assert len([f for f in fs if f["type"]=="DATEPICKER"])==3
    assert any(f["type"]=="RADIO" and "użyczenie" in f.get("options",[]) for f in fs)
    assert any(f["type"]=="NUMBER" and "uczestników" in f["label"] for f in fs)
    assert all("podpis" not in f["label"].casefold() for f in fs)
    again,more=normalize_semantic(SOURCE4,out)
    assert flatten(again)==flatten(out)
    assert not more
    result,validation=convert(out)
    assert validation["valid"] and validation["schema_valid"]

def test_no_unsupported_fields_are_invented():
    src=model(("Opis zgłoszenia","TEXTAREA"))
    out,changes=normalize_semantic("Opis zgłoszenia",src)
    assert out==src and changes==[]
