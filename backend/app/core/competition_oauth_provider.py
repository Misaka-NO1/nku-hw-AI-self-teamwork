"""Explicit five-field confidential-client OAuth for a fictional competition demo.

This is NOT PKCE-equivalent or a production personal-data authorization scheme.
It uses separate PG authorization state; the strict provider is unchanged.
"""
import re
import secrets
import time
from urllib.parse import urlencode

from app.core.cloud_oauth_provider import CloudOAuthProvider, SCHOOL_CALLBACK
from app.core.errors import AppError
from app.core.oauth_local import OAuthError, resource_token
from app.core.security import secret_hash


class CompetitionOAuthProvider(CloudOAuthProvider):
    def gate(self):
        super().gate()
        if not self.settings.cloud_oauth_competition_compat_enabled:
            raise OAuthError("temporarily_unavailable",503)

    def begin(self,request,params):
        self.gate()
        required={"response_type","client_id","redirect_uri","scope","state"}
        if (set(params)!=required or params["client_id"]!=self.settings.oauth_client_id
            or params["redirect_uri"]!=SCHOOL_CALLBACK):
            raise OAuthError()
        if params["response_type"]!="code": raise OAuthError("unsupported_response_type")
        if params["scope"]!="demo:read": raise OAuthError("invalid_scope")
        if not re.fullmatch(r"[A-Za-z0-9._~-]{8,256}",params["state"]): raise OAuthError()
        raw=secrets.token_urlsafe(32)
        self.store.competition_call("authorize_start",{**self._browser(request),
            "transaction_hash":secret_hash(raw),"audience":self.settings.oauth_client_id,
            "redirect_uri":SCHOOL_CALLBACK,"state":params["state"]})
        return raw,frozenset({"demo:read"})

    def approve(self,request,transaction,decision):
        if decision not in {"allow","deny"}: raise OAuthError()
        raw=secrets.token_urlsafe(32)
        result=self.store.competition_call("authorize_approve",{**self._browser(request,True),
            "transaction_hash":secret_hash(transaction),"decision":decision,"code_hash":secret_hash(raw)})
        if result["redirect_uri"]!=SCHOOL_CALLBACK: raise OAuthError("access_denied",403)
        response={"code":raw,"state":result["state"]} if decision=="allow" else {"error":"access_denied","state":result["state"]}
        return SCHOOL_CALLBACK+"?"+urlencode(response)

    def exchange(self,params):
        self.gate()
        if set(params)!={"grant_type","code","redirect_uri"}: raise OAuthError()
        if params["grant_type"]!="authorization_code": raise OAuthError("unsupported_grant_type")
        if params["redirect_uri"]!=SCHOOL_CALLBACK: raise OAuthError("invalid_grant")
        raw=secrets.token_urlsafe(32)
        try:
            result=self.store.competition_call("exchange",{"code_hash":secret_hash(params["code"]),
                "audience":self.settings.oauth_client_id,"redirect_uri":SCHOOL_CALLBACK,"token_hash":secret_hash(raw)})
        except AppError as exc:
            raise OAuthError("temporarily_unavailable",503) if exc.status_code>=500 else OAuthError("invalid_grant") from None
        expiry=result["expires_epoch"]-int(time.time())
        if not 0<expiry<=600 or result["scopes"]!=["demo:read"]: raise OAuthError("invalid_grant")
        return {"access_token":raw,"token_type":"Bearer","expires_in":expiry,"scope":"demo:read"}

    def revoke(self,token):
        self.gate()
        self.store.competition_call("revoke",{"token_hash":secret_hash(token),"audience":self.settings.oauth_client_id})

    def records(self,request):
        self.gate()
        from app.cloud_identity_site import format_times
        if self.settings.cloud_notice_text_pilot_enabled:
            return format_times(self.store.notice_call("records",self._notice_args(request)))
        return format_times(self.store.competition_call("records",{
            "grant_hash":secret_hash(resource_token(request).get_secret_value()),"audience":self.settings.oauth_client_id}))

    def draft(self,request,notice,key):
        self.gate()
        raise AppError(403,"FORBIDDEN","Competition OAuth permits fictional read-only queries")
