"""Exact school five-field transport against real embedded PG, not live proof."""
import base64
import re
from urllib.parse import parse_qs,urlsplit

import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.core.cloud_oauth_provider import SCHOOL_CALLBACK
from app.core.demo import load_fixture
from test_cloud_identity_site import environment,login,headers,save,SECRET,ORIGIN


PARAMS={"response_type":"code","client_id":"test-school-agent","redirect_uri":SCHOOL_CALLBACK,
        "scope":"demo:read","state":"a123456789"}


@pytest.fixture
def compatible(environment):
    settings,root,store,_=environment
    runtime=settings.model_copy(update={"cloud_oauth_competition_compat_enabled":True})
    with TestClient(create_cloud_identity_site(root,store,runtime),base_url=ORIGIN) as client:
        yield client,store,runtime


def authorize(client):
    page=client.get('/oauth/authorize',params=PARAMS)
    assert page.status_code==200,page.text
    transaction=re.search(r'name="transaction" value="([^"]+)"',page.text)[1]
    result=client.post('/oauth/approve',data={"transaction":transaction,"decision":"allow"},
        headers={"Origin":ORIGIN},follow_redirects=False)
    assert result.status_code==303,result.text
    callback=parse_qs(urlsplit(result.headers['Location']).query)
    assert callback['state']==[PARAMS['state']]
    return callback['code'][0]


def exchange(client,code,form=False):
    payload={"grant_type":"authorization_code","code":code,"redirect_uri":SCHOOL_CALLBACK}
    if form:
        basic=base64.b64encode(('test-school-agent:'+SECRET).encode()).decode()
        return client.post('/oauth/token',data=payload,headers={"Authorization":"Basic "+basic})
    return client.post('/oauth/token',json={**payload,"client_id":"test-school-agent","client_secret":SECRET})


@pytest.mark.parametrize('form',[False,True])
def test_exact_five_fields_read_owner_and_time(compatible,form):
    client,_,_=compatible
    a=login(client)
    save(client,a,'schedule','timetable.demo.json')
    _,task=save(client,a)
    code=authorize(client)
    token=exchange(client,code,form)
    assert token.status_code==200,token.text
    assert token.json()['scope']=='demo:read' and 0<token.json()['expires_in']<=600
    bearer={"Authorization":"Bearer "+token.json()['access_token']}
    assert exchange(client,code).status_code==400
    records=client.get('/oauth/records',headers=bearer)
    assert records.status_code==200,records.text
    assert records.json()['data']['tasks'][0]['task_id']==task['task_id']
    assert records.json()['data']['schedule']['workspace_ref']==a['workspace_ref']
    query=load_fixture('oauth-pilot.demo.json')['owned_time_check']
    import json
    result=client.post('/oauth/time/check',json={'query_json':json.dumps(query)},headers=bearer)
    assert result.status_code==200,result.text
    assert result.json()['data']['coverage']!='complete'
    assert client.post('/oauth/task-drafts',json={'fixture_id':'notice-event.demo.json','idempotency_key':'compat-no-write-001'},headers=bearer).status_code==403
    b=login(client,'fictional-b')
    # Signing in as B cannot redirect an already issued A bearer to B records.
    assert client.get('/oauth/records',headers=bearer).json()['data']['schedule']['workspace_ref']==a['workspace_ref']
    bcode=authorize(client); btoken=exchange(client,bcode).json()['access_token']
    assert client.get('/oauth/records',headers={'Authorization':'Bearer '+btoken}).json()['data']['tasks']==[]
    client.post('/oauth/revoke',json={'token':token.json()['access_token'],'client_id':'test-school-agent','client_secret':SECRET})
    assert client.get('/oauth/records',headers=bearer).status_code==401
    client.post('/api/v1/auth/cloudbase/logout',headers=headers(b))
    assert client.get('/oauth/records',headers={'Authorization':'Bearer '+btoken}).status_code==401


@pytest.mark.parametrize('changes',[
    {'scope':'demo:read demo:draft'},{'state':'short'}, {'redirect_uri':'https://attacker.invalid'},
    {'client_id':'unknown-client'}, {'code_challenge':'fake'}, {'workspace_ref':'other'},
    {'code_challenge_method':'S256'},{'response_type':'token'}])
def test_competition_invalid_requests(compatible,changes):
    client,_,_=compatible
    login(client)
    assert client.get('/oauth/authorize',params={**PARAMS,**changes},follow_redirects=False).status_code==400


def test_resume_login_exact_request_and_expiry(compatible):
    client,store,_=compatible
    response=client.get('/oauth/authorize',params=PARAMS,follow_redirects=False)
    assert response.status_code==303
    target=parse_qs(urlsplit(response.headers['location']).query)['return_to'][0]
    assert parse_qs(urlsplit(target).query)=={k:[v] for k,v in PARAMS.items()}
    login(client)
    code=authorize(client)
    bad=client.post('/oauth/token',json={'client_id':'test-school-agent','client_secret':'not-the-secret',
        'grant_type':'authorization_code','code':code,'redirect_uri':SCHOOL_CALLBACK})
    assert bad.status_code==401
    from app.core.security import secret_hash
    store.call('__test_expire_browser_session__',{'token_hash':secret_hash(client.cookies.get('campus_session'))})
    assert exchange(client,code).status_code==400


def test_consent_cannot_cross_owner_or_origin(compatible):
    client,_,_=compatible
    login(client)
    response=client.get('/oauth/authorize',params=PARAMS)
    txn=re.search(r'name="transaction" value="([^"]+)"',response.text)[1]
    assert client.post('/oauth/approve',data={'transaction':txn,'decision':'allow'},headers={'Origin':'https://attacker.invalid'}).status_code==403
    login(client,'fictional-b')
    assert client.post('/oauth/approve',data={'transaction':txn,'decision':'allow'},headers={'Origin':ORIGIN}).status_code==403


def test_default_strict_mode_still_rejects_five_fields(environment):
    settings,_,_,client=environment
    assert not settings.cloud_oauth_competition_compat_enabled
    login(client)
    assert client.get('/oauth/authorize',params=PARAMS,follow_redirects=False).status_code==400


def test_consent_form_policy_retains_origin_without_relaxing_check(compatible):
    client,_,_=compatible
    login(client)
    page=client.get('/oauth/authorize',params=PARAMS)
    assert page.status_code==200
    assert page.headers['Referrer-Policy']=='same-origin'
    assert "form-action 'self'" in page.headers['Content-Security-Policy']
    assert "form-action 'self' "+SCHOOL_CALLBACK+";" in page.headers['Content-Security-Policy']
    assert 'attacker.invalid' not in page.headers['Content-Security-Policy']
    txn=re.search(r'name="transaction" value="([^"]+)"',page.text)[1]
    # Null/missing/foreign origins are not accepted as a browser workaround.
    for origin in ('null','', 'https://attacker.invalid'):
        rejected=client.post('/oauth/approve',data={'transaction':txn,'decision':'allow'},
            headers={'Origin':origin} if origin else {},follow_redirects=False)
        assert rejected.status_code==403
        assert rejected.json()=={'error':'access_denied'}
        assert rejected.headers['Referrer-Policy']=='no-referrer'
    allowed=client.post('/oauth/approve',data={'transaction':txn,'decision':'allow'},
        headers={'Origin':ORIGIN},follow_redirects=False)
    assert allowed.status_code==303
    assert allowed.headers['Referrer-Policy']=='no-referrer'
    assert "form-action 'self';" in allowed.headers['Content-Security-Policy']
    callback=parse_qs(urlsplit(allowed.headers['Location']).query)
    assert callback['state']==[PARAMS['state']]
    token=exchange(client,callback['code'][0])
    assert token.status_code==200
    assert token.headers['Referrer-Policy']=='no-referrer'
    assert SCHOOL_CALLBACK not in token.headers['Content-Security-Policy']
