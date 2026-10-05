# D06：005兼容工具平台实测、团队发布及主Agent部分验收

日期：2026-09-30，北京时间。结论：学校插件六类兼容工具的正反例通过，团队测试插件已发布，主Agent草稿七工具绑定和提示词保存已读回；主Agent仅资料真null用例在本轮实际验收通过，其余主Agent用例因学校登录过期未完成。不能签收全部D06，更不是个人数据或完整项目验收。

续步状态：用户随后告知重新登录并要求未经其通知不再关闭公网。学校编排页实际恢复，七项绑定与提示词仍在，草稿保存时间读回19:41:31；未重建或部署。前一窗口已按原“人工阻塞关闭”约定关闭，因此正在就**重新开启并持续到用户明确要求关闭（跨本轮结束）**的新时长确认风险与范围；尚未重新开启，后文关闭证据仍有效。

## 范围与版本

用户针对本轮入口持续开放、插件同步/映射复核、仅发布已通过工具、绑定主Agent草稿及固定虚构测试明确回复“允许”。仅使用既有nku-campus-mcp-probe默认HTTPS入口，保留Bearer；结束或需人工处理时关闭。旧令牌暴露风险已知且用户不轮换，本轮不读取、复制或修改正确令牌。

本轮**没有部署任何新云版本**：仍用005，源码853d17dd3557d8872f0f78e5f13a12acadc514f1，build_id=cloudbase-demo-readonly-20260930-853d17dd-platform-compat。005正常100%；004、003保留。没有改变实例下限、数据库、个人上传、A/B/C算法、REST、原MCP定义或Schema1.0.0。仅学校插件映射/启用状态、团队测试插件发布和主Agent草稿变更；未发布主Agent、上架市场或接入个人数据。

## 前置检查与同步

入口开启后实际前置结果：19:17:10健康GET为200（247.41ms）；19:17:11无Bearer POST为401（70.01ms），错误Bearer为401（136.03ms）。首次本机受限环境连接错误在约35ms结束，无HTTP状态；允许网络诊断后同一脚本通过，不能将首次连接错误记为服务器故障。正确令牌只由学校已保存插件使用，未在本机读取或测试。

campus-tools-dev（datsct54shh9f0j06qkg）同步实际发现13工具：原六业务、六platform_*兼容业务、health_probe。同步覆盖了旧手工输出映射并重置Debug状态，因此仅对六个兼容工具重新保存并逐一重开确认：

- 输入为唯一必填String字段query_json，保留原导入定义。
- 保留isError:Boolean、content:Array<Object>及其type/text。
- 保留structuredContent:Object根，只移除学校误推断的data/error/meta/ok子类型定义。服务器实际字段未删除，完整JSON仍在content.text及structuredContent中。
- 六份配置均完成保存；重新打开后structuredContent没有子类型定义。

一次较长浏览器复核批次超时导致操作会话重建，随后按小批次重新核对六份保存状态；未据此重新同步、部署或假定前一批已经保存。

## 插件Debug真实正反例

以下request_id均取自当次工具原始业务JSON，不是模型生成。绿勾只表示平台能处理返回，错误分支以ok=false、data=null及真实错误码判断，不算业务成功。六类兼容工具最后均显示Debug通过、启用；health_probe也通过并启用。

| 用例 | 工具（均为platform_前缀）/实际输入 | 实际业务结果 | meta.request_id |
|---|---|---|---|
| PC01 | search_study_materials：demo-CS101/topic:null/limit5 | ok=true；demo-note-01有正文，demo-index-02仅索引；error=null | e79c10b9-b196-4229-a372-dae5aa94b13e |
| PC02 | 同上，topic字面字符串"null" | ok=true，data=[]；未强制转成null | ff1ca803-a061-421b-8b28-d392c203f709 |
| PC03 | 同上，topic="递归" | ok=true；自创笔记正文及标题锚点，非真实课程材料 | abdc1592-ec8f-4eb4-a077-b27b5ad23660 |
| PC04 | 同上，topic:null/limit0 | VALIDATION_ERROR，limit/minimum；isError=true | 2c8415ee-92b4-42f0-a4de-d2646af5d420 |
| PC05 | check_time_plan：原time-event-query.demo.json，全部null原样 | ok=true；冲突09:20–09:40、10:10–10:20，+08:00；覆盖未知完整度 | d79f9ebf-5dd9-4169-b1c0-122a65994c80 |
| PC06 | check_time_plan：原time-deadline-query.demo.json | ok=true；候选09:40–10:00，20分钟 | 28495385-e36f-4e43-95b8-0544f2d7ae0e |
| PC07 | 同上，estimated_minutes:null | ok=true；候选空，needs_confirmation=[estimated_minutes] | 313bf53b-2659-47b4-98c4-7d3da7bb53af |
| PC08 | 活动查询workspace_ref=demo-unbound-test | IDENTITY_NOT_VERIFIED；isError=true，无资源兜底 | 9c77126c-65cb-4aba-aa13-a4f2d2a166b6 |
| PC09 | validate_timetable：完整原timetable.demo.json | ok=true；normalized_payload保留null/数组；issues=[]；仅校验，不保存 | a201bc03-1e65-4e05-9cf2-d6eeb7090b5d |
| PC10 | 同上，首课程teacher_display改为虚构非夹具文字 | DEMO_ONLY；不接受任意上传 | 6d918ec9-acdb-4d59-bfe1-38594ada919a |
| PC11 | search_scenic_spots：campus_id:null/tags:[]/month:null/limit5 | ok=true；demo-spot-01/02/03；photos=[]、observation=null、非实时 | 5e95d5bd-edb8-46d3-a7b6-e88013623ed2 |
| PC12 | 同上，JSON内重复limit键（5与1） | VALIDATION_ERROR/invalid_json；不回显请求正文 | df5643bc-6ea8-4df2-8511-c91738d129b5 |
| PC13 | query_free_time：原time-free-query.demo.json | ok=true；09:40–10:10，30分钟；第3周/完整度未知 | 7bfce5d6-ed79-43f5-a339-79c27f72dd46 |
| PC14 | 同上，min_minutes="30"字符串 | VALIDATION_ERROR/type；不自动转为数字 | 9279a38b-62b1-44f5-b052-b747854b05a6 |
| PC15 | audit_degree_progress：原degree-query.demo.json | ok=true；incomplete；已获5.0、尚缺7.0；非毕业决定 | 409f9324-7e18-436b-9f7e-2743ec18ed93 |
| PC16 | 同上，plan_id=demo-missing-plan | NOT_FOUND；不回退到另一方案 | 1a054adf-32d3-490d-8e7e-dfda181f8346 |

PC09 payload_hash=643fef057c3c6503a888a84727f2f9d7a497558b37b0087d6887b3973f725335；覆盖term第1–4周/complete。PC15核心已获3.0/目标8.0、选修已获2.0/目标4.0，missing_required_courses为CS102/CS103，计入2、排除3条。以上只是固定公开虚构夹具，不是真实课表、成绩或官方培养规则。

探针另测：nonce=d06-005-20260930-probe-ba29ecfc83ab，原样回显，isError=false，build_id匹配005，server_time=2026-09-30T19:27:04+08:00。这是本轮插件探针调用，不是本轮主Agent探针验收。

## 团队发布与草稿绑定

六个原业务工具在学校插件编辑版中禁用，配置和后端工具均保留；六个platform_工具及探针启用。发布确认仍列出六个原工具“未通过”警告（同步重置），没有隐瞒或把警告等同算法失败；确认后平台返回“发布成功”。随后主Agent自定义插件添加面板实际只有7工具，证明本次可添加集合排除了六个禁用原业务，而不是仅由开关推断。

主Agent草稿datqi1l4shh989l30fp0绑定以下7项，删除4个旧同义业务绑定；刷新后确认七项完整、无原业务同义绑定：

health_probe、platform_validate_timetable、platform_check_time_plan、platform_query_free_time、platform_audit_degree_progress、platform_search_scenic_spots、platform_search_study_materials。

prompts/main.md更新工具名、唯一query_json字符串传参、一次JSON编码、真null/字面"null"区分及失败如实报告规则，保留只读、身份、证据和禁止编造边界。写入学校草稿后刷新读回，保存时间显示19:41:30，文本有平台空白格式化但语义持久化。模型仍为doubao-seed-2-0-mini，没有添加变量、KB、工作流或写入能力。插件卡旧创建时间不作为本次发布时刻。

## 主Agent本轮实际验收

MA-C01：用户选择固定演示后请求platform_search_study_materials，19:42:05工具卡出现。本次**核对了实际Input和Output**，不仅依据模型回答：

```json
{"query_json":"{\"course_id\":\"demo-CS101\",\"topic\":null,\"limit\":5}"}
```

只有一个字符串参数，其中topic是无引号的null，没有再次成为"null"。实际Output：isError=false，ok=true，error=null，request_id=30d7651a-cc80-400a-8392-3afbd55effac；资料为有正文demo-note-01及无正文demo-index-02，后者evidence=[]、content_available=false；page_label=null保留，真实标题/来源锚点存在。模型回答也正确区分正文和索引。只签收这一用例，不推断模型永不传错或全部工具已端到端通过。

MA-C02–C07随后一次请求拟验课表校验/时间冲突/空闲/培养/景点/探针；页面在出现新工具卡前报“运行失败”“请求异常，请稍后重试”。改单项时间冲突请求也立即失败，无新的工具执行证据。刷新实际跳到学校IAM登录页，确认会话失效；一次点击页面现有“一键登录”后仍停在IAM，需要用户自行恢复登录。未把批量/单项失败算业务验收、未声明后端报错、未据此修改算法或重新部署。

随后只读核对云端005的工具审计，19:42:08确有platform_search_study_materials tools/call，JSON-RPC id="3"、协议2025-06-18、duration_ms=3.15、outcome=ok，与MA-C01当次工具卡时间/工具相符。此RPC id不同于业务UUID，审计不含业务参数或UUID，不声称两者可按同一个ID直接联结。19:27:05探针审计id="2"/0.92ms/ok；插件培养方案19:26:19/2.33ms/ok与19:26:31/0.55ms/error、空闲19:25:54/1.98ms/ok与19:26:01/0.95ms/error、景点19:25:25/2.54ms/ok与19:25:33/0.36ms/error均来自005，业务失败现正确标记error。只保存白名单摘要，不保存令牌、SDK会话ID或完整日志。

没有声称16项插件用例全与审计逐一对照。其余五类主Agent用例、主Agent新探针、主Agent错误/身份分支仍待完成；原004主Agent历史结果不代替005新绑定验收。

## 最终安全状态、证据与下一步

登录需人工处理后关闭默认公网入口，保存完成后读回：公网默认域名关闭、内网默认地址关闭、保存按钮消失；005仍正常100%，不删004/003。令牌未读取或改变。关闭的是入站默认域名，不混同实例出站“公网访问”。

本机忽略目录截图（不提交Git、不含令牌）：

- deploy/cloudbase-demo-readonly/dist/D06-005-study-null-debug-20260930.jpg：插件真null成功。
- D06-005-compatible-tools-tested-20260930.jpg：六兼容和探针通过/启用，六原工具禁用。
- D06-005-compatible-plugin-published-20260930.jpg：团队插件发布后的页面。
- D06-005-main-study-null-output-20260930.jpg：本轮主Agent实际工具卡Output（预览区域较窄，详细数值以本文原始Output记录为准）。
- D06-005-compat-round-closed-20260930.jpg：005正常100%及公网/内网入口关闭。

本轮只有提示词/文档本地变更，不新增后端代码；此前275项后端本地通过是候选实现阶段证据，不冒充本轮重新执行。未跟踪的local_secure_probe_bridge.py和cloudbase-mcp/assets保留且不提交。

下一步先恢复学校登录；核对已保存的七绑定和提示词，**不重新同步、重建插件或部署005**，避免覆盖已验证映射。新的公网窗口按当次范围确认后补验其余主Agent真实Input/Output和审计。之后才推进原计划D07通知工作流、D08 TasksPage、D09学习KB工作流及D11身份/持久化门禁；本轮未完成这些，也不提前发布主Agent。
