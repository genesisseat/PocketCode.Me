"""
tools.py -- Safe file operations routed through `workspace.resolve_path`
---------------------------------------------------------------
All filesystem operations resolve paths via `workspace.resolve_path` to
prevent path traversal or writes outside the configured workspace.

Dangerous operations prompt for confirmation before executing.
"""

from pathlib import Path
import shutil
import os
from typing import List

from workspace import resolve_path, select_project
from config import load_config
import subprocess
import urllib.parse
import urllib.request
import json


def _confirm(prompt: str) -> bool:
    try:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[tools] Cancelled.")
        return False
    return ans in ("y", "yes")


def list_dir(path: str | None = None, rel: str | None = None) -> List[str]:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    if not p.exists():
        raise FileNotFoundError(str(p))
    return sorted([x.name for x in p.iterdir()])


def read_file(path: str | None = None, rel: str | None = None) -> str:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding="utf-8")


def write_file(path: str | None = None, content: str = "", overwrite: bool = True, rel: str | None = None) -> str:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    if p.exists() and not overwrite:
        raise FileExistsError(str(p))

    preview = content if len(content) < 1000 else content[:1000] + "\n...[truncated]"
    if not _confirm(f"Write file {p}? Preview:\n{preview}"):
        return "declined"

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


def append_file(path: str | None = None, content: str = "", rel: str | None = None) -> str:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    preview = content if len(content) < 1000 else content[:1000] + "\n...[truncated]"
    if not _confirm(f"Append to {p}? Preview:\n{preview}"):
        return "declined"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return str(p)


def create_folder(path: str | None = None, rel: str | None = None) -> str:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    if p.exists():
        return str(p)
    if not _confirm(f"Create folder {p}?"):
        return "declined"
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def delete_file(path: str | None = None, rel: str | None = None) -> str:
    target = path if path is not None else rel
    if not target:
        raise ValueError("Missing required path")
    p = resolve_path(target)
    if not p.exists():
        raise FileNotFoundError(str(p))
    if not _confirm(f"Delete {p}? This cannot be undone."):
        return "declined"
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return str(p)


def move_or_rename(src_rel: str, dest_rel: str) -> str:
    src = resolve_path(src_rel)
    dest = resolve_path(dest_rel)
    if not src.exists():
        raise FileNotFoundError(str(src))
    if not _confirm(f"Move {src} -> {dest}?"):
        return "declined"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return str(dest)


def create_project(name: str) -> dict:
    """Create a project folder inside the projects root and activate it."""
    if not name:
        raise ValueError("Missing project name")
    if not _confirm(f"Create project '{name}'?"):
        return "declined"
    return select_project(name)


def get_tools_schema() -> list:
    """Return a list of JSON-schema-like declarations for Gemini function-calling.

    Each entry contains: name, description, and parameters (JSON schema object).
    Keep parameter shapes narrow and precise to avoid model confusion.
    """
    # Gemini expects a `tools` array containing an object with
    # a `functionDeclarations` array. Types use Gemini's dialect
    # (e.g. "OBJECT", "STRING").
    fns = [
        {
            "name": "list_dir",
            "description": "List filenames in a directory relative to the workspace root.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"path": {"type": "STRING", "description": "Relative path (e.g. '.')"}},
                "required": ["path"],
            },
        },
        {
            "name": "read_file",
            "description": "Read a UTF-8 text file under the workspace and return its contents.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"path": {"type": "STRING", "description": "Relative file path"}},
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Create or overwrite a file under the workspace. This requires user confirmation.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "path": {"type": "STRING"},
                    "content": {"type": "STRING"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "append_file",
            "description": "Append text to a file under the workspace. This requires user confirmation.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"path": {"type": "STRING"}, "content": {"type": "STRING"}},
                "required": ["path", "content"],
            },
        },
        {
            "name": "create_folder",
            "description": "Create a folder under the workspace. This requires user confirmation.",
            "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]},
        },
        {
            "name": "delete_file",
            "description": "Delete a file or folder under the workspace. This requires user confirmation.",
            "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]},
        },
        {
            "name": "move_or_rename",
            "description": "Move or rename a file within the workspace. This requires user confirmation.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"src": {"type": "STRING"}, "dest": {"type": "STRING"}},
                "required": ["src", "dest"],
            },
        },
        {
            "name": "list_projects",
            "description": "List existing project folders inside the projects root. Use this before creating a new project to check if one already exists.",
            "parameters": {"type": "OBJECT", "properties": {}, "required": []},
        },
        {
            "name": "create_project",
            "description": "Create a new project folder inside the projects root and activate it as the current workspace. Use this when the user asks to build something and no matching project folder exists yet.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"name": {"type": "STRING", "description": "Plain project folder name, e.g. 'coffee-shop'. No slashes or path separators."}},
                "required": ["name"],
            },
        },
    ]

    # Optionally include a web search tool and a shell execution tool
    cfg = load_config()
    if cfg.get("enable_search"):
        fns.append(
            {
                "name": "duckduckgo_search",
                "description": "Perform a web search using DuckDuckGo Instant Answer API and return summarized results.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Search query string"},
                        "max_results": {"type": "NUMBER", "description": "Max number of results to return"},
                    },
                    "required": ["query"],
                },
            }
        )

    if cfg.get("enable_shell"):
        fns.append(
            {
                "name": "run_shell",
                "description": "Run a shell command on the local machine (requires user confirmation). Returns stdout or an error message.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "command": {"type": "STRING", "description": "Shell command to run"},
                    },
                    "required": ["command"],
                },
            }
        )

    # Gemini expects tools to be an array containing an object with
    # `functionDeclarations` as shown in the spec.
    return [{"functionDeclarations": fns}]


def list_projects() -> list:
    """List project folder names inside the projects root."""
    from workspace import list_projects as _list_projects
    return _list_projects()


def duckduckgo_search(query: str, max_results: int = 5):
    """Perform a simple DuckDuckGo Instant Answer API query and return summarized results."""
    if not query:
        raise ValueError("Missing query")

    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "PocketCode/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Search failed: {exc}"}

    results = []
    # Preferred place: AbstractText or RelatedTopics
    abstract = data.get("AbstractText", "")
    if abstract:
        results.append({"title": data.get("Heading", "Summary"), "snippet": abstract, "url": data.get("AbstractURL", "")})

    related = data.get("RelatedTopics", [])
    for item in related:
        if isinstance(item, dict):
            if "Text" in item:
                results.append({"title": item.get("Text"), "snippet": item.get("Text"), "url": item.get("FirstURL", "")})
            elif "Topics" in item:
                for t in item.get("Topics", [])[:max_results]:
                    results.append({"title": t.get("Text"), "snippet": t.get("Text"), "url": t.get("FirstURL", "")})
        if len(results) >= max_results:
            break

    # Fallback: Results field
    ddg_results = data.get("Results", [])
    for r in ddg_results:
        if len(results) >= max_results:
            break
        results.append({"title": r.get("Text", ""), "snippet": r.get("Text", ""), "url": r.get("FirstURL", "")})

    # Trim to max_results
    results = results[:max_results]
    if not results:
        return {"query": query, "results": []}
    return {"query": query, "results": results}


def run_shell(command: str):
    """Run a shell command after user confirmation. Returns stdout or error."""
    if not command:
        raise ValueError("Missing command")

    try:
        ans = input(f"Run shell command? '{command}' [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "declined"
    if ans not in ("y", "yes"):
        return "declined"

    timeout = load_config().get("shell_timeout", 30)
    try:
        # Run command through shell for convenience but capture output
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout or ""
        err = proc.stderr or ""
        if proc.returncode != 0:
            return {"error": f"Exit {proc.returncode}", "stderr": err, "stdout": out}
        return {"stdout": out}
    except Exception as exc:
        return {"error": str(exc)}
