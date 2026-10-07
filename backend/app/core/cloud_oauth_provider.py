"""Cloud OAuth provider using shared durable PostgreSQL transactions.

The HTTP parser/consent UI is shared with the local pilot. No global/session
memory or filesystem grants, no SYS_USERID binding, no shared token as owner.
"""
import base64
import hashlib
import re
import secrets
import time
from urllib.parse import urlencode

from app.core.oauth_local import OAuthError,resource_token
from app.core.security import SESSION_COOKIE,payload_hash,require_idempotency_key,secret_hash
from app.core.demo import enforce_demo_fixture
from app.core.errors import AppError

SCHOOL_CALLBACK="https://coze.nankai.edu.cn/product/llm/info/oauth"


class CloudOAuthProvider:
    def __init__(self,settings,store):
        self.settings,self.store=settings,store

    def gate(self):
        from app.cloud_identity_site import require_cloud_identity
        settings=self.settings
        try: require_cloud_identity(settings)
        except (ValueError,AppError): raise OAuthError("temporarily_unavailable",503) from None
        if (not settings.cloud_oauth_pilot_enabled or settings.oauth_client_id!=settings.agent_pairing_audience
          or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}",settings.oauth_client_id)
          or not re.fullmatch(r"[0-9a-f]{64}",settings.oauth_client_secret_hash.get_secret_value())
          or settings.oauth_redirect_uri!=SCHOOL_CALLBACK):
            raise OAuthError("temporarily_unavailable",503)

    def initialize(self): self.gate()

    def authenticate(self,client_id,client_secret):
        self.gate()
        if (client_id!=self.settings.oauth_client_id or not 40<=len(client_secret)<=256 or
          not secrets.compare_digest(secret_hash(client_secret),self.settings.oauth_client_secret_hash.get_secret_value())):
            raise OAuthError("invalid_client",401)

    def _browser(self,request,write=False):
        self.gate()
        token=request.cookies.get(SESSION_COOKIE,"")
        if not token: raise AppError(401,"AUTH_REQUIRED","Verified pilot login required")
        if write and request.headers.get("Origin","")!=self.settings.app_origin:
            raise OAuthError("access_denied",403)
        return {"session_hash":secret_hash(token)}

    def login_url(self,params):
        # begin() validates the exact client/callback/PKCE fields before raising
        # AUTH_REQUIRED. Resume only this same-origin authorize path; never
        # redirect to a user-provided destination or carry a credential.
        return "/tools/login?"+urlencode({"return_to":"/oauth/authorize?"+urlencode(params)})

    def begin(self,request,params):
        self.gate()
        required={"response_type","client_id","redirect_uri","scope","state","code_challenge","code_challenge_method"}
        if (set(params)!=required or params["client_id"]!=self.settings.oauth_client_id or params["redirect_uri"]!=SCHOOL_CALLBACK): raise OAuthError()
        if params["response_type"]!="code": raise OAuthError("unsupported_response_type")
        if params["scope"] not in {"demo:read","demo:read demo:draft","demo:draft demo:read"}: raise OAuthError("invalid_scope")
        if (params["code_challenge_method"]!="S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43}",params["code_challenge"])
          or not re.fullmatch(r"[A-Za-z0-9._~-]{16,256}",params["state"])): raise OAuthError()
        raw=secrets.token_urlsafe(32); scopes=frozenset(params["scope"].split(" "))
        self.store.call("authorize_start",{**self._browser(request),"transaction_hash":secret_hash(raw),
            "audience":self.settings.oauth_client_id,"redirect_uri":SCHOOL_CALLBACK,"scopes":sorted(scopes),
            "challenge":params["code_challenge"],"state":params["state"]})
        return raw,scopes

    def approve(self,request,transaction,decision):
        if decision not in {"allow","deny"}: raise OAuthError()
        raw=secrets.token_urlsafe(32)
        result=self.store.call("authorize_approve",{**self._browser(request,True),"transaction_hash":secret_hash(transaction),
            "decision":decision,"code_hash":secret_hash(raw)})
        if result["redirect_uri"]!=SCHOOL_CALLBACK: raise OAuthError("access_denied",403)
        response={"code":raw,"state":result["state"]} if decision=="allow" else {"error":"access_denied","state":result["state"]}
        return SCHOOL_CALLBACK+"?"+urlencode(response)

    def exchange(self,params):
        self.gate()
        if set(params)!={"grant_type","code","redirect_uri","code_verifier"}: raise OAuthError()
        if params["grant_type"]!="authorization_code": raise OAuthError("unsupported_grant_type")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}",params["code_verifier"]): raise OAuthError("invalid_grant")
        challenge=base64.urlsafe_b64encode(hashlib.sha256(params["code_verifier"].encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        raw=secrets.token_urlsafe(32)
        try:
            result=self.store.call("oauth_exchange",{"code_hash":secret_hash(params["code"]),"audience":self.settings.oauth_client_id,
                "redirect_uri":params["redirect_uri"],"challenge":challenge,"token_hash":secret_hash(raw)})
        except AppError as exc:
            raise OAuthError("temporarily_unavailable",503) if exc.status_code>=500 else OAuthError("invalid_grant") from None
        expiry=result["expires_epoch"]-int(time.time())
        if not 0<expiry<=600: raise OAuthError("invalid_grant")
        return {"access_token":raw,"token_type":"Bearer","expires_in":expiry,"scope":" ".join(result["scopes"])}

    def revoke(self,token):
        self.gate()
        self.store.call("oauth_revoke",{"token_hash":secret_hash(token),"audience":self.settings.oauth_client_id})

    def _agent(self,request):
        self.gate()
        return {"principal_kind":"agent","grant_hash":secret_hash(resource_token(request).get_secret_value()),
                "audience":self.settings.oauth_client_id}

    def records(self,request):
        from app.cloud_identity_site import format_times
        if self.settings.cloud_notice_text_pilot_enabled:
            return format_times(self.store.notice_call("records",self._notice_args(request)))
        return format_times(self.store.call("records",self._agent(request)))

    def _notice_args(self,request):
        self.gate()
        return {"principal_kind":"agent","grant_mode":"competition" if self.settings.cloud_oauth_competition_compat_enabled else "strict",
                "grant_hash":secret_hash(resource_token(request).get_secret_value()),"audience":self.settings.oauth_client_id}

    def notice_query(self,request,arguments,operation):
        from app.core.cloud_notice_text import CloudNoticeService
        from app.core.contracts import validate_boundary
        from app.core.platform_query import decode_platform_query
        service=CloudNoticeService(self.settings,self.store)
        # OAuth can read/compute. It has no draft, confirmation or save route.
        args=self._notice_args(request)
        service.records(args)
        validate_boundary(arguments,"NoticeTextPlatformRequest")
        payload=decode_platform_query(arguments)
        return service.read(args,payload) if operation=="read" else service.check(args,payload)

    def calendar_summary(self,request):
        from app.core.task_calendar import TaskCalendarService
        return TaskCalendarService(self.settings,self.store).summary(self._notice_args(request))

    def personal_query(self,request,arguments,operation):
        from app.core.personal_tasks import PersonalTaskService
        from app.core.platform_query import decode_platform_query
        service=PersonalTaskService(self.settings,self.store)
        args=self._notice_args(request)
        access=self.store.personal_call("access",args)
        if not access["can_read"] or (operation!="records" and not access["can_write"]):
            raise AppError(403,"FORBIDDEN","需要重新授权本人待办读写；旧只读授权不能保存")
        if operation=="records":
            from app.core.task_calendar import calendar_task
            return {"items":[calendar_task(t) for t in service.records(args)],"background_push":False,
                    "calendar_url":self.settings.app_origin+"/tools/calendar"}
        payload=decode_platform_query(arguments)
        return service.draft(args,payload) if operation=="draft" else service.commit(args,payload)

    def time_query(self,request,arguments,operation):
        from app.core.owned_time import calculate_owned_time,decode_owned_time
        # Authenticate and require demo:read before processing query content.
        # Browser cookies cannot switch the owner of this bearer grant.
        records=self.records(request)
        payload=decode_owned_time(arguments,operation)
        return calculate_owned_time(records,payload,operation,allow_notice_text=self.settings.cloud_notice_text_pilot_enabled)

    def draft(self,request,notice,key):
        require_idempotency_key(key)
        digest=enforce_demo_fixture(notice,"task")
        result=self.store.call("create_draft",{**self._agent(request),"kind":"task","payload_hash":digest,"key":key,
            "request_hash":payload_hash({"kind":"task","payload":notice}),"draft_id":"draft_"+secrets.token_urlsafe(18)})
        from app.cloud_identity_site import format_times
        return format_times({**result,"review_url":self.settings.app_origin+"/tools/tasks?draft_id="+result["draft_id"]})
