import importlib.util
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[2] / "deploy/genios-workflows/repair_native_binding_prompt.py"
spec = importlib.util.spec_from_file_location("native_prompt_repair", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def original():
    return "\n".join(["保留原课表和日历业务。", module.OLD_HEADING,
        "入口和设备码说明保留。", module.START + "后必须旧OAuth bind_my_browser。",
        "只有authorized才进入的旧规则。", module.END + "支持本人确认后导入。",
        "其他功能保持不变。", module.OLD_NATIVE + "先lookup不确认。"])


def test_repair_preserves_other_rules_and_removes_conflicting_binding():
    result = module.repair(original())
    for keep in ("保留原课表和日历业务。", "入口和设备码说明保留。",
                 module.END + "支持本人确认后导入。", "其他功能保持不变。"):
        assert keep in result
    assert "后必须旧OAuth bind_my_browser" not in result
    assert "existing_space表示平台身份已关联唯一空间" in result
    assert "legacy_authorization_required才走" in result
    assert "browser_authorized仅表示可领取" in result
    assert "attest_my_platform_identity→read_my_demo_records（课表）/read_my_calendar_entries（日历）" in result
    assert "不得只说“将读取”后结束" in result
    assert "401/invalid_token表示授权失效" in result
    assert "公开问答不读私有摘要" in result
    assert module.NEW_HEADING in result


@pytest.mark.parametrize("prompt", ["", original() + original(), original().replace(module.END, "未知")])
def test_ambiguous_prompt_fails_closed(prompt):
    with pytest.raises(ValueError):
        module.repair(prompt)


def test_byte_limit_fails_without_truncating_business_rules():
    with pytest.raises(ValueError, match="byte limit"):
        module.repair(original() + "\n" + "原业务" * 22000)


def test_byte_limit_includes_final_newline():
    base = original()
    padding = 65535 - len(module.repair(base).encode("utf-8"))
    assert len(module.repair("x" * padding + base).encode("utf-8")) == 65535
    with pytest.raises(ValueError, match="byte limit"):
        module.repair("x" * (padding + 1) + base)


def test_repair_keeps_complete_meeting_periods_and_source_times():
    result = module.repair(original())
    assert result.count("【课表时间准确性】") == 1
    for rule in (
        "按查询日期计算教学周、weekday并筛选meeting.weeks",
        "start_period到end_period（两端都包含）",
        "开始时间取term.periods中start_period的start，结束取end_period的end",
        "不把跨三节课缩成一两节，不漏最后一节，不凭习惯补时间",
        "节次缺失就说明无法确定",
        "不从课程名猜实验",
        "只有逐项核对后才描述空闲",
        "同一course的多个meeting只算一门课程",
        "逐项称“上课安排/次数”，不把三次上课说成三门课",
        "课程名严格使用source course.title",
        "优先使用schedule.resolved_meetings的course_title、period_label、time_label",
        "完整照录后端计算的每次起止时间，不再自行缩短",
        "不根据教室或实验楼给课程改名、加“实验”后缀",
    ):
        assert rule in result
    assert "existing_space表示平台身份已关联唯一空间" in result
    assert "401/invalid_token表示授权失效" in result
    assert "course.name" not in result


def test_campus_rule_uses_current_public_kb_and_preserves_source_boundaries():
    rule = FILE.with_name("campus-affairs-r1-agent-rule.txt").read_text(encoding="utf-8")
    for required in (
        "KB_Campus-20261013-r1.md", "nku-affairs-2026-10-13-r1",
        "owner_confirmed_guidance", "不改称官方核验", "原核验日期",
        "多个事务时逐项检索", "学生证与校园卡", "空调报修与租赁",
        "本科生不套用研究生", "历史截止日期", "不改为当前开放",
        "缺失信息不编造", "公共知识库", "不调用私人待办或日历",
    ):
        assert required in rule
    assert "nku-affairs-2026-10-08-r1" not in rule
