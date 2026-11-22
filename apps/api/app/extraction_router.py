"""Normalize input into physical PDF pages; OCR and vision share page identity."""

import base64
from io import BytesIO
import os
from PIL import Image
from pypdf import PdfReader, PdfWriter
import httpx
from .uploads import RejectedFile
from .source_fidelity import assess_docx_render, mirrored_source_pages
from .render_fidelity import check_visible_text

OFFICE = {".doc", ".docx", ".xlsx", ".ods"}
DOCLING_URL = "http://docling-office:8001"  # retained internal service DNS
PDF_URL = "http://pdf-engine:8002"
MAX_BYTES = 15 * 1024 * 1024


async def _request(url, extension, content, *, previews=False):
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90, connect=3), follow_redirects=False
        ) as client:
            response = await client.post(
                url + "/extract",
                params={"previews": "true"} if previews else {},
                files={
                    "file": ("input" + extension, content, "application/octet-stream")
                },
            )
    except httpx.HTTPError as exc:
        raise RejectedFile("Moduł odczytu dokumentów jest niedostępny.", 503) from exc
    if response.status_code != 200:
        if response.status_code in (413, 415, 422):
            try:
                detail = response.json().get("detail", "Nieprawidłowy dokument.")
            except (ValueError, TypeError):
                detail = "Nieprawidłowy dokument."
            raise RejectedFile(str(detail), response.status_code)
        raise RejectedFile("Błąd modułu odczytu dokumentów.", 503)
    payload = response.json()
    if not isinstance(payload, dict):
        raise RejectedFile("Nieprawidłowa odpowiedź modułu odczytu.", 502)
    return payload


async def _extract_pdf_chunked(content, *, visual):
    """Preserve every original page while bounding each PDF worker request.

    Large PDFs are split in memory only. Reassemble original page numbers before
    the AI inventory: no special cases for form titles and no skipped pages.
    """
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            return await _request(PDF_URL, ".pdf", content, previews=visual)
        total = len(reader.pages)
    except Exception:
        return await _request(PDF_URL, ".pdf", content, previews=visual)
    if total <= 6:
        return await _request(PDF_URL, ".pdf", content, previews=visual)
    if total > 24:
        raise RejectedFile("Dokument przekracza limit 24 stron.", 413)
    texts = []
    images = []
    page_sources = []
    ocr_pages = 0
    truncated = False
    for start in range(0, total, 6):
        end = min(start + 6, total)
        writer = PdfWriter()
        for index in range(start, end):
            writer.add_page(reader.pages[index])
        buffer = BytesIO()
        writer.write(buffer)
        part = await _request(PDF_URL, ".pdf", buffer.getvalue(), previews=visual)
        # The worker must account for EVERY page, never silently drop one.
        if part.get("page_count") != end - start:
            raise RejectedFile("Silnik PDF nie zwrócił wszystkich stron.", 502)
        from .source_pages import split_pages
        parts = split_pages(part.get("text", ""), [], [])
        if len(parts) != end - start or [x.number for x in parts] != list(range(1, end - start + 1)):
            raise RejectedFile("Niekompletne indeksy stron po podziale PDF.", 502)
        for item in parts:
            texts.append(f"[Strona {start + item.number}/{total}]\n{item.text}")
        for entry in part.get("preview_images", []):
            global_number = start + entry.get("page", 0)
            if not start < global_number <= end:
                raise RejectedFile("Niepoprawny numer obrazu strony.", 502)
            images.append({**entry, "page": global_number})
        for entry in part.get("page_sources", []):
            page_sources.append({**entry, "page": start + entry.get("page", 0)})
        ocr_pages += part.get("ocr_pages") or 0
        truncated = truncated or bool(part.get("truncated"))
    if visual and {entry["page"] for entry in images} != set(range(1, total + 1)):
        raise RejectedFile("Niekompletne obrazy PDF po automatycznym podziale.", 502)
    return {
        "engine": "pdf-layout-ocr+in-memory-chunks",
        "page_count": total,
        "ocr_pages": ocr_pages,
        "text": "\n\n".join(texts),
        "truncated": truncated,
        "page_sources": page_sources,
        "preview_images": images,
        "vision_incomplete": bool(visual and len(images) != total),
        "automatic_pdf_chunks": (total + 5) // 6,
    }


def image_pdf(content):
    try:
        with Image.open(BytesIO(content)) as opened:
            if opened.width * opened.height > 32_000_000:
                raise RejectedFile("Obraz przekracza limit 32 milionów pikseli.", 413)
            canvas = opened.convert("RGB")
            count = max(1, round(canvas.height / (canvas.width * 2**0.5)))
            if count > 24:
                raise RejectedFile("Obraz przekracza limit stron.", 413)
            pages = [
                canvas.crop(
                    (
                        0,
                        round(i * canvas.height / count),
                        canvas.width,
                        round((i + 1) * canvas.height / count),
                    )
                )
                for i in range(count)
            ]
            stream = BytesIO()
            pages[0].save(stream, format="PDF", save_all=True, append_images=pages[1:])
            return stream.getvalue()
    except (OSError, ValueError) as exc:
        raise RejectedFile("Nie można odczytać obrazu.", 422) from exc


async def extract_with_backend(content, extension, *, vision_mode="auto"):
    if vision_mode not in {"auto", "on", "off"}:
        raise ValueError("Nieprawidłowy tryb vision.")
    original = extension
    normalization = None
    original_docx = content if extension == ".docx" else None
    office_structure = None
    office_print_normalization = None
    visible_pdf_check = None
    if extension in OFFICE:
        if os.environ.get("FORMFLOW_DOCLING_URL") != DOCLING_URL:
            raise RejectedFile("Brak modułu normalizacji Office.", 503)
        payload = await _request(DOCLING_URL, extension, content)
        office_structure = payload.get("source_structure")
        office_print_normalization = payload.get("print_normalization")
        if not isinstance(office_structure, dict):
            office_structure = None
        try:
            content = base64.b64decode(payload["pdf_base64"], validate=True)
        except (KeyError, ValueError, TypeError) as exc:
            raise RejectedFile(
                "Brak poprawnego PDF z normalizacji Office.", 502
            ) from exc
        if not content.startswith(b"%PDF-") or len(content) > MAX_BYTES:
            raise RejectedFile("Nieprawidłowy PDF po normalizacji Office.", 422)
        normalization = "libreoffice-pdf"
        extension = ".pdf"
        try:
            visible_pdf_check = check_visible_text(content)
        except ValueError as exc:
            raise RejectedFile(str(exc), 422) from exc
        if visible_pdf_check["material_clipping"]:
            raise RejectedFile(
                "PDF wygenerowany z Office zawiera tekst poza widocznym "
                "obszarem strony. Konwersja byłaby niekompletna.",
                422,
            )
    elif extension in {".png", ".jpg", ".jpeg"}:
        content = image_pdf(content)
        normalization = "image-page-slices"
        extension = ".pdf"
    if extension != ".pdf":
        raise RejectedFile("Nieobsługiwany format.", 415)
    if os.environ.get("FORMFLOW_PDF_WORKER_URL") != PDF_URL:
        raise RejectedFile("Brak modułu odczytu PDF.", 503)
    visual = (
        vision_mode == "on"
        or vision_mode == "auto"
        and os.environ.get("FORMFLOW_PDF_VISION", "false").lower()
        in {"true", "1", "yes"}
    )
    # Normalized Office/images always require visual evidence.
    visual = visual or normalization is not None
    payload = await _extract_pdf_chunked(content, visual=visual)
    text = payload.get("text")
    if not isinstance(text, str):
        raise RejectedFile("Moduł PDF nie zwrócił tekstu źródłowego.", 502)
    if original in {".xlsx", ".ods"} and mirrored_source_pages(text):
        raise RejectedFile(
            "Normalizacja arkusza wygenerowała niemal identyczne strony. "
            "Nie można bezpiecznie ustalić unikalnych pól formularza.",
            422,
        )
    fidelity = None
    if original_docx is not None:
        try:
            result = assess_docx_render(original_docx, text)
        except ValueError as exc:
            raise RejectedFile(str(exc), 422) from exc
        fidelity = result.report()
        if not result.complete_enough:
            raise RejectedFile(
                "Renderer DOCX utracił znaczną część tekstu źródłowego. "
                "Konwersja została przerwana zamiast wygenerować niepełny formularz.",
                422,
            )
    images = []
    numbers = []
    rejected = []
    for i, entry in enumerate(payload.get("preview_images", []) if visual else [], 1):
        number = entry.get("page", i)
        try:
            data = base64.b64decode(entry["base64"], validate=True)
        except (KeyError, ValueError, TypeError):
            rejected.append(number)
            continue
        if entry.get("mime") == "image/jpeg" and 0 < len(data) <= 4 * 1024 * 1024:
            images.append(("image/jpeg", data))
            numbers.append(number)
        else:
            rejected.append(number)
    count = payload.get("page_count") or 0
    return (
        text,
        images,
        {
            "engine": payload.get("engine", "pdf-layout-ocr"),
            "automatic_pdf_chunks": payload.get("automatic_pdf_chunks", 1),
            "pages": count,
            "ocr_pages": payload.get("ocr_pages"),
            "page_sources": payload.get("page_sources", []),
            "truncated": bool(payload.get("truncated")),
            "vision_enabled": visual,
            "vision_pages": len(images),
            "vision_page_numbers": numbers,
            "vision_rejected_pages": rejected,
            "vision_incomplete": bool(visual and (len(numbers) != count or rejected)),
            "normalization_engine": normalization,
            "original_extension": original,
            "normalization_fidelity": fidelity,
            "office_print_normalization": office_print_normalization,
            "office_pdf_visibility": visible_pdf_check,
            "office_structure_engine": (
                office_structure.get("engine") if office_structure else None
            ),
            "office_structure_status": (
                office_structure.get("status") if office_structure else "not_available"
            ),
            "office_source_cells": (
                office_structure.get("cell_count", 0) if office_structure else 0
            ),
            "office_source_chars": (
                len(office_structure.get("plain_text", "")) if office_structure else 0
            ),
            # Internal-only: main.py passes this into the page analyzer and
            # removes it from HTTP diagnostics to avoid echoing document text.
            "source_sections": (
                office_structure
                if office_structure and office_structure.get("status") == "ok"
                else None
            ),
        },
    )
