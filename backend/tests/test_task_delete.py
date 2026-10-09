"""Single-task deletion against real embedded PG; no production data touched."""
from fastapi.testclient import TestClient
import pytest
from app.cloud_identity_site import create_cloud_identity_site
from test_cloud_identity_site import login, save, headers, ORIGIN
from test_task_calendar import calendar_env, new_task, listing, update, body
from test_personal_task_isolation import personal, draft as entry_draft, commit as entry_commit, grant
from test_cloud_identity_site import environment


def remove(client, owner, task, key="delete-test-key", **changes):
    return client.post(f"/api/v1/tasks/{task['task_id']}/calendar/delete", headers=headers(owner,key),
        json={"workspace_ref":owner['workspace_ref'],"expected_revision":task['calendar_revision'],"confirmed":True,**changes})


@pytest.mark.parametrize("source", ["fixture", "notice"])
@pytest.mark.parametrize("status", ["pending", "completed", "cancelled"])
def test_delete_all_statuses_retry_and_restart(calendar_env, source, status):
    runtime, root, db, client, owner=calendar_env
    task_id=save(client,owner)[1]['task_id'] if source=='fixture' else new_task(client,owner)
    task=next(t for t in listing(client,owner)['items'] if t['task_id']==task_id)
    response=update(client,owner,task_id,body(owner,task,status=status))
    assert response.status_code==200
    task=response.json()['data']
    assert remove(client,owner,task,confirmed=False).status_code==422
    assert remove(client,owner,task,expected_revision=0).status_code==409
    assert remove(client,owner,task).json()['data']=={'task_id':task_id,'deleted':True}
    assert remove(client,owner,task).status_code==200  # Lost response retry, not a second mutation.
    assert listing(client,owner)['items']==[]
    assert client.get('/api/v1/tasks/calendar/summary',params={'workspace_ref':owner['workspace_ref']}).json()['data']['total_count']==0
    assert update(client,owner,task_id,body(owner,task,status='pending'),'restore-deleted-key').status_code==404
    assert remove(client,owner,task,'another-delete-key').status_code==404
    with TestClient(create_cloud_identity_site(root,db,runtime),base_url=ORIGIN) as restarted:
        restarted.cookies.set('campus_session',client.cookies.get('campus_session'))
        assert listing(restarted,owner)['items']==[]


def test_delete_owner_csrf_and_origin_isolation(calendar_env):
    _, _, _, client, owner=calendar_env
    new_task(client,owner)
    task=listing(client,owner)['items'][0]
    assert client.post(f"/api/v1/tasks/{task['task_id']}/calendar/delete",json={
        'workspace_ref':owner['workspace_ref'],'expected_revision':0,'confirmed':True},headers={
        **headers(owner),'X-CSRF-Token':'wrong'}).status_code==403
    assert client.post(f"/api/v1/tasks/{task['task_id']}/calendar/delete",json={
        'workspace_ref':owner['workspace_ref'],'expected_revision':0,'confirmed':True},headers={
        **headers(owner),'Origin':'https://other.invalid'}).status_code==403
    other=login(client,'fictional-b')
    assert remove(client,other,task).status_code==404
    assert remove(client,other,task,workspace_ref=owner['workspace_ref']).status_code==404
    login(client)
    assert len(listing(client,owner)['items'])==1


def test_deleted_personal_task_absent_from_agent(personal):
    client, db, runtime, root=personal
    owner=login(client)
    auth=grant(client)
    d=entry_draft(client,owner,title='虚构删除测试',key='delete-entry-draft').json()['data']
    saved=entry_commit(client,owner,d,'delete-entry-commit').json()['data']['item']
    assert remove(client,owner,saved).status_code==200
    assert listing(client,owner)['items']==[]
    from app.core.personal_tasks import PersonalTaskService
    from app.core.security import secret_hash
    assert PersonalTaskService(runtime,db).records({'principal_kind':'browser',
        'session_hash':secret_hash(client.cookies.get('campus_session')),'csrf_hash':secret_hash(owner['csrf_token'])})==[]
    assert client.get('/oauth/tasks/entries',headers=auth).json()['data']['items']==[]
    # Replaying the old commit cannot resurrect a deleted saved row.
    assert entry_commit(client,owner,d,'delete-entry-commit').status_code==503
    assert listing(client,owner)['items']==[]
