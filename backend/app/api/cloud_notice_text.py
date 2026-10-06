"""Backend-only opt-in routes. Never registered by the public content site."""
from typing import Annotated, Any
from fastapi import Body, File, Form, Header, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.cloud_notice_text import CloudNoticeService
from app.core.envelope import success
from app.core.request_id import current_request_id
from app.domains.schedule.service import CALCULATION_VERSION


def install_notice_routes(site, settings, store, browser_args, format_times):
    service = CloudNoticeService(settings, store)

    def args(request, write=False):
        return {"principal_kind": "browser", **browser_args(request, write)}

    def reply(request, data, calculation=False):
        return success(format_times(data), request_id=current_request_id(request), data_version="notice-text-pilot-v1",
                       **({"calculation_version": CALCULATION_VERSION} if calculation else {}))

    @site.post("/api/v1/notice-text/read")
    def read(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.read(args(request, True), payload))

    @site.post("/api/v1/notice-text/check")
    def check(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.check(args(request, True), payload), calculation=True)

    @site.post("/api/v1/notice-text/workflow")
    def workflow(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.workflow(args(request, True), payload),
                     calculation=payload.get("analysis") is not None)

    @site.post("/api/v1/notice-text/images/read")
    async def image_read(request: Request, file: Annotated[UploadFile, File()],
                         fictional_data_confirmed: Annotated[bool, Form()],
                         source_ref: Annotated[str, Form()] = "self-authored-screenshot",
                         reference_at: Annotated[str | None, Form()] = None):
        from app.domains.tasks.notice_image_reader import MAX_IMAGE_BYTES, ScreenshotReader
        service.records(args(request, True))
        service.fictional({"fictional_data_confirmed": fictional_data_confirmed})
        form = await request.form()
        if set(form) - {"file", "fictional_data_confirmed", "source_ref", "reference_at"} or any(len(form.getlist(k)) != 1 for k in form):
            from app.core.errors import AppError
            raise AppError(422, "VALIDATION_ERROR", "截图输入包含额外或重复字段")
        try:
            data = await file.read(MAX_IMAGE_BYTES + 1)
            source = await run_in_threadpool(ScreenshotReader(settings).read, data, file.content_type)
        finally:
            await file.close()
        read_payload = {"source_text": source["source_text"], "source_ref": source_ref,
            "reference_at": reference_at, "fictional_data_confirmed": True,
            "source_kind": "ocr", "document_sha256": source["document_sha256"]}
        batch = service.read(args(request, True), read_payload)
        return reply(request, {"source": source, "read_request": read_payload, "batch": batch,
                               "can_save": False})

    @site.post("/api/v1/notice-text/drafts")
    def draft(request: Request, payload: Annotated[dict[str, Any], Body()], key: Annotated[str, Header(alias="Idempotency-Key")]):
        return reply(request, service.draft(args(request, True), payload, key))

    @site.get("/api/v1/notice-text/drafts/{draft_id}")
    def get_draft(request: Request, draft_id: str):
        return reply(request, service.get_draft(args(request), draft_id))

    @site.post("/api/v1/notice-text/drafts/{draft_id}/update")
    def update(request: Request, draft_id: str, payload: Annotated[dict[str, Any], Body()], key: Annotated[str, Header(alias="Idempotency-Key")]):
        return reply(request, service.draft(args(request, True), payload, key, draft_id))

    @site.post("/api/v1/notice-text/confirmations")
    def confirm(request: Request, payload: Annotated[dict[str, Any], Body()], key: Annotated[str, Header(alias="Idempotency-Key")]):
        return reply(request, service.confirm(args(request, True), payload, key))

    @site.post("/api/v1/notice-text/commit")
    def commit(request: Request, payload: Annotated[dict[str, Any], Body()]):
        return reply(request, service.commit(args(request, True), payload))

    @site.get("/api/v1/notice-text/tasks")
    def tasks(request: Request, offset: Annotated[int, Query(ge=0, le=100)] = 0,
              limit: Annotated[int, Query(ge=1, le=5)] = 5):
        if set(request.query_params) - {"offset", "limit"}:
            from app.core.errors import AppError
            raise AppError(422, "VALIDATION_ERROR", "列表仅接受分页参数")
        return reply(request, service.tasks(args(request), offset, limit))

    @site.get("/api/v1/notice-text/tasks/{task_id}")
    def task(request: Request, task_id: str):
        return reply(request, service.task(args(request), task_id))
