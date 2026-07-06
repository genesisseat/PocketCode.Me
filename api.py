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
        text = msg.get("content", "")

        # Skip anything that isn't a valid Gemini role
        if role not in ("user", "model"):
            continue
        # Skip empty messages
        if not text:
            continue

        contents.append({
            "role": role,
            "parts": [{"text": text}],
        })

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
