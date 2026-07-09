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
# Claude Code-inspired 256-color palette
# ------------------------------------------------------------------

# Primary accent: warm orange/amber (Claude's signature)
ORANGE      = "\033[38;5;208m"    # #FF8700
AMBER       = "\033[38;5;214m"    # #FFAF00
PEACH       = "\033[38;5;216m"    # #FFAF87

# Text
WHITE       = "\033[38;5;255m"    # bright white
LIGHT_GRAY  = "\033[38;5;250m"    # readable body text
MID_GRAY    = "\033[38;5;243m"    # secondary / timestamps
DARK_GRAY   = "\033[38;5;238m"    # borders, rules

# Accent colors
SOFT_BLUE   = "\033[38;5;111m"    # info / session IDs
SOFT_GREEN  = "\033[38;5;114m"    # success / "SET"
SOFT_RED    = "\033[38;5;203m"    # errors / warnings
SOFT_PURPLE = "\033[38;5;141m"    # model name
TEAL        = "\033[38;5;73m"     # command names in help

# Background variants (for filled text / panels)
ORANGE_BG   = "\033[48;5;208m"

# ------------------------------------------------------------------
# Semantic aliases
# ------------------------------------------------------------------

COL_YOU     = BOLD + AMBER          # "You" prompt / label
COL_AI      = BOLD + PEACH          # "AI" label
COL_SYS     = MID_GRAY              # system info messages
COL_ERROR   = BOLD + SOFT_RED       # error messages
COL_HEADER  = BOLD + ORANGE         # box headers / banner
COL_DIM     = ORANGE                # borders, rules, decorative (Claude Code palette)
COL_MODEL   = BOLD + SOFT_PURPLE    # model name
COL_CMD     = TEAL                  # command names in /help
COL_OK      = SOFT_GREEN            # success indicators
COL_INFO    = SOFT_BLUE             # info text / session IDs


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
