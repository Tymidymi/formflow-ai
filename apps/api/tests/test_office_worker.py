"""Office normalization boundary: isolation, cleanup and fixed commands."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

path = Path(__file__).resolve().parents[2] / "extractor" / "app.py"
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location("office_worker_under_test", path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


@pytest.mark.parametrize("extension", [".doc", ".docx", ".xlsx", ".ods"])
def test_formats_share_isolated_pdf_renderer(monkeypatch, extension):
    paths = []

    class Process:
        returncode = 0

        def __init__(self, args, **kw):
            assert args[0] == "soffice" and "--headless" in args
            assert kw["start_new_session"] is True
            root = Path(args[-1]).parent
            assert Path(args[-1]).suffix == extension
            assert (
                "MacroSecurityLevel"
                in (root / "profile/user/registrymodifications.xcu").read_text()
            )
            assert (root / "source.pdf").exists() is False
            (root / "source.pdf").write_bytes(b"%PDF-fixture")
            paths.append(root)

        def wait(self, timeout=None):
            assert timeout == 75

    monkeypatch.setattr(worker.subprocess, "Popen", Process)
    assert worker.render_pdf(b"source", extension) == b"%PDF-fixture"
    assert paths and not paths[0].exists()


def test_timeout_kills_process_group_and_cleans_files(monkeypatch):
    paths = []
    killed = []

    class Process:
        pid = 123

        def __init__(self, args, **kw):
            paths.append(Path(args[-1]).parent)

        def wait(self, timeout=None):
            if timeout:
                raise subprocess.TimeoutExpired("soffice", timeout)

    monkeypatch.setattr(worker.subprocess, "Popen", Process)
    monkeypatch.setattr(worker.os, "killpg", lambda pid, sig: killed.append(pid))
    with pytest.raises(ValueError, match="czas"):
        worker.render_pdf(b"source", ".docx")
    assert killed == [123] and not paths[0].exists()


def test_unsupported_or_empty_inputs_never_start_renderer(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Unexpected subprocess")

    monkeypatch.setattr(worker.subprocess, "Popen", fail)
    for data, ext in [(b"source", ".exe"), (b"", ".docx")]:
        with pytest.raises(ValueError):
            worker.render_pdf(data, ext)
