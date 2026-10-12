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
