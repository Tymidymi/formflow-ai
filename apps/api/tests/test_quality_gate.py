"""Heuristic completeness gate: a valid schema may still omit source inputs."""
from app.quality_gate import assess

SOURCE = """Młynary, dnia ... Imię i nazwisko ... Adres ... PESEL ...
Nr telefonu ... Proszę o wydanie zaświadczenia o: ... Zaświadczenie potrzebne jest celem ..."""

def test_rejects_schema_valid_but_semantically_empty_result():
    weak={"pages":[{"sections":[{"fields":[{"label":"Podpis","type":"TEXT_FIELD"}]}]}]}
    result=assess(SOURCE,weak)
    assert result["ok"] is False
    assert result["source_signals"]>=6
    assert result["signal_coverage"]<.45
    assert "PESEL" in result["possible_missing"]

def test_good_result_passes():
    good={"pages":[{"sections":[{"fields":[
        {"label":"Data wniosku"},{"label":"Imię i nazwisko"},{"label":"Adres"},
        {"label":"Numer PESEL"},{"label":"Telefon"},{"label":"Rodzaj zaświadczenia"},
        {"label":"Cel przedłożenia zaświadczenia"}]}]}]}
    result=assess(SOURCE,good)
    assert result["ok"] is True, result
    assert result["signal_coverage"]>=.70

def test_no_text_has_no_false_omission_claims():
    result=assess("",{"pages":[{"sections":[{"fields":[{"label":"Adres"}]}]}]})
    assert result["ok"] is True
    assert result["source_signals"]==0
