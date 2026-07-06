"""
tests/test_pocketcode.py -- Gemini-only end-to-end test suite
==============================================================
Run:  python -m unittest tests.test_pocketcode -v
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# =====================================================================
# Config tests
# =====================================================================

class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        import config as cfg_mod
        self._orig_dir  = cfg_mod.CONFIG_DIR
        self._orig_file = cfg_mod.CONFIG_FILE
        cfg_mod.CONFIG_DIR  = self.tmp_dir
        cfg_mod.CONFIG_FILE = self.tmp_dir / "config.json"

    def tearDown(self):
        import config as cfg_mod
        cfg_mod.CONFIG_DIR  = self._orig_dir
        cfg_mod.CONFIG_FILE = self._orig_file
        self.tmp.cleanup()

    def _cfg(self):
        import config as cfg_mod
        return cfg_mod

    def test_fresh_install_creates_config(self):
        mod = self._cfg()
        cfg = mod.load_config()
        self.assertIn("api_key", cfg)
        self.assertIn("model", cfg)
        self.assertEqual(cfg["model"], "gemini-2.5-flash")
        self.assertTrue(mod.CONFIG_FILE.exists())

    def test_only_two_default_fields(self):
        """Config should only have api_key and model."""
        mod = self._cfg()
        cfg = mod.load_config()
        self.assertEqual(set(cfg.keys()), {"api_key", "model"})

    def test_save_and_reload(self):
        mod = self._cfg()
        original = mod.load_config()
        original["model"] = "gemini-2.0-flash"
        mod.save_config(original)
        reloaded = mod.load_config()
        self.assertEqual(reloaded["model"], "gemini-2.0-flash")

    def test_backfill_missing_keys(self):
        mod = self._cfg()
        mod.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with mod.CONFIG_FILE.open("w") as fh:
            json.dump({"api_key": "test"}, fh)
        cfg = mod.load_config()
        self.assertIn("model", cfg)

    def test_show_config_masks_key(self):
        mod = self._cfg()
        cfg = mod.load_config()
        cfg["api_key"] = "AIzaSyAbCdEfGhIjKlMnOp"
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            mod.show_config(cfg)
        output = buf.getvalue()
        self.assertNotIn("AIzaSyAbCdEfGhIjKlMnOp", output)
        self.assertIn("MnOp", output)  # last 4 visible

    def test_set_model(self):
        mod = self._cfg()
        mod.load_config()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            result = mod.set_model("gemma-3-27b-it")
        self.assertEqual(result["model"], "gemma-3-27b-it")
        reloaded = mod.load_config()
        self.assertEqual(reloaded["model"], "gemma-3-27b-it")

    def test_set_key(self):
        mod = self._cfg()
        mod.load_config()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            result = mod.set_key("AIzaTestKey1234")
        self.assertEqual(result["api_key"], "AIzaTestKey1234")


# =====================================================================
# History tests
# =====================================================================

class TestHistory(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        import history as hist_mod
        self._orig = {k: getattr(hist_mod, k)
                      for k in ("POCKET_DIR", "SESSIONS_DIR", "STATE_FILE")}
        hist_mod.POCKET_DIR   = tmp_path
        hist_mod.SESSIONS_DIR = tmp_path / "sessions"
        hist_mod.STATE_FILE   = tmp_path / "state.json"

    def tearDown(self):
        import history as hist_mod
        for k, v in self._orig.items():
            setattr(hist_mod, k, v)
        self.tmp.cleanup()

    def _hist(self):
        import history as hist_mod
        return hist_mod

    def test_new_session_creates_file(self):
        mod = self._hist()
        sid = mod.new_session()
        self.assertTrue(mod._session_path(sid).exists())

    def test_state_tracks_current_session(self):
        mod = self._hist()
        sid = mod.new_session()
        self.assertEqual(mod._get_current_session_id(), sid)

    def test_append_and_load(self):
        mod = self._hist()
        sid = mod.new_session()
        mod.append_message("user",  "Hello", sid)
        mod.append_message("model", "Hi!",   sid)
        msgs = mod.load_history(sid)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "model")

    def test_gemini_roles_only(self):
        """Only 'user' and 'model' are valid -- 'assistant'/'system' rejected."""
        mod = self._hist()
        sid = mod.new_session()
        with self.assertRaises(ValueError):
            mod.append_message("assistant", "bad", sid)
        with self.assertRaises(ValueError):
            mod.append_message("system", "bad", sid)

    def test_trim_history(self):
        mod = self._hist()
        sid = mod.new_session()
        for i in range(10):
            mod.append_message("user", f"msg {i}", sid)
        trimmed = mod.trim_history(3, sid)
        self.assertEqual(len(trimmed), 3)
        reloaded = mod.load_history(sid)
        self.assertEqual(len(reloaded), 3)
        self.assertEqual(reloaded[-1]["content"], "msg 9")

    def test_session_persists_across_kill(self):
        """Simulate kill mid-chat, relaunch, verify session reloads."""
        mod = self._hist()
        sid = mod.new_session()
        mod.append_message("user",  "What is Termux?", sid)
        mod.append_message("model", "Termux is ...",   sid)

        # Simulate relaunch
        recovered = mod._get_current_session_id()
        self.assertEqual(recovered, sid)
        msgs = mod.load_history(recovered)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["content"], "What is Termux?")

    def test_list_sessions(self):
        mod = self._hist()
        sid1 = mod.new_session()
        sid2 = mod.new_session()
        sessions = mod.list_sessions()
        self.assertIn(sid1, sessions)
        self.assertIn(sid2, sessions)
        self.assertLess(sessions.index(sid1), sessions.index(sid2))


# =====================================================================
# API layer tests  (all HTTP mocked)
# =====================================================================

def _mock_response(body: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__  = MagicMock(return_value=False)
    return resp


class TestGeminiAPI(unittest.TestCase):

    BASE_CFG = {
        "api_key": "AIzaTestKey1234",
        "model":   "gemini-2.5-flash",
    }

    # -- Format conversion --

    def test_to_gemini_contents(self):
        from api import _to_gemini_contents
        msgs = [
            {"role": "user",  "content": "hello", "ts": "2026-01-01"},
            {"role": "model", "content": "hi!",   "ts": "2026-01-01"},
        ]
        contents = _to_gemini_contents(msgs)
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[0]["parts"][0]["text"], "hello")
        self.assertEqual(contents[1]["role"], "model")

    def test_to_gemini_contents_strips_ts(self):
        from api import _to_gemini_contents
        msgs = [{"role": "user", "content": "hi", "ts": "2026-07-06T00:00:00"}]
        contents = _to_gemini_contents(msgs)
        self.assertNotIn("ts", contents[0])

    def test_to_gemini_contents_skips_invalid_roles(self):
        from api import _to_gemini_contents
        msgs = [
            {"role": "system",    "content": "you are helpful"},
            {"role": "user",      "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        contents = _to_gemini_contents(msgs)
        self.assertEqual(len(contents), 1)  # only "user" kept

    # -- Response parsing --

    def test_parse_gemini_response(self):
        from api import _parse_gemini_response
        data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello world!"}],
                    "role": "model",
                }
            }]
        }
        self.assertEqual(_parse_gemini_response(data), "Hello world!")

    def test_parse_gemini_multi_part(self):
        from api import _parse_gemini_response
        data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello "}, {"text": "world!"}],
                    "role": "model",
                }
            }]
        }
        self.assertEqual(_parse_gemini_response(data), "Hello world!")

    def test_parse_blocked_response(self):
        from api import _parse_gemini_response
        data = {
            "candidates": [],
            "promptFeedback": {"blockReason": "SAFETY"},
        }
        # Empty candidates but with promptFeedback
        data2 = {"promptFeedback": {"blockReason": "SAFETY"}}
        with self.assertRaises(ValueError):
            _parse_gemini_response(data2)

    # -- send_message --

    @patch("urllib.request.urlopen")
    def test_send_message_success(self, mock_urlopen):
        from api import send_message
        gemini_resp = {
            "candidates": [{
                "content": {"parts": [{"text": "OK!"}], "role": "model"}
            }]
        }
        mock_urlopen.return_value = _mock_response(gemini_resp)

        reply = send_message(
            [{"role": "user", "content": "hi"}],
            cfg=self.BASE_CFG,
        )
        self.assertEqual(reply, "OK!")

        # Verify the URL is correct Gemini endpoint
        req = mock_urlopen.call_args[0][0]
        self.assertIn("generativelanguage.googleapis.com", req.full_url)
        self.assertIn("gemini-2.5-flash", req.full_url)
        self.assertIn("generateContent", req.full_url)

    @patch("urllib.request.urlopen")
    def test_send_message_sends_contents_format(self, mock_urlopen):
        from api import send_message
        mock_urlopen.return_value = _mock_response(
            {"candidates": [{"content": {"parts": [{"text": "OK"}], "role": "model"}}]}
        )

        send_message(
            [{"role": "user", "content": "hello", "ts": "x"}],
            cfg=self.BASE_CFG,
        )

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        # Must use "contents" key with parts format
        self.assertIn("contents", body)
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "hello")

    def test_missing_key_raises(self):
        from api import send_message, APIError
        cfg = {"api_key": "", "model": "gemini-2.5-flash"}
        with self.assertRaises(APIError) as ctx:
            send_message([{"role": "user", "content": "hi"}], cfg=cfg)
        self.assertIn("No API key", str(ctx.exception))

    # -- Error handling (step 7) --

    @patch("urllib.request.urlopen")
    def test_401_bad_key(self, mock_urlopen):
        import urllib.error
        from api import send_message, APIError
        err = urllib.error.HTTPError(
            url="https://x", code=401, msg="Unauthorized", hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"API key not valid"}}'),
        )
        mock_urlopen.side_effect = err
        with self.assertRaises(APIError) as ctx:
            send_message([{"role": "user", "content": "hi"}], cfg=self.BASE_CFG)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid API key", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_429_rate_limit(self, mock_urlopen):
        import urllib.error
        from api import send_message, APIError
        err = urllib.error.HTTPError(
            url="https://x", code=429, msg="Too Many Requests", hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"quota exceeded"}}'),
        )
        mock_urlopen.side_effect = err
        with self.assertRaises(APIError) as ctx:
            send_message([{"role": "user", "content": "hi"}], cfg=self.BASE_CFG)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Rate limit", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_500_server_error(self, mock_urlopen):
        import urllib.error
        from api import send_message, APIError
        err = urllib.error.HTTPError(
            url="https://x", code=500, msg="Internal", hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"internal"}}'),
        )
        mock_urlopen.side_effect = err
        with self.assertRaises(APIError) as ctx:
            send_message([{"role": "user", "content": "hi"}], cfg=self.BASE_CFG)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("server error", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_404_bad_model(self, mock_urlopen):
        import urllib.error
        from api import send_message, APIError
        err = urllib.error.HTTPError(
            url="https://x", code=404, msg="Not Found", hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"model not found"}}'),
        )
        mock_urlopen.side_effect = err
        with self.assertRaises(APIError) as ctx:
            send_message([{"role": "user", "content": "hi"}], cfg=self.BASE_CFG)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Model not found", str(ctx.exception))


# =====================================================================
# REPL integration tests
# =====================================================================

class TestREPL(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self.tmp.name)
        import config as cfg_mod
        import history as hist_mod
        self._cfg_orig = (cfg_mod.CONFIG_DIR, cfg_mod.CONFIG_FILE)
        cfg_mod.CONFIG_DIR  = tmp_path
        cfg_mod.CONFIG_FILE = tmp_path / "config.json"
        self._hist_orig = {k: getattr(hist_mod, k)
                           for k in ("POCKET_DIR", "SESSIONS_DIR", "STATE_FILE")}
        hist_mod.POCKET_DIR   = tmp_path
        hist_mod.SESSIONS_DIR = tmp_path / "sessions"
        hist_mod.STATE_FILE   = tmp_path / "state.json"

    def tearDown(self):
        import config as cfg_mod
        import history as hist_mod
        cfg_mod.CONFIG_DIR, cfg_mod.CONFIG_FILE = self._cfg_orig
        for k, v in self._hist_orig.items():
            setattr(hist_mod, k, v)
        self.tmp.cleanup()

    def test_cmd_new_creates_session(self):
        from repl import cmd_new
        from history import load_history
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            sid = cmd_new()
        msgs = load_history(sid)
        self.assertIsInstance(msgs, list)

    def test_dispatch_exit(self):
        from repl import _dispatch
        from config import load_config
        from history import new_session
        sid = new_session()
        cfg = load_config()
        with patch("sys.stdout", io.StringIO()):
            result_sid, result_cfg = _dispatch("/exit", sid, cfg)
        self.assertIsNone(result_sid)

    def test_dispatch_unknown(self):
        from repl import _dispatch
        from config import load_config
        from history import new_session
        sid = new_session()
        cfg = load_config()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            result_sid, _ = _dispatch("/nosuchcmd", sid, cfg)
        self.assertEqual(result_sid, sid)
        self.assertIn("Unknown command", buf.getvalue())

    def test_cmd_key_from_dispatch(self):
        """Test /key <value> sets the key via dispatch."""
        from repl import _dispatch
        from config import load_config, CONFIG_FILE
        from history import new_session
        sid = new_session()
        cfg = load_config()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _, updated = _dispatch("/key AIzaTestKeyFromDispatch", sid, cfg)
        self.assertEqual(updated["api_key"], "AIzaTestKeyFromDispatch")
        saved = json.loads(CONFIG_FILE.read_text())
        self.assertEqual(saved["api_key"], "AIzaTestKeyFromDispatch")

    def test_cmd_clear(self):
        from repl import cmd_clear
        from history import new_session, append_message, load_history
        sid = new_session()
        append_message("user", "hello", sid)
        append_message("model", "hi!", sid)
        self.assertEqual(len(load_history(sid)), 2)
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cmd_clear(sid)
        self.assertEqual(len(load_history(sid)), 0)

    def test_old_session_persists_after_new(self):
        """After /new, the old session's messages must still be on disk."""
        from repl import cmd_new
        from history import append_message, load_history, new_session
        # First session
        sid1 = new_session()
        append_message("user",  "old message", sid1)
        append_message("model", "old reply",   sid1)

        # Start new session
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            sid2 = cmd_new()

        self.assertNotEqual(sid1, sid2)
        # Old session intact
        old_msgs = load_history(sid1)
        self.assertEqual(len(old_msgs), 2)
        self.assertEqual(old_msgs[0]["content"], "old message")


# =====================================================================
# Colors tests
# =====================================================================

class TestColors(unittest.TestCase):

    def test_c_with_ansi(self):
        import colors
        orig = colors.ANSI_ENABLED
        try:
            colors.ANSI_ENABLED = True
            result = colors.c(colors.BOLD, "hello")
            self.assertIn("\033[", result)
            self.assertTrue(result.endswith(colors.RESET))
        finally:
            colors.ANSI_ENABLED = orig

    def test_c_without_ansi(self):
        import colors
        orig = colors.ANSI_ENABLED
        try:
            colors.ANSI_ENABLED = False
            result = colors.c(colors.BOLD, "hello")
            self.assertEqual(result, "hello")
        finally:
            colors.ANSI_ENABLED = orig

    def test_strip_ansi(self):
        import colors
        styled = "\033[1m\033[92mhello\033[0m"
        self.assertEqual(colors.strip_ansi(styled), "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
