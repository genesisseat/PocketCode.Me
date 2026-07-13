"""GitHub helper module for PocketCode.

Provides a minimal authentication flow for GitHub API access. The user must
authenticate first by providing a personal access token.
"""

import json
import os
import stat
import urllib.request
from pathlib import Path

GITHUB_CONFIG_DIR = Path.home() / ".pocketcode"
GITHUB_TOKEN_FILE = GITHUB_CONFIG_DIR / "github_token.json"


def _ensure_dir() -> None:
    GITHUB_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _secure(path: Path) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def authenticate_github(token: str) -> dict:
    token = (token or "").strip()
    if not token:
        return {}
    _ensure_dir()
    data = {"token": token}
    with GITHUB_TOKEN_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    _secure(GITHUB_TOKEN_FILE)
    return data


def logout_github() -> None:
    if GITHUB_TOKEN_FILE.exists():
        GITHUB_TOKEN_FILE.unlink(missing_ok=True)


def is_authenticated() -> bool:
    if not GITHUB_TOKEN_FILE.exists():
        return False
    try:
        with GITHUB_TOKEN_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("token", ""))


def github_status() -> str:
    if is_authenticated():
        return "GitHub authenticated"
    return "GitHub not authenticated"


def _read_token() -> str:
    if not GITHUB_TOKEN_FILE.exists():
        return ""
    try:
        with GITHUB_TOKEN_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get("token", ""))


def list_repositories() -> list[str]:
    token = _read_token()
    if not token:
        raise RuntimeError("GitHub not authenticated. Run /github-auth <token> first.")

    req = urllib.request.Request(
        "https://api.github.com/user/repos?per_page=5",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return [item.get("name") for item in data if isinstance(item, dict) and item.get("name")]
