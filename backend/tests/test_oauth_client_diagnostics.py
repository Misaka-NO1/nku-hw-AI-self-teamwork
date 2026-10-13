"""Offline, synthetic credentials. Classifications must never include input data."""
import logging
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.core.cloud_oauth_provider import CloudOAuthProvider
from app.core.oauth_local import OAuthError
from app.core.security import secret_hash


class IsolatedProvider(CloudOAuthProvider):
    def gate(self):
        pass  # This unit tests authentication only, not deployment gates.


@pytest.mark.parametrize("client,secret,reason",[
    ("DO_NOT_LOG_CLIENT","fictional-"+"x"*50,"client_id"),
    ("fictional-client","DO_NOT_LOG_SHORT","secret_length"),
    ("fictional-client","DO_NOT_LOG_SECRET"+"x"*50,"secret_mismatch"),
])
def test_client_rejection_is_generic_and_log_is_classification_only(caplog,client,secret,reason):
    good="fictional-"+"x"*50
    provider=IsolatedProvider(SimpleNamespace(oauth_client_id="fictional-client",
        oauth_client_secret_hash=SecretStr(secret_hash(good))),None)
    caplog.set_level(logging.INFO,logger="uvicorn.error")
    with pytest.raises(OAuthError) as result:
        provider.authenticate(client,secret)
    assert result.value.error=="invalid_client" and result.value.status==401
    logs=[r.getMessage() for r in caplog.records if r.name=="uvicorn.error"]
    assert logs==[f"campus_oauth_client rejection={reason}"]
    assert "DO_NOT_LOG" not in " ".join(logs)
    caplog.clear()
    provider.authenticate("fictional-client",good)
    assert not caplog.records
