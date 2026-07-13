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
API_KEYS_FILE = CONFIG_DIR / "api_keys.json"

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


def _load_key_drawer() -> dict:
    _ensure_dir()
    if not API_KEYS_FILE.exists():
        drawer = {"active_name": "default", "keys": []}
        _save_key_drawer(drawer)
        return drawer

    try:
        with API_KEYS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"active_name": "default", "keys": []}

    if not isinstance(data, dict):
        return {"active_name": "default", "keys": []}

    keys = data.get("keys", [])
    if not isinstance(keys, list):
        keys = []

    return {
        "active_name": data.get("active_name") or "default",
        "keys": keys,
    }


def _save_key_drawer(drawer: dict) -> None:
    _ensure_dir()
    try:
        with API_KEYS_FILE.open("w", encoding="utf-8") as fh:
            json.dump(drawer, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        print(f"[config] Error: could not write API key drawer -- {exc}", file=sys.stderr)


def set_key(key: str = "", name: str = "") -> dict:
    """Store an API key in the drawer and make it the active key."""
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

    if not name:
        name = "default"

    drawer = _load_key_drawer()
    keys = drawer.get("keys", [])
    if not isinstance(keys, list):
        keys = []

    existing = None
    for item in keys:
        if isinstance(item, dict) and item.get("name") == name:
            existing = item
            break

    if existing is None:
        keys.append({"name": name, "key": key})
    else:
        existing["key"] = key

    drawer["keys"] = keys
    drawer["active_name"] = name
    _save_key_drawer(drawer)
    cfg["api_key"] = key
    save_config(cfg)
    print(f"[config] API key updated for '{name}'.")
    return cfg


def switch_key(name: str) -> dict:
    """Switch the active API key to one stored in the drawer."""
    cfg = load_config()
    drawer = _load_key_drawer()
    keys = drawer.get("keys", [])
    for item in keys:
        if isinstance(item, dict) and item.get("name") == name:
            drawer["active_name"] = name
            _save_key_drawer(drawer)
            cfg["api_key"] = item.get("key", "")
            save_config(cfg)
            print(f"[config] Switched to API key '{name}'.")
            return cfg

    print(f"[config] No saved API key named '{name}'.")
    return cfg


def list_keys() -> list[dict]:
    """Return the stored API key drawer entries."""
    drawer = _load_key_drawer()
    keys = drawer.get("keys", [])
    if not isinstance(keys, list):
        return []
    return keys


def get_active_key_name() -> str:
    """Return the name of the currently active key in the drawer."""
    drawer = _load_key_drawer()
    return drawer.get("active_name") or "default"


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
