"""
repl.py -- PocketCode Gemini CLI (minimal interface)
===================================================
Compact, low-visual-noise terminal UI with simple borders and concise status blocks.
"""

import json
import shutil
import textwrap
import urllib.request
from pathlib import Path

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
from config import get_active_key_name, list_keys, load_config, save_config, show_config, switch_key
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
from memory import (
    build_memory_context,
    forget_memory_entry,
    load_memory,
    remember_detail,
    remember_preference,
)
from github import (
    authenticate_github,
    github_status,
    is_authenticated,
    list_repositories,
    logout_github,
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

def _print_banner(cfg: dict) -> None:
    w = _w()
    model   = cfg.get("model", "?")
    key_ok  = bool(cfg.get("api_key", "").strip())
    session = _get_current_session_id() or "none"

    title = c(COL_HEADER, "PocketCode")
    print()
    print(_box_top(w))
    print(_box_line(f"{title}  {c(COL_DIM, 'Gemini CLI for Termux')}", w))
    print(_box_sep(w))
    print(_box_line(f"{c(COL_SYS, 'Model')}  {c(COL_MODEL, model)}", w))
    print(_box_line(f"{c(COL_SYS, 'Session')}  {c(COL_INFO, session[:30])}", w))
    print(_box_line(f"{c(COL_SYS, 'API Key')}  {'SET' if key_ok else 'NOT SET'}", w))
    print(_box_sep(w))
    print(_box_line(f"{c(COL_DIM, 'Type a message to chat')}  {c(COL_CMD, '/help')}", w))
    print(_box_bottom(w))
    print()


# ------------------------------------------------------------------
# /help
# ------------------------------------------------------------------

def cmd_help(cfg: dict | None = None) -> None:
    if cfg is None:
        cfg = load_config()

    search_state = c(COL_INFO, "ON") if cfg.get("enable_search") else c(COL_DIM, "OFF")
    shell_state = c(COL_INFO, "ON") if cfg.get("enable_shell") else c(COL_DIM, "OFF")

    cmds = [
        (f"/help",               "Show this help"),
        (f"/config",             "View current model and masked API key"),
        (f"/toggle-search",      None),
        (f"/toggle-shell",       None),
        (f"/key <api_key>",      "Set or update your active Google AI Studio key"),
        (f"/keys",               "List saved API keys and the active selection"),
        (f"/key <name> <api_key>", "Save a key under a name and make it active"),
        (f"/switch-key <name>",  "Switch to a saved API key by name"),
        (f"/model",              "List available models and switch"),
        (f"/workspace [path]",   "Set or show the active project folder"),
        (f"/projects-root [path]", "Set or show the root folder for projects"),
        (f"/projects",           "List existing projects and switch to one"),
        (f"/projects <name>",    "Create/select a project inside the projects root"),
        (f"/new",                "Start a new conversation session"),
        (f"/history",            "Show messages in the current session"),
        (f"/clear",              "Clear the current conversation"),
        (f"/status",             "Show session, model, and workspace summary"),
        (f"/save <file>",        "Export the current conversation to a text file"),
        (f"/memory",             "View or manage remembered details and preferences"),
        (f"/github-auth <token>", "Authenticate PocketCode with GitHub (personal access token)"),
        (f"/github-status",      "Show whether GitHub authentication is active"),
        (f"/github-repos",       "List your recent GitHub repositories"),
        (f"/github-logout",      "Remove stored GitHub authentication"),
        (f"/exit",               "Quit PocketCode"),
    ]

    lines = []
    for cmd, desc in cmds:
        if cmd == "/toggle-search":
            desc_text = f"Enable/disable web search tool for the assistant {search_state}"
            lines.append(f"  {c(COL_CMD, cmd):<30}  {desc_text}")
        elif cmd == "/toggle-shell":
            desc_text = f"Enable/disable shell execution tool for the assistant {shell_state}"
            lines.append(f"  {c(COL_CMD, cmd):<30}  {desc_text}")
        else:
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
        f"  {c(COL_SYS, 'Search')}   {c(COL_INFO, 'ON') if cfg.get('enable_search') else c(COL_DIM, 'OFF')}",
        f"  {c(COL_SYS, 'Shell')}    {c(COL_INFO, 'ON') if cfg.get('enable_shell') else c(COL_DIM, 'OFF')}",
        f"  {c(COL_SYS, 'Projects')} {c(COL_INFO, cfg.get('projects_root', '(not set)'))}",
        f"  {c(COL_SYS, 'Workspace')} {c(COL_INFO, cfg.get('workspace_path', '(not set)'))}",
    ]
    _print_box("Configuration", lines)


# ------------------------------------------------------------------
# /key <api_key>
# ------------------------------------------------------------------

def cmd_key(args: str, cfg: dict) -> dict:
    parts = args.split(maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        name = parts[0].strip()
        key = parts[1].strip()
        cfg = load_config()
        cfg["api_key"] = key
        cfg["active_api_key_name"] = name
        cfg.setdefault("api_keys", [])
        api_keys = cfg["api_keys"]
        if not isinstance(api_keys, list):
            api_keys = []
        existing = None
        for item in api_keys:
            if isinstance(item, dict) and item.get("name") == name:
                existing = item
                break
        if existing is None:
            api_keys.append({"name": name, "key": key})
        else:
            existing["key"] = key
        cfg["api_keys"] = api_keys
        save_config(cfg)
        _ok_msg(f"Saved API key '{name}' and made it active.")
        return cfg

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
    cfg["active_api_key_name"] = "default"
    cfg.setdefault("api_keys", [])
    api_keys = cfg["api_keys"]
    if not isinstance(api_keys, list):
        api_keys = []
    existing = None
    for item in api_keys:
        if isinstance(item, dict) and item.get("name") == "default":
            existing = item
            break
    if existing is None:
        api_keys.append({"name": "default", "key": key})
    else:
        existing["key"] = key
    cfg["api_keys"] = api_keys
    save_config(cfg)
    _ok_msg("API key updated.")
    return cfg


def cmd_keys(cfg: dict) -> None:
    items = list_keys()
    if not items:
        _sys_msg("No saved API keys yet.")
        return
    lines = []
    active = get_active_key_name()
    for item in items:
        name = item.get("name", "?")
        marker = c(COL_OK, " [active]") if name == active else ""
        lines.append(f"  {c(COL_SYS, name)}{marker}")
    _print_box("Saved API Keys", lines)


def cmd_switch_key(args: str, cfg: dict) -> dict:
    name = args.strip()
    if not name:
        _err_msg("Usage: /switch-key <name>")
        return cfg
    return switch_key(name)


def cmd_toggle_search(cfg: dict) -> dict:
    """Toggle the `enable_search` config flag."""
    on = bool(cfg.get("enable_search"))
    cfg["enable_search"] = not on
    save_config(cfg)
    state = "enabled" if cfg["enable_search"] else "disabled"
    _ok_msg(f"Web search tool {state}.")
    return cfg


def cmd_toggle_shell(cfg: dict) -> dict:
    """Toggle the `enable_shell` config flag."""
    on = bool(cfg.get("enable_shell"))
    cfg["enable_shell"] = not on
    save_config(cfg)
    state = "enabled" if cfg["enable_shell"] else "disabled"
    _ok_msg(f"Shell execution tool {state}.")
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


def cmd_status(session_id: str, cfg: dict) -> None:
    messages = load_history(session_id)
    model = cfg.get("model", "?")
    lines = [
        f"  {c(COL_SYS, 'Session')}  {c(COL_INFO, session_id[:20])}",
        f"  {c(COL_SYS, 'Messages')} {c(COL_INFO, str(len(messages)))}",
        f"  {c(COL_SYS, 'Model')}    {c(COL_MODEL, model)}",
        f"  {c(COL_SYS, 'Workspace')} {c(COL_INFO, cfg.get('workspace_path', '(not set)'))}",
    ]
    _print_box("Status", lines)


def cmd_save(session_id: str, path_str: str = "") -> None:
    if not path_str:
        _err_msg("Usage: /save <file-path>")
        return

    messages = load_history(session_id)
    export_path = Path(path_str).expanduser()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"[{role}] {content}")
    export_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    _ok_msg(f"Conversation exported to {export_path}")


def cmd_github_auth(args: str) -> None:
    token = args.strip()
    if not token:
        _err_msg("Usage: /github-auth <token>")
        return
    authenticate_github(token)
    _ok_msg("GitHub authentication stored.")


def cmd_github_status() -> None:
    _sys_msg(github_status())


def cmd_github_repos() -> None:
    if not is_authenticated():
        _err_msg("GitHub is not authenticated. Run /github-auth <token> first.")
        return
    try:
        repos = list_repositories()
    except Exception as exc:
        _err_msg(str(exc))
        return
    if not repos:
        _sys_msg("No repositories found.")
        return
    lines = [f"  {c(COL_SYS, repo)}" for repo in repos]
    _print_box("GitHub Repositories", lines)


def cmd_github_logout() -> None:
    logout_github()
    _ok_msg("GitHub authentication removed.")


def cmd_memory(args: str) -> None:
    if not args.strip():
        data = load_memory()
        lines = []
        if data.get("details"):
            lines.append(f"  {c(COL_SYS, 'Details')}")
            for item in data["details"]:
                lines.append(f"    - {item}")
        if data.get("preferences"):
            lines.append(f"  {c(COL_SYS, 'Preferences')}")
            for key, value in sorted(data["preferences"].items()):
                lines.append(f"    - {key}: {value}")
        if not lines:
            _sys_msg("No remembered details or preferences yet.")
            return
        _print_box("Memory", lines)
        return

    parts = args.split(maxsplit=1)
    if len(parts) == 2 and parts[0].lower() in {"remember", "rem", "add"}:
        remember_detail(parts[1])
        _ok_msg(f"Remembered detail: {parts[1]}")
        return

    if len(parts) == 2 and parts[0].lower() in {"preference", "pref"}:
        key, value = parts[1].split("=", 1)
        remember_preference(key.strip(), value.strip())
        _ok_msg(f"Stored preference: {key.strip()}={value.strip()}")
        return

    if len(parts) == 2 and parts[0].lower() in {"forget", "remove", "del"}:
        removed = forget_memory_entry(parts[1].strip())
        if removed:
            _ok_msg(f"Removed memory entry: {parts[1].strip()}")
        else:
            _sys_msg(f"No memory entry found for: {parts[1].strip()}")
        return

    _err_msg("Usage: /memory, /memory remember <detail>, /memory preference <key>=<value>, or /memory forget <key>")


# ------------------------------------------------------------------
# Chat turn -- thick response block
# ------------------------------------------------------------------

def chat_turn(user_input: str, session_id: str, cfg: dict) -> None:
    append_message("user", user_input, session_id)
    messages = load_history(session_id)

    memory_context = build_memory_context()
    if memory_context:
        memory_note = {
            "role": "user",
            "content": f"[User memory context]\n{memory_context}\nUse these details when answering.",
        }
        messages = [memory_note] + messages

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
    elif cmd == "keys":
        cmd_keys(cfg)
    elif cmd == "switch-key":
        cfg = cmd_switch_key(args, cfg)
    elif cmd == "toggle-search":
        cfg = cmd_toggle_search(cfg)
    elif cmd == "toggle-shell":
        cfg = cmd_toggle_shell(cfg)
    elif cmd == "model":
        cfg = cmd_model(cfg)
    elif cmd == "workspace":
        # /workspace [path] - set or show current workspace
        if args:
            cfg = workspace.set_workspace(args)
        else:
            ws = cfg.get("workspace_path") or "(not set)"
            _sys_msg(f"Workspace: {ws}")
    elif cmd in ("projects-root", "projects_root"):
        if args:
            cfg = workspace.set_projects_root(args)
        else:
            root = cfg.get("projects_root") or "(not set)"
            _sys_msg(f"Projects root: {root}")
    elif cmd in ("projects", "project", "switch-project"):
        if args:
            cfg = workspace.set_project(args)
            _ok_msg(f"Active workspace: {cfg.get('workspace_path')}")
        else:
            projects = workspace.list_projects()
            if not projects:
                _sys_msg("No projects yet. Use /projects <name> to create one.")
                return session_id, cfg

            _sys_msg("Projects:")
            for i, name in enumerate(projects, start=1):
                _sys_msg(f"  [{i}] {name}")

            try:
                raw = input(f"  {c(COL_SYS, 'Select project [1-{len(projects)}] or enter a name:')} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                _sys_msg("Cancelled.")
                return session_id, cfg

            if not raw:
                _sys_msg("Cancelled.")
                return session_id, cfg

            if raw.isdigit():
                choice = int(raw)
                if 1 <= choice <= len(projects):
                    cfg = workspace.set_project(projects[choice - 1])
                    _ok_msg(f"Active workspace: {cfg.get('workspace_path')}")
                    return session_id, cfg
                _err_msg(f"Enter 1-{len(projects)}.")
                return session_id, cfg

            cfg = workspace.set_project(raw)
            _ok_msg(f"Active workspace: {cfg.get('workspace_path')}")
    elif cmd == "new":
        session_id = cmd_new()
    elif cmd == "history":
        cmd_history(session_id)
    elif cmd == "clear":
        cmd_clear(session_id)
    elif cmd == "status":
        cmd_status(session_id, cfg)
    elif cmd == "save":
        cmd_save(session_id, args)
    elif cmd == "memory":
        cmd_memory(args)
    elif cmd == "github-auth":
        cmd_github_auth(args)
    elif cmd == "github-status":
        cmd_github_status()
    elif cmd == "github-repos":
        cmd_github_repos()
    elif cmd == "github-logout":
        cmd_github_logout()
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
