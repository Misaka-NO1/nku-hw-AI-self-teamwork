"""Destructive maintenance is tested ONLY against disposable fictional PGlite."""
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from test_cloud_identity_site import environment, ORIGIN, headers
from test_genios_identity_site import native, start_and_create, attest
from test_agent_device import grant
from test_degree_progress_private import body


def test_manual_reset_revokes_sessions_preserves_policy_and_allows_fresh_identity(native):
    runtime, root, db, _, _, _ = native
    runtime = runtime.model_copy(update={"cloud_degree_progress_enabled": True,
                                        "cloud_degree_agent_write_enabled": True})
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as tools, \
            TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as browser:
        _, _, owner = start_and_create(tools, browser)
        credential = {**grant(browser, 'demo:read devices:bind degree:read degree:write'),
                      'platform-user-id': 'fictional-native-a',
                      'platform-attestation': attest(tools)}
        assert browser.post('/api/v1/degree/progress', json=body(owner),
                            headers=headers(owner)).status_code == 200
        for kind in ('schema_drift', 'outside_fk'):
            assert db.call('__test_reset_guard__', {'kind': kind}) == {'rejected': True, 'spaces': 1}
            assert browser.get('/api/v1/degree/progress').json()['data']['report'] is not None
        result = db.call('__test_reset_private_spaces__', {})
        assert result == {'spaces': 0, 'fixtures': 4, 'approved': 2, 'reports': 0,
                          'anonymous_execute': False, 'backend_execute': True}
        assert browser.get('/api/v1/auth/cloudbase/browser-session',
                           headers={'X-Campus-Session-Read': '1'}).status_code == 401
        assert tools.get('/oauth/degree/progress', headers=credential).status_code == 401
        # Same platform identity can start over, without stale owner collisions.
        with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as fresh:
            _, created, new_owner = start_and_create(tools, fresh)
            assert created['created'] is True
            assert new_owner['workspace_ref'] != owner['workspace_ref']
            assert fresh.get('/api/v1/degree/progress').json()['data']['report'] is None
