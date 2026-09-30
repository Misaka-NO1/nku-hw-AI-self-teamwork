# 后端与 MCP 基座

本目录已完成 D01–D06 的本地基座和固定演示领域适配。D03 云端探针曾由主 Agent 真实调用通过；D06 业务工具未做云端/平台验收。REST API 与 MCP 是两个独立入口：

- REST：`python -m app.main`，默认监听 `127.0.0.1:8000`
- MCP：`python -m app.mcp.http`，默认监听 `127.0.0.1:8001/mcp`

## 本地运行

在 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
if (-not (Test-Path -LiteralPath .env)) { Copy-Item ..\deploy\.env.example .env }
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
$env:MCP_PROBE_EXPECTED_BUILD_ID='dev' # 与服务端 BUILD_ID 一致
# 服务端开启鉴权时，还需通过保密配置设置 MCP_PROBE_TOKEN。
.\.venv\Scripts\python scripts\probe_mcp_url.py
```

当前阶段默认 `AUTH_MODE=demo_fixture` 且 `ALLOW_PERSONAL_UPLOADS=false`。不要把真实令牌写入仓库；真实平台地址和凭证由部署人员通过环境变量注入。

## 隔离的完整本地检查

从仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/Test-Local.ps1
```

此命令运行后端回归并启动临时 REST/MCP 实例，检查认证、官方 SDK 发现/调用、错误 build_id 拒绝，以及固定演示任务重启后持久化。临时数据库与随机令牌独立于现有 `.env`/业务库，结束后停止测试进程并清理测试数据。不修改系统执行策略。详见 [`deploy/PREPARE-AND-TEST.md`](../deploy/PREPARE-AND-TEST.md)。

## D04/D05 本地写入流程

当前云端写入只接受 `fixtures/` 中的固定虚构数据，数据集 ID 为 `demo-v1`。即使客户端填写 `dataset_kind=demo`，只要规范化内容 hash 不在夹具白名单中，服务端仍返回 `DEMO_ONLY`。

1. `POST /api/v1/demo/workspaces` 创建短期虚构工作区；响应设置 HttpOnly 会话 Cookie，并返回 CSRF 值。
2. 浏览器写请求在 `X-CSRF-Token` 中携带该值。
3. 扩展上传课表前，由浏览器调用 `POST /api/v1/import-tickets` 获取一次性、限 `schedule_import` 的票据。
4. 扩展用 `Authorization: ImportTicket <token>` 调用 `POST /api/v1/schedules/import-drafts`。令牌原文只返回一次，数据库只存 hash。
5. 草稿经 `POST /api/v1/confirmations` 绑定 owner、revision 和 payload hash。
6. 受控工具页调用 `/api/v1/schedules/commit` 或 `/api/v1/tasks/commit`。同一幂等键重试返回同一资源，不会重复写入。

`workspace_ref`、draft ID、MCP session ID 和客户端自由填写的用户 ID 都不是身份凭据。

## D06 本地只读业务接口

领域算法来自 A/B/C，D 的 `app/core/domain_adapter.py` 共用同一调度层。Schema 版本 1.0.0，AUTH_MODE=demo_fixture，个人数据关闭。

| REST | MCP |
|---|---|
| `POST /api/v1/schedules/validate` | `validate_timetable` |
| `POST /api/v1/time/free-slots` | `query_free_time` |
| `POST /api/v1/time/check` | `check_time_plan` |
| `GET /api/v1/scenic/spots` | `search_scenic_spots` |
| `GET /api/v1/study/materials` | `search_study_materials` |
| `POST /api/v1/degree/audit` | `audit_degree_progress` |

POST JSON 和 MCP arguments 直接使用同一个契约对象，不嵌套 payload/query。两个 GET 搜索使用一个 query 参数，值为该 JSON 的 URL 编码；nullable 字段必需且显式为 null。例如：

```javascript
const query = { campus_id: null, tags: [], month: null, limit: 5 };
const params = new URLSearchParams({ query: JSON.stringify(query) });
const path = `/api/v1/scenic/spots?${params}`;
// 使用已配置的 API 地址，不猜测线上域名。
```

另有 REST 详情和白名单下载：`GET /api/v1/scenic/spots/{spot_id}`、`GET /api/v1/study/materials/{material_id}`、`GET /api/v1/study/materials/{material_id}/download`。下载成功为附件文件（不是 JSON 信封）；拒绝仍为统一错误信封。无下载 MCP 工具，不接受文件路径或任意 URL。

`demo-workspace-01` 为公开只读固定虚构课表；未确认的通知草稿不会纳入忙碌时间。degree 只支持 demo-cs-plan-v1 / demo-transcript-01。浏览器随机工作区需会话 owner 校验，读已确认课表/任务，缺课表返回 NOT_FOUND，不回退成公共 demo；MCP 服务令牌不能查询这些工作区。

MCP 默认只发现 health_probe；显式 `MCP_ENABLE_DOMAIN_TOOLS=true` 才发现六个领域工具。推荐使用隔离检查：

```powershell
.\.venv\Scripts\python -m pytest tests/test_domain_adapters.py
.\.venv\Scripts\python scripts/check_domain_stack.py
```

脚本启动本机 REST/MCP，使用临时库和随机令牌，结束仅停止自己的进程，令牌不输出。原 CloudBase 单探针包不含 contracts、fixtures、知识目录和资料正文，**不可直接开启其业务开关**；部署需先明确完整资源打包和授权。D06 LOCAL_PASS 不代替平台业务联调。

完整只读固定演示包另见 [`deploy/cloudbase-demo-readonly/README.md`](../deploy/cloudbase-demo-readonly/README.md)。它保留资源层级、校验清单并使用解压后的 MCP 进程进行实测；不启动 REST/数据库。

2026-09-30 后续已获准用该完整包发布CloudBase004，构建和启动完成、003回退保留、入口仍关闭。详细状态见 [`004部署记录`](../docs/evidence/platform/D06-cloudbase-004-deployment-2026-09-30.md)；学校六类业务工具和主Agent调用尚未通过。
