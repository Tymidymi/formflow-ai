"""Document-independent extraction: no hardcoded corrections for COI examples."""
import asyncio
from io import BytesIO

from fastapi.testclient import TestClient

from app import structured_extraction as inventory
from app.layout_slots import extract_multislot_rows
from app.quality_gate import assess
from app.main import app
from app.document_zones import split_legal_notice

def multiline_table(name:str="Tabela pomiarów")->str:
    return "\n".join([
        name,
        "a/ Obszar A",
        *["długość .............................. szerokość ............................... suma ................................. m2" for _ in range(2)],
        "b/ Obszar B",
        *["długość .............................. szerokość ............................... suma ................................. m2" for _ in range(2)],
        "c/ Obszar C",
        *["długość .............................. szerokość ............................... suma ................................. m2" for _ in range(2)],
        "d/ Obszar D",
        *["długość .............................. szerokość ............................... suma ................................. m2" for _ in range(2)],
    ])

def test_table_extractor_detects_eight_rows_and_24_fields():
    fields,regions=extract_multislot_rows(multiline_table())
    assert len(fields)==24
    assert len(regions)==8
    assert all(x["type"]=="NUMBER" for x in fields)
    assert "Obszar A" in fields[0]["label"]
    assert "wiersz 2" in fields[3]["label"]
    assert "Obszar D" in fields[-1]["label"]
    assert all("szerokość" in x["label"] for x in fields[1::3])

def test_table_extractor_is_universal_not_bound_to_road_terms():
    doc=("Formularz rozliczenia\n"
         "a) Komórka pierwsza\n"
         "liczba ................ cena ................ opis ................\n"
         "liczba ................ cena ................ opis ................\n"
         "b) Komórka druga\n"
         "liczba ................ cena ................ opis ................\n")
    fields,regions=extract_multislot_rows(doc)
    assert len(fields)==9 and len(regions)==3
    assert fields[0]["type"]=="TEXT_FIELD"
    assert "Komórka druga" in fields[-1]["label"]
    assert fields[1]["label"].endswith("cena")

def test_source_pages_are_not_silently_dropped():
    source="[Strona 1/2]\nDane wnioskodawcy........\n[Strona 2/2]\nOpis wykonania ........"
    pages=inventory.split_pages(source,[],[])
    assert len(pages)==2
    assert [p.number for p in pages]==[1,2]
    assert "Opis wykonania" in pages[1].text

def test_office_long_text_is_not_truncated_by_page_split():
    source="\n".join("Opis pole i odpowiedź:\n" + ("tekst " * 25) for _ in range(85))
    pages=inventory.split_pages(source,[],[])
    assert len(pages)>=2
    assert "".join(p.text for p in pages).replace("\n","").replace(" ","")==source.replace("\n","").replace(" ","")

def test_generic_quality_blocks_major_omission():
    source=multiline_table()
    bad={"pages":[{"sections":[{"fields":[
        {"label":"Opis","type":"TEXT_FIELD"},
        {"label":"Kontakt","type":"TEXT_FIELD"}]}]}]}
    outcome=assess(source,bad)
    assert not outcome["ok"]
    assert outcome["source_blank_slots"]>=24
    assert outcome["blank_coverage_ratio"]<0.2
    assert any("znacznie mniej" in x for x in outcome["possible_missing"])

def test_generic_quality_accepts_complete_table_and_flags_truncation():
    source=multiline_table()
    fields,_=extract_multislot_rows(source)
    data={"pages":[{"sections":[{"fields":fields}]}]}
    assert assess(source,data)["ok"]
    assert not assess(source,data,vision_incomplete=True)["ok"]
    assert not assess(source,data,truncated=True)["ok"]

def test_new_inventory_does_not_insert_example_domain_fields(monkeypatch):
    source=("[Strona 1/1]\nWNIOSEK o działanie\n"
            "Termin od dnia ........... do dnia ...........\n"
            "w miejscowości ...........\n"
            +multiline_table())
    async def fake_model(txt,images,prompt=None):
        return {"title":"Wniosek o działanie","pages":[{
            "title":"Dane","sections":[{"title":"Dane",
                "fields":[{"label":"Miejscowość działania","type":"TEXT_FIELD",
                           "evidence":"w miejscowości","options":[],"required":False},
                          {"label":"Data od","type":"DATEPICKER",
                           "evidence":"Termin od","options":[],"required":False},
                          {"label":"Data do","type":"DATEPICKER",
                           "evidence":"do dnia","options":[],"required":False}]}]}]},{
            "model":"fake","usage":{},"images_sent":0}
    monkeypatch.setattr(inventory,"generate",fake_model)
    form,meta,reports=asyncio.run(inventory.extract(source,[],pages_expected=1))
    labels=[f["label"] for p in form["pages"] for s in p["sections"] for f in s["fields"]]
    assert len(labels)>=27,labels
    assert not any("wynajmu" in label.lower() for label in labels)
    assert not any("miejscowość budynku" in label.lower() for label in labels)
    assert reports[0]["mechanically_extracted_cells"]==24

def test_api_generates_full_generic_table_from_text_and_image(monkeypatch):
    import app.main as api
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","not-a-real-key")
    source="[Strona 1/1]\nWNIOSEK o rozliczenie\nNazwisko .......\n"+multiline_table()
    async def fake_extract(*args,**kwargs):
        return source,[("image/jpeg",b"\xff\xd8\xffsynthetic")],{
            "engine":"unit-fixture","pages":1,"vision_page_numbers":[1],
            "vision_incomplete":False,"truncated":False}
    async def fake_model(txt,images,prompt=None):
        return {"title":"Wniosek o rozliczenie","pages":[{"title":"Dane",
        "sections":[{"title":"Dane","fields":[
            {"label":"Nazwisko","type":"TEXT_FIELD","required":False,
             "evidence":"Nazwisko","options":[]}]}]}]},{
            "model":"unit-test","usage":{},"images_sent":len(images)}
    monkeypatch.setattr(api,"extract_with_backend",fake_extract)
    monkeypatch.setattr(inventory,"generate",fake_model)
    async def no_extra_table(*args,**kwargs):
        return []
    monkeypatch.setattr(inventory,"visually_detect",no_extra_table)
    out=TestClient(app).post("/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent":"true"},
        files={"file":("mock.pdf",b"%PDF-1.7\n%fixture","application/pdf")})
    assert out.status_code==200,out.text
    result=out.json()
    assert result["validation"]["schema_valid"]
    assert result["validation"]["valid"]
    assert result["quality"]["ok"]
    assert result["quality"]["source_blank_slots"]>=24
    assert result["quality"]["input_fields"]>=25
    assert result["inventory"]["pages"][0]["mechanically_extracted_cells"]==24
    output_labels=[e["field"]["title"] for t in result["form"]["tabs"]
                   for s in t["questions"] for e in s["field"].get("repeatingSectionGrid",[])]
    assert not any("wynajmu" in x.lower() for x in output_labels)
    assert len([x for x in output_labels if "wiersz" in x])==24

def test_generic_gdpr_citation_is_readonly_even_without_heading():
    source=("WNIOSEK o wykonanie prac\nNazwisko: _____\nOpis: _____\n"
            +("Prośba o rozpatrzenie sprawy. " * 8)
            +"\nZgodnie z art. 13 rozporządzenia UE 2016/679 RODO,\n"
            +("administratorem danych jest urząd; przysługują prawa "
              "dostępu do danych. " * 12))
    regions=split_legal_notice(source)
    assert regions.was_split
    assert "Zgodnie z art. 13" in regions.legal
    assert "Nazwisko" in regions.body

def test_exported_table_retains_source_row_and_column_grid():
    from app.coi_builder import convert
    cells,_=extract_multislot_rows(multiline_table())
    semantic={"title":"Dowolna tabela","pages":[
        {"title":"Pomiary","sections":[{"title":"Wartości","fields":cells[:6]}]}]}
    output,validation=convert(semantic)
    assert validation["valid"] and validation["schema_valid"],validation
    grid=output["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    assert len(grid)==6
    assert [(x["x"],x["y"],x["cols"]) for x in grid]==[
        (0,0,1),(1,0,1),(2,0,1),
        (0,1,1),(1,1,1),(2,1,1),
    ]

def test_unit_suffix_does_not_become_an_extra_input():
    """General geometry regression: one numeric blank plus printed unit."""
    page=inventory.Page(1,"Wielkość ................ m²",None)
    result={"pages":[{"sections":[{"fields":[
        {"label":"Wielkość","type":"NUMBER","source_line":1,"evidence":"Wielkość"},
        {"label":"m²","type":"NUMBER","source_line":1,"evidence":"Wielkość ................ m²"},
    ]}]}]}
    assert inventory._remove_unit_only_phantoms(result,page)==1
    assert [x["label"] for x in inventory._fields(result)]==["Wielkość"]


def test_unit_suffix_does_not_remove_other_distinct_fields():
    page=inventory.Page(1,"Masa ........ kg  Liczba ........ szt.",None)
    result={"pages":[{"sections":[{"fields":[
        {"label":"Masa","type":"NUMBER","source_line":1},
        {"label":"Liczba","type":"NUMBER","source_line":1},
    ]}]}]}
    assert inventory._remove_unit_only_phantoms(result,page)==0
    assert len(inventory._fields(result))==2
