"""
duo.py -- PocketCode Two-Agent Relay Mode
========================================
Runs a single user task through two agents sequentially:
    user_message -> Agent A -> Agent B -> final reply
"""

from api import APIError, send_message
from config import load_config


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

    a_messages = list(history) + [
        {
            "role": "user",
            "content": f"{agent_a.get('persona', '').strip()}\n\n{user_message}".strip(),
        }
    ]
    draft = send_message(a_messages, cfg=a_cfg, tools_enabled=False)

    if status_cb:
        status_cb("-> Agent B refining...")

    b_cfg = dict(cfg)
    b_cfg["model"] = agent_b.get("model", cfg.get("model"))

    b_prompt = (
        f"{agent_b.get('persona', '').strip()}\n\n"
        f"User's request: {user_message}\n\n"
        f"First draft from another assistant:\n{draft}\n\n"
        f"Provide the improved final response."
    ).strip()

    b_messages = list(history) + [{"role": "user", "content": b_prompt}]
    final = send_message(b_messages, cfg=b_cfg, tools_enabled=True, status_cb=status_cb)

    return {"final": final, "draft": draft}
