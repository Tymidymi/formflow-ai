"""Run a reproducible conversion matrix; results are evidence, not accuracy scores."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="JSON list of {path, reference?: bool}; references are not OCR inputs",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:18171")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--external-ai-consent", action="store_true", required=True)
    args = parser.parse_args()
    # Fail before scheduling uploads if the selected instance is not ready.
    with urllib.request.urlopen(
        args.url.rstrip("/") + "/healthz", timeout=10
    ) as response:
        if response.status != 200:
            raise SystemExit("Instance is not healthy")
    entries = [
        e for e in json.loads(args.manifest.read_text()) if not e.get("reference")
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    lock = threading.Lock()
    results = []

    def run(item):
        if stop.is_set():
            return
        path = Path(item["path"])
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        key = digest[:16] + "_" + path.suffix[1:]
        boundary = "formflow_validation_" + digest[:20]
        body = (
            (
                "--"
                + boundary
                + '\r\nContent-Disposition: form-data; name="file"; filename="'
                + path.name
                + '"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + data
            + ("\r\n--" + boundary + "--\r\n").encode()
        )
        started = time.monotonic()
        req = urllib.request.Request(
            args.url.rstrip("/") + "/api/v1/forms/convert?mode=diagnostic",
            data=body,
            headers={
                "Content-Type": "multipart/form-data; boundary=" + boundary,
                "X-External-AI-Consent": "true",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=270) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            raw = error.read()
            status = error.code
        except (TimeoutError, OSError) as error:
            raw = json.dumps(
                {"code": "CLIENT_TRANSPORT_ERROR", "detail": type(error).__name__}
            ).encode()
            status = None
        (args.output / (key + ".json")).write_bytes(raw)
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {}
        # Stop scheduling when provider access is unavailable. No blind paid retries.
        if payload.get("code") == "PROVIDER_HTTP_ERROR":
            stop.set()
        record = {
            "file": path.name,
            "path": str(path),
            "sha256": digest,
            "response": key + ".json",
            "http": status,
            "seconds": round(time.monotonic() - started, 2),
            "status": payload.get("status"),
            "error": payload.get("code"),
            "quality": payload.get("quality"),
            "usage": payload.get("usage"),
        }
        with lock:
            results.append(record)
            (args.output / "summary.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2)
            )
            print(json.dumps(record, ensure_ascii=False), flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run, entries))
    print(
        json.dumps(
            {
                "attempted": len(results),
                "selected": len(entries),
                "provider_blocked": stop.is_set(),
            }
        )
    )
    if (
        stop.is_set()
        or len(results) != len(entries)
        or any(r["http"] != 200 for r in results)
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
