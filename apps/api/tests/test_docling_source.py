"""Regression tests for Docling source cells and non-destructive print settings."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import importlib.util

from openpyxl import Workbook

from app.page_inventory import visible_office_cells

module = Path(__file__).resolve().parents[2] / "extractor" / "xlsx_print.py"
spec = importlib.util.spec_from_file_location("formflow_xlsx_print", module)
xlsx_print = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xlsx_print)


def workbook_bytes():
    book = Workbook()
    sheet = book.active
    sheet["A1"] = "Imię i nazwisko"
    sheet["H1"] = "Urząd Miejski"
    sheet["A2"] = 100
    sheet["B2"] = "=A2*2"
    sheet.merge_cells("A3:H3")
    sheet["A3"] = "Wniosek o wydanie zaświadczenia"
    handle = BytesIO()
    book.save(handle)
    return handle.getvalue()


def test_xlsx_fit_modifies_only_print_settings_and_preserves_formula():
    source = workbook_bytes()
    updated, report = xlsx_print.fit_xlsx_print_width(source)
    assert report["changed"] is True
    assert report["worksheets"] == 1
    with ZipFile(BytesIO(source)) as original, ZipFile(BytesIO(updated)) as normalized:
        assert original.namelist() == normalized.namelist()
        assert [
            name for name in original.namelist()
            if original.read(name) != normalized.read(name)
        ] == ["xl/worksheets/sheet1.xml"]
        page = normalized.read("xl/worksheets/sheet1.xml")
        assert b'fitToPage="1"' in page
        assert b'fitToWidth="1"' in page
        assert b'fitToHeight="0"' in page
        assert b"<f>A2*2</f>" in page
    second, again = xlsx_print.fit_xlsx_print_width(updated)
    assert again["changed"] is False
    assert second == updated


def test_invalid_xlsx_rejected_before_rendering():
    try:
        xlsx_print.fit_xlsx_print_width(b"not a ZIP")
    except ValueError:
        pass
    else:
        raise AssertionError("corrupt XLSX should be rejected")


def test_office_hints_only_include_cells_seen_on_same_page():
    structure = {
        "status": "ok",
        "tables": [
            {
                "table_index": 1,
                "cells": [
                    {"text": "Imię i nazwisko", "row": 2, "column": 1,
                     "row_span": 1, "column_span": 2},
                    {"text": "Dane innego wnioskodawcy", "row": 5, "column": 1,
                     "row_span": 1, "column_span": 1},
                ],
            }
        ],
    }
    value = visible_office_cells(structure, "Imię i nazwisko wnioskodawcy")
    assert "Imię i nazwisko" in value
    assert "Dane innego" not in value
    assert "r2 c1 span=1x2" in value


def test_ods_fit_changes_only_page_layout_not_source_data():
    import io
    from zipfile import ZIP_DEFLATED

    helper = module.with_name("ods_print.py")
    ods_spec = importlib.util.spec_from_file_location("formflow_ods_print", helper)
    ods = importlib.util.module_from_spec(ods_spec)
    ods_spec.loader.exec_module(ods)

    styles = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<office:document-styles '
        b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        b'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0">'
        b'<style:page-layout-properties style:scale-to="100%"/>'
        b'</office:document-styles>'
    )
    raw = io.BytesIO()
    with ZipFile(raw, "w", compression=ZIP_DEFLATED) as original:
        original.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        original.writestr("styles.xml", styles)
        original.writestr("content.xml", "<protected-content>do not change me</protected-content>")
    before = raw.getvalue()
    after, report = ods.fit_ods_print_width(before)
    assert report["changed"] is True
    with ZipFile(BytesIO(before)) as source, ZipFile(BytesIO(after)) as fitted:
        assert fitted.read("content.xml") == source.read("content.xml")
        assert fitted.read("mimetype") == source.read("mimetype")
        assert b'scale-to-X="1"' in fitted.read("styles.xml")
        assert b'scale-to="100%"' not in fitted.read("styles.xml")
    assert ods.fit_ods_print_width(after)[1]["changed"] is False
