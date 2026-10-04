# D 接手复核：2026-10-02

## 范围与版本

- 独立接手分支：`codex/d-takeover-20261002`。
- 基线：`f6fe20977d60fbc85871bd07e52c810c5d399960`，来自 D 的远程接手分支。
- 原工作区已有修改保留；本轮未重新部署、修改公网开关、读取服务令牌或发布主 Agent。
- 用户告知校内网站恢复并要求继续操作。本轮结果仅反映以下实际检查，不沿用历史成功作为当前验收。

## 本地回归

在 `backend` 使用独立 `.venv` 和仓库 `requirements.lock`：

```text
.venv\Scripts\python.exe -m pytest -q
退出码：0，275 项全部通过。
1 个第三方弃用警告：starlette TestClient 使用 anyio.abc.BlockingPortal 别名。

.venv\Scripts\python.exe -m pytest -o addopts= --collect-only -q
275 tests collected
```

没有重跑前端或扩展构建。初始检查时未做学校工具调用；同日后续工作流验证见下文。

## 云端前置检查

检查既有 MCP 地址：
`https://nku-campus-mcp-probe-308235-6-1467707525.sh.run.tcloudbase.com/mcp`。

使用 `backend/scripts/preflight_mcp_auth.py`，不读取真实令牌。

| 项目 | 实际结果 |
|---|---|
| 开始时间 | 2026-10-02T15:10:05+08:00 |
| 健康检查 | 未通过 |
| HTTP 状态 | 未收到，`null` |
| 耗时 | 5544.54 ms |
| 错误类别 | `connect_error` |
| 无/错 Bearer 检查 | 健康门禁未通过，未执行 |
| 正确令牌/业务检查 | 未执行 |

不能仅凭此结果认定云服务已宕机、学校会话导致错误或需要重新部署。需要恢复腾讯云登录后只读核对现有服务状态和相关日志。

## 初始浏览器阻塞（后续已恢复）

学校标签页仍显示旧的“无法访问此站点”。接管该标签页时浏览器明确返回安全策略拒绝，要求不得通过其他浏览器或间接方式绕过；因此未继续导航或操作学校页面，已请用户手动重新打开并登录。

浏览器盘点显示腾讯云标签页在登录页；未操作认证信息。

待用户恢复页面后：

1. 核对学校主 Agent 草稿与云服务当前可用性；会话过期先重新打开，需要登录则交给用户，不反复诊断登录失效。
2. 服务健康通过后再核对鉴权、探针和必要业务调用。
3. 检查平台实际代码节点、变量映射能力，再制作确定性课表参数工作流；当前没有创建工作流，节点语言与调用能力尚未验证。
4. 保留此前完整课表长 JSON 传参失败，不在服务端补括号、不放宽契约、不以模型回答替代真实 Input/Output。

初始状态：本地回归 `LOCAL_PASS`；当时云/学校前置检查未通过，尚无新 `PLATFORM_PASS`。以下后续记录取代此处的等待登录状态。

## 同日后续：入口恢复，确定性工作流部分平台通过

用户手动打开学校新标签页并完成登录，腾讯云也恢复登录。没有绕过旧错误页安全限制。学校主 Agent 草稿的七个绑定和原提示词读回保持不变；未发布主 Agent。

### 云端只读检查

- 既有服务 `nku-campus-mcp-probe`，环境 `sunner-wang-d8ght8niaaaea70b7`。
- 控制台显示 005 正常、100% 流量，旧版本保留；实例数量在检查期间从 0 到服务配置可见 1，未人工调整实例策略。
- 公网默认 HTTPS 仍开启，内网地址仍关闭；没有修改开关、环境变量或令牌，也没有重新部署。
- 第二次脚本检查 15:16:01+08:00 超时，30108.79 ms，无 HTTP 状态。
- 浏览器健康页到达 CloudBase 测试域名“风险提醒”。用户明确允许点击“确定访问”，确认后仍显示提示页，不能仅凭点击称健康通过；未移除提醒、未变更域名或保护措施。
- 控制台最近一小时日志实际出现 15:32:46、15:33:26 `GET /__tcb_probe__` 200 OK；服务于 15:17:20 完成启动。这些日志不等于浏览器已显示 `ok`，也不足以归因早前失败。
- 因日志出现新成功证据，再跑独立前置脚本，退出码 0：

| 检查 | 开始时间（+08:00） | HTTP | 耗时 | 结果 |
|---|---|---|---|---|
| readiness（精确响应 `ok`） | 2026-10-02 15:43:38 | 200 | 203.41 ms | PASS |
| missing_token | 2026-10-02 15:43:39 | 401 | 56.84 ms | PASS |
| wrong_token（随机无效值） | 2026-10-02 15:43:39 | 401 | 143.71 ms | PASS |

没有读取真实令牌，未将该检查当作正确令牌或业务工具调用通过。

### 确定性课表工作流

在团队工作区创建独立未发布草稿 `WF_D06_TimetableFixture_Test`，ID `davll3d4shhbpg8v1lm0`，0 个智能体引用。仅固定公开虚构夹具 `timetable.demo`，不接收个人数据、不保存课表、不使用大模型生成参数。新建时多出的空代码模板节点已撤除，保留实际代码01；已有业务配置未删除。

仓库代码与测试：`deploy/genios-workflows/`。本地 VM 测试完整对象、单次序列化、1606 字符、重复稳定、未知标识拒绝全部通过。

| 平台测试 | 实际结果 |
|---|---|
| 代码节点 `timetable.demo` 单步 | 266 ms，成功；完整输出与仓库 JSON.stringify 结果相同 |
| 代码节点 `unknown-fixture` 单步 | 91 ms，失败；`UNKNOWN_FIXTURE: only timetable.demo is supported` |
| 代码节点正常重复单步 | 262 ms，成功；输出仍精确相同 |
| Start→代码01→End 正常整体 | 93 ms（代码65 / End11），成功；query_json 精确1606字符 |
| 纯生成链未知标识 | 93 ms（代码75），失败；End 未执行，无成功输出 |
| 纯生成链正常重复 | 88 ms（代码70 / End8），成功；query_json 精确相同 |

精确比较使用平台可见输出文本，不读取隐藏状态。输入中的真 null、[] 和中文原样保留。首次 End 校验提示在配置更新后消失，无需放宽类型或在服务器补括号。

### 插件直连：会话恢复后端到端通过

在同一测试草稿添加既有已发布 `campus-tools-dev / platform_validate_timetable`，将生成节点的 query_json 直接作为变量引用；启用“校验 isError 作为异常”，异常忽略保持“无”。执行边变为 Start→代码01→插件01→End；End.result 引用插件 structuredContent Object。

试运行含插件链路时平台出现 Network Error；按用户此前关于会话过期的要求重新打开，实际跳到统一身份认证 IAM。已请用户重新登录；**没有完整插件调用结果，最后配置是否全部保存仍需登录后读回**。不能签收 D06 完成，也不能把0 Tokens纯生成成功当作后端成功。

用户随后完成登录，一键登录返回IAM首页后正常打开工作流。读回发现插件选择及isError开关已保存，但执行边和输入/End映射仍为纯生成链，说明会话过期期间后续修改没有保存。已重新配置，完成以下实测并刷新读回持久化。

| 完整插件链测试 | 总耗时 | 工具耗时 | 实际结果 |
|---|---|---|---|
| `timetable.demo` | 499 ms | 404 ms | PASS；输入精确1606字符，isError=false，Envelope ok=true/error=null |
| `unknown-fixture` | 94 ms | 未执行业务节点 | FAIL_CLOSED；代码75 ms失败，插件和End无执行结果 |
| `timetable.demo` 重复 | 444 ms | 344 ms | PASS；实际输入仍精确相同，响应data与首轮一致 |

首轮响应 `meta.request_id=b75b29f0-a1c4-4035-9c34-336c985906ba`；重复响应 `da9be863-55b4-4e62-8fb7-69159108df0b`。两个request_id应各自唯一，不要求整个Envelope逐字相同。

两轮 payload_hash 都是：

```text
643fef057c3c6503a888a84727f2f9d7a497558b37b0087d6887b3973f725335
```

normalized_payload与原始夹具完整比较一致；issues为空数组，coverage.complete/term/[1,2,3,4]，meta.schema_version=1.0.0/data_version=demo-v1/calculation_version=time-v1、DEMO_DATA警告保留。End.result返回真实structuredContent，不由模型改写。

云日志只读复核：15:54:51及15:55:52有`platform_validate_timetable`的`tools/call`，protocol_version=2025-06-18，outcome=ok，耗时分别5.66/4.16 ms，POST /mcp 200。日志的request_id=2是JSON-RPC调用编号，不等于Envelope UUID；按工具、时间和流程关联，不把两者强行等同。未知标识测试期间平台仍可能做初始化/握手，不能把“业务节点未执行”误写为“完全没有网络请求”。

刷新读回：三条边Start→代码01→插件01→End持久化，插件query_json引用代码01/query_json、isError开关1、异常忽略无，End.result引用插件01/structuredContent Object。工作流仍未发布、0智能体引用。

当前边界：完整测试工作流 `WORKFLOW_MCP_PASS`，但主Agent未绑定此工作流、没有新一轮主Agent课表测试；D06不能据此全部签收。已向负责人询问是否允许仅发布该固定虚构课表工作流到团队工作区，并绑定主Agent测试草稿；不会发布主Agent、上架公众、接入个人数据或新部署云服务。

下一步：获确认后发布指定测试工作流→绑定测试草稿→验证实际workflow/tool Input/Output和main-Agent边界，再更新D06结论。

## 同日最终续步：获授权发布测试工作流，主Agent课表链通过

负责人明确回复“允许发布测试工作流并绑定草稿”，限定团队测试工作流、主Agent测试草稿，不发布主Agent、不上架、不接个人数据、不新部署云服务。

平台发布操作返回“发布成功”；工作流列表显示2026-10-02 16:01:33已发布，版本输入为v0.1.0。主Agent草稿新增指定工作流绑定，保留原七工具、其他约束，在提示词追加固定夹具工作流路由：不模型抄写长JSON、未知标识原样失败、不兜底改成演示、按真实result回答、不导入保存。刷新读回绑定及提示词，草稿保存16:04:11。

| 主Agent测试 | 实际Input/Output与回答 | 结果 |
|---|---|---|
| 16:04:54 明确固定演示课表校验 | 工作流Input fixture_id字符串timetable.demo；Output result.ok=true/error=null、正确payload_hash；真实request_id `a15f61f5-d785-47c7-a3c0-b6e49e7f60f3`；回答同ID、覆盖term第1–4周、虚构非个人、未导入保存 | PASS |
| 16:06:36 指定unknown-fixture异常 | 实际Input原样unknown-fixture；工作流代码UNKNOWN_FIXTURE失败；平台显示执行错误，不给成功结果或前轮request_id | FAIL_CLOSED |
| 16:07:30 自然提问再次校验固定演示课表（不指定工作流名称） | 实际调用同工作流，Input timetable.demo；Output正确payload_hash/ok=true；真实request_id `fce5fc18-b243-4dbc-8837-e3f41a3456b3`；回答同ID且非个人/未保存 | PASS |
| 16:09:09 要获取真实个人课表且未选演示 | 没有工作流调用卡，拒绝获取/保存；但拒绝表述误提“需要密码/Cookie”，未索取信息，记录为需修正的文案 | BOUNDARY_OK / WORDING_REPAIR |
| 16:09:58 修正后复测个人课表能力 | 无工具调用；明确当前未接可信身份与授权接口，无法获取/保存，无需密码/Cookie/验证码，演示不是替代品 | PASS |

个人数据修正仅追加提示词边界，不更改权限或实现个人数据读取。平台“已完成”不代表业务成功：未知标识为真实失败；当前显示通用执行错误，未隐藏/改写成成功，但错误展示体验仍可后续改善。

结论：固定虚构课表确定性JSON链 `WORKFLOW_MCP_PASS` + 主Agent草稿课表链 `MAIN_TIMETABLE_PASS`。历史长课表JSON损坏缺口已由确定性代码节点+变量引用解决，不是放宽后端校验。**不能据此称本轮其他五类主Agent回归、真实个人数据、持久数据库、任务写入、知识库或整个项目上线已完成。**

本轮只发布已确认的测试工作流、修改主Agent草稿绑定/路由提示词；没有主Agent发布/上架、云部署、开关变更、令牌读取、main合并、Git提交/推送或新PR。公网保持原用户要求持续开启。

截图（本地 ignored dist，不自动上传）：

- `dist/d06-platform-20261002/cloudbase-domain-notice.png`
- `dist/d06-platform-20261002/code-node-repeat-success.png`
- `dist/d06-platform-20261002/workflow-success.png`
- `dist/d06-platform-20261002/workflow-unknown-rejected.png`
- `dist/d06-platform-20261002/workflow-repeat-success.png`
- `dist/d06-platform-20261002/mcp-workflow-unknown-rejected.png`
- `dist/d06-platform-20261002/mcp-workflow-success.png`
- `dist/d06-platform-20261002/workflow-published.png`
- `dist/d06-platform-20261002/main-agent-workflow-success.png`
- `dist/d06-platform-20261002/main-agent-unknown-rejected.png`
- `dist/d06-platform-20261002/main-agent-natural-repeat.png`
- `dist/d06-platform-20261002/main-agent-personal-boundary.png`
