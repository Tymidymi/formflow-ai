"""Compile restricted semantic show_when references into COI JSONata states.

No arbitrary JSONata from untrusted LLM output is executed or copied through.
All source fields must exist and offer the literal option being tested.
"""
from __future__ import annotations
import json

def _literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")

def attach_states(tabs: list[dict]) -> list[dict]:
    source_fields = {}
    targets = []
    for tab in tabs:
        if tab.get("type") != "MAIN":
            continue
        for section in tab.get("questions", []):
            parent = section.get("field", {})
            for entry in parent.get("repeatingSectionGrid", []):
                field = entry.get("field", {})
                tech = field.get("techName")
                if tech:
                    source_fields[tech] = (tab["title"], parent["techName"], field)
                if "__show_when" in field:
                    targets.append(field)
    for field in targets:
        spec = field.pop("__show_when")
        if not isinstance(spec, dict):
            continue
        source = spec.get("field")
        value = spec.get("value")
        if not isinstance(source, str) or not isinstance(value, str):
            continue
        found = source_fields.get(source)
        if found is None:
            continue
        tab_title, section_tech, src_field = found
        if src_field.get("type") not in ("RADIO", "CHECKBOX", "SELECT"):
            continue
        choices = [opt.get("name") for opt in src_field.get("options", [])
                   if isinstance(opt, dict)]
        if value not in choices:
            continue
        query = (
            "(" + json.dumps(value, ensure_ascii=False)
            + " in tabs['" + _literal(tab_title)
            + "' in title].questions['" + _literal(section_tech)
            + "' in field.techName].field.repeatingSectionGrid['"
            + _literal(source)
            + "' in field.techName].field.__userAnswer)"
        )
        field["states"] = [{"type": "SHOW", "query": query}]
    return tabs
