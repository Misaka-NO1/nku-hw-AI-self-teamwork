"""培养计划已观测 DOM 章节层级的纯推断。

定位
----
``infer_degree_hierarchy(modules)`` 只消费**已经观测到的模块报告数组**，按文档
顺序把它们还原成「中文主章 → 括号子章 → 数字子模块 → 点分细项」的父子关系。
它是纯函数：不读写文件、不访问网络、不做身份识别、不修改输入、不计算学分，也
不把规则文字（例如「所有子项均应满足要求」）当成指令。

本函数不替代既有解析器，而是给 Codex 一个**可回退**的层级结论：
``profile == "unsupported"`` 时，调用方必须沿用既有纯数字解析。

输入契约
--------
``modules`` 是模块报告数组，每一项只读取三个字段::

    {
      "row_index": 0,          # int，文档顺序中的稳定行号
      "label": "一\u00a0虚构主章(所有子项均应满足要求)",
      "locator": "dom-row:0",  # str，用于待核实项定位
    }

其余字段（学分、规则文本、证据、原始单元格等）一律忽略，绝不当成层级证据。
输入不会被修改，返回结构中也不保留标签原文。

已观测 DOM 章节模式（标签全部为虚构示例）
----------------------------------------
==================================  ==================  ================
标签示例                            标记                层级
==================================  ==================  ================
``一\u00a0虚构主章(…)``            中文数字 + 空白     主章（root）
``(一)\u00a0虚构子章``             中文括号数字        主章的下一级
``1\u00a0虚构子模块``              阿拉伯整数          再下一级
``1.1\u00a0虚构细项``              点分编号            该局部编号下更深层
==================================  ==================  ================

* 主章只接受「中文数字 + 空白」或「中文数字 + 中文序号分隔符」开头的标签；
  ``一虚构主章`` 这类没有分隔符的写法**不识别**，进入待核实。
* 括号子章同时接受全角 ``（）``、半角 ``()`` 以及 ``【】`` / ``[]``。
* 局部编号不是全局 ID：括号子章、数字模块、点分编号都只在自己的**局部章节
  范围**内有效，所以「不同主章 / 不同括号子章下重复 1」合法，
  「同一上级下重复 1」非法。
* 数字模块可以直接挂在主章下面（有主章、但该主章没有括号子章）。
* 点分编号必须能在**同一局部范围**内找到明确存在的直接父编号
  （``1.1`` 需要同范围的 ``1``，``1.1.1`` 需要同范围的 ``1.1``）；缺失即待
  核实，不猜、也不伪造虚拟父节点。
* 父子关系只来自编号层级与章节范围，不依赖 CSS class、不要求学分、不读取
  规则文本，也不推断「所有章节均已完成」或「覆盖完整」。

失败类别（``known=False`` 且进入 ``pending``）
--------------------------------------------
======================================  ==================================
``pending[].code``                       触发条件
======================================  ==================================
``invalid_modules_input``                ``modules`` 不是数组
``invalid_module_report``                单项缺 ``row_index`` / ``label`` /
                                         ``locator`` 或类型不对
``duplicate_row_index``                  ``row_index`` 重复
``row_index_out_of_order``               ``row_index`` 逆序（来源顺序被破坏）
``missing_main_chapter``                 整个范围没有任何明确中文主章（此时
                                         ``profile == "unsupported"``）
``module_without_main_chapter``          范围里有主章，但该数字 / 点分模块出现
                                         在第一个主章之前
``subchapter_without_main_chapter``      括号子章没有可归属的主章
``duplicate_local_number``               同一上级下重复局部编号
``dotted_parent_missing``                点分编号在同一局部范围内缺少直接父编号
``unrecognized_marker``                  标签开头不是任何已知标记
======================================  ==================================

``profile == "unsupported"`` 时 ``pending`` 只作提示，调用方应回退；此时数字
模块不再逐行报 ``module_without_main_chapter``，避免给既有纯数字解析制造噪音，
但括号子章无上级仍会报 ``subchapter_without_main_chapter``。

返回结构
--------
``{"known": bool, "profile": str, "parent_by_row": dict[int, int | None],
"root_rows": list[int], "pending": list[dict]}``

* ``known``：仅当 ``profile`` 为中文主章模式、``pending`` 为空且所有模块都已
  落位时为 ``True``。``False`` 表示**不得**据此推断完成度。
* ``profile``：``"chinese-chaptered"`` 或 ``"unsupported"``。
* ``parent_by_row``：子行 ``row_index`` → 父行 ``row_index``（``None`` 为主章
  root）。无法落位的行**不出现**在这个映射里，而不是被伪造成 root。
* ``root_rows``：主章行号，按来源顺序排列；多主章就返回多个 root，交由调用方
  用 unknown 虚拟根承接，本函数不合并、不补全。
* ``pending``：去重并排序后的待核实项，每项恰好含 ``code`` / ``detail`` /
  ``locator``。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

PROFILE_CHINESE_CHAPTERED = "chinese-chaptered"
PROFILE_UNSUPPORTED = "unsupported"

PENDING_INVALID_MODULES_INPUT = "invalid_modules_input"
PENDING_INVALID_MODULE_REPORT = "invalid_module_report"
PENDING_DUPLICATE_ROW_INDEX = "duplicate_row_index"
PENDING_ROW_INDEX_OUT_OF_ORDER = "row_index_out_of_order"
PENDING_MISSING_MAIN_CHAPTER = "missing_main_chapter"
PENDING_MODULE_WITHOUT_MAIN_CHAPTER = "module_without_main_chapter"
PENDING_SUBCHAPTER_WITHOUT_MAIN_CHAPTER = "subchapter_without_main_chapter"
PENDING_DUPLICATE_LOCAL_NUMBER = "duplicate_local_number"
PENDING_DOTTED_PARENT_MISSING = "dotted_parent_missing"
PENDING_UNRECOGNIZED_MARKER = "unrecognized_marker"

_KIND_CHAPTER = "chapter"
_KIND_SUBCHAPTER = "subchapter"
_KIND_NUMERIC = "numeric"
_KIND_DOTTED = "dotted"

# 中文数字集合（用于主章与括号子章）。
_CHINESE_DIGITS = "零〇一二三四五六七八九十百千两"
# 只认 ASCII 阿拉伯数字，避免 \d 带来的其它 Unicode 数位歧义。
_ARABIC = "[0-9]"
# 单个编号段的长度上限：超长数字不再解释，直接判为无法识别。
_MAX_NUMBER_CHARS = 64

# 主章：中文数字 + 空白，或中文数字 + 中文序号分隔符。
_MAIN_RE = re.compile(rf"^([{_CHINESE_DIGITS}]+)(?:\s+|\s*[、.．。])")
# 括号子章：全角 / 半角 / 方括号包裹的中文数字。
_BRACKET_RE = re.compile(rf"^[（(【\[]\s*([{_CHINESE_DIGITS}]+)\s*[）)】\]]")
# 点分细项：至少两段阿拉伯数字，段间以点相连。
_DOTTED_RE = re.compile(rf"^({_ARABIC}+(?:\.{_ARABIC}+)+)(?=\s|[、,，:：.．]|$)")
# 数字子模块：单段阿拉伯整数。
_PLAIN_INT_RE = re.compile(rf"^({_ARABIC}+)(?=\s|[、.．,，:：]|$)")


def _pending(code: str, detail: str, locator: str | None) -> dict[str, Any]:
    return {"code": code, "detail": detail, "locator": locator}


def _dedup_pending(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (str(item["code"]), str(item["locator"] or ""), str(item["detail"]))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(item))
    result.sort(key=lambda item: (item["code"], item["locator"] or "", item["detail"]))
    return result


def _normalize_number(token: str) -> str | None:
    """把单个阿拉伯编号段规范化为无前导零的十进制文本；超长 / 非法时返回 None。"""

    if not token or len(token) > _MAX_NUMBER_CHARS:
        return None
    try:
        return str(int(token, 10))
    except ValueError:
        return None


def _normalize_dotted(token: str) -> str | None:
    parts = token.split(".")
    normalized: list[str] = []
    for part in parts:
        value = _normalize_number(part)
        if value is None:
            return None
        normalized.append(value)
    if len(normalized) < 2:
        return None
    return ".".join(normalized)


def _marker(label: str) -> dict[str, str] | None:
    """识别标签开头的章节标记；无法识别时返回 ``None``（不猜）。"""

    text = label.lstrip()
    dotted = _DOTTED_RE.match(text)
    if dotted:
        value = _normalize_dotted(dotted.group(1))
        if value is None:
            return None
        return {"kind": _KIND_DOTTED, "value": value}
    bracket = _BRACKET_RE.match(text)
    if bracket:
        return {"kind": _KIND_SUBCHAPTER, "value": bracket.group(1)}
    main = _MAIN_RE.match(text)
    if main:
        return {"kind": _KIND_CHAPTER, "value": main.group(1)}
    plain = _PLAIN_INT_RE.match(text)
    if plain:
        value = _normalize_number(plain.group(1))
        if value is None:
            return None
        return {"kind": _KIND_NUMERIC, "value": value}
    return None


def _pack(
    *,
    known: bool,
    profile: str,
    parent_by_row: dict[int, int | None],
    root_rows: list[int],
    pending: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "known": known,
        "profile": profile,
        "parent_by_row": parent_by_row,
        "root_rows": root_rows,
        "pending": _dedup_pending(pending),
    }


def infer_degree_hierarchy(modules: object) -> dict[str, Any]:
    """从已观测模块报告推断中文主章 / 括号子章 / 数字 / 点分的父子层级。

    参数
    ----
    modules: 模块报告数组，每项含 ``row_index``（int）、``label``（原文本 str）、
        ``locator``（str）；其余字段忽略。函数不修改输入。

    返回
    ----
    dict，恰好五个键：

    * ``known``：层级是否**完整且无歧义**。仅当 ``profile`` 为
      ``"chinese-chaptered"``、``pending`` 为空且所有模块都已落位时为 ``True``。
    * ``profile``：``"chinese-chaptered"`` 或 ``"unsupported"``；后者表示没有
      明确中文主章，调用方应回退到既有纯数字解析。
    * ``parent_by_row``：``row_index`` → 父 ``row_index``（``None`` 为主章
      root）；未落位的行不会出现在映射里。
    * ``root_rows``：主章行号，按来源顺序排列；多主章返回多个 root。
    * ``pending``：待核实项，每项恰好含 ``code`` / ``detail`` / ``locator``，
      已去重并按 ``(code, locator, detail)`` 排序。

    本函数不计算学分、不解释规则文字（最少子组数量 / 任选 / 非必须等）、不推断
    完成度或覆盖完整，也不访问网络。
    """

    pending: list[dict[str, Any]] = []
    parent_by_row: dict[int, int | None] = {}
    root_rows: list[int] = []

    if (
        isinstance(modules, (str, bytes, bytearray))
        or isinstance(modules, Mapping)
        or not isinstance(modules, Sequence)
    ):
        pending.append(
            _pending(
                PENDING_INVALID_MODULES_INPUT,
                "modules 必须是模块报告数组",
                None,
            )
        )
        return _pack(
            known=False,
            profile=PROFILE_UNSUPPORTED,
            parent_by_row=parent_by_row,
            root_rows=root_rows,
            pending=pending,
        )

    parsed: list[tuple[int, str, str]] = []
    seen_rows: set[int] = set()
    previous_row: int | None = None

    for index, item in enumerate(modules):
        if not isinstance(item, Mapping):
            pending.append(
                _pending(
                    PENDING_INVALID_MODULE_REPORT,
                    f"modules[{index}] 必须是模块报告对象",
                    None,
                )
            )
            continue
        raw_locator = item.get("locator")
        locator = raw_locator.strip() if isinstance(raw_locator, str) else None
        if not locator:
            pending.append(
                _pending(
                    PENDING_INVALID_MODULE_REPORT,
                    f"modules[{index}] 缺少非空 locator",
                    None,
                )
            )
            continue
        row_index = item.get("row_index")
        if isinstance(row_index, bool) or not isinstance(row_index, int):
            pending.append(
                _pending(
                    PENDING_INVALID_MODULE_REPORT,
                    f"modules[{index}].row_index 必须是整数",
                    locator,
                )
            )
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            pending.append(
                _pending(
                    PENDING_INVALID_MODULE_REPORT,
                    f"modules[{index}] 缺少非空 label",
                    locator,
                )
            )
            continue
        if row_index in seen_rows:
            pending.append(
                _pending(
                    PENDING_DUPLICATE_ROW_INDEX,
                    f"row_index {row_index} 重复出现，无法确定唯一的文档位置",
                    locator,
                )
            )
            continue
        if previous_row is not None and row_index < previous_row:
            pending.append(
                _pending(
                    PENDING_ROW_INDEX_OUT_OF_ORDER,
                    f"row_index {row_index} 出现在 {previous_row} 之后，来源顺序被破坏",
                    locator,
                )
            )
        seen_rows.add(row_index)
        previous_row = row_index
        parsed.append((row_index, label, locator))

    markers: list[tuple[int, str, str, dict[str, str] | None]] = [
        (row_index, label, locator, _marker(label))
        for row_index, label, locator in parsed
    ]
    has_main = any(
        marker is not None and marker["kind"] == _KIND_CHAPTER
        for _, _, _, marker in markers
    )

    current_main_row: int | None = None
    current_main_key: str | None = None
    current_bracket_row: int | None = None
    current_bracket_key: str | None = None
    main_seen: set[str] = set()
    bracket_seen: dict[str, set[str]] = {}
    numeric_nodes: dict[tuple[str, str | None], dict[str, int]] = {}

    for row_index, label, locator, marker in markers:
        if marker is None:
            pending.append(
                _pending(
                    PENDING_UNRECOGNIZED_MARKER,
                    f"{locator} 的标签开头不是已观测章节标记，保留原值待核实",
                    locator,
                )
            )
            continue

        kind = marker["kind"]
        value = marker["value"]

        if kind == _KIND_CHAPTER:
            if value in main_seen:
                pending.append(
                    _pending(
                        PENDING_DUPLICATE_LOCAL_NUMBER,
                        f"{locator} 在同一上级（章节根）下重复主章编号 {value!r}",
                        locator,
                    )
                )
            else:
                main_seen.add(value)
            parent_by_row[row_index] = None
            root_rows.append(row_index)
            current_main_row = row_index
            current_main_key = value
            current_bracket_row = None
            current_bracket_key = None
            continue

        if kind == _KIND_SUBCHAPTER:
            if current_main_row is None or current_main_key is None:
                pending.append(
                    _pending(
                        PENDING_SUBCHAPTER_WITHOUT_MAIN_CHAPTER,
                        f"{locator} 的括号子章没有可归属的主章",
                        locator,
                    )
                )
                continue
            seen = bracket_seen.setdefault(current_main_key, set())
            if value in seen:
                pending.append(
                    _pending(
                        PENDING_DUPLICATE_LOCAL_NUMBER,
                        f"{locator} 在同一主章下重复括号子章编号 {value!r}",
                        locator,
                    )
                )
            else:
                seen.add(value)
            parent_by_row[row_index] = current_main_row
            current_bracket_row = row_index
            current_bracket_key = value
            continue

        # 数字子模块 / 点分细项都需要一个已开启的中文主章范围。
        if current_main_row is None or current_main_key is None:
            if has_main:
                pending.append(
                    _pending(
                        PENDING_MODULE_WITHOUT_MAIN_CHAPTER,
                        f"{locator} 出现在第一个中文主章之前，无法归属章节范围",
                        locator,
                    )
                )
            continue

        scope = (current_main_key, current_bracket_key)
        nodes = numeric_nodes.setdefault(scope, {})
        container_row = (
            current_bracket_row if current_bracket_row is not None else current_main_row
        )

        if kind == _KIND_NUMERIC:
            if value in nodes:
                pending.append(
                    _pending(
                        PENDING_DUPLICATE_LOCAL_NUMBER,
                        f"{locator} 在同一上级下重复局部编号 {value!r}",
                        locator,
                    )
                )
            else:
                nodes[value] = row_index
            parent_by_row[row_index] = container_row
            continue

        prefix = value.rsplit(".", 1)[0]
        parent_row = nodes.get(prefix)
        if parent_row is None:
            pending.append(
                _pending(
                    PENDING_DOTTED_PARENT_MISSING,
                    f"{locator} 的点分编号 {value!r} 在同一局部章节范围内"
                    f"缺少直接父编号 {prefix!r}",
                    locator,
                )
            )
            continue
        if value in nodes:
            pending.append(
                _pending(
                    PENDING_DUPLICATE_LOCAL_NUMBER,
                    f"{locator} 在同一上级下重复局部编号 {value!r}",
                    locator,
                )
            )
        else:
            nodes[value] = row_index
        parent_by_row[row_index] = parent_row

    if parsed and not has_main:
        pending.append(
            _pending(
                PENDING_MISSING_MAIN_CHAPTER,
                "已观测范围内没有以明确中文主章编号开头的模块，"
                "无法建立章节层级；调用方应回退到既有纯数字解析",
                parsed[0][2],
            )
        )

    profile = PROFILE_CHINESE_CHAPTERED if has_main else PROFILE_UNSUPPORTED
    pending_sorted = _dedup_pending(pending)
    known = (
        profile == PROFILE_CHINESE_CHAPTERED
        and not pending_sorted
        and len(parent_by_row) == len(parsed)
    )
    return _pack(
        known=known,
        profile=profile,
        parent_by_row=parent_by_row,
        root_rows=root_rows,
        pending=pending_sorted,
    )
