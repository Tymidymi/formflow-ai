"""Recover numbered source subsections without inventing or modifying controls.

A single collapsed model section can be split, even alongside other chapters. Fields are located against
the actual OCR line sequence, including repeated captions, so a later "Ulica"
can correctly belong to a later "2.4" instead of an earlier "2.2".
Uncertain cases remain untouched for manual review.
"""
from __future__ import annotations

import re
import unicodedata

HEADING = re.compile(r"^\s*(?P<number>\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+(?P<name>\S.*)$")


def normalized(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text).translate(str.maketrans("łŁ", "lL")))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", "".join(
        c for c in value.lower() if not unicodedata.combining(c)
    ))).strip()


def source_subsections(text: str) -> list[tuple[int, str, str]]:
    items = []
    for i, line in enumerate(text.splitlines()):
        match = HEADING.match(line)
        if not match:
            continue
        number = match["number"]
        label = match["name"].strip()
        # OCR often cuts a parenthetical note across lines; do not present an
        # unfinished sentence as part of the user's section heading.
        if label.count("(") > label.count(")"):
            label = label.split("(", 1)[0].rstrip()
        if len(label) > 180 or len(normalized(label).split()) < 2:
            continue
        if not any(c.isalpha() for c in label):
            continue
        items.append((i, number, f"{number}. {label}"))
    # Require sibling headings (2.1, 2.2), never split on random numbered notes.
    siblings: dict[str, list[tuple[int, str, str]]] = {}
    for entry in items:
        parent = entry[1].rsplit(".", 1)[0]
        siblings.setdefault(parent, []).append(entry)
    chosen = max(siblings.values(), key=len, default=[])
    return chosen if len(chosen) >= 2 else []


def _match_line(
    lines: list[str], label: str, start: int, start_col: int
) -> tuple[int, int] | None:
    target = normalized(label)
    if len(target) < 3:
        return None
    for i in range(start, len(lines)):
        pos = lines[i].find(target, start_col if i == start else 0)
        if pos >= 0:
            return i, pos + len(target)
    # OCR may wrap the caption. Only use neighboring lines after cursor.
    if len(target) >= 12:
        for i in range(start, len(lines) - 1):
            combined = lines[i] + " " + lines[i + 1]
            pos = combined.find(target, start_col if i == start else 0)
            if pos >= 0:
                return i + (pos > len(lines[i])), 0
    return None


def recover_numbered_sections(text: str, sections: list[dict]) -> tuple[list[dict], list[str]]:
    """Partition an evidenced collapsed parent, leaving unrelated sections alone."""
    if not sections:
        return sections, []
    headings = source_subsections(text)
    if not headings:
        return sections, []
    # When the model already separated chapter "1. Instructions" from "2.
    # Applicant", recover subsection siblings only inside their parent. Do not
    # merge or rewrite unrelated model sections.
    parent = headings[0][1].split(".", 1)[0]
    if len(sections) == 1:
        target_index = 0
    else:
        matches = [
            i for i, section in enumerate(sections)
            if re.match(r"^\s*" + re.escape(parent) + r"\.\s+", str(section.get("title") or ""))
        ]
        if len(matches) != 1:
            return sections, []
        target_index = matches[0]
    original = sections[target_index]
    fields = original.get("fields") or []
    if len(fields) < 2:
        return sections, []
    # Sibling subsections may be followed by independent numbered top-level
    # chapters (3. Opłata, 4. Uzasadnienie, ...). Treat those chapters as
    # boundaries too: never attach all subsequent fields to the last "2.4".
    headings_for_fields = [(row, title) for row, _, title in headings]
    parent_number = int(headings[0][1].split(".", 1)[0])
    root_heading = re.compile(r"^\s*(?P<number>\d{1,2})\.\s{1,8}(?P<title>\S.*)$")
    for row, line in enumerate(text.splitlines()):
        if row <= headings[-1][0]:
            continue
        root = root_heading.match(line)
        if not root or int(root["number"]) <= parent_number:
            continue
        title = root["title"].strip()
        if title.count("(") > title.count(")"):
            title = title.split("(", 1)[0].rstrip()
        if len(title) > 180 or len(normalized(title).split()) < 2:
            continue
        headings_for_fields.append((row, f'{root["number"]}. {title}'))
    headings_for_fields.sort(key=lambda entry: entry[0])
    lines = [normalized(line) for line in text.splitlines()]
    next_line = headings[0][0] + 1
    next_col = 0
    assigned = []
    last_section = -1
    hits = 0
    for field in fields:
        match = _match_line(lines, str(field.get("label") or ""), next_line, next_col)
        if match is None:
            assigned.append(last_section)
            continue
        row_found, col_found = match
        section_no = -1
        for i, (row, _) in enumerate(headings_for_fields):
            if row_found >= row:
                section_no = i
        if section_no >= 0:
            last_section = section_no
            hits += 1
        assigned.append(last_section)
        next_line, next_col = row_found, col_found
    # Do not reshape uncertain structures; a grouping error is worse than a
    # manual step. Require strong positioning evidence and >=2 populated groups.
    groups = {x for x in assigned if x >= 0}
    if len(groups) < 2 or hits < max(2, (len(fields) + 1) // 2):
        return sections, []
    prelude = [f for f, x in zip(fields, assigned) if x < 0]
    new_sections = []
    if prelude:
        new_sections.append({"title":original["title"], "fields":prelude})
    for i, (_, heading) in enumerate(headings_for_fields):
        group = [f for f, x in zip(fields, assigned) if x == i]
        if group:
            new_sections.append({"title":heading, "fields":group})
    recovered = sections[:target_index] + new_sections + sections[target_index + 1:]
    if len(recovered) > 24:
        return sections, []
    if sum(len(x["fields"]) for x in new_sections) != len(fields):
        return sections, []
    return recovered, [
        "Odtworzono numerowane podsekcje z oryginalnych nagłówków OCR; "
        "przydział pól wymaga kontroli w podglądzie źródła."
    ]
