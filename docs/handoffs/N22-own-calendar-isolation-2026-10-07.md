# 本人日历与课表归属交接（2026-10-07）

## 不可改变的归属规则

- 访问名单是“谁可以使用 Agent”；它不决定日历数据属于谁。
- 数据归属取自后台验证过的 CloudBase 登录 subject。网页 Cookie 与 Agent OAuth grant 分别验证；前端/模型不得通过学号、user_id、owner_subject_id、workspace_ref 选择他人数据。
- 两人必须使用各自的 CloudBase 账号（现有 A/B 两个批准账号）。共用同一账号就是共用同一身份，不能靠不同学校聊天页面假装隔离。插件不能配置共享的固定用户 Bearer。
- 课表继续使用现有 owner workspace 校验。保存、当前课表、任务列表、冲突/空档计算均仅能读取已验证身份的记录。真实课表上传仍未接通，不应拿公开课表夹具冒充本人真实课表。
- 新增待办按稳定 `owner_subject_id` 保存，不依赖 24 小时演示工作区。重登录、重启或工作区更新后仍属于原账号；不自动搬到另一个账号。
- 单个提醒点和截止日期不占用忙碌区间；只有已选的实际安排时段才参与冲突计算。多段安排全部参与，完成/取消后不占用。

## 实现与接口

在现有 `nku_task_calendar_v1` 中新增 `entry_drafts`、`entries`、`entry_idempotency`，主键均包含 owner。仅固定 `public.nku_personal_tasks_v1_rpc` 后台操作可访问；匿名/普通前端角色没有表或函数执行权限。

浏览器接口（Cookie + Same-Origin，写操作要求 CSRF）：

- `POST /api/v1/tasks/entries/drafts`：`{content, idempotency_key}`。
- `POST /api/v1/tasks/entries/commit`：`{draft_id, payload_hash, confirmed: true, idempotency_key}`。
- `GET /api/v1/tasks/calendar?workspace_ref=本人工作区`：重新读回本人列表。
- `POST /api/v1/tasks/{task_id}/calendar`：原接口更新本人状态/提醒；不允许旧单区间界面覆盖多段安排。

`content` 允许标题、kind、due_at/due_date、reminder_at、notes、scheduled_slots（最多 8 段）、reminder_minutes。不需要 estimated_minutes，也不强制结束时间。草稿需用户核对后明确确认，成功响应必须 `saved=true` 且 `readback_verified=true`。记录成功不代表做过冲突检查（`conflicts_checked=false`），不代表推送已实现（`background_push=false`）。

Agent 候选接口：`GET /oauth/tasks/entries`、`POST /oauth/tasks/entries/drafts`、`POST /oauth/tasks/entries/commit`。POST 使用唯一 `query_json` 字符串包装。新增权限为明确重新授权的 `demo:read tasks:read tasks:write`；旧 `demo:read` 不自动升级，`tasks:read` 不能写。

## 已验证与边界

本地真实嵌入式 PostgreSQL + HTTP 测试使用虚构身份，不是线上 A/B 验收证明。5 项专项测试覆盖：跨账号读写/草稿提交拒绝、伪造归属拒绝、A grant 在浏览器登录 B 后仍绑定 A、旧授权不升级、CSRF、退出后失效、按 owner 幂等、重启与工作区更新后的稳定归属、多段忙碌区间及提醒点不占时间。

原有课表/OAuth/通知/日历回归已通过（有原测试主动跳过项），打包 6 项通过。前端账号切换测试通过：回到页面先隐藏旧账号数据，再核验当前 Cookie；原有前端测试及多时段/提醒点显示测试通过，TypeScript 检查和 Vite 构建通过。

云端已安装两项增量迁移，并经 SQL 控制台核验：三表 RLS=true，匿名执行=false，普通前端角色执行=false，后台执行=true，扩权旧 grant 数=0，批准账号数仍为 2。未读取个人记录或令牌。

候选包 `cloudbase-identity-pilot-20261007-r18.zip`：SHA256 `dc390716006137d532cc66e3f430f0cc2f03a51e656abd2f543101a1e2a998c0`，186 文件，不含私有配置/密钥/用户数据。现有服务部署 018、任务 2299233 已于 11:37:25 提交，部署详情已显示“正常”。没有调整资源规格或访问名单。

内置浏览器访问 `/healthz` 被浏览器以 `ERR_BLOCKED_BY_CLIENT` 拦截（页面明确显示“此页面已被 ChatGPT 屏蔽”），未绕过拦截。这不是服务返回的 503。随后经腾讯云运行日志确认：11:39:57 Application startup complete，11:41:51 `/healthz` completed，build=`cloudbase-identity-pilot-20261007-r18`，status=200，elapsed_ms=229。该日志证明新版本启动与健康检查成功，不能代替线上 A/B 读写验收。部署正常截图：工作区根目录 `own-calendar-isolation-deploy-20261007.png`；数据库权限核验截图：`own-calendar-isolation-db-20261007.png`；健康日志截图：`own-calendar-isolation-health-20261007.png`。仍需在正常可访问的浏览器完成两账号端到端验收。

## 14:50 补充：线上联调已完成部分

- 插件已保存明确扩权 scope `demo:read tasks:read tasks:write`；三个新工具实际调试通过并发布，主 Agent 草稿实际绑定。A/B 分别重新授权，没有共享固定用户令牌。
- A 的无工作区间 DDL 记录实际确认保存，`saved=true/readback_verified=true`，task ID `entry_Sz5Z9cOmqTlvXFMquqql2aQq`。重登录和部署更新后前端仍只有 A 记录。
- B 初始读回列表为空，未看见 A。主 Agent 实际生成 B 提醒草稿，另一轮明确确认后保存并读回，task ID `entry_KkNN4u8dEcPRX9vatrApexGd`。B 前端刷新和“查看全部”仍只见 B 提醒；A 重登录不见 B。提醒无结束时间，未声称后台推送。
- 原九月夹具保留；将已有 `timetable-october-2026.simulation.json` 的固定虚构内容增量加入精确哈希白名单，覆盖 10 月 5 日起四周。没有接个人截图或任意上传。哈希 `fb19120effa0c46f1af0523ec58f6fced45e97fd5aa8edcc97310cd635c5b0b8`。新增种子首次经终端输出出现中文编码问题，已用 JSON Unicode 转义修复这一个新种子，并在控制台和课表页核验中文正确。
- A 课表保存为原 schedule `schedule_B_CGKn3ecTj9LDaEypFfWqX7` 版本 2；B 独立新 schedule `schedule_GPIeD41DUdF_tVZIt887kcfl` 版本 1。两份内容相同但 owner 和数据库记录独立。
- r19 修复 OAuth 回程允许明确批准的三个 scope 组合；r20 包已部署正常，版本 020 / 任务 2300245。包 SHA256 `51ef5a831e2d9f3f078fc0a95b1d07fcd761290ac015c4cbbe0a217186e9a1c0`，187 文件，无私有配置/密钥。资源规格与环境密钥不变，仅更新 BUILD_ID。
- 主 Agent v0.2.9 配置发布成功；原 Web 渠道名单仍为孙佳兴、傅思敬。14:46:10 已提交渠道更新，工单 `db2ulca2to1aki72sd6g` 当前审批中。此时不能把旧用户端 v0.2.8 当新版验收，不能代审批或重复申请。
- 本轮 October/打包测试 19 项通过，OAuth/登录/账号切换前端 28 项通过，三工具契约 6 项通过；TypeScript 和 Vite 构建通过。待继续实际用户端多时段保存和既有安排空档扣除验证。

未做 Git commit/push/PR 更新。后台推送未接通；静态开场白不能自动请求个人摘要。部署包中的原始迁移只供首次安装，不得重跑旧建表脚本。本轮种子迁移只修复上述新增固定哈希，不改变旧数据、RLS、访问名单或身份归属。

## 15:00 补充：正式用户端跨轮确认修复

- v0.2.9 工单 `db2ulca2to1aki72sd6g` 已于 14:50:05 通过，Web 服务已实际运行 v0.2.9。
- 在正式用户聊天页（不是编排调试页）读取 A 自己记录、查询虚拟课表空档，生成两段 DDL 作业草稿。首次下一轮提交得到 `NOT_FOUND`；未宣称保存成功。用户聊天历史不保证保留隐藏工具回执，模型随后明确无法取到上一轮真实 ID/hash。
- 实际重新生成同内容草稿并展示真实回执，下一轮确认保存成功，另一次查询读回成功；刷新前端显示 A 未完成 2 条，10 月 8 日该项“共 2 段”（09:00—10:00、14:00—15:00），10 月 9 日显示截止时间。截图 `calendar-own-a-two-ranges-20261007.png`。这证明真实保存链路，不能把第一次失败当成通过。
- v0.2.10 修正为草稿清单后显示真实 `draft_id` / `payload_hash` 核对回执（不是认证令牌，仍需本人身份才能提交），用户只回复确认，不需复制。取不到回执则重新生成并重新确认，不能猜 ID。限定“只某一天”查询不扩大到其他日期。
- v0.2.10 配置已发布，15:00:20 提交原 Web 渠道，工单 `db2us15r805t2j8d4m40` 当前审批中。访问名单、其他渠道开关不变；待通过后在全新正式会话验收默认草稿/确认流程，不能把 v0.2.9 临时恢复流程当最终版本验收。
- 本轮隔离专项 5 项重新通过（嵌入式 PostgreSQL+HTTP），三工具契约与跨轮回执回归 7 项通过。受限环境首次嵌入式进程未启动，已中止并在本地允许的测试环境复跑成功；不是线上故障。
- 正式用户端随后仅查询 10 月 8 日空档，实际结果为 08:00—09:00、15:00 后到睡觉前；已保存 09:00—10:00 和 14:00—15:00 两段均扣除，课表 10:10—11:50 和午休 12:00—14:00 排除。未修改记录。覆盖状态仍 unknown，只证明当前固定虚构课表与本人已有安排参与计算。
- 日历详情实际显示两个完整区间与 DDL，提醒选项仍为“不提醒”。ICS 导出在内置浏览器未取得下载事件，不能把点击按钮当作已验收下载；页面提醒/ICS 与关闭页面后的后台推送是不同能力。

## 15:05 审核通过

v0.2.10 工单 `db2us15r805t2j8d4m40` 已于 15:05:05 通过。渠道页面实际显示 Web 服务“运行中 v0.2.10”，API/MCP/WebSDK 仍停用，原两人名单未改变。上线截图 `calendar-genios-v0210-approved-20261007.png`。继续在全新正式会话验证，不代替管理员审批，没有重复申请。

## 15:09 最终用户端验收

- 新建正式用户会话，普通输入“记一条虚构验收待办……只记录DDL……核对后再保存”，未教模型调用工具。会话/授权正常过期时以原账号、原范围重新登录与授权，没有延长期限。
- 新版默认回复已实际生成草稿，展示真实回执 `entry_draft_1hAiGQg-mJ1tq0ecJcgm1oRi` / `c7ea5b1fe30b24d13d4a81a05447d6a9105c711a0634b6cbd5a852a5e2bd27d9`。下一轮仅输入“确认保存”，实际保存成功；独立只读查询返回 task ID `entry_1s35-A2gBAQoAoHyt3ymgUOL`、pending、未完成总数 3。
- 前端刷新、查看全部显示第三条“新版用户端验收：虚构作业”，只有截止时间，没有强制结束时间；原两段安排仍存在。截图 `calendar-own-a-v0210-final-20261007.png`。课表重登录后仍读回 A 的版本 2；截图 `calendar-own-a-virtual-ready-20261007.png`。
- 浏览器仅保留正式 Agent、本人日历、本人虚拟课表三个体验页。没有删除任何历史会话或验收事项。
- 学校登录允许进入 Agent；数据身份仍取自分别授权的 CloudBase A/B，不是按学号匹配，共用测试账号会共用同一数据身份。授权过期需正常恢复，已保存待办不会因此移到别人账号或被抹掉。课表仍属于原有短期演示空间，未延长其期限，未上传个人课表截图。
- 本次不提交 GitHub PR，不修改现有 PR。后台推送、关闭页面后提醒、无用户交互自动读取开场摘要、内置浏览器 ICS 文件下载仍不应声称已验收。
