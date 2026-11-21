"""Evaluate fictional held-out FormFlow documents against declared expectations.

The fixture expectations are test data, never imported by the converter.
This audits meaning and COI controls rather than relying on HTTP or quality.ok.
Usage: python scripts/evaluate_independent.py INPUT_DIR RESULTS_DIR
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

INPUT_TYPES = {
    "TEXT_FIELD",
    "TEXTAREA",
    "DATEPICKER",
    "NUMBER",
    "RADIO",
    "CHECKBOX",
    "SELECT",
    "FILE_UPLOADER",
}


def sections(form):
    for tab in form.get("tabs", []):
        if tab.get("type") != "MAIN":
            continue
        for question in tab.get("questions", []):
            item = question.get("field", {})
            if item.get("type") == "SECTION":
                yield item.get("title", ""), item.get("repeatingSectionGrid", [])


def all_fields(form):
    for title, cells in sections(form):
        for cell in cells:
            if "field" in cell:
                yield title, cell["field"], cell


def compare(payload, expected):
    errors = []
    if payload.get("status") not in ("generated", "needs_review"):
        return ["Brak prawidłowego wyniku konwersji"]
    if not payload.get("quality", {}).get("ok", False):
        errors.append("Kontrola jakości nie zaliczona")
    fields = list(all_fields(payload.get("form", {})))
    inputs = [(s, f, c) for s, f, c in fields if f.get("type") in INPUT_TYPES]
    actual_types = Counter(f.get("type") for _, f, _ in inputs)
    if len(inputs) != expected["input_fields"]:
        errors.append(f"Pola: {len(inputs)} / {expected['input_fields']}")
    if "types" in expected:
        for typ, count in expected["types"].items():
            if actual_types[typ] != count:
                errors.append(f"{typ}: {actual_types[typ]} / {count}")
    if "notes_type_allowed" in expected:
        if not any(
            "uwagi" in f.get("title", "").casefold()
            and f.get("type") in expected["notes_type_allowed"]
            for _, f, _ in inputs
        ):
            errors.append("Brak właściwego pola uwag")
    if "pages" in expected:
        seen = payload.get("document", {}).get("extraction", {}).get("pages")
        if seen != expected["pages"]:
            errors.append(f"Źródłowe strony: {seen} / {expected['pages']}")
    if "radio_options" in expected:
        if not any(
            set(expected["radio_options"])
            <= set(o.get("name") for o in f.get("options", []))
            for _, f, _ in inputs
            if f.get("type") == "RADIO"
        ):
            errors.append("Niepoprawny jednokrotny wybór i/lub opcje")
    if "checkbox_options" in expected:
        if not any(
            set(expected["checkbox_options"])
            <= set(o.get("name") for o in f.get("options", []))
            for _, f, _ in inputs
            if f.get("type") == "CHECKBOX"
        ):
            errors.append("Niepoprawny wielokrotny wybór i/lub opcje")
    if "conditional_detail" in expected:
        if not any(
            expected["conditional_detail"] in f.get("title", "").casefold()
            and any(state.get("type") == "SHOW" for state in f.get("states", []))
            for _, f, _ in inputs
        ):
            errors.append("Brak warunku na polu szczegółów")
    if "literal_static" in expected:
        if not any(
            expected["literal_static"] in f.get("description", "")
            for _, f, _ in fields
            if f.get("type") == "TEXT_BLOCK"
        ):
            errors.append("Zmieniono lub zgubiono dosłowny tekst instrukcji")
    if not expected.get("signature_input", True):
        if any(re.search(r"(?i)\bpodpis\b", f.get("title", "")) for _, f, _ in inputs):
            errors.append("Wprowadzono edytowalne pole podpisu")
    if not expected.get("declaration_choice", True):
        if any(
            "oświadczam" in f.get("title", "").casefold()
            for _, f, _ in inputs
            if f.get("type") in {"RADIO", "CHECKBOX"}
        ):
            errors.append("Oświadczenie zamienione w wybór")
    if "repeated_label_roles" in expected:
        if sum(
            "imię i nazwisko" in f.get("title", "").casefold() for _, f, _ in inputs
        ) < len(expected["repeated_label_roles"]):
            errors.append("Zgubiono jedno z powtarzających się pól osoby")
    if "table_rows" in expected:

        def has_grid(cells):
            row_columns = {}
            for cell in cells:
                if cell.get("cols") != 1:
                    continue
                if cell.get("x") not in (0, 1, 2):
                    continue
                row_columns.setdefault(cell.get("y"), set()).add(cell["x"])
            return any(
                all(row_columns.get(first + offset) == {0, 1, 2} for offset in range(3))
                for first in row_columns
                if isinstance(first, int)
            )

        if not any(has_grid(cells) for _, cells in sections(payload.get("form", {}))):
            errors.append("Nie zachowano tabeli 3x3")
    if not expected.get("all_required", True):
        if all("REQUIRED" in f.get("validation", []) for _, f, _ in inputs):
            errors.append("Wszystkie odpowiedzi oznaczono jako obowiązkowe")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixtures", type=Path)
    ap.add_argument("results", type=Path)
    args = ap.parse_args()
    cases = json.loads((args.fixtures / "expected.json").read_text())
    summary = json.loads((args.results / "summary.json").read_text())
    by_name = {x["file"]: x for x in summary}
    failed = 0
    for name, expected in cases.items():
        row = by_name.get(name)
        if not row or row.get("http") != 200:
            errors = ["Brak wyniku HTTP 200, status " + str((row or {}).get("http"))]
        else:
            payload = json.loads((args.results / row["response"]).read_text())
            errors = compare(payload, expected)
        failed += bool(errors)
        print(name, "PASS" if not errors else "FAIL", "; ".join(errors))
    print(f"Finished: {len(cases)-failed}/{len(cases)} pass")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
