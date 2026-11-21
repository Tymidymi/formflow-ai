"""Vision-based structural table detection, independent of document domain.

The vision model identifies table geometry (number of rows and printed
columns). Deterministic code expands cells; it never guesses which form type
is being processed.
"""
from __future__ import annotations
from difflib import SequenceMatcher
import re
from .layout_slots import GROUP
from .ai_provider import generate
from .field_grounding import norm

PROMPT = """You are a VISUAL TABLE GEOMETRY detector, not a form writer.
Inspect ONE document image and its OCR text. Find every fillable table:
multiple physical rows of aligned blank cells under printed column labels,
including repeated forms divided into groups/categories.

Your ONLY task is COUNTING physical rows and identifying columns.
A unit printed next to a cell (m², kg, cm, %, PLN etc.) is not a
separate column or a separate writable cell. Count only actual blanks.
If a caption is printed below a dotted line, it labels the line above.
Do not generate fields, do not collapse repeated rows.
Do not treat attachment bullet lists, legal notices, address blocks,
or text paragraphs as tables.
Return ONLY JSON:
{"pages":[{"tables":[
 {"group":"short exact printed heading on this page",
  "rows":2,
  "columns":["printed name of column 1","printed name of column 2"],
  "cell_type":"NUMBER|TEXT_FIELD|DATEPICKER",
  "source_quote":"short nearby printed row/heading"}
]}]}
Each distinct physical subgroup is a separate table record.
A physical group containing two aligned rows requires rows:2 even when
both rows have identical printed captions.
If there are no fillable repeated-row tables, return
{"pages":[{"tables":[]}]}.
Avoid inferring tables merely because a paragraph contains several blanks.
Do not invent group names or columns that are not visible.
JSON only."""

async def visually_detect(text:str,image:tuple[str,bytes])->list[dict]:
    raw,_=await generate(text,[image],prompt=PROMPT)
    tables=[]
    for page in raw.get("pages",[]):
        if not isinstance(page,dict):continue
        for table in page.get("tables",[]):
            if not isinstance(table,dict):continue
            try: rows=int(table.get("rows",0))
            except (ValueError,TypeError):continue
            cols=[str(x).strip() for x in table.get("columns",[])
                  if isinstance(x,str) and x.strip()]
            # Standalone measurement units are NOT blank input columns.
            cols=[x for x in cols if norm(x) not in
                  {"m2","m","mm","cm","km","kg","g","ha","zl","pln","%","szt"}]
            group=str(table.get("group","")).strip()
            if not group or not 2<=rows<=25 or not 2<=len(cols)<=6:continue
            kind=table.get("cell_type")
            if kind not in ("NUMBER","TEXT_FIELD","DATEPICKER"):
                kind="TEXT_FIELD"
            tables.append({"group":group[:140],"rows":rows,
                           "columns":cols,
                           "type":kind,"evidence":str(table.get("source_quote") or "")[:200]})
    return tables[:25]

def expand(tables:list[dict],source_page:int)->list[dict]:
    fields=[]
    for table in tables:
        for row in range(1,table["rows"]+1):
            for column in table["columns"]:
                fields.append({
                    "label":f"{table['group']} — wiersz {row} — {column}"[:220],
                    "type":table["type"],"required":False,"options":[],
                    "evidence":table["evidence"] or "image-only",
                    "row":row,"column":column,
                    "source_page":source_page,"source":"visual_table_geometry"})
    return fields

def likely_table_duplicate(field:dict,tables:list[dict])->bool:
    label=norm(str(field.get("label") or ""))
    for table in tables:
        # Generic repeated column headings emitted as independent controls
        # by an LLM are duplicates when the measured table geometry is known.
        columns={norm(x) for x in table["columns"] if len(norm(x))>=4}
        if label.strip() in columns:
            return True
        group=norm(table["group"])
        # Do not match a single generic token like "data"; require printed
        # group context plus a column name. This avoids deleting other inputs.
        if len(group)<7 or not (group in label or label in group):
            continue
        if any(norm(col) in label for col in table["columns"]
               if len(norm(col))>=4):
            return True
    return False


def recover_groups_from_ocr(source:str,tables:list[dict])->list[dict]:
    """Use OCR line *geometry* to count repeated rows under source headings.

    No known field vocabulary: column labels come from vision. Fuzzy token
    alignment handles damaged scanned OCR, while group boundaries come
    from page layout. Fallback to vision geometry if OCR is insufficient.
    """
    if not tables:return []
    lines=source.splitlines()
    headings=[]
    for i,line in enumerate(lines):
        match=GROUP.match(line)
        if match:
            mark=line.strip().split(maxsplit=1)[0].rstrip(")/.")
            headings.append((i,match.group(1).strip(),mark))
    # Prefer repeated alphabetical or numbered subgroups, not a single
    # overall "1. Wniosek" heading above them.
    letters=[(i,title) for i,title,mark in headings
             if len(mark)==1 and mark.isalpha()]
    numbers=[(i,title) for i,title,mark in headings
             if mark.isdecimal()]
    groups=letters if len(letters)>=2 else numbers if len(numbers)>=2 else []
    def matches_column(line:str,columns:list[str])->int:
        tokens=[norm(w) for w in re.findall(r"[\wąćęłńóśźż]+",line.lower())]
        scored=0
        for column in columns:
            term=norm(column)
            if len(term)<4:continue
            if max((SequenceMatcher(None,term,t).ratio()
                    for t in tokens if len(t)>=3),default=0)>=0.64:
                scored+=1
        return scored
    # A column schema from the visual model applies to source-aligned groups.
    # Only expand when at least two physical source groups can be verified.
    schema=max(tables,key=lambda t:len(t["columns"]))
    # Independent source verification: a checklist, a paragraph or a series
    # of bullet-pointed attachments is NOT a fillable multi-column table.
    # A VLM claim without at least two OCR lines containing two of its
    # purported column headings must not generate dozens of fake cells.
    table_row_evidence=sum(matches_column(line,schema["columns"])>=2
                           for line in lines)
    if table_row_evidence<2:
        return []
    if len(groups)<2:
        return tables
    derived=[]
    for index,(start,title) in enumerate(groups):
        end=groups[index+1][0] if index+1<len(groups) else len(lines)
        count=0
        for text in lines[start+1:end]:
            if len(text.strip())<18:continue
            if matches_column(text,schema["columns"])>=1:
                count+=1
            elif count>0:
                # A different substantive paragraph ends this particular
                # repeated-row group even if OCR missed the next heading.
                break
        if count>=1:
            derived.append({"group":title[:140],"rows":count,
                            "columns":schema["columns"],
                            "type":schema["type"],
                            "evidence":title[:180]})
    # Reject unreliable decomposition rather than inventing categories.
    if len(derived)>=2 and sum(x["rows"] for x in derived)>=len(derived)*2:
        return derived
    return tables
