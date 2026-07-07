import json
import urllib.request
from api import send_message

calls = []

class DummyResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

orig_urlopen = urllib.request.urlopen

def fake_urlopen(req, timeout=None):
    if hasattr(req, 'data') and req.data is not None:
        calls.append(req.data.decode('utf-8'))
    else:
        calls.append(None)

    if len(calls) == 1:
        resp = {
            'candidates': [
                {
                    'content': {
                        'parts': [
                            {
                                'functionCall': {
                                    'name': 'create_folder',
                                    'args': {'path': 'testsite'},
                                    'thoughtSignature': {'version': 1, 'sig': 'abc'}
                                }
                            }
                        ]
                    }
                }
            ]
        }
    else:
        resp = {
            'candidates': [
                {
                    'content': {
                        'parts': [
                            {'text': 'Done!'}
                        ]
                    }
                }
            ]
        }
    return DummyResp(json.dumps(resp).encode('utf-8'))

urllib.request.urlopen = fake_urlopen
try:
    messages = [{'role': 'user', 'content': 'create folder'}]
    cfg = {'api_key': 'x', 'model': 'm'}
    reply = send_message(messages, cfg=cfg, timeout=10, tools_enabled=True)
    print('reply:', reply)
    print('--- outgoing requests ---')
    for i, body in enumerate(calls, start=1):
        print(f'REQUEST {i}:')
        if body is None:
            print('  <no body>')
            continue
        print(json.dumps(json.loads(body), indent=2))
finally:
    urllib.request.urlopen = orig_urlopen
