from typing import Annotated, Any
from fastapi import Body, Header, Query, Request
from app.core.task_calendar import TaskCalendarService
from app.core.envelope import success
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.domains.schedule.service import CALCULATION_VERSION


def install_calendar_routes(site, settings, store, browser_args, format_times):
    service = TaskCalendarService(settings, store)
    def args(request, write=False):
        return {"principal_kind": "browser", **browser_args(request, write)}
    def reply(request, data, calculation=False):
        return success(format_times(data), request_id=current_request_id(request), data_version="task-calendar-v1",
            **({"calculation_version": CALCULATION_VERSION} if calculation else {}))
    def query(request):
        if set(request.query_params) != {"workspace_ref"} or len(request.query_params.getlist("workspace_ref")) != 1:
            raise AppError(422, "VALIDATION_ERROR", "只允许一个本人工作区参数")

    @site.get("/api/v1/tasks/calendar")
    def calendar(request: Request, workspace_ref: Annotated[str, Query(min_length=1, max_length=128)]):
        query(request)
        return reply(request, service.list(args(request), workspace_ref))

    @site.get("/api/v1/tasks/calendar/summary")
    def summary(request: Request, workspace_ref: Annotated[str, Query(min_length=1, max_length=128)]):
        query(request)
        return reply(request, service.summary(args(request), workspace_ref))

    @site.get("/api/v1/tasks/{task_id}/calendar/candidates")
    def candidates(request: Request, task_id: str, workspace_ref: Annotated[str, Query(min_length=1, max_length=128)]):
        query(request)
        return reply(request, service.candidates(args(request), task_id, workspace_ref), True)

    @site.post("/api/v1/tasks/{task_id}/calendar")
    def update(request: Request, task_id: str, payload: Annotated[dict[str, Any], Body()],
               key: Annotated[str, Header(alias="Idempotency-Key")]):
        if request.url.query:
            raise AppError(422, "VALIDATION_ERROR", "写入参数只来自请求正文")
        return reply(request, service.update(args(request, True), task_id, payload, key))
