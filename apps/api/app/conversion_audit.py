"""Minimal, private conversion telemetry. Never log raw documents or model text."""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re

REQUEST_ID: ContextVar[str] = ContextVar("conversion_request_id", default="-")
SAFE_KEYS = {
    "status", "http_status", "stage", "error_code", "error_class",
    "model", "finish_reason", "provider_http_status", "provider_request_id",
    "response_chars", "json_error_line", "json_error_column",
    "prompt_tokens", "completion_tokens", "total_tokens", "max_tokens",
    "images_sent", "file_bytes", "file_extension", "elapsed_ms",
    "vision_mode", "page_count", "schema_valid", "quality_ok",
}
SAFE_STRING = re.compile(r"^[A-Za-z0-9_.:/-]{1,100}$")
logger = logging.getLogger("formflow.conversion")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    destination = os.getenv("FORMFLOW_AUDIT_LOG_FILE", "").strip()
    if destination:
        # Ensure rotated audit log files stay private (0600) as well.
        os.umask(0o077)
        # The directory is a pre-provisioned restricted Docker bind mount.
        try:
            writer = RotatingFileHandler(
                destination, maxBytes=3 * 1024 * 1024, backupCount=3,
                encoding="utf-8", delay=True)
            writer.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(writer)
        except OSError:
            logger.warning('{"event":"audit_file_unavailable"}')

def record(event: str, **details) -> None:
    """Explicit allowlist prevents filenames, PII, OCR text or raw model output."""
    if not SAFE_STRING.fullmatch(event):
        raise ValueError("Unsafe audit event.")
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "request_id": REQUEST_ID.get(),
    }
    for name, value in details.items():
        if name not in SAFE_KEYS or value is None:
            continue
        if isinstance(value, bool):
            entry[name] = value
        elif isinstance(value, int | float) and not isinstance(value, bool):
            entry[name] = value
        elif isinstance(value, str) and SAFE_STRING.fullmatch(value):
            entry[name] = value
    logger.info(json.dumps(entry, separators=(",", ":"), ensure_ascii=False))
