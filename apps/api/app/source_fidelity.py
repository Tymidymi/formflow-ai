"""Detect substantial loss of readable OOXML content during DOCX-to-PDF normalization.

This is a conservative, format-level safety check, not a form-specific parser.
It never fabricates answers from OOXML or claims that lexical coverage proves
visual fidelity. A failing result means the renderer must not silently succeed.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from io import BytesIO
import re
import unicodedata
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

W_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
W_PARAGRAPH = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
WORD = re.compile(r"[^\W_]+", re.UNICODE)
WINDOW = 4
MIN_WINDOWS = 40
MIN_RECALL = 0.45
MAX_XML_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Fidelity:
    source_windows: int
    matched_windows: int
    recall: float
    complete_enough: bool

    def report(self) -> dict:
        return {
            "method": "docx-4word-recall",
            "source_windows": self.source_windows,
            "matched_windows": self.matched_windows,
            "lexical_recall": self.recall,
            "substantial_loss_detected": not self.complete_enough,
            "note": "Lexical coverage is only a loss detector, not proof of complete rendering.",
        }


def _words(text: str) -> list[str]:
    return WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def _windows(words: list[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + WINDOW]) for i in range(len(words) - WINDOW + 1)}


def _source_windows(data: bytes) -> set[tuple[str, ...]]:
    with ZipFile(BytesIO(data)) as archive:
        entry = archive.getinfo("word/document.xml")
        if entry.file_size > MAX_XML_BYTES:
            raise ValueError("Źródłowy DOCX przekracza limit bezpiecznej analizy XML.")
        xml = archive.read(entry)
    root = ElementTree.fromstring(xml)
    phrases: set[tuple[str, ...]] = set()
    for paragraph in root.iter(W_PARAGRAPH):
        # This also reads text within drawing/textbox paragraphs, which a
        # visual renderer may silently drop. Duplicate Choice/Fallback
        # branches are naturally deduplicated by the set.
        text = " ".join(item.text for item in paragraph.iter(W_TEXT) if item.text)
        phrases.update(_windows(_words(text)))
    return phrases


def assess_docx_render(source_docx: bytes, rendered_text: str) -> Fidelity:
    """Fail closed only on substantial loss; minor OCR reflow is tolerated."""
    try:
        original = _source_windows(source_docx)
    except (BadZipFile, KeyError, ElementTree.ParseError, ValueError) as exc:
        raise ValueError("Nie można zweryfikować struktury źródłowego DOCX.") from exc
    rendered = _windows(_words(rendered_text))
    matched = len(original & rendered)
    coverage = matched / len(original) if original else 1.0
    return Fidelity(
        source_windows=len(original),
        matched_windows=matched,
        recall=round(coverage, 3),
        complete_enough=len(original) < MIN_WINDOWS or coverage >= MIN_RECALL,
    )


PAGE_SPLIT = re.compile(r"(?m)^\[Strona \d+/\d+\][ \t]*$")


def mirrored_source_pages(rendered_text: str) -> list[tuple[int, int]]:
    """Find near-identical consecutive physical pages, never merge silently."""
    pages = [text for text in PAGE_SPLIT.split(rendered_text) if text.strip()]
    normalized = [" ".join(_words(text)) for text in pages]
    mirrored = []
    for index, (first, second) in enumerate(zip(normalized, normalized[1:]), 1):
        if min(len(first), len(second)) < 250:
            continue
        similarity = SequenceMatcher(None, first, second).ratio()
        if similarity >= 0.96:
            mirrored.append((index, index + 1))
    return mirrored
