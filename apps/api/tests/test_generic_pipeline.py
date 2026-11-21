"""Document-independent extraction: no hardcoded corrections for COI examples."""

import asyncio
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app


def test_api_reports_missing_generic_table_without_fabricating_rows(monkeypatch):
    import app.main as api
    from app import page_inventory

    monkeypatch.setenv("FORMFLOW_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic")

    async def extraction(*args, **kw):
        return (
            "[Strona 1/1]\nNazwisko _____",
            [("image/jpeg", b"image")],
            {"pages": 1, "vision_page_numbers": [1]},
        )

    count = []

    async def model(*args, **kw):
        count.append(True)
        if len(count) == 2:
            return {
                "title": "Dowolny wniosek",
                "pages": [
                    {
                        "sections": [
                            {
                                "title": "Dane",
                                "fields": [
                                    {
                                        "label": "Nazwisko",
                                        "type": "TEXT_FIELD",
                                        "evidence": "Nazwisko",
                                        "region": [0, 0.1, 1, 0.2],
                                    }
                                ],
                            }
                        ]
                    }
                ],
                "audit": {"issues": ["Brakuje wierszy tabeli."], "changes": []},
            }, {}
        return {
            "title": "Dowolny wniosek",
            "pages": [
                {
                    "sections": [
                        {
                            "title": "Dane",
                            "fields": [
                                {
                                    "label": "Nazwisko",
                                    "type": "TEXT_FIELD",
                                    "evidence": "Nazwisko",
                                    "region": [0, 0.1, 1, 0.2],
                                }
                            ],
                        }
                    ]
                }
            ],
        }, {}

    monkeypatch.setattr(api, "extract_with_backend", extraction)
    monkeypatch.setattr(page_inventory, "generate", model)
    response = TestClient(app).post(
        "/api/v1/forms/convert?mode=diagnostic",
        headers={"X-External-AI-Consent": "true"},
        files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_review" and not data["quality"]["ok"]
    assert data["quality"]["input_fields"] == 1
    assert len(count) == 2


def test_exported_table_retains_source_row_and_column_grid():
    from app.coi_builder import convert

    cells = [
        {"label": f"Wiersz {row} {col}", "type": "NUMBER", "row": row, "column": col}
        for row in (1, 2)
        for col in ("A", "B", "C")
    ]
    semantic = {
        "title": "Dowolna tabela",
        "pages": [
            {
                "title": "Pomiary",
                "sections": [{"title": "Wartości", "fields": cells[:6]}],
            }
        ],
    }
    output, validation = convert(semantic)
    assert validation["valid"] and validation["schema_valid"], validation
    grid = output["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    assert len(grid) == 6
    assert [(x["x"], x["y"], x["cols"]) for x in grid] == [
        (0, 0, 1),
        (1, 0, 1),
        (2, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
        (2, 1, 1),
    ]
