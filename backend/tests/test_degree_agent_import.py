import json
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from app.core.degree_progress import agent_report
from app.core.errors import AppError
from test_degree_progress_private import report, body
from test_genios_identity_site import native, start_and_create, attest
from test_agent_device import grant
from test_cloud_identity_site import environment, ORIGIN, headers

@pytest.mark.parametrize('value',[
    {'report_json': '{}'}, {'report_json': json.dumps({'courses':[]})},
    {'report_json': json.dumps(json.dumps(report()))},
    {'report_json': json.dumps(report()), 'owner_id':'other'},
    {'report_json': '{"kind":"first","kind":"second"}'},
    {'report_json': '['*10000}, {'report_json':'x'*131073},
])
def test_agent_json_is_complete_strict_module_report(value):
    with pytest.raises(AppError) as error: agent_report(value)
    assert error.value.status_code==422

def test_agent_import_preview_confirm_owner_revision_and_logout(native):
    runtime,root,db,_,_,_=native
    runtime=runtime.model_copy(update={'cloud_degree_progress_enabled':True,'cloud_degree_agent_write_enabled':True})
    app=create_cloud_identity_site(root,db,runtime)
    with TestClient(app,base_url=ORIGIN) as tools,TestClient(app,base_url=ORIGIN) as a,TestClient(app,base_url=ORIGIN) as b:
        _,_,owner=start_and_create(tools,a)
        _,_,other=start_and_create(tools,b,'fictional-native-b')
        scope='demo:read tasks:read tasks:write devices:bind degree:read degree:write'
        checked={**grant(a,scope),'platform-user-id':'fictional-native-a','platform-attestation':attest(tools)}
        upload_report=report()
        upload_report['modules'][0].update(school_in_progress_credits='3',school_direct_in_progress_credits='3')
        upload={'report_json':json.dumps(upload_report)}
        path='/oauth/degree/import-drafts'
        assert tools.post(path,content='{"report_json":"first","report_json":"second"}',headers={**checked,'Content-Type':'application/json'}).status_code==422
        assert tools.post(path,content='broken',headers={**checked,'Content-Type':'application/json'}).status_code==422
        assert tools.post(path,json=upload,headers=grant(a,scope)).status_code==401
        read_only={**checked,**grant(a,scope.removesuffix(' degree:write'))}
        assert tools.post(path,json=upload,headers=read_only).status_code==403
        assert tools.post(path,json=upload,headers={**checked,**grant(b,scope)}).status_code==403
        bad=deepcopy(report());bad['modules'][0]['grade']='private'
        assert tools.post(path,json={'report_json':json.dumps(bad)},headers=checked).status_code==422
        assert tools.post(path+'?owner=other',json=upload,headers=checked).status_code==400
        preview=tools.post(path,json=upload,headers=checked)
        assert preview.status_code==200,preview.text
        draft=preview.json()['data']
        assert draft['saved'] is False and draft['confirmation_required'] is True
        assert draft['report']['modules'][0]['provisional_credit_gap']=='4'
        assert draft['report']['modules'][0]['reported_actual_excluding_marked_in_progress']=='7'
        assert tools.get('/oauth/degree/progress',headers=checked).json()['data']['report'] is None
        confirmation={k:draft[k] for k in ('draft_id','payload_hash')};confirmation['confirmed']=True
        commit='/oauth/degree/import-confirm'
        assert tools.post(commit,json={**confirmation,'confirmed':False},headers=checked).status_code==409
        assert tools.post(commit,json={**confirmation,'payload_hash':'f'*64},headers=checked).status_code==409
        assert tools.post(commit,json={**confirmation,'report':report()},headers=checked).status_code==422
        bchecked={**grant(b,scope),'platform-user-id':'fictional-native-b','platform-attestation':attest(tools,'fictional-native-b')}
        assert tools.post(commit,json=confirmation,headers=bchecked).status_code==404
        saved=tools.post(commit,json=confirmation,headers=checked)
        assert saved.status_code==200,saved.text
        receipt=saved.json()['data']
        assert receipt['saved'] and receipt['readback_verified'] and receipt['revision']==1
        assert receipt['report']==draft['report']
        assert tools.get('/oauth/degree/progress',headers=checked).json()['data']['report']['modules'][0]['school_direct_in_progress_credits']=='3'
        assert tools.post(commit,json=confirmation,headers=checked).json()['data']==receipt
        assert b.get('/api/v1/degree/progress').json()['data']['report'] is None
        second=tools.post(path,json=upload,headers=checked).json()['data']
        assert second['replaces_existing'] and second['expected_revision']==1
        assert a.post('/api/v1/degree/progress',json=body(owner,1),headers=headers(owner,'browser-race-save')).status_code==200
        assert tools.post(commit,json={**{k:second[k] for k in ('draft_id','payload_hash')},'confirmed':True},headers=checked).status_code==409
        third=tools.post(path,json=upload,headers=checked).json()['data']
        assert db.call('__test_expire_degree_draft__',{'draft_id':third['draft_id']})=={}
        assert tools.post(commit,json={**{k:third[k] for k in ('draft_id','payload_hash')},'confirmed':True},headers=checked).status_code==410
        assert a.post('/api/v1/auth/cloudbase/logout',headers=headers(owner)).status_code==200
        assert tools.post(commit,json=confirmation,headers=checked).status_code==401

def test_agent_write_disabled_by_default(native):
    runtime,root,db,_,_,_=native
    runtime=runtime.model_copy(update={'cloud_degree_progress_enabled':True})
    with TestClient(create_cloud_identity_site(root,db,runtime),base_url=ORIGIN) as client:
        assert client.post('/oauth/degree/import-drafts',json={'report_json':json.dumps(report())}).status_code==404
