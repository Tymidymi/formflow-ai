"""Numbered headings in source are separate COI sections, not extra pages."""
from app.source_sections import recover_numbered_sections, source_subsections


def field(label):
    return {"label": label, "type": "TEXT_FIELD", "required": False}


def test_collapsed_numbered_subsections_split_without_dropping_fields():
    source = """2. Dane wnioskodawcy
    2.1. Dane identyfikacyjne
    Nazwa /Imię i nazwisko
    NIP
    2.2. Adres siedziby lub miejsca zamieszkania
    Miejscowość
    Ulica
    Nr domu         Nr lokalu        Kod pocztowy
    2.3. Dane kontaktowe (podanie danych jest dobrowolne, ale
    Numer telefonu
    Adres poczty elektronicznej
    2.4. Dane pełnomocnika
    Imię i nazwisko
    Miejscowość
    Ulica
    Nr domu         Nr lokalu        Kod pocztowy
    """
    labels = [
        "Nazwa /Imię i nazwisko", "NIP",
        "Miejscowość", "Ulica", "Nr domu", "Nr lokalu", "Kod pocztowy",
        "Numer telefonu", "Adres poczty elektronicznej",
        "Imię i nazwisko", "Miejscowość", "Ulica", "Nr domu",
        "Nr lokalu", "Kod pocztowy",
    ]
    fields = [field(value) for value in labels]
    result, changes = recover_numbered_sections(
        source, [{"title": "2. Dane wnioskodawcy", "fields": fields}]
    )
    assert [len(section["fields"]) for section in result] == [2, 5, 2, 6]
    assert [section["title"].split()[0] for section in result] == [
        "2.1.", "2.2.", "2.3.", "2.4."
    ]
    assert [f for section in result for f in section["fields"]] == fields
    assert len(changes) == 1


def test_does_not_split_numbers_in_lists_or_overwrite_existing_sections():
    source = """2. Dane wnioskodawcy
      2.1. Dane podstawowe
      Nazwisko
      2.2. Adres korespondencyjny
      Ulica
    """
    groups = [
        {"title": "Dane", "fields": [field("Nazwisko")]},
        {"title": "Adres", "fields": [field("Ulica")]},
    ]
    assert recover_numbered_sections(source, groups) == (groups, [])
    assert source_subsections("1. Jedna opcja\n2. Druga opcja\n") == []


def test_no_split_if_source_positions_cannot_ground_multiple_groups():
    source = """3.1. Dane identyfikacyjne
    Nazwisko
    3.2. Adres
    Ulica
    """
    original = [{"title": "Dane", "fields": [field("Nieznane"), field("Nazwisko")]}]
    assert recover_numbered_sections(source, original) == (original, [])


def test_splits_only_applicant_chapter_when_instructions_are_already_separate():
    source = """1. Instrukcja wypełnienia
Wypełnij druk zgodnie z instrukcją.
2. Dane wnioskodawcy
2.1. Dane identyfikacyjne
Imię i nazwisko
NIP
2.2. Dane kontaktowe
Adres
Telefon
"""
    original = [
        {"title": "1. Instrukcja wypełnienia", "fields": [
            {"label": "Instrukcja", "type": "INFO_BLOCK"}
        ]},
        {"title": "2. Dane wnioskodawcy", "fields": [
            field("Imię i nazwisko"), field("NIP"), field("Adres"), field("Telefon")
        ]},
    ]
    result, changes = recover_numbered_sections(source, original)
    assert len(changes) == 1
    assert result[0] == original[0]
    assert [(x["title"], len(x["fields"])) for x in result[1:]] == [
        ("2.1. Dane identyfikacyjne", 2),
        ("2.2. Dane kontaktowe", 2),
    ]
