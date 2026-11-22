import asyncio
from app import page_inventory as pipeline
from app.coi_builder import field_validation


def test_alternative_contact_and_email_synonym():
    assert field_validation("Telefon / adres e-mail", False) == []
    assert field_validation("Adres poczty elektronicznej", False) == ["EMAIL"]


def test_regions_do_not_merge_repeated_labels_on_distinct_rows():
    assert pipeline.overlap([0, 0.1, 1, 0.2], [0, 0.3, 1, 0.4]) == 0
    assert pipeline.region([0, 0, 1, float("nan")]) is None


def test_deterministic_source_coverage_blocks_duplicate_labels(monkeypatch):
    candidate = {
        "title": "Dowolny dokument",
        "pages": [
            {
                "sections": [
                    {
                        "title": "Osoby",
                        "fields": [
                            {
                                "label": "Adres",
                                "type": "TEXT_FIELD",
                                "region": [0.1, 0.1, 0.8, 0.2],
                                "evidence": "Adres",
                            },
                            {
                                "label": "Adres",
                                "type": "TEXT_FIELD",
                                "region": [0.1, 0.3, 0.8, 0.4],
                                "evidence": "Adres",
                            },
                        ],
                    }
                ]
            }
        ],
    }
    calls = []

    async def model(text, images, **kw):
        calls.append(kw["prompt"])
        return candidate, {"usage": {"total_tokens": 7}}

    monkeypatch.setattr(pipeline, "generate", model)
    form, meta, reports = asyncio.run(
        pipeline.extract("[Strona 1/1]\nAdres", [("image/jpeg", b"image")])
    )
    assert len(form["pages"][0]["sections"][0]["fields"]) == 2
    assert len(calls) == 1 and meta["usage"]["total_tokens"] == 7
    assert meta["rechecked_pages"] == 0
    quality = pipeline.assess("[Strona 1/1]\nAdres", form, pages=reports)
    assert not quality["ok"]
    assert any("występuje" in issue for issue in quality["possible_missing"])
    assert len(reports[0]["regions"]) == 2


def test_timeout_cancels_running_conversion(monkeypatch):
    import app.main as api

    stopped = []

    async def convert(*args):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.append(True)

    class Request:
        async def is_disconnected(self):
            return False

    monkeypatch.setattr(api, "_convert_form", convert)
    monkeypatch.setattr(api, "CONVERSION_TIMEOUT_SECONDS", 0.01)
    response = asyncio.run(
        api.convert_form(Request(), None, None, "diagnostic", "auto")
    )
    assert response.status_code == 504 and stopped == [True]


def test_deterministic_rules_correct_a_source_supported_semantic_mismatch(
    monkeypatch,
):
    raw = {
        "title": "Fictional",
        "pages": [
            {
                "title": "Page",
                "sections": [
                    {
                        "title": "Data",
                        "fields": [
                            {
                                "label": "Wybierz dokładnie jeden sposób transportu:",
                                "type": "CHECKBOX",
                                "options": ["samodzielnie", "kurier"],
                                "required": False,
                                "required_evidence": "",
                                "evidence": "Wybierz dokładnie jeden sposób transportu:",
                                "region": [0.1, 0.1, 0.8, 0.2],
                                "row": None,
                                "column": "",
                                "content": "",
                                "source_choice_ref": "transport",
                                "show_when": None,
                            },
                            {
                                "label": "Podpis zgłaszającego:",
                                "type": "TEXT_FIELD",
                                "options": [],
                                "required": False,
                                "required_evidence": "",
                                "evidence": "Podpis zgłaszającego:",
                                "region": [0.1, 0.3, 0.8, 0.4],
                                "row": None,
                                "column": "",
                                "content": "",
                                "source_choice_ref": "",
                                "show_when": None,
                            },
                        ],
                    }
                ],
            }
        ],
    }

    async def fake_model(*args, **kwargs):
        return raw, {}

    monkeypatch.setattr(pipeline, "generate", fake_model)
    source = (
        "[Strona 1/1]\nWybierz dokładnie jeden sposób transportu: "
        "samodzielnie / kurier\nPodpis zgłaszającego: .............."
    )
    form, _, report = asyncio.run(pipeline.extract(source, [("image/jpeg", b"test")]))
    fields = form["pages"][0]["sections"][0]["fields"]
    assert [f["type"] for f in fields] == ["RADIO", "INFO_BLOCK"]
    assert fields[1]["content"] == "Podpis zgłaszającego:"
    assert pipeline.assess(source, form, pages=report)["ok"]


def test_inline_blank_wrongly_marked_info_remains_editable_but_needs_region_review(
    monkeypatch,
):
    raw = {
        "title": "Fictional",
        "pages": [
            {
                "title": "Page",
                "sections": [
                    {
                        "title": "Data",
                        "fields": [
                            {
                                "label": "Miejsce i data:",
                                "type": "INFO_BLOCK",
                                "evidence": "Miejsce i data:",
                                "content": "Miejsce i data:",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    async def fake_model(*args, **kwargs):
        return raw, {}

    monkeypatch.setattr(pipeline, "generate", fake_model)
    source = "[Strona 1/1]\nMiejsce i data: ......................"
    form, _, report = asyncio.run(pipeline.extract(source, [("image/jpeg", b"test")]))
    assert form["pages"][0]["sections"][0]["fields"][0]["type"] == "TEXT_FIELD"
    assert not pipeline.assess(source, form, pages=report)["ok"]


def test_two_physical_pages_run_concurrently_but_keep_original_order(monkeypatch):
    import time

    active = 0
    peak = 0
    calls = []

    async def fake_model(text, images, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.025)
            marker = "first" if "A-source" in text else "second"
            calls.append(marker)
            response = {
                "title": marker,
                "pages": [
                    {
                        "title": marker,
                        "sections": [
                            {
                                "title": marker,
                                "fields": [
                                    {
                                        "label": marker,
                                        "type": "INFO_BLOCK",
                                        "content": marker,
                                        "evidence": marker,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            return response, {"usage": {"total_tokens": 1}}
        finally:
            active -= 1

    monkeypatch.setattr(pipeline, "generate", fake_model)
    started = time.monotonic()
    form, meta, reports = asyncio.run(
        pipeline.extract(
            "[Strona 1/2]\nA-source\n[Strona 2/2]\nB-source",
            [("image/jpeg", b"p1"), ("image/jpeg", b"p2")],
            image_page_numbers=[1, 2],
            pages_expected=2,
        )
    )
    elapsed = time.monotonic() - started
    assert peak == 2
    assert [p["title"] for p in form["pages"]] == ["Strona 1", "Strona 2"]
    assert [p["source_page"] for p in reports] == [1, 2]
    assert meta["usage"]["total_tokens"] == 2
    assert meta["rechecked_pages"] == 0
    assert calls.count("first") == 1 and calls.count("second") == 1


def test_page_with_printed_answer_blanks_cannot_pass_with_zero_fields():
    semantic = {
        "title": "Fictional",
        "pages": [
            {
                "title": "Page 1",
                "sections": [
                    {
                        "title": "Applicant",
                        "fields": [{"type": "TEXT_FIELD", "label": "Name"}],
                    }
                ],
            },
            {"title": "Page 2", "sections": []},
        ],
    }
    reports = [
        {"source_page": 1, "blank_slots": 1, "detected_fields": 1, "audit_issues": []},
        {"source_page": 2, "blank_slots": 1, "detected_fields": 0, "audit_issues": []},
    ]
    result = pipeline.assess("", semantic, pages=reports, pages_expected=2)
    assert not result["ok"]
    assert any("Strona 2" in issue for issue in result["possible_missing"])


def test_repeated_model_fields_without_repeated_source_labels_require_review():
    semantic = {
        "title": "Fictional",
        "pages": [
            {
                "title": "Page 1",
                "sections": [
                    {
                        "title": "Data",
                        "fields": [
                            {
                                "label": "Statement",
                                "type": "TEXT_FIELD",
                                "source_page": 1,
                            },
                            {
                                "label": "Statement",
                                "type": "TEXT_FIELD",
                                "source_page": 1,
                            },
                        ],
                    }
                ],
            }
        ],
    }
    result = pipeline.assess(
        "[Strona 1/1]\nStatement\nI confirm the details.",
        semantic,
        pages=[
            {
                "source_page": 1,
                "detected_fields": 2,
                "blank_slots": 0,
                "audit_issues": [],
            }
        ],
    )
    assert not result["ok"]
    assert any("2 razy" in issue for issue in result["possible_missing"])


def test_repeated_labels_with_multiple_source_occurrences_are_not_rejected():
    semantic = {
        "title": "Fictional",
        "pages": [
            {
                "title": "Page",
                "sections": [
                    {
                        "title": "Data",
                        "fields": [
                            {"label": "Name", "type": "TEXT_FIELD", "source_page": 1},
                            {"label": "Name", "type": "TEXT_FIELD", "source_page": 1},
                        ],
                    }
                ],
            }
        ],
    }
    result = pipeline.assess(
        "[Strona 1/1]\nName ____\nGuardian\nName ____",
        semantic,
        pages=[
            {
                "source_page": 1,
                "detected_fields": 2,
                "blank_slots": 2,
                "audit_issues": [],
            }
        ],
    )
    assert result["ok"]
