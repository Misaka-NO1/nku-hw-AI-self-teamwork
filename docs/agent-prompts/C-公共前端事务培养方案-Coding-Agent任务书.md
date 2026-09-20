# C 任务书：公共前端、校园事务与培养方案

> 这份文件是给 Coding Agent 的完整任务说明。交给 AI 后，AI 负责搭建公共前端、共享组件、校园事务页面、培养方案规则和测试。人员本人不需要会写代码。

## 直接交给 Coding Agent 的开场指令

```text
你是本仓库的 C 模块 Coding Agent。

我不会写代码，请你直接完成任务，不要只给我教程或代码片段。你需要自己检查仓库、创建和修改文件、运行测试，并在最后告诉我真实结果。

开始前先阅读：
1. README.md
2. contracts/integration-conventions.md
3. contracts/api.schema.json
4. 本文件全部内容

如果没有真实校园来源、培养方案或政策文件，不要编造。使用明确标记的 demo 模板，记录 WAITING_HUMAN，并继续完成公共前端和规则测试。

现在开始执行 C01 到 C07，完成后再根据实际资料继续 C08 到 C12。
```

## 你的角色

你负责统一前端外壳、公共组件、校园事务导航、课程目录和培养方案规则。

你不负责地图、复习资料正文、课表解析、时间算法、数据库、MCP 或平台发布。

## 允许修改的范围

```text
frontend/src/app/
frontend/src/shared/
frontend/src/features/affairs/
frontend/src/features/degree/
knowledge/affairs/
knowledge/courses/
knowledge/degree/
backend/app/domains/degree/
对应测试
docs/handoffs/C-progress.md
docs/blockers/C-*.md
```

## 公共前端必须完成

统一导出以下组件：

```text
ScenicPage
StudyPage
ImportPage
TimetablePage
TasksPage
AffairsPage
DegreePage
```

公共组件至少包括：

```text
SourceCard
StatusBanner
LoadingState
EmptyState
ErrorState
ConfirmSummary
```

前端 API client 必须统一使用 `VITE_API_BASE_URL`，不得使用 `APP_API_BASE`，不得让每个功能自己写一套 fetch 逻辑。

前端字段转换规则：

```text
后端 request_id → StatusBanner 的 requestId
后端 snake_case → 前端内部 camelCase
```

所有接口错误都必须显示清楚的错误信息和 `request_id`，不能把失败显示为成功。

## 校园事务要求

实现 `AffairsPage`，支持分类搜索、来源展示、适用范围、登录限制、校园网限制、办理步骤、过期和待核验提示。

没有正式来源时必须标记待核验，不得把第三方帖子写成学校规定。

## 培养方案要求

实现纯函数：

```python
audit_degree_progress(plan, records)
```

公共接口不接收任意成绩记录，D 会通过 `transcript_ref` 解析出允许使用的 records。

审计结果必须统一为：

```text
plan_id
plan_version
source_ref
modules[]
  module_id
  earned_credits
  required_credits
  remaining_credits
  missing_required_courses
  counted_attempts
  excluded_attempts
unallocated_courses
unresolved_rules
data_coverage
status
```

状态只能使用：

```text
complete_under_supported_rules
incomplete
needs_policy
```

计算要求：

- passed 才能作为已完成候选
- failed、in_progress、unknown 不计入已完成
- 重复课程按明确的 repeat_policy 去重
- 一个课程默认只能计入一个模块
- 没有归属规则时返回 needs_policy
- 使用 Decimal 计算学分
- 结果不能表述为“保证毕业”

## 测试要求

至少完成：

```text
SHELL-01 所有工具页可刷新
SHELL-02 401/403/422/503 显示正确错误
CAMPUS-01 无正式来源时不编造流程
CAMPUS-02 不混用不同校区和人群规则
COURSE-01 同名课程不错误合并
DEGREE-01 重复通过记录只计一次
DEGREE-02 failed/in_progress 不计完成
DEGREE-03 学分够但缺必修仍显示缺口
DEGREE-04 无模块归属规则返回 needs_policy
DEGREE-05 计划版本不匹配时拒绝硬算
DEGREE-06 demo 夹具结果与预期一致
```

## 完成后的汇报格式

在 `docs/handoffs/C-progress.md` 写入：

```text
任务状态：LOCAL_PASS / WAITING_HUMAN / 未完成
修改文件：
页面和组件导出路径：
公共 API client 配置：
培养方案函数输入输出：
测试命令：
测试实际结果：
待核验校园来源：
给 A 的下一步：
给 B 的下一步：
给 D 的下一步：
```
