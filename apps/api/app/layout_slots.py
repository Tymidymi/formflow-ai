"""General-purpose OCR slot geometry and repeated-row table extraction.

Uses punctuation placeholders, textual column headers and source-order group
headings, never names of government forms or fixed administrative field labels.
"""
from __future__ import annotations
from collections import defaultdict, Counter
import re

BLANK = re.compile(r"(?:\.{5,}|…{3,}|_{4,}|﹏{3,})")
GROUP = re.compile(r"^\s*(?:(?:[a-z]|[0-9]+)[/).]\s+)([\w\s.,()/<>%²\-]{3,100})$",re.I)
NUMERIC_UNITS = re.compile(r"(?:\b(?:m²|m2|km|kg|cm|mm|szt\.?|zł|pln|%|ha)\b)",re.I)

def _label_between(s:str)->str:
    value=re.sub(r"^\s*[-–—;/,.:]+|[-–—;/,.:]+\s*$","",s.strip())
    value=" ".join(value.split()).strip()
    return value[-55:] or "Wartość"

def extract_multislot_rows(source:str) -> tuple[list[dict],list[dict]]:
    """Return deterministic fields plus line numbers for source traceability.

    A line with at least two clearly delimited blanks separated by printed
    text is treated as multiple independently fillable cells. Every slot
    keeps its printed column caption; no semantic assumptions are required.
    """
    lines=source.splitlines()
    # A single line with two dotted blanks can be a date range, not a table.
    # Recognize repeated row structures by their printed column captions.
    # This works for arbitrary columns, without knowing any domain vocabulary.
    def row_signature(line:str):
        matches=list(BLANK.finditer(line))
        if len(matches)<2:return ()
        segments=[line[:matches[0].start()]]
        segments.extend(line[a.end():b.start()]
                        for a,b in zip(matches,matches[1:]))
        return tuple(re.sub(r"\s+"," ",re.sub(r"[^\w]+"," ",x,
                                            flags=re.UNICODE)).strip().lower()
                     for x in segments)
    repeated=Counter(row_signature(line) for line in lines)
    result=[];regions=[];group="Pola tabeli";row_numbers=defaultdict(int)
    for lineno,line in enumerate(lines,1):
        heading=GROUP.match(line)
        if heading and not BLANK.search(line):
            group=heading.group(1).strip(" .")
        matches=list(BLANK.finditer(line))
        if len(matches)<2 or repeated[row_signature(line)]<2:
            continue
        between=[line[a.end():b.start()].strip()
                 for a,b in zip(matches,matches[1:])]
        # Multiple adjacent dotted runs separated only by whitespace are
        # ambiguous; visual model will handle those instead.
        if any(not re.search(r"[^\W\d_]",segment,re.UNICODE)
               for segment in between):
            continue
        row_numbers[group]+=1
        row_index=row_numbers[group]
        fields=[]
        start=0
        for col,match in enumerate(matches,1):
            raw=_label_between(line[start:match.start()])
            # First cell may be prefixed by a group/row number; retaining a
            # short source label is preferable to inventing a column name.
            if not raw:raw=f"Kolumna {col}"
            source_label=f"{group} — wiersz {row_index} — {raw}"
            kind="NUMBER" if NUMERIC_UNITS.search(line) else "TEXT_FIELD"
            fields.append({
                "label":source_label[:220],
                "type":kind,"required":False,"options":[],
                "evidence":line.strip()[:260],
                "source_line":lineno,"row":row_index,"column":raw,
                "source":"printed_blank_cell",
            })
            start=match.end()
        result.extend(fields)
        regions.append({"line":lineno,"columns":len(fields),
                        "group":group,"row":row_index})
    return result,regions

def grouped_fields(fields:list[dict]) -> list[dict]:
    grouped=defaultdict(list)
    for field in fields:
        group=field["label"].split(" — wiersz ",1)[0]
        grouped[group].append(field)
    return [{"title":name,"fields":items} for name,items in grouped.items()]
