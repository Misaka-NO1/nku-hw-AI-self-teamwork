# 培养方案知识库状态

- 当前只有 `fixtures/degree-plan.demo.json`（虚构演示规则，不是南开培养方案）。
- 真实培养方案（一个专业、一个年级、一个版本）尚未收集，规则核验表未建立：见 `docs/blockers/C-02-degree-plan.md`。
- 正式文件到达前，`audit_degree_progress` 对 `status=needs_verification` 的计划一律返回 `needs_policy`，不硬算。
