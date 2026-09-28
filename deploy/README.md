# D03：HTTPS 与 NK-GeniOS 接入方案

当前状态（2026-09-28）：本地第一阶段及 CloudBase 探针候选部署包已准备；云端/学校平台端到端仍为 `WAITING_HUMAN`。后续交接文档说明当前没有 CVM 或轻量服务器，已有 CloudBase 私有探针 002（未由当前会话独立核验），公网关闭。本次不更新现有云端版本、不开启公网，也不得写成“已接通平台”。下面以“普通持久主机”为前提的历史方案不应直接套到 CloudBase；CloudBase 专项说明见 [`cloudbase-mcp/README.md`](cloudbase-mcp/README.md)。

本次可复测入口、服务器信息表和验收步骤见 [`PREPARE-AND-TEST.md`](PREPARE-AND-TEST.md)。部署保密配置从 [`.env.staging.example`](.env.staging.example) 开始填写，不能直接使用空白模板。

## 部署边界

- REST 进程运行 `python -m app.main`，内部默认地址 `127.0.0.1:8000`。
- MCP 进程运行 `python -m app.mcp.http`，内部默认地址 `127.0.0.1:8001/mcp`。
- 公网入口必须是有效 HTTPS；`/healthz`、`/readyz` 与 `/mcp` 是不同端点。
- MCP 使用官方 SDK 的 Streamable HTTP。不能把 REST JSON 地址填成 MCP 地址，也不能用浏览器打开 `/mcp` 的结果代替官方客户端测试。
- 生产或预发布环境必须设置 `MCP_REQUIRE_AUTH=true`，并在服务器保密变量和 NK-GeniOS 保密字段中配置同一服务凭据。凭据不得进入 Git、前端、扩展、群聊或截图。
- 首版只有一个后端实例和一个 SQLite 持久卷。多实例部署在数据库迁移前禁止启用。

## 人工需要先确定的内容

以下内容没有提供，Coding Agent 不自行猜测：

1. CloudBase 作为后端托管已由交接同学选用；赛事是否允许外部服务及 NK-GeniOS 是否能访问仍待真实确认。
2. CloudBase 目标服务的变更权限、实际 HTTPS 路由与公网开关权限。
3. NK-GeniOS 的账号、正确空间、唯一主 Agent 标识及插件配置权限。
4. 平台已观察到 Bearer 等选项；仍需在正确比赛空间验证字段如何生成 Authorization 请求头及真实调用。
5. SQLite 持久卷目录、备份位置和数据保留要求。

## 获得上述信息后的部署步骤

1. 在目标环境按 `backend/requirements.lock` 安装 Python 3.12 依赖。
2. 从 `deploy/.env.example` 创建服务器保密配置；填入真实 `BUILD_ID`、`MCP_PUBLIC_URL`、`APP_ORIGIN` 和随机服务令牌。
3. 设置 `APP_ENV=staging` 或 `production`、`MCP_REQUIRE_AUTH=true`，保持 `AUTH_MODE=demo_fixture` 和 `ALLOW_PERSONAL_UPLOADS=false`。
4. 给 SQLite 文件配置持久卷，仅运行一个后端实例；启动 REST 与 MCP 两个进程。
5. 由反向代理终止 TLS，并把 REST 路径转发至 8000、准确的 MCP 路径转发至 8001。代理不得缓冲或截断 Streamable HTTP 响应。
6. 从外部检查 HTTPS 证书、`/healthz`、`/readyz`；再设置 `MCP_PROBE_URL`、与部署一致的 `MCP_PROBE_EXPECTED_BUILD_ID` 和保密注入的 `MCP_PROBE_TOKEN`，运行 `backend/scripts/probe_mcp_url.py` 做工具发现和 `health_probe` 调用。报告须 `ok=true` 且进程退出码为 0。
7. 在 NK-GeniOS 中进入 `插件 → 自定义插件 → 接入 MCP 插件`，选择 Streamable HTTP，填写完整 MCP HTTPS URL 和平台保密认证字段。
8. 只有发现 `health_probe` 后，才把该插件绑定到唯一主 Agent。用随机 nonce 发起真实工具调用，并对照服务端协议版本、方法、request_id、build_id 与耗时日志。
9. 将脱敏后的真实结果填入 `docs/evidence/platform/D03-platform-probe.md`。连接后 0 个工具、只有聊天文本或只有本机测试都不算平台通过。

## 失败诊断顺序

| 现象 | 首查内容 |
|---|---|
| 本地健康检查失败 | 进程、端口、环境配置、SQLite 目录 |
| 平台连接超时 | TLS、云端可达性、反向代理、平台出站限制 |
| 401/403 | 平台认证类型、Bearer 前缀、密钥匹配；不要用关闭认证作为生产修复 |
| 404/405 | 完整 MCP 路径、重定向、实际请求方法 |
| 连接后 0 工具 | MCP 协议协商、工具注册、Schema、插件绑定 |
| 工具可见但调用失败 | 参数 Schema、超时、输出映射和服务日志 request_id |
