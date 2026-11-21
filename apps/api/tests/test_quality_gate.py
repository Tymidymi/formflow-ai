"""Document-general quality gate: detect omissions without vocabulary exceptions."""
from app.quality_gate import assess

def form(n):
    return {"title":"Test","pages":[{"sections":[{"fields":[
        {"label":f"Wartość {i}","type":"TEXT_FIELD"} for i in range(n)
    ]}]}]}

def source_slots(n):
    return "\\n".join(f"Pozycja {i}: ................................" for i in range(n))

def test_major_omission_prevents_false_success():
    result=assess(source_slots(28),form(3))
    assert result["ok"] is False
    assert result["source_blank_slots"]==28
    assert result["blank_coverage_ratio"]<0.2

def test_complete_form_passes_and_incomplete_source_fails():
    result=assess(source_slots(12),form(12))
    assert result["ok"] is True
    assert result["blank_coverage_ratio"]==1.0
    assert assess(source_slots(12),form(12),truncated=True)["ok"] is False

def test_arbitrary_no_placeholder_form_does_not_invent_requirements():
    result=assess("Opis zgłoszenia (odpowiedz poniżej)",form(1))
    assert result["ok"] is True
    assert result["source_blank_slots"]==0
