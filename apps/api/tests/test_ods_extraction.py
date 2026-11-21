"""ODS extraction: real ODF ZIP shape, bounded rows and text."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi.testclient import TestClient
from app.main import app
from app.document_text import extract_document

ODF_MIME=b"application/vnd.oasis.opendocument.spreadsheet"
CONTENT='''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
<office:body><office:spreadsheet><table:table table:name="Formularz COI">
<table:table-row>
<table:table-cell><text:p>Imię</text:p></table:table-cell>
<table:table-cell><text:p>Nazwisko</text:p></table:table-cell>
</table:table-row>
<table:table-row><table:table-cell><text:p>PESEL</text:p></table:table-cell></table:table-row>
</table:table></office:spreadsheet></office:body>
</office:document-content>'''.encode('utf-8')

def fake_ods():
    stream=BytesIO()
    with ZipFile(stream,"w",ZIP_DEFLATED) as z:
        z.writestr("mimetype",ODF_MIME)
        z.writestr("content.xml",CONTENT)
    return stream.getvalue()

def test_ods_text_extraction():
    txt,images=extract_document(fake_ods(),".ods")
    assert "Arkusz: Formularz COI" in txt
    assert "Imię | Nazwisko" in txt
    assert "PESEL" in txt
    assert images==[]

def test_ods_upload_inspection():
    r=TestClient(app).post("/api/v1/forms/inspect",files={
        "file":("example.ods",fake_ods(),"application/vnd.oasis.opendocument.spreadsheet")})
    assert r.status_code==200,r.text

def test_ods_rejects_external_entities():
    bad=CONTENT.replace(b"<office:document-content",b"<!DOCTYPE foo [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><office:document-content",1)
    stream=BytesIO()
    with ZipFile(stream,"w",ZIP_DEFLATED) as z:
        z.writestr("mimetype",ODF_MIME)
        z.writestr("content.xml",bad)
    from app.uploads import RejectedFile
    import pytest
    with pytest.raises(RejectedFile):
        extract_document(stream.getvalue(),".ods")
