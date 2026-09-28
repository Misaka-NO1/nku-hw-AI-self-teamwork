# D03 CloudBase 安全接入记录（003 已私有发布，公网待授权）

本单只用于 `nku-campus-mcp-probe` 的 `health_probe` 联调。用户选择**先用 CloudBase 默认 HTTPS 域名作测试**，不作为正式生产域名；保持现有最小实例数 0，不更改其他应用、数据库、权限或域名路由。生成候选包不代表云端已更新或学校平台已接通。

## 已核对的现场基线（2026-09-28）

- CloudBase 上海环境：`sunner-wang-d8ght8niaaaea70b7`；目标服务：`nku-campus-mcp-probe`。
- 002 部署版本显示“正常”、流量 100%，当前 0 个实例；服务允许自动缩容到 0（最小 0、最大 1），端口 8080。**不要为联调而改成常驻 1 个实例。**
- 默认域名：`nku-campus-mcp-probe-308235-6-1467707525.sh.run.tcloudbase.com`，目前公网入口关闭；内网默认地址也关闭，且没有自定义域名。
- 控制台展示的环境变量键只有 `APP_ENV`、`MCP_HOST`、`MCP_PORT`、`MCP_PATH`、`BUILD_ID`；值均隐藏。尚未证实 002 的镜像鉴权配置。**绝不把 002 原样开放到公网。**
- 上述是 003 发布前的基线；发布后的现场记录见下节。

## 003 私有发布结果（2026-09-28）

- 用户批准更新此服务并确认新版本自动承接 100% 流量，要求继续关闭公网。上传包 39 个条目逐一与提交 `b7f3baef6b0b21f18a01a5bc172d8c3edb27529f` 对应源码一致，ZIP SHA-256 为 `C37A3EA1E9E570EBA3F74FAA5BCFE9A0FC63FC64ADEA6A6CDB3F63C72F04B104`。
- 云端新部署 ID `003`，任务 `2251206`，`BUILD_ID=cloudbase-probe-20260928-b7f3bae-secure`。状态“正常”、流量 100%；旧 `002` 仍在历史列表，可回退。端口 8080、最小实例 0、最大实例 1 均保持；核对时新实例数 1。
- 控制台可见下表 10 个环境变量键。服务令牌由 48 字节安全随机数生成并填入云端配置；文档不记录值。云开发 API Key 注入、个人上传和数据库接入均未启用。
- 运行日志显示会话管理器、应用启动完成，以及新版本 `GET /__tcb_probe__` 多次 `200 OK`。默认公网域名和内网默认地址均仍关闭；外部 Bearer/MCP/NK-GeniOS 联调尚未做，D03 保持 `WAITING_HUMAN`。

[腾讯云公网访问说明](https://docs.cloudbase.net/run/deploy/networking/public)明确指出云托管默认域名没有内建鉴权，必须由服务自行鉴权；[自动扩缩容说明](https://docs.cloudbase.net/run/deploy/configuring/autoscaling/about-instance-autoscaling)指出最小实例为 0 时可缩容到 0，并由新请求冷启动。

## 候选版本安全门槛

在任何云端发布或公网开关操作前，逐项确认：

1. 使用本仓库 `deploy/cloudbase-mcp/Build-Package.ps1` 生成的**新候选包**，而非交接 ZIP 或旧 002 镜像；核对 39 个文件、ZIP SHA-256 和即将发布的 Git 提交。候选 Dockerfile 只装 Python 锁定依赖与 `backend/app`，以非 root 身份运行 MCP。
2. 云端新版本明确设置下表配置。CloudBase 同名环境变量优先于 Dockerfile 默认值，因此不能只看 Dockerfile。`MCP_SERVICE_TOKEN` 必须由安全随机数产生，至少 32 字节熵，仅填入 CloudBase 与 NK-GeniOS 的保密配置；不放入仓库、ZIP、URL、命令行、日志或聊天截图。
3. 代码在 `MCP_HOST` 为非本机地址时，即使 `APP_ENV=development` 或 `test`，也必须同时有有效 HTTPS `/mcp` URL、`MCP_REQUIRE_AUTH=true` 和非空令牌，否则拒绝启动。本地回归要覆盖该条件。
4. 保留 `GET /__tcb_probe__` 的精确健康检查；`/mcp` 及错误方法/路径仍须 Bearer，不能为了通过 CloudBase 健康检查关闭认证或 Host/Origin 校验。
5. 不配置现有 PostgreSQL、业务数据、个人上传或额外工具。此候选仅提供 `health_probe`。

| 配置键 | 新版本目标值 |
| --- | --- |
| `APP_ENV` | `staging` |
| `MCP_HOST` / `MCP_PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` |
| `MCP_PUBLIC_URL` | `https://nku-campus-mcp-probe-308235-6-1467707525.sh.run.tcloudbase.com/mcp` |
| `MCP_REQUIRE_AUTH` | `true` |
| `MCP_SERVICE_TOKEN` | 云端保密配置中的新随机令牌，不在本单记录其值 |
| `BUILD_ID` | 新的、与 Git 提交和部署对应的唯一标识，不复用 `002` |
| `AUTH_MODE` / `ALLOW_PERSONAL_UPLOADS` | `demo_fixture` / `false` |

`MCP_PUBLIC_URL` 只是服务的允许地址配置；填写它**不会**开启公网。若后续控制台实际默认域名与上表不同，先更新配置并复测，不能猜测或临时关闭 Host 校验。

## 执行顺序与停止条件

1. **已完成：**用户批准更新这一项服务及自动切换流量；新版本 `003` 构建并发布，保留 `002` 回退入口和最小实例 0。
2. **已完成内部检查：**`003` 状态“正常”、端口 8080、内部探针 `200 OK`，流量 100%；只有版本“正常”或容器探针 200，**不算 MCP 连通**。
3. 用户另行批准**开启默认域名公网入口**后，立即以 HTTPS 验证：无令牌 `/mcp` 401、错误令牌 401、正确令牌可初始化与发现 `health_probe`、随机 nonce 和 `BUILD_ID` 回传正确、空 nonce 拒绝。若 401、TLS、Host/Origin 或协议检查失败，立即关闭公网并排查；不可跳过鉴权继续。
4. 最后在比赛指定的 NK-GeniOS 工作空间，以 Streamable HTTP + Bearer 保密配置接入 `/mcp`，由主 Agent 真实调用 `health_probe`。记录脱敏证据到 `docs/evidence/platform/D03-platform-probe.md`；在此之前始终保持 `WAITING_HUMAN`。

默认域名仅供短期开发联调。若 NK-GeniOS 不支持所需 Bearer 配置、不能访问该域名，或 CloudBase 代理不保留所需请求头，停止联调并报告具体证据，不用关闭安全检查“修通”。正式演示域名及业务数据库另行决定。
