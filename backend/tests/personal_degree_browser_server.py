"""Loopback QA proxy: actual local PG/HTTP/OAuth, only a fixed fictional owner.

The fixture bridge is a test-only button, not evidence of a real extension read.
No production credentials, personal data, migrations or deployment are accessed.
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
import uvicorn
from app.cloud_identity_site import create_cloud_identity_site
from app.cloud_tasks_site import ENV_ID
from app.core.config import Settings
from app.core.security import secret_hash
from app.core.cloud_oauth_provider import SCHOOL_CALLBACK
from pydantic import SecretStr
from test_cloud_identity_site import SECRET, ORIGIN, login
from test_personal_degree import DegreePostgresStore, observation
from test_competition_oauth import authorize, exchange

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / '.review-cache/degree-own-flow-main0051687-20261010-r2/frontend/dist-identity'
LOCAL = 'http://127.0.0.1:8026'
client = None
bearer = None

@asynccontextmanager
async def lifespan(app):
    global client, bearer
    store = DegreePostgresStore()
    settings = Settings(_env_file=None, app_env='test', app_origin=ORIGIN, cloud_identity_pilot_enabled=True,
        cloudbase_auth_pilot_enabled=True, cloudbase_auth_profile='pg_registered', cloudbase_auth_env_id=ENV_ID,
        cloudbase_auth_pilot_user_ids=['fictional-a', 'fictional-b'], cloud_oauth_pilot_enabled=True,
        cloud_oauth_competition_compat_enabled=True, cloud_personal_degree_enabled=True,
        cloud_personal_schedules_enabled=True, cloud_notice_text_pilot_enabled=True,
        oauth_client_id='test-school-agent', agent_pairing_audience='test-school-agent', oauth_redirect_uri=SCHOOL_CALLBACK,
        oauth_client_secret_hash=SecretStr(secret_hash(SECRET)), build_id='degree-local-own-flow-qa')
    import app.cloud_identity_site as identity
    original = identity.verify_cloudbase_user
    async def verify(runtime, authorization):
        if authorization != 'Bearer fictional-a': raise ValueError('fixed fixture only')
        return 'cloudbase_pilot_' + secret_hash(runtime.cloudbase_auth_env_id + ':fictional-a')
    identity.verify_cloudbase_user = verify
    try:
        with TestClient(create_cloud_identity_site(FRONTEND, store, settings), base_url=ORIGIN) as qa_client:
            client = qa_client
            login(client)
            token = exchange(client, authorize(client)).json()['access_token']
            bearer = {'Authorization': 'Bearer ' + token}
            yield
    finally:
        identity.verify_cloudbase_user = original
        client = None; bearer = None; store.shutdown()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware('http')
async def local_only(request: Request, call_next):
    if request.headers.get('host') != '127.0.0.1:8026' or request.headers.get('origin') not in (None, LOCAL):
        return JSONResponse({'error': 'local QA only'}, status_code=403)
    result = await call_next(request)
    result.headers['Cache-Control'] = 'no-store'
    return result

@app.get('/qa/observation')
def fixture(): return observation()

@app.get('/qa/agent-read')
def agent_read():
    result = client.get('/oauth/degree/records', headers=bearer)
    data = result.json().get('data') or {}
    snapshot = data.get('degree')
    return {'status': result.status_code, 'degree': None if snapshot is None else {
        'revision': snapshot['revision'], 'modules': len(snapshot['report']['modules']),
        'passed': snapshot['report']['module_summaries'][0]['observed_passed_credits'],
        'in_progress': snapshot['report']['module_summaries'][0]['observed_in_progress_credits'],
        'can_decide_complete': snapshot['report']['can_decide_complete']}}

@app.api_route('/api/{path:path}', methods=['GET', 'POST'])
async def proxy(path: str, request: Request):
    outgoing = {key: request.headers[key] for key in ('x-csrf-token', 'idempotency-key', 'x-campus-session-read') if key in request.headers}
    outgoing['Origin'] = ORIGIN
    if request.headers.get('content-type'): outgoing['Content-Type'] = request.headers['content-type']
    result = client.request(request.method, '/api/' + path, params=request.query_params,
        content=await request.body(), headers=outgoing, follow_redirects=False)
    return Response(result.content, status_code=result.status_code, media_type='application/json')

app.mount('/assets', StaticFiles(directory=FRONTEND / 'assets'), name='assets')
@app.get('/tools/degree')
def degree():
    html = (FRONTEND / 'index.html').read_text(encoding='utf-8')
    controls = '''<aside style="background:#fff4c4;padding:12px">本机虚构数据验收（不会读取真实成绩）
<button id="qa-load" type="button">载入虚构培养计划表格</button>
<button id="qa-read" type="button">检查 Agent 已保存版本</button><output id="qa-result"></output></aside>
<script>
document.getElementById('qa-load').onclick=async()=>{const value=await(await fetch('/qa/observation')).json();window.dispatchEvent(new CustomEvent('campus:degree-observation',{detail:value}));};
document.getElementById('qa-read').onclick=async()=>{const value=await(await fetch('/qa/agent-read')).json();document.getElementById('qa-result').textContent=JSON.stringify(value);};
</script>'''
    return HTMLResponse(html.replace('<body>', '<body>' + controls))

if __name__ == '__main__': uvicorn.run(app, host='127.0.0.1', port=8026, access_log=False)
