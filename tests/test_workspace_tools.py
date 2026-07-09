import tempfile
import os
from pathlib import Path

import pytest

import config as cfg_mod
from workspace import (
    set_workspace,
    resolve_path,
    set_projects_root,
    list_projects,
    set_project,
    select_project,
)
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


def test_projects_root_and_project_activation(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    cfg_mod.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    ws = tmp_path / "workspace"
    ws.mkdir()
    set_workspace(str(ws))

    projects_root = tmp_path / "projects"
    cfg = set_projects_root(str(projects_root))
    assert projects_root.exists()
    assert cfg["projects_root"] == str(projects_root.resolve())
    assert list_projects() == []

    cfg = set_project("coffee-shop")
    project_dir = Path(cfg["workspace_path"])
    assert project_dir.exists()
    assert project_dir == projects_root / "coffee-shop"
    assert "coffee-shop" in list_projects()


def test_select_project_creates_and_activates(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    cfg_mod.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    ws = tmp_path / "workspace"
    ws.mkdir()
    set_workspace(str(ws))

    projects_root = tmp_path / "projects"
    set_projects_root(str(projects_root))

    result = select_project("coffee-shop")
    assert result["status"] == "created"
    assert Path(result["path"]) == projects_root / "coffee-shop"
    assert list_projects() == ["coffee-shop"]


def test_create_project_tool_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "cfg" / "config.json")
    cfg_mod.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    ws = tmp_path / "workspace"
    ws.mkdir()
    set_workspace(str(ws))

    projects_root = tmp_path / "projects"
    set_projects_root(str(projects_root))

    monkeypatch.setattr("builtins.input", lambda prompt='': "y")
    result = tools.create_project("coffee-shop")
    assert result["status"] == "created"
    assert Path(result["path"]) == projects_root / "coffee-shop"
    assert (projects_root / "coffee-shop").exists()
