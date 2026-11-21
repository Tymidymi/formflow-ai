"""Reproducible, fictional documents for manual end-to-end validation.

Run with the API test environment and an output directory. Expectations belong
here, never in conversion code. These forms are unrelated to the audit corpus.
"""

import json
from pathlib import Path
import sys
from docx import Document
from docx.shared import Cm, Pt


def document(title):
    doc = Document()
    doc.sections[0].top_margin = Cm(1.5)
    doc.sections[0].bottom_margin = Cm(1.5)
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(title, 0)
    return doc


def create(root):
    root.mkdir(parents=True, exist_ok=True)
    expected = {}
    doc = document("Zgłoszenie serwisowe sprzętu")
    for line in [
        "Nazwa zgłaszającego: ........................................",
        "Telefon lub e-mail (opcjonalnie): ........................................",
        "PESEL: ........................................",
        "Data zakupu: ........................................",
        "Koszt naprawy (PLN): ........................................",
        "Wybierz dokładnie jeden sposób odbioru: ☐ osobiście  ☐ pocztą",
        "Jeżeli wybrano pocztę, adres doręczenia: ........................................",
        "Załączniki (można zaznaczyć kilka): ☐ dowód zakupu  ☐ zdjęcia usterki",
        "Opis usterki:",
        "........................................................................................",
        "........................................................................................",
        "Podpis zgłaszającego: ........................................",
        "Informacja: dane służą wyłącznie obsłudze zgłoszenia. Zachowaj ten ten dokument.",
    ]:
        doc.add_paragraph(line)
    path = root / "service.docx"
    doc.save(path)
    expected[path.name] = {
        "input_fields": 9,
        "types": {
            "TEXT_FIELD": 4,
            "DATEPICKER": 1,
            "NUMBER": 1,
            "RADIO": 1,
            "CHECKBOX": 1,
            "TEXTAREA": 1,
        },
        "radio_options": ["osobiście", "pocztą"],
        "checkbox_options": ["dowód zakupu", "zdjęcia usterki"],
        "conditional_detail": "adres doręczenia",
        "literal_static": "Zachowaj ten ten dokument.",
        "signature_input": False,
        "all_required": False,
    }

    doc = document("Rezerwacja wyposażenia pracowni")
    doc.add_paragraph("Osoba rezerwująca: ........................................")
    doc.add_paragraph("Każdy wiersz oznacza oddzielną pozycję rezerwacji.")
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, text in zip(
        table.rows[0].cells, ["Kod wyposażenia", "Liczba sztuk", "Data rozpoczęcia"]
    ):
        cell.text = text
    for _ in range(3):
        for cell in table.add_row().cells:
            cell.text = ".........................."
    doc.add_paragraph(
        "Uwagi do całej rezerwacji: ........................................"
    )
    path = root / "table.docx"
    doc.save(path)
    expected[path.name] = {
        "input_fields": 11,
        "table_rows": 3,
        "table_columns": ["Kod wyposażenia", "Liczba sztuk", "Data rozpoczęcia"],
        "types": {"TEXT_FIELD": 4, "NUMBER": 3, "DATEPICKER": 3},
        "notes_type_allowed": ["TEXT_FIELD", "TEXTAREA"],
        "all_required": False,
    }

    doc = document("Zgłoszenie uczestników warsztatów")
    doc.add_heading("Uczestnik", 1)
    doc.add_paragraph("Imię i nazwisko: ........................................")
    doc.add_paragraph("Data urodzenia: ........................................")
    doc.add_paragraph("Adres zamieszkania: ........................................")
    doc.add_heading("Opiekun", 1)
    doc.add_paragraph("Imię i nazwisko: ........................................")
    doc.add_paragraph(
        "Telefon (nieobowiązkowo): ........................................"
    )
    doc.add_page_break()
    doc.add_heading("Deklaracja", 1)
    doc.add_paragraph(
        "Oświadczam, że zapoznałem się z regulaminem i przyjmuję jego warunki."
    )
    doc.add_paragraph("Podpis opiekuna: ........................................")
    doc.add_paragraph("Miejscowość i data: ........................................")
    path = root / "roles.docx"
    doc.save(path)
    expected[path.name] = {
        "input_fields": 6,
        "pages": 2,
        "types": {"TEXT_FIELD": 5, "DATEPICKER": 1},
        "repeated_label_roles": ["Uczestnik", "Opiekun"],
        "signature_input": False,
        "declaration_choice": False,
        "all_required": False,
    }
    (root / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2)
    )
    (root / "manifest.json").write_text(
        json.dumps([{"path": str(root / name)} for name in expected])
    )


if __name__ == "__main__":
    create(Path(sys.argv[1]).resolve())
