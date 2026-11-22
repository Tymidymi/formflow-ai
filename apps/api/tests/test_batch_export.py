"""Batch packaging never converts or exports structurally invalid forms."""
from io import BytesIO
import json
from zipfile import ZipFile

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_batch_exports_only_valid_coi_and_sanitizes_names():
    demo = client.get("/api/v1/demo/convert").json()["form"]
    result = client.post("/api/v1/forms/batch/export", json={"forms": [
        {"filename": "../formularz-test.pdf", "form": demo},
        {"filename": "../formularz-test.pdf", "form": demo},
    ]})
    assert result.status_code == 200
    assert result.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(result.content)) as archive:
        names = archive.namelist()
        assert names == ["formularz-test.json", "formularz-test-2.json"]
        assert all(not x.startswith("/") and ".." not in x for x in names)
        assert json.loads(archive.read(names[0])) == demo


def test_batch_rejects_invalid_forms_and_excessive_count():
    demo = client.get("/api/v1/demo/convert").json()["form"]
    assert client.post("/api/v1/forms/batch/export", json={"forms": [
        {"filename": "bad.pdf", "form": {"title": "bad"}}
    ]}).status_code == 422
    assert client.post("/api/v1/forms/batch/export", json={"forms": []}).status_code == 422
    assert client.post("/api/v1/forms/batch/export", json={"forms": [
        {"filename": str(i), "form": demo} for i in range(6)
    ]}).status_code == 422
    assert client.post("/api/v1/forms/batch/export", data="not json").status_code == 400
