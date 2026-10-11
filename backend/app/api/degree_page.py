"""Read-only curriculum analysis route, installed with a host-owned authorizer.

No owner IDs, persistence, demo fallback or authentication implementation here.
The host must verify its existing browser session before processing the body.
"""
from typing import Annotated, Any, Callable
import json
from fastapi import Body, Request
from app.core.envelope import success, FieldError
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.domains.degree.page_progress import analyze_page_progress, PageProgressValidationError


def install_degree_page_routes(site, authorize: Callable[[Request], Any]):
    @site.post("/api/v1/degree/page/observation")
    def observation(request: Request, payload: Annotated[dict[str, Any], Body()]):
        authorize(request)
        if request.url.query:
            raise AppError(422, "VALIDATION_ERROR", "培养计划读取分析不接受额外参数")
        from app.domains.degree.page_observation import analyze_page_observation, PageObservationValidationError
        from app.domains.degree.page_report import analyze_page_report
        try:
            result = analyze_page_report(payload)
        except PageObservationValidationError as exc:
            raise AppError(422, "VALIDATION_ERROR", "培养计划读取内容未通过校验", field_errors=[FieldError(field="observation", code=exc.code, message="读取内容无效")]) from None
        return success(result, request_id=current_request_id(request), data_version="degree-page-v1")

    @site.post("/api/v1/degree/page/analyze")
    def analyze(request: Request, payload: Annotated[dict[str, Any], Body()]):
        authorize(request)
        allowed = {"plan_version", "source_coverage", "missing_pages", "repeat_policy", "evidence", "coverage_evidence", "courses", "modules"}
        if request.url.query or set(payload) - allowed:
            raise AppError(422, "VALIDATION_ERROR", "培养计划分析不接受归属字段或未知参数")
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 1_048_576:
            raise AppError(422, "VALIDATION_ERROR", "培养计划内容超过限制")
        if not isinstance(payload.get("modules"), list) or len(payload["modules"]) > 500:
            raise AppError(422, "VALIDATION_ERROR", "模块数量或结构无效")
        if not isinstance(payload.get("courses"), list) or len(payload["courses"]) > 2000:
            raise AppError(422, "VALIDATION_ERROR", "课程数量或结构无效")
        try:
            result = analyze_page_progress(payload)
        except PageProgressValidationError as exc:
            # Never echo original page/student values in error responses.
            raise AppError(422, "VALIDATION_ERROR", "培养计划结构未通过校验", field_errors=[FieldError(field="snapshot", code=exc.code, message="字段无效")]) from None
        return success(result, request_id=current_request_id(request), data_version="degree-page-v1")
