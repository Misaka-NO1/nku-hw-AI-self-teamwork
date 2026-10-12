"""Own-service identity-first probe; never enroll anonymous QA owners.

Check capability before POSTing: an old enrollment deployment is not exercised.
With the new guard, generate only public device locators, then verify unknown
proof is denied. No courses/tasks/account/space are created; no Cookie export.
"""
import json
import httpx

ORIGIN = 'https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com'


def main():
    results = {}
    with httpx.Client(base_url=ORIGIN, timeout=25, trust_env=False) as client:
        health = client.get('/healthz')
        results['health_status'] = health.status_code
        if health.status_code != 200:
            print(json.dumps(results)); return 1
        results['build_id'] = health.json().get('build_id')
        config = client.get('/api/v1/auth/cloudbase/config')
        if config.status_code != 200:
            print(json.dumps(results)); return 1
        results['identity_first_enabled'] = config.json().get('data', {}).get('visitor_identity_first') is True
        if not results['identity_first_enabled']:
            results['stopped_before_post'] = True
            print(json.dumps(results)); return 1
        begin_headers = {'Origin':ORIGIN,'X-Campus-Visitor':'1'}
        device_headers = {'Origin':ORIGIN,'X-Campus-Device':'1'}
        unknown = client.post('/api/v1/auth/visitor/session', json={}, headers=begin_headers)
        results['unknown_browser_denied'] = unknown.status_code == 401 and 'set-cookie' not in unknown.headers
        if not results['unknown_browser_denied']:
            print(json.dumps(results)); return 1
        first = client.post('/api/v1/auth/agent-device/start', json={}, headers=device_headers)
        second = client.post('/api/v1/auth/agent-device/start', json={}, headers=device_headers)
        results['fixed_device_code'] = first.status_code == second.status_code == 200 and first.json()['data']['device_code'] == second.json()['data']['device_code']
        for _ in range(2):
            denied = client.post('/api/v1/auth/visitor/session', json={}, headers=begin_headers)
            results['unknown_private_proof_denied'] = denied.status_code == 401 and 'set-cookie' not in denied.headers
            if not results['unknown_private_proof_denied']:
                print(json.dumps(results)); return 1
        state = client.post('/api/v1/auth/agent-device/state', json={}, headers=device_headers)
        results['no_space_created'] = state.status_code == 200 and state.json()['data']['has_space'] is False and state.json()['data']['agent_linked'] is False
        results['no_school_identity_claim'] = state.status_code == 200 and state.json()['data']['school_identity_verified'] is False
        claim = client.post('/api/v1/auth/agent-device/claim', json={}, headers=device_headers)
        results['no_unauthorized_claim'] = claim.status_code == 200 and claim.json()['data']['status'] == 'pending' and 'set-cookie' not in claim.headers
        results['owner_override_denied'] = client.post('/api/v1/auth/visitor/session', json={'workspace_ref':'other'}, headers=begin_headers).status_code == 422
        results['foreign_origin_denied'] = client.post('/api/v1/auth/visitor/session', json={}, headers={**begin_headers,'Origin':'https://foreign.invalid'}).status_code == 403
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all(value is True for key,value in results.items() if key not in {'health_status','build_id'}) else 1


if __name__ == '__main__':
    raise SystemExit(main())
