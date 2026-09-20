from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    app_origin: str = ""
    genios_agent_url: str = ""
    mcp_public_url: str = ""
    mcp_service_token: SecretStr = Field(default=SecretStr(""), repr=False)
    mcp_require_auth: bool = False
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
        if self.app_env not in {"staging", "production"}:
            return
        if not self.mcp_public_url.startswith("https://"):
            raise ValueError("MCP_PUBLIC_URL must be an HTTPS URL outside local development")
        if not self.mcp_require_auth:
            raise ValueError("MCP_REQUIRE_AUTH must be true outside local development")
        if not self.mcp_service_token.get_secret_value():
            raise ValueError("MCP_SERVICE_TOKEN is required when MCP authentication is enabled")


@lru_cache
def get_settings() -> Settings:
    return Settings()
