"""Memory-bounded, local text extraction for pre-OOXML Word .doc files.

Uses the open-source antiword utility in the isolated Office worker.
This does not execute document macros or external URLs. Antiword is text-only:
layout fidelity and graphical controls require human review.
"""
from __future__ import annotations

import os
import resource
import subprocess
import tempfile

OLE2_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
MAX_DOC_BYTES = 15 * 1024 * 1024
MAX_TEXT_BYTES = 3 * 1024 * 1024


class LegacyDocError(ValueError):
    pass


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (192 * 1024 * 1024, 192 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def extract_doc(content: bytes) -> str:
    if not content.startswith(OLE2_MAGIC) or len(content)>MAX_DOC_BYTES:
        raise LegacyDocError("Nieprawidłowy lub zbyt duży plik DOC.")
    # No client-supplied filenames reach the filesystem or subprocess.
    with tempfile.TemporaryDirectory(prefix="formflow-doc-") as temp:
        filename=os.path.join(temp,"input.doc")
        descriptor=os.open(filename,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,"wb") as stream:
            stream.write(content)
        try:
            process=subprocess.run(
                ["antiword","-w","0","-m","UTF-8.txt",filename],
                shell=False,check=False,capture_output=True,timeout=20,
                preexec_fn=_limits,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            raise LegacyDocError("Nie udało się bezpiecznie odczytać pliku DOC.") from exc
    if process.returncode != 0 or len(process.stdout)>MAX_TEXT_BYTES:
        raise LegacyDocError("Nie udało się wydobyć tekstu ze starego formatu DOC.")
    text=process.stdout.decode("utf-8","replace").strip()
    if not text:
        raise LegacyDocError("Dokument DOC nie zawiera czytelnego tekstu.")
    return text