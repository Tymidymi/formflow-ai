"""Clipped vector text must not be mistaken for visible source evidence."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.render_fidelity import check_visible_text


def make_pdf(*, x):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): ref}),
    })
    stream = DecodedStreamObject()
    content = "Application field" if x < 200 else (
        "Application must preserve every printed label on the form"
    )
    stream.set_data(f"BT /F1 11 Tf {x} 90 Td ({content}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_visible_vector_text_is_not_rejected():
    info = check_visible_text(make_pdf(x=4))
    assert info["material_clipping"] is False
    assert info["off_page_glyphs"] == 0


def test_entirely_off_page_pdf_text_is_detected():
    info = check_visible_text(make_pdf(x=400))
    assert info["material_clipping"] is True
    assert info["off_page_glyphs"] >= 20
    assert info["off_page_fraction"] > 0.9


def test_empty_pdf_is_not_automatically_wrong():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)
    info = check_visible_text(stream.getvalue())
    assert info["off_page_glyphs"] == 0
    assert not info["material_clipping"]
