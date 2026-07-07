import os
import json
import sys
from pathlib import Path

import pytest

from workspace import set_workspace, resolve_path
import tools
from api import send_message, APIError


def test_absolute_and_traversal_rejected(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace(str(ws))

    # absolute path should be rejected
    with pytest.raises(ValueError):
        resolve_path(str(Path("/etc/passwd")))

    # traversal outside workspace should be rejected
    with pytest.raises(ValueError):
        resolve_path("../outside.txt")


def test_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret", encoding="utf-8")

    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace(str(ws))

    link = ws / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks not supported here: {exc}")

    # Accessing through the symlink should be detected as escape
    with pytest.raises(ValueError):
        resolve_path("link/secret.txt")


def test_confirmation_decline(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace(str(ws))

    # Simulate user declining
    monkeypatch.setattr("builtins.input", lambda prompt='': 'n')

    ret = tools.write_file("a.txt", "hello world")
    assert ret == "declined"


def test_max_call_loop(tmp_path, monkeypatch):
    # Prepare workspace and config
    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace(str(ws))

    # Create a dummy urlopen that always returns a functionCall response
    def make_resp():
        body = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "list_dir", "args": {"path": "."}}}
                        ]
                    }
                }
            ]
        }
        return json.dumps(body).encode("utf-8")

    class DummyResp:
        def __init__(self, b):
            self._b = b
        def read(self):
            return self._b
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        return DummyResp(make_resp())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    # Call send_message with tools enabled; it should hit the max-call cap and raise
    messages = [{"role": "user", "content": "list files"}]
    cfg = {"api_key": "x", "model": "m"}

    with pytest.raises(APIError):
        send_message(messages, cfg=cfg, timeout=2, tools_enabled=True)
