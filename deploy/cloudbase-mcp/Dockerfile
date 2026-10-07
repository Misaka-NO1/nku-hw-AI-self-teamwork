FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    MCP_PATH=/mcp \
    APP_ENV=staging \
    MCP_REQUIRE_AUTH=true \
    AUTH_MODE=demo_fixture \
    ALLOW_PERSONAL_UPLOADS=false

WORKDIR /srv/campus
COPY backend/requirements.lock /srv/campus/requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && useradd --system --uid 10001 --create-home campus
COPY backend/app /srv/campus/app
USER campus
EXPOSE 8080
CMD ["python", "-m", "app.mcp.http"]
