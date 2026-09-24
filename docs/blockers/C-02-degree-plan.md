# C-02 阻塞：真实培养方案缺失（WAITING_HUMAN）

状态：WAITING_HUMAN（不阻塞规则内核与 demo 测试）

C08 要求收集“一个专业、一个年级、一个版本”的正式培养方案并制作规则核验表。
当前仅有虚构夹具 `fixtures/degree-plan.demo.json`。

需要人工提供：

1. 一份正式培养方案文件（含专业、年级、版本号）。
2. 规则核验表：每条规则（必修集合、模块最低学分、跨模块归属优先级、重复修读政策）
   标注原文位置（页码/条目）。
3. 无法确定的规则保持空白，由规则引擎返回 `needs_policy`，不得擅自填默认值。

文件到位前，`audit_degree_progress` 对 `status=needs_verification` 的计划拒绝硬算。
