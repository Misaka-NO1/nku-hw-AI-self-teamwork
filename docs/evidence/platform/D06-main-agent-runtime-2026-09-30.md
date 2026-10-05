# D06 主 Agent 实际调用、失败定位与本地兼容修复

日期：2026-09-30，北京时间。范围：同一CloudBase服务、既有团队插件及主Agent草稿，固定公开虚构夹具。状态：**部分平台案例通过，整体D06未通过；query_json兼容层仅本地候选，未部署**。

## 环境与授权

- 空间：南开校园助手，workspace `datqfnm9t58vf5r4v1eg`；主Agent `datqi1l4shh989l30fp0`，未发布。
- 插件：campus-tools-dev，`datsct54shh9f0j06qkg`；草稿绑定health_probe、景点、资料、空闲时间、培养方案5工具。
- 云服务：上海 `sunner-wang-d8ght8niaaaea70b7` / nku-campus-mcp-probe；004保持100%，build `cloudbase-demo-readonly-20260930-cda01c67`，旧003保留。
- 地址：原默认HTTPS域名 `/mcp`。用户批准本轮持续开启，结束/人工阻塞关闭；本轮结束已关闭并读回公网/内网均关闭。8080、最小0/最大1、数据库/个人上传/其他服务不变。
- 旧令牌曾暴露，用户已知风险；本轮不读取、复制或输出正确令牌，仅学校已保存的保密配置调用。无个人数据、知识库上传、主Agent发布或市场上架。
- 用户另批准先实现query_json兼容层并本地测试、准备候选包，不据此发布云服务/新插件。

## 前置检查与提示词变更

17:35:11健康GET等待30109.78ms后超时，无HTTP状态，未发鉴权测试。控制台当时0实例；17:36:20实际容器启动完成。此轮入口没有在重试间切换；17:37:17再试健康200/210.99ms，无Bearer401/74.93ms，错误Bearer401/122.47ms。时序符合冷启动延迟，不能据此解释其他历史403。

将草稿提示词更新为实际已绑定的5工具和未绑定2工具，明确固定演示、空值保真、来源/身份/错误边界。页面保存先显示17:33:31。MA04首次无工具编造结果后，在线草稿再加入“执行优先约束”，相同内容保存到 `prompts/main.md`；后续MA04-R1真实调用通过。**这只是一次纠正和重测，不能保证LLM永不幻觉**。最终尝试刷新核对新增约束持久化时转到IAM登录页，因此约束最终刷新读回仍待下一次登录，不声称字节一致或已完全核验保存。

## 实际Input / Output结果

成功/失败均以工具卡实际输入、原始content.text业务信封和isError为依据，不以模型回答代替。下表请求ID是业务信封UUID；JSON-RPC序号另列，不能混用。主Agent请求时间与服务器日志时间有数秒差异。

| 案例/请求时间 | 实际结论 | 业务 request_id |
|---|---|---|
| MA01 17:38:37 景点 | PASS；demo-campus/flower/3/5，返回demo-spot-01；空观测、空照片、历史花期警告保留 | 6b2710ef-022a-43f0-bb22-9fc313373c60 |
| MA02 17:39:46 资料正文 | PASS；demo-CS101/递归/5，返回demo-note-01，真实正文定位，无伪造页码 | 3f693793-b6b7-4c2a-94ed-7f06c8d6528e |
| MA03 17:40:42 空闲时间 | PASS；固定workspace/window/min=30/buffers=0；09:40–10:10+08:00，30分钟，time-v1，覆盖限选定周 | ebca44a2-5301-40e7-999c-53be755d89e2 |
| MA04 17:41:19 培养方案首次 | FAIL；没有工具卡，模型捏造学分/进度及request_id，不属于服务器结果 | 无真实UUID |
| MA04-R1 17:42:56 加约束重测 | PASS；真实工具返回incomplete，earned5.0/remaining7.0；非官方毕业结论 | 527c3992-cd6f-402e-bdd9-bf386c0e950e |
| MA05 17:43:34 索引无正文 | PASS；topic=排序，demo-index-02，content_available=false/evidence=[]，回答未编正文 | 99277b2e-bada-4bd0-81fa-a06b1ab6faf9 |
| MA06 17:44:18 景点nullable | PASS；实际tags=[]、month=NULL、limit整数5，返回3点位；GUI限制不等于此Agent运行时限制 | 29906c33-d9f3-4d99-a54d-726568d57d4e |
| MA07 17:44:57 资料nullable | FAIL；要求topic:null，实际Input为String "null"；返回空数组不是null请求通过 | eebd7d95-8992-459f-85b7-683023da714b |
| MA07-R1 17:46:26 强调类型再试 | FAIL；仍为String "null"，模型反称传了null；提示词无法可靠保证类型 | 347b44a3-cbfa-4f25-8bb7-73057145aa3f |
| MA08 17:48:10 非法limit | PASS错误分支；实际limit整数0，isError=true/ok=false/data=null/VALIDATION_ERROR，未悄悄改成5 | 6bf970a0-3465-4c1e-9df9-c5fff74290a9 |
| MA09 17:48:57 未知plan | PASS错误分支；demo-missing-plan，NOT_FOUND，未回退默认plan | ab0be388-b709-441d-b8a2-866eacaeb8c1 |
| MA10 17:49:43 未绑定身份 | PASS错误分支；demo-unbound-test为虚构不存在引用，IDENTITY_NOT_VERIFIED，未回退公共workspace | 0cc53a03-17d5-4307-a551-b89009fa4f6f |

MA02证据定位：knowledge/study/sources/demo-note-01.md#递归的两个必要部分、#数组下标检查，page_label=null。回答中额外的一般性解释不能伪装成逐字来源。MA03实际window为2026-09-21T08:00:00+08:00至12:00:00+08:00，warnings含DEMO_DATA/calendar_not_official；这不是个人实时课表。MA04-R1模块core earned3/required8/remaining5，elective earned2/required4/remaining2，warnings DEMO_DATA/NOT_GRADUATION_DECISION。

探针真实输出：nonce `d06-ma-runtime-20260930-8f403e22` 精确回显，build同004，server_time=2026-09-30T17:37:31+08:00，isError=false。插件编辑列表的未通过状态与真实探针成功不同，原因未知，不据此改后端或签收其他工具。

MA04首次模型捏造earned60/remaining15、core80%/elective65%及自造编号；真实工具卡缺失，完整日志中17:40:46至17:42:58间未见degree工具调用。不能让这类回答进入演示成绩。

MA07两次证明输入在业务算法前已失真，但尚不能区分模型生成与平台类型转换的责任；**不把字符串"null"强制转null**，因为它本来就是合法字面查询。新增query_json仅绕过分散nullable字段传输，不放宽任何业务规则。

## 云端工具审计（004，同一轮）

全部method=tools/call；tools/call记录protocol_version=2025-06-18。initialize记录为2025-11-25，与调用审计不同；不据此宣称完整协议协商一致，需按实际平台请求继续核对。以下outcome是原日志值，不代替业务信封：错误分支也记ok，因此判断业务成败仍须看isError/ok/error。

| 时间 | tool_name | JSON-RPC request_id | duration_ms | 日志outcome |
|---|---|---|---|---|
| 17:37:32 | health_probe | 3 | 0.97 | ok |
| 17:38:40 | search_scenic_spots | 6 | 3.53 | ok |
| 17:39:49 | search_study_materials | 8 | 3.48 | ok |
| 17:40:46 | query_free_time | 10 | 2.56 | ok |
| 17:42:58 | audit_degree_progress | 12 | 2.36 | ok |
| 17:43:37 | search_study_materials | 14 | 2.99 | ok |
| 17:44:20 | search_scenic_spots | 16 | 2.97 | ok |
| 17:45:00 | search_study_materials | 18 | 3.02 | ok |
| 17:46:29 | search_study_materials | 20 | 2.76 | ok |
| 17:48:13 | search_scenic_spots | 22 | 0.56 | ok |
| 17:49:00 | audit_degree_progress | 24 | 0.46 | ok |
| 17:49:46 | query_free_time | 26 | 0.66 | ok |

审计工具耗时、模型/工具卡合计和整段回复耗时口径不同，不横向当作算法速度。无令牌/正文/传输会话ID保存到本文。

## 当前边界与下一步

固定正向四类业务、索引边界、部分nullable与3类错误分支已有证据；资料nullable失败，两类check_time_plan/validate_timetable仍未平台验收。D06不可整体标PLATFORM_PASS_DEMO；更不能标PLATFORM_PASS_PERSONAL。

公网关闭截图：本机忽略目录 `deploy/cloudbase-demo-readonly/dist/D06-main-agent-runtime-closed-20260930.png`，含004及公网/内网关闭状态，无秘密。学校最终刷新跳IAM；不要求现在为本地开发重新登录。只读兼容候选完成后另获更新同一服务/流量范围、团队插件和临时公网的确认，再验完整真实Input/Output；主Agent继续草稿。

本地兼容设计、测试、包指纹另见 [query_json本地记录](D06-query-json-local-2026-09-30.md)。
