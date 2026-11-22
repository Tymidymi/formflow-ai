"""Infer COI grid positions for *obviously* repeated tabular answer groups.

Only consecutive repeated sequences of 2-3 distinct source field captions
qualify. Other content keeps its original order and full-width layout. This
does not invent fields, change labels, or collapse repeated input instances.
"""

import re
import unicodedata

INPUTS = {
    "TEXT_FIELD",
    "TEXTAREA",
    "DATEPICKER",
    "NUMBER",
    "RADIO",
    "CHECKBOX",
    "SELECT",
    "FILE_UPLOADER",
}


def _caption(field):
    label = unicodedata.normalize("NFKC", str(field.get("label") or "")).casefold()
    return re.sub(r"\s+", " ", label).strip(" :.")


def _matrix_geometry(fields, columns):
    """A repeated caption sequence alone does not establish tabular layout."""
    if len(fields) < columns * 2 or len(fields) % columns:
        return False
    boxes = [field.get("region") for field in fields]
    if any(
        not isinstance(box, list)
        or len(box) != 4
        or any(not isinstance(v, (int, float)) for v in box)
        for box in boxes
    ):
        return False
    rows = [boxes[i : i + columns] for i in range(0, len(boxes), columns)]
    previous_y = None
    base_x = [(box[0] + box[2]) / 2 for box in rows[0]]
    if any(right - left < 0.05 for left, right in zip(base_x, base_x[1:])):
        return False
    for row in rows:
        x_centers = [(box[0] + box[2]) / 2 for box in row]
        y_centers = [(box[1] + box[3]) / 2 for box in row]
        if max(y_centers) - min(y_centers) > 0.025:
            return False
        if any(abs(x - base) > 0.06 for x, base in zip(x_centers, base_x)):
            return False
        y = sum(y_centers) / len(y_centers)
        if previous_y is not None and y - previous_y < 0.008:
            return False
        previous_y = y
    return True


def _repeat_at(fields, index):
    """Return (columns, rows) only for a contiguous, unambiguous matrix."""
    remaining = len(fields) - index
    candidates = []
    for width in (2, 3):
        if remaining < width * 2:
            continue
        pattern = [_caption(f) for f in fields[index : index + width]]
        if (
            not all(pattern)
            or len(set(pattern)) != width
            or any(f.get("type") not in INPUTS for f in fields[index : index + width])
        ):
            continue
        rows = 1
        while (rows + 1) * width <= remaining:
            group = fields[index + rows * width : index + (rows + 1) * width]
            if any(f.get("type") not in INPUTS for f in group):
                break
            if [_caption(f) for f in group] != pattern:
                break
            rows += 1
        if rows >= 2 and _matrix_geometry(fields[index : index + width * rows], width):
            candidates.append((width * rows, width, rows))
    if not candidates:
        return None
    _, width, rows = max(candidates)
    return width, rows


def layout_for_fields(fields):
    """Return x,y,cols for each field, preserving all source field instances."""
    result = []
    i = y = 0
    while i < len(fields):
        match = _repeat_at(fields, i)
        if match:
            cols, rows = match
            for r in range(rows):
                for c in range(cols):
                    result.append({"x": c, "y": y + r, "cols": 1})
            i += cols * rows
            y += rows
        else:
            result.append({"x": 0, "y": y, "cols": 3})
            i += 1
            y += 1
    return result
