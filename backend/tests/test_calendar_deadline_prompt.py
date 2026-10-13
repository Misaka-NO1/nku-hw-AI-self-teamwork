import importlib.util
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[2] / "deploy/genios-workflows/repair_calendar_deadline_prompt.py"
spec = importlib.util.spec_from_file_location("deadline_prompt_repair", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    return "\n\n\n\n".join(module.ANCHORS) + "\n\n其他原业务不可删除。\n"


def test_deadline_rule_preserves_all_business_and_is_idempotent():
    result = module.repair(sample())
    assert result.startswith(module.HEADER)
    assert module.repair(result) == result
    for line in sample().splitlines():
        if line:
            assert line in result
    for text in ("kind=deadline", "content.due_at", "content.due_date", "不能仅在备注写DDL",
                 "必须继承同一事项最新已核对的DDL", "不把计划结束当截止",
                 "未明确修改不得清空/替换DDL", "无截止不编造", "仅日期不补23:59",
                 "24:00转次日00:00", "截止（DDL）", "计划完成时段",
                 "草稿返回后逐项核对", "notice.due.at/date", "全部scheduled_slots",
                 "等本人下一轮确认", "不自动重复创建", "不占工作区间"):
        assert text in result


@pytest.mark.parametrize("value", ["", sample() + sample(), sample().replace(module.ANCHORS[0], "其他版本")])
def test_missing_or_ambiguous_anchor_fails_closed(value):
    with pytest.raises(ValueError):
        module.repair(value)


def test_conflicting_existing_rule_and_excess_bytes_fail_closed():
    with pytest.raises(ValueError, match="differs"):
        module.repair(module.HEADER + "错误内容\n" + sample())
    with pytest.raises(ValueError, match="byte limit"):
        module.repair(sample() + "原业务" * 23000)


def test_public_tool_descriptions_keep_due_separate_from_notes_and_slots():
    import json
    root = FILE.parent
    for name in ("personal-task-tools.openapi.json", "oauth-recovery-tools.openapi.json"):
        doc = json.loads((root / name).read_text(encoding="utf-8"))
        text = doc["paths"]["/oauth/tasks/entries/drafts"]["post"]["description"]
        for required in ("kind=deadline", "不能只写notes", "保留原DDL", "scheduled_slots", "核对"):
            assert required in text


def test_only_reviewed_redundant_task_paragraph_is_compacted():
    paragraph = module.DRAFT_PREFIX + "scheduled_slots、draft_id/payload_hash；422重试一次。"
    result = module.repair(sample() + paragraph)
    assert paragraph not in result
    assert module.COMPACT_DRAFT in result
    for line in sample().splitlines():
        if line:
            assert line in result
    assert module.repair(result) == result
    with pytest.raises(ValueError, match="Ambiguous"):
        module.repair(sample() + paragraph + "\n" + paragraph)
    with pytest.raises(ValueError, match="Unrecognized"):
        module.repair(sample() + module.DRAFT_PREFIX + "different content")
