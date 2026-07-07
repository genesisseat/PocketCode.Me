"""
workspace.py -- Secure workspace path handling
------------------------------------------------
Provides a simple sandbox root for AI-driven file ops. Ensures all
paths resolve under a configured workspace root and prevents path
traversal, absolute paths, or symlink escapes.

Public API:
  set_workspace(path: str | None) -> dict
  resolve_path(rel: str) -> pathlib.Path
"""

from pathlib import Path
import os
import json
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
