"""Reconcile an AI inventory against printed workbook answer boxes.

The anchors are extracted from the *same uploaded workbook*, never from a
registry of known form names or administrative-domain fields. Native section
titles take precedence over any grouping invented by a language model.
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

INPUT={"TEXT_FIELD","TEXTAREA","NUMBER","DATEPICKER",
       "CHECKBOX","RADIO","SELECT","FILE_UPLOADER"}


def _norm(text:object)->str:
    return re.sub(r"[^a-z0-9]+"," ",unicodedata.normalize("NFKD",str(text))
                  .encode("ascii","ignore").decode("ascii").lower()).strip()


def _label_is_heading(label:object,heading:object)->bool:
    # Printed headings often inflect Polish nouns differently from an AI
    # paraphrase. Compare short lexical stems only when at least 3 source
    # tokens exist; never remove a field just because a single word repeats.
    left=[part[:5] if len(part)>=6 else part
          for part in _norm(label).split()]
    right={part[:5] if len(part)>=6 else part
           for part in _norm(heading).split()}
    return (len(left)>=2 and len(''.join(left))>=9
            and len(set(left)&right)/max(1,len(set(left)))>=.80)


def _matched(a:str,b:str)->bool:
    x,y=_norm(a),_norm(b)
    if not x or not y:return False
    if x==y:return True
    # Small editorial differences are not additional physical fields.
    return min(len(x),len(y))>=8 and (x in y or y in x) and (
        min(len(x),len(y))/max(len(x),len(y))>=.78)


def _date(label:str,source:str)->bool:
    # The printed label/format controls the type, not the form's category.
    return bool(re.search(r"(?i)\b(?:data|date|dnia)\b",label)
                or re.search(r"(?i)\bDD[-./ ]MM[-./ ](?:RRRR|YYYY)\b",source))


def _source_line(text:str,row:int)->int|None:
    marker=re.compile(r"^\[Wiersz "+str(row)+r"\]")
    return next((i for i,line in enumerate(text.splitlines(),1)
                 if marker.match(line)),None)


def _choice_clusters(anchors:list[dict])->list[list[dict]]:
    """Only adjacent printed boxes; separate independent distant questions."""
    choices=sorted((a for a in anchors if a.get("kind_hint")=="CHECKBOX"),
                   key=lambda a:a.get("row",0))
    clusters=[];current=[]
    for choice in choices:
        if current and choice.get("row",0)-current[-1].get("row",0)>4:
            if len(current)>=2:clusters.append(current)
            current=[]
        current.append(choice)
    if len(current)>=2:clusters.append(current)
    return clusters


def _unboxed_printed_instruction(field:dict,page,anchors:list[dict])->bool:
    """A marked note is read-only unless its row has a printed answer box.

    The Unicode information icon is source geometry, not a domain keyword.
    Also accept a visually marked instruction line with evidence grounded
    to that exact line. Do not remove adjacent labelled response fields.
    """
    label=_norm(field.get("label",""))
    if len(label)<12 or field.get("source")=="workbook_printed_answer_box":
        return False
    anchored={a.get("row") for a in anchors}
    for line in page.text.splitlines():
        marker=re.match(r"^\[Wiersz (\d+)\]",line)
        if not marker or int(marker.group(1)) in anchored:
            continue
        if not re.search(r"[ⓘℹ]",line) or "DRUKOWANE PUSTE POLE" in line:
            continue
        normalized=_norm(line)
        if label in normalized and len(label)/max(1,len(normalized))>=.50:
            return True
    return False


def _printed_box_rows(text:str)->set[int]:
    return {int(number) for number in re.findall(
        r"(?m)^\[Wiersz (\d+)\][^\n]*DRUKOWANE PUSTE POLE",text)}


def _source_conditions(fields:list[dict],group:dict,cluster:list[dict],
                       page)->None:
    """Bind a printed 'if this option' note to subsequent writable controls.

    The source note must be physically AFTER the last option and BEFORE the
    next printed answer. Do not invent a condition from proximity alone.
    """
    last_row=max(x.get("row",0) for x in cluster)
    next_rows=sorted({x.get("row") for x in page.source_anchors
                      if isinstance(x.get("row"),int)
                      and x["row"]>last_row})
    if not next_rows:
        return
    next_row=next_rows[0]
    notes=[]
    for line in page.text.splitlines():
        marker=re.match(r"^\[Wiersz (\d+)\]",line)
        if not marker or not last_row<int(marker.group(1))<next_row:
            continue
        if re.search(r"(?i)\b(je[sś]li|w przypadku|if|when)\b",line):
            notes.append(line)
    if not notes:return
    ref=group["source_choice_ref"]
    option=cluster[-1]["label"]
    for field in fields:
        row=field.get("source_row")
        line=field.get("source_line")
        if row is None and isinstance(line,int):
            source_line=page.text.splitlines()[line-1]
            parsed=re.match(r"^\[Wiersz (\d+)\]",source_line)
            if parsed:row=int(parsed.group(1))
        if isinstance(row,int) and row>=next_row:
            field.setdefault("show_when",{"field_ref":ref,"value":option})


def enforce_source_region(inventory:dict,page)->tuple[dict,int]:
    """Apply original heading and recover only actual printed source anchors.

    Existing fields can be preserved (e.g. context-dependent choices) while
    duplicates within a source region are removed when a single physical
    answer area was printed. Labels repeating in *different* regions are
    intentionally retained.
    """
    fields=[f for p in inventory.get("pages",[]) if isinstance(p,dict)
            for section in p.get("sections",[]) if isinstance(section,dict)
            for f in section.get("fields",[]) if isinstance(f,dict)
            and f.get("type") in INPUT]
    anchors=list(page.source_anchors)
    for f in fields:
        f["source_page"]=page.number
    recovered=0
    for anchor in anchors:
        label=str(anchor.get("label") or "").strip()
        if not label:continue
        source_line=_source_line(page.text,anchor.get("row",0))
        # One selection control may represent several physical option boxes.
        already=next((f for f in fields
            if _matched(label,f.get("label","")) or (
               f.get("type") in {"CHECKBOX","RADIO","SELECT"} and
               any(_matched(label,v) for v in (f.get("options") or [])))),
            None)
        if already:
            if source_line:
                # Workbook coordinates are authoritative. AI evidence may
                # match an earlier instruction quoting the same caption.
                already["source_line"]=source_line
            # Only a real printed checkbox may override a model's file
            # uploader guess. Paper attachment tick boxes are answers,
            # not standalone upload controls.
            if anchor.get("kind_hint")=="CHECKBOX" and already.get("type")=="FILE_UPLOADER":
                already["type"]="CHECKBOX"
            continue
        # Printed handwritten signatures are not text-entry questions.
        if re.fullmatch(r"(?i)\s*(?:podpis|signature|własnoręczny podpis)\s*",
                        label):
            continue
        kind=anchor.get("kind_hint")
        if kind not in INPUT:kind="TEXT_FIELD"
        # Date format printed elsewhere in the same section must not turn
        # unrelated amount/address fields into date controls.
        local_line=(page.text.splitlines()[source_line-1]
                    if source_line else "")
        if _date(label,local_line):
            kind="DATEPICKER"
        entry={"label":label[:220],"type":kind,"required":False,
               "options":[],"evidence":label[:260],
               "source_page":page.number,
               "source":"workbook_printed_answer_box"}
        if source_line:entry["source_line"]=source_line
        fields.append(entry)
        recovered+=1

    if not anchors and not fields and "DRUKOWANE PUSTE POLE" in page.text:
        # One unlabeled physical answer area immediately below its heading:
        # use that actual source caption, without a known-document dictionary.
        label=str(page.section_title or "").strip()
        if label:
            fields.append({"label":label[:220],
                           "type":"TEXTAREA" if len(page.text.splitlines())<5
                                      else "TEXT_FIELD",
                           "required":False,"options":[],
                           "evidence":label[:260],"source_page":page.number,
                           "source":"workbook_unlabeled_printed_box"})
            recovered+=1

    # Reconcile adjacent printed choice boxes into one source-grounded
    # option group, even when Qwen returned separate checkboxes or file
    # uploaders. No labels come from a prewritten form dictionary.
    clusters=_choice_clusters(anchors)
    choice_parents=[]
    for cluster in clusters:
        labels=[str(a["label"]).strip() for a in cluster]
        selected=[f for f in fields
                  if any(_matched(f.get("label",""),label) for label in labels)]
        parent=next((f for f in fields if
                     f.get("type") in {"CHECKBOX","RADIO","SELECT"} and
                     len(f.get("options") or [])>=2 and
                     sum(any(_matched(option,label) for option in f["options"])
                         for label in labels)>=2),None)
        if parent:
            parent["options"]=labels
        else:
            title=re.sub(r"^\d+(?:\.\d+)*\.\s*","",
                         str(page.section_title or "Wybór"))
            title=title.split(" (",1)[0][:220]
            parent={"label":title,"type":"CHECKBOX","required":False,
                    "options":labels,"evidence":labels[0],
                    "source_page":page.number,
                    "source":"workbook_printed_choice_group"}
            fields.append(parent)
            recovered+=1
        choice_parents.append(parent)
        parent.setdefault("source_choice_ref",
                          f"choice_{page.number}_{cluster[0].get('row',0)}")
        first=_source_line(page.text,cluster[0].get("row",0))
        if first:parent["source_line"]=first
        fields=[f for f in fields if f is parent or f not in selected]
        _source_conditions(fields,parent,cluster,page)

    # If every physical answer box has a sourced anchor, don't render a
    # second answer for the section heading itself.
    if _printed_box_rows(page.text)<={
       a.get("row") for a in anchors if isinstance(a.get("row"),int)}:
        heading=_norm(page.section_title)
        fields=[f for f in fields if (
            any(f is original for original in choice_parents) or
            f.get("source")=="workbook_printed_answer_box" or
            not (_label_is_heading(f.get("label"),heading) and
                 all(not _matched(f.get("label"),a.get("label"))
                     for a in anchors)))]

    # Information icons distinguish an explanation of another answer from
    # a writable response. They are not standalone fields.
    fields=[f for f in fields if not _unboxed_printed_instruction(
        f,page,anchors)]
    # A model can render a source field twice. Allow as many occurrences as
    # physically printed anchors, otherwise keep one. No global label dedupe.
    capacities=Counter(_norm(a.get("label")) for a in anchors)
    seen=Counter()
    distinct=[]
    for f in fields:
        key=_norm(f.get("label"))
        if not key:
            continue
        if key in capacities and seen[key]>=capacities[key]:
            continue
        if key not in capacities and seen[key]>0 and not f.get("row"):
            continue
        seen[key]+=1
        distinct.append(f)
    # Restore printed reading order: options above their conditional
    # details, not whatever order the model happened to emit.
    distinct.sort(key=lambda f:(
        f.get("source_line") if isinstance(f.get("source_line"),int)
        else 10**6))
    return {"title":inventory.get("title") or "Formularz",
            "pages":[{"title":page.group_title or page.section_title or "Dane",
                      "sections":[{"title":page.section_title or "Dane",
                                   "fields":distinct}]}]},recovered
