import json
import urllib.request
from api import send_message, APIError


def test_gemini_function_call_forwards_thought_signature(monkeypatch):
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

    def fake_urlopen(req, timeout=None):
        body = req.data.decode('utf-8') if hasattr(req, 'data') and req.data is not None else None
        calls.append(body)
        if len(calls) == 1:
            resp = {
                'candidates': [
                    {
                        'content': {
                            'parts': [
                                {
                                    'functionCall': {
                                        'name': 'create_folder',
                                        'args': {
                                            'path': 'testsite'
                                        },
                                        'id': 'abc123'
                                    },
                                    'thoughtSignature': 'sig-abc123'
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

    monkeypatch.setattr('urllib.request.urlopen', fake_urlopen)

    messages = [{'role': 'user', 'content': 'create a folder'}]
    cfg = {'api_key': 'x', 'model': 'm'}

    reply = send_message(messages, cfg=cfg, timeout=10, tools_enabled=True)
    assert reply == 'Done!'
    assert len(calls) == 2

    second_payload = json.loads(calls[1])
    part = second_payload['contents'][1]['parts'][0]
    function_call = part['functionCall']
    assert function_call['name'] == 'create_folder'
    assert function_call['args'] == {'path': 'testsite'}
    assert function_call['id'] == 'abc123'
    assert part['thoughtSignature'] == 'sig-abc123'
    assert 'thought_signature' not in function_call
    assert 'thoughtSignature' not in function_call


def test_normalize_function_call_strips_thought_signature_fields():
    from api import _normalize_function_call

    normalized = _normalize_function_call({'name': 'create_project', 'args': {'name': 'demo'}})

    assert normalized == {'name': 'create_project', 'args': {'name': 'demo'}}
    assert 'thought_signature' not in normalized
    assert 'thoughtSignature' not in normalized


def test_create_folder_tool_accepts_path_arg(tmp_path, monkeypatch):
    from workspace import set_workspace
    import tools

    ws = tmp_path / 'ws'
    ws.mkdir()
    set_workspace(str(ws))

    monkeypatch.setattr('builtins.input', lambda prompt='': 'y')
    result = tools.create_folder(path='coffee')
    assert 'coffee' in result
    assert (ws / 'coffee').exists()
