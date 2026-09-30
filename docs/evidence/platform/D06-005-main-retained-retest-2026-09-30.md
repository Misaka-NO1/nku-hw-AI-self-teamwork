# D06：005主Agent补测与持续公网入口

日期：2026-09-30，北京时间。用户明确要求“重新开启并保留，补测其他工具”，不再按本轮结束/登录失效自动关闭公网。旧令牌暴露风险已说明且用户拒绝轮换；只改变既有服务默认HTTPS入站入口的开放时长，保留鉴权，不改数据库、其他服务、实例下限或云版本。

## 入口与版本

实际重新开启nku-campus-mcp-probe默认公网域名，保存后读回“开启”、内网默认地址“关闭”、保存按钮消失；仍使用005，没有上传候选、构建或发布新云版本。公网按照用户新授权持续保留，不能把此前关闭截图当当前状态。

20:01:00健康检查200/190.21ms；20:01:01无Bearer401/66.79ms、错误Bearer401/119.27ms。正确令牌不读取、不在本机测试，仅由学校既有插件保密配置使用。截图为本机忽略目录deploy/cloudbase-demo-readonly/dist/D06-005-retained-public-20260930.jpg。

## 主Agent真实业务补测

沿用已保存七工具草稿与提示词，不重复同步、重建插件或部署。查询只用仓库原公开虚构夹具，不涉及学生个人记录或实际培养规则。

| 用例 | 已核对的实际Input/Output | 本次业务UUID与结果 |
|---|---|---|
| MA-C03 | platform_check_time_plan，query_json与time-event-query.demo.json一致，due/estimated_minutes/earliest_start/date保持真null、allow_split=false | 147e9118-870a-44dd-95d4-e1e53b347978；ok=true/error=null；冲突09:20–09:40与10:10–10:20+08:00；覆盖term第1–4周/unknown |
| MA-C04 | platform_query_free_time，解析实际query_json后与time-free-query.demo.json完全一致 | c6667e48-0634-45f4-ad9f-eaedbfc3ffc3；isError=false/ok=true/error=null；09:40–10:10+08:00，30分钟；覆盖第3周/unknown |
| MA-C05 | platform_audit_degree_progress，解析实际query_json后与degree-query.demo.json完全一致 | 62b3569c-1912-4132-a4bd-96bb5d6d9458；isError=false/ok=true/error=null；已获5.0/尚缺7.0，incomplete；not_graduation_decision=true |
| MA-C06 | platform_search_scenic_spots，实际query_json为campus_id:null、tags:[]、month:null、limit:5，解析比较一致 | 9ccdc160-b79d-4de8-8b9c-3366b2edbb68；isError=false/ok=true/error=null；3个虚构点位，photos=[]、observation=null、非实时 |

MA-C03工具卡时间20:01:19，MA-C04为20:03:38，MA-C05为20:04:21，MA-C06为20:04:41。以上UUID来自实际工具原始content.text，不是只依据模型回答。MA-C01资料真null及正文/索引已在前一轮实际验收，见[前一轮平台结果](D06-005-platform-compat-results-2026-09-30.md)；合计五类业务有005主Agent成功证据，**课表校验仍不通过**。

## 课表失败：不能掩盖为成功

完整原timetable.demo.json序列化后为1606个字符，可解析。MA-C02按完整JSON文本要求调用后出现两张platform_validate_timetable工具卡；已核对最后一张的Input/Output：

- 实际query_json长度1604，末尾为`..."campus_id":"demo-campus"}]}`，预期为`..."campus_id":"demo-campus"}]}]}`，缺少最后两个字符。
- 在本地解析实际Input得到位置1604的JSON语法错误（缺少数组/对象闭合）。
- 原始Output request_id=93f703e3-d38f-4cb3-8b87-c01d73344b44，ok=false/data=null、VALIDATION_ERROR/invalid_json。另一张调用未单独读取完整Output，不将思考区所提UUID当已核验。

MA-C02-R1随后给出完整预编码工具arguments并明确末尾、不允许自行反复重试；仍失败：

- 实际Input长度1605，末尾为`..."campus_id":"demo-campus"}]}}`，缺数组闭合，解析在位置1604失败。
- 原始Output request_id=8fddbc2e-0942-4d29-90dc-5ee5cb23df84，ok=false/data=null、VALIDATION_ERROR/invalid_json，无payload_hash。
- 模型如实说明未完成校验和未保存，没有编造成功。

可证实的是**主Agent调用卡中的长JSON已损坏，后端正确拒绝**；不能仅凭模型思考确定损坏发生在模型生成还是平台参数加工的具体环节。插件Debug原完整夹具此前已成功，所以不能据此判定课表算法错误或重新部署服务。普通传参和完整预编码提示都未可靠解决，停止无意义重试；不在服务器补括号/宽松解析，不修改公共契约以把坏输入变成成功。

后续修复应考虑在学校工作流中用确定性节点生成/传递课表JSON，或经明确批准引入固定演示引用，不让语言模型抄写整个嵌套课表。需要先检查平台能力、明确实现范围，再本地/平台验收；本次未新增工作流、工具或部署，课表兼容工具仍保持现有团队配置，未擅自禁用或发布新版本。

## 探针、错误分支与当前阻塞

MA-C07真实出现health_probe调用卡，模型报告nonce=d06-005-retained-20260930-2006、build_id=cloudbase-demo-readonly-20260930-853d17dd-platform-compat、server_time=2026-09-30T20:06:09+08:00。已打开Input/Output，但当时多张展开卡导致文本输出过长截断，本轮未完成探针原始输出的精确取值记录，因此**待补读，不能只由模型回答签收探针**。

MA-C08已发送未知培养方案demo-missing-plan的查询；尚未读取其真实Input/Output，不签收NOT_FOUND。剩余主Agent非法参数/未绑定身份/缺耗时等分支待补测，前一轮插件Debug错误分支通过不代替这些主Agent用例。

22:55后接续时浏览器仅剩一个学校插件标签页，打开既有主Agent草稿实际跳IAM；一次一键登录未恢复。等待用户自行重新登录，**没有关闭公网**，没有改云服务/插件/草稿。云控制台标签页已不在当前浏览器，不能称22:55后的控制台开关已经现场重读；最后开关证据是上述20:01窗口，本轮后续只做无正确令牌的外部前置检查。

外部复核：22:56:39健康GET超时，30162.13ms，无HTTP状态，没有继续无/错令牌或正确鉴权业务测试。23:02:23同一脚本再验健康200/194.24ms、无Bearer401/81.62ms、错Bearer401/138.94ms，入口外部可达且鉴权仍有效。首次超时原因未证明，不自行判定为冷启动或后端故障；不据此重部署/改实例下限/开关入口。正确令牌仍未读取。

下一步登录后只补读MA-C07/MA-C08真实卡片和剩余错误用例；不重做五类已通过业务，不重复同步、发布或部署。保留课表失败为独立待修问题，整体D06未签收，个人数据、DB、工作流/KB/TasksPage和最终主Agent发布仍未完成。
