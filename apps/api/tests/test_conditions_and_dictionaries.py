"""COI runtime conditions must be explicitly provided, not guessed from forms."""
from app.coi_builder import convert

def test_explicit_generic_show_when_is_respected():
    semantic={"title":"Formularz testowy","pages":[{"title":"Dane","sections":[{
        "title":"Dane","fields":[
            {"label":"Rodzaj zgłoszenia","type":"RADIO","required":False,
             "options":["Własne","Przez pełnomocnika"]},
            {"label":"Dane pełnomocnika","type":"TEXT_FIELD","required":False,
             "options":[],"show_when":{"field":"rodzaj_zgloszenia",
                                        "value":"Przez pełnomocnika"}}
        ]}]}]}
    form,valid=convert(semantic)
    assert valid["valid"] and valid["schema_valid"]
    children=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    target=children[1]["field"]
    assert target["type"]=="TEXT_FIELD"
    assert len(target["states"])==1
    assert target["states"][0]["type"]=="SHOW"
    assert "Przez pełnomocnika" in target["states"][0]["query"]

def test_arbitrary_conditions_are_not_invented():
    semantic={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"Dane","fields":[
            {"label":"Podaj dane podmiotu","type":"TEXT_FIELD",
             "options":[],"required":False}
        ]}]}]}
    form,valid=convert(semantic)
    assert valid["valid"] and valid["schema_valid"]
    child=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    assert child["states"]==[]

def test_dictionary_country_select_preserved():
    semantic={"title":"Wniosek","pages":[{"title":"Dane","sections":[{
        "title":"Adres","fields":[
            {"label":"Kraj","type":"SELECT","required":False,"options":[]},
        ]}]}]}
    form,valid=convert(semantic)
    f=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"][0]["field"]
    assert f["type"]=="SELECT"
    assert f["dictionaryName"]=="Kraje"
    assert valid["schema_valid"]
