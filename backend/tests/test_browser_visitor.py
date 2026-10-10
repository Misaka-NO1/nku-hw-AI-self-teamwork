"""Private passwordless visitor + real embedded PG + existing OAuth isolation."""
import pytest
import json
import httpx
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from app.core.security import SESSION_COOKIE, secret_hash
from app.core.browser_session_context import CONTEXT_COOKIE
from app.agent_device_site import COOKIE
from app.core.cloud_identity_store import CloudIdentityStore, RPC_URL
from app.core.errors import AppError
from test_cloud_identity_site import environment, login, headers, ORIGIN
from test_agent_device import device_post, grant, agent_bind
from test_personal_schedules import personal, create, confirm
from test_personal_task_isolation import draft as task_draft, commit as task_commit, calendar
from app.core.contracts import validate_boundary
from pathlib import Path


def test_visitor_operations_reach_pinned_transport_only():
    seen = []
    def transport(request):
        assert str(request.url) == RPC_URL
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "data": {"transport": True}})
    store = CloudIdentityStore('fictional-server-key', httpx.MockTransport(transport))
    try:
        for op in ('visitor_probe', 'visitor_begin', 'visitor_status'):
            assert store.call(op, {}) == {"transport": True}
        assert [item['op'] for item in seen] == ['visitor_probe', 'visitor_begin', 'visitor_status']
        with pytest.raises(AppError):
            store.call('visitor_admin', {})
        assert len(seen) == 3
    finally:
        store.close()


@pytest.fixture
def visitors(environment):
    settings, root, db, _ = environment
    runtime = settings.model_copy(update={"cloud_oauth_competition_compat_enabled": True,
        "cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True,
        "cloud_personal_tasks_enabled": True, "cloud_persistent_auth_enabled": True,
        "cloud_personal_schedules_enabled": True, "cloud_agent_device_binding_enabled": True,
        "cloud_visitor_enabled": True})
    # Exercise the production identity operation allowlist as well as real SQL.
    # Other domain transports delegate to the same embedded private database.
    def transport(request):
        assert str(request.url) == RPC_URL
        body = json.loads(request.content)
        try:
            result = {"ok": True, "data": db.call(body['op'], body['args'])}
        except AppError as exc:
            result = {"ok": False, "code": exc.code, "status": exc.status_code}
        return httpx.Response(200, json=result)
    identity = CloudIdentityStore('fictional-server-key', httpx.MockTransport(transport))
    class TransportStore:
        def call(self, op, args):
            return identity.call(op, args)
        def close(self):
            pass
        def __getattr__(self, name):
            return getattr(db, name)
    transport_db = TransportStore()
    with TestClient(create_cloud_identity_site(root, transport_db, runtime), base_url=ORIGIN) as a, TestClient(create_cloud_identity_site(root, transport_db, runtime), base_url=ORIGIN) as b:
        yield runtime, root, db, a, b
    identity.close()


def begin(client, body=None, **extra_headers):
    return client.post('/api/v1/auth/visitor/session', json={} if body is None else body,
        headers={"Origin": ORIGIN, "X-Campus-Visitor": "1", **extra_headers})


def test_visitor_private_save_agent_read_binding_restart_and_cross_owner_denial(visitors):
    runtime, root, db, a, b = visitors
    ar = begin(a); br = begin(b)
    assert ar.status_code == br.status_code == 200, ar.text + br.text
    owner, other = ar.json()['data'], br.json()['data']
    validate_boundary(owner, 'CloudBrowserSession')
    assert calendar(a, owner).json()['data']['items'] == []
    assert calendar(b, other).json()['data']['items'] == []
    assert owner['workspace_ref'] != other['workspace_ref']
    assert a.cookies.get(COOKIE) != b.cookies.get(COOKIE)
    assert all(flag in ar.headers['set-cookie'] for flag in ('HttpOnly', 'Secure', 'SameSite=strict'))
    assert a.cookies.get(SESSION_COOKIE) not in ar.text
    assert begin(a).json()['data']['workspace_ref'] == owner['workspace_ref']
    assert a.get('/api/v1/auth/cloudbase/browser-session', headers={'X-Campus-Session-Read':'1'}).status_code == 200
    assert a.get('/tools/timetable', follow_redirects=False).status_code == 200
    payload = personal('访客A本人课程')
    draft = create(a, owner, payload, 'visitor-personal')
    assert b.get('/api/v1/drafts/'+draft['draft_id']).status_code == 404
    receipt = confirm(a, owner, draft, 'visitor-personal')
    assert a.post('/api/v1/schedules/commit', json=receipt, headers=headers(owner)).status_code == 200
    new_task = task_draft(a, owner, title='访客A本人提醒', key='visitor-task-draft').json()['data']
    saved_task = task_commit(a, owner, new_task, key='visitor-task-commit')
    assert saved_task.status_code == 200, saved_task.text
    task_id = saved_task.json()['data']['item']['task_id']
    assert [item['task_id'] for item in calendar(a, owner).json()['data']['items']] == [task_id]
    assert calendar(b, other).json()['data']['items'] == []
    assert calendar(b, owner).status_code == 404
    assert task_commit(b, other, new_task, key='visitor-steal-draft').status_code == 404
    assert b.get('/api/v1/schedules/current', params={'workspace_ref':owner['workspace_ref']}).status_code == 404
    assert b.get('/api/v1/schedules/current', params={'workspace_ref':other['workspace_ref']}).status_code == 404
    bearer = grant(a)
    code = device_post(a, 'start').json()['data']['device_code']
    assert agent_bind(a, bearer, code).status_code == 200
    records = a.get('/oauth/records', headers=bearer)
    assert records.status_code == 200, records.text
    assert records.json()['data']['schedule']['timetable']['courses'][0]['title'] == payload['courses'][0]['title']
    agent_items = a.get('/oauth/tasks/entries', headers=bearer)
    assert agent_items.status_code == 200
    assert [item['task_id'] for item in agent_items.json()['data']['items']] == [task_id]
    assert agent_bind(b, grant(b), code).status_code == 403
    cookies = dict(a.cookies)
    # Startup roster synchronization must preserve visitor sessions and personal data.
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as restored:
        restored.cookies.update(cookies)
        assert restored.get('/api/v1/auth/cloudbase/browser-session', headers={'X-Campus-Session-Read':'1'}).status_code == 200
        current = restored.get('/api/v1/schedules/current', params={'workspace_ref':owner['workspace_ref']})
        assert current.json()['data']['timetable'] == payload
        assert [item['task_id'] for item in calendar(restored, owner).json()['data']['items']] == [task_id]
        assert device_post(restored, 'start').json()['data']['device_code'] == code


def test_visitor_logout_revokes_agent_and_explicit_resume_preserves_data_identity(visitors):
    _, _, _, a, _ = visitors
    owner = begin(a).json()['data']; bearer = grant(a)
    code = device_post(a, 'start').json()['data']['device_code']
    assert agent_bind(a, bearer, code).status_code == 200
    assert a.post('/api/v1/auth/cloudbase/logout', headers=headers(owner)).status_code == 200
    assert a.get('/api/v1/auth/cloudbase/browser-session', headers={'X-Campus-Session-Read':'1'}).status_code == 401
    assert a.get('/oauth/records', headers=bearer).status_code == 401
    assert begin(a).json()['data']['workspace_ref'] == owner['workspace_ref']
    assert a.get('/oauth/records', headers=bearer).status_code == 401  # No grant resurrection.
    assert device_post(a, 'start').json()['data']['device_code'] == code


def test_visitor_never_overwrites_registered_owner_or_accepts_owner_inputs(visitors, environment):
    _, _, db, a, b = visitors
    original = login(a)
    assert begin(a).json()['data']['workspace_ref'] == original['workspace_ref']
    assert db.call('visitor_status', {'session_hash':secret_hash(a.cookies.get(SESSION_COOKIE))}) == {'visitor':False}
    code = device_post(b, 'start').json()['data']['device_code']
    assert agent_bind(a, grant(a), code).status_code == 200
    assert begin(b).status_code == 409  # Pending registered binding cannot become visitor.
    assert device_post(b, 'claim').status_code == 200
    assert begin(b).json()['data']['workspace_ref'] == original['workspace_ref']
    for body in ({'workspace_ref':original['workspace_ref']}, {'device_code':code}, {'subject_id':'visitor_fake'}):
        assert begin(b, body).status_code == 422
    assert begin(b, Origin='https://evil.invalid').status_code == 403
    assert environment[3].post('/api/v1/auth/visitor/session', json={}).status_code == 404
    assert '免注册开始使用' in b.get('/tools/device-login').text or b.get('/tools/timetable').status_code == 200


def test_visitor_capacity_rate_limit_and_public_code_cannot_resume(visitors):
    _, root, db, a, b = visitors
    owner = begin(a).json()['data']
    code = device_post(a, 'start').json()['data']['device_code']
    # DEV is public locator only; a copied code never recovers A's workspace.
    b.cookies.set(COOKIE, code)
    assert begin(b).json()['data']['workspace_ref'] != owner['workspace_ref']
    for _ in range(10):
        response = begin(a)
    assert response.status_code == 429


def test_visitor_start_contract_has_no_caller_identity_fields():
    examples = json.loads((Path(__file__).parents[2] / 'fixtures/browser-visitor.example.json').read_text(encoding='utf-8'))
    validate_boundary(examples['request'], 'BrowserVisitorStartRequest')
    for invalid in examples['rejected_requests']:
        with pytest.raises(AppError):
            validate_boundary(invalid, 'BrowserVisitorStartRequest')


def test_visitor_dependency_failure_preserves_identity_without_fallback(visitors, monkeypatch):
    _, _, db, a, _ = visitors
    begin(a)
    before = dict(a.cookies)
    original = db.call
    def unavailable(op, args):
        if op == 'get_workspace':
            raise AppError(503, 'DEPENDENCY_UNAVAILABLE', 'Private storage unavailable', True)
        return original(op, args)
    monkeypatch.setattr(db, 'call', unavailable)
    response = begin(a)
    assert response.status_code == 503
    assert 'set-cookie' not in response.headers
    assert dict(a.cookies) == before


def test_visitor_device_details_is_read_only_and_contains_no_private_proof(visitors):
    _, _, _, a, _ = visitors
    begin(a)
    code = device_post(a, 'start').json()['data']['device_code']
    before = dict(a.cookies)
    page = a.get('/tools/device')
    assert code in page.text
    assert '本浏览器访客已登录；Agent 尚未完成关联授权' in page.text
    assert 'set-cookie' not in page.headers
    assert all(secret not in page.text for secret in before.values())
    assert dict(a.cookies) == before


@pytest.mark.parametrize('missing_gate', [
    'cloud_persistent_auth_enabled', 'cloud_agent_device_binding_enabled', 'cloud_personal_schedules_enabled'
])
def test_visitor_requires_all_private_identity_dependencies(visitors, missing_gate):
    runtime, root, db, _, _ = visitors
    with pytest.raises(ValueError, match='Browser visitors require private persistent'):
        create_cloud_identity_site(root, db, runtime.model_copy(update={missing_gate: False}))
