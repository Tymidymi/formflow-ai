"""Universal legacy Word path: strict OLE signature, isolated extraction and fail-closed routing."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import app.extraction_router as router
from app.uploads import RejectedFile, detect_mime

OLE=bytes.fromhex("d0cf11e0a1b11ae1")
MODULE=Path(__file__).resolve().parents[2]/"extractor"/"legacy_doc.py"
spec=importlib.util.spec_from_file_location("formflow_legacy_doc",MODULE)
legacy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def test_doc_magic_and_reject_wrong_format():
    assert detect_mime(OLE+b"test", ".doc")=="application/msword"
    with pytest.raises(RejectedFile):
        detect_mime(b"%PDF-1.7", ".doc")
    with pytest.raises(legacy.LegacyDocError):
        legacy.extract_doc(b"Not an OLE2 file")


def test_legacy_doc_executes_only_fixed_argv_and_deletes_temp(monkeypatch):
    captured={}
    def fake_run(args,**kwargs):
        assert args[:4]==["antiword","-w","0","-m"]
        assert args[4]=="UTF-8.txt"
        docpath=Path(args[5])
        assert docpath.exists()
        assert docpath.name=="input.doc"
        assert docpath.stat().st_mode & 0o777 == 0o600
        assert docpath.read_bytes()==OLE+b"safe bytes"
        assert kwargs["shell"] is False
        assert kwargs["timeout"] <= 20
        captured["path"]=docpath
        return SimpleNamespace(returncode=0,stdout="Tytuł\nPole ............\n".encode())
    monkeypatch.setattr(legacy.subprocess,"run",fake_run)
    text=legacy.extract_doc(OLE+b"safe bytes")
    assert "Pole" in text
    assert not captured["path"].exists()


def test_invalid_or_huge_antiword_response_is_rejected(monkeypatch):
    monkeypatch.setattr(legacy.subprocess,"run",lambda *a,**kw:SimpleNamespace(
        returncode=0,stdout=b""))
    with pytest.raises(legacy.LegacyDocError):
        legacy.extract_doc(OLE+b"safe")
    monkeypatch.setattr(legacy.subprocess,"run",lambda *a,**kw:SimpleNamespace(
        returncode=1,stdout=b"garbage"))
    with pytest.raises(legacy.LegacyDocError):
        legacy.extract_doc(OLE+b"safe")


def test_doc_route_requires_worker(monkeypatch):
    monkeypatch.delenv("FORMFLOW_DOCLING_URL",raising=False)
    with pytest.raises(RejectedFile) as err:
        asyncio.run(router.extract_with_backend(OLE+b"x", ".doc"))
    assert err.value.status==503


def test_doc_worker_used_with_candid_quality_metadata(monkeypatch):
    monkeypatch.setenv("FORMFLOW_DOCLING_URL",router.DOCLING_URL)
    async def fake_request(url,extension,content,**kwargs):
        assert url==router.DOCLING_URL
        assert extension==".doc" and content.startswith(OLE)
        return {"text":"Imię ................\nMiejscowość ................",
                "engine":"antiword-legacy-doc","layout_fidelity":"text_only",
                "page_count":0,"tables":0}
    monkeypatch.setattr(router,"_request",fake_request)
    text,images,metadata=asyncio.run(router.extract_with_backend(OLE+b"x",".doc"))
    assert "Imię" in text and not images
    assert metadata["engine"]=="antiword-legacy-doc"
    assert metadata["legacy_doc_review_required"] is True
    assert metadata["layout_fidelity"]=="text_only"


def test_legacy_doc_worker_connection_error_is_not_masked_as_success(monkeypatch):
    monkeypatch.setenv("FORMFLOW_DOCLING_URL",router.DOCLING_URL)
    async def fake_request(*args,**kwargs):
        raise router.httpx.ConnectError("Worker unavailable")
    monkeypatch.setattr(router,"_request",fake_request)
    with pytest.raises(RejectedFile) as err:
        asyncio.run(router.extract_with_backend(OLE+b"x",".doc"))
    assert err.value.status==503
