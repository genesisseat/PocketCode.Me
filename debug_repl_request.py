import json
import tempfile
import urllib.request
from api import send_message
import builtins

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
orig_input = builtins.input

responses = []

# First response: request create_folder
responses.append(
    {
        'candidates': [
            {
                'content': {
                    'parts': [
                        {
                            'functionCall': {
                                'name': 'create_folder',
                                'args': {'path': 'coffee-shop-site'},
                                'thoughtSignature': {'version': 1, 'sig': 'sig1'}
                            }
                        }
                    ]
                }
            }
        ]
    }
)

# Second response: request write_file
responses.append(
    {
        'candidates': [
            {
                'content': {
                    'parts': [
                        {
                            'functionCall': {
                                'name': 'write_file',
                                'args': {
                                    'path': 'coffee-shop-site/index.html',
                                    'content': '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Coffee Shop</title></head><body><h1>Hello</h1></body></html>'
                                },
                                'thoughtSignature': {'version': 1, 'sig': 'sig2'}
                            }
                        }
                    ]
                }
            }
        ]
    }
)

# Final response: done text
responses.append(
    {
        'candidates': [
            {
                'content': {
                    'parts': [
                        {'text': 'Your coffee shop website has been created.'}
                    ]
                }
            }
        ]
    }
)

response_index = 0

def fake_urlopen(req, timeout=None):
    global response_index
    if hasattr(req, 'data') and req.data is not None:
        calls.append(req.data.decode('utf-8'))
    else:
        calls.append(None)

    if response_index < len(responses):
        payload = responses[response_index]
    else:
        payload = responses[-1]
    response_index += 1
    return DummyResp(json.dumps(payload).encode('utf-8'))

urllib.request.urlopen = fake_urlopen
builtins.input = lambda prompt='': 'y'

try:
    import workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace.set_workspace(tmpdir)
        messages = [{'role': 'user', 'content': 'create a folder and an index.html inside it that prints hello'}]
        cfg = {'api_key': 'x', 'model': 'm'}
        reply = send_message(messages, cfg=cfg, timeout=10, tools_enabled=True)
        print('reply:', reply)
        print('\n--- outgoing requests ---')
        for i, body in enumerate(calls, start=1):
            print(f'REQUEST {i}:')
            if body is None:
                print('  <no body>')
                continue
            print(json.dumps(json.loads(body), indent=2))
        print('\nCreated files:')
        import os
        for root, dirs, files in os.walk(tmpdir):
            for fname in files:
                print(os.path.relpath(os.path.join(root, fname), tmpdir))
finally:
    urllib.request.urlopen = orig_urlopen
    builtins.input = orig_input
