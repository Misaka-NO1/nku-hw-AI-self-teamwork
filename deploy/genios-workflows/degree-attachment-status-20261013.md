# 学分 JSON 附件接入交接（2026-10-13）

## 当前状态

- 学校平台此前接受 JSON 上传，但 Agent 取得的是附件链接，未可靠取得完整正文。上传成功不等于内容读取或预览成功。此限制早已记在 `degree-agent-import-status.txt`，不能据此认定为最近 DDL 规则修改造成。
- 原生 Python 只读工作流 `WF_DegreeAttachment_ReadOnly_20261013`（ID：`db6qtsd4shhbpg918qh0`）已发布 **v0.1.0**，已加入主 Agent **草稿**。
- 公开合成附件工作流读取验收通过：7,252 字节、31 个虚构模块，严格完整读取耗时 332 ms。
- 本地 114 个唯一回归测试全部通过。
- 真实 Agent 草稿的附件 → 身份核验 → 学分预览已通过。工具跟踪实际出现上述工作流、`attest_my_platform_identity` 和 `preview_my_degree_import`；预览回包含完整 31 个分类、与源文件一致的规范化 hash、真实草稿回执，`saved=false`、`confirmation_required=true`。未调用确认工具。
- Agent 配置 **v0.2.30** 已发布成功，正式 Web 渠道于北京时间 **2026-10-13 13:06:15** 提交学校审批，**13:10:06** 审批通过。渠道页已核对 **Web 运行中 / v0.2.30**。
- 正式独立新会话上传同一公开样例后，44.497 秒完成附件读取与学分预览，返回 31 个分类、与源文件一致的规范化 hash 和新草稿回执，明确尚未保存、等待下一轮确认。没有确认保存样例。正式渠道只显示回答，草稿中的真实工具回包已另行核验，二者分别记录。
- 本次没有云端部署、SQL、权限、身份、课表或日历改动，也未确认保存合成报告或覆盖个人报告。

## 工作流配置

```text
Start
  attachment_url: String，必填
    ↓
Code（Python）
  代码：degree_attachment_reader.py 的 handler
  输入：attachment_url 引用 Start.attachment_url
  输出：result: String
    ↓
End
  result 引用 Code.result，直接返回变量
```

代码节点超时 30 秒、重试 0 次。读取器自身限制单次连接 5 秒、总读取 15 秒、正文 128 KiB；拒绝重复 JSON 键、非有限数、额外身份/课程字段、非 UTF-8 和截断内容。

代码源 SHA-256：`57db6fcc6e0c220a0483d06c5aeb471f3a10d6918f6d0ad3197b005a321a0356`。学校节点使用同一份标准库代码，未调用外部解析服务。模型保留 `doubao-seed-2-1-lite`，原 22 个插件工具及 5 个工作流保留，只新增本工作流。

实际应用 `degree-progress-attachment-fit-live.txt` 替换原学分尾块；完整提示词清理多余空行后为 65,450 UTF-8 字节，非学分正文逐字比较一致。`json-attachment-agent-rule.txt` 是详细接入说明，不应再叠加到接近平台长度上限的完整提示词。

`result` 是 JSON 字符串。成功包含 `ok`、完整 `report_json`、`module_count` 和 `payload_hash`；失败返回固定 `error`，不得编造或补齐正文。只允许本轮真实学校附件端点，不接受任意网站、重定向、浏览器凭据或由模型提供的下载器。

reader 的 `payload_hash` 用于完整性核对，**不是导入草稿凭证**。必须调用现有 `preview_my_degree_import` 取得真实 `draft_id`、`payload_hash`、预览与替换提示；本人下一轮明确确认后，才能走原 `confirm_my_degree_import`。读取和预览都不能声称已保存。

## 已通过的合成附件验收

- 源文件：`fixtures/degree/degree-progress-attachment.demo.json`。
- 内容：公开虚构专业、31 个虚构模块；无真实姓名、学号、成绩、身份或私人数据。
- UTF-8 长度：7,252 字节。
- 预期模块数：31。
- 预期规范化 payload SHA-256：`2d1c9647b57ccb9a951278ad663ba9661f8fe0e0c657ef6b674e4fe10f03abcc`。
- 该 hash 是排序键、紧凑分隔符、保留 Unicode 的 JSON 对象规范化摘要，不是原始文件字节摘要，也不是带后端计算字段的预览摘要。
- 本记录不保存学校附件的实际签名 URL、存储键或访问凭据。

## 手工复现与发布门槛

1. 在学校主 Agent 草稿确认已绑定上述 v0.1.0 工作流，使用本次的完整替换块 `degree-progress-attachment-fit-live.txt`。只替换原学分尾块，不追加冗余规则，不动其他模块。
2. 上传上述公开合成 JSON，要求“只读取附件并生成学分预览，不确认保存”。
3. 核对调用使用本轮实际附件地址；工作流 `ok=true`、模块数 31、规范化 hash 与上文一致，读取器完整保留源正文。
4. 核对 Agent 继续实际调用本轮身份签名和 `preview_my_degree_import`，将完整 `report_json` 字符串传入；规范化 hash 必须与源文件一致，不能遗漏或补造字段、截断或二次编码。模型传参可改变等价 JSON 的空白格式，不应据此判为字段变化。不能停留在“准备读取”的文字承诺。
5. 核对实际预览返回 `saved=false`、真实 `draft_id/payload_hash`，分类内容完整，并明确任何替换提示。**不对合成报告确认保存。** 原个人报告和版本不得因测试变化。
6. 对不存在、过期或非白名单地址，以及不完整/非学分 JSON，必须如实返回失败，不读取任意网站、不用历史正文兜底、不补造学分。
7. 正式 Agent 只能在草稿附件到预览验收通过后发布；发布后仍需正式会话回归，并记录实际版本与结果。

## 失败降级

工作流读取失败时说明实际错误，不将全部问题笼统称为“安全限制”。指导用户在本机用记事本打开 `degree-progress.json`，全选、复制全部正文并粘贴到聊天；仍须验证完整 JSON 后按原流程预览、本人下一轮确认保存。降级不是自动保存，也不应被当作附件功能已通过的证据。

## 发布证据与提交

- PR：<https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/22>；实现提交 `e795263` 已推送，最终验收记录会随同一 PR 更新。
- 本机截图（`dist/` 忽略，不提交私人页面历史）：`agent-v0.2.30-published-20261013.png`、`degree-attachment-formal-preview-20261013.png`。
- 本次仅验收公开合成附件读取和预览。没有将样例保存为个人报告；不将此结果表述为所有账号、所有报告或所有问答均已验证。

该交接记录对应本次实际版本和结果；旧日志中的未接入附件限制保留为历史记录。
