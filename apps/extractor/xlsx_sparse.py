"""Structure-first XLSX form extraction.

Reads the native workbook layout (merged ranges, heading styles, printed
answer boxes) before any language model call. No labels, municipalities, or
form-specific templates are preconfigured. Regions and field candidates are
sourced from actual workbook cells.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_SHEETS=20
MAX_ROWS=1800
MAX_COLUMNS=128
MAX_CONTENT_CELLS=4000
MAX_OUTPUT_CHARS=150000
MAX_REGIONS=64
NUMBERED_HEADING=re.compile(r"^\s*((?:\d+\.)+)(?:\s+|(?=[A-Za-zĄĆĘŁŃÓŚŹŻ]))(.{3,})$")
PURE_COUNTER=re.compile(r"^\s*\d+[.)]?\s*$")
NOTICE_MARKER=re.compile(r"^[ⓘℹ]")
DATE_FORMAT=re.compile(r"(?i)\b(?:DD[-. /]MM[-. /](?:RRRR|YYYY)|RRRR[-. /]MM[-. /]DD)\b")


class SpreadsheetSourceError(ValueError):
    pass


def _text(value:object)->str:
    if isinstance(value,(date,datetime)):
        return value.isoformat()
    return str(value).replace("\r"," ").replace("\n"," / ").strip()[:400]


def _has_box(cell)->bool:
    border=cell.border
    top=bool(border.top and border.top.style)
    bottom=bool(border.bottom and border.bottom.style)
    left=bool(border.left and border.left.style)
    right=bool(border.right and border.right.style)
    return top and bottom or left and right


def _occupied_merged_ranges(sheet)->dict[int,list[tuple[int,int]]]:
    # A styled, merged display cell may carry borders across a long run.
    # If its top-left contains instructions, the remainder is NOT a blank.
    occupied={}
    for merged in sheet.merged_cells.ranges:
        if sheet.cell(merged.min_row,merged.min_col).value is None:
            continue
        for row in range(merged.min_row,merged.max_row+1):
            occupied.setdefault(row,[]).append((merged.min_col,merged.max_col))
    return occupied


def _printed_spans(sheet,row_num:int,
                   occupied:dict|None=None)->list[tuple[int,int]]:
    """Group neighboring styled empty cells as ONE printed input region.

    A sequence of single digit squares (NIP/date) is not many independent
    questions. Distinct runs separated by captions are kept independent.
    """
    columns=[]
    filled=(occupied or {}).get(row_num,[])
    for col in range(1,min(MAX_COLUMNS,sheet.max_column)+1):
        if any(a<=col<=b for a,b in filled):
            continue
        cell=sheet.cell(row_num,col)
        if cell.value is None and _has_box(cell):
            columns.append(col)
    spans=[]
    if not columns:
        return spans
    first=prev=columns[0]
    for col in columns[1:]:
        if col>prev+1:
            spans.append((first,prev))
            first=col
        prev=col
    spans.append((first,prev))
    return spans


def _heading(row_values:list, sheet)->tuple[str,int|None]|None:
    """Use explicit heading numbering OR native style cues, never a word list."""
    if len(row_values)!=1:
        return None
    cell=row_values[0]
    value=_text(cell.value)
    if len(value)<5:
        return None
    numbered=NUMBERED_HEADING.match(value)
    if numbered:
        return value,len(numbered.group(1).rstrip(".").split("."))
    if cell.font.bold and cell.border.bottom and cell.border.bottom.style:
        # Visually emphasized, standalone, underlined headings.
        return value,None
    return None


def _source_line(sheet,row_num:int,occupied:dict)->tuple[str,list[dict]]:
    row_values=[cell for cell in sheet[row_num]
                if cell.value is not None and _text(cell.value)]
    spans=_printed_spans(sheet,row_num,occupied)
    fragments=[(cell.column,f"{get_column_letter(cell.column)}: {_text(cell.value)}")
               for cell in row_values]
    for lo,hi in spans:
        address=(f"{get_column_letter(lo)}{row_num}:"
                 f"{get_column_letter(hi)}{row_num}")
        fragments.append((lo,
                          f"[DRUKOWANE PUSTE POLE {address}; {hi-lo+1} kom.]"))
    fragments.sort(key=lambda item:item[0])
    output=(f"[Wiersz {row_num}] "+" | ".join(text for _,text in fragments)
            if fragments else "")
    labels=[cell for cell in row_values if
            not PURE_COUNTER.fullmatch(_text(cell.value))
            and not NOTICE_MARKER.match(_text(cell.value))
            and _text(cell.value)!="-"
            and not str(cell.value).startswith("=")]
    anchors=[]
    if spans:
        for cell in labels:
            label=_text(cell.value)
            # A printed label must be close to one of the writable groups;
            # otherwise it is descriptive text, not a response caption.
            closest=min(min(abs(cell.column-lo),abs(cell.column-hi))
                        for lo,hi in spans)
            if closest>22:
                continue
            nearby=[f"{get_column_letter(lo)}{row_num}:"
                    f"{get_column_letter(hi)}{row_num}"
                    for lo,hi in spans
                    if lo>=cell.column and
                    (not any(other.column>cell.column and other.column<lo
                             for other in labels))]
            if not nearby:
                nearby=[f"{get_column_letter(lo)}{row_num}:"
                        f"{get_column_letter(hi)}{row_num}"
                        for lo,hi in spans if hi<cell.column and
                        cell.column-hi<=5]
            if not nearby:
                continue
            box=(len(spans)==1 and spans[0][0]==spans[0][1]
                 and spans[0][1]<cell.column)
            anchors.append({"label":label,"row":row_num,
                            "source":cell.coordinate,"boxes":nearby,
                            "kind_hint":"CHECKBOX" if box else "TEXT_FIELD"})
    return output,anchors


def extract_xlsx(content:bytes)->dict:
    try:
        book=load_workbook(BytesIO(content),read_only=False,
                           data_only=False,keep_links=False)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise SpreadsheetSourceError("Nie udało się odczytać XLSX.") from exc
    lines=[];regions=[];cell_count=0;total_rows=0
    document_title=None
    try:
        if len(book.worksheets)>MAX_SHEETS:
            raise SpreadsheetSourceError("Arkusz zawiera zbyt wiele zakładek.")
        for sheet_index,sheet in enumerate(book.worksheets,1):
            if sheet.max_row>MAX_ROWS or sheet.max_column>MAX_COLUMNS:
                raise SpreadsheetSourceError(
                    "Arkusz ma zbyt duży obszar roboczy do bezpiecznej analizy.")
            lines.append(f"[Arkusz {sheet_index}/{len(book.worksheets)}: {sheet.title}]")
            parent=None;parent_number=None
            current=None
            occupied=_occupied_merged_ranges(sheet)
            for row_num in range(1,sheet.max_row+1):
                values=[c for c in sheet[row_num] if c.value is not None
                        and _text(c.value)]
                cell_count+=len(values)
                if cell_count>MAX_CONTENT_CELLS:
                    raise SpreadsheetSourceError("Zbyt wiele komórek XLSX.")
                if not values and not _printed_spans(sheet,row_num,occupied):
                    continue
                heading=_heading(values,sheet)
                row_line,anchors=_source_line(sheet,row_num,occupied)
                if (not heading and document_title is None and row_num<=5
                    and len(values)==1 and values[0].font.bold
                    and len(_text(values[0].value))>=8):
                    document_title=_text(values[0].value)
                    lines.append(row_line)
                    continue
                if heading and document_title is None and not regions and current is None:
                    if heading[1] is None:
                        document_title=heading[0]
                        lines.append(row_line)
                        continue
                if heading:
                    name,level=heading
                    if current is not None:
                        regions.append(current)
                    if level==1:
                        parent=name
                        parent_number=name.split(".",1)[0]
                    elif level is None:
                        parent=name
                        parent_number=None
                    elif parent_number is None or name.split(".",1)[0]!=parent_number:
                        parent=name
                        parent_number=name.split(".",1)[0]
                    current={"sheet":sheet.title,
                             "group_title":parent or name,
                             "section_title":name,
                             "start_row":row_num,"end_row":row_num,
                             "lines":[],"anchors":[]}
                    lines.append(row_line)
                    continue
                if current is None:
                    # Unnumbered/no-style spreadsheet: still extract its cells.
                    current={"sheet":sheet.title,"group_title":sheet.title,
                             "section_title":sheet.title,
                             "start_row":row_num,"end_row":row_num,
                             "lines":[],"anchors":[]}
                current["lines"].append(row_line)
                current["anchors"].extend(anchors)
                current["end_row"]=row_num
                if row_line:
                    lines.append(row_line)
                    total_rows+=1
            if current is not None:
                regions.append(current)
            lines.append("")
        if not regions and not lines:
            raise SpreadsheetSourceError("XLSX nie zawiera tekstu formularza.")
        if len(regions)>MAX_REGIONS:
            raise SpreadsheetSourceError("Zbyt wiele sekcji XLSX.")
        full="\n".join(lines)
        if len(full)>MAX_OUTPUT_CHARS:
            raise SpreadsheetSourceError("Tekst XLSX przekracza limit.")
        # When styles do not contain any writable box, fall back to source
        # text analysis rather than silently declaring the form empty.
        has_geometry=any(region["anchors"] for region in regions)
        serialized=[]
        for region in regions:
            snippet=("Sekcja źródłowa: "+region["section_title"]+"\n"
                     +"\n".join(region["lines"]))
            if not region["lines"]:
                continue
            # A pre-heading masthead is not an independent form step.
            if (region["section_title"]==region["sheet"]
                and region["group_title"]==region["sheet"]
                and not region["anchors"]
                and has_geometry):
                continue
            box_rows={int(re.search(r"\[Wiersz (\d+)\]",line).group(1))
                for line in region["lines"] if "DRUKOWANE PUSTE POLE" in line
                and re.search(r"\[Wiersz (\d+)\]",line)}
            anchored_rows={a["row"] for a in region["anchors"]}
            extra_lines=[
                line for line in region["lines"]
                if ("DRUKOWANE PUSTE POLE" not in line
                    and "Wiersz" in line)
            ]
            native_confident=bool(
                region["anchors"] and box_rows==anchored_rows
                and not extra_lines
                and all(a["kind_hint"]=="TEXT_FIELD"
                        for a in region["anchors"]))
            serialized.append({
                "sheet":region["sheet"],
                "group_title":region["group_title"],
                "section_title":region["section_title"],
                "start_row":region["start_row"],
                "end_row":region["end_row"],
                "text":snippet[:12000],
                "source_anchors":region["anchors"],
                "native_confident":native_confident,
                "info_only":bool(has_geometry and not region["anchors"]
                                  and not any("DRUKOWANE PUSTE POLE" in l
                                              for l in region["lines"])),
            })
        return {"engine":"xlsx-structure-aware","format":".xlsx",
                "text":full, "document_title":document_title,
                "source_sections":serialized,
                "page_count":0,"tables":len(book.worksheets),
                "sheet_count":len(book.worksheets),
                "populated_cells":cell_count,"populated_rows":total_rows,
                "truncated":False,"layout_fidelity":"native_borders_and_headings",
                "warning":"Kontrolki rozpoznano ze struktury arkusza; sprawdź wynik."}
    finally:
        book.close()