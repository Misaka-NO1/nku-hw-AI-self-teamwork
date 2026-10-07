# 通知联动后端接口交接

2026-10-06。按负责人最新要求，本轮只完成后端、工作流候选和接口逻辑，不继续开发前端。下列是本地验过的云入口候选，尚未部署或绑定学校主Agent；不把已有线上固定通知测试当作新接口验收。

## 入口与身份

复用`app.cloud_identity_site`、现有CloudBase两个批准普通账号、原Cookie/CSRF/24小时本人工作区；不另建用户体系。新增`CLOUD_NOTICE_TEXT_PILOT_ENABLED`默认false。开启前必须具备既有身份配置和独立`notice-text-migration.sql`；启动和健康检查会验证`notice-text-v1`，迁移缺失不启动业务。

新增迁移仅建`nku_notice_text_v1`四张表（drafts、confirmations、tasks、idempotency）与后台RPC，沿用原身份owner锁。旧15张身份表、原固定夹具/RPC及参赛OAuth三表保留；匿名/普通登录角色不能调用新RPC或直读表。本轮未在云上执行迁移、改权限或切流。

以下浏览器API均相对于身份服务origin。写请求沿用`credentials: include`、精确同源Origin与`X-CSRF-Token`；创建/修改/确认草稿另需`Idempotency-Key`。调用方不得传owner/user/workspace或任意课表/任务覆盖，归属只来自已验证会话。新通知必须显式`fictional_data_confirmed: true`，仅使用自编虚构内容。

## API与调用顺序

| 方法/路径 | 输入 | 返回/作用 |
|---|---|---|
| POST `/api/v1/notice-text/read` | NoticePilotReadRequest | 多事项批次、13字段通知、原文证据、未分类段落、缺项 |
| POST `/api/v1/notice-text/images/read` | multipart：file、fictional_data_confirmed=true；source_ref/reference_at可选 | OCR原始/处理文字、文件hash、单页覆盖、read_request、待复核batch；can_save=false |
| POST `/api/v1/notice-text/check` | NoticePilotCheckRequest | 本次TimeCheckRequest/TimeResult、冲突名称、候选及来源索引、覆盖、Plan |
| POST `/api/v1/notice-text/workflow` | NoticeTextWorkflowRequest：read 与 analysis（可为null） | 同一本人资源下的提取批次、分析结果、可核对步骤与下一步保存接口；不自动写入 |
| POST `/api/v1/notice-text/drafts` | `{"plan": Plan}` | 草稿ID/revision/payload_hash；仅草稿、不占时间 |
| GET `/api/v1/notice-text/drafts/{id}` | 无owner参数 | 本人完整草稿payload及状态 |
| POST `/api/v1/notice-text/drafts/{id}/update` | `{"revision": n, "plan": Plan}` | revision+1；旧确认失效，同键同体重试不重复修改 |
| POST `/api/v1/notice-text/confirmations` | draft_id/revision/payload_hash | 本人明确确认后取得confirmation_id，最长10分钟且不超过会话 |
| POST `/api/v1/notice-text/commit` | confirmation_id/idempotency_key | 已保存task_id/revision；同键重试一条任务 |
| GET `/api/v1/notice-text/tasks` | offset=0..100、limit=1..5 | items/total/next_offset；仅新文本任务，分页避免传超大原文 |
| GET `/api/v1/notice-text/tasks/{id}` | 无owner参数 | 本人完整Plan与确认保存时间 |

原`/api/v1/tasks`仍是固定演示列表；新文本列表用上表专用路径。原本人`/api/v1/time/free-slots`和`check`在新开关开启时统一考虑固定演示活动及已确认文本工作区间，关闭时保留旧行为。

所有业务仍是ApiEnvelope 1.0.0。新业务data_version为`notice-text-pilot-v1`；算法版本来自B，check顶层meta中保留calculation_version。新草稿返回`review_url: null`、`review_required: true`，因为旧固定通知页不能正确呈现Plan包装；前端接入方须自行构建复核页，不能假设已有链接可用。本轮没有实现任何代点确认或自动保存。

## 文字与模型输入

Read至少包含：

```json
{
  "source_text": "请在2026年9月21日10:10前提交虚构新实验记录，材料：实验PDF。",
  "source_ref": "self-authored",
  "reference_at": null,
  "fictional_data_confirmed": true
}
```

这是历史虚构算法测试，不是当前日期默认值。省略model_output时使用保守明确文字读取器。可选`model_output`必须是原始JSON对象**字符串**：`{"items":[{"kind":...,"notice":13字段}],"unclassified":[逐字原文]}`。模型不在此后端内调用；学校大模型节点把原始输出送入本接口。重复键、非法数值/深度、额外字段、伪造引用、时间结构不一致会拒绝；原文漏读明确标记，不能勾选source_review后强行保存。

通过校验的模型输出也只是一份建议。通知ID由服务器结合本次原文/证据生成；需用响应ID作为item_id。模型提炼的时间、耗时和最早开始始终需逐字段确认，不能仅勾一个“已阅读”就交给时间工具。原文/模型原输出和用户补充分别保存，补充证据source_ref为user-confirmation。

原文最多20000字符，model_output最多120000字符且其严格JSON解码最多131072 UTF-8字节、64层；每批最多50事项。复杂文字优先模型提炼并复核，受限读取器不等于通用LLM，不承诺语义识别所有行动。

## Check与Plan

Check复用Read字段，增加item_id、user_confirmations、window与available_windows。用户补充支持source_review、ocr_review、estimated_minutes、earliest_start、due_at、event_start/event_end及accept_conflicts。全部时间须带时区；缺时刻不补23:59，缺耗时不猜测。相对日期须reference_at或用户直接确认具体时间。

window须递增且≤31天、完整包含活动；available_windows是最多20个在window内的不重叠限制区间，可以表达仅晚间等条件。可选buffers对象含before_minutes/after_minutes（0..1440），表示忙碌事件前后的预留，直接交B算法；不改B算法，不由模型心算空档。省略buffers等价于0/0，禁止分段工作。

Plan保存source_text/source_ref/reference_at、可选原始model_output、source_kind/document_sha256、buffers、用户补充、查询限制、kind、原13字段NoticeDraft及selected_slot。deadline_feasibility必须选择**本次真实candidate_slots的完整对象**；活动selected_slot为null，有冲突须accept_conflicts=true。总计划最多262144 UTF-8字节。推荐取最多前三个实际候选，保留candidate_index，其他候选也保留在原始TimeResult。

示例完整请求见[text-notice-pilot.example.json](../../fixtures/text-notice-pilot.example.json)。接口不接受直接改notice字段绕过原文/补充；服务端重建提炼结果并对比整个计划。修改耗时/限制/时间后须重新check，再更新同一草稿revision。

## 保存一致性与读回

确认和提交前都重读本人课表/已保存任务，再计算所选时间。PG在原owner锁内核对records_revision，阻止“服务计算后、事务提交前”发生的新课表/安排变化；版本只是内部一致性标记，不能作为身份凭证，客户端不能选择它。

截止时刻保留为deadline。仅已确认selected_slot映射为后续忙碌event；未提交草稿不占时间。相同本人notice_id有唯一约束。创建/更新/确认/提交分别使用稳定幂等键，同键不同请求409；丢失响应可同键同体重试。旧revision、篡改/过期票据、外人ID或已改变的候选拒绝。新任务保存后重新查询可避开该工作区间。账号退出/会话到期/撤销批准也会阻断读写和OAuth重放。

完整分页列出时如期间有新任务，刷新可取得最新列表；分页不是跨多次请求的数据库快照。工作区24小时后拒绝访问，本轮没有物理清理作业，不承诺已删除原文。

## 学校OAuth与工作流候选

现有严格S256和参赛普通授权码两模式在新开关开启时均增加只读：

- POST `/oauth/notice/read`：`{"query_json":"完整Read JSON对象文本"}`。
- POST `/oauth/notice/check`：`{"query_json":"完整Check JSON对象文本"}`。

query_json保留null/数组/对象与用户明确补充，最多131072 UTF-8字节。owner只来自Bearer授权，不相信浏览器Cookie或模型参数。既有demo:read继续只读；OAuth没有新文本草稿、确认或提交接口，不增加参赛写scope。本人records/time读工具在开关开启时返回/考虑文本工作安排；records为计算返回语义摘要，原文用本人浏览器GET task读回。

源码候选：notice-text-input.js → 学校模型提示词 → notice-read-request.js → OAuth read；用户补充后notice-check-request.js → OAuth check。原始模型extraction传入后端，不能传已包装的validated_json冒充原始13字段输出。代码校验仅结构与引用存在，不证明模型字段语义正确。配置及提示词见[工作流说明](../../deploy/genios-workflows/README-notice-text-pilot.md)。D14已创建独立学校测试稿，正文输入/模型/校验实际Debug通过；该次原始输出也通过本地统一workflow入口与PG保存读回。学校OAuth新接口实际注册绑定和主Agent实跑仍未进行，不能等同于线上闭环。

## 图片格式与运行时

只支持单张PNG/JPEG，2 MiB、边长≤4096、≤1200万像素；读取文件头而非相信扩展名。PDF明确415，不宣传支持文字PDF或扫描PDF。OCR默认`NOTICE_OCR_BACKEND=disabled`，未配置返回503，并建议粘贴文字。

Windows本机可显式配置windows，使用系统现有中文识别器；不修改系统脚本策略。Linux云容器使用tesseract适配时须预装含chi_sim+eng的受认可OCR运行时，并把`NOTICE_OCR_COMMAND`设为可执行程序绝对路径；本轮未安装云OCR运行时或改Docker基础镜像。程序参数固定、临时文件名固定、超时25秒，无动态shell或外部上传。

OCR保留raw_ocr_text及处理后source_text，处理只去掉中文分词空格，**不拼数字、不修复错字**；覆盖表示单图已送OCR，不表示文字100%正确。source_kind=ocr和document_sha256必须随check/Plan保留，原图核对ocr_review、关键字段补充和source_review均完成才能推荐/保存。图片原件只用于读取临时文件，读取完成即清理；原文与hash可在本人计划中保留。

本机真实虚构截图的10:10被识别为分开的“1 0 ： 1 0”，材料句也有错字；缺时刻/图文复核阻止自动计算。测试在明确确认10:10等字段后实际返回09:40—10:00并保存读回。这是本机系统OCR+嵌入式PG证据，不等于Linux云OCR或学校附件链路通过。

## 错误与接入边界

401需本人重新授权/登录；403是本人/CSRF/虚构模式限制；404表示本人记录不存在（缺课表与外人ID不借用共享数据）；409需重新核对版本/候选；410票据或草稿到期；413/415输入大小或格式超范围；422需修正文案/结构/字段；503依赖未配置/不可用。工具失败不能回答为“没空”，needs_confirmation未清不能保存，未知课表覆盖不能说用户确定有空。

本轮交付代码与接口，并在D14完成学校独立提取工作流Debug和该次原始模型输出的本地PG保存读回。上线迁移、部署、学校新OAuth工具注册绑定/主Agent实操、两个真实账号及前端复核页接入尚未执行，后续按具体上线范围验收。测试与失败记录见[D13](../evidence/platform/D13-notice-schedule-acceptance.md)与[D14](../evidence/platform/D14-notice-workflow-acceptance-2026-10-06.md)。
