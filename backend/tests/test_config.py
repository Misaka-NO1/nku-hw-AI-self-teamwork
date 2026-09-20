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
