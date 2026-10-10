"""Own-service smoke check with fresh in-memory visitors, no browser credentials.

Creates two empty QA visitor identities only; never writes courses/tasks, exports
cookies, or touches existing users. Prints status/boolean evidence only.
"""
import json
import httpx

ORIGIN = 'https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com'


def main():
    results = {}
    with httpx.Client(base_url=ORIGIN, timeout=25, trust_env=False) as a, httpx.Client(base_url=ORIGIN, timeout=25, trust_env=False) as b:
        health = a.get('/healthz')
        results['health_status'] = health.status_code
        if health.status_code != 200:
            print(json.dumps(results)); return 1
        results['build_id'] = health.json().get('build_id')
        config = a.get('/api/v1/auth/cloudbase/config')
        results['visitor_enabled'] = config.json().get('data', {}).get('visitor_enabled') is True
        if not results['visitor_enabled']:
            print(json.dumps(results)); return 1
        begin_headers = {'Origin': ORIGIN, 'X-Campus-Visitor': '1'}
        owners = []
        for label, client in (('a', a), ('b', b)):
            response = client.post('/api/v1/auth/visitor/session', json={}, headers=begin_headers)
            results[label+'_begin_status'] = response.status_code
            if response.status_code != 200:
                results[label+'_error_code'] = response.json().get('error', {}).get('code')
                print(json.dumps(results)); return 1
            owner = response.json()['data']; owners.append(owner)
            query = {'workspace_ref': owner['workspace_ref']}
            results[label+'_empty_schedule'] = client.get('/api/v1/schedules/current', params=query).status_code == 404
            calendar = client.get('/api/v1/tasks/calendar', params=query)
            results[label+'_calendar_status'] = calendar.status_code
            results[label+'_empty_calendar'] = calendar.status_code == 200 and calendar.json()['data']['items'] == []
            results[label+'_ui_status'] = client.get('/tools/timetable').status_code
            session = client.get('/api/v1/auth/cloudbase/browser-session', headers={'X-Campus-Session-Read':'1'})
            results[label+'_resume_same_workspace'] = session.status_code == 200 and session.json()['data']['workspace_ref'] == owner['workspace_ref']
        results['distinct_workspaces'] = owners[0]['workspace_ref'] != owners[1]['workspace_ref']
        results['cross_workspace_denied'] = b.get('/api/v1/tasks/calendar', params={'workspace_ref':owners[0]['workspace_ref']}).status_code == 404
        code_headers = {'Origin':ORIGIN, 'X-Campus-Device':'1'}
        code_one = a.post('/api/v1/auth/agent-device/start', json={}, headers=code_headers)
        code_two = a.post('/api/v1/auth/agent-device/start', json={}, headers=code_headers)
        results['fixed_device_code'] = code_one.status_code == code_two.status_code == 200 and code_one.json()['data']['device_code'] == code_two.json()['data']['device_code']
        repeated = a.post('/api/v1/auth/visitor/session', json={}, headers=begin_headers)
        results['repeat_preserves_workspace'] = repeated.status_code == 200 and repeated.json()['data']['workspace_ref'] == owners[0]['workspace_ref']
        results['owner_override_denied'] = b.post('/api/v1/auth/visitor/session', json={'workspace_ref':owners[0]['workspace_ref']}, headers=begin_headers).status_code == 422
        results['foreign_origin_denied'] = b.post('/api/v1/auth/visitor/session', json={}, headers={**begin_headers,'Origin':'https://foreign.invalid'}).status_code == 403
    with httpx.Client(base_url=ORIGIN, timeout=25, trust_env=False) as unauthenticated:
        results['no_cookie_private_read_denied'] = unauthenticated.get('/api/v1/tasks/calendar', params={'workspace_ref':owners[0]['workspace_ref']}).status_code == 401
    print(json.dumps(results, ensure_ascii=False))
    return 0 if all(value is True for key, value in results.items() if not key.endswith('_status') and key != 'build_id') else 1


if __name__ == '__main__':
    raise SystemExit(main())
