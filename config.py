"""
config.py -- PocketCode Config Module (Gemini-only)
====================================================
Manages persistent configuration stored at ~/.pocketcode/config.json
with restricted file permissions (chmod 600).

Only two fields:
    api_key  --  Google AI Studio API key
    model    --  Gemini/Gemma model name

Public API
----------
load_config()              -> dict
save_config(cfg: dict)     -> None
set_key(key: str)          -> dict
set_model(model: str)      -> dict
show_config(cfg: dict)     -> None
"""

import json
import os
import stat
import sys
from pathlib import Path

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

CONFIG_DIR  = Path.home() / ".pocketcode"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict = {
    "api_key": "",
    "model":   "gemini-2.5-flash",
    "workspace_path": str(CONFIG_DIR / "workspace"),
    "projects_root": str(CONFIG_DIR / "projects"),
}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _ensure_dir() -> None:
    """Create ~/.pocketcode/ if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _secure_file(path: Path) -> None:
    """
    Apply chmod 600 (owner read/write only).
    On Windows this is silently skipped -- Windows uses ACLs.
    """
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def load_config() -> dict:
    """
    Load configuration from ~/.pocketcode/config.json.

    If the file does not exist the default config is written and
    returned.  Missing keys are back-filled from DEFAULTS so that
    older config files stay forward-compatible.
    """
    _ensure_dir()

    if not CONFIG_FILE.exists():
        print(f"[config] No config found -- creating default at {CONFIG_FILE}")
        save_config(dict(DEFAULTS))
        return dict(DEFAULTS)

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as fh:
            cfg: dict = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[config] Warning: could not read config ({exc}). Using defaults.")
        return dict(DEFAULTS)

    # Back-fill any keys added since the file was first written
    changed = False
    for key, default_val in DEFAULTS.items():
        if key not in cfg:
            cfg[key] = default_val
            changed = True

    if changed:
        save_config(cfg)

    return cfg


def save_config(cfg: dict) -> None:
    """Write *cfg* to ~/.pocketcode/config.json and apply chmod 600."""
    _ensure_dir()

    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        print(f"[config] Error: could not write config -- {exc}", file=sys.stderr)
        return

    _secure_file(CONFIG_FILE)
    print(f"[config] Saved -> {CONFIG_FILE}")


def set_key(key: str = "") -> dict:
    """
    Set (or interactively prompt for) the Google AI Studio API key.

    Parameters
    ----------
    key : str
        The API key.  If empty the user is prompted via stdin.

    Returns
    -------
    dict   The updated configuration.
    """
    cfg = load_config()

    if not key:
        try:
            key = input("Enter Google AI Studio API key: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[config] Cancelled.")
            return cfg

    if not key:
        print("[config] API key was not changed (empty input).")
        return cfg

    cfg["api_key"] = key
    save_config(cfg)
    print("[config] API key updated.")
    return cfg


def set_model(model: str = "") -> dict:
    """
    Update the active Gemini/Gemma model name and persist it.

    Parameters
    ----------
    model : str
        Model identifier (e.g. ``gemini-2.5-flash``).
        If empty the user is prompted via stdin.

    Returns
    -------
    dict   The updated configuration.
    """
    cfg = load_config()

    if not model:
        try:
            current = cfg.get("model", DEFAULTS["model"])
            model = input(f"Enter model name [{current}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[config] Cancelled.")
            return cfg

    if not model:
        print("[config] Model was not changed (empty input).")
        return cfg

    cfg["model"] = model
    save_config(cfg)
    print(f"[config] Model updated -> {model}")
    return cfg


def show_config(cfg: dict = None) -> None:
    """
    Pretty-print the current configuration.
    The api_key value is masked to hide all but the last 4 characters.
    """
    if cfg is None:
        cfg = load_config()

    # Build a display-safe copy (mask the key)
    display = dict(cfg)
    raw_key: str = display.get("api_key", "")
    if raw_key:
        if len(raw_key) > 4:
            display["api_key"] = "*" * (len(raw_key) - 4) + raw_key[-4:]
        else:
            display["api_key"] = "****"
    else:
        display["api_key"] = "(not set)"

    print("\n+-- PocketCode Config -------------------------------------------")
    for k, v in display.items():
        print(f"|  {k:<12} : {v}")
    print(f"|  config_file : {CONFIG_FILE}")
    # show workspace path explicitly
    ws = display.get("workspace_path", "(not set)")
    print(f"|  workspace_path: {ws}")
    print("+---------------------------------------------------------------\n")
