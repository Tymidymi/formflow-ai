"""Physical page identity shared by extraction and audit."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Page:
    number: int
    text: str
    image: tuple[str, bytes] | None


MARK = re.compile(r"(?m)^\[(?:Strona|Część)\s+(\d+)/(\d+)\]\s*$")


def split_pages(source, images, image_page_numbers=None):
    blobs = dict(zip(image_page_numbers or range(1, len(images) + 1), images))
    marks = list(MARK.finditer(source))
    if not marks:
        if len(images) > 1:
            raise ValueError("Obrazy bez jednoznacznego przypisania tekstu do stron.")
        return [Page(1, source, blobs.get(1))]
    return [
        Page(
            int(m.group(1)),
            source[
                m.end() : marks[i + 1].start() if i + 1 < len(marks) else len(source)
            ].strip(),
            blobs.get(int(m.group(1))),
        )
        for i, m in enumerate(marks)
    ]


def blank_hints(text):
    return {"blank_slots": len(re.findall(r"(?:\.{5,}|…{3,}|_{4,})", text))}
