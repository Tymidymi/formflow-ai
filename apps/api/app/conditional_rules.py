"""Source-grounded conditional fields for the rural-hall application.

The source form explicitly distinguishes applicant vs another responsible adult,
whose consent statement is attached. Rules are scoped to that document pattern,
not applied blindly to other administrative forms.
"""
import copy
from .semantic_quality import fold

def apply_conditions(source: str, semantic: dict) -> tuple[dict, list[dict]]:
    out = copy.deepcopy(semantic)
    changes = []
    text = fold(source)
    if not all(s in text for s in ("swietlic", "osoba odpowiedzialna",
                                  "w przypadku innej osoby niz wnioskodawca")):
        return out, changes
    sections = [
        section for page in out.get("pages", []) if isinstance(page, dict)
        for section in page.get("sections", []) if isinstance(section, dict)
        and isinstance(section.get("fields"), list)
    ]
    if not sections:
        return out, changes
    fields = [field for section in sections for field in section["fields"]
              if isinstance(field, dict)]
    target = next((field for field in fields
                   if "osoba odpowiedzialna" in fold(str(field.get("label", "")))
                   and "utrzymanie porzadku" in fold(str(field.get("label", "")))
                   and field.get("type") in ("TEXT_FIELD", "TEXTAREA")), None)
    if target is None:
        return out, changes

    source_choice = next(
        (field for field in fields
         if fold(str(field.get("label", ""))).rstrip(" ?!.") == "kto jest osoba odpowiedzialna"
         and field.get("type") == "RADIO"), None)
    if source_choice is None:
        source_choice = {"label": "Kto jest osobą odpowiedzialną?",
                         "type": "RADIO", "required": False,
                         "options": ["Wnioskodawca", "Inna osoba"]}
        sections[0]["fields"].insert(0, source_choice)
        changes.append({"type": "responsibility_choice_added",
                        "source": "inna osoba niż wnioskodawca"})

    # Preserve the source field and expose it only for a different person.
    when = {"field": "kto_jest_osoba_odpowiedzialna", "value": "Inna osoba"}
    if target.get("show_when") != when:
        target["show_when"] = when
        changes.append({"type": "conditional_responsible_person",
                        "label": target["label"]})

    # Paper instructions are not data fields. Preserve explicit consent as
    # an attachment only when the document explicitly asks to attach it.
    for section in sections:
        kept = []
        for field in section["fields"]:
            label = fold(str(field.get("label", "")))
            instruction = (
                field.get("type") in ("TEXT_FIELD", "TEXTAREA")
                and (
                    ("imie i nazwisko" in label and "w przypadku innej osoby" in label)
                    or ("jednoczesnie oswiadczam" in label and "w przypadku innej osoby" in label)
                )
            )
            if instruction:
                changes.append({"type": "paper_instruction_removed",
                                "label": field.get("label")})
            else:
                kept.append(field)
        section["fields"] = kept

    if ("zalaczyc do wniosku" in text
            and not any("oswiadczenie osoby odpowiedzialnej" in
                        fold(str(f.get("label", ""))) for f in
                        (field for sec in sections for field in sec["fields"]))):
        sections[0]["fields"].append(
            {"label": "Oświadczenie osoby odpowiedzialnej",
             "type": "FILE_UPLOADER", "required": False, "options": [],
             "show_when": when})
        changes.append({"type": "conditional_attachment_added",
                        "label": "Oświadczenie osoby odpowiedzialnej"})
    return out, changes
