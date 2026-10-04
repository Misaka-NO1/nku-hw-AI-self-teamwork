# D07 通知提取与时间检查：2026-10-03 实际证据

## 范围与状态

继续负责人授权的团队草稿联调，只使用三份仓库固定公开虚构通知。未公开发布主 Agent，未修改公共契约、个人权限、旧云服务或数据库，没有新增购买和 Git 提交。

学校页面本次多次会话到期：重新打开主 Agent 页后进入统一认证，使用现有飞连一键登录恢复，再刷新工作流继续。成功恢复不等于所有 503 都是登录问题。通知模型执行已经恢复；后续时间插件错误来自 MCP initialize，分别记录。

## 通知预览工作流

- 名称：`WF_NoticeDraft_v1_Test`。
- ID：`db0an354shhbpg8v4or0`；16:47:39 已发布团队测试版本0.1.0，并绑定主Agent草稿；不是公开发布主Agent。
- 五节点四边：Start → 固定来源代码 → 模型 → 严格校验代码 → End.result。
- 模型：doubao-seed-2-0-mini，JSON 模式；取 raw_output，不使用 reasoning_content。
- 代码、提示词和映射见 `deploy/genios-workflows/README-notice.md`。刷新后五节点、输入输出和最近实际运行仍在。
- 所有输出明确 `saved=false`；没有 database draft_id、task_id 或确认票据。

### 实际运行（保留失败，不把平台绿勾当业务成功）

| 测试 | 实际结果 |
| --- | --- |
| 初次活动 | 模型误填预计耗时 60 分钟，校验拒绝，notice=null、query 为空、未保存 |
| 修改活动/任务耗时提示后 | 活动 start/end 正确，estimated_minutes=null，预览通过 |
| 初次相对日期 | 无 published_at 的“本周五”被模型猜为 9 月 18 日，校验拒绝 |
| 强化相对日期提示后 | 日期不再猜测，但模型漏报两项必要确认，旧严格版本拒绝 |
| 确认策略确定性派生后，相对日期 | needs_confirmation，日期时间均 null；恢复 publication_reference、due_time、estimated_minutes 三项，记录模型遗漏两项；不生成时间请求 |
| 未知 unknown-notice | 93ms / 0 Tokens；代码01停止，模型和后续节点未执行 |
| 最新活动回归 | 9076ms / 2171 Tokens；validated_preview，13 字段、证据和时间正确，confirmation_policy_applied=true，无遗漏，未保存 |
| 最新截止回归 | 16963ms / 3153 Tokens；due=2026-09-21T10:10:00+08:00，estimated=20，earliest=09:40，validated_preview，无遗漏，未保存 |

必要确认项由可信代码策略派生，不允许模型减少操作保护。模型必须提供合法唯一字符串数组，未知项、重复项、字段缺失仍拒绝；其他 12 个观察字段严格核验，不能修坏 JSON、猜日期或补证据。这是闭合集的验收器，**不是通用真人通知提取器**。

## 独立时间检查工作流

`WF_D07_NoticeTime_Test`，ID `db0boqd4shhas0akgb8g`，从 D06 复制；原 D06 未修改。副本16:52:39已发布团队测试版本0.1.0，并绑定主Agent草稿。

四节点三边：Start.fixture_id → `notice-time-fixture-handler.js` → `campus-tools-dev/platform_check_time_plan` → End.result 引用 structuredContent。只接受 event/deadline 两个完整通知 ID；模糊、未知及错误类型在代码节点拒绝。query_json 单次序列化直连；isError 校验开启、异常忽略无。它使用固定演示工作区，不读取个人课表。

副本标题和描述已通过工作流列表的更新界面改为D07通知时间检查，刷新读回通过。此副本独立验证确定性时间参数，不是已把模型输出自动串成个人写入闭环。

首次活动调用：2026-10-03 16:32:50–16:33:51，代码成功 68ms，插件失败 60366ms，End 未执行。日志明确：`Internal.McpClient`，调用 initialize 时 `broken session: 503 Service Unavailable`。失败保留，不算业务验收通过。

刷新工作流后相同活动重试 **456ms成功**，插件274ms：ok=true，event_conflict，两处交集09:20–09:40及10:10–10:20，request_id=`66c66a36-03f9-4a14-9ad9-f91773967942`。本次MCP broken-session错误可经重开重试恢复，不证明其他云503相同根因。

截止通知 **567ms成功**，插件297ms：deadline_feasibility，候选09:40–10:00、20分钟，request_id=`361113f0-a3aa-4cbc-b641-ffd609aefd6e`。两个结果均保留DEMO_DATA、calendar_not_official与coverage.completeness=unknown，不冒充真实完整课表。

模糊通知86ms、未知通知84ms在代码01失败，插件和End未执行。重复截止测试期间学校又会话到期（Network Error），重新飞连登录恢复；该次不算成功。恢复后重载再运行451ms成功，09:40–10:00候选和20分钟不变，返回新的request_id=`66b808c3-3f92-418c-a60b-1b89f324fc54`。腾讯云只读核对旧MCP005正常、100%流量、1实例，未改配置或读取密钥。

## 主Agent实际调用

通知预览0.1.0绑定后，追加D07固定夹具、待确认、不保存、不猜日期和个人身份限制，其他提示词内容保留。主Agent实际输入fixture_id=notice-ambiguous.demo，调用记录可见WF_NoticeDraft_v1_Test，原始Output为needs_confirmation、三个必要项、saved=false、time_check_ready=false、model_confirmation_omissions两项；最终回答保留自创测试通知03原句，未查个人课表或声称已保存。19.927s/15547Tokens；不只依据模型口述判断成功。

主Agent未知标识测试16:52:24结束，6.411s/6033Tokens，实际执行被UNKNOWN_FIXTURE拒绝，未用历史成功结果兜底。平台目前展示通用执行错误及代码栈；这是拒绝行为证据，不是已经完成友好错误界面的证据。

时间工作流绑定后，追加先取得本次validated_preview且time_check_ready=true、再检查同一fixture_id的草稿编排约束。16:54:40主Agent实际完成notice-event.demo连续两次调用：通知预览6.38s（工作流4.89s），时间检查1.78s（工作流0.47s），完整回答21.135s/30015Tokens。逐项查看两个原始Output：活动09:20–10:20、estimated_minutes=null、来源原句准确、预览validated_preview、time_check_ready=true、saved=false；随后真实时间结果ok=true、event_conflict，交集09:20–09:40及10:10–10:20，request_id=`0e53c943-64ea-4ceb-a6ef-782c0f16d211`。最终回答保留demo、周1–4和完整性unknown限制，没有读取个人课表或声称保存。

此顺序是Agent草稿策略的本次实际验收，不是服务器强制的通用条件事务：时间工作流仍从已知fixture_id确定性构造固定请求，未直接接收任意模型通知输出。当前主Agent保留原7个插件，绑定4个工作流（StudyAnswer、D06、NoticeDraft、D07NoticeTime）；原提示词规范化前缀核对一致，测试前草稿保存时间16:54:11。最后主动刷新后四工作流与两段D07约束仍在，原提示词规范化前缀再次一致，页面显示保存时间17:03:54。主Agent未公开发布。

## 本地回归

- Node 通知 handler：206 项断言通过。
- Node 时间 handler：14 项断言通过。
- Python NoticeDraft 契约夹具 + tasks_site：5 例通过，保留第三方 anyio 弃用警告。
- 本地回归未调用学校模型或云数据库，不替代平台实测；未复跑全量后端/前端。

## 截图与剩余项

截图在忽略目录 `dist/d07-local-20261002/`，包括初次耗时拒绝、相对日期拒绝、确认遗漏拒绝、最新待确认通过、未知标识模型前停止、最新截止回归与 MCP initialize 503。主Agent连续实测截图：`notice-agent-extract-time-passed-20261003.png`。

尚须：通用通知提取及服务端强制条件门禁、可信身份下的数据库草稿和受控用户确认写入；不能把固定夹具验收直接放宽到真人通知。个人写入依然需要合格逐用户授权，OAuth协议缺口未解决前不能使用SYS_USERID或共享服务令牌冒充身份。云身份默认域名503与本次学校/MCP会话恢复是独立问题；正式培养方案与事务内容仍需批准来源。主Agent未公开发布，D07整体尚未完成。
