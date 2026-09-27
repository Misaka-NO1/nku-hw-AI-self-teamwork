# 培养方案知识库状态

- 演示规则：`fixtures/degree-plan.demo.json`（虚构，不是南开培养方案）。
- 真实方案：计算机科学与技术 2025 版已收集（教务系统截图），规则核验表见
  `cs-2025/plan-rules.md`；整体状态 needs_verification，缺口清单见
  `docs/blockers/C-02-degree-plan.md`。
- 正式文件补齐前，`audit_degree_progress` 对 `status=needs_verification` 的计划
  一律返回 `needs_policy`，不硬算。
