"""Deployment-time settings; secrets must never be hard-coded."""

import os


def max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_MB", "15")
    try:
        mb = int(raw)
    except ValueError as exc:
        raise RuntimeError("MAX_UPLOAD_MB must be an integer") from exc
    if not 1 <= mb <= 50:
        raise RuntimeError("MAX_UPLOAD_MB must be between 1 and 50")
    return mb * 1024 * 1024
