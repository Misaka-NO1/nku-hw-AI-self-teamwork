# D03 平台探针证据

## 当前结论

2026-09-28 交接更新：用户提供的《D同学_腾讯云后端交接.md》报告 CloudBase 环境 `sunner-wang-d8ght8niaaaea70b7` 已有一个私有 `nku-campus-mcp-probe` 002 版，`BUILD_ID=cloudbase-probe-20260928-002`，容器健康检查曾在云端日志得到 200，公网关闭；这些是交接文档的报告，**本次尚未登录控制台独立核验**。当前代码补齐了同路径的精确 GET 健康检查及回归，重建了候选部署包，但未替换云端 002、未开启公网、未进行平台调用。仍为 `WAITING_HUMAN`，不能因容器健康检查成功升级为 `PLATFORM_PASS_DEMO`。

候选代码提交 `b91ca41` 已推送到 `origin/codex/d-mcp-local-readiness`，尚未 PR/合并或云端构建。2026-09-28 从当前对话打开腾讯云控制台时被重定向到登录页，未能现场查看版本、运行配置、鉴权开关或日志；等待用户接管登录后再核验，不填写猜测值。

同日收到 `cloudbase-mcp-20260928-001612(1).zip`，SHA-256 为 `C43740DC868192BD14359D59D95070EF29866E9A2F11D9FDE7BB4E3AF84C24FB`。只读检查：ZIP 共含根目录 Dockerfile、锁定依赖与 37 个 Python 源文件，无 `.env`、密钥或部署元数据。依赖和 34 个 Python 文件与当前候选版相同；差异为 `main.py`（候选版启动时增加部署校验）、`config.py`（候选版严格校验 HTTPS URL/路径）及 `mcp/http.py`（候选版增加 Host/Origin 限制，保留相同的精确 GET 健康探针与 Bearer 认证），另有 Dockerfile（候选版显式设置 staging、8080、鉴权并使用非 root 用户）。ZIP 的 Dockerfile 没有这些默认值；其实际云端安全性取决于未附带的环境变量，不能只凭源码判断。该 ZIP 被视为交接资料，未执行其中的代码，也不能证明正在运行的 002 镜像与它完全一致。

根据仓库候选代码本地生成新的源码上传包（`deploy/cloudbase-mcp/Build-Package.ps1`）：39 个预期条目，无缺失、额外或重复；本次 ZIP SHA-256 为 `3927AA2D72B2D42FF384C78E117D010EFF5C68F373DF65BE0785C0026D37CF6E`，文件保留在本机忽略提交的 `deploy/cloudbase-mcp/dist/`。复跑 `deploy/Test-Local.ps1`：依赖检查通过、120 项后端测试通过、真实本地 REST/MCP 联调 `LOCAL_PASS`。没有本机 Docker 构建、云端部署或 NK-GeniOS 调用证据。

2026-09-27 更新：仍为 `WAITING_HUMAN`（仅指云端/学校平台）。已完成指南第一阶段本地搭建与复测，详见 [本地证据](D03-local-readiness-2026-09-27.md)。用户表示已有云服务器，尚待环境详情；未执行云端部署或真实平台调用。以下 2026-09-20 记录是历史基线，不能用旧日期的“暂不部署”描述替代当前已获授权的本地准备工作。

`WAITING_HUMAN`（用户于 2026-09-20 明确选择暂不部署）

截至 2026-09-20，只完成本地 REST/MCP 代码、认证拒绝测试和官方 SDK 客户端验证。没有真实服务器地址、HTTPS 域名、NK-GeniOS 登录环境、空间或插件配置权限，因此没有执行平台真实调用，也没有生成平台通过结论。

需要人工提供：平台账号、正确工作空间、唯一主 Agent 标识、允许使用的部署环境、HTTPS 地址、DNS/TLS 权限、平台密钥配置权限，以及平台实际支持的 Bearer/API Key 方式。

## 本地证据

- SDK：`mcp==2.2.0`，锁定于 `backend/requirements.lock`
- 传输：Streamable HTTP
- MCP 路径：`/mcp`
- 已发现工具：`health_probe`
- 返回字段：`nonce`、`build_id`、`server_time`
- 错误输入：空 nonce 被拒绝
- 认证失败：缺失或错误 Bearer 令牌返回 401
- 本地自动测试：23 项通过（含后续 D04/D05 安全与事务回归）
- 当前 `AUTH_MODE`：`demo_fixture`
- 个人数据开关：关闭

本地 Streamable HTTP 实测（不等于平台通过）：

| 项目 | 本地结果 |
|---|---|
| 地址 | `http://127.0.0.1:8766/mcp`，仅临时本机测试 |
| 协商协议版本 | `2025-11-25` |
| 未携带服务令牌 | HTTP 401 |
| 携带正确 Bearer | 工具发现和调用成功 |
| 工具清单 | `health_probe` |
| nonce | 随机生成，返回一致 |
| 日志字段 | method、protocol_version、request_id、tool_name、duration_ms、outcome；不记录令牌和参数正文 |

## 获得权限后填写的真实记录

| 字段 | 真实值 |
|---|---|
| 执行时间 | 待填 |
| 平台空间 | 待填 |
| 主 Agent 标识 | 待填 |
| 部署 build_id | 待填 |
| MCP HTTPS 地址（无秘密） | 待填 |
| SDK 版本 | `2.2.0`，待与平台实测组合确认 |
| 平台协商协议版本 | 待实测 |
| 认证类型 | 待实测 |
| 工具发现结果 | 待实测 |
| 随机 nonce | 待实测 |
| nonce 返回值 | 待实测 |
| 服务端 request_id | 待实测 |
| 调用耗时 | 待实测 |
| 失败阶段与脱敏错误 | 待实测 |
| 平台证据文件/截图 | 待实测；不得包含密钥 |

只有主 Agent 真实完成一次 `health_probe`，且 nonce 与 build_id 对得上，状态才可从 `WAITING_HUMAN` 改为 `PLATFORM_PASS_DEMO`。
