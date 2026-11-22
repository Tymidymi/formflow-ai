"""Preserve ODS source content while normalizing Calc print scaling.

Only styles.xml page-layout print-width attributes are changed. Content,
formulas, drawings, and other ZIP members remain byte-for-byte intact.
"""

from io import BytesIO
from zipfile import ZipFile, BadZipFile

from lxml import etree

ODF_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
MAX_UNCOMPRESSED = 160 * 1024 * 1024
MAX_STYLES_XML = 12 * 1024 * 1024


def fit_ods_print_width(data: bytes) -> tuple[bytes, dict]:
    if not data or len(data) > 15 * 1024 * 1024:
        raise ValueError("Nieprawidłowy dokument ODS.")
    try:
        with ZipFile(BytesIO(data)) as source:
            entries = source.infolist()
            if (
                not entries
                or len(entries) > 2000
                or sum(item.file_size for item in entries) > MAX_UNCOMPRESSED
            ):
                raise ValueError("ODS przekracza limit rozpakowanych danych.")
            entry = source.getinfo("styles.xml")
            if entry.file_size > MAX_STYLES_XML:
                raise ValueError("Zbyt duża definicja stylów ODS.")
            original = source.read(entry)
            tree = etree.fromstring(
                original,
                parser=etree.XMLParser(
                    resolve_entities=False, no_network=True,
                    remove_blank_text=False, huge_tree=False,
                ),
            )
            layouts = tree.xpath(
                '//*[local-name()="page-layout-properties" '
                'and namespace-uri()="urn:oasis:names:tc:opendocument:xmlns:style:1.0"]'
            )
            if not layouts:
                # Nothing to adjust; renderer still produces an exact
                # source-based PDF and API fidelity checks apply.
                return data, {"engine": "odf-print-width", "changed": False, "page_layouts": 0}
            modified = 0
            scale = f"{{{ODF_STYLE}}}scale-to"
            scale_x = f"{{{ODF_STYLE}}}scale-to-X"
            for item in layouts:
                if item.get(scale_x) == "1" and scale not in item.attrib:
                    continue
                item.attrib.pop(scale, None)
                item.set(scale_x, "1")
                modified += 1
            if not modified:
                return data, {"engine": "odf-print-width", "changed": False, "page_layouts": len(layouts)}
            edited = etree.tostring(tree, encoding="UTF-8", xml_declaration=True)
            result = BytesIO()
            with ZipFile(result, "w") as output:
                for item in entries:
                    output.writestr(
                        item, edited if item.filename == "styles.xml"
                        else source.read(item.filename),
                    )
            return result.getvalue(), {
                "engine": "odf-print-width",
                "changed": True,
                "page_layouts": len(layouts),
                "normalized_layouts": modified,
            }
    except (BadZipFile, etree.XMLSyntaxError, KeyError, OverflowError) as exc:
        raise ValueError("Nie można zweryfikować ustawień wydruku ODS.") from exc
