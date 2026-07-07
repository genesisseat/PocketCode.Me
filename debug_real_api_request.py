import json
import urllib.request
import urllib.error
from api import send_message
from config import load_config

import builtins

orig_urlopen = urllib.request.urlopen
orig_input = builtins.input

class LoggingResponse:
    def __init__(self, resp):
        self._resp = resp

    def read(self):
        return self._resp.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, item):
        return getattr(self._resp, item)


def logging_urlopen(req, timeout=None):
    body = None
    if hasattr(req, 'data') and req.data is not None:
        try:
            body = json.loads(req.data.decode('utf-8'))
        except Exception:
            body = req.data.decode('utf-8', errors='replace')
    print('--- OUTGOING REQUEST ---')
    if body is not None:
        print(json.dumps(body, indent=2))
    else:
        print('<no body>')
    print('URL:', req.full_url)
    try:
        resp = orig_urlopen(req, timeout=timeout)
        return LoggingResponse(resp)
    except urllib.error.HTTPError as exc:
        print('--- HTTP ERROR ---')
        raw = exc.read().decode('utf-8', errors='replace')
        print(raw)
        raise

urllib.request.urlopen = logging_urlopen
builtins.input = lambda prompt='': 'y'

try:
    cfg = load_config()
    print('Using model:', cfg.get('model'))
    print('API key set:', bool(cfg.get('api_key')))
    messages = [{'role': 'user', 'content': 'create a folder and an index.html inside it that prints hello'}]
    try:
        reply = send_message(messages, cfg=cfg, timeout=30, tools_enabled=True)
        print('reply:', reply)
    except Exception as e:
        print('Exception:', type(e).__name__, e)
finally:
    urllib.request.urlopen = orig_urlopen
    builtins.input = orig_input
