"""Vision/OCR A-B controls and conservative source-evidence reports."""
import asyncio
import base64

import httpx
from app.extraction_router import extract_with_backend
from app.field_grounding import analyze_grounding

def test_pdf_vision_on_overrides_disabled_default(monkeypatch):
    import app.extraction_router as router
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL","http://pdf-engine:8002")
    monkeypatch.setenv("FORMFLOW_PDF_VISION","false")
    calls=[]
    jpeg=b"\xff\xd8\xffexample"
    class Response:
        status_code=200
        def json(self):
            return {"text":"[Strona 1/2]\nPESEL\n[Strona 2/2]\nTelefon",
                    "page_count":2,"engine":"pdf-layout-ocr",
                    "preview_images":[{"page":1,"mime":"image/jpeg",
                                       "base64":base64.b64encode(jpeg).decode()},
                                      {"page":2,"mime":"image/jpeg",
                                       "base64":base64.b64encode(jpeg).decode()}]}
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            calls.append(kwargs)
            return Response()
    monkeypatch.setattr(router.httpx,"AsyncClient",Client)
    text,images,meta=asyncio.run(extract_with_backend(
        b"%PDF-1.7\n", ".pdf",vision_mode="on"))
    assert len(images)==2
    assert meta["vision_pages"]==2
    assert meta["vision_page_numbers"]==[1,2]
    assert meta["vision_incomplete"] is False
    assert calls[0]["params"]=={"previews":"true"}
    _,disabled,info=asyncio.run(extract_with_backend(
        b"%PDF-1.7\n", ".pdf",vision_mode="off"))
    assert disabled==[]
    assert info["vision_enabled"] is False
    assert calls[1]["params"]=={}

def test_incomplete_page_images_are_explicitly_reported(monkeypatch):
    import app.extraction_router as router
    monkeypatch.setenv("FORMFLOW_PDF_WORKER_URL","http://pdf-engine:8002")
    sample=base64.b64encode(b"\xff\xd8\xffimage").decode()
    class Response:
        status_code=200
        def json(self):
            return {"text":"[Strona 1/5]\nNazwisko", "page_count":5,
                    "preview_images":[{"page":n,"mime":"image/jpeg","base64":sample}
                                      for n in (1,2,3)]}
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return Response()
    monkeypatch.setattr(router.httpx,"AsyncClient",Client)
    _,images,meta=asyncio.run(extract_with_backend(
        b"%PDF-1.7\n",".pdf",vision_mode="on"))
    assert len(images)==3
    assert meta["vision_incomplete"] is True
    assert meta["vision_page_numbers"]==[1,2,3]
    assert meta["pages"]==5

def test_ocr_evidence_reports_excerpts_and_respects_page_boundaries():
    form={"pages":[{"sections":[{"fields":[
        {"label":"PESEL","type":"TEXT_FIELD"},
        {"label":"Numer ewidencyjny działki","type":"TEXT_FIELD"},
        {"label":"Województwo","type":"SELECT"},
        {"label":"Klauzula informacyjna","type":"INFO_BLOCK"},
    ]}]}]}
    text="[Strona 1/2]\nWpisz PESEL: ____________\n[Strona 2/2]\nnr ewidencyjny działki .........."
    result=analyze_grounding(text,form,images_count=2)
    assert result["fields_total"]==3
    assert result["ocr_supported"]>=2,result
    assert result["requires_review"]>=1
    pe=result["items"][0]
    assert pe["source_page"]==1 and pe["evidence"]=="ocr_match"
    plot=result["items"][1]
    assert plot["source_page"]==2 and plot["evidence"]=="ocr_match"
    assert result["items"][2]["evidence"]=="requires_visual_review"
    assert result["items"][2]["source_excerpt"] is None

def test_no_ocr_support_does_not_automatically_remove_visual_fields():
    value={"pages":[{"sections":[{"fields":[
        {"label":"Miejscowość","type":"TEXT_FIELD"}
    ]}]}]}
    result=analyze_grounding("z l0kali1owanym ...",value,images_count=1)
    assert result["fields_total"]==1
    assert result["items"][0]["evidence"]=="requires_visual_review"
