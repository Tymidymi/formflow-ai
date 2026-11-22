"""Deterministic semantic form -> COI tabs/questions/flow exporter."""

from __future__ import annotations

import re
import unicodedata
from html import escape
from uuid import NAMESPACE_URL, uuid5
from .coi_validation import validate_coi_form
from .coi_conditions import attach_states
from .canonical_form import canonicalize
from .source_layout import layout_for_fields

KINDS = {
    "TEXT_FIELD",
    "TEXTAREA",
    "NUMBER",
    "DATEPICKER",
    "RADIO",
    "CHECKBOX",
    "SELECT",
    "FILE_UPLOADER",
    "INFO_BLOCK",
}
# Match only sufficiently explicit field labels. These are suggestions, not legal
# interpretation; never infer required-ness from the mere presence of a field.
VALIDATORS = [
    (re.compile(r"(?i)\bPESEL\b"), "PESEL"),
    (re.compile(r"(?i)\bNIP\b"), "NIP"),
    (re.compile(r"(?i)\bREGON\b"), "REGON"),
    (re.compile(r"(?i)\b(kod pocztowy|pocztowy kod)\b"), "ZIP_CODE"),
    (
        re.compile(r"(?i)\b(e-mail|email|adres e.?mail|adres poczty elektronicznej)\b"),
        "EMAIL",
    ),
]


def slug(text: str) -> str:
    raw = (
        unicodedata.normalize("NFKD", text.translate(str.maketrans("łŁ", "lL")))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return (re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_") or "pole")[:55]


def identifier(*parts: str) -> str:
    return str(
        uuid5(NAMESPACE_URL, "formflow-ai/coi/v1/" + "/".join(str(v) for v in parts))
    )


def field(
    label: str,
    kind: str,
    name: str,
    path: str,
    *,
    children=None,
    options=None,
    required=False,
    description="",
    validation=None,
) -> dict:
    return {
        "id": identifier(path),
        "type": kind,
        "techName": name,
        "title": label,
        "description": description,
        "options": options or [],
        "validation": (
            validation if validation is not None else (["REQUIRED"] if required else [])
        ),
        "readOnly": False,
        "repeatingSectionGrid": children or [],
        "states": [],
        "questionOrder": 0,
        "tooltipMessage": "",
    }


def wrap(item: dict, y: int, order: int) -> dict:
    item["questionOrder"] = order
    return {"x": 0, "y": y, "rows": 1, "cols": 3, "field": item}


def safe_list(data: dict, key: str) -> list:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def field_validation(label: str, required: bool) -> list[str]:
    rules = ["REQUIRED"] if required else []
    for expression, code in VALIDATORS:
        if code == "EMAIL" and re.search(r"(?i)telefon|phone", label):
            continue
        if expression.search(label):
            rules.append(code)
            break
    return rules


def convert(semantic: dict) -> tuple[dict, dict]:
    semantic = canonicalize(semantic)
    pages = safe_list(semantic, "pages")
    if not pages:
        raise ValueError("Model nie zidentyfikował stron.")
    if len(pages) > 24:
        raise ValueError("Zbyt wiele stron formularza do bezpiecznego eksportu COI.")
    title = str(semantic.get("title") or "Formularz urzędowy")[:255]
    tabs = []
    used = set()
    total = 0
    choice_refs = {}
    pending_conditions = []
    for pi, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        questions = []
        y = 0
        sections = safe_list(page, "sections")
        if len(sections) > 24:
            raise ValueError("Zbyt wiele sekcji na stronie.")
        for si, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            children = []
            source_fields = safe_list(section, "fields")
            # The source may describe a real table. COI supports a 3-column
            # grid; preserve its printed row/column structure instead of
            # flattening multiple cells into a vertical list.
            tabular = bool(
                source_fields
                and all(
                    isinstance(f, dict)
                    and isinstance(f.get("row"), int)
                    and isinstance(f.get("column"), str)
                    and f["row"] > 0
                    for f in source_fields
                )
            )
            columns = list(dict.fromkeys(str(f.get("column")) for f in source_fields))
            tabular = tabular and 2 <= len(columns) <= 3
            column_positions = {name: i for i, name in enumerate(columns)}
            inferred_positions = layout_for_fields(source_fields) if not tabular else []

            if len(source_fields) > 120:
                raise ValueError("Zbyt wiele pól w pojedynczej sekcji.")
            for fi, data in enumerate(source_fields):
                if not isinstance(data, dict):
                    continue
                label = str(data.get("label") or "").strip()[:220]
                if not label:
                    continue
                kind = data.get("type", "TEXT_FIELD")
                if kind not in KINDS:
                    kind = "TEXT_FIELD"
                name = slug(label)
                base = name
                j = 2
                while name in used:
                    name = base[:50] + "_" + str(j)
                    j += 1
                used.add(name)
                raw = data.get("options")
                opts = []
                if kind in {"RADIO", "CHECKBOX", "SELECT"} and isinstance(raw, list):
                    seen = set()
                    for opt in raw[:20]:
                        val = str(opt).strip()[:160]
                        if val and val not in seen:
                            seen.add(val)
                            opts.append({"id": val, "name": val, "techName": slug(val)})
                dictionary = data.get("dictionary_name")
                if dictionary not in ("Kraje", "TERYT_DOWODOWY", "TERYT_4G_DOWODOWY"):
                    dictionary = None
                if kind == "SELECT" and not opts and not dictionary:
                    if slug(label) in ("kraj", "kraj_zamieszkania", "kraj_urodzenia"):
                        dictionary = "Kraje"
                if kind in {"RADIO", "SELECT"} and not opts and not dictionary:
                    kind = "TEXT_FIELD"
                if kind == "CHECKBOX" and not opts:
                    # An explicit independent yes/no checkbox needs no invented
                    # enumerated choices; fill only if specified by the document.
                    pass
                if kind == "NUMBER" and re.search(
                    r"(?i)\b(PESEL|NIP|REGON|kod pocztowy)\b", label
                ):
                    kind = "TEXT_FIELD"  # preserve leading zeros
                validation = field_validation(label, data.get("required") is True)
                item = field(
                    label,
                    kind,
                    name,
                    f"{title}/{pi}/{si}/{fi}/{name}",
                    options=opts,
                    validation=validation,
                )
                if kind == "INFO_BLOCK":
                    content = str(data.get("content", ""))[:7000]
                    # Use COI's supported read-only TEXT_BLOCK, not TEXTAREA.
                    item["type"] = "TEXT_BLOCK"
                    item["readOnly"] = True
                    item["validation"] = []
                    item["description"] = (
                        "<html><head></head><body><p>"
                        + escape(content).replace("\n", "<br/>")
                        + "</p></body></html>"
                    )
                if kind in {"RADIO", "CHECKBOX", "SELECT"} and dictionary:
                    item["dictionaryName"] = dictionary
                if isinstance(data.get("source_choice_ref"), str):
                    choice_refs[data["source_choice_ref"]] = name
                if isinstance(data.get("show_when"), dict):
                    spec = dict(data["show_when"])
                    ref = spec.pop("field_ref", None)
                    if isinstance(ref, str):
                        pending_conditions.append((item, ref))
                    item["__show_when"] = spec
                placement = wrap(item, len(children), len(children))
                if tabular:
                    placement["x"] = column_positions[data["column"]]
                    placement["y"] = max(0, data["row"] - 1)
                    placement["cols"] = 1
                else:
                    placement.update(inferred_positions[fi])
                children.append(placement)
                total += 1
                if total > 400:
                    raise ValueError("Formularz przekracza maksymalną liczbę 400 pól.")
            if not children:
                continue
            heading = str(section.get("title") or "Dane")[:220]
            item = field(
                heading,
                "SECTION",
                f"sekcja_{pi}_{si}_{slug(heading)}",
                f"{title}/section/{pi}/{si}/{heading}",
                children=children,
                description="<html><head></head><body></body></html>",
            )
            section_height = (
                max((cell["y"] + cell["rows"] for cell in children), default=0) + 1
            )
            questions.append(
                {
                    "x": 0,
                    "y": y,
                    "rows": section_height,
                    "cols": 3,
                    "field": {**item, "questionOrder": len(questions)},
                }
            )
            y += section_height
            if total > 400:
                raise ValueError("Formularz przekracza maksymalną liczbę 400 pól.")
        if questions:
            tabs.append(
                {
                    "id": identifier(title, "tab", str(pi)),
                    "title": str(page.get("title") or f"Dane {pi+1}")[:220],
                    "type": "MAIN",
                    "questions": questions,
                }
            )
        if total > 400:
            raise ValueError("Formularz przekracza maksymalną liczbę 400 pól.")
    if not tabs:
        raise ValueError("Model nie wykrył pól.")
    info = field(
        "",
        "TEXT_BLOCK",
        "tekst_koncowy",
        f"{title}/finish/text",
        description="<html><head></head><body><p>Sprawdź dane przed wysłaniem wniosku.</p></body></html>",
    )
    finish = field(
        "Podgląd i wysłanie wniosku",
        "SECTION",
        "podglad_wniosku",
        f"{title}/finish/section",
        children=[wrap(info, 0, 0)],
    )
    tabs.append(
        {
            "id": identifier(title, "finish"),
            "title": "Strona końcowa",
            "type": "FINISH",
            "questions": [{"x": 0, "y": 0, "rows": 2, "cols": 3, "field": finish}],
        }
    )
    links = [
        {
            "id": identifier(title, "link", a["id"], b["id"]),
            "source": a["id"],
            "target": b["id"],
        }
        for a, b in zip(tabs, tabs[1:])
    ]
    # The source group can share a printed caption with groups on other
    # source pages. Resolve dependencies via internal instance references,
    # never by a possibly duplicated label or untrusted model expression.
    for item, ref in pending_conditions:
        item["__show_when"]["field"] = choice_refs.get(ref)
    attach_states(tabs)
    coi = {"title": title, "tabs": tabs, "flow": {"links": links}}
    return coi, validate_coi_form(coi)
