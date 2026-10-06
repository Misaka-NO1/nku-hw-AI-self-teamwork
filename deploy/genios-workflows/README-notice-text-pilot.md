# 通知文字工作流候选与本地试点

## D14：已进行学校独立Debug与本地后端读回

2026-10-06新增 `WF_D14_NoticeText_20261006_Test`，未发布、0个智能体引用。Start的notice_input为完整虚构输入JSON字符串，接本目录notice-school-input.js → prompts/notice-extract.md → notice-text-validate.js → End。校验输出result和query_json（保留原始模型输出），不是固定fixture答案选择器。实际Debug出现并修正类型/引用/原文覆盖问题；最终3项提取且无未覆盖字符。

该次原始模型输出已通过新增POST /api/v1/notice-text/workflow送本地本人后端，真实B计算、嵌入式PG确认保存2项、缺日期事项写入拒绝、HTTP服务重启读回通过。学校提取与本地保存是两段分别验证；线上API迁移/部署仍未执行。详情及可复用样本见[D14验收](../../docs/evidence/platform/D14-notice-workflow-acceptance-2026-10-06.md)，流程见[D14交接](../../docs/handoffs/D-notice-workflow-2026-10-06.md)。以下旧说明中的“尚未学校实跑”保留作为D13历史状态，不代表D14本轮状态。

## 2026-10-06：只交付后端逻辑与编排候选

负责人明确前端由其他人负责。本轮补齐云本人身份下的文本读/查、独立PG草稿/确认/提交/读回及已确认工作区间的时间适配；没有继续修改前端或安装/发布学校工作流。新云开关默认false，迁移未在线执行。

学校模型输出现在可作为原始model_output传入后端，经过严格JSON、13字段、证据与覆盖检查；模型时间/耗时始终需要用户逐字段确认。候选顺序：

1. Start的source_text/source_ref/reference_at → notice-text-input.js → 系统提示词prompts/notice-extract.md与本次model_input。
2. 可用notice-text-validate.js做预校验；notice-read-request.js接source_json和**原始**extraction，输出query_json → OAuth POST /oauth/notice/read。不要把带item_index的validated_json当原始模型输出。
3. 用户明确补充后，notice-check-request.js接read_request_json、服务器item_id、user_confirmations_json/window_json/available_windows_json及可选buffers_json，输出query_json → OAuth POST /oauth/notice/check。
4. 前端接入方根据返回的Plan与用户选择创建本人草稿/复核/确认保存。学校OAuth仍仅只读，没有自动保存或确认工具；新草稿review_url为null，不能编造旧页面可用链接。

旧工作流与主Agent本轮未改动。代码节点映射与校验本地10项测试通过，尚未学校Debug或主Agent实操。云新API、来源/OCR标记、身份、参数及保存步骤见[后端接口交接](../../docs/handoffs/D-notice-backend-interface-2026-10-06.md)。

截图增加独立后台接口和系统OCR适配，本机自编单张截图已实际读到提炼/缺项；核心字段经明确确认后计算和PG保存通过。该记录不证明学校文件输入或Linux云OCR已通；PDF仍不支持。下面是10月5日历史候选说明，云“尚不接受”限制已被本轮后端候选接入替代，但线上部署状态仍未改变。

2026-10-05：这里新增的是本地候选源码，**未导入、未部署、未发布、未绑定学校主Agent**。
不覆盖已发布的 `WF_NoticeDraft_v1_Test` 或 `WF_D07_NoticeTime_Test`。

已在学校界面只读核对：旧提取工作流 Start 输入为 fixture_id；代码01构造固定模型输入；
代码02输入fixture_id/extraction，输出query_json/result。代码02仍是 closed-fixture semantic oracle。
Javascript代码节点的入口是 `function handler(params)`。已知节点形态不代表本候选已Debug成功。

通用阅读候选节点：

| 节点 | 输入 | 输出 |
|---|---|---|
| Start | source_text / source_ref / reference_at（文本，参照可空） | 原样传递 |
| 代码输入 | 本目录notice-text-input.js | source_json / model_input（字符串） |
| 大模型 | model_input；系统提示词 ../../prompts/notice-extract.md | raw_output（JSON字符串） |
| 代码校验 | source_json直连代码输入、extraction直连raw_output；notice-text-validate.js | result对象 / validated_json字符串 |
| End | result | 待复核批次 |

校验器不比对三个固定答案，检查字段、枚举、时间格式、引用是否存在、材料引用及文本覆盖。
**它不能证明引用与每个模型字段在语义上完全一致**，因此每项始终保留source_review；
不得直接把模型日期交给旧的时间工作流，更不得去掉复核后接保存。未引用字符明确返回，不能宣称整篇已整理。
相对日期的模型换算尚须语义实测，通用模型结果也尚未接入本地计划接口。

当前可实际运行的闭环使用后端 `explicit-text-v1` 受限文字读取器和 `/tools/tasks?notice_pilot=1`，并要求前后端同时显式开启本地试点开关。
它不使用学校模型，直接从本次原文保守提炼；支持范围及启动方式见
[本地操作说明](../../docs/handoffs/D-notice-schedule-usage.md)。

已同步2026-10-05合并的PR #8（main `b4dbaec`），本人时间工具在
`backend/app/core/owned_time.py`，云身份与OAuth工具页源码也已存在。
现有云工具仍逐项校验固定虚构通知；本轮本地包装不能直接投入现有PG RPC。
下一阶段须明确隔离文本试点的云存储契约、本人时间适配和复核页，再验收模型结果→本人时间→确认保存。
不能把本地Cookie工作区或共享Bearer当成学校账号身份；本地试点接口不能在当前云只读容器里直接开启。
