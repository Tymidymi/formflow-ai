"""Two-layer COI validation: verbatim official JSON Schema + documented business rules.

The supplied COI schema has no 'required' lists and allows undeclared properties.
Passing it is necessary but NOT proof of compatibility with a real importer.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).with_name("contracts") / "coi_form_schema.json"
OFFICIAL_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = Draft202012Validator(OFFICIAL_SCHEMA)

VALID_TYPES = {
    "TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX",
    "SELECT", "FILE_UPLOADER", "SECTION", "REPEATING_SECTION",
    "INFO_SECTION", "TEXT_BLOCK", "CONSENT_SECTION",
}
INPUT_TYPES = {
    "TEXT_FIELD", "TEXTAREA", "NUMBER", "DATEPICKER", "RADIO", "CHECKBOX",
    "SELECT", "FILE_UPLOADER",
}
VALID_RULES = {
    "REQUIRED", "EMAIL", "PESEL", "NIP", "REGON", "ZIP_CODE",
    "EPUAP", "ADE", "SERIAL_NUMBER_ID_CARD",
}


def uuid_ok(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _path(parts) -> str:
    return "$" + "".join(f"[{x}]" if isinstance(x, int) else f".{x}" for x in parts)


def validate_coi_form(data: object) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    summary = {"tabs": 0, "fields_including_sections": 0, "input_fields": 0, "links": 0}
    def error(path: str, code: str, message: str):
        errors.append({"path": path, "code": code, "message": message})
    def warn(path: str, code: str, message: str):
        warnings.append({"path": path, "code": code, "message": message})

    schema_errors = sorted(SCHEMA_VALIDATOR.iter_errors(data), key=lambda e: str(e.path))
    for item in schema_errors[:30]:
        error(_path(item.path), "COI_JSON_SCHEMA", item.message)
    schema_valid = not schema_errors

    if not isinstance(data, dict):
        error("$", "ROOT", "Formularz musi być obiektem JSON.")
        return {"valid": False, "schema_valid": schema_valid, "errors": errors,
                "warnings": warnings, "summary": summary}

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        error("$.title", "TITLE", "Brak tytułu formularza.")
    elif len(title) > 255:
        error("$.title", "TITLE_LENGTH", "Maksymalna długość tytułu: 255.")

    tabs = data.get("tabs")
    if not isinstance(tabs, list) or len(tabs) < 2:
        error("$.tabs", "TABS", "Wymagane minimum jedna strona MAIN i jedna FINISH.")
        tabs = tabs if isinstance(tabs, list) else []
    summary["tabs"] = len(tabs)
    tab_ids: set[str] = set()
    field_ids: set[str] = set()
    tech_names: set[str] = set()

    def inspect_questions(items: object, path: str, level: int, on_finish: bool):
        if not isinstance(items, list) or not items:
            error(path, "QUESTIONS", "Wymagana niepusta lista pytań.")
            return
        occupied: set[tuple[int, int]] = set()
        for i, entry in enumerate(items):
            p = f"{path}[{i}]"
            if not isinstance(entry, dict):
                error(p, "QUESTION", "Pytanie musi być obiektem.")
                continue
            for prop in ("x", "y", "rows", "cols"):
                val = entry.get(prop)
                if not isinstance(val, int) or isinstance(val, bool) or val < (1 if prop in ("rows", "cols") else 0):
                    error(f"{p}.{prop}", "GRID", "Nieprawidłowe współrzędne/wymiary siatki.")
            x, y, rows, cols = [entry.get(k) for k in ("x", "y", "rows", "cols")]
            if all(type(v) is int for v in (x, y, rows, cols)) and rows > 0 and cols > 0:
                if x + cols > 3:
                    warn(p, "GRID_WIDTH", "Pole wychodzi poza siatkę trzech kolumn.")
                if rows * cols < 500:
                    coords = {(ix, iy) for ix in range(x, x + cols) for iy in range(y, y + rows)}
                    if occupied & coords:
                        warn(p, "GRID_OVERLAP", "Elementy siatki nakładają się.")
                    occupied.update(coords)
            f = entry.get("field")
            if not isinstance(f, dict):
                error(f"{p}.field", "FIELD", "Brak konfiguracji pola.")
                continue
            summary["fields_including_sections"] += 1
            kind = f.get("type")
            fid = f.get("id")
            if not uuid_ok(fid):
                error(f"{p}.field.id", "FIELD_UUID", "ID pola musi być UUID.")
            elif fid in field_ids:
                error(f"{p}.field.id", "FIELD_ID_DUP", "Powtórzony identyfikator pola.")
            else:
                field_ids.add(fid)
            if kind not in VALID_TYPES:
                error(f"{p}.field.type", "FIELD_TYPE", "Nieznany typ komponentu.")
            tech = f.get("techName")
            if not isinstance(tech, str) or not tech.strip():
                error(f"{p}.field.techName", "TECHNAME", "Brak nazwy technicznej.")
            elif tech in tech_names:
                warn(f"{p}.field.techName", "TECHNAME_REUSE", "Nazwa techniczna występuje wielokrotnie.")
            else:
                tech_names.add(tech)
            if not isinstance(f.get("validation", []), list):
                error(f"{p}.field.validation", "VALIDATION", "Walidacje muszą być listą.")
            else:
                for rule in f.get("validation", []):
                    if not isinstance(rule, str):
                        error(f"{p}.field.validation", "VALIDATION_TYPE", "Walidacja musi być stringiem.")
                    elif rule not in VALID_RULES:
                        warn(f"{p}.field.validation", "UNKNOWN_VALIDATION", "Nierozpoznana nazwa walidacji.")
            for attr in ("states", "options"):
                if not isinstance(f.get(attr, []), list):
                    error(f"{p}.field.{attr}", "LIST", "Wymagana tablica.")
            for j, state in enumerate(f.get("states", []) if isinstance(f.get("states", []), list) else []):
                if not isinstance(state, dict) or state.get("type") not in ("SHOW", "READ_ONLY") or not isinstance(state.get("query"), str):
                    error(f"{p}.field.states[{j}]", "STATE", "Oczekiwano SHOW/READ_ONLY z zapytaniem JSONata.")
            if level == 0 and kind not in ("SECTION", "REPEATING_SECTION", "INFO_SECTION"):
                error(f"{p}.field.type", "SECTION_REQUIRED", "Element na stronie powinien być sekcją.")
            if level > 0 and kind in ("SECTION", "REPEATING_SECTION"):
                error(f"{p}.field.type", "NESTED_SECTION", "Sekcja nie może znajdować się w innej sekcji.")
            if kind in ("SECTION", "REPEATING_SECTION"):
                # The COI schema has a 'repetingSectionGrid' typo, but both official
                # reference examples correctly use 'repeatingSectionGrid'.
                children = f.get("repeatingSectionGrid", f.get("repetingSectionGrid"))
                inspect_questions(children, f"{p}.field.repeatingSectionGrid", level + 1, on_finish)
            elif kind in INPUT_TYPES:
                summary["input_fields"] += 1
                if on_finish:
                    error(p, "FINISH_INPUT", "Strona FINISH nie może zawierać pól do wypełnienia.")
            if on_finish and level == 0 and kind == "SECTION":
                warn(f"{p}.field.type", "FINISH_SECTION_EXAMPLE",
                     "Reguły COI sugerują INFO_SECTION, lecz dostarczone wzorce używają SECTION + TEXT_BLOCK.")
            if kind in ("RADIO", "SELECT", "CHECKBOX"):
                choices = f.get("options", [])
                if not choices and not f.get("dictionaryName"):
                    warn(f"{p}.field.options", "EMPTY_CHOICES", "Pole wyboru bez opcji ani słownika.")

    for i, tab in enumerate(tabs):
        p = f"$.tabs[{i}]"
        if not isinstance(tab, dict):
            error(p, "TAB", "Strona musi być obiektem.")
            continue
        tid = tab.get("id")
        if not uuid_ok(tid):
            error(f"{p}.id", "TAB_UUID", "ID strony musi być UUID.")
        elif tid in tab_ids:
            error(f"{p}.id", "TAB_DUP", "Powtórzony identyfikator strony.")
        else:
            tab_ids.add(tid)
        expected = "FINISH" if i == len(tabs)-1 else "MAIN"
        if tab.get("type") != expected:
            error(f"{p}.type", "TAB_TYPE", f"Typ strony powinien być {expected}.")
        if not isinstance(tab.get("title"), str) or not tab["title"].strip():
            error(f"{p}.title", "TAB_TITLE", "Brak tytułu strony.")
        inspect_questions(tab.get("questions"), f"{p}.questions", 0, tab.get("type")=="FINISH")

    flow = data.get("flow")
    links = flow.get("links") if isinstance(flow, dict) else None
    if not isinstance(links, list):
        error("$.flow.links", "FLOW", "Wymagana tablica przepływu stron.")
        links = []
    summary["links"] = len(links)
    edges: list[tuple[str, str]] = []
    for i, link in enumerate(links):
        p = f"$.flow.links[{i}]"
        if not isinstance(link, dict):
            error(p, "LINK", "Połączenie musi być obiektem.")
            continue
        if not uuid_ok(link.get("id")):
            # Reference #5 uses short IDs such as 'a16ec'; official schema accepts strings.
            warn(f"{p}.id", "LINK_ID_NON_UUID", "Reguły opisują UUID; przykład COI zawiera też krótkie identyfikatory.")
        src, dest = link.get("source"), link.get("target")
        if src not in tab_ids or dest not in tab_ids:
            error(p, "LINK_TARGET", "Połączenie odwołuje się do nieznanej strony.")
        elif src == dest:
            warn(p, "SELF_LINK", "Pętla do tej samej strony.")
        else:
            edges.append((src, dest))
    if tabs and isinstance(tabs[0], dict) and isinstance(tabs[-1], dict):
        first = tabs[0].get("id")
        final = tabs[-1].get("id")
        accessible = {first}
        for _ in range(len(tabs)):
            accessible.update(dest for src, dest in edges if src in accessible)
        if final not in accessible:
            error("$.flow.links", "UNREACHABLE_FINISH", "Strona końcowa jest nieosiągalna z pierwszej.")
    return {"valid": not errors, "schema_valid": schema_valid, "errors": errors,
            "warnings": warnings, "summary": summary,
            "note": "schema_valid = zgodność z oryginalnym JSON Schema; valid = schemat + dodatkowe reguły."}
