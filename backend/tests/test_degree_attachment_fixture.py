"""Public synthetic attachment for platform preview; never a saved personal report."""
import json
from pathlib import Path

import pytest

from app.core.degree_progress import agent_report
from app.core.errors import AppError
from app.core.security import payload_hash


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/degree/degree-progress-attachment.demo.json"
EXPECTED_PAYLOAD_HASH = "2d1c9647b57ccb9a951278ad663ba9661f8fe0e0c657ef6b674e4fe10f03abcc"


def test_synthetic_attachment_is_complete_31_module_report_in_requested_size_range():
    raw = FIXTURE.read_bytes()
    assert 6 * 1024 <= len(raw) <= 8 * 1024
    assert not raw.startswith(b"\xef\xbb\xbf")
    parsed = json.loads(raw.decode("utf-8"))
    validated = agent_report({"report_json": raw.decode("utf-8")})
    assert validated == parsed  # No field or module is supplied by the model.
    assert validated["kind"] == "degree_credit_progress"
    assert validated["program"] == "虚构附件验收专业（非个人数据）"
    assert validated["summary"]["note"] == "用于附件全文读取与预览验收，不确认保存"
    assert len(validated["modules"]) == 31
    assert [m["title"] for m in validated["modules"]] == [f"虚构模块{i:02d}" for i in range(1, 32)]
    for module in validated["modules"]:
        assert module["school_note"] == "合成附件验收"
        assert module["school_in_progress_credits"] == "1"
        assert module["school_direct_in_progress_credits"] == "1"
        assert not {"courses", "grade", "student_id", "owner_id", "workspace_ref"} & module.keys()
    assert payload_hash(validated) == EXPECTED_PAYLOAD_HASH


@pytest.mark.parametrize("options", [
    {"ensure_ascii": False, "indent": 2},
    {"ensure_ascii": True, "sort_keys": True},
    {"ensure_ascii": False, "sort_keys": True, "separators": (",", ":")},
])
def test_attachment_canonical_hash_is_not_dependent_on_json_whitespace_or_key_order(options):
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = agent_report({"report_json": json.dumps(original, **options)})
    assert report == original
    assert payload_hash(report) == EXPECTED_PAYLOAD_HASH


@pytest.mark.parametrize("mode", ["url_only", "metadata_only", "truncated", "double_encoded"])
def test_attachment_requires_full_text_not_filename_url_or_summary(mode):
    raw = FIXTURE.read_text(encoding="utf-8")
    argument = {
        "url_only": {"report_json": "https://attachments.example.invalid/degree-progress.json"},
        "metadata_only": {"report_json": json.dumps({"filename": FIXTURE.name, "modules": 31})},
        "truncated": {"report_json": raw[: len(raw) // 2]},
        "double_encoded": {"report_json": json.dumps(raw)},
    }[mode]
    with pytest.raises(AppError) as error:
        agent_report(argument)
    assert error.value.status_code == 422
