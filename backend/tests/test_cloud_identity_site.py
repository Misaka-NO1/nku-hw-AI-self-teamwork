"""HTTP + real embedded PostgreSQL integration. CloudBase verifier is mocked;
these tests are NOT evidence of cloud or school-platform live acceptance.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs,urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.cloud_identity_site import create_cloud_identity_site
from app.cloud_tasks_site import ENV_ID
from app.core.cloud_identity_store import CloudIdentityStore,storage_result,RPC_URL
from app.core.config import Settings
from app.core.demo import load_fixture
from app.core.errors import AppError
from app.core.security import secret_hash
from app.core.cloud_oauth_provider import SCHOOL_CALLBACK
from app.core.browser_session_context import CONTEXT_COOKIE,encode_context

ROOT=Path(__file__).parents[2]
SQL_DIR=ROOT/'deploy/cloudbase-identity-pilot/sql-tests'
SECRET='fictional-oauth-test-only-'+('q'*48)
VERIFIER='dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
CHALLENGE='E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'
ORIGIN='https://pilot.example.invalid'


class RealPostgresPipeStore:
    def __init__(self):
        self.process=subprocess.Popen([shutil.which('node'),'rpc-test-driver.mjs'],cwd=SQL_DIR,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
        assert json.loads(self.process.stdout.readline())=={'ready':True}
        self.lock=Lock()
    def call(self,op,args):
        with self.lock:
            self.process.stdin.write(json.dumps({'op':op,'args':args})+'\n'); self.process.stdin.flush()
            result=json.loads(self.process.stdout.readline())
        if result.get('driver_error'): raise AssertionError('SQL driver failed without disclosing request parameters')
        return storage_result(result)
    def close(self): pass  # HTTP transport restarts do not destroy the database.
    def competition_call(self,op,args): return self.call('__competition__:'+op,args)
    def notice_call(self,op,args): return self.call('__notice__:'+op,args)
    def calendar_call(self,op,args): return self.call('__calendar__:'+op,args)
    def shutdown(self):
        self.process.stdin.close(); self.process.wait(timeout=20)


@pytest.fixture
def environment(tmp_path,monkeypatch):
    if not shutil.which('node') or not (SQL_DIR/'node_modules/@electric-sql/pglite/package.json').is_file():
        pytest.skip('Install pinned SQL-test dependencies to run actual PostgreSQL integration tests')
    settings=Settings(_env_file=None,app_env='test',app_origin=ORIGIN,cloud_identity_pilot_enabled=True,
        cloudbase_auth_pilot_enabled=True,cloudbase_auth_profile='pg_registered',cloudbase_auth_env_id=ENV_ID,
        cloudbase_auth_pilot_user_ids=['fictional-a','fictional-b'],cloud_oauth_pilot_enabled=True,
        oauth_client_id='test-school-agent',agent_pairing_audience='test-school-agent',oauth_redirect_uri=SCHOOL_CALLBACK,
        oauth_client_secret_hash=SecretStr(secret_hash(SECRET)),build_id='fictional-pg-test')
    async def verify(runtime,authorization):
        if authorization not in {'Bearer fictional-a','Bearer fictional-b'}:
            raise AppError(403,'FORBIDDEN','Not an approved fictional credential')
        return 'cloudbase_pilot_'+secret_hash(runtime.cloudbase_auth_env_id+':'+authorization.removeprefix('Bearer '))
    monkeypatch.setattr('app.cloud_identity_site.verify_cloudbase_user',verify)
    root=tmp_path/'web'; (root/'assets').mkdir(parents=True); (root/'index.html').write_text('<html>fixture UI</html>',encoding='utf-8')
    database=RealPostgresPipeStore()
    try:
        with TestClient(create_cloud_identity_site(root,database,settings),base_url=ORIGIN) as client:
            yield settings,root,database,client
    finally: database.shutdown()


def login(client,name='fictional-a'):
    response=client.post('/api/v1/auth/cloudbase/session',headers={'Origin':ORIGIN,'Authorization':'Bearer '+name})
    assert response.status_code==200
    return response.json()['data']


def test_competition_c_pages_and_real_degree_algorithm(environment):
    _,_,_,client=environment
    for path in ('/tools/affairs','/tools/degree','/tools/calendar'):
        assert client.get(path).status_code==200
    request={'workspace_ref':'demo-workspace-01','plan_id':'demo-cs-plan-v1','transcript_ref':'demo-transcript-01'}
    response=client.post('/api/v1/degree/audit',json=request)
    assert response.status_code==200
    envelope=response.json()
    assert envelope['ok'] is True and envelope['data']['status']=='incomplete'
    assert envelope['meta']['calculation_version']
    assert any(w['code']=='NOT_GRADUATION_DECISION' for w in envelope['meta']['warnings'])
    assert envelope['data']['modules']
    assert client.post('/api/v1/degree/audit',json={**request,'plan_id':'unknown-plan'}).status_code==404
    assert client.post('/api/v1/degree/audit',json={**request,'workspace_ref':'someone-elses-workspace'}).status_code==403
    assert client.post('/api/v1/degree/audit',json={**request,'records':[]}).status_code==422


def headers(owner,key='test-write-key-001'):
    return {'Origin':ORIGIN,'X-CSRF-Token':owner['csrf_token'],'Idempotency-Key':key}


def save(client,owner,kind='task',fixture='notice-event.demo.json',key='test-save-001'):
    key=key+'-'+kind
    payload=load_fixture(fixture)
    url='/api/v1/tasks/drafts' if kind=='task' else '/api/v1/schedules/import-drafts'
    body={'workspace_ref':owner['workspace_ref'],'notice':payload} if kind=='task' else payload
    created=client.post(url,json=body,headers=headers(owner,key+'-draft'))
    assert created.status_code==200,created.text
    draft=client.get('/api/v1/drafts/'+created.json()['data']['draft_id']).json()['data']
    confirmed=client.post('/api/v1/confirmations',json={'draft_id':draft['draft_id'],'revision':draft['revision'],'payload_hash':draft['payload_hash']},headers=headers(owner,key+'-confirm'))
    assert confirmed.status_code==200,confirmed.text
    args={'confirmation_id':confirmed.json()['data']['confirmation_id'],'idempotency_key':key+'-commit'}
    result=client.post('/api/v1/'+('tasks' if kind=='task' else 'schedules')+'/commit',json=args,headers=headers(owner))
    assert result.status_code==200,result.text
    assert client.post('/api/v1/'+('tasks' if kind=='task' else 'schedules')+'/commit',json=args,headers=headers(owner)).json()['data']==result.json()['data']
    return draft,result.json()['data']


def authorize(client,scope='demo:read demo:draft'):
    response=client.get('/oauth/authorize',params={'response_type':'code','client_id':'test-school-agent','redirect_uri':SCHOOL_CALLBACK,
        'scope':scope,'state':'fictional-pg-state-20261002','code_challenge':CHALLENGE,'code_challenge_method':'S256'})
    assert response.status_code==200,response.text
    transaction=re.search(r'name="transaction" value="([^"]+)"',response.text)[1]
    approved=client.post('/oauth/approve',data={'transaction':transaction,'decision':'allow'},headers={'Origin':ORIGIN},follow_redirects=False)
    assert approved.status_code==303,approved.text
    return parse_qs(urlsplit(approved.headers['Location']).query)['code'][0]


def exchange(client,code,**changes):
    return client.post('/oauth/token',json={'client_id':'test-school-agent','client_secret':SECRET,'grant_type':'authorization_code',
        'code':code,'redirect_uri':SCHOOL_CALLBACK,'code_verifier':VERIFIER,**changes})


def test_cloud_http_save_readback_relogin_and_backend_restart(environment):
    settings,root,database,client=environment
    a=login(client)
    cookie=client.cookies.get('campus_session')
    assert 'HttpOnly' in client.post('/api/v1/auth/cloudbase/session',headers={'Origin':ORIGIN,'Authorization':'Bearer fictional-a'}).headers['set-cookie']
    a=login(client)
    save(client,a,'schedule','timetable.demo.json')
    _,task=save(client,a)
    tasks=client.get('/api/v1/tasks',params={'workspace_ref':a['workspace_ref']})
    assert len(tasks.json()['data'])==1 and tasks.json()['data'][0]['task_id']==task['task_id']
    assert tasks.json()['data'][0]['confirmed_at'].endswith('+08:00')
    owner_cookie=client.cookies.get('campus_session')
    with TestClient(create_cloud_identity_site(root,database,settings),base_url=ORIGIN) as restarted:
        restarted.cookies.set('campus_session',owner_cookie)
        assert restarted.get('/api/v1/tasks',params={'workspace_ref':a['workspace_ref']}).json()['data']==tasks.json()['data']
        assert restarted.get('/api/v1/schedules/current',params={'workspace_ref':a['workspace_ref']}).status_code==200


def test_cloud_http_account_isolation_and_csrf(environment):
    _,_,_,client=environment
    a=login(client); draft,task=save(client,a)
    b=login(client,'fictional-b')
    assert client.get('/api/v1/tasks',params={'workspace_ref':b['workspace_ref']}).json()['data']==[]
    assert client.get('/api/v1/schedules/current',params={'workspace_ref':b['workspace_ref']}).status_code==404
    assert client.get('/api/v1/tasks',params={'workspace_ref':a['workspace_ref']}).status_code==404
    assert client.get('/api/v1/tasks/'+task['task_id']).status_code==404
    assert client.get('/api/v1/drafts/'+draft['draft_id']).status_code==404
    response=client.post('/api/v1/tasks/drafts',json={'workspace_ref':b['workspace_ref'],'notice':load_fixture('notice-event.demo.json')},headers={'Origin':ORIGIN,'Idempotency-Key':'test-csrf-001'})
    assert response.status_code==403
    assert client.post('/api/v1/auth/cloudbase/logout',headers=headers(b)).status_code==200
    assert client.get('/api/v1/tasks',params={'workspace_ref':b['workspace_ref']}).status_code==401


def test_cloud_http_new_tab_resumes_without_rotating_session_or_grant(environment):
    settings,root,database,client=environment
    a=login(client)
    code=authorize(client)
    bearer={'Authorization':'Bearer '+exchange(client,code).json()['access_token']}
    created=client.post('/oauth/task-drafts',headers=bearer,json={
        'fixture_id':'notice-event.demo.json','idempotency_key':'new-tab-resume-draft-001'})
    assert created.status_code==200,created.text
    draft_id=created.json()['data']['draft_id']
    original_cookies=dict(client.cookies)
    with TestClient(create_cloud_identity_site(root,database,settings),base_url=ORIGIN) as new_tab:
        for name,value in original_cookies.items(): new_tab.cookies.set(name,value)
        resumed=new_tab.get('/api/v1/auth/cloudbase/browser-session',headers={'X-Campus-Session-Read':'1','Sec-Fetch-Site':'same-origin'})
        assert resumed.status_code==200
        value=resumed.json()['data']
        assert value['workspace_ref']==a['workspace_ref'] and value['csrf_token']==a['csrf_token']
        assert value['expires_at']==a['expires_at']
        assert value['dataset_kind']=='demo' and value['personal_uploads'] is False and value['agent_paired'] is False
        assert 'set-cookie' not in resumed.headers
        assert 'no-store' in resumed.headers['cache-control']
        assert new_tab.cookies.get('campus_session')==original_cookies['campus_session']
        draft=new_tab.get('/api/v1/drafts/'+draft_id).json()['data']
        assert draft['status']=='draft'
        assert new_tab.get('/api/v1/tasks',params={'workspace_ref':a['workspace_ref']}).json()['data']==[]
        approved=new_tab.post('/api/v1/confirmations',headers=headers(value,'resume-confirm-001'),json={
            'draft_id':draft_id,'revision':draft['revision'],'payload_hash':draft['payload_hash']})
        assert approved.status_code==200
        assert new_tab.get('/oauth/records',headers=bearer).status_code==200


def test_cloud_http_resume_origin_parameters_and_revocation_fail_closed(environment):
    _,_,_,client=environment
    path='/api/v1/auth/cloudbase/browser-session'
    read={'X-Campus-Session-Read':'1'}
    assert client.get(path,headers=read).status_code==401
    a=login(client)
    assert client.get(path).status_code==403
    assert client.get(path,headers={**read,'Origin':'https://foreign.invalid'}).status_code==403
    assert client.get(path,headers={**read,'Sec-Fetch-Site':'cross-site'}).status_code==403
    for query in ['workspace_ref=other','access_token=not-a-bearer','owner_id=other']:
        assert client.get(path+'?'+query,headers=read).status_code==422
    assert client.request('GET',path,content=b'{}',headers=read).status_code==422
    raw_session=client.cookies.get('campus_session')
    context=client.cookies.get(CONTEXT_COOKIE)
    client.cookies.clear()
    client.cookies.set('campus_session',raw_session)
    assert client.get(path,headers=read).status_code==401  # Pre-r5 session: log in once, never invent CSRF.
    client.cookies.set(CONTEXT_COOKIE,context)
    assert client.get(path,headers=read).status_code==200
    assert client.post('/api/v1/auth/cloudbase/logout',headers=headers(a)).status_code==200
    client.cookies.set('campus_session',raw_session)
    client.cookies.set(CONTEXT_COOKIE,context)
    assert client.get(path,headers=read).status_code==401


def test_cloud_http_resume_context_is_not_an_independent_or_cross_user_credential(environment):
    _,_,_,client=environment
    a=login(client); old_context=client.cookies.get(CONTEXT_COOKIE)
    b=login(client,'fictional-b'); b_session=client.cookies.get('campus_session')
    client.cookies.clear(); client.cookies.set('campus_session',b_session); client.cookies.set(CONTEXT_COOKIE,old_context)
    path='/api/v1/auth/cloudbase/browser-session'; read={'X-Campus-Session-Read':'1'}
    assert client.get(path,headers=read).status_code==401
    # Even a context signed with B's session must match the DB-verified owner/workspace.
    expiry=int(__import__('datetime').datetime.fromisoformat(b['expires_at']).timestamp())
    client.cookies.set(CONTEXT_COOKIE,encode_context(b_session,a['workspace_ref'],b['csrf_token'],expiry))
    assert client.get(path,headers=read).status_code==401
    client.cookies.clear(); client.cookies.set(CONTEXT_COOKIE,old_context)
    assert client.get(path,headers=read).status_code==401


def test_cloud_http_resume_rejects_large_and_chunked_get_body_before_owner_read(environment,monkeypatch):
    _,_,database,client=environment
    operations=[]
    original=database.call
    def tracked(op,args):
        operations.append(op)
        return original(op,args)
    monkeypatch.setattr(database,'call',tracked)
    path='/api/v1/auth/cloudbase/browser-session'
    read={'X-Campus-Session-Read':'1'}
    assert client.request('GET',path,headers=read,content=b'x'*32769).status_code==422
    assert 'get_workspace' not in operations
    operations.clear()
    response=client.request('GET',path,headers={**read,'Transfer-Encoding':'chunked'},
        content=iter([b'first-invalid-body',b'x'*32769]))
    assert response.status_code==422
    assert 'get_workspace' not in operations


def test_cloud_http_resume_cookie_attributes_logout_and_no_cors(environment):
    _,_,_,client=environment
    response=client.post('/api/v1/auth/cloudbase/session',headers={'Origin':ORIGIN,'Authorization':'Bearer fictional-a'})
    assert response.status_code==200
    cookies=response.headers.get_list('set-cookie')
    assert len(cookies)==2
    assert {value.split('=',1)[0] for value in cookies}=={'campus_session',CONTEXT_COOKIE}
    for value in cookies:
        assert all(attribute in value for attribute in ('HttpOnly','Secure','SameSite=strict','Max-Age=900','Path=/'))
    a=response.json()['data']
    path='/api/v1/auth/cloudbase/browser-session'
    preflight=client.options(path,headers={'Origin':'https://foreign.invalid',
        'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'X-Campus-Session-Read'})
    assert 'access-control-allow-origin' not in preflight.headers
    restored=client.get(path,headers={'X-Campus-Session-Read':'1'})
    assert restored.status_code==200 and 'access-control-allow-origin' not in restored.headers
    logout=client.post('/api/v1/auth/cloudbase/logout',headers=headers(a))
    removed=logout.headers.get_list('set-cookie')
    assert len(removed)==2
    assert {value.split('=',1)[0] for value in removed}=={'campus_session',CONTEXT_COOKIE}
    assert all('Max-Age=0' in value and 'HttpOnly' in value and 'Secure' in value for value in removed)


def test_cloud_http_resume_rechecks_original_pg_expiry_and_approved_user(environment):
    settings,_,database,client=environment
    a=login(client)
    raw=client.cookies.get('campus_session')
    path='/api/v1/auth/cloudbase/browser-session'; read={'X-Campus-Session-Read':'1'}
    assert client.get(path,headers=read).status_code==200
    database.call('__test_expire_browser_session__',{'token_hash':secret_hash(raw)})
    # Context still has its original future expiry; the DB session gate wins.
    assert client.get(path,headers=read).status_code==401
    a=login(client)
    subjects=['cloudbase_pilot_'+secret_hash(settings.cloudbase_auth_env_id+':'+name)
        for name in ['fictional-b','fictional-c-not-approved-by-http-verifier']]
    database.call('configure_subjects',{'subjects':subjects})
    assert client.get(path,headers=read).status_code==401


def test_cloud_http_timetable_time_queries_only_use_own_saved_records(environment):
    _,_,_,client=environment
    a=login(client)
    query={'workspace_ref':a['workspace_ref'],'window':{'start':'2026-09-07T08:00:00+08:00','end':'2026-09-07T18:00:00+08:00'},'min_minutes':30,
        'buffers':{'before_minutes':0,'after_minutes':0}}
    assert client.post('/api/v1/time/free-slots',json=query).status_code==404
    save(client,a,'schedule','timetable.demo.json')
    result=client.post('/api/v1/time/free-slots',json=query)
    assert result.status_code==200,result.text
    assert result.json()['data']['coverage']['completeness']=='unknown'
    b=login(client,'fictional-b')
    assert client.post('/api/v1/time/free-slots',json=query).status_code==404


def test_cloud_http_oauth_read_and_draft_cannot_save_or_override_owner(environment):
    _,_,_,client=environment
    a=login(client); save(client,a)
    code=authorize(client); response=exchange(client,code)
    assert response.status_code==200,response.text
    token=response.json()['access_token']; bearer={'Authorization':'Bearer '+token}
    assert len(client.get('/oauth/records',headers=bearer).json()['data']['tasks'])==1
    assert exchange(client,code).json()=={'error':'invalid_grant'}
    draft=client.post('/oauth/task-drafts',json={'fixture_id':'notice-deadline.demo.json','idempotency_key':'oauth-test-draft-001'},headers=bearer)
    assert draft.status_code==200,draft.text
    assert draft.json()['data']['review_url'].startswith(ORIGIN+'/tools/tasks?draft_id=')
    assert len(client.get('/oauth/records',headers=bearer).json()['data']['tasks'])==1
    assert client.post('/oauth/commit',json={},headers=bearer).status_code==404
    assert client.post('/api/v1/tasks/commit',json={'confirmation_id':'unknown','idempotency_key':'wrong-commit-001'},headers=bearer).status_code==403
    b=login(client,'fictional-b')
    assert client.get('/api/v1/drafts/'+draft.json()['data']['draft_id']).status_code==404
    assert client.get('/oauth/records',params={'workspace_ref':b['workspace_ref']},headers=bearer).status_code==401


def test_cloud_http_oauth_read_only_revoke_logout_and_restart(environment):
    settings,root,database,client=environment
    a=login(client); code=authorize(client,scope='demo:read'); token=exchange(client,code).json()['access_token']
    bearer={'Authorization':'Bearer '+token}
    assert client.post('/oauth/task-drafts',json={'fixture_id':'notice-event.demo.json','idempotency_key':'read-only-draft-001'},headers=bearer).status_code==403
    with TestClient(create_cloud_identity_site(root,database,settings),base_url=ORIGIN) as next_client:
        assert next_client.get('/oauth/records',headers=bearer).status_code==200
    assert client.post('/oauth/revoke',json={'client_id':'test-school-agent','client_secret':SECRET,'token':token}).status_code==200
    assert client.get('/oauth/records',headers=bearer).status_code==403
    token=exchange(client,authorize(client)).json()['access_token']
    assert client.post('/api/v1/auth/cloudbase/logout',headers=headers(a)).status_code==200
    assert client.get('/oauth/records',headers={'Authorization':'Bearer '+token}).status_code==401


def test_cloud_oauth_time_uses_grant_owner_saved_records_and_b_algorithms(environment):
    _,_,_,client=environment
    example=json.loads((ROOT/'fixtures/oauth-pilot.demo.json').read_text(encoding='utf-8'))
    free=example['owned_free_time']; check=example['owned_time_check']
    a=login(client)
    bearer={'Authorization':'Bearer '+exchange(client,authorize(client,scope='demo:read')).json()['access_token']}
    def query(path,payload,auth=bearer):
        return client.post('/oauth/time/'+path,json={'query_json':json.dumps(payload)},headers=auth)
    assert query('free-slots',free).status_code==404  # No public timetable fallback.
    save(client,a,'schedule','timetable.demo.json')
    browser_before=client.post('/api/v1/time/free-slots',json={'workspace_ref':a['workspace_ref'],**free}).json()
    assert query('free-slots',free).json()['data']==browser_before['data']
    save(client,a)  # The confirmed 09:20-10:20 task blocks a formerly free gap.
    browser=client.post('/api/v1/time/free-slots',json={'workspace_ref':a['workspace_ref'],**free}).json()
    result=query('free-slots',free)
    assert result.status_code==200 and result.json()['data']==browser['data']
    assert result.json()['data']!=browser_before['data']
    assert result.json()['meta']['calculation_version']==browser['meta']['calculation_version']
    assert result.json()['data']['coverage']['completeness']=='unknown'
    conflict=query('check',check)
    assert conflict.status_code==200 and len(conflict.json()['data']['conflicts'])==1
    assert conflict.json()['data']['conflicts'][0]['source_event_id'].startswith('task:')
    due={**check,'kind':'deadline_feasibility','event':None,
         'due':{'at':None,'date':'2026-09-21','precision':'date_only'}}
    pending=query('check',due).json()['data']
    assert pending['candidate_slots']==[] and set(pending['needs_confirmation'])=={'due_time','estimated_minutes','earliest_start'}
    due.update(due={'at':'2026-09-21T12:00:00+08:00','date':None,'precision':'datetime'},
               estimated_minutes=30,earliest_start='2026-09-21T08:00:00+08:00')
    expected=client.post('/api/v1/time/check',json={'workspace_ref':a['workspace_ref'],**due}).json()['data']
    assert query('check',due).json()['data']==expected
    b=login(client,'fictional-b')
    # A's token must not become B's identity merely because the browser switched.
    assert query('free-slots',free).json()['data']==browser['data']
    b_bearer={'Authorization':'Bearer '+exchange(client,authorize(client,scope='demo:read')).json()['access_token']}
    assert query('free-slots',free,b_bearer).status_code==404
    assert query('free-slots',free,{}).status_code==401  # Browser cookie alone is insufficient.
    assert client.post('/oauth/time/free-slots',params={'workspace_ref':a['workspace_ref']},
                       json={'query_json':json.dumps(free)},headers=bearer).status_code==401
    for override in example['invalid_owned_time']:
        rejected=query('free-slots',{**free,**override})
        assert rejected.status_code==422,rejected.text
        assert 'foreign-workspace' not in rejected.text and 'foreign-user' not in rejected.text
    for malformed in ('{"window":{},"window":{}}','{"min_minutes":NaN}','[]','"double-encoded"'):
        assert client.post('/oauth/time/free-slots',json={'query_json':malformed},headers=bearer).status_code==422
    assert client.post('/oauth/time/free-slots',json={'query_json':json.dumps(free),'user_id':'override'},headers=bearer).status_code==422
    assert client.post('/oauth/revoke',json={'client_id':'test-school-agent','client_secret':SECRET,
                                           'token':bearer['Authorization'][7:]}).status_code==200
    assert query('free-slots',free).status_code==403


def test_cloud_http_import_ticket_and_fixture_gate(environment):
    _,_,_,client=environment
    a=login(client)
    issue={'workspace_ref':a['workspace_ref'],'purpose':'schedule_import'}
    result=client.post('/api/v1/import-tickets',json=issue,headers=headers(a,'issue-key-001'))
    assert result.status_code==200,result.text
    assert client.post('/api/v1/import-tickets',json=issue,headers=headers(a,'issue-key-001')).status_code==409
    token=result.json()['data']['import_ticket']; client.cookies.clear()
    response=client.post('/api/v1/schedules/import-drafts',json=load_fixture('timetable.demo.json'),headers={'Authorization':'ImportTicket '+token,'Idempotency-Key':'ticket-import-001'})
    assert response.status_code==200,response.text
    assert client.post('/api/v1/schedules/import-drafts',json=load_fixture('timetable.demo.json'),headers={'Authorization':'ImportTicket '+token,'Idempotency-Key':'ticket-import-002'}).status_code==410
    a=login(client)
    notice={**load_fixture('notice-event.demo.json'),'title':'unapproved-personal-text'}
    assert client.post('/api/v1/tasks/drafts',json={'workspace_ref':a['workspace_ref'],'notice':notice},headers=headers(a)).status_code==403
    assert client.post('/api/v1/demo/workspaces',json={'fixture_set_id':'demo-v1'}).status_code==401


def test_cloud_http_login_rate_limit_is_shared_across_instances(environment):
    settings,root,database,client=environment
    with TestClient(create_cloud_identity_site(root,database,settings),base_url=ORIGIN) as another:
        for attempt in range(10):
            target=client if attempt%2==0 else another
            assert target.post('/api/v1/auth/cloudbase/session',json={},headers={'Origin':ORIGIN,'Authorization':'Bearer fictional-a'}).status_code==200
        response=another.post('/api/v1/auth/cloudbase/session',json={},headers={'Origin':ORIGIN,'Authorization':'Bearer fictional-a'})
        assert response.status_code==429 and response.json()['error']['code']=='RATE_LIMITED'


def test_cloud_http_oauth_anonymous_resume_is_same_origin_and_not_auto_approved(environment):
    _,_,_,client=environment
    params={'response_type':'code','client_id':'test-school-agent','redirect_uri':SCHOOL_CALLBACK,'scope':'demo:read',
            'state':'fictional-state-only-001','code_challenge':CHALLENGE,'code_challenge_method':'S256'}
    response=client.get('/oauth/authorize',params=params,follow_redirects=False)
    assert response.status_code==303
    location=urlsplit(response.headers['Location'])
    assert location.scheme=='' and location.netloc=='' and location.path=='/tools/login'
    next_url=parse_qs(location.query)['return_to'][0]
    assert urlsplit(next_url).path=='/oauth/authorize'
    assert client.get(response.headers['Location']).status_code==200
    login(client)
    consent=client.get(next_url)
    assert consent.status_code==200 and '允许本次授权' in consent.text
    assert 'Location' not in consent.headers  # Still awaits explicit consent.
    client.cookies.clear()
    for bad in ({**params,'redirect_uri':'https://attacker.invalid/'},{**params,'code_challenge_method':'plain'}, {**params,'access_token':'not-accepted'}):
        assert client.get('/oauth/authorize',params=bad,follow_redirects=False).status_code==400


@pytest.mark.parametrize('change',[{'cloud_identity_pilot_enabled':False},{'allow_personal_uploads':True},{'app_env':'production'},
    {'cloudbase_auth_pilot_user_ids':['one']},{'cloudbase_auth_env_id':'different-env'},{'app_origin':'http://untrusted.example.invalid'}])
def test_cloud_identity_fails_closed_before_connecting_database(tmp_path,change):
    settings=Settings(_env_file=None,app_env='test',app_origin=ORIGIN,cloud_identity_pilot_enabled=True,
        cloudbase_auth_pilot_enabled=True,cloudbase_auth_profile='pg_registered',cloudbase_auth_env_id=ENV_ID,
        cloudbase_auth_pilot_user_ids=['fictional-a','fictional-b'])
    with pytest.raises((ValueError,AppError)):
        create_cloud_identity_site(tmp_path,settings=settings.model_copy(update=change))


def test_cloud_store_pins_url_no_redirects_and_sanitizes_upstream():
    def malicious(request):
        assert str(request.url)==RPC_URL
        return httpx.Response(302,headers={'Location':'https://attacker.example.invalid/'},json={'key':'never-disclose'})
    with pytest.raises(AppError) as result:
        CloudIdentityStore('fictional-server-key',httpx.MockTransport(malicious)).call('probe',{})
    assert result.value.status_code==503 and 'never-disclose' not in result.value.message


def test_bootstrap_has_no_credentials_database_login_oauth_or_business(tmp_path):
    settings=Settings(_env_file=None,app_env='staging',cloud_identity_bootstrap_enabled=True,build_id='bootstrap-only')
    with TestClient(create_cloud_identity_site(tmp_path,settings=settings)) as client:
        health=client.get('/healthz').json()
        assert health['status']=='configuration_pending' and health['database_connected'] is False
        assert client.get('/__tcb_probe__').text=='ok'
        for method,path in [('get','/tools/login'),('get','/oauth/authorize'),('post','/api/v1/auth/cloudbase/session'),('get','/api/v1/tasks')]:
            assert getattr(client,method)(path).status_code==503
    with pytest.raises(ValueError):
        create_cloud_identity_site(tmp_path,settings=settings.model_copy(update={'cloud_identity_pilot_enabled':True}))
