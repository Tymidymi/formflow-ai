"""Regression: generic recovery from Qwen completion limits on Office and PDF."""
import asyncio
from io import BytesIO
from pathlib import Path
import importlib.util
import re

from PIL import Image
import pytest

from app.ai_provider import AIProviderError
from app.page_recovery import split_source_text,generate_page_with_recovery


def test_text_partition_never_drops_any_character():
    source="".join(f"[Wiersz {r}] A: Wartość pola {r}\n" for r in range(1,94))
    for count in (2,4,8):
        assert "".join(split_source_text(source,count))==source
    assert "".join(split_source_text("Nazwa "+
        "bardzo długa etykieta "*200,4)).startswith("Nazwa")


def test_xlsx_like_many_rows_survive_a_truncated_initial_response():
    text="".join(f"[Wiersz {i}] A: Pole_{i}\n" for i in range(1,92))
    calls=[]
    async def model(prompt_text,images,prompt):
        calls.append(prompt_text)
        if "CZĘŚĆ" not in prompt_text:
            raise AIProviderError("Limit",code="MODEL_OUTPUT_TRUNCATED")
        fields=[{"label":f"Pole_{i}","type":"TEXT_FIELD",
                 "evidence":f"Pole_{i}"} for i in
                map(int,re.findall(r"\bA: Pole_(\d+)\b",prompt_text))]
        return {"title":"Arkusz",
                "pages":[{"title":"Arkusz","sections":[{"title":"Dane",
                           "fields":fields}]}]}, {"usage":{"completion_tokens":40}}
    output,info=asyncio.run(generate_page_with_recovery(
        text,None,prompt="SOURCE",source_text=text,model_generate=model))
    fields=[f for p in output["pages"] for s in p["sections"] for f in s["fields"]]
    assert len(fields)==91
    assert {f["label"] for f in fields}=={f"Pole_{i}" for i in range(1,92)}
    assert info["recovered_fragments"]==2
    assert len(calls)==3


def test_recovery_increases_segmentation_when_a_half_still_truncates():
    text="".join(f"[Wiersz {i}] Pole_{i}\n" for i in range(1,81))
    calls=[]
    async def model(source,images,prompt):
        calls.append(source)
        if "CZĘŚĆ" not in source or "/2." in source:
            raise AIProviderError("Truncated",code="MODEL_OUTPUT_TRUNCATED")
        found=re.findall(r"Pole_(\d+)",source)
        return {"title":"Dane","pages":[{"title":"Dane","sections":[{
            "title":"Tabela","fields":[{"label":f"Pole_{index}","type":"TEXT_FIELD"}
                                        for index in found]}]}]},{}
    result,info=asyncio.run(generate_page_with_recovery(
        text,None,prompt="REVIEW",source_text=text,model_generate=model))
    found=[f["label"] for p in result["pages"] for s in p["sections"]
           for f in s["fields"]]
    assert set(found)=={f"Pole_{i}" for i in range(1,81)}
    assert info["recovered_fragments"]==4


def test_pdf_vision_recovery_crops_instead_of_repeating_entire_page():
    im=Image.new("RGB",(800,1600),"white")
    payload=BytesIO();im.save(payload,format="JPEG")
    sizes=[]
    async def model(source,images,prompt):
        if "CZĘŚĆ" not in source:
            raise AIProviderError("Truncated",code="MODEL_OUTPUT_TRUNCATED")
        with Image.open(BytesIO(images[0][1])) as crop:
            sizes.append(crop.size)
        return {"title":"Dokument","pages":[{"title":"Dane",
               "sections":[{"title":"Sekcja","fields":[
               {"label":f"fragment_{len(sizes)}","type":"TEXT_FIELD"}]}]}]},{}
    output,stats=asyncio.run(generate_page_with_recovery(
        "Opis dokumentu",("image/jpeg",payload.getvalue()),
        prompt="VISION",source_text="Opis dokumentu",
        model_generate=model))
    assert sizes==[(800,800),(800,800)]
    assert stats["recovered_fragments"]==2
    assert sum(len(s["fields"]) for p in output["pages"] for s in p["sections"])==2


def test_nontruncation_api_errors_not_hidden_by_recovery():
    async def model(*args,**kwargs):
        raise AIProviderError("Provider 401",code="PROVIDER_HTTP_ERROR")
    with pytest.raises(AIProviderError) as err:
        asyncio.run(generate_page_with_recovery(
            "Dane",None,prompt="SOURCE",model_generate=model))
    assert err.value.code=="PROVIDER_HTTP_ERROR"


def test_xlsx_sparse_reader_preserves_all_ordinary_cell_labels_and_positions():
    from openpyxl import Workbook
    w=Workbook(); ws=w.active;ws.title="Rejestr sprzętu"
    ws["A1"]="Wniosek o rejestrację"
    for i in range(2,62):
        ws[f"A{i}"]=f"Nazwa pozycji {i}"
        ws[f"AE{i}"]=f"Wartość {i}"
        # A lot of blank/formatted cells should not become Markdown filler.
        ws[f"Z{i}"].border=__import__("openpyxl").styles.Border(
            bottom=__import__("openpyxl").styles.Side(style="thin"))
    data=BytesIO();w.save(data)
    root=Path(__file__).resolve().parents[2]/"extractor"/"xlsx_sparse.py"
    spec=importlib.util.spec_from_file_location("xlsx_sparse_test",root)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result=module.extract_xlsx(data.getvalue())
    assert result["engine"]=="xlsx-structure-aware"
    assert result["populated_cells"]==121
    assert result["sheet_count"]==1
    assert not result["truncated"]
    assert "[Wiersz 61]" in result["text"]
    assert "AE: Wartość 61" in result["text"]
    assert "A: Nazwa pozycji 61" in result["text"]
    assert len(result["text"])<7000


def test_openrouter_second_attempt_uses_larger_completion_budget(monkeypatch):
    from app import ai_provider
    monkeypatch.setenv("FORMFLOW_AI_PROVIDER","openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY","synthetic-test-key")
    budgets=[]
    class Response:
        status_code=200
        def __init__(self,budget):self.budget=budget
        def json(self):
            if self.budget==6500:
                return {"choices":[{"finish_reason":"length",
                      "message":{"content":'{"pages":['}}],
                      "usage":{"completion_tokens":6500},
                     "id":"gen-retry-test-1"}
            return {"choices":[{"finish_reason":"stop",
                    "message":{"content":'{"title":"Gotowe","pages":[]}'} }],
                   "usage":{"completion_tokens":120},
                   "id":"gen-retry-test-2"}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            budget=kwargs["json"]["max_tokens"];budgets.append(budget)
            return Response(budget)
    monkeypatch.setattr(ai_provider.httpx,"AsyncClient",Client)
    result,_=asyncio.run(ai_provider.generate("Syntetyczna etykieta do formularza rejestracji urządzenia",[]))
    assert result=={"title":"Gotowe","pages":[]}
    assert budgets==[6500,12000]


def test_dense_page_is_prepartitioned_before_reaching_the_hard_limit():
    source="".join(f"[Wiersz {i}] A: Dane {i}\n" for i in range(1,60))
    calls=[]
    async def synthetic_model(text,images,prompt):
        calls.append(text)
        assert "CZĘŚĆ" in text  # no initial oversized request
        labels=re.findall(r"\bA: Dane (\d+)\b",text)
        return {"title":"Formularz","pages":[{"title":"Arkusz","sections":[
            {"title":"Dane","fields":[{"label":str(x),"type":"TEXT_FIELD"}
                                    for x in labels]}]}]},{}
    result,meta=asyncio.run(generate_page_with_recovery(
        source,None,prompt="TASK",source_text=source,force_parts=2,
        model_generate=synthetic_model))
    assert meta["recovered_fragments"]==2
    assert len(calls)==2
    assert sum(len(s["fields"]) for p in result["pages"] for s in p["sections"])==59


def test_timeout_on_whole_page_can_recover_by_chunking():
    async def timed(text,images,prompt):
        if "CZĘŚĆ" not in text:
            raise AIProviderError("Timeout",code="MODEL_TIMEOUT")
        return {"title":"Form","pages":[{"title":"Part","sections":[]}]},{}
    result,meta=asyncio.run(generate_page_with_recovery(
        "Dane testowe "*80,None,prompt="TASK",model_generate=timed))
    assert meta["recovered_fragments"]==2
    assert isinstance(result["pages"],list)


def test_incomplete_llm_table_row_metadata_does_not_reject_regular_field():
    from app.structured_extraction import Page,_sanitize_page
    from app.canonical_form import canonicalize
    proposal={"title":"Dokument","pages":[{"title":"Strona","sections":[
        {"title":"Pytania","fields":[{"label":"Identyfikator",
          "type":"TEXT_FIELD","required":False,"options":[],
          "evidence":"Identyfikator .......","row":1}]}]}]}
    page=Page(1,"Identyfikator .......",None)
    cleaned=_sanitize_page(proposal,page)
    field=cleaned["pages"][0]["sections"][0]["fields"][0]
    assert "row" not in field
    assert "column" not in field
    assert canonicalize(cleaned)["pages"][0]["sections"][0]["fields"][0]==field