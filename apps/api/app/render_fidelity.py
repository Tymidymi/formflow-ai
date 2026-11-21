"""Detect text painted entirely outside physical PDF page boundaries.

PDF text extraction can report off-page characters as ordinary words even
when rendering clips them. Compare source structure with actual visible PDF,
not only the PDF's plain-text layer.
"""

from io import BytesIO
import math

import pypdfium2 as pdfium

MAX_PAGES = 24
MAX_GLYPHS = 180_000
MIN_OFF_PAGE_GLYPHS = 20
MAX_OFF_PAGE_RATIO = 0.03


def check_visible_text(pdf_bytes: bytes) -> dict:
    inspected = 0
    outside = 0
    pages = []
    try:
        document = pdfium.PdfDocument(pdf_bytes)
        if len(document) > MAX_PAGES:
            raise ValueError("Dokument przekracza limit stron PDF.")
        for idx in range(len(document)):
            page = document[idx]
            width, height = page.get_size()
            text = page.get_textpage()
            count = text.count_chars()
            if inspected + count > MAX_GLYPHS:
                raise ValueError("PDF przekracza limit sprawdzania znaków.")
            page_outside = 0
            checked = 0
            for i in range(count):
                box = text.get_charbox(i, loose=True)
                if len(box) != 4 or not all(math.isfinite(x) for x in box):
                    continue
                x0, y0, x1, y1 = box
                if x1 <= x0 or y1 <= y0:
                    continue
                checked += 1
                if (
                    x1 <= -1 or x0 >= width + 1
                    or y1 <= -1 or y0 >= height + 1
                ):
                    page_outside += 1
            inspected += checked
            outside += page_outside
            pages.append({"page": idx + 1, "text_glyphs": checked, "off_page_glyphs": page_outside})
            text.close()
            page.close()
        document.close()
    except (OSError, RuntimeError, TypeError, IndexError) as exc:
        raise ValueError("Nie można zweryfikować widocznych znaków PDF.") from exc
    ratio = outside / inspected if inspected else 0.0
    return {
        "engine": "pdfium-page-box",
        "visible_text_glyphs": inspected - outside,
        "off_page_glyphs": outside,
        "off_page_fraction": round(ratio, 4),
        "material_clipping": outside >= MIN_OFF_PAGE_GLYPHS and ratio >= MAX_OFF_PAGE_RATIO,
        "pages": pages,
    }
