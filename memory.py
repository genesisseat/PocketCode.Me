"""
memory.py -- PocketCode memory management
=======================================
Stores user details and preferences in a small JSON file so the assistant
can remember them across sessions.
"""

import json
import os
import stat
import sys
from pathlib import Path

POCKET_DIR = Path.home() / ".pocketcode"
MEMORY_FILE = POCKET_DIR / "memory.json"

DEFAULT_MEMORY = {
    "details": [],
    "preferences": {},
}


def _ensure_dir() -> None:
    POCKET_DIR.mkdir(parents=True, exist_ok=True)


def _secure(path: Path) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_memory() -> dict:
    _ensure_dir()
    if not MEMORY_FILE.exists():
        save_memory(dict(DEFAULT_MEMORY))
        return dict(DEFAULT_MEMORY)

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[memory] Warning: could not read memory ({exc}). Using defaults.")
        return dict(DEFAULT_MEMORY)

    normalized = dict(DEFAULT_MEMORY)
    normalized.update({
        "details": list(data.get("details", [])) if isinstance(data.get("details"), list) else [],
        "preferences": dict(data.get("preferences", {})) if isinstance(data.get("preferences"), dict) else {},
    })
    if normalized != data:
        save_memory(normalized)
    return normalized


def save_memory(data: dict) -> None:
    _ensure_dir()
    try:
        with MEMORY_FILE.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        print(f"[memory] Error: could not write memory -- {exc}", file=sys.stderr)
        return
    _secure(MEMORY_FILE)


def remember_detail(detail: str) -> dict:
    detail = (detail or "").strip()
    if not detail:
        return load_memory()

    data = load_memory()
    if detail not in data["details"]:
        data["details"].append(detail)
        save_memory(data)
    return data


def remember_preference(key: str, value: str) -> dict:
    key = (key or "").strip()
    value = (value or "").strip()
    if not key or not value:
        return load_memory()

    data = load_memory()
    data["preferences"][key] = value
    save_memory(data)
    return data


def forget_memory_entry(key: str) -> bool:
    key = (key or "").strip()
    if not key:
        return False

    data = load_memory()
    if key in data["preferences"]:
        del data["preferences"][key]
        save_memory(data)
        return True

    if key in data["details"]:
        data["details"].remove(key)
        save_memory(data)
        return True

    return False


def build_memory_context() -> str:
    data = load_memory()
    lines = []
    if data["details"]:
        lines.append("User details:")
        lines.extend(f"- {item}" for item in data["details"])
    if data["preferences"]:
        lines.append("Preferences:")
        for key, value in sorted(data["preferences"].items()):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)
