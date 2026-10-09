FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=staging \
    MCP_HOST=0.0.0.0 MCP_PORT=8080 MCP_PATH=/mcp MCP_REQUIRE_AUTH=true \
    MCP_ENABLE_DOMAIN_TOOLS=true MCP_ENABLE_PLATFORM_COMPAT_TOOLS=true \
    AUTH_MODE=demo_fixture ALLOW_PERSONAL_UPLOADS=false PUBLIC_CATALOG_PROFILE=published \
    DATABASE_URL=sqlite:///:memory: DOMAIN_BUNDLE_MANIFEST_PATH=/srv/campus/public-content-manifest.json
WORKDIR /srv/campus/backend
COPY backend/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock && useradd --system --uid 10001 --create-home campus
COPY backend/app/ ./app/
COPY contracts/ /srv/campus/contracts/
COPY fixtures/ /srv/campus/fixtures/
COPY knowledge/ /srv/campus/knowledge/
COPY frontend/dist/ /srv/campus/frontend/dist/
COPY campus-map/ /srv/campus/campus-map/
COPY Dockerfile public-content-manifest.json /srv/campus/
USER campus
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.public_content_site:create_public_content_site", "--factory", "--host", "0.0.0.0", "--port", "8080"]
