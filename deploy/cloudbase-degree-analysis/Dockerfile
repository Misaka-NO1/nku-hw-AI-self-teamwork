FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=staging \
    MCP_HOST=0.0.0.0 MCP_PORT=8080 MCP_PATH=/mcp MCP_REQUIRE_AUTH=true \
    MCP_ENABLE_DOMAIN_TOOLS=false MCP_ENABLE_PLATFORM_COMPAT_TOOLS=false \
    AUTH_MODE=demo_fixture ALLOW_PERSONAL_UPLOADS=false
WORKDIR /srv/campus
COPY backend/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && useradd --system --uid 10001 --create-home campus
COPY backend/app ./app
RUN find /srv/campus/app -type d -exec chmod 0555 {} + \
    && find /srv/campus/app -type f -exec chmod 0444 {} +
USER campus
EXPOSE 8080
CMD ["python", "-m", "app.mcp.degree_http"]
