"""Notice backend over the EXISTING cloud identity; no alternate users or UI."""
from secrets import token_urlsafe

from app.core.contracts import validate_boundary
from app.core.errors import AppError
from app.core.notice_plan import calculate_notice, validate_notice_plan
from app.core.security import payload_hash, require_idempotency_key, secret_hash
from app.core.notice_workflow import extract_notice, run_notice_workflow


class CloudNoticeService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not self.settings.cloud_notice_text_pilot_enabled:
            raise AppError(403, "DEMO_ONLY", "云文字试点未开启")
        from app.cloud_identity_site import require_cloud_identity
        require_cloud_identity(self.settings)

    def records(self, args):
        self.gate()
        return self.store.notice_call("records", args)

    def read(self, args, payload):
        self.records(args)  # verify owner/grant before parsing user-supplied text
        validate_boundary(payload, "NoticePilotReadRequest")
        self.fictional(payload)
        return extract_notice(payload)

    def workflow(self, args, payload):
        records = self.records(args)
        validate_boundary(payload, "NoticeTextWorkflowRequest")
        self.fictional(payload["read"])
        return run_notice_workflow(payload, records)

    def check(self, args, payload):
        records = self.records(args)
        validate_boundary(payload, "NoticePilotCheckRequest")
        self.fictional(payload)
        return calculate_notice(payload, records, records["workspace_ref"])

    @staticmethod
    def fictional(payload):
        if payload.get("fictional_data_confirmed") is not True:
            raise AppError(403, "DEMO_ONLY", "请明确确认仅使用自编虚构通知")

    def _retry(self, args, operation, key, request_hash):
        require_idempotency_key(key)
        return self.store.notice_call("lookup", {**args, "operation": operation,
                                                "key": key, "request_hash": request_hash})

    def draft(self, args, payload, key, draft_id=None):
        self.gate()
        validate_boundary(payload, "NoticePilotUpdateRequest" if draft_id else "NoticePilotDraftRequest")
        operation = "update" if draft_id else "create"
        digest = payload_hash({"operation": operation, "draft_id": draft_id, "body": payload})
        cached = self._retry(args, operation, key, digest)
        if cached is not None:
            return self.review(cached)
        records = self.records(args)
        if draft_id:
            draft = self.store.notice_call("get_draft", {**args, "draft_id": draft_id})
            if draft["status"] != "draft" or draft["revision"] != payload["revision"]:
                raise AppError(409, "STALE_REVISION", "草稿版本已变更")
        plan = payload["plan"]
        self.fictional(plan)
        plan_hash = validate_notice_plan(plan, records, records["workspace_ref"])
        data = {**args, "plan": plan, "payload_hash": plan_hash, "records_revision": records["records_revision"],
                "draft_id": draft_id or "notice_draft_" + token_urlsafe(18), "key": key, "request_hash": digest}
        if draft_id:
            data["revision"] = payload["revision"]
        return self.review(self.store.notice_call(operation, data))

    @staticmethod
    def review(result):
        # A frontend is outside this delivery. Do not point to the old fixture
        # page as though it could render and confirm this new payload.
        return {**result, "review_url": None, "review_required": True}

    def get_draft(self, args, draft_id):
        self.gate()
        return self.review(self.store.notice_call("get_draft", {**args, "draft_id": draft_id}))

    def confirm(self, args, payload, key):
        self.gate()
        validate_boundary(payload, "ConfirmationRequest")
        digest = payload_hash(payload)
        draft = self.store.notice_call("get_draft", {**args, "draft_id": payload["draft_id"]})
        if draft["revision"] != payload["revision"] or draft["payload_hash"] != payload["payload_hash"]:
            raise AppError(409, "STALE_REVISION", "草稿版本已变更")
        cached = self._retry(args, "confirm", key, digest)
        if cached is not None:
            return cached
        records = self.records(args)
        validate_notice_plan(draft["payload"], records, records["workspace_ref"])
        raw = "notice_confirmation_" + token_urlsafe(18)
        return self.store.notice_call("confirm", {**args, **payload, "key": key, "request_hash": digest,
            "records_revision": records["records_revision"], "confirmation_id": raw, "confirmation_hash": secret_hash(raw)})

    def commit(self, args, payload):
        self.gate()
        validate_boundary(payload, "CommitRequest")
        key = payload["idempotency_key"]
        digest = payload_hash({"confirmation_id": payload["confirmation_id"]})
        ticket_hash = secret_hash(payload["confirmation_id"])
        draft = self.store.notice_call("get_confirmation", {**args, "confirmation_hash": ticket_hash})
        cached = self._retry(args, "commit", key, digest)
        if cached is not None:
            return cached
        records = self.records(args)
        validate_notice_plan(draft["payload"], records, records["workspace_ref"])
        return self.store.notice_call("commit", {**args, "confirmation_hash": ticket_hash, "key": key,
            "request_hash": digest, "records_revision": records["records_revision"], "resource_id": "notice_task_" + token_urlsafe(18)})

    def tasks(self, args, offset=0, limit=5):
        self.gate()
        return self.store.notice_call("list_tasks", {**args, "offset": offset, "limit": limit})

    def task(self, args, task_id):
        self.gate()
        return self.store.notice_call("get_task", {**args, "task_id": task_id})
