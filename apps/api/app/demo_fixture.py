"""Fully synthetic COI eService fixture for safe, API-free demos."""
from .coi_builder import convert
from .conditional_rules import apply_conditions

DEMO_SOURCE = (
    "Wniosek o wynajęcie/użyczenie świetlicy wiejskiej. "
    "Osoba odpowiedzialna za utrzymanie porządku i bezpieczeństwo. "
    "W przypadku innej osoby niż wnioskodawca zbiorcze oświadczenie "
    "tej osoby załączyć do wniosku."
)

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
                            {
                                "label": "Osoba odpowiedzialna (pełnoletnia) za utrzymanie porządku",
                                "type": "TEXT_FIELD", "required": False, "options": [],
                            },
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
    semantic, changes = apply_conditions(DEMO_SOURCE, sample())
    form, validation = convert(semantic)
    return {
        "status": "demo",
        "provider": "synthetic-local-fixture",
        "form": form,
        "validation": validation,
        "quality": {"ok": True, "note": "To syntetyczny formularz demonstracyjny, nie wynik AI."},
        "normalization": changes,
        "warning": "Przykładowy formularz DEMO z fikcyjnymi polami. Bez wysyłki danych do OpenRouter.",
        "source": "synthetic",
    }
