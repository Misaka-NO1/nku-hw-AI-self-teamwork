"""Curriculum import follows the timetable's human draft/confirm/commit flow."""
from typing import Annotated, Any
from fastapi import Body, Header, Request
from app.core.envelope import success
from app.core.errors import AppError
from app.core.personal_degree import PersonalDegreeService
from app.core.request_id import current_request_id


def install_personal_degree_routes(site, settings, store, browser_args, authorize_write, format_times):
    service = PersonalDegreeService(settings, store)

    def principal(request, write=False):
        service.gate()
        if request.url.query:
            raise AppError(422, "VALIDATION_ERROR", "本人培养计划不接受账号或额外参数")
        if write:
            authorize_write(request)
        return {"principal_kind": "browser", **browser_args(request, write)}

    def reply(request, value):
        return success(format_times(value), request_id=current_request_id(request), data_version="personal-degree-v1")

    @site.post("/api/v1/degree/import-drafts")
    def draft(request: Request, payload: Annotated[dict[str, Any], Body()], key: Annotated[str, Header(alias="Idempotency-Key")]):
        return reply(request, service.draft(principal(request, True), payload, key))

    @site.get("/api/v1/degree/drafts/{draft_id}")
    def get_draft(request: Request, draft_id: str):
        return reply(request, service.get_draft(principal(request), draft_id))

    @site.post("/api/v1/degree/confirmations")
    def confirm(request: Request, payload: Annotated[dict[str, Any], Body()], key: Annotated[str, Header(alias="Idempotency-Key")]):
        return reply(request, service.confirm(principal(request, True), payload, key))

    @site.post("/api/v1/degree/commit")
    def commit(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.commit(principal(request, True), payload))

    @site.get("/api/v1/degree/current")
    def current(request: Request):
        return reply(request, service.read(principal(request)))
