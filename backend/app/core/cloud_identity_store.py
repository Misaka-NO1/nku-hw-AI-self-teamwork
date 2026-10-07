"""Pinned CloudBase RPC transport. No dynamic SQL, credentials in browser, or redirects."""
import httpx

from app.cloud_tasks_site import ENV_ID
from app.core.errors import AppError

RPC_URL = f"https://{ENV_ID}.api.tcloudbasegateway.com/v1/rdb/rest/rpc/nku_identity_pilot_v1_rpc"
OPERATIONS = frozenset({"probe", "persistent_probe", "rate_limit", "configure_subjects", "login", "logout", "get_workspace", "records",
    "create_draft", "get_draft", "confirm", "commit", "list_tasks", "get_task", "current_schedule",
    "import_ticket", "authorize_start", "authorize_approve", "oauth_exchange", "oauth_revoke"})
COMPETITION_OPERATIONS = frozenset({"probe", "authorize_start", "authorize_approve", "exchange", "records", "revoke"})
COMPETITION_RPC_URL = RPC_URL.removesuffix("nku_identity_pilot_v1_rpc") + "nku_competition_oauth_v1_rpc"
NOTICE_RPC_URL = RPC_URL.removesuffix("nku_identity_pilot_v1_rpc") + "nku_notice_text_v1_rpc"
NOTICE_OPERATIONS = frozenset({"probe", "records", "get_draft", "get_confirmation", "get_task", "list_tasks",
                              "lookup", "create", "update", "confirm", "commit"})
CALENDAR_RPC_URL = RPC_URL.removesuffix("nku_identity_pilot_v1_rpc") + "nku_task_calendar_v1_rpc"
CALENDAR_OPERATIONS = frozenset({"probe", "records", "lookup", "update"})
PERSONAL_RPC_URL = RPC_URL.removesuffix("nku_identity_pilot_v1_rpc") + "nku_personal_tasks_v1_rpc"
PERSONAL_OPERATIONS = frozenset({"probe", "access", "records", "draft", "commit", "update"})
STATUSES = {"AUTH_REQUIRED":401, "FORBIDDEN":403, "NOT_FOUND":404, "TOKEN_EXPIRED":410,
    "VALIDATION_ERROR":422, "DEMO_ONLY":403, "RATE_LIMITED":429,
    "STALE_REVISION":409, "CONFIRMATION_REQUIRED":409}


def storage_result(body):
    if not isinstance(body, dict) or type(body.get("ok")) is not bool:
        raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
    if not body["ok"]:
        code=body.get("code")
        if code not in STATUSES or body.get("status") != STATUSES[code]:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
        raise AppError(STATUSES[code],code,"Identity storage rejected this operation",code=="RATE_LIMITED")
    if "data" not in body:
        raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
    return body["data"]


class CloudIdentityStore:
    def __init__(self,api_key: str,transport=None):
        if not api_key:
            raise ValueError("Configure the approved database key in server-only configuration")
        self._headers={"Authorization":"Bearer "+api_key}
        self.client=httpx.Client(transport=transport,timeout=15,follow_redirects=False,trust_env=False)

    def call(self,op,args):
        if op not in OPERATIONS:
            raise AppError(403,"FORBIDDEN","Unsupported storage operation")
        return self._request(RPC_URL,op,args)

    def competition_call(self,op,args):
        if op not in COMPETITION_OPERATIONS:
            raise AppError(403,"FORBIDDEN","Unsupported competition operation")
        return self._request(COMPETITION_RPC_URL,op,args)

    def notice_call(self,op,args):
        if op not in NOTICE_OPERATIONS:
            raise AppError(403,"FORBIDDEN","Unsupported notice operation")
        return self._request(NOTICE_RPC_URL,op,args,max_response=2097152)

    def calendar_call(self,op,args):
        if op not in CALENDAR_OPERATIONS:
            raise AppError(403,"FORBIDDEN","Unsupported calendar operation")
        return self._request(CALENDAR_RPC_URL,op,args,max_response=33554432)

    def personal_call(self,op,args):
        if op not in PERSONAL_OPERATIONS:
            raise AppError(403,"FORBIDDEN","Unsupported personal task operation")
        return self._request(PERSONAL_RPC_URL,op,args,max_response=2097152)

    def _request(self,url,op,args,max_response=262144):
        try:
            response=self.client.post(url,headers=self._headers,json={"op":op,"args":args})
            if response.status_code!=200 or len(response.content)>max_response:
                raise ValueError("Invalid storage response")
            body=response.json()
        except (httpx.HTTPError,ValueError):
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True) from None
        return storage_result(body)

    def close(self):
        self.client.close()
