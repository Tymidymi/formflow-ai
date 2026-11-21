"""Regression for multiple standalone declarations hidden under one preamble."""
from app.semantic_quality import normalize_semantic
from app.coi_builder import convert

TEXT="""WNIOSEK o wynajęcie świetlicy
Wnioskodawca: Jan Nowak __________
Osoba odpowiedzialna: ____________
4. Jednocześnie oświadczam, że (w przypadku innej osoby dołącz zgody):
1) zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej,
2) w czasie najmu odpowiadam za ład i porządek w świetlicy,
3) zobowiązuję się do przestrzegania przepisów sanitarnych, BHP i p.poż.,
4) na okres wynajmu ponoszę odpowiedzialność za powierzone mienie.
(podpis)
"""
MODEL={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
    "title":"Oświadczenia","fields":[
        {"label":"Imię i nazwisko","type":"TEXT_FIELD","options":[]},
        {"label":"4. Jednocześnie oświadczam, że (w przypadku innej osoby...)",
         "type":"CHECKBOX","options":[]}
    ]}]}]}
def fields(form):
    return [f for p in form["pages"] for s in p["sections"] for f in s["fields"]]
def test_four_distinct_declarations_recovered():
    fixed,changes=normalize_semantic(TEXT,MODEL)
    f=fields(fixed)
    choices=[x for x in f if x["type"]=="CHECKBOX"]
    assert len(choices)==4,[x["label"] for x in choices]
    assert all("Jednocześnie oświadczam" not in x["label"] for x in choices)
    assert len([x for x in changes if x["type"]=="source_declaration_recovered"])==4
    final,valid=convert(fixed)
    assert valid["schema_valid"] and valid["valid"]

def test_existing_checkbox_options_not_duplicated():
    previous={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"Oświadczenia","fields":[
            {"label":"zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej",
             "type":"CHECKBOX","options":[]},
            {"label":"w czasie najmu odpowiadam za ład i porządek w świetlicy",
             "type":"CHECKBOX","options":[]}
        ]}]}]}
    fixed,changes=normalize_semantic(TEXT,previous)
    assert len([f for f in fields(fixed) if f["type"]=="CHECKBOX"])==4
    repeated,again=normalize_semantic(TEXT,fixed)
    assert repeated==fixed
    assert not [x for x in again if x["type"]=="source_declaration_recovered"]

def test_no_declaration_section_no_invention():
    fixed,changes=normalize_semantic(
        "WNIOSEK o wydanie dokumentu\nNazwisko______\n1) telefon\n2) adres",MODEL)
    assert not [x for x in changes if x["type"]=="source_declaration_recovered"]

def test_wrapped_declaration_preamble_like_actual_coi4_ocr():
    text=(
        "WNIOSEK o wynajem świetlicy\n"
        "Osoba odpowiedzialna: __________\n"
        "4. Jednocześnie oświadczam, że(w przypadku innej osoby niż wnioskodawca, zbiorcze\n"
        "oświadczenie tej osoby załączyć do wniosku):\n"
        "1) zapoznałem/am się z warunkami wynajmu świetlicy wiejskiej,\n"
        "2) w czasie najmu odpowiadam za ład i porządek w świetlicy oraz na ternie przyległym do\n"
        "świetlicy,\n"
        "3) zobowiązuję się do przestrzegania przepisów sanitarnych, BHP i p.poż. w czasie trwania\n"
        "przedsięwzięcia,\n"
        "4) na okres wynajmu ponoszę pełną odpowiedzialność za powierzone mienie.\n"
        "(czytelny podpis wnioskodawcy)\n"
    )
    fixed,changes=normalize_semantic(text,MODEL)
    choices=[x for x in fields(fixed) if x["type"]=="CHECKBOX"]
    assert len(choices)==4,choices
    assert "przyległym do świetlicy" in choices[1]["label"]
    assert "czasie trwania przedsięwzięcia" in choices[2]["label"]
    assert len([x for x in changes if x["type"]=="source_declaration_recovered"])==4

def test_parenthesized_example_is_not_an_extra_input():
    sample={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"Informacje","fields":[
            {"label":"1. Cel wynajęcia świetlicy:","type":"TEXT_FIELD","options":[]},
            {"label":"(rodzaj uroczystości, np. wesele, urodziny, zabawa itp.)",
             "type":"TEXT_FIELD","options":[]}
        ]}]}]}
    fixed,changes=normalize_semantic(
        "WNIOSEK\n1. Cel wynajęcia świetlicy: ____\n"
        "(rodzaj uroczystości, np. wesele, urodziny, zabawa itp.)",
        sample)
    labels=[x["label"] for x in fields(fixed)]
    assert "1. Cel wynajęcia świetlicy:" in labels
    assert not any(x.startswith("(rodzaj uroczystości") for x in labels)
    assert any(c["type"]=="parenthetical_example_removed" for c in changes)
