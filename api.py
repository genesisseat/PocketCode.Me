"""
api.py -- PocketCode Gemini API Request Layer
==============================================
Talks directly to the Google AI Studio (Gemini) API.

Endpoint
--------
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}

Request format (Gemini contents/parts):
    {
      "contents": [
        {"role": "user",  "parts": [{"text": "hello"}]},
        {"role": "model", "parts": [{"text": "hi there!"}]}
      ]
    }

Response: candidates[0].content.parts[0].text

Public API
----------
send_message(messages, cfg=None)  -> str
    Convert saved history to Gemini format, POST, return reply text.
"""

import json
import sys
import urllib.error
import urllib.request

from config import load_config

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


# ------------------------------------------------------------------
# Format conversion
# ------------------------------------------------------------------

def _normalize_function_call(function_call: dict) -> dict:
    """Return a Gemini-compatible function call object using the documented schema."""
    if not isinstance(function_call, dict):
        return function_call

    normalized = dict(function_call)
    normalized.pop("thoughtSignature", None)
    normalized.pop("thought_signature", None)
    return normalized


def _to_gemini_contents(messages: list) -> list:
    """
    Convert our saved history format into Gemini's contents/parts format.

    Input  (from history.py):
        [{"role": "user", "content": "hello", "ts": "..."},
         {"role": "model", "content": "hi!", "ts": "..."}]

    Output (for Gemini API):
        [{"role": "user",  "parts": [{"text": "hello"}]},
         {"role": "model", "parts": [{"text": "hi!"}]}]

    Notes:
        - The "ts" field is stripped (Gemini doesn't use it).
        - Only "user" and "model" roles are included.
    """
    contents = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # user messages -> text parts
        if role == "user":
            if not content:
                continue
            parts = [{"text": str(content)}]

        # model messages -> could be text or a functionCall part
        elif role == "model":
            if isinstance(content, dict) and ("functionCall" in content or "function_call" in content):
                updated_content = dict(content)
                call_key = "function_call" if "function_call" in updated_content else "functionCall"
                updated_content[call_key] = _normalize_function_call(updated_content[call_key])
                parts = [updated_content]
            else:
                if not content:
                    continue
                parts = [{"text": str(content)}]

        # function messages -> functionResponse part
        elif role == "function":
            # content expected to be a dict like {"name": ..., "response": {...}}
            if not isinstance(content, dict):
                continue
            parts = [{"functionResponse": content}]

        elif role in ("agent_a", "agent_b"):
            # duo-mode roles are not sent in single-agent calls
            continue

        else:
            # skip any unknown roles
            continue

        contents.append({"role": role, "parts": parts})

    return contents


# ------------------------------------------------------------------
# Response parsing
# ------------------------------------------------------------------

def _parse_gemini_response(data: dict) -> str:
    """
    Extract the reply text from a Gemini generateContent response.

    Expected shape:
        {
          "candidates": [
            {
              "content": {
                "parts": [{"text": "..."}],
                "role": "model"
              }
            }
          ]
        }
    """
    try:
        candidates = data.get("candidates")
        if not candidates:
            # Check for a promptFeedback block (safety filter)
            feedback = data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "")
            if block_reason:
                raise ValueError(
                    f"Request blocked by safety filter: {block_reason}"
                )
            raise ValueError("Empty 'candidates' list in response.")

        candidate = candidates[0]
        parts = candidate["content"]["parts"]

        # Concatenate all text parts
        texts = [p["text"] for p in parts if "text" in p]
        if not texts:
            raise ValueError("No text parts found in candidate.")
        return "".join(texts)

    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Could not parse Gemini response: {exc}\nRaw: {data}"
        ) from exc


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

class APIError(Exception):
    """Raised for HTTP-level or parsing errors from the Gemini API."""

    def __init__(self, message: str, status_code: int = 0, raw: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


_FRIENDLY_ERRORS = {
    400: "Bad request -- check your message format.",
    401: "Invalid API key. Run /key to update it.",
    403: "API key does not have access to this model.",
    404: "Model not found. Run /model to pick a valid one.",
    429: "Rate limit reached -- try again shortly.",
    500: "Gemini server error -- try again in a moment.",
    503: "Gemini service temporarily unavailable -- try again shortly.",
}


def _friendly_message(status_code: int, detail: str) -> str:
    """Return a short user-friendly error string."""
    friendly = _FRIENDLY_ERRORS.get(status_code)
    if friendly:
        return f"{friendly} (HTTP {status_code})"
    return f"HTTP {status_code}: {detail[:200]}"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def send_message(
    messages: list,
    cfg: dict = None,
    timeout: int = 60,
    tools_enabled: bool = False,
    status_cb=None,
) -> str:
    """
    Send *messages* to the Gemini API and return the reply text.

    Parameters
    ----------
    messages : list[dict]
        Conversation history from load_history().
        Each dict has {"role", "content", "ts"}.
        "ts" is stripped before sending.

    cfg : dict, optional
        Configuration dict.  Loaded from disk when omitted.

    timeout : int
        HTTP timeout in seconds.  Defaults to 60.

    Returns
    -------
    str
        The model's reply text.

    Raises
    ------
    APIError
        On HTTP errors, missing key, or unparseable responses.
    """
    if cfg is None:
        cfg = load_config()

    api_key = cfg.get("api_key", "").strip()
    model   = cfg.get("model", "gemini-2.5-flash")

    if not api_key:
        raise APIError(
            "No API key configured. Run /key <your_key> to set it."
        )

    # Build the Gemini endpoint URL
    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent?key={api_key}"

    # Convert history to Gemini contents/parts format
    contents = _to_gemini_contents(messages)

    if not contents:
        raise APIError("No valid messages to send.")

    payload = {"contents": contents}

    # Optionally include function/tool declarations so the model knows what it can call
    if tools_enabled:
        try:
            from tools import get_tools_schema
            payload["tools"] = get_tools_schema()
            # Build an allow-list of function names declared in the tools schema.
            allowed_tool_names = set()
            try:
                for t in payload.get("tools", []):
                    for fd in t.get("functionDeclarations", []):
                        n = fd.get("name")
                        if n:
                            allowed_tool_names.add(n)
            except Exception:
                allowed_tool_names = set()
            # Add a conservative system instruction to encourage using tools
            # for file creation tasks. This steers Gemini to call functions
            # like create_folder / write_file instead of emitting code as text.
            payload["systemInstruction"] = {
                "parts": [
                    {
                        "text": (
                            "When the user asks to build, create, or set up files or a project, "
                            "use the available file tools (create_folder, write_file, append_file, delete_file, move_or_rename) "
                            "to perform the actions in the workspace. If the user references a project that doesn't exist yet in the projects folder, "
                            "create it automatically using create_project before writing files. Do not only print code as text unless the user explicitly asks to see or explain the code without creating files."
                        )
                    }
                ]
            }
        except Exception:
            pass
    body = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    # -- Execute HTTP request --
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        # Try to extract a detail message from the error body
        try:
            err_data = json.loads(raw_body)
            detail = (
                err_data.get("error", {}).get("message")
                or raw_body[:300]
            )
        except json.JSONDecodeError:
            detail = raw_body[:300]

        raise APIError(
            _friendly_message(exc.code, detail),
            status_code=exc.code,
            raw=raw_body,
        ) from exc
    except urllib.error.URLError as exc:
        raise APIError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise APIError(f"Request timed out after {timeout}s.") from exc

    # -- Parse response --
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise APIError(
            f"Could not parse JSON response: {exc}\nRaw: {raw_body[:500]}"
        ) from exc

    # If function-calling is enabled, process structured `functionCall` parts
    # Note: thoughtSignature handling removed. We will not inject or modify
    # the model's `functionCall` object. To avoid schema validation issues,
    # we append only the `function` (functionResponse) turn back to the
    # conversation and let Gemini continue. This keeps the payload minimal
    # and avoids sending fields the API rejects.

    if tools_enabled:
        calls = 0
        max_calls = cfg.get("tool_call_limit", 10)
        # operate on a mutable copy of messages so we can append the model/function turns
        convo = list(messages)

        while calls < max_calls:
            # Inspect response parts for a functionCall
            try:
                candidates = data.get("candidates", [])
                if not candidates:
                    raise APIError("Empty candidates in response")
                candidate = candidates[0]
                parts = candidate["content"].get("parts", [])
            except Exception as exc:
                raise APIError(f"Malformed response while checking for functionCall: {exc}") from exc

            # If the first part contains a structured functionCall, handle it
            first_part = parts[0] if parts else {}
            function_call = None
            if "functionCall" in first_part:
                function_call = first_part["functionCall"]
            elif "function_call" in first_part:
                function_call = first_part["function_call"]

            if function_call is None:
                # No function call -> return the text reply
                try:
                    return _parse_gemini_response(data)
                except ValueError as exc:
                    raise APIError(str(exc)) from exc

            fc = _normalize_function_call(function_call)
            thought_signature = None
            if isinstance(first_part, dict):
                thought_signature = first_part.get("thoughtSignature") or first_part.get("thought_signature")
            if thought_signature is None and isinstance(function_call, dict):
                thought_signature = function_call.get("thoughtSignature") or function_call.get("thought_signature")
            fname = fc.get("name")
            fargs = fc.get("args") or {}

            # Notify caller (REPL) about the planned tool call
            if status_cb:
                try:
                    status_cb(f"→ invoking {fname} ...")
                except Exception:
                    pass

            # Execute the function via tools module
            try:
                import tools as _tools
                # Ensure the model-declared function is allowed by the schema
                if allowed_tool_names and fname not in allowed_tool_names:
                    result = {"error": f"Tool not allowed: {fname}"}
                else:
                    func = getattr(_tools, fname, None)
                    if func is None:
                        result = {"error": f"Unknown tool: {fname}"}
                    else:
                        # Call tool with kwargs. The tools functions handle confirmations.
                        result = func(**fargs)
            except Exception as exc:
                result = {"error": str(exc)}

            # Build both the model's functionCall turn and the functionResponse turn
            if result == "declined":
                func_resp = {"name": fname, "response": {"error": "User declined this action."}}
            else:
                # Ensure response is an object per spec
                try:
                    # If result is a simple string, wrap it
                    if isinstance(result, str):
                        resp_obj = {"result": result}
                    else:
                        resp_obj = {"result": result}
                except Exception:
                    resp_obj = {"result": str(result)}

                func_resp = {"name": fname, "response": resp_obj}

            model_content = {"functionCall": fc}
            if thought_signature is not None:
                model_content["thoughtSignature"] = thought_signature
            model_turn = {"role": "model", "content": model_content}
            function_turn = {"role": "function", "content": func_resp}

            # Append both the model call turn and the function response turn to the conversation
            convo.append(model_turn)
            convo.append(function_turn)

            contents = _to_gemini_contents(convo)
            payload = {"contents": contents}
            # re-attach tools declarations on each loop per Gemini spec
            try:
                from tools import get_tools_schema
                payload["tools"] = get_tools_schema()
                # Recompute allowed tool names for the continued payload
                allowed_tool_names = set()
                try:
                    for t in payload.get("tools", []):
                        for fd in t.get("functionDeclarations", []):
                            n = fd.get("name")
                            if n:
                                allowed_tool_names.add(n)
                except Exception:
                    allowed_tool_names = set()
            except Exception:
                pass

            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_body = resp.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                raw_body = exc.read().decode("utf-8", errors="replace")
                try:
                    err_data = json.loads(raw_body)
                    detail = err_data.get("error", {}).get("message") or raw_body[:300]
                except Exception:
                    detail = raw_body[:300]
                raise APIError(_friendly_message(exc.code, detail), status_code=exc.code, raw=raw_body) from exc
            except Exception as exc:
                raise APIError(f"Error while continuing function-call loop: {exc}") from exc

            try:
                data = json.loads(raw_body)
            except Exception as exc:
                raise APIError(f"Error parsing continued response: {exc}") from exc

            calls += 1

        raise APIError("Max function-call loop reached")

    # Default (tools disabled): return textual reply
    try:
        return _parse_gemini_response(data)
    except ValueError as exc:
        raise APIError(str(exc)) from exc


# ------------------------------------------------------------------
# CLI smoke-test  (python api.py --test)
# ------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PocketCode Gemini API smoke-test")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Print config status and exit (no HTTP call).",
    )
    args = parser.parse_args()

    cfg = load_config()

    print(f"[api] Model      : {cfg.get('model')}")
    print(f"[api] Key set    : {'yes' if cfg.get('api_key') else 'NO - run /key'}")

    if args.test:
        print("\n[api] Dry-run complete (no HTTP request sent).")
        sys.exit(0)

    # Live test with a minimal prompt
    test_msgs = [
        {"role": "user", "content": "Say hello in exactly three words."},
    ]
    print("\n[api] Sending test message ...")
    try:
        reply = send_message(test_msgs, cfg=cfg, timeout=30)
        print(f"[api] Reply: {reply}")
    except APIError as e:
        print(f"[api] APIError ({e.status_code}): {e}", file=sys.stderr)
        sys.exit(1)
