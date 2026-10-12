"""Smoke-script safety tested with in-memory HTTP only, never the actual cloud."""
import importlib.util
from pathlib import Path
import httpx

SPEC = importlib.util.spec_from_file_location('identity_first_probe', Path(__file__).parents[1] / 'scripts/verify_live_visitors.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def fake_server(monkeypatch, *, enabled=True, unknown_creates=False):
    seen = []
    real_client = httpx.Client
    def handler(request):
        seen.append((request.method, request.url.path))
        path = request.url.path
        if path == '/healthz':
            return httpx.Response(200, json={'build_id':'fictional-local-probe'})
        if path.endswith('/config'):
            return httpx.Response(200, json={'data':{'visitor_identity_first':enabled}})
        if path.endswith('/visitor/session'):
            if request.headers.get('Origin') != probe.ORIGIN:
                return httpx.Response(403, json={})
            if request.content != b'{}':
                return httpx.Response(422, json={})
            return httpx.Response(200 if unknown_creates else 401, json={'error':{'code':'AUTH_REQUIRED'}})
        if path.endswith('/start'):
            return httpx.Response(200, json={'data':{'device_code':'DEV-'+'A'*26}})
        if path.endswith('/state'):
            return httpx.Response(200, json={'data':{'has_space':False,'agent_linked':False,'school_identity_verified':False}})
        if path.endswith('/claim'):
            return httpx.Response(200, json={'data':{'status':'pending'}})
        raise AssertionError('Unexpected probe operation')
    monkeypatch.setattr(probe.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return seen


def test_old_deployment_probe_stops_before_any_post(monkeypatch, capsys):
    seen = fake_server(monkeypatch, enabled=False)
    assert probe.main() == 1
    assert all(method == 'GET' for method, _ in seen)
    assert 'stopped_before_post' in capsys.readouterr().out


def test_guarded_probe_checks_unknown_denial_without_enrollment(monkeypatch, capsys):
    seen = fake_server(monkeypatch)
    assert probe.main() == 0
    assert ('POST', '/api/v1/auth/agent-device/claim') in seen
    assert 'no_space_created' in capsys.readouterr().out


def test_unexpected_create_response_fails_probe(monkeypatch, capsys):
    seen = fake_server(monkeypatch, unknown_creates=True)
    assert probe.main() == 1
    assert sum(method == 'POST' for method, _ in seen) == 1
    assert 'false' in capsys.readouterr().out
