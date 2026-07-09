"""
workspace.py -- Secure workspace path handling
------------------------------------------------
Provides a simple sandbox root for AI-driven file ops. Ensures all
paths resolve under a configured workspace root and prevents path
traversal, absolute paths, or symlink escapes.

Public API:
  set_workspace(path: str | None) -> dict
  set_projects_root(path: str | None) -> dict
  list_projects() -> list[str]
  set_project(name: str | None) -> dict
  resolve_path(rel: str) -> pathlib.Path
"""

from pathlib import Path
import os
from typing import Optional

from config import load_config, save_config


def set_workspace(path: Optional[str]) -> dict:
    """Set the workspace path in config. If path does not exist prompt to create it.

    Returns the updated config dict.
    """
    cfg = load_config()

    if not path:
        try:
            path = input(f"Workspace path [{cfg.get('workspace_path') or ''}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[workspace] Cancelled.")
            return cfg

    if not path:
        print("[workspace] No change made.")
        return cfg

    root = Path(path).expanduser()

    if not root.exists():
        try:
            yn = input(f"Path {root} does not exist. Create it? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[workspace] Cancelled.")
            return cfg

        if yn not in ("y", "yes"):
            print("[workspace] Not created.")
            return cfg
        root.mkdir(parents=True, exist_ok=True)

    root = root.resolve()
    cfg["workspace_path"] = str(root)
    save_config(cfg)
    print(f"[workspace] Workspace set -> {root}")
    return cfg


def set_projects_root(path: Optional[str]) -> dict:
    """Set the folder that holds all project folders and create it if needed."""
    cfg = load_config()

    if not path:
        try:
            path = input(f"Projects root [{cfg.get('projects_root') or ''}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[workspace] Cancelled.")
            return cfg

    if not path:
        print("[workspace] No change made.")
        return cfg

    root = Path(path).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    cfg["projects_root"] = str(root)
    save_config(cfg)
    print(f"[workspace] Projects root set -> {root}")
    return cfg


def get_projects_root() -> Path:
    """Return the resolved projects root, creating it if necessary."""
    cfg = load_config()
    root = Path(cfg.get("projects_root") or "").expanduser()
    if not root:
        root = Path(cfg.get("workspace_path") or "").expanduser().parent / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def list_projects() -> list[str]:
    """List the names of project folders inside the projects root."""
    root = get_projects_root()
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def select_project(name: str) -> dict:
    """Activate a project folder inside the projects root, creating it if missing."""
    cfg = load_config()
    root = cfg.get("projects_root", "")
    if not root:
        raise ValueError("No projects_root set. Run /projects_root <path> first.")

    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("Invalid project name.")

    project_path = Path(root).expanduser() / name
    created = False
    if not project_path.exists():
        project_path.mkdir(parents=True, exist_ok=True)
        created = True

    cfg["workspace_path"] = str(project_path.resolve())
    save_config(cfg)
    return {"status": "created" if created else "activated", "path": str(project_path.resolve())}


def set_project(project_name: Optional[str]) -> dict:
    """Create/select a project folder inside the projects root and activate it."""
    cfg = load_config()

    if not project_name:
        try:
            project_name = input("Project name: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[workspace] Cancelled.")
            return cfg

    if not project_name:
        print("[workspace] No change made.")
        return cfg

    projects_root = get_projects_root()
    candidate = Path(project_name).expanduser()
    if candidate.is_absolute():
        raise ValueError("Project names must be relative to the projects root.")

    target = (projects_root / candidate).resolve()
    try:
        common = os.path.commonpath([str(projects_root), str(target)])
    except Exception as exc:
        raise ValueError("Invalid project path") from exc

    if common != str(projects_root):
        raise ValueError("Project path escapes the projects root.")

    target.mkdir(parents=True, exist_ok=True)
    cfg["workspace_path"] = str(target)
    save_config(cfg)
    print(f"[workspace] Project selected -> {target}")
    return cfg


def resolve_path(rel: str) -> Path:
    """Resolve *rel* against configured workspace root and ensure it stays inside.

    Raises ValueError on attempts to escape the workspace.
    """
    cfg = load_config()
    root = Path(cfg.get("workspace_path") or "").expanduser()
    if not root:
        raise ValueError("Workspace not configured. Use /workspace to set one.")

    root_resolved = root.resolve()

    # Reject absolute paths supplied by the caller to be strict
    p = Path(rel)
    if p.is_absolute():
        raise ValueError("Absolute paths are not allowed. Use paths relative to the workspace.")

    candidate = (root_resolved / p).resolve()

    # Ensure candidate is inside root_resolved
    try:
        common = os.path.commonpath([str(root_resolved), str(candidate)])
    except Exception:
        raise ValueError("Invalid path")

    if common != str(root_resolved):
        raise ValueError("Path escape detected: operation outside workspace is forbidden.")

    return candidate
