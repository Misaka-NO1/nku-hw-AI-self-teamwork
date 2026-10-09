from typing import Annotated, Any
from fastapi import Body, Request
from app.core.envelope import success
from app.core.personal_tasks import PersonalTaskService
from app.core.request_id import current_request_id
from app.core.errors import AppError


def install_personal_routes(site, settings, store, browser_args, format_times):
    service = PersonalTaskService(settings, store)
    def args(request, write=False):
        if request.url.query:
            raise AppError(422, "VALIDATION_ERROR", "本人归属来自登录状态，不接受查询参数")
        return {"principal_kind": "browser", **browser_args(request, write)}
    def reply(request, data):
        return success(format_times(data), request_id=current_request_id(request), data_version="personal-tasks-v1")
    @site.post("/api/v1/tasks/entries/drafts")
    def draft(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.draft(args(request, True), payload))
    @site.post("/api/v1/tasks/entries/commit")
    def commit(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.commit(args(request, True), payload))
