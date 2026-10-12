from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from app.core.degree_progress import validate_save, question_progress
from app.core.errors import AppError
from app.core.security import SESSION_COOKIE,secret_hash
from test_cloud_identity_site import environment,login,headers,ORIGIN
from test_competition_oauth import exchange,PARAMS
from test_genios_identity_site import native, start_and_create, attest
from test_agent_device import grant
from urllib.parse import parse_qs,urlsplit
import re

def report():
    return {'schema_version':'1.0.0','kind':'degree_credit_progress','program':'虚构验收专业','cohort':'2025',
        'summary':{'required_credits':'150','completed_credits':'12.5','actual_credits':'15',
            'reported_result':'预审','reviewed_at':None,'note':'非最终审核'},
        'modules':[{'title':'通识选修课','required_credits':'14','school_actual_credits':'10',
            'school_status':'缺 4 学分','school_note':None}], 'has_in_progress_courses':True}

def body(owner,revision=0):
    return {'report':report(),'expected_revision':revision,'expected_workspace_ref':owner['workspace_ref'],'confirmed':True}

def test_progress_projection_math_and_no_grades():
    value=question_progress(report())
    assert value['summary']['credit_gap']=='137.5'
    assert value['modules'][0]['provisional_credit_gap']=='4'
    assert value['general_elective_policy']['minimum_modules']==4
    assert value['general_elective_policy']['verification_status']=='needs_policy'
    assert 'courses' not in value and 'grade' not in str(value)
    value=report();value['modules'][0]['required_credits']='2.3';value['modules'][0]['school_actual_credits']='2.1'
    assert question_progress(value)['modules'][0]['provisional_credit_gap']=='0.2'
    value['summary']['completed_credits']=None
    assert question_progress(value)['summary']['credit_gap'] is None

@pytest.mark.parametrize('change',[
    lambda v:v.update(owner_id='other'),lambda v:v['report'].update(courses=[]),
    lambda v:v['report']['modules'][0].update(grade='private'),
    lambda v:v['report']['modules'][0].update(required_credits='301'),
    lambda v:v.update(expected_revision=True),lambda v:v.update(confirmed='true'),
    lambda v:v['report'].update(modules=[]),lambda v:v['report'].update(program='x'*301),
])
def test_strict_payload_rejects_grades_owner_and_bad_credit(change):
    value=body({'workspace_ref':'fictional'});change(value)
    with pytest.raises(AppError) as error:validate_save(value)
    assert error.value.status_code==422

def test_private_progress_pg_owner_csrf_revision_retry_and_restart(environment):
    settings,root,store,_=environment
    settings=settings.model_copy(update={'cloud_degree_progress_enabled':True,'cloud_oauth_pilot_enabled':True,'cloud_oauth_competition_compat_enabled':True})
    with TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as a,TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as b:
        owner=login(a);other=login(b,'fictional-b')
        assert a.get('/api/v1/degree/progress').json()['data']['report'] is None
        request=body(owner)
        assert b.post('/api/v1/degree/progress',json=request,headers=headers(other,'degree-b-wrong')).status_code==403
        assert a.post('/api/v1/degree/progress',json=request,headers={**headers(owner),'X-CSRF-Token':'wrong'}).status_code==403
        assert a.post('/api/v1/degree/progress',json=request,headers={**headers(owner),'Origin':'https://evil.invalid'}).status_code==403
        unconfirmed={**request,'confirmed':False}
        assert a.post('/api/v1/degree/progress',json=unconfirmed,headers=headers(owner,'degree-unconfirmed')).status_code==409
        saved=a.post('/api/v1/degree/progress',json=request,headers=headers(owner,'degree-first-save'))
        assert saved.status_code==200,saved.text
        assert a.post('/api/v1/degree/progress',json=request,headers=headers(owner,'degree-first-save')).json()['data']==saved.json()['data']
        changed=deepcopy(request);changed['report']['modules'][0]['school_actual_credits']='12'
        assert a.post('/api/v1/degree/progress',json=changed,headers=headers(owner,'degree-first-save')).status_code==409
        assert a.post('/api/v1/degree/progress',json=changed,headers=headers(owner,'degree-second-save')).status_code==409
        changed['expected_revision']=1
        assert a.post('/api/v1/degree/progress',json=changed,headers=headers(owner,'degree-second-save')).json()['data']['revision']==2
        assert b.get('/api/v1/degree/progress').json()['data']['report'] is None
        assert b.get('/api/v1/degree/progress',params={'owner_id':owner['workspace_ref']}).status_code==422
        data=a.get('/api/v1/degree/progress').json()['data'];assert data['report']['modules'][0]['provisional_credit_gap']=='2'
        cookies=dict(a.cookies)
    with TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as restored:
        restored.cookies.update(cookies)
        assert restored.get('/api/v1/degree/progress').json()['data']==data
        assert restored.post('/api/v1/auth/cloudbase/logout',headers=headers(owner)).status_code==200
        assert restored.get('/api/v1/degree/progress').status_code==401

def test_disabled_feature_and_empty_login(environment):
    settings,root,store,client=environment
    assert client.get('/api/v1/degree/capabilities').json()['data']['private_progress_enabled'] is False
    login(client)
    assert client.get('/api/v1/degree/progress').status_code==403

def scoped_token(client,scope):
    page=client.get('/oauth/authorize',params={**PARAMS,'scope':scope})
    assert page.status_code==200,page.text
    if 'degree:read' in scope:assert '不含课程成绩' in page.text
    transaction=re.search(r'name="transaction" value="([^"]+)"',page.text)[1]
    approved=client.post('/oauth/approve',data={'transaction':transaction,'decision':'allow'},headers={'Origin':ORIGIN},follow_redirects=False)
    code=parse_qs(urlsplit(approved.headers['Location']).query)['code'][0]
    issued=exchange(client,code);assert issued.status_code==200,issued.text
    return issued.json()['access_token']

def test_oauth_degree_requires_fresh_scope_own_space_and_revocation(environment):
    settings,root,store,_=environment
    settings=settings.model_copy(update={'cloud_degree_progress_enabled':True,'cloud_oauth_competition_compat_enabled':True})
    with TestClient(create_cloud_identity_site(root,store,settings),base_url=ORIGIN) as client:
        a=login(client)
        old=scoped_token(client,'demo:read')
        assert client.post('/api/v1/degree/progress',json=body(a),headers=headers(a,'degree-agent-report')).status_code==200
        assert client.get('/oauth/degree/progress',headers={'Authorization':'Bearer '+old}).status_code==403
        token=scoped_token(client,'demo:read degree:read')
        bearer={'Authorization':'Bearer '+token}
        read=client.get('/oauth/degree/progress',headers=bearer)
        assert read.status_code==200,read.text
        assert read.json()['data']['report']['modules'][0]['provisional_credit_gap']=='4'
        assert client.get('/oauth/degree/progress?workspace_ref=other',headers=bearer).status_code==400
        b=login(client,'fictional-b')
        btoken=scoped_token(client,'demo:read degree:read')
        assert client.get('/oauth/degree/progress',headers={'Authorization':'Bearer '+btoken}).json()['data']['report'] is None
        assert client.get('/oauth/degree/progress',headers=bearer).json()['data']['revision']==1
        from test_cloud_identity_site import SECRET
        assert client.post('/oauth/revoke',json={'token':token,'client_id':PARAMS['client_id'],'client_secret':SECRET}).status_code==200
        assert client.get('/oauth/degree/progress',headers=bearer).status_code==401
        assert client.post('/api/v1/auth/cloudbase/logout',headers=headers(b)).status_code==200
        assert client.get('/oauth/degree/progress',headers={'Authorization':'Bearer '+btoken}).status_code==401

def test_native_degree_read_requires_fixed_identity_proof_and_matching_grant(native):
    runtime,root,db,_,_,_=native
    runtime=runtime.model_copy(update={'cloud_degree_progress_enabled':True})
    app=create_cloud_identity_site(root,db,runtime)
    with TestClient(app,base_url=ORIGIN) as tools,TestClient(app,base_url=ORIGIN) as a,TestClient(app,base_url=ORIGIN) as b:
        _,_,owner=start_and_create(tools,a)
        _,_,other=start_and_create(tools,b,'fictional-native-b')
        assert a.post('/api/v1/degree/progress',json=body(owner),headers=headers(owner,'native-degree-save')).status_code==200
        scope='demo:read tasks:read tasks:write devices:bind degree:read'
        bearer=grant(a,scope)
        proof=attest(tools)
        checked={**bearer,'platform-user-id':'fictional-native-a','platform-attestation':proof}
        result=tools.get('/oauth/degree/progress',headers=checked)
        assert result.status_code==200,result.text
        assert result.json()['data']['report']['modules'][0]['provisional_credit_gap']=='4'
        assert tools.get('/oauth/degree/progress',headers=bearer).status_code==401
        assert tools.get('/oauth/degree/progress',headers={**checked,'platform-user-id':'fictional-native-b'}).status_code==401
        wrong={**checked,**grant(b,scope)}
        assert tools.get('/oauth/degree/progress',headers=wrong).status_code==403
        assert a.get('/oauth/degree/progress',headers=checked).status_code==403
        assert tools.get('/oauth/degree/progress',headers={**checked,**grant(a)}).status_code==403

def test_database_also_rejects_direct_grade_or_bad_schema(environment):
    settings,root,db,client=environment
    owner=login(client)
    base={'principal_kind':'browser','session_hash':secret_hash(client.cookies.get(SESSION_COOKIE)),
        'csrf_hash':secret_hash(owner['csrf_token']),**body(owner),'key':'direct-degree-test','request_hash':'a'*64}
    for changed in [{'grade':'private'},{'owner_id':'another'},
        {'school_in_progress_credits':'11'},
        {'school_in_progress_credits':'3','school_direct_in_progress_credits':'4'},
        {'school_in_progress_credits':None,'school_direct_in_progress_credits':'1'},
        {'school_in_progress_credits':3},
        {'school_in_progress_credits':'-1'}]:
        request=deepcopy(base);request['report']['modules'][0].update(changed)
        with pytest.raises(AppError) as error:db.degree_call('save',request)
        assert error.value.status_code==422
    request=deepcopy(base);request['report']['schema_version']=None
    with pytest.raises(AppError) as error:db.degree_call('save',request)
    assert error.value.status_code==422
