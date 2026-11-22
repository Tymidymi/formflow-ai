"""Typed paper-form semantics, checked without referencing any audit file."""

from app.source_semantics import (
    normalize_observed_field,
    match_source_option,
    reconcile_conditions,
    preserve_static_source,
)


def test_ink_signature_is_read_only_instead_of_a_web_text_input():
    source = "Name ........\nPodpis przedstawiciela: ........"
    raw = {
        "label": "Podpis przedstawiciela:",
        "type": "TEXT_FIELD",
        "evidence": "Podpis przedstawiciela:",
        "required": False,
        "region": [0.1, 0.2, 0.8, 0.3],
    }
    converted, note = normalize_observed_field(raw, source)
    assert converted["type"] == "INFO_BLOCK"
    assert converted["content"] == "Podpis przedstawiciela:"
    assert note
    assert raw["type"] == "TEXT_FIELD"


def test_single_option_instruction_overrides_checkbox_label():
    raw = {
        "label": "Wybierz dokładnie jeden sposób dostarczenia:",
        "type": "CHECKBOX",
        "options": ["odbiór", "kurier"],
    }
    result, note = normalize_observed_field(raw, raw["label"])
    assert result["type"] == "RADIO"
    assert note


def test_multi_option_instruction_overrides_radio_label():
    raw = {
        "label": "Można zaznaczyć kilka umiejętności:",
        "type": "RADIO",
        "options": ["język", "programowanie"],
    }
    result, note = normalize_observed_field(raw, raw["label"])
    assert result["type"] == "CHECKBOX"
    assert note


def test_no_source_evidence_no_automatic_change():
    raw = {
        "label": "Wybierz dokładnie jeden sposób dostarczenia:",
        "type": "CHECKBOX",
        "options": ["odbiór", "kurier"],
    }
    result, note = normalize_observed_field(
        raw, "Source does not contain this instruction"
    )
    assert result == raw
    assert note is None


def test_ambiguous_or_mixed_cardinality_is_not_guessed():
    raw = {
        "label": "Wybierz dokładnie jeden lub można zaznaczyć kilka",
        "type": "CHECKBOX",
        "options": ["a", "b"],
    }
    result, note = normalize_observed_field(raw, raw["label"])
    assert result == raw
    assert note is None


def test_inline_answer_blank_cannot_remain_a_static_block():
    source = "Room allocation: ............................................\nPolicy: keep this document."
    raw = {
        "label": "Room allocation:",
        "type": "INFO_BLOCK",
        "content": "Room allocation:",
        "evidence": "Room allocation:",
    }
    converted, note = normalize_observed_field(raw, source)
    assert converted["type"] == "TEXT_FIELD"
    assert converted["region"] is None  # no fabricated coordinates
    assert note
    static, note = normalize_observed_field(
        {"label": "Policy:", "type": "INFO_BLOCK", "content": "keep this document"},
        source,
    )
    assert static["type"] == "INFO_BLOCK" and note is None


def test_signature_with_blank_remains_readonly():
    raw = {
        "label": "Podpis opiekuna:",
        "type": "INFO_BLOCK",
        "content": "Podpis opiekuna:",
    }
    result, _ = normalize_observed_field(raw, "Podpis opiekuna: ....................")
    assert result["type"] == "INFO_BLOCK"


def test_condition_uses_canonical_existing_choice_spelling():
    options = ["collection", "delivery"]
    assert match_source_option("DeliverY", options) == "delivery"
    assert match_source_option("delivry", options) == "delivery"
    assert match_source_option("another unrelated option", options) is None
    sections = [
        {
            "title": "Section",
            "fields": [
                {
                    "label": "Method",
                    "type": "RADIO",
                    "source_choice_ref": "r",
                    "options": options,
                },
                {
                    "label": "Address",
                    "type": "TEXT_FIELD",
                    "show_when": {"field_ref": "r", "value": "delivry"},
                },
            ],
        }
    ]
    changes = reconcile_conditions(sections)
    assert changes
    assert sections[0]["fields"][1]["show_when"]["value"] == "delivery"


def test_condition_spelling_never_changes_when_choice_is_ambiguous():
    assert match_source_option("abc", ["abca", "abcb"]) is None


def test_ocr_source_typo_is_preserved_without_model_proofreading():
    source = "[Strona 1/1]\nInformation: this document is used only for the application. Keep keep this document."
    raw = {
        "type": "INFO_BLOCK",
        "label": "Information",
        "content": "Information: this document is used only for the application. Keep this document.",
    }
    corrected, note = preserve_static_source(raw, source)
    assert corrected["content"].endswith("Keep keep this document.")
    assert note
    assert raw["content"].endswith("Keep this document.")


def test_unrelated_static_source_is_not_substituted():
    source = "Rules and instructions for a completely different form."
    raw = {
        "type": "INFO_BLOCK",
        "label": "Privacy",
        "content": "Notice about processing personal information for the applicant.",
    }
    corrected, note = preserve_static_source(raw, source)
    assert corrected == raw and note is None
