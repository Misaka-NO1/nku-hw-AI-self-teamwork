# D07 固定虚构通知提取工作流

学校团队草稿 `WF_NoticeDraft_v1_Test`，工作流 ID `db0an354shhbpg8v4or0`。只接三个公开虚构夹具标识，不接真人通知、任意 URL、文件路径、凭证或个人身份。不修改公共契约、A/B/C 算法或旧云服务。

## 配置

```text
Start.fixture_id (String, required)
  → 代码01：notice-fixture-handler.js
      fixture_id ← Start.fixture_id
      fixture_id (String), model_input (String)
  → 大模型01：doubao-seed-2-0-mini，JSON 输出
      model_input ← 代码01.model_input
      系统提示词 ← notice-extract-system-prompt.txt
      用户提示词 ← notice-extract-user-prompt.txt
  → 代码02：notice-preview-guard.js
      fixture_id ← Start.fixture_id
      extraction ← 大模型01.raw_output（不使用 reasoning_content）
      query_json (String), result (Object)
  → End.result (Object) ← 代码02.result
```

三份来源文字分别与 `fixtures/notice-{event,deadline,ambiguous}.demo.json` 的证据逐字一致。模型输入包含受控元数据和原文，不包含预期答案；代码02与原夹具比较全部观察字段（忽略对象键顺序，但不忽略数组顺序或字段缺失）。这是**闭合集的语义验收器**，不是通用通知提取器；未知ID在模型执行前拒绝。

`needs_confirmation` 是代码策略派生字段，不由模型授予操作权限。模型仍须提供唯一字符串数组，不得带未知项；允许遗漏必要确认项，但校验器在全部观察字段通过后按可信固定夹具恢复完整必要项，记录 `model_confirmation_omissions`，并显式输出 `confirmation_policy_applied=true`。这不是补日期、改原文、修坏JSON或默认成功：猜出的日期、错误活动耗时、来源/字段错误仍被拒绝。缺参照通知始终不生成时间请求、不保存。

模型输出即使是合法 JSON 或平台绿勾，也必须通过原文、字段、时间、待确认项校验。重复键、Markdown包裹、增加字段、字符串null、捏造耗时/日期/来源均拒绝。失败不展示不可靠通知，不生成时间请求，不保存任务。

缺发布日期的相对日期不能以提取时间或今天作参照；活动时长不是截止任务预计耗时。输出 `saved=false` 是能力边界，不是失败被悄悄修成成功。没有数据库 draft_id/task_id、确认票据或业务 request_id，不得自造这些字段。

## 本地检查

```powershell
node deploy/genios-workflows/test-notice-handlers.cjs
# backend 目录：
.venv/Scripts/python.exe -m pytest tests/test_contracts.py::test_d_owned_notice_fixtures_match_shared_core_contract tests/test_tasks_site.py -q -p no:cacheprovider
```

Node 当前206项断言通过；Python当前5例通过，保留第三方 anyio 弃用警告。所有合法结果与共享 NoticeDraft 契约夹具及两份 TimeCheckRequest 夹具相同。本地测试没有调用模型、学校平台、真实账号或云数据库，不能当平台验收。

## 尚未完成的部分

当日平台实际证据见 `docs/evidence/platform/D07-notice-extraction-2026-10-03.md`。最新活动、截止预览通过；模糊日期维持待确认，未知标识在模型前停止。独立时间工作流 `WF_D07_NoticeTime_Test`（`db0boqd4shhas0akgb8g`）以确定性参数直连现有时间插件；首次MCP initialize 503保留为失败，刷新重试后活动/截止检查、重复截止及未知/模糊拒绝均实际通过。本地时间handler14项断言通过。原D06保持不变；两个新工作流发布团队测试版本0.1.0，并绑定主Agent草稿，未公开发布主Agent。

- 当前草稿最终结果只为通知预览；`query_json` 仅确定性准备时间请求，不代表执行了时间算法。
- 主Agent已实际完成模糊通知待确认、未知标识拒绝，以及活动通知先提取再检查的两工作流调用；原始Output、来源与真实request_id逐项核对。平台实测与本地回归须分开表述。
- 仅在 `time_check_ready=true` 时进入后续时间检查，缺项保持待确认，不把活动/截止互换。当前这是主Agent草稿编排策略，时间工作流根据同一固定ID构造规范请求，不是直接传入任意模型输出或服务器强制的通用事务门禁。
- 可信个人授权未通过前，不在学校建立个人数据库草稿，不使用 SYS_USERID 或共享令牌冒充身份。通用通知写入需要另行设计及验收，不能放宽现有固定夹具门禁。
- 用户的最终确认仍在受控页面；模型不能签确认回执。主 Agent 未发布，不宣称D07整体完成。
