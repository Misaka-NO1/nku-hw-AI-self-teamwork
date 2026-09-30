# D06：主Agent只读业务验收准备

日期：2026-09-30（北京时间）。本文件是待执行计划，不是通过证据。已有四类插件Debug通过见[D06兼容复测](D06-platform-output-compat-results-2026-09-30.md)。主Agent仍只绑定已发布的health_probe；不能由历史Debug推断主Agent已接通业务。

## 已获范围与当前阻塞

用户本轮明确允许：四类已通过业务工具与复测后的health_probe发布到“南开校园助手”团队测试插件；课表校验/时间冲突两类暂禁用，保留配置；绑定主Agent草稿并测固定虚构数据。只开同一nku-campus-mcp-probe默认HTTPS入口，保留Bearer，本轮结束或人工阻塞关闭；不发布主Agent、不上架、不接个人数据/数据库。旧令牌暴露风险已说明，仍不读取正确令牌。

首次点击check_time_plan禁用后UI切换为禁用，却出现Network Error；刷新真实跳转学校IAM登录。因此禁用保存状态未确认，不算成功。尚未点击第二个工具的禁用、未发布插件、未新增草稿绑定、未开启公网。等待用户在插件页面自行重新登录；重新进入列表先读真实开关，避免重复切换已保存的状态。

## 执行顺序

1. 确认学校/云端登录有效。读回工具开关，仅禁用check_time_plan与validate_timetable；确认另外四类及health_probe开启。保留两类参数和待测问题，不能删工具或更改公共契约。
2. 在当前health_probe编辑版准备新的随机nonce，前置健康200/无错Bearer401后才Debug。必须原始Output回显nonce与cloudbase-demo-readonly-20260930-cda01c67构建号一致。传输失败/构建不符/鉴权门禁失败停下并关闭入口。
3. 发布前查看实际发布范围/提示，确保只包含已复测的5个启用工具，不发布尚未通过两类；若平台会纳入禁用工具或强制全部通过，停下报告，不假设禁用等于排除。
4. 仅发布campus-tools-dev团队测试版本，不点上架或主Agent发布。读回发布状态，主Agent草稿的添加列表应发现这5个工具；两类不得添加。
5. 草稿绑定四类业务，保留探针。草稿提示词明确当前能力与只读演示范围，不改变模型/真实身份变量，不把SYS_USERID当认证。保存后重开确认绑定和提示词。
6. 以下用例逐一发送；每次核对实际Input/Output、业务信封、warnings、证据及云端tools/call。不要以模型自然语言或旧结果单独签收。保持入口本轮持续开启，不在每次请求间切换；结束/人工阻塞关闭并读回。

## 核心验收用例（均待执行）

| 编号 | 工具与输入 | 必须验证 |
| --- | --- | --- |
| MA01 | search_scenic_spots：demo-campus，tags=[flower]，month=3，limit=5 | 新的真实工具调用；数组含demo-spot-01；ok=true/error=null；提醒虚构和非实时花况 |
| MA02 | search_study_materials：demo-CS101，topic=递归，limit=5 | demo-note-01正文摘录和真实标题锚点；不编造页码、考试范围或试题 |
| MA03 | query_free_time：fixtures/time-free-query.demo.json原值 | 2026-09-21 09:40–10:10+08:00、30分钟；coverage所选周/未知完整度与calendar_not_official保留 |
| MA04 | audit_degree_progress：demo-workspace-01/demo-cs-plan-v1/demo-transcript-01 | 总已获5.0、尚缺7.0等固定规则结果；incomplete；非官方毕业判断 |
| MA05 | search_study_materials：demo-CS101，topic=排序，limit=5 | 仅索引demo-index-02，无正文证据；不能凭目录生成“材料正文总结” |
| MA06 | MA01修改tags=[]、month=null | 检查实际Input显式null、空数组未被省略或强制转换；是否支持运行时nullable尚未知，失败如实记录 |
| MA07 | MA02修改topic=null | 实际Input显式null；不能用上次非空topic结果替代；平台GUI限制是否也影响Agent尚未知 |

## 错误与隔离检查（均待执行）

- 景点limit=0：必须真实发送0；后端isError=true/ok=false/data=null/VALIDATION_ERROR，不能称查询成功。若模型自行纠正为5，该次不能算错误分支验收，记录模型未遵从测试请求。
- 培养方案plan_id=demo-missing-plan，其他为原值：固定虚构未知ID，应NOT_FOUND，不自动换用相似计划。
- query_free_time用workspace_ref=demo-unbound-test（明确为公开虚构的不存在引用，不使用真实个人ID）：应IDENTITY_NOT_VERIFIED，不展示或编造个人课表，不自动回退固定工作区。
- 现阶段不调用未发布两类，不以模型猜测取代课表校验/时间冲突算法；不提供个人文件或原始通知，不发任意URL、路径、SQL。

## 主Agent草稿提示词增补候选（绑定成功后才应用）

保留prompts/main.md中的证据、权限、确认和安全边界，将“当前只绑定探针”段替换为与实际绑定一致的阶段说明：

> 当前仅接入只读演示health_probe、search_scenic_spots、search_study_materials、query_free_time、audit_degree_progress。只有工具真实返回才报告查询结果；工具缺失、失败或超时须明确说明。数据为固定公开虚构夹具，不是实时校园数据或用户私人记录。不接入个人数据，不保存任务。课表校验与时间冲突工具尚未完成平台验收，不能以模型推理冒充工具结果。可用演示标识仅demo-campus、demo-CS101、demo-workspace-01、demo-cs-plan-v1、demo-transcript-01；只在用户明确选择演示时使用，不用于兜底身份失败或未知资源。显式null与空数组遵循工具契约，不替换成0、假字符串或省略字段。

此段尚未写入线上或prompts/main.md；当前真实绑定仍仅探针，因此不得提前使提示词宣称业务可用。

## 记录与停止条件

新结果需记录实际时间、工具、业务UUID、云端JSON-RPC id/协议、构建号和真实结果，不保存令牌/会话ID/私人数据。本轮结束保存公网/内网关闭截图。任何发布范围不明、登录过期、权限不足、未过门禁、需要扩大配置/费用/数据范围时停下，不因“按计划继续”推断新授权。未通过两类的null问题保留，后续是否发布实验版或改平台输入适配需另行决定。
