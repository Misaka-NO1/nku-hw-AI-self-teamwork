FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    MCP_PATH=/mcp \
    APP_ENV=staging \
    MCP_REQUIRE_AUTH=true \
    MCP_ENABLE_DOMAIN_TOOLS=true \
    DOMAIN_BUNDLE_MANIFEST_PATH=/srv/campus/domain-bundle-manifest.json \
    DATABASE_URL=sqlite:///:memory: \
    AUTH_MODE=demo_fixture \
    ALLOW_PERSONAL_UPLOADS=false

WORKDIR /srv/campus/backend
COPY backend/requirements.lock /srv/campus/backend/requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && useradd --system --uid 10001 --create-home campus
COPY backend/app/ /srv/campus/backend/app/
COPY contracts/core.schema.json contracts/api.schema.json /srv/campus/contracts/
COPY fixtures/timetable.demo.json fixtures/term.demo.json \
    fixtures/degree-plan.demo.json fixtures/transcript.demo.json \
    fixtures/notice-event.demo.json fixtures/notice-deadline.demo.json fixtures/notice-ambiguous.demo.json \
    fixtures/time-free-query.demo.json fixtures/time-event-query.demo.json fixtures/time-deadline-query.demo.json \
    fixtures/scenic-query.demo.json fixtures/study-query.demo.json fixtures/degree-query.demo.json /srv/campus/fixtures/
COPY knowledge/scenic/catalog.demo.json /srv/campus/knowledge/scenic/catalog.demo.json
COPY knowledge/study/materials.json /srv/campus/knowledge/study/materials.json
COPY knowledge/study/sources/demo-note-01.md /srv/campus/knowledge/study/sources/demo-note-01.md
COPY Dockerfile domain-bundle-manifest.json /srv/campus/
USER campus
EXPOSE 8080
CMD ["python", "-m", "app.mcp.http"]
