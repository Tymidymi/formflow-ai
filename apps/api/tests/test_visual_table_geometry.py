"""Vision + noisy OCR can reconstruct arbitrary repeated table geometry."""
import asyncio
from app import visual_tables as vt

OCR = """[Strona 1/2]
WNIOSEK O WYKONANIE PRAC
a) Obszar pierwszy
GNIQOSE .... SZEROKOŚĆ .... RBZOM .... M2
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
b) Obszar drugi
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
DHUGOŚĆ .... SZETOKOŚĆ .... FAZOM .... M2
c) Obszar trzeci
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
d) Obszar czwarty
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
dłUgośŚć .... SZETOKOŚĆ .... TAZEM .... M2
Całkowita powierzchnia .......... M2
"""

def test_reconstructs_24_cells_despite_noisy_ocr_and_wrong_model_row_count():
    rough=[{"group":"WNIOSEK O WYKONANIE PRAC","rows":4,
            "columns":["długość","szerokość","razem"],
            "type":"NUMBER","evidence":"fragment źródła"}]
    recovered=vt.recover_groups_from_ocr(OCR,rough)
    assert [(x["rows"],x["group"]) for x in recovered]==[
        (2,"Obszar pierwszy"),(2,"Obszar drugi"),
        (2,"Obszar trzeci"),(2,"Obszar czwarty")]
    items=vt.expand(recovered,1)
    assert len(items)==24
    assert all(x["source_page"]==1 for x in items)

def test_no_inferred_table_from_ordinary_dates():
    plain="WNIOSEK\nTermin od ........... do ...........\nData ................"
    geometry=[{"group":"Tabela 1","rows":2,"columns":["Od","Do"],
               "type":"DATEPICKER","evidence":"X"}]
    # No independent evidence for a repeated, multi-column table.
    assert vt.recover_groups_from_ocr(plain,geometry)==[]

def test_visual_model_only_supplies_structure_and_units_are_not_columns(monkeypatch):
    async def fake_generate(text,images,prompt=None):
        return {"pages":[{"tables":[{"group":"Wykaz temperatur",
            "rows":3,"columns":["Wartość","Wynik","m2"],
            "cell_type":"NUMBER","source_quote":"Wykaz temperatur"}]}]},{
            "model":"synthetic","usage":{}}
    monkeypatch.setattr(vt,"generate",fake_generate)
    layout=asyncio.run(vt.visually_detect("Wykaz temperatur",("image/jpeg",b"x")))
    assert len(layout)==1
    assert layout[0]["columns"]==["Wartość","Wynik"]
    assert len(vt.expand(layout,1))==6

def test_deletes_only_fields_already_represented_by_visual_table():
    tables=[{"group":"Obszar pierwszy","rows":2,"columns":["Długość","Szerokość","Razem"]}]
    assert vt.likely_table_duplicate({"label":"Długość — Obszar pierwszy"},tables)
    assert not vt.likely_table_duplicate({"label":"Adres wnioskodawcy"},tables)


def test_source_quoted_column_duplicates_not_returned_as_new_fields(monkeypatch):
    import app.structured_extraction as inventory
    source=("[Strona 1/1]\nFORMULARZ POMIARU\n"
            "a) Pierwszy obszar\n"
            "X ................ Y ................ Z ................\n"
            "X ................ Y ................ Z ................\n"
            "b) Drugi obszar\n"
            "X ................ Y ................ Z ................\n"
            "X ................ Y ................ Z ................\n")
    async def fake_model(text,images,prompt=None):
        return {"title":"Pomiar","pages":[{"title":"Pomiary",
         "sections":[{"title":"Pomiar","fields":[
            {"label":f"Pomiar — wiersz {n} — {letter}",
             "type":"NUMBER","evidence":"X ................ Y ................ Z ................"}
            for n in (1,2,3,4) for letter in ("X","Y","Z")
          ]}]}]},{"model":"mock","usage":{}}
    async def geometry(text,image):
        return [{"group":"Pomiar","rows":4,
                 "columns":["Wartość x","Wartość y","Wartość z"],
                 "type":"NUMBER","evidence":"X ................ Y ................ Z ................"}]
    monkeypatch.setattr(inventory,"generate",fake_model)
    monkeypatch.setattr(inventory,"visually_detect",geometry)
    data,report,pages=__import__("asyncio").run(
        inventory.extract(source,[("image/jpeg",b"test")],
            image_page_numbers=[1],pages_expected=1))
    labels=[f["label"] for p in data["pages"] for s in p["sections"] for f in s["fields"]]
    assert len(labels)>=12
    assert not any(label.startswith("Pomiar — wiersz") for label in labels)


def test_document_checklist_is_not_a_fake_table_even_when_vision_says_so():
    document=("4. Dokumenty wymagane do zgłoszenia:\n"
              "- Plan orientacyjny obszaru.\n"
              "- Szczegółowy schemat instalacji.\n"
              "- Harmonogram prac.\n"
              "- Potwierdzenie pełnomocnictwa.\n")
    guessed=[{"group":"Wymagane dokumenty","rows":4,
              "columns":["Plan orientacyjny","Schemat instalacji",
                         "Harmonogram prac","Pełnomocnictwo"],
              "type":"TEXT_FIELD","evidence":"Wymagane dokumenty"}]
    assert vt.recover_groups_from_ocr(document,guessed)==[]


def test_false_vision_table_from_four_bulleted_statements_is_rejected():
    """A generic vertical checklist must not turn into an NxN table."""
    lines = """[Strona 2/2]
4. Dodatkowe materiały wymagane do zgłoszenia:
- Plan orientacyjny.
- Szczegółowy opis stanu.
- Harmonogram wykonania.
- Projekt organizacji.
Oświadczenie: zapoznałem się z informacją.
"""
    alleged=[{"group":"4. Dodatkowe materiały wymagane do zgłoszenia",
              "rows":4,
              "columns":["Plan orientacyjny","Szczegółowy opis",
                         "Harmonogram wykonania","Projekt organizacji"],
              "type":"TEXT_FIELD","evidence":"materiały wymagane"}]
    assert vt.recover_groups_from_ocr(lines,alleged)==[]

def test_real_ocr_repeated_column_rows_survive_source_evidence_gate():
    lines="""1. Zestawienie wartości:
a) Strefa Alfa
długość ................... szerokość ............... wartość ..............
długość ................... szerokość ............... wartość ..............
b) Strefa Beta
długość ................... szerokość ............... wartość ..............
długość ................... szerokość ............... wartość ..............
"""
    alleged=[{"group":"Zestawienie wartości","rows":3,
              "columns":["długość","szerokość","wartość"],
              "type":"NUMBER","evidence":"Zestawienie wartości"}]
    verified=vt.recover_groups_from_ocr(lines,alleged)
    assert len(verified)==2
    assert [g["rows"] for g in verified]==[2,2]
    assert len(vt.expand(verified,1))==12
