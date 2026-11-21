import io
from zipfile import ZipFile

import pytest

from app.uploads import RejectedFile, detect_mime, validate_filename


def test_filename_rejects_forbidden_chars():
    for name in ["x;bad.pdf", "x%bad.pdf", "x|bad.pdf", "../x.pdf", "x:bad.pdf", "x'bad.pdf"]:
        with pytest.raises(RejectedFile):
            validate_filename(name)


def test_filename_rejects_long_and_unsupported():
    with pytest.raises(RejectedFile):
        validate_filename("a" * 251 + ".pdf")
    with pytest.raises(RejectedFile):
        validate_filename("invoice.exe")


def test_detect_pdf_and_png():
    assert detect_mime(b"%PDF-1.7\n", ".pdf") == "application/pdf"
    assert detect_mime(b"\x89PNG\r\n\x1a\n...", ".png") == "image/png"


def test_mismatched_extension_is_rejected():
    with pytest.raises(RejectedFile):
        detect_mime(b"%PDF-1.7", ".png")


def test_docx_ooxml_structure():
    output = io.BytesIO()
    with ZipFile(output, "w") as zip_file:
        zip_file.writestr("[Content_Types].xml", "<Types/>")
        zip_file.writestr("word/document.xml", "<document/>")
    assert detect_mime(output.getvalue(), ".docx").endswith("wordprocessingml.document")
