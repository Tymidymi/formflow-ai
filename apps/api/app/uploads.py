"""Upload acceptance before isolated document rendering."""

from __future__ import annotations

import io
import re
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile

from .settings import max_upload_bytes

ALLOWED = {".pdf", ".doc", ".docx", ".ods", ".xlsx", ".jpg", ".jpeg", ".png"}
INVALID_NAME_CHARS = re.compile(r"[;:><\/\\|'*%$]")
ZIP_MAX_ENTRIES = 3000
ZIP_MAX_EXPANDED = 128 * 1024 * 1024


class RejectedFile(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def validate_filename(name: str | None) -> str:
    if not name or name in {".", ".."}:
        raise RejectedFile("Nieprawidłowa nazwa pliku.")
    if len(name) > 250:
        raise RejectedFile("Nazwa pliku przekracza 250 znaków.")
    if INVALID_NAME_CHARS.search(name) or "\x00" in name:
        raise RejectedFile("Nazwa pliku zawiera niedozwolone znaki.")
    if PurePath(name).suffix.lower() not in ALLOWED:
        raise RejectedFile("Nieobsługiwane rozszerzenie pliku.", 415)
    return PurePath(name).suffix.lower()


def _office_mime(content: bytes, extension: str) -> str:
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if (
                len(infos) > ZIP_MAX_ENTRIES
                or sum(i.file_size for i in infos) > ZIP_MAX_EXPANDED
            ):
                raise RejectedFile(
                    "Archiwum Office przekracza limit bezpieczeństwa.", 413
                )
            names = set(archive.namelist())
            if (
                extension == ".docx"
                and {"[Content_Types].xml", "word/document.xml"} <= names
            ):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if (
                extension == ".xlsx"
                and {"[Content_Types].xml", "xl/workbook.xml"} <= names
            ):
                return (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            if extension == ".ods" and "mimetype" in names:
                if (
                    archive.read("mimetype", pwd=None)
                    == b"application/vnd.oasis.opendocument.spreadsheet"
                ):
                    return "application/vnd.oasis.opendocument.spreadsheet"
    except (BadZipFile, OSError, RuntimeError, ValueError) as exc:
        raise RejectedFile("Uszkodzony plik Office.", 415) from exc
    raise RejectedFile("Zawartość pliku nie odpowiada rozszerzeniu Office.", 415)


def detect_mime(content: bytes, extension: str) -> str:
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return "application/pdf"
    if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if extension == ".doc" and content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        # Only identifies OLE2 signature; complete DOC validation follows in the isolated Office renderer.
        return "application/msword"
    if extension in {".docx", ".xlsx", ".ods"}:
        return _office_mime(content, extension)
    raise RejectedFile("Zawartość pliku nie odpowiada jego rozszerzeniu.", 415)


async def inspect_upload(file: UploadFile) -> dict:
    extension = validate_filename(file.filename)
    limit = max_upload_bytes()
    try:
        payload = await file.read(limit + 1)
    finally:
        await file.close()
    if not payload:
        raise RejectedFile("Nie można przesłać pustego pliku.")
    if len(payload) > limit:
        raise RejectedFile("Plik przekracza dopuszczalny rozmiar.", 413)
    mime = detect_mime(payload, extension)
    return {
        "filename": file.filename,
        "size_bytes": len(payload),
        "detected_mime": mime,
        "extension": extension,
        "validation": "passed",
    }
