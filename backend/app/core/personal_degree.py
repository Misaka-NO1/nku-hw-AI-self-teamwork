"""Own curriculum drafts and confirmed snapshots; timetable storage is untouched."""
import json
from secrets import token_urlsafe

from app.core.errors import AppError
from app.core.security import payload_hash, require_idempotency_key, secret_hash
from app.domains.degree.page_observation import PageObservationValidationError
from app.domains.degree.page_report import analyze_page_report


class PersonalDegreeService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not self.settings.cloud_personal_degree_enabled:
            raise AppError(403, "FORBIDDEN", "本人培养计划导入尚未启用")

    def read(self, args, agent=False):
        self.gate()
        return self.store.degree_call("records" if agent else "current", args)

    def draft(self, args, observation, key):
        self.gate()
        require_idempotency_key(key)
        try:
            report = analyze_page_report(observation)
        except PageObservationValidationError:
            raise AppError(422, "VALIDATION_ERROR", "培养计划读取内容未通过校验") from None
        if not report.get("modules") and not report.get("courses"):
            raise AppError(422, "VALIDATION_ERROR", "未识别到培养计划模块或课程，不能生成空草稿")
        # Bound the stored observation AND computed evidence-rich report.
        if len(json.dumps({"payload": observation, "report": report}, ensure_ascii=False).encode()) > 900000:
            raise AppError(422, "VALIDATION_ERROR", "培养计划过大，请缩小读取范围")
        digest = payload_hash({"observation": observation, "report": report})
        return self.store.degree_call("draft", {**args, "observation": observation, "report": report,
            "report_hash": payload_hash(report),
            "payload_hash": digest, "key": key,
            "request_hash": payload_hash(observation), "draft_id": "draft_" + token_urlsafe(18)})

    def get_draft(self, args, draft_id):
        self.gate()
        return self.store.degree_call("get_draft", {**args, "draft_id": draft_id})

    def confirm(self, args, payload, key):
        self.gate()
        require_idempotency_key(key)
        allowed = {"draft_id", "revision", "payload_hash", "share_with_agent"}
        if type(payload) is not dict or set(payload) != allowed:
            raise AppError(422, "VALIDATION_ERROR", "请核对培养计划草稿与版本")
        if payload["share_with_agent"] is not True:
            raise AppError(409, "CONFIRMATION_REQUIRED", "请明确确认保存并供本人 Agent 读取")
        if (type(payload["revision"]) is not int or payload["revision"] < 1
                or type(payload["draft_id"]) is not str or type(payload["payload_hash"]) is not str):
            raise AppError(422, "VALIDATION_ERROR", "培养计划草稿字段无效")
        receipt = "confirmation_" + token_urlsafe(18)
        draft = self.get_draft(args, payload["draft_id"])
        return self.store.degree_call("confirm", {**args, **payload, "key": key,
            "report_hash": draft["report_hash"],
            "request_hash": payload_hash(payload), "confirmation_id": receipt,
            "confirmation_hash": secret_hash(receipt)})

    def commit(self, args, payload):
        self.gate()
        if type(payload) is not dict or set(payload) != {"confirmation_id", "idempotency_key"}:
            raise AppError(422, "VALIDATION_ERROR", "培养计划保存参数无效")
        if type(payload["confirmation_id"]) is not str or not 1 <= len(payload["confirmation_id"]) <= 128:
            raise AppError(422, "VALIDATION_ERROR", "培养计划确认凭据无效")
        require_idempotency_key(payload["idempotency_key"])
        return self.store.degree_call("commit", {**args, "key": payload["idempotency_key"],
            "share_with_agent": True,
            "request_hash": payload_hash({"confirmation_id": payload["confirmation_id"]}),
            "confirmation_hash": secret_hash(payload["confirmation_id"]),
            "resource_id": "degree_" + token_urlsafe(18)})
