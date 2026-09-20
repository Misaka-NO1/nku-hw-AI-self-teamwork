# 后端与 MCP 基座

本目录对应 D Agent 的 D01–D03 范围。REST API 与 MCP 是两个独立入口：

- REST：`python -m app.main`，默认监听 `127.0.0.1:8000`
- MCP：`python -m app.mcp.http`，默认监听 `127.0.0.1:8001/mcp`

## 本地运行

在 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
Copy-Item ..\deploy\.env.example .env
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m app.main
```

另开一个终端启动 MCP：

```powershell
.\.venv\Scripts\python -m app.mcp.http
```

对正在运行的 Streamable HTTP 服务做真实传输探针：

```powershell
$env:MCP_PROBE_URL='http://127.0.0.1:8001/mcp'
.\.venv\Scripts\python scripts\probe_mcp_url.py
```

当前阶段默认 `AUTH_MODE=demo_fixture` 且 `ALLOW_PERSONAL_UPLOADS=false`。不要把真实令牌写入仓库；真实平台地址和凭证由部署人员通过环境变量注入。

## D04/D05 本地写入流程

当前云端写入只接受 `fixtures/` 中的固定虚构数据，数据集 ID 为 `demo-v1`。即使客户端填写 `dataset_kind=demo`，只要规范化内容 hash 不在夹具白名单中，服务端仍返回 `DEMO_ONLY`。

1. `POST /api/v1/demo/workspaces` 创建短期虚构工作区；响应设置 HttpOnly 会话 Cookie，并返回 CSRF 值。
2. 浏览器写请求在 `X-CSRF-Token` 中携带该值。
3. 扩展上传课表前，由浏览器调用 `POST /api/v1/import-tickets` 获取一次性、限 `schedule_import` 的票据。
4. 扩展用 `Authorization: ImportTicket <token>` 调用 `POST /api/v1/schedules/import-drafts`。令牌原文只返回一次，数据库只存 hash。
5. 草稿经 `POST /api/v1/confirmations` 绑定 owner、revision 和 payload hash。
6. 受控工具页调用 `/api/v1/schedules/commit` 或 `/api/v1/tasks/commit`。同一幂等键重试返回同一资源，不会重复写入。

`workspace_ref`、draft ID、MCP session ID 和客户端自由填写的用户 ID 都不是身份凭据。
