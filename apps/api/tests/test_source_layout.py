"""Repeated table cells retain their 2D geometry in COI exports."""

from app.source_layout import layout_for_fields
from app.coi_builder import convert


def test_repeated_columns_form_rows_not_a_vertical_list():
    fields = [{"label": "Applicant", "type": "TEXT_FIELD"}]
    for _ in range(3):
        fields.extend(
            {"label": label, "type": kind}
            for label, kind in (
                ("Asset ID", "TEXT_FIELD"),
                ("Quantity", "NUMBER"),
                ("Start", "DATEPICKER"),
            )
        )
    # Evidence-backed cell locations, not just repeated labels.
    for i in range(1, 10):
        row, col = divmod(i - 1, 3)
        fields[i]["region"] = [
            0.1 + col * 0.25,
            0.2 + row * 0.06,
            0.28 + col * 0.25,
            0.24 + row * 0.06,
        ]
    fields.append({"label": "Notes", "type": "TEXTAREA"})
    layout = layout_for_fields(fields)
    assert layout[0] == {"x": 0, "y": 0, "cols": 3}
    assert layout[1:4] == [
        {"x": 0, "y": 1, "cols": 1},
        {"x": 1, "y": 1, "cols": 1},
        {"x": 2, "y": 1, "cols": 1},
    ]
    assert layout[7:10] == [
        {"x": 0, "y": 3, "cols": 1},
        {"x": 1, "y": 3, "cols": 1},
        {"x": 2, "y": 3, "cols": 1},
    ]
    assert layout[10] == {"x": 0, "y": 4, "cols": 3}

    semantic = {
        "title": "Inventory",
        "pages": [
            {"title": "Page", "sections": [{"title": "Items", "fields": fields}]}
        ],
    }
    coi, validation = convert(semantic)
    assert validation["valid"]
    cells = coi["tabs"][0]["questions"][0]["field"]["repeatingSectionGrid"]
    assert [(x["x"], x["y"], x["cols"]) for x in cells] == [
        (x["x"], x["y"], x["cols"]) for x in layout
    ]


def test_nonconsecutive_or_nonunique_labels_do_not_make_a_table():
    fields = [
        {"label": "Person", "type": "TEXT_FIELD"},
        {"label": "Phone", "type": "TEXT_FIELD"},
        {"label": "Different information", "type": "TEXT_FIELD"},
        {"label": "Person", "type": "TEXT_FIELD"},
        {"label": "Phone", "type": "TEXT_FIELD"},
    ]
    assert all(x["cols"] == 3 for x in layout_for_fields(fields))


def test_repeated_vertical_blocks_do_not_become_a_grid_without_geometry():
    fields = [
        {
            "label": label,
            "type": "TEXT_FIELD",
            "region": [0.1, i * 0.1, 0.6, i * 0.1 + 0.04],
        }
        for i, label in enumerate(["Name", "Phone", "Name", "Phone"])
    ]
    assert all(item["cols"] == 3 for item in layout_for_fields(fields))
