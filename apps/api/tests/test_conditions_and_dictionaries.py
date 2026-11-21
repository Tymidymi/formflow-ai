"""Regressions against the supplied COI reference JSONata shape."""
import copy

from app.coi_builder import convert
from app.conditional_rules import apply_conditions

HALL = """Wniosek o wynajęcie/użyczenie świetlicy wiejskiej.
Osoba odpowiedzialna za porządek i bezpieczeństwo (imię i nazwisko).
W przypadku innej osoby niż wnioskodawca, zbiorcze oświadczenie
tej osoby załączyć do wniosku.
"""

def semantic():
    return {"title":"Wniosek o świetlicę",
            "pages":[{"title":"Dane wnioskodawcy","sections":[{
                "title":"Dane odpowiedzialnego","fields":[
                    {"label":"Osoba odpowiedzialna (pełnoletnia) za utrzymanie porządku",
                     "type":"TEXT_FIELD","required":False,"options":[]},
                    {"label":"(imię i nazwisko – wnioskodawca, w przypadku innej osoby niż wnioskodawca - zgoda osoby odpowiedzialnej)",
                     "type":"TEXT_FIELD","required":False,"options":[]},
                    {"label":"Jednocześnie oświadczam, że (w przypadku innej osoby niż wnioskodawca, zbiorcze oświadczenie tej osoby załączyć do wniosku)",
                     "type":"TEXTAREA","required":False,"options":[]},
                ]}]}]}

def test_conditional_fields_use_coi_jsonata_and_match_reference():
    sem, changes = apply_conditions(HALL, semantic())
    assert changes
    form, validation = convert(sem)
    assert validation["schema_valid"] is True, validation
    assert validation["valid"] is True, validation
    children=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    fields={c["field"]["techName"]:c["field"] for c in children}
    choice=fields["kto_jest_osoba_odpowiedzialna"]
    assert choice["type"]=="RADIO"
    assert {o["name"] for o in choice["options"]}=={"Wnioskodawca","Inna osoba"}
    target=next(value for key,value in fields.items() if key.startswith("osoba_odpowiedzialna_p"))
    consent=fields["oswiadczenie_osoby_odpowiedzialnej"]
    assert target["states"][0]["type"]=="SHOW"
    query=target["states"][0]["query"]
    assert '"Inna osoba" in tabs[' in query
    assert "Dane wnioskodawcy" in query
    assert "kto_jest_osoba_odpowiedzialna" in query
    assert "repeatingSectionGrid" in query
    assert consent["states"]==target["states"]
    assert "dictionaryName" not in choice

def test_conditional_inference_is_idempotent_and_scoped():
    initial=semantic()
    first,changes=apply_conditions(HALL,initial)
    second,next_changes=apply_conditions(HALL,first)
    assert second==first
    assert next_changes==[]
    assert initial==semantic()
    irrelevant,_=apply_conditions("Dane posiadacza psa. Osoba odpowiedzialna",initial)
    assert irrelevant==initial

def test_dictionary_kraje_select_preserved():
    sem={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"Adres","fields":[
            {"label":"Kraj","type":"SELECT","required":False,"options":[]},
        ]}]}]}
    form,validation=convert(sem)
    field=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    assert field["type"]=="SELECT"
    assert field["dictionaryName"]=="Kraje"
    assert field["options"]==[]
    assert validation["schema_valid"]
