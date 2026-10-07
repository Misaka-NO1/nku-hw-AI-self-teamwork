FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=staging \
    AUTH_MODE=demo_fixture ALLOW_PERSONAL_UPLOADS=false DEMO_WORKSPACE_TTL_HOURS=24 \
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
CMD ["python", "-m", "uvicorn", "app.cloud_tasks_site:create_cloud_tasks_site", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
