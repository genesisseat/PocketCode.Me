"""
repl.py -- PocketCode Gemini CLI (Claude Code-style interface)
===============================================================
Thick double-line borders, warm orange/amber palette, spacious layout.
"""

import json
import shutil
import textwrap

from api import APIError, GEMINI_BASE_URL, send_message
from colors import (
    ANSI_ENABLED,
    ARROW,
    BOX_BL,
    BOX_BR,
    BOX_H,
    BOX_SEP,
    BOX_TL,
    BOX_TR,
    BOX_V,
    BULLET,
    COL_AI,
    COL_CMD,
    COL_DIM,
    COL_ERROR,
    COL_HEADER,
    COL_INFO,
    COL_MODEL,
    COL_OK,
    COL_SYS,
    COL_YOU,
    DOT,
    RESET,
    c,
    strip_ansi,
    ORANGE_BG,
    WHITE,
)
from config import load_config, save_config, show_config
import workspace
import tools
from history import (
    _get_current_session_id,
    _session_path,
    append_message,
    list_sessions,
    load_history,
    new_session,
)

try:
    import readline  # noqa: F401
except ImportError:
    pass


# ------------------------------------------------------------------
# Hardcoded free-tier models
# ------------------------------------------------------------------

FREE_TIER_MODELS = [
    {"id": "gemini-2.5-flash",        "name": "Gemini 2.5 Flash",      "daily": "500 RPD"},
    {"id": "gemini-2.5-flash-lite",   "name": "Gemini 2.5 Flash Lite", "daily": "500 RPD"},
    {"id": "gemini-2.0-flash",        "name": "Gemini 2.0 Flash",      "daily": "500 RPD"},
    {"id": "gemini-2.0-flash-lite",   "name": "Gemini 2.0 Flash Lite", "daily": "500 RPD"},
    {"id": "gemma-3-27b-it",          "name": "Gemma 3 27B",           "daily": "500 RPD"},
]


# ------------------------------------------------------------------
# UI primitives -- thick Claude Code style
# ------------------------------------------------------------------

def _w() -> int:
    """Terminal width, capped at 80."""
    return min(shutil.get_terminal_size(fallback=(80, 24)).columns, 80)


def _hline(char=None) -> str:
    """Full-width horizontal line."""
    ch = char or BOX_H
    return ch * _w()


def _thin_rule() -> None:
    """Thin separator rule."""
    print(c(COL_DIM, BOX_SEP * _w()))


def _thick_rule() -> None:
    """Thick double-line rule."""
    print(c(COL_DIM, _hline()))


def _blank_box_line(w: int) -> str:
    """Empty padded box line."""
    inner = " " * (w - 2)
    return f"{c(COL_DIM, BOX_V)}{inner}{c(COL_DIM, BOX_V)}"


def _box_top(w: int) -> str:
    return c(COL_DIM, f"{BOX_TL}{BOX_H * (w - 2)}{BOX_TR}")


def _box_bottom(w: int) -> str:
    return c(COL_DIM, f"{BOX_BL}{BOX_H * (w - 2)}{BOX_BR}")


def _box_line(text: str, w: int, bg_fill: str = None, fg_for_text: str = "") -> str:
    """A box line with padded text inside.

    If `bg_fill` is provided (an ANSI background code like `ORANGE_BG`), the
    inner area (text + padding) will be filled using that background. Pass
    a foreground code in `fg_for_text` for readable text color on the fill.
    """
    raw = strip_ansi(text)
    pad = max(0, w - 4 - len(raw))
    inner = f"  {text}{' ' * pad}"

    if bg_fill and ANSI_ENABLED:
        codes = (bg_fill + (fg_for_text or ""))
        inner = c(codes, inner)

    return f"{c(COL_DIM, BOX_V)}{inner}{c(COL_DIM, BOX_V)}"


def _box_sep(w: int) -> str:
    """Thin separator inside a box."""
    return c(COL_DIM, f"{BOX_V}{BOX_SEP * (w - 2)}{BOX_V}")


def _print_box(title: str, lines: list) -> None:
    """Print a complete thick-bordered box with title and content lines."""
    w = _w()
    print()
    print(_box_top(w))
    print(_box_line(c(COL_HEADER, title), w))
    print(_box_sep(w))
    if lines:
        for line in lines:
            print(_box_line(line, w))
    else:
        print(_box_line(c(COL_DIM, "(empty)"), w))
    print(_box_bottom(w))
    print()


def _wrap_text(text: str, indent: int = 0) -> list:
    """Word-wrap text to terminal width minus indent."""
    w = _w()
    return textwrap.wrap(text, width=max(20, w - indent - 4))


def _sys_msg(text: str) -> None:
    print(f"  {c(COL_SYS, f'{BULLET} {text}')}")


def _err_msg(text: str) -> None:
    print(f"  {c(COL_ERROR, f'{BULLET} {text}')}")


def _ok_msg(text: str) -> None:
    print(f"  {c(COL_OK, f'{BULLET} {text}')}")


# ------------------------------------------------------------------
# Banner
# ------------------------------------------------------------------

BANNER_ART = r"""
     ____            _        _    ____          _
    |  _ \ ___   ___| | _____| |_ / ___|___   __| | ___
    | |_) / _ \ / __| |/ / _ \ __| |   / _ \ / _` |/ _ \
    |  __/ (_) | (__|   <  __/ |_| |__| (_) | (_| |  __/
    |_|   \___/ \___|_|\_\___|\__|\____\___/ \__,_|\___|
"""


def _print_banner(cfg: dict) -> None:
    w = _w()
    model   = cfg.get("model", "?")
    key_ok  = bool(cfg.get("api_key", "").strip())
    session = _get_current_session_id() or "none"

    print()
    print(_box_top(w))

    # Banner art lines (remove common leading indentation so art aligns)
    for line in textwrap.dedent(BANNER_ART).strip().splitlines():
        txt = line.rstrip()
        # Fill only the literal 'PocketCode' title line with orange background
        if "PocketCode" in txt:
            print(_box_line(txt, w, bg_fill=ORANGE_BG, fg_for_text=WHITE))
        else:
            print(_box_line(c(COL_HEADER, txt), w))

    print(_box_line("", w))
    print(_box_line(f"Gemini CLI for Termux {DOT} v1.0", w, bg_fill=ORANGE_BG, fg_for_text=WHITE))
    print(_box_sep(w))

    # Status rows
    key_status = c(COL_OK, "SET") if key_ok else c(COL_ERROR, "NOT SET")
    print(_box_line(
        f"{c(COL_SYS, 'Model')}   {c(COL_MODEL, model)}",
        w
    ))
    print(_box_line(
        f"{c(COL_SYS, 'Session')} {c(COL_INFO, session[:30])}",
        w
    ))
    print(_box_line(
        f"{c(COL_SYS, 'API Key')} {key_status}",
        w
    ))

    print(_box_sep(w))
    print(_box_line(f"Type a message to chat {DOT} /help for commands", w, bg_fill=ORANGE_BG, fg_for_text=WHITE))
    print(_box_bottom(w))
    print()


# ------------------------------------------------------------------
# /help
# ------------------------------------------------------------------

def cmd_help() -> None:
    cmds = [
        (f"/help",           "Show this help"),
        (f"/config",         "View current model and masked API key"),
        (f"/key <api_key>",  "Set or update your Google AI Studio key"),
        (f"/model",          "List available models and switch"),
        (f"/new",            "Start a new conversation session"),
        (f"/history",        "Show messages in the current session"),
        (f"/clear",          "Clear the current conversation"),
        (f"/exit",           "Quit PocketCode"),
    ]
    lines = []
    for cmd, desc in cmds:
        lines.append(f"  {c(COL_CMD, cmd):<30}  {c(COL_SYS, desc)}")
    _print_box("Commands", lines)


# ------------------------------------------------------------------
# /config
# ------------------------------------------------------------------

def cmd_config(cfg: dict) -> None:
    raw_key = cfg.get("api_key", "")
    if raw_key:
        masked = "*" * (len(raw_key) - 4) + raw_key[-4:] if len(raw_key) > 4 else "****"
    else:
        masked = c(COL_ERROR, "(not set)")

    model = cfg.get("model", "?")

    lines = [
        f"  {c(COL_SYS, 'API Key')}  {masked}",
        f"  {c(COL_SYS, 'Model')}    {c(COL_MODEL, model)}",
    ]
    _print_box("Configuration", lines)


# ------------------------------------------------------------------
# /key <api_key>
# ------------------------------------------------------------------

def cmd_key(args: str, cfg: dict) -> dict:
    key = args.strip()

    if not key:
        try:
            print()
            key = input(f"  {c(COL_SYS, 'Enter Google AI Studio API key:')} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _sys_msg("Cancelled.")
            return cfg

    if not key:
        _sys_msg("API key was not changed.")
        return cfg

    cfg["api_key"] = key
    save_config(cfg)
    _ok_msg("API key updated.")
    return cfg


# ------------------------------------------------------------------
# /model
# ------------------------------------------------------------------

def _fetch_live_models(api_key: str) -> list:
    url = f"{GEMINI_BASE_URL}/models?key={api_key}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    models = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        model_id = m.get("name", "").replace("models/", "")
        display  = m.get("displayName", model_id)
        if model_id:
            models.append({"id": model_id, "name": display})
    return models


def cmd_model(cfg: dict) -> dict:
    api_key = cfg.get("api_key", "").strip()
    models = []

    if api_key:
        _sys_msg("Fetching models from Google...")
        models = _fetch_live_models(api_key)

    if models:
        _ok_msg(f"Found {len(models)} model(s).")
    else:
        if api_key:
            _sys_msg("Could not fetch live. Using built-in list.")
        else:
            _sys_msg("No API key. Using built-in list.")
        models = list(FREE_TIER_MODELS)

    current = cfg.get("model", "")
    w = _w()

    lines = []
    for i, m in enumerate(models, start=1):
        marker = c(COL_OK, " (active)") if m["id"] == current else ""
        daily  = m.get("daily", "")
        daily_s = f"  {c(COL_DIM, daily)}" if daily else ""
        num = c(COL_HEADER, f"[{i:>2}]")
        lines.append(f"  {num} {m['name']:<28} {c(COL_DIM, m['id'])}{daily_s}{marker}")

    _print_box("Available Models", lines)

    while True:
        try:
            raw = input(f"  {c(COL_SYS, f'Select [1-{len(models)}]:')} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _sys_msg("Cancelled.")
            return cfg

        if not raw:
            _sys_msg("Cancelled.")
            return cfg

        try:
            choice = int(raw)
        except ValueError:
            _err_msg("Enter a number.")
            continue

        if 1 <= choice <= len(models):
            break
        _err_msg(f"Enter 1-{len(models)}.")

    selected = models[choice - 1]
    cfg["model"] = selected["id"]
    save_config(cfg)
    _ok_msg(f"Switched to {selected['name']} ({selected['id']})")
    return cfg


# ------------------------------------------------------------------
# /new
# ------------------------------------------------------------------

def cmd_new() -> str:
    session_id = new_session()
    _ok_msg(f"New session: {session_id}")
    return session_id


# ------------------------------------------------------------------
# /history
# ------------------------------------------------------------------

def cmd_history(session_id: str) -> None:
    messages = load_history(session_id)

    lines = []
    for msg in messages:
        role    = msg.get("role", "?")
        ts      = msg.get("ts", "")[:19].replace("T", " ")
        content = msg.get("content", "")
        snippet = (content[:90] + "...") if len(content) > 90 else content

        if role == "user":
            tag = c(COL_YOU, "YOU  ")
        else:
            tag = c(COL_AI, "AI   ")

        lines.append(f"  {c(COL_DIM, ts)}  {tag}  {snippet}")

    _print_box(f"Session {session_id[:20]}", lines)


# ------------------------------------------------------------------
# /clear
# ------------------------------------------------------------------

def cmd_clear(session_id: str) -> None:
    path = _session_path(session_id)
    if path.exists():
        path.write_text("", encoding="utf-8")
    _ok_msg("Conversation cleared.")


# ------------------------------------------------------------------
# Chat turn -- thick response block
# ------------------------------------------------------------------

def chat_turn(user_input: str, session_id: str, cfg: dict) -> None:
    append_message("user", user_input, session_id)
    messages = load_history(session_id)

    w = _w()
    print()

    try:
        # Enable tool-calling and provide a status callback for UI updates
        reply = send_message(
            messages,
            cfg=cfg,
            tools_enabled=True,
            status_cb=lambda s: _sys_msg(s),
        )
    except APIError as exc:
        print(c(COL_DIM, _hline(BOX_SEP)))
        _err_msg(str(exc))
        # If the API returned raw content include a truncated preview to aid debugging
        raw = getattr(exc, "raw", None)
        if raw:
            try:
                preview = raw if len(raw) < 1000 else raw[:1000] + "\n...[truncated]"
            except Exception:
                preview = str(raw)
            print(f"  [api raw] {preview}")
        _sys_msg("Check /config or run /key to fix.")
        print(c(COL_DIM, _hline(BOX_SEP)))
        print()
        return

    # AI response block with thick borders
    print(c(COL_DIM, _hline(BOX_SEP)))
    print()

    # Wrap the response text
    indent = 4
    wrapped = _wrap_text(reply, indent)
    prefix = f"  {c(COL_AI, f'{ARROW} AI')}"
    if wrapped:
        print(f"{prefix}  {wrapped[0]}")
        pad = " " * (len(strip_ansi(prefix)) + 2)
        for line in wrapped[1:]:
            print(f"{pad}{line}")
    else:
        print(prefix)

    print()
    print(c(COL_DIM, _hline(BOX_SEP)))
    print()

    append_message("model", reply, session_id)


# ------------------------------------------------------------------
# Command dispatcher
# ------------------------------------------------------------------

def _dispatch(raw_input: str, session_id: str, cfg: dict) -> tuple:
    parts = raw_input.lstrip("/").split(maxsplit=1)
    cmd   = parts[0].lower()
    args  = parts[1] if len(parts) > 1 else ""

    if cmd in ("exit", "quit", "q"):
        return None, None
    elif cmd == "help":
        cmd_help()
    elif cmd == "config":
        cmd_config(cfg)
    elif cmd == "key":
        cfg = cmd_key(args, cfg)
    elif cmd == "model":
        cfg = cmd_model(cfg)
    elif cmd == "workspace":
        # /workspace [path] - set or show current workspace
        if args:
            cfg = workspace.set_workspace(args)
        else:
            ws = cfg.get("workspace_path") or "(not set)"
            _sys_msg(f"Workspace: {ws}")
    elif cmd == "new":
        session_id = cmd_new()
    elif cmd == "history":
        cmd_history(session_id)
    elif cmd == "clear":
        cmd_clear(session_id)
    else:
        _err_msg(f"Unknown command: /{cmd}")
        _sys_msg("Type /help for commands.")

    return session_id, cfg


# ------------------------------------------------------------------
# Main REPL
# ------------------------------------------------------------------

def run_repl() -> None:
    """Launch the PocketCode interactive REPL."""
    cfg = load_config()

    session_id = _get_current_session_id()
    if not session_id:
        session_id = cmd_new()

    _print_banner(cfg)

    # Prompt -- clean Claude Code style
    prompt = f"{c(COL_YOU, ARROW)} " if ANSI_ENABLED else "> "

    while True:
        try:
            user_input = input(prompt).strip()
        except KeyboardInterrupt:
            print(f"\n  {c(COL_SYS, f'{BULLET} Ctrl-C -- type /exit to quit.')}")
            continue
        except EOFError:
            print(f"\n  {c(COL_SYS, f'{BULLET} Goodbye!')}")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            session_id, cfg = _dispatch(user_input, session_id, cfg)
            if session_id is None:
                print(f"  {c(COL_SYS, f'{BULLET} Goodbye!')}")
                break
        else:
            chat_turn(user_input, session_id, cfg)
