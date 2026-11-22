"""Source-grounded semantic normalization for form controls.

No rules depend on form titles, page names, or fixture-specific field labels.
"""

from difflib import SequenceMatcher
import re
import unicodedata

_SIGNATURE = re.compile(
    r"(?iu)^\s*(?:czytelny\s+|własnoręczny\s+)?podpis\b|^\s*signature\b"
)
_SINGLE = re.compile(
    r"(?iu)\b(?:dokładnie\s+(?:jeden|jedną|jedno)|"
    r"(?:wybierz|zaznacz|wskaż)\s+(?:tylko\s+)?(?:jeden|jedną|jedno)|"
    r"(?:choose|select)\s+(?:exactly\s+)?one)\b"
)
_MULTIPLE = re.compile(
    r"(?iu)\b(?:można\s+zaznaczyć\s+kilka|"
    r"(?:wybierz|zaznacz)\s+(?:kilka|wiele|wszystkie)|"
    r"(?:select|choose)\s+(?:multiple|all\s+that\s+apply))\b"
)


def normalize_observed_field(raw: dict, source_text: str) -> tuple[dict, str | None]:
    """Apply only type corrections supported by the same physical source."""
    field = dict(raw)
    label = str(field.get("label") or "").strip()
    kind = field.get("type")
    evidence = str(field.get("evidence") or "")
    context = label + " " + evidence
    rendered = " ".join(source_text.casefold().split())
    source_support = bool(label and " ".join(label.casefold().split()) in rendered)

    if source_support and kind == "INFO_BLOCK" and not _SIGNATURE.search(label):
        for line in source_text.splitlines():
            pos = line.casefold().find(label.casefold())
            if pos < 0:
                continue
            suffix = line[pos + len(label) :]
            if re.match(r"^\s*(?:\.{5,}|_{4,}|…{3,})", suffix):
                return (
                    {
                        "label": label,
                        "type": "TEXT_FIELD",
                        "required": False,
                        "required_evidence": "",
                        "options": [],
                        "evidence": evidence or label,
                        "region": None,
                        "row": None,
                        "column": "",
                        "content": "",
                        "source_choice_ref": "",
                        "show_when": None,
                    },
                    "Źródłowy obszar odpowiedzi nie może być tylko blokiem informacyjnym.",
                )

    if source_support and kind != "INFO_BLOCK" and _SIGNATURE.search(label):
        field = {
            "label": label,
            "type": "INFO_BLOCK",
            "evidence": evidence or label,
            "content": evidence or label,
        }
        return field, "Podpis papierowy zapisano jako instrukcję, nie pole edycyjne."

    if source_support and kind in ("RADIO", "CHECKBOX") and field.get("options"):
        single = bool(_SINGLE.search(context))
        multiple = bool(_MULTIPLE.search(context))
        if single != multiple:
            desired = "RADIO" if single else "CHECKBOX"
            if kind != desired:
                field["type"] = desired
                return (
                    field,
                    "Dostosowano wybór jedno-/wielokrotny do instrukcji źródła.",
                )
    return field, None


def _choice_key(value):
    text = str(value).casefold().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if c.isalnum())


def match_source_option(value: str, options: list[str]) -> str | None:
    """Resolve unambiguous spelling/inflection to an *actual* printed option.

    A low-confidence match stays unresolved; we do not invent a new option.
    """
    key = _choice_key(value)
    if not key:
        return None
    matches = [option for option in options if _choice_key(option) == key]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1 or len(key) < 4:
        return None
    ranked = sorted(
        (
            SequenceMatcher(None, key, _choice_key(option)).ratio(),
            option,
        )
        for option in options
    )
    if not ranked:
        return None
    top_score, top = ranked[-1]
    next_score = ranked[-2][0] if len(ranked) > 1 else 0
    return top if top_score >= 0.82 and top_score - next_score >= 0.22 else None


def reconcile_conditions(sections: list[dict]) -> list[str]:
    """Align conditional values with existing choice options, or leave errors."""
    fields = [f for s in sections for f in s.get("fields", [])]
    choices = {
        f["source_choice_ref"]: f
        for f in fields
        if f.get("source_choice_ref") and f.get("options")
    }
    changes = []
    for field in fields:
        condition = field.get("show_when")
        if not isinstance(condition, dict):
            continue
        target = choices.get(condition.get("field_ref"))
        if target is None:
            continue
        actual = match_source_option(condition.get("value", ""), target["options"])
        if actual is not None and actual != condition.get("value"):
            condition["value"] = actual
            changes.append(
                "Dopasowano warunek do istniejącej opcji źródłowej: "
                + field["label"][:60]
            )
    return changes


def preserve_static_source(raw: dict, source_text: str) -> tuple[dict, str | None]:
    """Copy a high-confidence OCR passage verbatim instead of model proofreading."""
    if raw.get("type") != "INFO_BLOCK":
        return raw, None
    content = str(raw.get("content") or "").strip()
    if len(content) < 35:
        return raw, None
    norm = lambda value: " ".join(
        unicodedata.normalize("NFKC", value).casefold().split()
    )
    lines = [
        line.strip()
        for line in source_text.splitlines()
        if line.strip() and not line.strip().startswith("[Strona")
    ]
    target = norm(content)
    winner = (0.0, None)
    for first in range(len(lines)):
        for width in range(1, min(5, len(lines) - first) + 1):
            passage = " ".join(lines[first : first + width])
            ratio = len(passage) / len(content)
            if ratio > 1.25:
                break
            if ratio < 0.78:
                continue
            similarity = SequenceMatcher(None, target, norm(passage)).ratio()
            if similarity > winner[0]:
                winner = (similarity, passage)
    if winner[0] < 0.93 or winner[1] is None or norm(content) == norm(winner[1]):
        return raw, None
    corrected = dict(raw)
    corrected["content"] = winner[1]
    return corrected, "Przywrócono dosłowną treść z OCR zamiast redakcji modelu."
