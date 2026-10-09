from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from app.core.demo import load_fixture
from app.core.security import SESSION_COOKIE, secret_hash
from test_cloud_identity_site import environment, login, headers, ORIGIN

def personal(title="本地隔离测试课程"):
 value=deepcopy(load_fixture("timetable.demo.json"))
 value["dataset_kind"]="personal";value["term"]["calendar_status"]="user_confirmed"
 value["courses"][0]["title"]=title;value["source"]["kind"]="file"
 return value

def create(client,owner,payload,key):
 r=client.post('/api/v1/schedules/import-drafts',json=payload,headers=headers(owner,key+'-draft'))
 assert r.status_code==200,r.text
 return client.get('/api/v1/drafts/'+r.json()['data']['draft_id']).json()['data']

def confirm(client,owner,d,key):
 r=client.post('/api/v1/confirmations',json={k:d[k] for k in ('draft_id','revision','payload_hash')},headers=headers(owner,key+'-confirm'))
 assert r.status_code==200,r.text
 return {'confirmation_id':r.json()['data']['confirmation_id'],'idempotency_key':key+'-commit'}

def test_personal_payload_http_save_edit_restart_and_account_isolation(environment):
 settings,root,store,_=environment
 settings=settings.model_copy(update={'cloud_personal_schedules_enabled':True,'cloud_notice_text_pilot_enabled':True})
 with TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as a, TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as b:
  owner=login(a);other=login(b,'fictional-b');payload=personal()
  assert a.post('/api/v1/schedules/validate',json=payload,headers=headers(owner)).status_code==200
  d=create(a,owner,payload,'personal-one')
  assert b.get('/api/v1/drafts/'+d['draft_id']).status_code==404
  assert b.post('/api/v1/schedules/import-drafts',json=payload,headers=headers(owner,'wrong-owner-key')).status_code==403
  args=confirm(a,owner,d,'personal-one')
  assert b.post('/api/v1/schedules/commit',json=args,headers=headers(other)).status_code==404
  saved=a.post('/api/v1/schedules/commit',json=args,headers=headers(owner));assert saved.status_code==200,saved.text
  assert a.post('/api/v1/schedules/commit',json=args,headers=headers(owner)).json()['data']==saved.json()['data']
  current=a.get('/api/v1/schedules/current',params={'workspace_ref':owner['workspace_ref']}).json()['data']
  assert current['timetable']['courses'][0]['title']==payload['courses'][0]['title']
  assert b.get('/api/v1/schedules/current',params={'workspace_ref':owner['workspace_ref']}).status_code==404
  records=store.notice_call('records',{'principal_kind':'browser','session_hash':secret_hash(a.cookies.get(SESSION_COOKIE)),'csrf_hash':secret_hash('')})
  assert records['schedule']['timetable']==current['timetable']
  old_records_revision=records['records_revision']
  stale=create(a,owner,personal('older'),'personal-stale')
  fresh=create(a,owner,personal('edited'),'personal-edited');receipt=confirm(a,owner,fresh,'personal-edited')
  assert a.post('/api/v1/schedules/commit',json=receipt,headers=headers(owner)).status_code==200
  records=store.notice_call('records',{'principal_kind':'browser','session_hash':secret_hash(a.cookies.get(SESSION_COOKIE)),'csrf_hash':secret_hash('')})
  assert records['records_revision']!=old_records_revision
  assert a.post('/api/v1/confirmations',json={k:stale[k] for k in ('draft_id','revision','payload_hash')},headers=headers(owner,'personal-stale-confirm')).status_code==409
  cookies=dict(a.cookies)
 with TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as restored:
  restored.cookies.update(cookies)
  current=restored.get('/api/v1/schedules/current',params={'workspace_ref':owner['workspace_ref']}).json()['data']
  assert current['revision']==2 and current['timetable']['courses'][0]['title']=='edited'
  login(restored)
  assert restored.get('/api/v1/schedules/current',params={'workspace_ref':owner['workspace_ref']}).json()['data']['revision']==2

def test_personal_schedule_gate_semantics_calendar_and_origin(environment):
 settings,root,store,_=environment
 with TestClient(create_cloud_identity_site(root,store,settings.model_copy(update={'cloud_personal_schedules_enabled':True})),base_url=ORIGIN) as client:
  owner=login(client);payload=personal();payload['term']['calendar_status']='demo'
  assert client.post('/api/v1/schedules/import-drafts',json=payload,headers=headers(owner,'bad-calendar')).status_code==422
  payload=personal();payload['courses'][0]['meetings'][0]['start_period']=999
  assert client.post('/api/v1/schedules/import-drafts',json=payload,headers=headers(owner,'bad-period')).status_code==422
  assert client.post('/api/v1/schedules/import-drafts',json=personal(),headers={**headers(owner),'Origin':'https://evil.invalid'}).status_code==403
