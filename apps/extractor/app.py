"""Isolated Office-to-PDF renderer with Docling Slim source evidence."""

import base64
import os
from pathlib import Path
import signal
import subprocess
import sys
import json
import tempfile
import threading
from fastapi import FastAPI, File, HTTPException, UploadFile
from xlsx_print import fit_xlsx_print_width
from ods_print import fit_ods_print_width

app = FastAPI(docs_url=None, openapi_url=None)
LOCK = threading.Lock()
MAX_BYTES = 15 * 1024 * 1024
FORMATS = {".doc", ".docx", ".xlsx", ".ods"}


def render_pdf(data: bytes, extension: str) -> bytes:
    if extension not in FORMATS or not data or len(data) > MAX_BYTES:
        raise ValueError("Nieprawidłowy dokument Office.")
    # Unique writable profile, no shared LibreOffice process, no network in Docker.
    with LOCK, tempfile.TemporaryDirectory(prefix="office-") as tmp:
        root = Path(tmp)
        source = root / ("source" + extension)
        source.write_bytes(data)
        profile = root / "profile"
        profile.mkdir()
        (profile / "user").mkdir()
        (profile / "user/registrymodifications.xcu").write_text(
            '<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
            "</item></oor:items>"
        )
        process = subprocess.Popen(
            [
                "soffice",
                "-env:UserInstallation=" + profile.as_uri(),
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(source),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "HOME": tmp},
        )
        try:
            process.wait(timeout=75)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise ValueError("Przekroczono czas renderowania Office.")
        pdf = root / "source.pdf"
        if process.returncode or not pdf.exists():
            raise ValueError("Nie udało się wyrenderować dokumentu Office.")
        result = pdf.read_bytes()
        if not result.startswith(b"%PDF-") or len(result) > MAX_BYTES:
            raise ValueError("Nieprawidłowy lub zbyt duży wynik renderowania.")
        return result


def read_structure(data: bytes, extension: str) -> dict:
    """An isolated, timed Docling Slim process; PDF rendering still works on failure."""
    with LOCK, tempfile.TemporaryDirectory(prefix="source-structure-") as tmp:
        source = Path(tmp) / ("source" + extension)
        source.write_bytes(data)
        try:
            result = subprocess.run(
                [sys.executable, "/app/office_structure.py", str(source)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=25,
                check=False,
                env={**os.environ, "HOME": tmp},
            )
        except subprocess.TimeoutExpired:
            return {"engine": "docling-slim", "status": "timeout"}
        if len(result.stdout) > 512_000:
            return {"engine": "docling-slim", "status": "oversized"}
        try:
            parsed = json.loads(result.stdout)
        except (ValueError, TypeError):
            return {"engine": "docling-slim", "status": "error"}
        if result.returncode or not isinstance(parsed, dict):
            return {"engine": "docling-slim", "status": "error"}
        return parsed


@app.get("/healthz")
def health():
    return {"status": "ok", "engine": "libreoffice-pdf", "formats": sorted(FORMATS)}


@app.post("/extract")
def extract(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    try:
        raw = file.file.read(MAX_BYTES + 1)
        printable = raw
        print_meta = None
        if extension == ".xlsx":
            printable, print_meta = fit_xlsx_print_width(raw)
        elif extension == ".ods":
            printable, print_meta = fit_ods_print_width(raw)
        pdf = render_pdf(printable, extension)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    structure = read_structure(raw, extension)
    return {
        "engine": "libreoffice-pdf",
        "pdf_base64": base64.b64encode(pdf).decode(),
        "source_structure": structure,
        "print_normalization": print_meta,
    }
