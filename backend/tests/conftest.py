import os

import pytest


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_MODE", "demo_fixture")
os.environ.setdefault("ALLOW_PERSONAL_UPLOADS", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("BUILD_ID", "test-build")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
