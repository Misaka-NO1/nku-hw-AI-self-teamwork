"""Prepend the DDL persistence rule without dropping existing Agent business text."""
from pathlib import Path

RULE = Path(__file__).with_name("calendar-deadline-agent-rule.txt")
HEADER = "【DDL独立字段，覆盖旧待办规则】"
ANCHORS = ("【课表时间准确性】", "【本人待办持久保存：2026-10-07接入规则】",
           "【身份接入最终规则：覆盖旧设备绑定规则】", "【学分问答与导入最终规则】")
DRAFT_PREFIX = "只调用独立草稿工具生成未保存草稿："
COMPACT_DRAFT = ("待办写入只用独立草稿工具：query_json编码一次，恰含content、idempotency_key；"
                 "content仅用契约字段，scheduled_slots每项仅start/end。展示规范化内容、真draft_id/payload_hash，"
                 "等本人下一轮明确确认才commit并读回。失败说明未保存；422核对全部字段，"
                 "只修无歧义格式后重试一次，不改业务值，仍失败停止，不编造回执。")


def repair(prompt: str) -> str:
    if any(prompt.count(anchor) != 1 for anchor in ANCHORS):
        raise ValueError("Expected current reviewed Agent prompt; do not replace unrelated rules")
    rule = RULE.read_text(encoding="utf-8").strip()
    lines = [line for line in prompt.splitlines() if line.strip()]
    old = [line for line in lines if line.startswith(DRAFT_PREFIX)]
    if len(old) > 1:
        raise ValueError("Ambiguous duplicate task draft paragraph")
    if old:
        # Rephrase only this reviewed, redundant calendar paragraph to fit the
        # platform limit; preserve every other non-empty business paragraph.
        if not all(marker in old[0] for marker in ("scheduled_slots", "draft_id/payload_hash", "422", "重试一次")):
            raise ValueError("Unrecognized task draft paragraph")
        lines = [COMPACT_DRAFT if line == old[0] else line for line in lines]
    normalized = "\n".join(lines)
    if HEADER in normalized:
        if normalized.count(HEADER) != 1 or not normalized.startswith(rule + "\n"):
            raise ValueError("Existing DDL rule differs; review before replacing")
        result = normalized + "\n"
    else:
        result = rule + "\n" + normalized + "\n"
    if len(result.encode("utf-8")) > 65535:
        raise ValueError("Prompt exceeds platform byte limit; never truncate business rules")
    return result
