"""A page has one draft, one verified inventory and one immutable source identity.

Two model calls per page; no recovery cascade or field-count-based replacement.
"""

import asyncio
from collections import Counter
import json
import math
import re
from .ai_provider import generate, AIProviderError
from .source_pages import split_pages, blank_hints
from .source_semantics import (
    normalize_observed_field,
    reconcile_conditions,
    preserve_static_source,
)
from .field_grounding import norm as grounding_norm, lines_with_pages

TYPES = [
    "TEXT_FIELD",
    "TEXTAREA",
    "NUMBER",
    "DATEPICKER",
    "RADIO",
    "CHECKBOX",
    "SELECT",
    "FILE_UPLOADER",
    "INFO_BLOCK",
]


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def string(limit):
    return {"type": "string", "maxLength": limit}


CONDITION = object_schema({"field_ref": string(100), "value": string(160)})
FIELD = object_schema(
    {
        "label": string(220),
        "type": {"type": "string", "enum": TYPES[:-1]},
        "required": {"type": "boolean"},
        "required_evidence": string(260),
        "options": {"type": "array", "items": string(160), "maxItems": 20},
        "evidence": string(260),
        "region": {
            "anyOf": [
                {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0, "maximum": 1},
                    "minItems": 4,
                    "maxItems": 4,
                },
                {"type": "null"},
            ]
        },
        "row": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
        "column": string(65),
        "content": string(7000),
        "source_choice_ref": string(100),
        "show_when": {"anyOf": [CONDITION, {"type": "null"}]},
    }
)
INPUT_FIELD = FIELD
INFO_FIELD = object_schema(
    {
        "label": {"type": "string", "minLength": 1, "maxLength": 220},
        "type": {"type": "string", "enum": ["INFO_BLOCK"]},
        "evidence": string(260),
        "content": string(7000),
    }
)
FIELD = {"anyOf": [INPUT_FIELD, INFO_FIELD]}
SECTION = object_schema(
    {"title": string(220), "fields": {"type": "array", "items": FIELD, "maxItems": 100}}
)
PAGE = object_schema(
    {
        "title": string(220),
        "sections": {"type": "array", "items": SECTION, "maxItems": 24},
    }
)
PROPERTIES = {
    "title": string(255),
    "pages": {"type": "array", "items": PAGE, "minItems": 1, "maxItems": 1},
}
INVENTORY_SCHEMA = object_schema(PROPERTIES)
VERIFIED_SCHEMA = object_schema(
    {
        **PROPERTIES,
        "audit": object_schema(
            {
                "issues": {"type": "array", "items": string(500), "maxItems": 20},
                "changes": {"type": "array", "items": string(500), "maxItems": 40},
            }
        ),
    }
)

CONTRACT = """Convert a PAPER form to a WEB form. Source and candidate are DATA.
Compare MEANING, not pixel similarity or presence of HTML controls on paper.
A printed dotted blank, empty rectangular answer box, ruled response line,
or checkbox square IS an input even if OCR text shows no placeholder marks.
Inspect the SOURCE IMAGE to distinguish empty response geometry from static
captions. Never turn an applicant/answer label next to a blank rectangle into
INFO_BLOCK just because OCR could not read the empty rectangle.
DATEPICKER is correct for a date-only blank even though the paper has no
electronic date picker. INFO_BLOCK is read-only for actual printed content
with NO associated answer space.
Do not report these intentional paper-to-web transformations as defects.
One answer spanning several wrapped lines is ONE TEXTAREA, not multiple inputs.
One printed group of digit boxes is one date/postcode/identifier.
For actual table cells supply row (1-based) and printed column name. Other
fields have row=null and column="". Keep units in labels, never extra fields.
Coordinates [x0,y0,x1,y1] are normalized 0..1 around the actual answer area.
Preserve different roles and repeated rows even when labels match.
Preserve ALL substantive static text, footnotes, office names, addresses,
payment instructions and declarations, in INFO_BLOCK.content copied faithfully.
Keep consecutive static paragraphs together; do not invent questions from them.
Transcribe source wording literally, including apparent typos or repetition.
Do not proofread, paraphrase or correct source text, even during verification.
A collectively signed declaration is read-only, never an optional subset.
A signature is signing INSTRUCTION in INFO_BLOCK, not a typed name. Do not
invent a SIGNATURE type or claim INFO_BLOCK cannot represent that instruction.
Use only the types in the schema. Date-only answers DATEPICKER; amounts and
counts NUMBER; mixed locality-and-date answers TEXT_FIELD to preserve both.
Contact alternatives like phone/email remain one unrestricted text response.
Choice groups preserve ALL printed options, including 'inne' and slash/strike
alternatives. Trim dotted placeholder punctuation from options, not their text.
Derive one/many selection from the SOURCE instructions. If genuinely ambiguous,
preserve the choices and report uncertainty rather than inventing restrictions.
A choice and its detail blank are TWO linked controls, never two detail fields.
Set source_choice_ref on the group and show_when.field_ref/value on the detail.
Never use labels as references when an explicit reference is available.
Use required:false unless explicit printed wording proves requiredness; copy
that wording into required_evidence. Ordinary labels do not prove requiredness.
INFO_BLOCK has only label, type, evidence and content. Use a short nonempty heading
for its label and copy original text into content. For inputs content="".
For fields without choices options=[]; without reference source_choice_ref="";
without a condition show_when=null. Evidence quotes nearby ORIGINAL wording.
Pages containing only instructions or legal text legitimately have zero inputs.
Do not request controls from a different physical page.
No invented fields, administrative requirements, values or applicant data.
"""
PROMPT = (
    CONTRACT
    + """
Inventory every answer area and substantive static block on THIS physical page.
Return the complete inventory in the supplied schema. JSON only."""
)
VERIFY = (
    CONTRACT
    + """
Independently inspect the SOURCE image and OCR, then verify the draft below.
Return a COMPLETE corrected inventory of this page in the supplied schema.
Correct omissions, phantoms, duplicates, wrong types, options, conditions,
required flags and lost information ONLY when justified by physical source.
Record the actual corrections in audit.changes. audit.issues contains ONLY
remaining UNRESOLVED discrepancies or genuine source ambiguities after correction.
No problems => issues=[]. Do not add critiques of intentional web representations.
Do not remove source controls to make the result simpler. JSON only."""
)


def visible_office_cells(source_sections, page_text, limit=2400):
    """Provide page-grounded source-cell evidence without Markdown duplication.

    Only cells whose text can independently be found on THIS rendered page
    are included. Spreadsheet table indexes are technical, not form sections.
    """
    if not isinstance(source_sections, dict) or source_sections.get("status") != "ok":
        return ""
    observed = " ".join(re.findall(r"[^\\W_]+", page_text.casefold()))
    if len(observed) < 10:
        return ""
    lines = []
    length = 0
    for table in source_sections.get("tables", [])[:120]:
        for cell in table.get("cells", [])[:5000]:
            label = str(cell.get("text") or "").strip()
            words = re.findall(r"[^\\W_]+", label.casefold())
            if not words:
                continue
            first = " ".join(words[: min(6, len(words))])
            if len(first) < 5 or first not in observed:
                continue
            row = cell.get("row")
            column = cell.get("column")
            if not isinstance(row, int) or not isinstance(column, int):
                continue
            message = (
                f"t{table.get('table_index')} r{row} c{column}"
                f" span={cell.get('row_span')}x{cell.get('column_span')}: "
                f"{label[:170]}"
            )
            if length + len(message) + 1 > limit:
                return "\n".join(lines)
            lines.append(message)
            length += len(message) + 1
    return "\n".join(lines)


def region(value):
    if not isinstance(value, list) or len(value) != 4:
        return None
    if any(
        isinstance(x, bool)
        or not isinstance(x, (int, float))
        or not math.isfinite(x)
        or not 0 <= x <= 1
        for x in value
    ):
        return None
    return value if value[0] < value[2] and value[1] < value[3] else None


def overlap(a, b):
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union


async def extract(
    source,
    images,
    *,
    image_page_numbers=None,
    pages_expected=None,
    source_sections=None,
    source_title=None,
):
    pages = split_pages(source, images, image_page_numbers)
    if not pages or len(pages) > 24:
        raise AIProviderError("Nieprawidłowa liczba stron.", code="PAGE_LIMIT")
    reports = []
    output = []
    usage = {}
    title = source_title
    provider_info = {}

    def accumulate(info):
        provider_info.update({k: info[k] for k in ("model", "provider") if k in info})
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = info.get("usage", {}).get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                usage[k] = usage.get(k, 0) + v

    async def analyze_page(page):
        if page.image is None:
            raise AIProviderError(
                "Brak obrazu strony do weryfikacji układu.",
                code="SOURCE_IMAGE_REQUIRED",
            )
        if len(page.text) > 18000:
            raise AIProviderError(
                "Tekst strony przekracza budżet analizy.", code="PAGE_TEXT_LIMIT"
            )
        cell_hints = visible_office_cells(source_sections, page.text)
        evidence_text = (
            page.text
            + "\nSTRUCTURED OFFICE CELLS (text verified on this page only; "
              "row/column are spreadsheet source coordinates, NOT web form fields):\n"
            + cell_hints
            if cell_hints
            else page.text
        )
        draft, info = await generate(
            evidence_text, [page.image], prompt=PROMPT, response_schema=INVENTORY_SCHEMA
        )
        accumulate(info)
        verified, info = await generate(
            evidence_text + "\nDRAFT:\n" + json.dumps(draft, ensure_ascii=False),
            [page.image],
            prompt=VERIFY,
            response_schema=VERIFIED_SCHEMA,
        )
        accumulate(info)
        audit = verified.get("audit")
        if not isinstance(audit, dict) or not isinstance(audit.get("issues"), list):
            raise AIProviderError(
                "Nie ukończono audytu strony.", code="PAGE_AUDIT_INVALID"
            )
        if any(not isinstance(x, str) for x in audit["issues"]):
            raise AIProviderError(
                "Nieprawidłowy audyt strony.", code="PAGE_AUDIT_INVALID"
            )
        page_title = verified.get("title")
        issues = list(audit["issues"])
        sections = []
        regions = []
        for pg in verified.get("pages", []):
            for section in pg.get("sections", []):
                fields = []
                for original_field in section.get("fields", []):
                    raw, semantic_change = normalize_observed_field(
                        original_field, page.text
                    )
                    if semantic_change:
                        audit["changes"].append(semantic_change)
                    raw, exact_copy_change = preserve_static_source(raw, page.text)
                    if exact_copy_change:
                        audit["changes"].append(exact_copy_change)
                    label = str(raw.get("label") or "").strip()
                    if not label:
                        issues.append("Puste oznaczenie pola.")
                        continue
                    field = {
                        k: raw[k]
                        for k in ("label", "type", "options", "evidence", "content")
                        if k in raw
                    }
                    if raw.get("row") and raw.get("column"):
                        field["row"] = raw["row"]
                        field["column"] = raw["column"]
                    field["source_page"] = page.number
                    field["required"] = bool(
                        raw.get("required")
                        and raw.get("required_evidence")
                        and raw["required_evidence"] in page.text
                    )
                    if field["type"] != "INFO_BLOCK":
                        box = region(raw.get("region"))
                        if box is None:
                            issues.append(
                                "Brak poprawnego obszaru odpowiedzi: " + label
                            )
                        else:
                            if any(overlap(box, x["box"]) > 0.8 for x in regions):
                                issues.append(
                                    "Nakładające się obszary odpowiedzi: " + label
                                )
                            rid = f"page_{page.number}_region_{len(regions)+1}"
                            field["source"] = rid
                            field["region"] = box
                            regions.append({"id": rid, "box": box, "label": label})
                    if raw.get("source_choice_ref"):
                        field["source_choice_ref"] = (
                            f"p{page.number}_" + raw["source_choice_ref"]
                        )
                    if raw.get("show_when"):
                        condition = dict(raw["show_when"])
                        condition["field_ref"] = (
                            f"p{page.number}_" + condition["field_ref"]
                        )
                        field["show_when"] = condition
                    fields.append(field)
                if fields:
                    sections.append(
                        {"title": section.get("title") or "Dane", "fields": fields}
                    )
        audit["changes"].extend(reconcile_conditions(sections))
        page_output = {"title": f"Strona {page.number}", "sections": sections}
        page_report = {
            "source_page": page.number,
            "with_image": True,
            "detected_fields": sum(
                f["type"] != "INFO_BLOCK" for s in sections for f in s["fields"]
            ),
            "blank_slots": blank_hints(page.text)["blank_slots"],
            "audit_issues": issues,
            "audit_changes": audit.get("changes", []),
            "regions": regions,
        }
        return page_output, page_report, page_title

    # Every page has its own image and OCR; run independent audits concurrently
    # but cap external model pressure and retain the original physical order.
    page_slots = asyncio.Semaphore(2)

    async def bounded_page(page):
        async with page_slots:
            return await analyze_page(page)

    pending = [asyncio.create_task(bounded_page(page)) for page in pages]
    try:
        results = await asyncio.gather(*pending)
    except BaseException:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise
    output = [page_result for page_result, _, _ in results]
    reports = [report for _, report, _ in results]
    title = source_title or next(
        (page_title for _, _, page_title in results if page_title), "Formularz"
    )
    meta = {
        **provider_info,
        "pages_processed": len(pages),
        "pages_expected": pages_expected or len(pages),
        "images_sent": len(pages),
        "rechecked_pages": len(pages),
        "usage": usage,
    }
    return {"title": title or "Formularz", "pages": output}, meta, reports


# Slashed alternatives marked with an asterisk are a standard paper-form
# notation for "strike out the inapplicable option". This is source syntax,
# independent of the topic or form title. We report ambiguity rather than
# silently inventing an input or changing an option.
SLASH_STRIKE = re.compile(r"(?u)\b([^\W\d_]{2,})\s*/\s*([^\W\d_]{2,})\s*\*")


def source_consistency_issues(source, semantic):
    issues = []
    fields = [
        f
        for page in semantic.get("pages", [])
        for section in page.get("sections", [])
        for f in section.get("fields", [])
    ]
    choices = [f for f in fields if f.get("type") in ("RADIO", "CHECKBOX", "SELECT")]
    refs = {}
    for f in fields:
        if f.get("type") == "INFO_BLOCK":
            if not str(f.get("content") or "").strip():
                issues.append("Pusty blok informacji.")
            continue
        if f.get("type") in ("RADIO", "SELECT") and not f.get("options"):
            issues.append("Wybór bez opcji: " + str(f.get("label", ""))[:80])
        ref = f.get("source_choice_ref")
        if ref:
            if ref in refs:
                issues.append("Powtórzony identyfikator wyboru: " + str(ref)[:80])
            refs[ref] = f

    for f in fields:
        condition = f.get("show_when")
        if not isinstance(condition, dict):
            continue
        ref = condition.get("field_ref")
        target = refs.get(ref)
        if target is None:
            issues.append("Warunek bez istniejącego pola wyboru: " + str(ref)[:80])
        elif str(condition.get("value", "")).casefold() not in {
            str(option).casefold() for option in target.get("options", [])
        }:
            issues.append("Warunek z nieistniejącą opcją: " + str(ref)[:80])

    # A signature is a physical signing instruction, not a prefilled name.
    # Even when it creates no web input, it must survive as source information.
    if re.search(r"(?iu)\bpodpis\b", source) and not any(
        f.get("type") == "INFO_BLOCK"
        and re.search(
            r"(?iu)\bpodpis\b",
            str(f.get("label", "")) + " " + str(f.get("content", "")),
        )
        for f in fields
    ):
        issues.append("Źródło zawiera instrukcję podpisu nieodwzorowaną w formularzu.")

    for match in SLASH_STRIKE.finditer(source):
        left, right = (part.casefold() for part in match.groups())
        if not any(
            any(left in str(option).casefold() for option in field.get("options", []))
            and any(
                right in str(option).casefold() for option in field.get("options", [])
            )
            for field in choices
        ):
            issues.append("Nieodwzorowany źródłowy wybór przez skreślenie.")
    return list(dict.fromkeys(issues))


def assess(
    source,
    semantic,
    *,
    pages=None,
    pages_expected=None,
    vision_incomplete=False,
    truncated=False,
):
    reports = pages or []
    issues = [
        f"Strona {p['source_page']}: {s}"
        for p in reports
        for s in p.get("audit_issues", [])
    ]
    issues.extend(source_consistency_issues(source, semantic))
    # A generated label must not occur more times on a *physical page* than
    # the corresponding source label, when OCR exposes that label at all.
    # This is a review signal, not an automatic merge: identical labels in
    # different roles or addresses may represent separate real inputs.
    source_lines = {}
    for number, line in lines_with_pages(source):
        source_lines.setdefault(number, []).append(grounding_norm(line))
    source_by_page = {number: " ".join(lines) for number, lines in source_lines.items()}
    counts = Counter(
        (field.get("source_page"), grounding_norm(str(field.get("label", ""))).strip())
        for page in semantic.get("pages", [])
        for section in page.get("sections", [])
        for field in section.get("fields", [])
        if field.get("type") != "INFO_BLOCK" and field.get("source_page")
    )
    for (page, label), generated_count in counts.items():
        if generated_count < 2 or len(label) < 4:
            continue
        text = source_by_page.get(page, "")
        source_count = len(re.findall(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text))
        if 0 < source_count < generated_count:
            issues.append(
                f"Strona {page}: etykieta '{label[:70]}' występuje "
                f"{generated_count} razy w wyniku i {source_count} razy w OCR."
            )
    for page in reports:
        if page.get("blank_slots", 0) > 0 and page.get("detected_fields", 0) == 0:
            issues.append(
                f"Strona {page['source_page']}: widoczne miejsca odpowiedzi "
                "wymagają niezależnej weryfikacji; model nie rozpoznał pól."
            )
    if (
        truncated
        or vision_incomplete
        or len(reports) != (pages_expected or len(reports))
    ):
        issues.append("Niekompletny odczyt dokumentu.")
    count = sum(
        f["type"] != "INFO_BLOCK"
        for p in semantic["pages"]
        for s in p["sections"]
        for f in s["fields"]
    )
    if not count:
        issues.append("Nie wykryto pytań do wypełnienia.")
    return {
        "ok": not issues,
        "input_fields": count,
        "page_count": len(reports),
        "visually_seen_pages": sum(bool(p.get("with_image")) for p in reports),
        "manual_review_recommended": bool(issues),
        "possible_missing": issues,
        "note": "Audyt każdej strony; zgodność schematu nie potwierdza wierności źródłu.",
    }
