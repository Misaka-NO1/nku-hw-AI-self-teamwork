# D03 平台探针证据

## 当前结论

2026-09-28 现场更新：用户批准只更新 CloudBase 上海环境 `sunner-wang-d8ght8niaaaea70b7` 中的 `nku-campus-mcp-probe`，并明确要求继续关闭公网。现已将仓库提交 `b7f3baef6b0b21f18a01a5bc172d8c3edb27529f` 对应的候选 ZIP 发布为部署 `003`（任务 `2251206`）。控制台显示 `003` 状态“正常”、流量 100%；旧 `002` 仍在部署版本列表且“回退”按钮可用。服务端口 8080，实例最小 0、最大 1；核对时 `003` 有 1 个实例，后续可按原配置缩到 0。默认公网域名和内网默认地址均保持关闭，自定义域名未配置。此时**不能从外部访问 MCP**，D03 仍为 `WAITING_HUMAN`，不得写作 `PLATFORM_PASS_DEMO`。

本次上传包 `deploy/cloudbase-mcp/dist/nku-campus-mcp-probe-20260928-202913.zip` 含 39 个文件，上传前逐文件与仓库源码 SHA-256 一致；ZIP SHA-256 为 `C37A3EA1E9E570EBA3F74FAA5BCFE9A0FC63FC64ADEA6A6CDB3F63C72F04B104`。新版本在控制台配置 `APP_ENV=staging`、`MCP_HOST=0.0.0.0`、`MCP_PORT=8080`、`MCP_PATH=/mcp`、`MCP_PUBLIC_URL=https://nku-campus-mcp-probe-308235-6-1467707525.sh.run.tcloudbase.com/mcp`、`MCP_REQUIRE_AUTH=true`、`BUILD_ID=cloudbase-probe-20260928-b7f3bae-secure`、`AUTH_MODE=demo_fixture`、`ALLOW_PERSONAL_UPLOADS=false`。`MCP_SERVICE_TOKEN` 使用 48 字节安全随机数生成并写入云端环境变量；**不在证据文档记录令牌值**。云端列表可见以上 10 个变量键且值被遮蔽。没有配置数据库或云开发 API Key 注入，也没有更改同环境的其他服务、数据库或域名路由。

部署详情记录 `003` 于 2026-09-28 20:58:30 开始，状态“正常”；容器日志于 21:00:49 显示 MCP Streamable HTTP 会话管理器及应用启动完成，21:00:51～21:00:52 的 `GET /__tcb_probe__` 返回 `200 OK`。这只证明云端新容器通过内部健康探针；公网关闭期间尚未验证无令牌/错误令牌 401、有效 Bearer 的 SDK 初始化和 `health_probe`，也未在 NK-GeniOS 由主 Agent 调用。下一步必须由用户**另行批准开启默认域名公网入口**，再立即做上述鉴权和端到端联调；不得以内部探针代替外部验收。

## 历史准备记录

2026-09-28 交接更新：用户提供的《D同学_腾讯云后端交接.md》报告 CloudBase 环境 `sunner-wang-d8ght8niaaaea70b7` 曾有一个私有 `nku-campus-mcp-probe` 002 版，`BUILD_ID=cloudbase-probe-20260928-002`，容器健康检查曾在云端日志得到 200，公网关闭；这些是交接文档的历史报告。现已登录控制台并核对服务列表，但未打开版本详情。当前代码补齐了同路径的精确 GET 健康检查及回归，重建了候选部署包，但未替换云端 002、未开启公网、未进行平台调用。仍为 `WAITING_HUMAN`，不能因历史容器健康检查成功升级为 `PLATFORM_PASS_DEMO`。

候选代码提交 `b91ca41` 已推送到 `origin/codex/d-mcp-local-readiness`，尚未 PR/合并或云端构建。2026-09-28 首次打开腾讯云控制台时被重定向到登录页；用户稍后完成登录，见下段现场核对，不填写仍不可见的配置猜测值。

用户登录后，同日只读进入 CloudBase 开发平台环境 `sunner-wang-d8ght8niaaaea70b7`。云托管服务管理列表仅显示 1 个服务 `nku-campus-mcp-probe`，运行状态为**已暂停**，公网访问为**不允许**。这是控制台现场状态，比交接文档的历史描述更新；未确认暂停原因。当前浏览器中点击服务名称未打开详情，故未核实版本 002、镜像、端口、环境变量、日志或探针响应。未恢复服务、更新版本、上传文件或改变公网设置；平台结果仍为 `WAITING_HUMAN`。

进一步通过键盘进入服务详情及部署版本页后确认：002 版状态**正常**，分配 100% 流量，但当前实例数为 0、实例列表为空；001 版也存在但不承载流量。服务监听端口设为 8080，运行模式为始终自动扩缩容、最小实例 0、最大 1。控制台显示“已暂停”与[官方文档所述空闲缩容到 0](https://docs.cloudbase.net/run/deploy/configuring/autoscaling/about-instance-autoscaling)相容，不能据此断定部署故障或需要强制重启。默认公网域名与内网默认地址均关闭，自定义域名列表为空，因此当前没有可用的外部 MCP 联调入口。环境变量列表仅显示 `APP_ENV`、`MCP_HOST`、`MCP_PORT`、`MCP_PATH`、`BUILD_ID` 五个键（值均隐藏）；未见 `MCP_REQUIRE_AUTH` 或 `MCP_SERVICE_TOKEN`，在未证实实际镜像鉴权前严禁开启公网。002 部署详情显示状态正常，但未重新执行云端健康检查或 MCP 调用。用户授权“恢复”后未擅自将最小实例改成 1，因为这会改变自动扩缩容与持续费用，却不能在公网关闭时完成外部联调；用户随后选择先准备安全接入并保持现有自动缩容配置。

同日收到 `cloudbase-mcp-20260928-001612(1).zip`，SHA-256 为 `C43740DC868192BD14359D59D95070EF29866E9A2F11D9FDE7BB4E3AF84C24FB`。只读检查：ZIP 共含根目录 Dockerfile、锁定依赖与 37 个 Python 源文件，无 `.env`、密钥或部署元数据。依赖和 34 个 Python 文件与当前候选版相同；差异为 `main.py`（候选版启动时增加部署校验）、`config.py`（候选版严格校验 HTTPS URL/路径）及 `mcp/http.py`（候选版增加 Host/Origin 限制，保留相同的精确 GET 健康探针与 Bearer 认证），另有 Dockerfile（候选版显式设置 staging、8080、鉴权并使用非 root 用户）。ZIP 的 Dockerfile 没有这些默认值；其实际云端安全性取决于未附带的环境变量，不能只凭源码判断。该 ZIP 被视为交接资料，未执行其中的代码，也不能证明正在运行的 002 镜像与它完全一致。

根据仓库候选代码本地生成新的源码上传包（`deploy/cloudbase-mcp/Build-Package.ps1`）：39 个预期条目，无缺失、额外或重复；本次 ZIP SHA-256 为 `3927AA2D72B2D42FF384C78E117D010EFF5C68F373DF65BE0785C0026D37CF6E`，文件保留在本机忽略提交的 `deploy/cloudbase-mcp/dist/`。复跑 `deploy/Test-Local.ps1`：依赖检查通过、120 项后端测试通过、真实本地 REST/MCP 联调 `LOCAL_PASS`。没有本机 Docker 构建、云端部署或 NK-GeniOS 调用证据。

用户随后选择“先准备安全接入”，并指定 CloudBase 默认 HTTPS 域名仅用于联调。本地候选代码增加非本机监听的强制 HTTPS/Bearer 校验，防止现有 `APP_ENV` 环境变量覆盖镜像默认值后以开发模式无鉴权启动；新增回归后 `deploy/Test-Local.ps1` 通过（126 项后端测试、真实本地 MCP 联调 `LOCAL_PASS`）。重新生成候选 ZIP：39 个条目逐一与仓库源文件 SHA-256 一致，ZIP SHA-256 为 `C37A3EA1E9E570EBA3F74FAA5BCFE9A0FC63FC64ADEA6A6CDB3F63C72F04B104`，保存在本机忽略提交的 `deploy/cloudbase-mcp/dist/`。具体云端配置与停止条件见 `deploy/cloudbase-mcp/SAFE-ACCESS-CHECKLIST.md`。未更改云端服务、实例下限、鉴权变量或公网入口；仍无云端 MCP/NK-GeniOS 调用证据。

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
