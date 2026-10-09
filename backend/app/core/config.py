from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    auth_mode: Literal["demo_fixture", "trusted_binding"] = "demo_fixture"
    allow_personal_uploads: bool = False
    notice_text_pilot_enabled: bool = False
    cloud_notice_text_pilot_enabled: bool = False
    cloud_task_calendar_enabled: bool = False
    # Two existing verified pilot accounts; NOT a switch for academic uploads.
    cloud_personal_tasks_enabled: bool = False
    # Explicit own timetable imports; does not enable general academic uploads.
    cloud_personal_schedules_enabled: bool = False
    notice_ocr_backend: Literal["disabled", "windows", "tesseract"] = "disabled"
    notice_ocr_command: str = ""
    app_origin: str = ""
    genios_agent_url: str = ""
    mcp_public_url: str = ""
    mcp_service_token: SecretStr = Field(default=SecretStr(""), repr=False)
    mcp_require_auth: bool = False
    mcp_enable_domain_tools: bool = False
    mcp_enable_platform_compat_tools: bool = False
    domain_bundle_manifest_path: str = ""
    # Server-selected, never an Agent argument. Personal-data gates stay separate.
    public_catalog_profile: Literal["demo", "published"] = "demo"
    # Closed pilot: real identity, but only exact fictional fixtures. Not a
    # shortcut for enabling personal uploads or granting NK-GeniOS identity.
    cloudbase_auth_pilot_enabled: bool = False
    cloudbase_auth_env_id: str = ""
    cloudbase_auth_profile: Literal["legacy", "pg_registered"] = "legacy"
    cloudbase_auth_pilot_user_ids: list[str] = Field(default_factory=list, repr=False)
    cloudbase_auth_session_seconds: int = Field(default=900, ge=60, le=900)
    cloud_persistent_auth_enabled: bool = False
    # Independent device binding, NOT platform SSO. Explicit opt-in after migration.
    cloud_device_login_enabled: bool = False
    # Fresh devices:bind consent; old grants are never silently upgraded.
    cloud_agent_device_binding_enabled: bool = False
    # Internal local prototype only: no REST route or MCP tool is registered.
    agent_pairing_local_enabled: bool = False
    agent_pairing_audience: str = ""
    # OAuth adapter is loopback/test-only until platform protocol and cloud
    # persistence are accepted. Registered client secret is a SHA-256 digest.
    oauth_local_enabled: bool = False
    oauth_client_id: str = ""
    oauth_client_secret_hash: SecretStr = Field(default=SecretStr(""), repr=False)
    oauth_redirect_uri: str = ""
    cloud_identity_pilot_enabled: bool = False
    cloud_identity_bootstrap_enabled: bool = False
    cloud_oauth_pilot_enabled: bool = False
    # Explicit competition-only confidential OAuth compatibility. No PKCE;
    # two approved fictional owners, read-only, short-lived, default off.
    cloud_oauth_competition_compat_enabled: bool = False
    database_url: str = "sqlite:///data/campus.db"
    import_ticket_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    confirmation_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    demo_workspace_ttl_hours: int = Field(default=24, ge=1, le=168)
    nku_allowed_edu_origins: list[str] = Field(default_factory=list)
    nku_allowed_edu_paths: list[str] = Field(default_factory=list)
    build_id: str = "dev"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8001, ge=1, le=65535)
    mcp_path: str = "/mcp"

    @field_validator("mcp_path")
    @classmethod
    def validate_mcp_path(cls, value: str) -> str:
        if not value.startswith("/") or value == "/":
            raise ValueError("MCP_PATH must start with '/' and cannot be the root path")
        return value.rstrip("/")

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw_path = self.database_url.removeprefix(prefix)
        if raw_path == ":memory:":
            return None
        return Path(raw_path)

    def validate_deployment(self) -> None:
        if self.notice_text_pilot_enabled and (
            self.app_env not in {"development", "test"}
            or self.api_host not in {"127.0.0.1", "localhost", "::1"}
            or self.auth_mode != "demo_fixture"
        ):
            raise ValueError("NOTICE_TEXT_PILOT_ENABLED is restricted to local fictional testing")
        if self.mcp_enable_platform_compat_tools and not self.mcp_enable_domain_tools:
            raise ValueError("MCP_ENABLE_PLATFORM_COMPAT_TOOLS requires MCP_ENABLE_DOMAIN_TOOLS")
        exposed_listener = self.mcp_host not in {"127.0.0.1", "localhost", "::1"}
        if self.app_env not in {"staging", "production"} and not exposed_listener:
            return
        url = urlsplit(self.mcp_public_url)
        if url.scheme != "https" or not url.hostname:
            raise ValueError("MCP_PUBLIC_URL must be an HTTPS URL outside local development")
        if url.username is not None or url.password is not None or url.query or url.fragment:
            raise ValueError("MCP_PUBLIC_URL must not contain credentials, query or fragment")
        if url.path != self.mcp_path:
            raise ValueError("MCP_PUBLIC_URL path must match MCP_PATH exactly")
        _ = url.port  # Also validates port syntax/range.
        if not self.mcp_require_auth:
            raise ValueError("MCP_REQUIRE_AUTH must be true outside local development")
        if not self.mcp_service_token.get_secret_value():
            raise ValueError("MCP_SERVICE_TOKEN is required when MCP authentication is enabled")
        if self.mcp_enable_domain_tools and not self.domain_bundle_manifest_path:
            raise ValueError("DOMAIN_BUNDLE_MANIFEST_PATH is required for non-local domain deployment")


@lru_cache
def get_settings() -> Settings:
    return Settings()
