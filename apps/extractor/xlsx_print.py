"""Non-destructive XLSX print-width normalization.

Modify ONLY OOXML worksheet print settings in a copy, preserving formulas,
cached values, embedded objects, drawings, relationships and formatting.
Never rewrite an XLSX using a spreadsheet API solely to change print setup.
"""

from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
import re

from lxml import etree

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
SHEET_PATTERN = re.compile(r"^xl/worksheets/sheet[0-9]+[.]xml$")
MAX_UNCOMPRESSED = 160 * 1024 * 1024
MAX_SHEET_XML = 12 * 1024 * 1024

# ECMA-376 worksheet element ordering. pageSetup precedes headerFooter and
# page/column breaks, and follows pageMargins when those elements are present.
AFTER_PAGE_SETUP = frozenset({
    "headerFooter", "rowBreaks", "colBreaks", "customProperties",
    "cellWatches", "ignoredErrors", "smartTags", "drawing",
    "legacyDrawing", "legacyDrawingHF", "picture", "oleObjects",
    "controls", "webPublishItems", "tableParts", "extLst",
})


def _fit_sheet(xml: bytes) -> tuple[bytes, bool]:
    root = etree.fromstring(xml, parser=etree.XMLParser(
        resolve_entities=False, no_network=True, remove_blank_text=False,
        huge_tree=False,
    ))
    if root.tag != f"{{{NS}}}worksheet":
        raise ValueError("Nieprawidłowa struktura arkusza XLSX.")
    original = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    sheet_pr = root.find(f"{{{NS}}}sheetPr")
    if sheet_pr is None:
        sheet_pr = etree.Element(f"{{{NS}}}sheetPr")
        root.insert(0, sheet_pr)
    setup_pr = sheet_pr.find(f"{{{NS}}}pageSetUpPr")
    if setup_pr is None:
        setup_pr = etree.SubElement(sheet_pr, f"{{{NS}}}pageSetUpPr")
    page_setup = root.find(f"{{{NS}}}pageSetup")
    if page_setup is None:
        page_setup = etree.Element(f"{{{NS}}}pageSetup")
        position = len(root)
        for i, element in enumerate(root):
            if etree.QName(element).localname in AFTER_PAGE_SETUP:
                position = i
                break
        root.insert(position, page_setup)
    prior = (
        setup_pr.get("fitToPage"),
        page_setup.get("fitToWidth"),
        page_setup.get("fitToHeight"),
        page_setup.get("scale"),
    )
    if prior == ("1", "1", "0", None):
        return xml, False
    setup_pr.set("fitToPage", "1")
    page_setup.set("fitToWidth", "1")
    page_setup.set("fitToHeight", "0")
    page_setup.attrib.pop("scale", None)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True), True


def fit_xlsx_print_width(data: bytes) -> tuple[bytes, dict]:
    if not data or len(data) > 15 * 1024 * 1024:
        raise ValueError("Nieprawidłowy plik XLSX.")
    try:
        with ZipFile(BytesIO(data)) as source:
            entries = source.infolist()
            if not entries or sum(item.file_size for item in entries) > MAX_UNCOMPRESSED:
                raise ValueError("Przekroczony limit rozpakowanych danych XLSX.")
            if len(entries) > 2000:
                raise ValueError("Zbyt wiele elementów archiwum XLSX.")
            worksheet_names = [
                item.filename for item in entries
                if SHEET_PATTERN.fullmatch(item.filename)
            ]
            if not worksheet_names or len(worksheet_names) > 24:
                raise ValueError("Nieobsługiwana liczba arkuszy XLSX.")
            edited = {}
            for name in worksheet_names:
                item = source.getinfo(name)
                if item.file_size > MAX_SHEET_XML:
                    raise ValueError("Zbyt duży arkusz XLSX.")
                xml, changed = _fit_sheet(source.read(name))
                if changed:
                    edited[name] = xml
            if not edited:
                return data, {"engine": "ooxml-print-width", "changed": False, "worksheets": len(worksheet_names)}
            result = BytesIO()
            with ZipFile(result, "w") as output:
                for item in entries:
                    output.writestr(
                        item, edited.get(item.filename, source.read(item.filename))
                    )
            return result.getvalue(), {
                "engine": "ooxml-print-width",
                "changed": True,
                "worksheets": len(worksheet_names),
                "normalized_sheets": len(edited),
            }
    except (BadZipFile, etree.XMLSyntaxError, KeyError, OverflowError) as exc:
        raise ValueError("Nie można zweryfikować ustawień wydruku XLSX.") from exc
