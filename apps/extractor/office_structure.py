"""Docling Slim Office parser. Returns source cells, never lossy Markdown tables.

Runs as a bounded subprocess inside the existing isolated Office worker.
The source document remains authoritative; this JSON is evidence, not a
substitute for the original page image.
"""

import json
from pathlib import Path
import sys

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

FORMATS = {
    ".doc": InputFormat.DOC,
    ".docx": InputFormat.DOCX,
    ".xlsx": InputFormat.XLSX,
    ".ods": InputFormat.ODS,
}
MAX_TEXT_CHARS = 28_000
MAX_CELLS = 5_000
MAX_TABLES = 120


def extract(path: Path) -> dict:
    fmt = FORMATS[path.suffix.lower()]
    converter = DocumentConverter(allowed_formats=[fmt])
    result = converter.convert(path)
    doc = result.document
    texts = []
    tables = []
    remaining = MAX_TEXT_CHARS
    remaining_cells = MAX_CELLS
    truncated = False

    def add_text(value: str, limit: int = 700):
        nonlocal remaining, truncated
        value = str(value or "").strip()
        if not value:
            return ""
        if len(value) > limit or len(value) > remaining:
            truncated = True
            return ""
        remaining -= len(value)
        return value

    for item in doc.texts:
        value = add_text(getattr(item, "text", ""), 1200)
        if value:
            texts.append(value)
    for index, table in enumerate(doc.tables):
        if index >= MAX_TABLES:
            truncated = True
            break
        data = table.data
        cells = []
        for cell in data.table_cells:
            if remaining_cells <= 0:
                truncated = True
                break
            remaining_cells -= 1
            value = add_text(getattr(cell, "text", ""), 1000)
            if not value:
                continue
            cells.append({
                "row": cell.start_row_offset_idx + 1,
                "column": cell.start_col_offset_idx + 1,
                "row_span": cell.row_span,
                "column_span": cell.col_span,
                "text": value,
            })
        if cells:
            tables.append({
                "table_index": index + 1,
                "rows": data.num_rows,
                "columns": data.num_cols,
                "cells": cells,
            })
    # Cell items are unique source cells, not repeated grid slots. Markdown
    # export flattens spans and can multiply text thousands of times.
    plain_parts = texts + [
        cell["text"]
        for table in tables
        for cell in table["cells"]
    ]
    return {
        "engine": "docling-slim",
        "status": "ok" if not truncated else "truncated",
        "source_pages": len(doc.pages),
        "texts": texts,
        "tables": tables,
        "plain_text": "\n".join(plain_parts),
        "truncated": truncated,
        "cell_count": sum(len(table["cells"]) for table in tables),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(extract(Path(sys.argv[1])), ensure_ascii=False, separators=(",", ":")))
    except Exception as exc:
        print(json.dumps({"engine": "docling-slim", "status": "error", "error": type(exc).__name__}))
        sys.exit(1)
