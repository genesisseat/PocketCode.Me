"""
history.py -- PocketCode Conversation / History Module
======================================================
Manages per-session chat history stored as JSONL files.

Storage layout
--------------
~/.pocketcode/
  sessions/
    20260706_195301_123456.jsonl   <-- one file per session
  state.json                       <-- current_session pointer

Each line in a .jsonl file is one message:
    {"role": "user"|"model", "content": "...", "ts": "<iso8601>"}

NOTE: Gemini uses "model" as the AI's role name (not "assistant").

Public API
----------
new_session()                          -> str
load_history(session_id=None)          -> list[dict]
append_message(role, content, sid)     -> None
list_sessions()                        -> list[str]
trim_history(max_messages, sid)        -> list[dict]
"""

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

POCKET_DIR   = Path.home() / ".pocketcode"
SESSIONS_DIR = POCKET_DIR / "sessions"
STATE_FILE   = POCKET_DIR / "state.json"

# Gemini roles -- no "assistant", no "system"
VALID_ROLES = {"user", "model", "function", "agent_a", "agent_b"}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _ensure_dirs() -> None:
    """Create ~/.pocketcode/sessions/ if it does not exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _secure(path: Path) -> None:
    """chmod 600 -- silently skipped on Windows."""
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _session_path(session_id: str) -> Path:
    """Resolve a session_id to its full .jsonl path."""
    return SESSIONS_DIR / f"{session_id}.jsonl"


# ------------------------------------------------------------------
# State file (current_session pointer)
# ------------------------------------------------------------------

def _load_state() -> dict:
    """Load ~/.pocketcode/state.json, returning {} on any error."""
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    """Persist state dict to ~/.pocketcode/state.json (chmod 600)."""
    _ensure_dirs()
    try:
        with STATE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
        _secure(STATE_FILE)
    except OSError as exc:
        print(f"[history] Error saving state: {exc}", file=sys.stderr)


def _get_current_session_id():
    """Return the current session_id from state.json, or None."""
    return _load_state().get("current_session")


def _set_current_session_id(session_id: str) -> None:
    """Update the current_session pointer in state.json."""
    state = _load_state()
    state["current_session"] = session_id
    _save_state(state)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def new_session() -> str:
    """
    Create a fresh session, update the current_session pointer, and
    return the new session_id.

    The session_id is a timestamp string: YYYYMMDD_HHMMSS_ffffff
    (microseconds included to avoid collisions).
    """
    _ensure_dirs()

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = _session_path(session_id)

    # Touch the file and lock it down
    path.touch(exist_ok=True)
    _secure(path)

    _set_current_session_id(session_id)
    print(f"[history] New session started -> {path}")
    return session_id


def load_history(session_id: str = None) -> list:
    """
    Load all messages for the given session.

    Parameters
    ----------
    session_id : str, optional
        Session to load.  Defaults to the current active session.
        If no session exists at all, new_session() is called.

    Returns
    -------
    list[dict]
        Ordered list of message dicts:
        {"role": str, "content": str, "ts": str}.
    """
    if session_id is None:
        session_id = _get_current_session_id()

    if session_id is None:
        session_id = new_session()

    path = _session_path(session_id)

    if not path.exists():
        return []

    messages = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(
                        f"[history] Skipping malformed line {lineno} "
                        f"in {path.name}: {exc}",
                        file=sys.stderr,
                    )
    except OSError as exc:
        print(f"[history] Could not read session file: {exc}", file=sys.stderr)

    return messages


def append_message(role: str, content: str, session_id: str = None) -> None:
    """
    Append a single message to the session's JSONL file.

    Parameters
    ----------
    role : str
        ``"user"`` or ``"model"`` (Gemini's role for AI replies).
    content : str
        The message text.
    session_id : str, optional
        Target session.  Defaults to the current active session.

    Raises
    ------
    ValueError
        If *role* is not one of the recognised values.
    """
    if role not in VALID_ROLES:
        raise ValueError(
            f"[history] Invalid role '{role}'. Must be one of {VALID_ROLES}."
        )

    if session_id is None:
        session_id = _get_current_session_id()

    if session_id is None:
        session_id = new_session()

    _ensure_dirs()
    path = _session_path(session_id)

    message = {"role": role, "content": content, "ts": _now_iso()}
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(message, ensure_ascii=False) + "\n")
        _secure(path)
    except OSError as exc:
        print(f"[history] Could not write message: {exc}", file=sys.stderr)


def trim_history(max_messages: int, session_id: str = None) -> list:
    """
    Keep only the most recent *max_messages* entries in the session file.
    The file is rewritten via a safe rename.
    """
    if max_messages < 1:
        raise ValueError("[history] max_messages must be >= 1.")

    if session_id is None:
        session_id = _get_current_session_id()

    if session_id is None:
        return []

    messages = load_history(session_id)
    if len(messages) <= max_messages:
        return messages  # nothing to do

    trimmed = messages[-max_messages:]
    path = _session_path(session_id)
    tmp_path = path.with_suffix(".jsonl.tmp")

    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            for msg in trimmed:
                fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        _secure(tmp_path)
        tmp_path.replace(path)
    except OSError as exc:
        print(f"[history] Could not trim session file: {exc}", file=sys.stderr)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return messages

    removed = len(messages) - len(trimmed)
    print(f"[history] Trimmed {removed} old message(s). Keeping {len(trimmed)}.")
    return trimmed


def list_sessions() -> list:
    """Return a sorted list of all session_ids (oldest first)."""
    _ensure_dirs()
    return sorted(
        p.stem for p in SESSIONS_DIR.glob("*.jsonl") if not p.stem.endswith(".tmp")
    )
