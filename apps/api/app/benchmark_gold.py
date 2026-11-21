"""Manually curated field inventory from supplied COI #3/#4 blank PDF forms.

Each inventory item describes one semantic input or choice; alternative labels
are accepted, and paper-only ink signatures are deliberately excluded.
This is a narrow evaluation fixture, NOT a general scorer or official COI gold.
"""
from __future__ import annotations
import unicodedata

def fold(value: str) -> str:
    return unicodedata.normalize("NFKD",value.translate(str.maketrans("Łł", "Ll"))).encode("ascii","ignore").decode("ascii").casefold()

# (description, alternative source-grounded match substrings, acceptable COI types)
GOLD = {
    3: [
        ("Data złożenia", ["data zlozenia", "dnia", "data wniosku"], {"DATEPICKER"}),
        ("Imię i nazwisko", ["imie i nazwisko", "nazwisko"], {"TEXT_FIELD"}),
        ("Adres wnioskodawcy", ["adres"], {"TEXT_FIELD","TEXTAREA"}),
        ("PESEL", ["pesel"], {"TEXT_FIELD"}),
        ("Telefon", ["telefon"], {"TEXT_FIELD"}),
        ("Posiadane użytki", ["ilosc posiadanych uzytkow"], {"CHECKBOX","RADIO"}),
        ("Dzierżawione użytki", ["ilosc dzierzawionych uzytkow"], {"CHECKBOX","RADIO"}),
        ("Okres gospodarstwa", ["okresie posiadania gospodarstwa","okres posiadania gospodarstwa"], {"CHECKBOX","RADIO"}),
        ("Nieposiadanie", ["nieposiadaniu uzytkow","nieposiadanie uzytkow"], {"CHECKBOX","RADIO"}),
        ("Inny rodzaj", ["inne"], {"TEXT_FIELD","CHECKBOX","RADIO"}),
        ("Cel zaświadczenia", ["celem przedlozenia","cel wydania","cel zaswiadczenia"], {"TEXTAREA","TEXT_FIELD"}),
    ],
    4: [
        ("Miejscowość wnioskodawcy", ["miejscowosc","ploskinia"], {"TEXT_FIELD"}),
        ("Data wniosku", ["data wniosku", "data zlozenia"], {"DATEPICKER"}),
        ("Imię i nazwisko", ["imie i nazwisko wnioskodawcy","nazwisko"], {"TEXT_FIELD"}),
        ("Adres", ["adres zamieszkania"], {"TEXT_FIELD"}),
        ("Telefon", ["nr telefonu","numer telefonu"], {"TEXT_FIELD"}),
        ("Forma udostępnienia", ["forma udostepnienia","wynajem/uzyczenie","wynajecie/uzyczenie"], {"RADIO","SELECT"}),
        ("Miejsce świetlicy", ["swietlicy w","swietlica w","swietlicy wiejskiej w"], {"TEXT_FIELD","SELECT"}),
        ("Termin od", ["terminie od","data rozpoczecia","data od","wynajmu od"], {"DATEPICKER"}),
        ("Termin do", ["data zakonczenia","data do","termin do","do"], {"DATEPICKER"}),
        ("Cel wynajęcia", ["cel wynajecia"], {"TEXT_FIELD","TEXTAREA"}),
        ("Liczba uczestników", ["ilosc uczestnikow","liczba uczestnikow"], {"NUMBER"}),
        ("Osoba odpowiedzialna", ["osoba odpowiedzialna (","imie i nazwisko osoby odpowiedzialnej"], {"TEXT_FIELD"}),
        ("Wybór odpowiedzialnego", ["kto jest osoba odpowiedzialna"], {"RADIO"}),
        ("Oświadczenie osoby innej", ["oswiadczenie osoby odpowiedzialnej"], {"FILE_UPLOADER"}),
        ("Potwierdzenie znajomości warunków", ["zapoznalem/am sie z warunkami","zapoznal"], {"CHECKBOX"}),
        ("Odpowiedzialność za porządek", ["czasie najmu odpowiadam"], {"CHECKBOX"}),
        ("Przepisy sanitarne/BHP", ["przestrzegania przepisow sanitarnych","przestrzegania przepisow"], {"CHECKBOX"}),
        ("Odpowiedzialność za mienie", ["odpowiedzialnosc za powierzone mienie"], {"CHECKBOX"}),
    ],
}

def score(case: int, fields: list[dict]) -> dict:
    items = GOLD[case]
    hits = []
    matched_indices = set()
    for description, aliases, types in items:
        candidates = [i for i, field in enumerate(fields)
                      if any(part in fold(str(field.get("label",""))) for part in aliases)]
        # Prefer type match over merely matching text.
        best = next((i for i in candidates if fields[i].get("type") in types),
                    candidates[0] if candidates else None)
        if best is not None:
            matched_indices.add(best)
        actual = fields[best].get("type") if best is not None else None
        hits.append({"expected":description, "found":best is not None,
                     "type_correct":actual in types if best is not None else False,
                     "actual_type":actual,
                     "matched_label":fields[best].get("label") if best is not None else None})
    found = sum(x["found"] for x in hits)
    typed = sum(x["type_correct"] for x in hits)
    return {
        "case":case,"expected":len(items),"labels_matched":found,
        "labels_recall":round(found/len(items),3),
        "type_correct":typed,"type_recall":round(typed/len(items),3),
        "unmatched_output_fields":len(fields)-len(matched_indices),
        "items":hits,
        "note":"Manual proxy against one reference source; not COI-verified ground truth or precision.",
    }
