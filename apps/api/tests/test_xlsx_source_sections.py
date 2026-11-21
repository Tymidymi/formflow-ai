"""Generic XLSX native layout tests — unrelated to the uploaded form category.

The source workbook, not an LLM's preferred sections, defines hierarchy.
Same-caption fields in different printed regions must survive separately.
"""
from __future__ import annotations

import asyncio
import importlib.util
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Border, Font, Side

from app import structured_extraction
from app.canonical_form import canonicalize
from app.coi_builder import convert

THIN=Side(style="thin")


def source_reader():
    path=Path(__file__).resolve().parents[2]/"extractor"/"xlsx_sparse.py"
    spec=importlib.util.spec_from_file_location("xlsx_source_native",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample():
    book=Workbook()
    sheet=book.active
    sheet.title="Rejestr narzędzi"
    sheet["A1"]="Zgłoszenie urządzenia";sheet["A1"].font=Font(bold=True)
    def heading(row,value):
        c=sheet.cell(row,1,value)
        c.font=Font(bold=True)
        c.border=Border(bottom=THIN)
    def field(row,label,start=7,end=20):
        sheet.cell(row,1,label)
        for col in range(start,end+1):
            sheet.cell(row,col).border=Border(top=THIN,bottom=THIN)
        sheet.cell(row,start).border=Border(left=THIN,top=THIN,bottom=THIN)
        sheet.cell(row,end).border=Border(right=THIN,top=THIN,bottom=THIN)
    heading(3,"1. Instrukcje")
    sheet["A4"]="Wypełniaj czytelnie. Podpisy elektroniczne nie są wymagane."
    heading(6,"2. Dane uczestników")
    heading(8,"2.1. Operator urządzenia")
    field(10,"Imię i nazwisko")
    field(12,"Miejscowość")
    heading(14,"2.2. Odbiorca urządzenia")
    field(16,"Imię i nazwisko")
    field(18,"Miejscowość")
    heading(20,"3. Parametry techniczne")
    field(22,"Typ urządzenia")
    heading(24,"4. Pouczenie prawne")
    sheet["A26"]="Należy zachować instrukcję do wglądu."
    output=BytesIO();book.save(output)
    return output.getvalue()


def test_native_headings_sections_and_writable_box_anchors():
    data=source_reader().extract_xlsx(sample())
    assert data["engine"]=="xlsx-structure-aware"
    assert data["document_title"]=="Zgłoszenie urządzenia"
    parts=data["source_sections"]
    sub=[x for x in parts if x["section_title"].startswith("2.")]
    assert [x["section_title"] for x in sub]==[
        "2.1. Operator urządzenia","2.2. Odbiorca urządzenia"]
    assert all(x["group_title"]=="2. Dane uczestników" for x in sub)
    assert [[a["label"] for a in x["source_anchors"]] for x in sub]==[
        ["Imię i nazwisko","Miejscowość"],
        ["Imię i nazwisko","Miejscowość"]]
    assert "DRUKOWANE PUSTE POLE" in sub[0]["text"]
    legal=next(x for x in parts if x["section_title"].startswith("4."))
    assert legal["info_only"] is True
    instructions=next(x for x in parts if x["section_title"].startswith("1."))
    assert instructions["info_only"] is True


def test_model_flattening_cannot_merge_distinct_native_sections(monkeypatch):
    data=source_reader().extract_xlsx(sample())
    async def llm(input_text,images,prompt):
        # Deliberately wrong top-level structure and missing one printed
        # caption: the source section contract must restore it.
        labels=[]
        if "2.1." in input_text:labels=["Imię i nazwisko"]
        elif "2.2." in input_text:labels=["Miejscowość"]
        elif "3." in input_text:labels=["Typ urządzenia"]
        return {"title":"Nieprawidłowy tytuł","pages":[{"title":"Jedna strona",
            "sections":[{"title":"Wszystkie dane w jednym miejscu",
                "fields":[{"label":label,"type":"TEXT_FIELD","required":False,
                            "options":[],"evidence":label}
                          for label in labels]}]}]},{"usage":{}}
    monkeypatch.setattr(structured_extraction,"generate",llm)
    async def fake_one(*args,**kwargs):return []
    monkeypatch.setattr(structured_extraction,"consolidate_choice_fields",
                        lambda model:0)
    converted,stats,reports=asyncio.run(structured_extraction.extract(
        data["text"],[],source_sections=data["source_sections"],
        source_title=data["document_title"]))
    valid=canonicalize(converted)
    assert valid["title"]=="Zgłoszenie urządzenia"
    target=next(x for x in valid["pages"]
                if x["title"]=="2. Dane uczestników")
    assert [s["title"] for s in target["sections"]]==[
        "2.1. Operator urządzenia","2.2. Odbiorca urządzenia"]
    assert [[f["label"] for f in sec["fields"]] for sec in target["sections"]]==[
        ["Imię i nazwisko","Miejscowość"],
        ["Imię i nazwisko","Miejscowość"]]
    coi,schema=convert(converted)
    assert schema["valid"]
    print("COI groups",[(p["title"],[s["field"]["title"]
           for s in p.get("questions",[])]) for p in coi["tabs"][:-1]])
    section_names=[q["field"]["title"] for tab in coi["tabs"]
                   for q in tab.get("questions",[])]
    assert "2.1. Operator urządzenia" in section_names
    assert "2.2. Odbiorca urządzenia" in section_names
    assert stats["pages_processed"]>=3
    assert sum(x.get("source_anchors_restored",0) for x in reports)>=2


def test_filled_merged_instruction_box_is_not_an_answer_field():
    from openpyxl import Workbook
    from openpyxl.styles import Border,Side,Font
    book=Workbook();s=book.active
    s["A1"]="Formularz danych";s["A1"].font=Font(bold=True)
    s["A3"]="1. Instrukcje";s["A3"].font=Font(bold=True)
    s["A3"].border=Border(bottom=THIN)
    s["B5"]="Pisz czytelnie drukowanymi literami."
    s.merge_cells("B5:R5")
    for col in range(2,19):
        c=s.cell(5,col)
        c.border=Border(top=THIN,bottom=THIN)
    s["A7"]="2. Dane";s["A7"].font=Font(bold=True)
    s["A7"].border=Border(bottom=THIN)
    s["A9"]="Nazwa";s["H9"].border=Border(left=THIN,right=THIN,top=THIN,bottom=THIN)
    out=BytesIO();book.save(out)
    source=source_reader().extract_xlsx(out.getvalue())
    read_only=next(x for x in source["source_sections"] if x["section_title"].startswith("1."))
    assert read_only["info_only"]
    assert not read_only["source_anchors"]
    assert "DRUKOWANE PUSTE POLE" not in read_only["text"]
    entry=next(x for x in source["source_sections"] if x["section_title"].startswith("2."))
    assert [f["label"] for f in entry["source_anchors"]]==["Nazwa"]


def test_neighboring_date_hint_does_not_cast_amount_as_date():
    from app.source_region_reconcile import enforce_source_region
    page=structured_extraction.Page(
        1,"Sekcja: Rejestr\n[Wiersz 10] A: Data | [DRUKOWANE PUSTE POLE]\n"
        "[Wiersz 11] B: DD-MM-RRRR\n"
        "[Wiersz 14] A: Kwota | [DRUKOWANE PUSTE POLE]\n",
        None,"Rejestr","Rejestr",
        ({"label":"Data","row":10,"kind_hint":"TEXT_FIELD"},
         {"label":"Kwota","row":14,"kind_hint":"TEXT_FIELD"}))
    result,n=enforce_source_region({"title":"Dane","pages":[]},page)
    fields=result["pages"][0]["sections"][0]["fields"]
    assert [(f["label"],f["type"]) for f in fields]==[
        ("Data","DATEPICKER"),("Kwota","TEXT_FIELD")]


def test_source_boxes_override_fabricated_choice_inputs_and_ground_conditions():
    from app.source_region_reconcile import enforce_source_region
    page=structured_extraction.Page(
        1,
        "Sekcja: 4. Sposób odbioru urządzenia\n"
        "[Wiersz 5] L: [DRUKOWANE PUSTE POLE L5:L5] | N: Odbiór osobisty\n"
        "[Wiersz 7] L: [DRUKOWANE PUSTE POLE L7:L7] | N: Przesyłka\n"
        "[Wiersz 9] K: ⓘ Jeśli wybierzesz tę formę, podaj adres.\n"
        "[Wiersz 11] A: Adres | L: [DRUKOWANE PUSTE POLE L11:Z11]\n",
        None,"4. Informacje dotyczące sposobu odbioru urządzenia",
        "4. Informacje dotyczące sposobu odbioru urządzenia",
        ({"label":"Odbiór osobisty","row":5,"kind_hint":"CHECKBOX"},
         {"label":"Przesyłka","row":7,"kind_hint":"CHECKBOX"},
         {"label":"Adres","row":11,"kind_hint":"TEXT_FIELD"}))
    proposal={"title":"Dane","pages":[{"title":"Wszystkie pola","sections":[
        {"title":"Bez podziału","fields":[
           {"label":"Sposób odbioru urządzenia","type":"TEXT_FIELD"},
           {"label":"Odbiór osobisty","type":"CHECKBOX","options":[]},
           {"label":"Przesyłka","type":"CHECKBOX","options":[]},
           {"label":"Adres","type":"TEXT_FIELD","evidence":"Adres",
            "source_line":4}]}]}]}
    fields,n=enforce_source_region(proposal,page)
    values=fields["pages"][0]["sections"][0]["fields"]
    assert len(values)==2,values
    choice=next(f for f in values if f["type"]=="CHECKBOX")
    assert choice["options"]==["Odbiór osobisty","Przesyłka"]
    dependent=next(f for f in values if f["label"]=="Adres")
    assert dependent["show_when"]=={
        "field_ref":choice["source_choice_ref"],"value":"Przesyłka"}
    form,contract=convert(fields)
    assert contract["valid"]
    items=form["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    address=next(x["field"] for x in items if x["field"]["title"]=="Adres")
    assert len(address["states"])==1
    assert "Przesyłka" in address["states"][0]["query"]


def test_two_printed_attachment_checkboxes_do_not_become_file_uploads():
    from app.source_region_reconcile import enforce_source_region
    page=structured_extraction.Page(
        1,
        "Sekcja: Wykaz załączników\n"
        "[Wiersz 3] J: [DRUKOWANE PUSTE POLE J3:J3] | L: Kopia dokumentu A\n"
        "[Wiersz 5] J: [DRUKOWANE PUSTE POLE J5:J5] | L: Kopia dokumentu B",
        None,"Załączniki","Wykaz załączników",
        ({"label":"Kopia dokumentu A","row":3,"kind_hint":"CHECKBOX"},
         {"label":"Kopia dokumentu B","row":5,"kind_hint":"CHECKBOX"}))
    proposal={"title":"Dokument","pages":[{"title":"Załączniki",
        "sections":[{"title":"Załączniki","fields":[
            {"label":"Kopia dokumentu A","type":"FILE_UPLOADER"},
            {"label":"Kopia dokumentu B","type":"FILE_UPLOADER"}]}]}]}
    resolved,_=enforce_source_region(proposal,page)
    found=resolved["pages"][0]["sections"][0]["fields"]
    assert len(found)==1
    assert found[0]["type"]=="CHECKBOX"
    assert found[0]["options"]==["Kopia dokumentu A","Kopia dokumentu B"]


def test_inflected_question_heading_does_not_create_extra_text_field():
    from app.source_region_reconcile import enforce_source_region
    page=structured_extraction.Page(
        1,
        'Sekcja źródłowa: 5. Informacje dotyczące sposobu odbioru\n'
        '[Wiersz 60] [DRUKOWANE PUSTE POLE L60:L60] | N: Osobiście\n'
        '[Wiersz 62] [DRUKOWANE PUSTE POLE L62:L62] | N: Kurierem\n'
        '[Wiersz 64] ⓘ Jeśli wybierzesz tę formę, wpisz poniżej adres\n'
        '[Wiersz 66] A: Adres | [DRUKOWANE PUSTE POLE L66:AJ66]',
        None,'5. Informacje dotyczące sposobu odbioru',
        '5. Informacje dotyczące sposobu odbioru',
        ({'label':'Osobiście','row':60,'kind_hint':'CHECKBOX'},
         {'label':'Kurierem','row':62,'kind_hint':'CHECKBOX'},
         {'label':'Adres','row':66,'kind_hint':'TEXT_FIELD'}))
    model={'title':'Zgłoszenie','pages':[{'title':'Dane','sections':[{
        'title':'Dane','fields':[
            {'label':'Sposób odbioru','type':'TEXT_FIELD'},
            {'label':'Osobiście','type':'CHECKBOX'},
            {'label':'Kurierem','type':'CHECKBOX'},
            {'label':'Adres','type':'TEXT_FIELD'}]}]}]}
    value,_=enforce_source_region(model,page)
    fields=value['pages'][0]['sections'][0]['fields']
    assert len(fields)==2, fields
    assert [(f['type'],f['label']) for f in fields]==[
        ('CHECKBOX','Informacje dotyczące sposobu odbioru'),
        ('TEXT_FIELD','Adres')]
    assert fields[1]['show_when']['value']=='Kurierem'


def test_radio_guess_for_choice_heading_does_not_duplicate_printed_checkbox_group():
    from app.source_region_reconcile import enforce_source_region
    page=structured_extraction.Page(
        1,'Sekcja źródłowa: 4. Informacje dotyczące sposobu odbioru\n'
          '[Wiersz 3] [DRUKOWANE PUSTE POLE L3:L3] | N: Osobiście\n'
          '[Wiersz 5] [DRUKOWANE PUSTE POLE L5:L5] | N: Kurierem\n'
          '[Wiersz 8] A: Nazwa | [DRUKOWANE PUSTE POLE L8:AA8]',
        None,'4. Informacje dotyczące sposobu odbioru',
        '4. Informacje dotyczące sposobu odbioru',
        ({'label':'Osobiście','row':3,'kind_hint':'CHECKBOX'},
         {'label':'Kurierem','row':5,'kind_hint':'CHECKBOX'},
         {'label':'Nazwa','row':8,'kind_hint':'TEXT_FIELD'}))
    proposal={'title':'Test','pages':[{'title':'Strona','sections':[{
        'title':'Sekcja','fields':[
            {'label':'Sposób odbioru','type':'RADIO',
             'options':['Pocztą','Osobiście']},
            {'label':'Nazwa','type':'TEXT_FIELD'}]}]}]}
    value,_=enforce_source_region(proposal,page)
    fields=value['pages'][0]['sections'][0]['fields']
    assert len(fields)==2,fields
    assert [f['type'] for f in fields]==['CHECKBOX','TEXT_FIELD']
    assert fields[0]['options']==['Osobiście','Kurierem']
