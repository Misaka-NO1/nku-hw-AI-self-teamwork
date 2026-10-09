# A/B/C 接口同步：D 的逐用户 OAuth 候选

## 2026-10-04 13:47 更新：截止字段已修复并实际验收

主Agent本人截止检查20分钟/最早09:40实际Input与Output一致，真实candidate_slots为09:40–10:00，request_id=692e167f-79e8-42b4-a671-b9e18afd57f4。学校输出定义补齐candidate_slots并保留conflicts；修改后活动回归真实两交集，request_id=684b0723-a81b-43fe-b7b9-9c850c7a0b86。日期仅精确到天且耗时未知时返回空列表与due_time/estimated_minutes待确认，request_id=a61c5fd0-7187-464e-99a0-5f0a4c75624a；不补23:59或借历史耗时。此前输出字段遗漏导致的猜测回复不计入通过，失败记录保留在D11。

现有固定虚构数据链路通过不代表真实教务或全部功能成品。主Agent仍未发布；平台发布渠道提示须先发布配置，尚未执行。不同学校用户评委入口、数据库Key跨当日18:21:48续期仍需负责人明确授权；未整体验收不提交Git。后端013/r12、SQL、权限和密钥保持原样。

## 2026-10-04 13:12：学校与主Agent本人只读链路已验收

三项已发布工具read_my_demo_records(GET /oauth/records)、find_my_demo_free_slots(POST /oauth/time/free-slots)、check_my_demo_time(POST /oauth/time/check)已绑定主Agent草稿。两个POST仍只有query_json字符串、禁止owner/workspace输入；活动event.start/end不可遗漏。A/B本人记录、退出401、自然问法空档与活动检查真实通过，证据与request_id见[D11](../evidence/platform/D11-all-features-integration-2026-10-04.md)。仅两测试账号虚构数据、demo:read，无写工具、真实成绩或公开主Agent；接口/schema/TTL不变，Key18:21:48到期。

## 2026-10-04 12:06：学校OAuth本人读回已通过

013/r12正常100%流量，精确学校callback与Origin校验保留。学校read_my_demo_records实际读回A原课表/两条待办，request_id=e0337a78-26b8-4bc4-b07b-f5d332800433；本人空档370分钟/coverage unknown，request_id=43b690ce-d31b-4ba5-b460-b5ace89f3c49。新增find_my_demo_free_slots、check_my_demo_time只接受query_json字符串，owner由grant决定，禁止workspace_ref/user_id/课表/令牌。新增工具仍调试中，B学校隔离与主Agent绑定待验。下文不兼容/未读回为历史，最新以[D11](../evidence/platform/D11-all-features-integration-2026-10-04.md)为准。

## 2026-10-04 最新：011整合与C草稿实测

011/r10已正常100%流量，校园事务/培养方案导航与固定公开demo审计上线；API契约和原owner算法不变。
C新增两项官方后勤摘要和5门虚构课程/2卡知识库绑定草稿，正反例通过；学分字段为 transcript_ref，不是 transcript_id。
学校会话恢复；A到OAuth同意页，后续 /oauth/approve 在内置浏览器被屏蔽，尚未兑换/读本人或发布个人插件。
正式成绩/培养方案仍不开放；其他服务保留，无新SQL或长期Key。详见[D11](../evidence/platform/D11-all-features-integration-2026-10-04.md)。

## 2026-10-04：参赛演示兼容已部署010，学校端仍待实调用

负责人批准具体切换后，三表迁移已执行、旧15表保留；010/r9正常100%流量，OAuth兼容开启。
学校会话已过期进入统一身份认证，不能把部署正常当逐用户授权通过。
追加全功能候选补齐校园事务/培养方案入口与既有固定公开demo审计；不新增成绩权限或owner记录。
该追加候选尚未部署。公共地图/资料服务不变；短期后台Key不自动延期；未提交Git/PR。

## 2026-10-03：负责人选择参赛演示兼容模式

学校实际仅发 client_id/redirect_uri/response_type/scope/state（10 字符 state，无 PKCE）。
独立默认关闭开关支持普通保密客户端授权码，不填假 challenge、不覆盖严格提供方。
新 nku_competition_oauth_v1 三张授权表/后台固定 RPC；仍须在线核验两测试账号并本人同意，
码最长120秒一次性、Bearer最长600秒且受来源会话约束；退出/撤销立即失效，只有 demo:read。
A：公开地图/复习资料服务不变；B：owner records/时间算法不变，模型不确认/保存；
C：正式培养方案、真实成绩仍未开放，缺规则仍 needs_policy。
此候选已同步 api.schema.json、oauth-pilot.demo.json、实际嵌入 PG HTTP 正反例及登录返回测试。
需要线上具体启用确认和学校端实调用后，才能声称“参赛链路能用”；不要求先验收生产级认证。
下文严格 PKCE 门槛保留给原模式/未来正式个人数据上线，不再作为本次虚构演示前提。

补充：已实现云 PostgreSQL 存储及独立 HTTP/OAuth 候选；002 身份版已部署正常并承接 100% 流量，OAuth 仍关闭、云业务与学校未实际验收。
复用同一组 OAuthPilot schema/正反例和业务路径，不让 Agent 确认/提交；
数据层含 15 张隔离表、固定 service_role RPC、共享限流与事务性确认/幂等。
自动 HTTP 验证使用实际 PGlite PostgreSQL，但 CloudBase 身份核验 mock、单连接，
不代表腾讯云双连接并发或学校 PKCE/逐用户授权已经验收。
部署源与权限边界见 [云身份候选](../../deploy/cloudbase-identity-pilot/README.md)。

2026-10-02：D 新增默认关闭、loopback/test-only 的 OAuth 授权码适配器。
按契约 §7 同步 `api.schema.json`、`oauth-pilot.demo.json`、正反例及 REST 边界测试。
控制端点是 OAuth 标准协议，不包装业务信封；records/task-drafts 仍 ApiEnvelope 1.0.0。
现有公共 REST/MCP、业务 schema_version、算法和云部署不变，**没有上线个人数据**。

- A：地图/资料现有公开只读查询不需要这个授权，无须迁移。
- B：候选 records 只返回已确认的 owner 课表/待办，课表缺失为 null，不回退公共课表。
  Agent 只可建固定通知草稿；浏览器确认/保存门禁保留。当前不接真实课表上传。
  云候选另提供 POST /oauth/time/free-slots、/oauth/time/check：OAuthPilotTimeQueryRequest
  的 query_json 为既有查询对象去掉 workspace_ref，其余必填字段与 null 保持。
  只计算 grant owner 的已保存课表/待办，复用原 B 算法及 TimeResult，不改变算法；
  已同步 schema、夹具与 HTTP 正反例。保留 coverage/needs_confirmation 和 calculation_version，
  不允许 Agent 传 owner、user_id、课表或任务替换真实归属。未接通学校调用前不算上线。
- C：本次不增加成绩接口，不扩展 DegreePlan；正式规则来源与知识库接入依然待交付。
  不能把缺规则的演示 audit 包装成毕业完成结论。
- D：必须完成云端持久身份/授权存储、学校 PKCE 与保密 token 实际验证、A/B 平台回归后才可推广。
  不注册 OAuth MCP 工具、不允许模型传 user_id/令牌当身份、不用 Client Credential 代替用户授权。

完整路径、限制、回调及上线门槛见 [OAuth 候选说明](../../deploy/OAUTH-PILOT-ADAPTER.md)。

2026-10-03 本人复核入口修复候选：新增云身份站只读 `GET /api/v1/auth/cloudbase/browser-session`。
契约 `CloudBrowserSession`、`browser-session.demo.json`、Cookie/Origin/到期/跨账号/退出 HTTP 正反例同步。
新标签页用原 HttpOnly 会话和 MAC 绑定的短期上下文恢复，不轮换 OAuth 来源会话/CSRF，不延长到期。
当前 owner 由既有 PG RPC 重验；不改 15 表、角色、RPC、B 算法或公共 MCP，不开放个人数据。
Tasks/Import 在身份模式不再显示匿名工作区按钮，过期才登录并回到受控原草稿；
只有本人显式复核能确认/提交。A 无须迁移，B 原算法不变，C 正式来源仍待交付。
这只是本地候选；不据此声称 Agent→本人复核的云端/学校链路已经通过。
