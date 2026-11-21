"""Canonical intermediate contract: unrelated forms, source-first and no repairs."""
from __future__ import annotations

import copy
import pytest
from pydantic import ValidationError

from app.canonical_form import CanonicalForm, canonicalize
from app.coi_builder import convert


def sample():
    return {"title":"Formularz ogólny","pages":[{"title":"Strona 1",
      "sections":[{"title":"Dane","fields":[
        {"label":"Identyfikator","type":"TEXT_FIELD","required":False,
         "evidence":"Identyfikator .............","source_page":1,"source_line":2},
        {"label":"Rodzaj zgłoszenia","type":"CHECKBOX","options":["A","B"],
         "source_choice_ref":"choice_1_2","source_page":1},
        {"label":"Numer dla A","type":"TEXT_FIELD",
         "show_when":{"field_ref":"choice_1_2","value":"A"},
         "source_page":1,"source":"visual_choice_detail"},
        {"label":"Wartość wiersz 1","type":"NUMBER","row":1,
         "column":"Wartość","source_line":4},
        {"label":"Informacja","type":"INFO_BLOCK","content":"Zasady są informacyjne."}
      ]}]}]}


def test_contract_preserves_source_and_controls_without_inventing_fields():
    original=sample()
    expected=copy.deepcopy(original)
    model=CanonicalForm.model_validate(original)
    assert len(model.pages[0].sections[0].fields)==5
    assert canonicalize(original)==expected
    output,valid=convert(original)
    assert valid["valid"],valid
    assert valid["summary"]["input_fields"]==4
    rows=[cell["field"] for section in output["tabs"][0]["questions"]
          for cell in section["field"]["repeatingSectionGrid"]]
    assert [row["title"] for row in rows]==[f["label"] for f in expected["pages"][0]["sections"][0]["fields"]]
    assert rows[2]["states"] and rows[2]["states"][0]["type"]=="SHOW"


@pytest.mark.parametrize("mutate",[
    lambda x:x["pages"][0]["sections"][0]["fields"][0].update({"type":"UNSUPPORTED"}),
    lambda x:x["pages"][0]["sections"][0]["fields"][0].update({"required":"yes"}),
    lambda x:x["pages"][0]["sections"][0]["fields"][0].update({"source_page":0}),
    lambda x:x["pages"][0]["sections"][0]["fields"][3].update({"column":None}),
    lambda x:x["pages"][0]["sections"][0]["fields"][2].update({"show_when":{"value":"A"}}),
    lambda x:x["pages"][0]["sections"][0]["fields"][1].update({"options":[""]}),
    lambda x:x["pages"][0]["sections"][0]["fields"][0].update({"invented":"not sourced"}),
])
def test_invalid_intermediate_contract_fails_closed(mutate):
    data=sample()
    mutate(data)
    with pytest.raises(ValidationError):
        canonicalize(data)


def test_no_model_autofill_for_missing_unsupported_attributes():
    data={"title":"Rejestr","pages":[{"title":"Jedna","sections":[{"title":"Dane",
          "fields":[{"label":"Opis","type":"TEXTAREA"}]}]}]}
    assert canonicalize(data)==data


def test_does_not_normalize_similar_printed_labels_or_merge_distinct_cells():
    data={"title":"Ankieta","pages":[{"title":"Dane","sections":[{"title":"Wyposażenie",
      "fields":[{"label":"Liczba","type":"NUMBER","row":1,"column":"Liczba"},
                {"label":"Liczba","type":"NUMBER","row":2,"column":"Liczba"}]}]}]}
    assert len(CanonicalForm.model_validate(data).pages[0].sections[0].fields)==2
    output,valid=convert(data)
    assert valid["valid"]
    assert valid["summary"]["input_fields"]==2