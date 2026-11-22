"""The DOCX renderer must not silently drop a substantial part of its source."""

from io import BytesIO
from zipfile import ZipFile
import pytest

from app.source_fidelity import assess_docx_render, mirrored_source_pages


def docx(paragraphs):
    body = "".join(
        "<w:p><w:r><w:t>" + text + "</w:t></w:r></w:p>" for text in paragraphs
    )
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>' + body + "</w:body></w:document>"
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def paragraphs():
    return [
        f"Position {i} in the document describes a different fictional item number {i}."
        for i in range(12)
    ]


def test_complete_render_accepted():
    lines = paragraphs()
    result = assess_docx_render(docx(lines), "\n".join(lines))
    assert result.complete_enough
    assert result.recall == 1


def test_lost_content_detected_before_model_call():
    lines = paragraphs()
    result = assess_docx_render(docx(lines), "\n".join(lines[:3]))
    assert not result.complete_enough
    assert result.source_windows >= 40
    assert result.recall < 0.45


def test_short_or_scanned_docx_not_confidently_called_lossy():
    result = assess_docx_render(docx(["A simple label"]), "OCR text")
    assert result.complete_enough
    assert result.source_windows == 0


def test_malformed_docx_fails_explicitly():
    with pytest.raises(ValueError, match="źródłowego DOCX"):
        assess_docx_render(b"bad", "")


def test_nearly_identical_printed_sheets_need_fidelity_review():
    common = "Fill in applicant and equipment details. " * 25
    assert mirrored_source_pages(
        "[Strona 1/2]\n" + common + "Declaration text.\n" + "[Strona 2/2]\n" + common
    ) == [(1, 2)]


def test_different_pages_do_not_trigger_mirrored_guard():
    a = "Equipment code and registration number. " * 25
    b = "Terms of service and privacy notice. " * 25
    assert mirrored_source_pages("[Strona 1/2]\n" + a + "[Strona 2/2]\n" + b) == []
