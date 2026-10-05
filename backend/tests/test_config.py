import pytest

from app.core.config import Settings


def test_production_requires_https_and_mcp_auth() -> None:
    settings = Settings(app_env="production")

    with pytest.raises(ValueError, match="HTTPS"):
        settings.validate_deployment()


def test_valid_production_configuration_does_not_expose_secret() -> None:
    settings = Settings(
        app_env="production",
        mcp_public_url="https://campus.example.invalid/mcp",
        mcp_require_auth=True,
        mcp_service_token="private-token",
    )

    settings.validate_deployment()
    assert "private-token" not in repr(settings)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_non_loopback_mcp_listener_requires_secure_configuration_even_outside_staging(app_env):
    settings = Settings(app_env=app_env, mcp_host="0.0.0.0")

    with pytest.raises(ValueError, match="HTTPS"):
        settings.validate_deployment()


def test_non_loopback_mcp_listener_accepts_secure_configuration_in_development():
    settings = Settings(
        app_env="development",
        mcp_host="0.0.0.0",
        mcp_public_url="https://campus.example.invalid/mcp",
        mcp_require_auth=True,
        mcp_service_token="test-secret",
    )

    settings.validate_deployment()


@pytest.mark.parametrize("url", [
    "https:///mcp", "https://user:password@campus.example.invalid/mcp",
    "https://campus.example.invalid/mcp?token=secret",
    "https://campus.example.invalid/mcp#fragment",
    "https://campus.example.invalid/healthz", "https://campus.example.invalid:invalid/mcp",
])
def test_staging_rejects_invalid_mcp_url(url):
    settings = Settings(app_env="staging", mcp_public_url=url,
                        mcp_require_auth=True, mcp_service_token="test-secret")
    with pytest.raises(ValueError):
        settings.validate_deployment()
