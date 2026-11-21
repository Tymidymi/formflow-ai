"""Source-agnostic checks for incomplete and inconsistent generated controls."""

from app.page_inventory import source_consistency_issues


def form(*fields):
    return {"pages": [{"sections": [{"fields": list(fields)}]}]}


def test_slash_strike_requires_an_actual_two_option_choice():
    source = "Select delivery/collection* for the fictional equipment; * strike one."
    missing = form({"type": "TEXT_FIELD", "label": "delivery/collection"})
    assert "wybór przez skreślenie" in " ".join(
        source_consistency_issues(source, missing)
    )
    valid = form(
        {
            "type": "RADIO",
            "label": "Transport",
            "options": ["delivery", "collection"],
            "source_choice_ref": "choice_1",
        }
    )
    assert source_consistency_issues(source, valid) == []


def test_conditions_must_reference_actual_choice_and_option():
    form_with_missing_ref = form(
        {
            "type": "TEXT_FIELD",
            "label": "Address",
            "show_when": {"field_ref": "none", "value": "x"},
        }
    )
    assert "Warunek bez" in " ".join(
        source_consistency_issues("", form_with_missing_ref)
    )

    form_with_bad_option = form(
        {
            "type": "RADIO",
            "label": "Mode",
            "options": ["delivery"],
            "source_choice_ref": "a",
        },
        {
            "type": "TEXT_FIELD",
            "label": "Address",
            "show_when": {"field_ref": "a", "value": "collection"},
        },
    )
    assert "nieistniejącą opcją" in " ".join(
        source_consistency_issues("", form_with_bad_option)
    )


def test_info_block_without_contents_and_choice_without_options_are_detected():
    broken = form(
        {"type": "INFO_BLOCK", "label": "Notice", "content": ""},
        {"type": "RADIO", "label": "Select", "options": []},
    )
    issues = source_consistency_issues("", broken)
    assert len(issues) == 2


def test_signature_instruction_must_survive_as_static_information():
    source = "Wnioskodawca: ................................... /podpis/"
    missing = form({"type": "TEXT_FIELD", "label": "Wnioskodawca"})
    assert "instrukcję podpisu" in " ".join(source_consistency_issues(source, missing))
    wrong_type = form({"type": "TEXT_FIELD", "label": "Podpis"})
    assert "instrukcję podpisu" in " ".join(source_consistency_issues(source, wrong_type))
    valid = form({"type": "INFO_BLOCK", "label": "Podpis", "content": "Miejsce na podpis"})
    assert source_consistency_issues(source, valid) == []
