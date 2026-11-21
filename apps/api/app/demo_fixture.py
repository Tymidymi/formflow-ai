"""Fully synthetic COI eService fixture for safe, API-free demos."""
from .coi_builder import convert


def sample():
    return {
        "title": "Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej — DEMO",
        "pages": [
            {
                "title": "Dane wnioskodawcy",
                "sections": [
                    {
                        "title": "Dane kontaktowe",
                        "fields": [
                            {"label": "Imię i nazwisko", "type": "TEXT_FIELD", "required": True, "options": []},
                            {"label": "PESEL", "type": "TEXT_FIELD", "required": True, "options": []},
                            {"label": "Adres zamieszkania", "type": "TEXT_FIELD", "required": True, "options": []},
                            {"label": "Adres e-mail", "type": "TEXT_FIELD", "required": False, "options": []},
                            {"label": "Numer telefonu", "type": "TEXT_FIELD", "required": False, "options": []},
                        ],
                    },
                    {
                        "title": "Odpowiedzialność za wydarzenie",
                        "fields": [
                            {"label":"Kto jest osobą odpowiedzialną?","type":"RADIO",
                             "required":False,"options":["Wnioskodawca","Inna osoba"]},
                            {"label":"Osoba odpowiedzialna (pełnoletnia) za utrzymanie porządku",
                             "type":"TEXT_FIELD","required":False,"options":[],
                             "show_when":{"field":"kto_jest_osoba_odpowiedzialna",
                                          "value":"Inna osoba"}},
                            {"label":"Oświadczenie osoby odpowiedzialnej",
                             "type":"FILE_UPLOADER","required":False,"options":[],
                             "show_when":{"field":"kto_jest_osoba_odpowiedzialna",
                                          "value":"Inna osoba"}},
                        ],
                    },
                ],
            },
            {
                "title": "Dane wydarzenia",
                "sections": [
                    {
                        "title": "Rezerwacja świetlicy",
                        "fields": [
                            {"label": "Miejscowość świetlicy", "type": "TEXT_FIELD", "required": True, "options": []},
                            {"label": "Forma udostępnienia świetlicy", "type": "RADIO",
                             "required": True, "options": ["Wynajem", "Użyczenie"]},
                            {"label": "Data rozpoczęcia wynajmu", "type": "DATEPICKER", "required": True, "options": []},
                            {"label": "Data zakończenia wynajmu", "type": "DATEPICKER", "required": True, "options": []},
                            {"label": "Liczba uczestników", "type": "NUMBER", "required": True, "options": []},
                            {"label": "Cel wynajęcia świetlicy", "type": "TEXTAREA", "required": True, "options": []},
                            {"label": "Zapoznałem się z warunkami wynajmu", "type": "CHECKBOX",
                             "required": True, "options": []},
                        ],
                    },
                ],
            },
        ],
    }

def create_demo():
    # Conditional fields exist only as explicit synthetic fixture data.
    # They are NEVER inferred from a user's document by a fixed rule.
    form, validation = convert(sample())
    return {
        "status": "demo",
        "provider": "synthetic-local-fixture",
        "form": form,
        "validation": validation,
        "quality": {"ok": True, "note": "To syntetyczny formularz demonstracyjny, nie wynik AI."},
        "normalization": [],
        "warning": "Przykładowy formularz DEMO z fikcyjnymi polami. Bez wysyłki danych do OpenRouter.",
        "source": "synthetic",
    }
