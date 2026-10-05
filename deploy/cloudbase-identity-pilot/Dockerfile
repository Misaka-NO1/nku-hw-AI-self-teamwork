FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=staging \
    AUTH_MODE=demo_fixture ALLOW_PERSONAL_UPLOADS=false DEMO_WORKSPACE_TTL_HOURS=24 \
    CLOUDBASE_AUTH_SESSION_SECONDS=900 CLOUDBASE_AUTH_PROFILE=pg_registered \
    CLOUD_IDENTITY_PILOT_ENABLED=false CLOUD_OAUTH_PILOT_ENABLED=false CLOUD_IDENTITY_BOOTSTRAP_ENABLED=false \
    CLOUD_OAUTH_COMPETITION_COMPAT_ENABLED=false \
    OAUTH_LOCAL_ENABLED=false AGENT_PAIRING_LOCAL_ENABLED=false \
    MCP_ENABLE_DOMAIN_TOOLS=false MCP_ENABLE_PLATFORM_COMPAT_TOOLS=false
WORKDIR /srv/campus/backend
COPY backend/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && useradd --system --uid 10001 --create-home campus
COPY backend/app ./app
COPY contracts /srv/campus/contracts
COPY fixtures /srv/campus/fixtures
COPY frontend/dist /srv/campus/frontend/dist
USER campus
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.cloud_identity_site:create_cloud_identity_site", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
