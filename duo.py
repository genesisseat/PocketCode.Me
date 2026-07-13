"""
duo.py -- PocketCode Two-Agent Relay Mode
========================================
Runs a single user task through two agents sequentially:
    user_message -> Agent A -> Agent B -> final reply
"""

from api import APIError, send_message
from config import load_config


def _build_duo_context(history: list, max_turns: int = 6) -> str:
    """Build a compact transcript from recent duo-aware history turns."""
    turns = []
    for msg in history[-max_turns * 3:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in {"user", "agent_a", "agent_b"} and content:
            label = {
                "user": "User",
                "agent_a": "Agent A",
                "agent_b": "Agent B",
            }.get(role, role)
            turns.append(f"{label}: {content}")

    if not turns:
        return ""
    return "\n".join(turns)


def run_duo_turn(user_message: str, history: list, status_cb=None) -> dict:
    """
    Run the two-agent relay for one user turn.

    Returns a dict with the Agent A draft and the final Agent B reply.
    """
    cfg = load_config()
    duo_cfg = cfg.get("duo_mode", {}) or {}
    agent_a = duo_cfg.get("agent_a", {}) or {}
    agent_b = duo_cfg.get("agent_b", {}) or {}

    if status_cb:
        status_cb("-> Agent A drafting...")

    a_cfg = dict(cfg)
    a_cfg["model"] = agent_a.get("model", cfg.get("model"))

    transcript = _build_duo_context(history)
    prompt_a = f"{agent_a.get('persona', '').strip()}\n\n"
    if transcript:
        prompt_a += f"Conversation so far:\n{transcript}\n\n"
    prompt_a += f"New user message: {user_message}"

    a_messages = list(history) + [{"role": "user", "content": prompt_a.strip()}]
    draft = send_message(a_messages, cfg=a_cfg, tools_enabled=False)

    if status_cb:
        status_cb("-> Agent B refining...")

    b_cfg = dict(cfg)
    b_cfg["model"] = agent_b.get("model", cfg.get("model"))

    b_prompt = (
        f"{agent_b.get('persona', '').strip()}\n\n"
        f"Conversation so far:\n{transcript}\n\n"
        f"New user message: {user_message}\n\n"
        f"First draft from another assistant:\n{draft}\n\n"
        f"Provide the improved final response."
    ).strip()

    b_messages = list(history) + [{"role": "user", "content": b_prompt}]
    final = send_message(b_messages, cfg=b_cfg, tools_enabled=True, status_cb=status_cb)

    return {"final": final, "draft": draft}
