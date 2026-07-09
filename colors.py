"""
colors.py -- PocketCode ANSI Color Helpers (Claude Code palette)
================================================================
256-color palette inspired by Claude Code's terminal interface.
Dark background, warm orange accents, muted grays.
"""

import os
import sys

# ------------------------------------------------------------------
# UTF-8 stdout (needed on Windows for box-drawing chars)
# ------------------------------------------------------------------

def _ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 on Windows so box chars don't crash."""
    try:
        if os.name == "nt" and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ensure_utf8_stdout()


# ------------------------------------------------------------------
# ANSI detection
# ------------------------------------------------------------------

def _enable_windows_vt100() -> bool:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


def _detect_ansi() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.name == "nt":
        if _enable_windows_vt100():
            return True
        term = os.environ.get("TERM", "")
        return "256color" in term or "xterm" in term
    return True


ANSI_ENABLED: bool = _detect_ansi()


# ------------------------------------------------------------------
# Reset
# ------------------------------------------------------------------

RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"

# ------------------------------------------------------------------
# Theme presets
# ------------------------------------------------------------------

THEMES = {
    "claude-dark": {
        "ORANGE": "\033[38;5;208m",
        "AMBER": "\033[38;5;214m",
        "PEACH": "\033[38;5;216m",
        "WHITE": "\033[38;5;255m",
        "LIGHT_GRAY": "\033[38;5;250m",
        "MID_GRAY": "\033[38;5;243m",
        "DARK_GRAY": "\033[38;5;238m",
        "SOFT_BLUE": "\033[38;5;111m",
        "SOFT_GREEN": "\033[38;5;114m",
        "SOFT_RED": "\033[38;5;203m",
        "SOFT_PURPLE": "\033[38;5;141m",
        "TEAL": "\033[38;5;73m",
        "ORANGE_BG": "\033[48;5;208m",
    },
    "claude-light": {
        "ORANGE": "\033[38;5;166m",
        "AMBER": "\033[38;5;172m",
        "PEACH": "\033[38;5;180m",
        "WHITE": "\033[38;5;236m",
        "LIGHT_GRAY": "\033[38;5;238m",
        "MID_GRAY": "\033[38;5;240m",
        "DARK_GRAY": "\033[38;5;245m",
        "SOFT_BLUE": "\033[38;5;67m",
        "SOFT_GREEN": "\033[38;5;65m",
        "SOFT_RED": "\033[38;5;124m",
        "SOFT_PURPLE": "\033[38;5;61m",
        "TEAL": "\033[38;5;30m",
        "ORANGE_BG": "\033[48;5;223m",
    },
    "dracula": {
        "ORANGE": "\033[38;5;212m",
        "AMBER": "\033[38;5;215m",
        "PEACH": "\033[38;5;218m",
        "WHITE": "\033[38;5;255m",
        "LIGHT_GRAY": "\033[38;5;252m",
        "MID_GRAY": "\033[38;5;246m",
        "DARK_GRAY": "\033[38;5;238m",
        "SOFT_BLUE": "\033[38;5;117m",
        "SOFT_GREEN": "\033[38;5;84m",
        "SOFT_RED": "\033[38;5;203m",
        "SOFT_PURPLE": "\033[38;5;141m",
        "TEAL": "\033[38;5;45m",
        "ORANGE_BG": "\033[48;5;61m",
    },
    "solarized-dark": {
        "ORANGE": "\033[38;5;136m",
        "AMBER": "\033[38;5;142m",
        "PEACH": "\033[38;5;180m",
        "WHITE": "\033[38;5;254m",
        "LIGHT_GRAY": "\033[38;5;245m",
        "MID_GRAY": "\033[38;5;240m",
        "DARK_GRAY": "\033[38;5;238m",
        "SOFT_BLUE": "\033[38;5;67m",
        "SOFT_GREEN": "\033[38;5;64m",
        "SOFT_RED": "\033[38;5;124m",
        "SOFT_PURPLE": "\033[38;5;61m",
        "TEAL": "\033[38;5;37m",
        "ORANGE_BG": "\033[48;5;60m",
    },
    "tokyo-night": {
        "ORANGE": "\033[38;5;216m",
        "AMBER": "\033[38;5;179m",
        "PEACH": "\033[38;5;181m",
        "WHITE": "\033[38;5;255m",
        "LIGHT_GRAY": "\033[38;5;252m",
        "MID_GRAY": "\033[38;5;246m",
        "DARK_GRAY": "\033[38;5;239m",
        "SOFT_BLUE": "\033[38;5;117m",
        "SOFT_GREEN": "\033[38;5;114m",
        "SOFT_RED": "\033[38;5;203m",
        "SOFT_PURPLE": "\033[38;5;141m",
        "TEAL": "\033[38;5;80m",
        "ORANGE_BG": "\033[48;5;60m",
    },
}

CURRENT_THEME = "claude-dark"


def _apply_palette(theme_name: str) -> None:
    palette = THEMES[theme_name]
    for key, value in palette.items():
        globals()[key] = value

    globals()["COL_YOU"] = BOLD + AMBER
    globals()["COL_AI"] = BOLD + PEACH
    globals()["COL_SYS"] = MID_GRAY
    globals()["COL_ERROR"] = BOLD + SOFT_RED
    globals()["COL_HEADER"] = BOLD + ORANGE
    globals()["COL_DIM"] = ORANGE
    globals()["COL_MODEL"] = BOLD + SOFT_PURPLE
    globals()["COL_CMD"] = TEAL
    globals()["COL_OK"] = SOFT_GREEN
    globals()["COL_INFO"] = SOFT_BLUE


def get_theme_names() -> list[str]:
    return list(THEMES.keys())


def get_current_theme() -> str:
    return CURRENT_THEME


def set_theme(theme_name: str | None = None) -> str:
    normalized = (theme_name or "claude-dark").strip().lower()
    if normalized not in THEMES:
        raise ValueError(f"Unknown theme: {theme_name}")
    globals()["CURRENT_THEME"] = normalized
    _apply_palette(normalized)
    return normalized


# Initialize the default palette
set_theme(CURRENT_THEME)


# ------------------------------------------------------------------
# Box-drawing characters (thick style)
# ------------------------------------------------------------------

# When ANSI + UTF-8 available, use heavy/double-line chars
# Fallback to ASCII otherwise

if ANSI_ENABLED:
    BOX_TL  = "╔"    # top-left
    BOX_TR  = "╗"    # top-right
    BOX_BL  = "╚"    # bottom-left
    BOX_BR  = "╝"    # bottom-right
    BOX_H   = "═"    # horizontal
    BOX_V   = "║"    # vertical
    BOX_SEP = "─"    # thin separator
    BULLET  = "●"    # bullet point
    ARROW   = "▸"    # arrow indicator
    DOT     = "·"    # middle dot
else:
    BOX_TL  = "+"
    BOX_TR  = "+"
    BOX_BL  = "+"
    BOX_BR  = "+"
    BOX_H   = "="
    BOX_V   = "|"
    BOX_SEP = "-"
    BULLET  = "*"
    ARROW   = ">"
    DOT     = "."


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def c(codes: str, text: str) -> str:
    """Wrap text in ANSI codes. Returns plain text if ANSI not supported."""
    if not ANSI_ENABLED:
        return text
    return f"{codes}{text}{RESET}"


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)
