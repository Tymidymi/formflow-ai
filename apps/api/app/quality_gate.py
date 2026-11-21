"""Heuristic omission warnings for administrative blank forms.

This does not prove semantic quality. It prevents a structurally valid form with
almost no input fields from being labeled an unqualified success.
"""
from __future__ import annotations
import re
import unicodedata

SIGNALS = (
    ("imię i nazwisko", r"imi[eę]\s+i\s+nazwisko|nazwisko", ("imie", "nazwisk")),
    ("adres", r"\badres\b", ("adres", "ulica", "zamieszkania")),
    ("PESEL", r"\bpesel\b", ("pesel",)),
    ("telefon", r"\btelefonu?\b|\btel\.", ("telefon", "kontaktowy", "tel")),
    ("data", r"\bdnia\b|\bdata\b", ("data", "dnia")),
    ("rodzaj zaświadczenia", r"prosz[eę]\s+o\s+wydanie\s+za[sś]wiadczenia\s+o", ("zaswiadczen", "rodzaj")),
    ("cel zaświadczenia", r"potrzebne\s+jest\s+celem|cel\s+(?:wydania|wniosku)", ("cel", "przedlozen", "zaswiadczen")),
    ("NIP", r"\bnip\b", ("nip",)),
    ("REGON", r"\bregon\b", ("regon",)),
    ("kod pocztowy", r"kod\s+pocztowy", ("pocztowy",)),
    ("e-mail", r"e-?mail", ("email", "mail")),
)

def fold(s: str) -> str:
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode("ascii").casefold()

def assess(text: str, semantic: dict) -> dict:
    source=fold(text)
    fields=[
        f for page in semantic.get("pages",[]) if isinstance(page,dict)
        for sec in page.get("sections",[]) if isinstance(sec,dict)
        for f in sec.get("fields",[]) if isinstance(f,dict) and f.get("label")
    ]
    labels=[fold(str(f["label"])) for f in fields]
    signals=[(title, keys) for title, pattern, keys in SIGNALS if re.search(fold(pattern),source)]
    # ^ Basic regex simplification is deliberate: fold(pattern) handles accented
    #    character classes, while the positive signals remain conservative.
    detected=[title for title,keys in signals if any(any(key in lab for key in keys) for lab in labels)]
    missing=[title for title,keys in signals if title not in detected]
    ratio=(len(detected)/len(signals)) if signals else 1.0
    severe=bool(len(signals)>=4 and (len(fields)<3 or ratio<0.45))
    return {"ok":not severe,"input_fields":len(fields),"source_signals":len(signals),
            "matched_signals":len(detected),"signal_coverage":round(ratio,3),
            "possible_missing":missing,
            "note":"Heuristic omissions check; not an authoritative field-coverage benchmark."}
