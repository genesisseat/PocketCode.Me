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

from workspace import resolve_path


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
    ]

    # Gemini expects tools to be an array containing an object with
    # `functionDeclarations` as shown in the spec.
    return [{"functionDeclarations": fns}]
