import tempfile
import os
from pathlib import Path

import pytest

from workspace import set_workspace, resolve_path
import tools


def test_resolve_rejects_outside(tmp_path):
    # set workspace to tmp_path/work
    ws = tmp_path / "work"
    ws.mkdir()
    cfg = set_workspace(str(ws))

    # allowed inside
    p = resolve_path("file.txt")
    assert str(p).startswith(str(ws))

    # attempt escape
    with pytest.raises(ValueError):
        resolve_path("../etc/passwd")


def test_tools_write_and_read(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    set_workspace(str(ws))

    # simulate user confirmation accepting
    monkeypatch.setattr("builtins.input", lambda prompt='': 'y')

    # write
    ret = tools.write_file("a.txt", "hello")
    assert Path(ret).exists()
    assert tools.read_file("a.txt") == "hello"

    # append
    tools.append_file("a.txt", " world")
    assert tools.read_file("a.txt") == "hello world"

    # list
    listing = tools.list_dir(".")
    assert "a.txt" in listing
