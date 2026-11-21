"""Bounded structural extraction for XLSX form templates.

Keeps meaningful populated cells and their positions instead of asking an LLM
to interpret thousands of Markdown table delimiters for empty spreadsheet
cells. No fixed form names or example-specific labels.
"""
from __future__ import annotations

from io import BytesIO
from datetime import date,datetime
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_SHEETS=20
MAX_ROWS=1800
MAX_COLUMNS=128
MAX_CONTENT_CELLS=4000
MAX_OUTPUT_CHARS=150000


class SpreadsheetSourceError(ValueError):
    pass


def extract_xlsx(content:bytes)->dict:
    try:
        book=load_workbook(BytesIO(content),read_only=True,
                           data_only=False,keep_links=False)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise SpreadsheetSourceError("Nie udało się odczytać XLSX.") from exc
    lines=[];cell_count=0;total_rows=0
    try:
        if len(book.worksheets)>MAX_SHEETS:
            raise SpreadsheetSourceError("Arkusz zawiera zbyt wiele zakładek.")
        for sheet_index,sheet in enumerate(book.worksheets,1):
            # Excel templates often use dozens of formatted-but-empty
            # columns; these are not 100 separate text questions.
            if sheet.max_row>MAX_ROWS or sheet.max_column>MAX_COLUMNS:
                raise SpreadsheetSourceError(
                    "Arkusz ma zbyt duży obszar roboczy do bezpiecznej analizy.")
            lines.append(f"[Arkusz {sheet_index}/{len(book.worksheets)}: {sheet.title}]")
            for row_number,row in enumerate(sheet.iter_rows(),1):
                entries=[]
                for cell in row:
                    value=cell.value
                    if value is None or isinstance(value,str) and not value.strip():
                        continue
                    if isinstance(value,(datetime,date)):
                        value=value.isoformat()
                    if isinstance(value,str):
                        value=value.replace("\r"," ").replace("\n"," / ").strip()
                    elif isinstance(value,(int,float,bool)):
                        value=str(value)
                    else:
                        value=str(value)
                    entries.append(f"{get_column_letter(cell.column)}: {value[:400]}")
                    cell_count+=1
                    if cell_count>MAX_CONTENT_CELLS:
                        raise SpreadsheetSourceError(
                            "Zbyt wiele wypełnionych komórek XLSX do konwersji formularza.")
                if entries:
                    lines.append(f"[Wiersz {row_number}] "+" | ".join(entries))
                    total_rows+=1
            lines.append("")
        text="\n".join(lines)
        if not text.strip() or cell_count==0:
            raise SpreadsheetSourceError("XLSX nie zawiera tekstu formularza.")
        if len(text)>MAX_OUTPUT_CHARS:
            raise SpreadsheetSourceError(
                "Tekst XLSX jest zbyt obszerny do bezpiecznej konwersji.")
        return {"engine":"xlsx-sparse-structural","format":".xlsx",
                "text":text,"page_count":0,"tables":len(book.worksheets),
                "sheet_count":len(book.worksheets),
                "populated_cells":cell_count,"populated_rows":total_rows,
                "truncated":False,
                "layout_fidelity":"cell_coordinates",
                "warning":"Puste obszary i komórki graficzne wymagają kontroli wizualnej."}
    finally:
        book.close()