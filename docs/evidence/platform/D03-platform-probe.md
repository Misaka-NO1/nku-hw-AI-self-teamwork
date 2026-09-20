# D03 平台探针证据

## 当前结论

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
