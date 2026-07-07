import json
import urllib.request
import urllib.error
import builtins
from api import send_message
from config import load_config

orig_urlopen = urllib.request.urlopen
orig_input = builtins.input

class ReplayResponse:
    def __init__(self, raw, resp):
        self._raw = raw
        self._resp = resp

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return getattr(self._resp, name)


def logging_urlopen(req, timeout=None):
    req_body = None
    if hasattr(req, 'data') and req.data is not None:
        try:
            req_body = json.loads(req.data.decode('utf-8'))
        except Exception:
            req_body = req.data.decode('utf-8', errors='replace')
    print('--- OUTGOING REQUEST ---')
    print(json.dumps(req_body, indent=2))
    print('URL:', req.full_url)
    try:
        resp = orig_urlopen(req, timeout=timeout)
        raw = resp.read()
        try:
            parsed = json.loads(raw.decode('utf-8'))
            print('--- RESPONSE BODY ---')
            print(json.dumps(parsed, indent=2))
        except Exception:
            print('--- RESPONSE BODY (non-json) ---')
            print(raw.decode('utf-8', errors='replace'))
        return ReplayResponse(raw, resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        print('--- HTTP ERROR BODY ---')
        print(raw.decode('utf-8', errors='replace'))
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
