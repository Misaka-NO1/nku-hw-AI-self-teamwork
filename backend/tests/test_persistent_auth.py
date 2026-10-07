"""Real embedded PG and HTTP: opt-in, retention, owner separation, revocation."""
import time

from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.core.browser_session_context import decode_context, encode_context
from app.core.errors import AppError
from app.core.persistent_auth import UNTIL_REVOKED_EPOCH, COOKIE_MAX_AGE
from test_cloud_identity_site import environment, login, save, headers, ORIGIN
from test_personal_task_isolation import grant, draft, commit, calendar
import pytest


def test_context_requires_explicit_runtime_opt_in_and_valid_mac():
    token, csrf = 't'*43, 'c'*43
    value = encode_context(token, 'pilot_workspace_abcdefghijklmnopqrstuvwx', csrf, UNTIL_REVOKED_EPOCH)
    with pytest.raises(AppError):
        decode_context(token, value)
    assert decode_context(token, value, now=int(time.time())+2*86400, persistent=True)['expires_epoch'] == UNTIL_REVOKED_EPOCH
    with pytest.raises(AppError):
        decode_context('x'*43, value, persistent=True)
    arbitrary = encode_context(token, 'pilot_workspace_abcdefghijklmnopqrstuvwx', csrf, int(time.time())+86400)
    with pytest.raises(AppError):
        decode_context(token, arbitrary, persistent=True)


def test_persistent_login_retains_schedule_and_own_records_but_logout_revokes(environment):
    settings, root, store, old_client = environment
    old_a = login(old_client)
    save(old_client, old_a, 'schedule', 'timetable.demo.json', key='persistent-old-schedule')
    original = old_client.get('/api/v1/schedules/current',params={'workspace_ref':old_a['workspace_ref']}).json()['data']
    store.call('__test_expire_workspace__', {'workspace_ref':old_a['workspace_ref']})
    runtime = settings.model_copy(update={'cloud_persistent_auth_enabled':True,
        'cloud_personal_tasks_enabled':True,'cloud_task_calendar_enabled':True,
        'cloud_notice_text_pilot_enabled':True,'cloud_oauth_competition_compat_enabled':True})
    with TestClient(create_cloud_identity_site(root,store,runtime),base_url=ORIGIN) as client:
        a = login(client)
        assert a['workspace_ref'] == old_a['workspace_ref']
        assert a['expires_at'].startswith('9999-01-01')
        assert client.get('/api/v1/schedules/current',params={'workspace_ref':a['workspace_ref']}).json()['data'] == original
        resumed = client.get('/api/v1/auth/cloudbase/browser-session',headers={'X-Campus-Session-Read':'1'})
        assert resumed.status_code == 200, resumed.text
        assert f'Max-Age={COOKIE_MAX_AGE}' in resumed.headers['set-cookie']
        a_grant = grant(client)
        made = draft(client,a,key='persistent-a-draft').json()['data']
        entry = commit(client,a,made,key='persistent-a-commit').json()['data']['item']
        b = login(client,'fictional-b')
        b_grant = grant(client)
        assert client.get('/oauth/tasks/entries',headers=b_grant).json()['data']['items'] == []
        readback = client.get('/oauth/tasks/entries',headers=a_grant).json()['data']
        assert readback['items'][0]['task_id'] == entry['task_id']
        assert readback['calendar_url'] == ORIGIN+'/tools/calendar'
        assert calendar(client,b).json()['data']['items'] == []
        # The original owner is preserved even while a different browser owner logs in.
        a = login(client)
        assert calendar(client,a).json()['data']['items'][0]['task_id'] == entry['task_id']
        renewed_grant = grant(client)
        assert client.post('/api/v1/auth/cloudbase/logout',headers=headers(a)).status_code == 200
        assert client.get('/oauth/tasks/entries',headers=renewed_grant).status_code == 401
        assert client.get('/api/v1/auth/cloudbase/browser-session',headers={'X-Campus-Session-Read':'1'}).status_code == 401


def test_persistent_grant_wire_ttl_and_explicit_revoke(environment):
    from test_competition_oauth import PARAMS, authorize, exchange, SECRET
    settings, root, store, _ = environment
    runtime = settings.model_copy(update={'cloud_persistent_auth_enabled':True,
        'cloud_personal_tasks_enabled':True,'cloud_task_calendar_enabled':True,
        'cloud_notice_text_pilot_enabled':True,'cloud_oauth_competition_compat_enabled':True})
    with TestClient(create_cloud_identity_site(root,store,runtime),base_url=ORIGIN) as client:
        login(client)
        code = authorize(client)
        token = exchange(client,code).json()
        assert token['expires_in'] == 2147483647
        assert exchange(client,code).status_code == 400  # Code remains one-use.
        bearer = {'Authorization':'Bearer '+token['access_token']}
        assert client.get('/oauth/records',headers=bearer).status_code == 200
        assert client.post('/oauth/revoke',json={'token':token['access_token'],
            'client_id':PARAMS['client_id'],'client_secret':SECRET}).status_code == 200
        assert client.get('/oauth/records',headers=bearer).status_code == 401


def test_migration_does_not_extend_short_session_or_grant(environment):
    settings, root, store, _ = environment
    runtime = settings.model_copy(update={'cloud_personal_tasks_enabled':True,
        'cloud_task_calendar_enabled':True,'cloud_notice_text_pilot_enabled':True,
        'cloud_oauth_competition_compat_enabled':True})
    with TestClient(create_cloud_identity_site(root,store,runtime),base_url=ORIGIN) as client:
        a = login(client)
        assert not a['expires_at'].startswith('9999')
        bearer = grant(client)
        from app.core.security import secret_hash
        store.call('__test_expire_browser_session__',{'token_hash':secret_hash(client.cookies.get('campus_session'))})
        assert client.get('/oauth/tasks/entries',headers=bearer).status_code == 401
