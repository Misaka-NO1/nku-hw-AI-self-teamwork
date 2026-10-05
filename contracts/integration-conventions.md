# 南开校园助手：跨 Agent 对接约定

本文件是 A/B/C/D 之间的实现约定。若个人任务书与本文件冲突，以本文件和 `api.schema.json` 为准。

## 1. 命名原则

- 所有 REST、MCP、JSON 文件和数据库边界使用 `snake_case`。
- TypeScript 内部可以使用 `camelCase`，但只能在 API client/adapter 内转换。
- 所有业务 JSON 的 `schema_version` 固定为 `1.0.0`。
- 时间统一 `Asia/Shanghai`，ISO 时间必须带 `+08:00`，区间采用半开区间 `[start, end)`。
- `course_id` 是稳定课程标识；`offering_id` 是具体开课实例；`term_id` 是教学日历标识。

## 2. 页面和配置

统一页面组件名与路径：

| 页面 | 默认组件 | 路径 |
|---|---|---|
| 导入 | `ImportPage` | `/tools/import` |
| 课表 | `TimetablePage` | `/tools/timetable` |
| 待办 | `TasksPage` | `/tools/tasks` |
| 地图 | `ScenicPage` | `/tools/map` |
| 复习 | `StudyPage` | `/tools/study` |
| 校园事务 | `AffairsPage` | `/tools/affairs` |
| 培养方案 | `DegreePage` | `/tools/degree` |

`MapPage` 不再作为名称使用，统一为 `ScenicPage`。

前端只使用公开的构建变量 `VITE_API_BASE_URL`；后端使用：

```dotenv
APP_ORIGIN=
GENIOS_AGENT_URL=
MCP_PUBLIC_URL=
AUTH_MODE=demo_fixture
ALLOW_PERSONAL_UPLOADS=false
MCP_SERVICE_TOKEN=
DATABASE_URL=sqlite:///data/campus.db
```

`MCP_SERVICE_TOKEN` 只能存在于服务器和平台保密配置，不得进入前端变量、扩展代码、Git 或日志。

## 3. 内部函数到公共接口的映射

内部函数不处理 HTTP、MCP、数据库或身份；D 的薄适配层负责构造 `Principal`、加载资源、调用函数并包装统一信封。

| 领域 | 内部函数 | REST | MCP |
|---|---|---|---|
| 景点 | `search_spots(query, catalog)` | `GET /api/v1/scenic/spots` | `search_scenic_spots` |
| 景点 | `get_spot(spot_id, catalog)` | `GET /api/v1/scenic/spots/{spot_id}` | 不单独发布；使用白名单深链接或 REST 详情 |
| 资料 | `search_materials(query, principal, catalog)` | `GET /api/v1/study/materials` | `search_study_materials` |
| 资料 | `get_material(material_id, principal, catalog)` | `GET /api/v1/study/materials/{material_id}` | 不单独发布 |
| 资料 | `resolve_download(material_id, principal, catalog)` | `GET /api/v1/study/materials/{material_id}/download` | 不发布下载工具 |
| 课表 | `validate_timetable(payload)` | `POST /api/v1/schedules/validate` | `validate_timetable` |
| 时间 | `find_free_slots(actual_events, window, min_minutes, buffers)` | `POST /api/v1/time/free-slots` | `query_free_time` |
| 时间 | `check_time_plan(calendar, courses, tasks, request)` | `POST /api/v1/time/check` | `check_time_plan` |
| 培养方案 | `audit_degree_progress(plan, records)` | `POST /api/v1/degree/audit` | `audit_degree_progress` |

B 的 `adapterId/adapterVersion` 只允许存在于 TypeScript 内部结果；写入 `TimetableImport.source` 时必须转换为 `adapter_id/adapter_version`。

C 的纯函数接收已经解析好的 `plan` 和 `records`。公共接口只接受 `transcript_ref`，由 D 根据 workspace 和权限解析为 records；客户端不得直接通过 MCP 传入任意成绩记录。

## 4. 统一 API 信封

所有 REST 和可预期的 MCP 业务结果都使用同一信封：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "schema_version": "1.0.0",
    "request_id": "server-generated",
    "data_version": "demo-v1",
    "calculation_version": "time-v1",
    "warnings": [],
    "evidence_refs": []
  }
}
```

约定：

- 成功时 `ok=true`、`error=null`；失败时 `ok=false`、`data=null`。
- `error.field_errors` 固定为数组，每项为 `{field, code, message}`。
- `meta.warnings` 固定为 `{code, message}` 数组。
- `meta.evidence_refs` 固定为 `{label, source_ref, locator}` 数组。
- 前端 `StatusBannerProps.requestId` 由 API client 从 `meta.request_id` 映射，不改变线上字段名。
- HTTP 状态码必须与业务结果一致；不能用 HTTP 200 包装失败。

## 5. 查询参数冻结

景点查询和资料查询均必须带 `limit`，范围为 1–20。可选值必须显式传 `null`，不得由不同客户端省略后采用不同默认值。

```json
{ "campus_id": "demo-campus", "tags": ["flower"], "month": 3, "limit": 5 }
```

```json
{ "course_id": "demo-CS101", "topic": "递归", "limit": 5 }
```

2026-09-30 经用户确认，两个 GET 搜索路径的传输编码统一为 **一个 `query` 参数，值为完整查询 JSON 的 UTF-8 URL 编码**。例如 JavaScript 使用 `new URLSearchParams({query: JSON.stringify(query)})`；Python HTTP 客户端使用 `params={"query": json.dumps(query, ensure_ascii=False)}`。MCP arguments 直接使用同一个 JSON 对象，不嵌套 `query`。省略必需的 nullable 字段、重复 query 参数、混入分散参数均返回 `VALIDATION_ERROR`；`null`、空数组和中文不会被分别推断为默认值。详情/下载路径不使用此查询格式。

当前演示读接口中的 `workspace_ref=demo-workspace-01` 专指服务器预置的**只读公开虚构夹具**，不是登录凭据，也不是浏览器创建的可写工作区。公共 demo 课表不自动纳入未确认的通知草稿。浏览器随机工作区仍须会话 owner 校验并读取已确认课表/任务；MCP 共享服务令牌不得访问这些工作区。培养方案和成绩引用仅解析服务器固定 demo 文件，不能提交 records 或文件路径。

2026-09-30 用户另行批准**本地**学校平台兼容层：新增可选 `platform_*` 工具，仅接收 `query_json` 字符串，解析为原业务对象后仍按 `api.schema.json` 严格校验。它是独立的传输扩展，不修改本节既有 MCP/REST 接口、业务字段、Schema 1.0.0 或 A/B/C 算法；原客户端继续发送原对象，不需要迁移。命名、开关、安全限制及完整示例见 [平台传输扩展](platform-mcp-compat.md)。尚未更新云服务、同步或发布兼容插件；不能因本地测试通过就改平台绑定。

2026-09-30 用户另行批准**本地**学校平台兼容层：新增可选 `platform_*` 工具，仅接收 `query_json` 字符串，解析为原业务对象后仍按 `api.schema.json` 严格校验。它是独立的传输扩展，不修改本节既有 MCP/REST 接口、业务字段、Schema 1.0.0 或 A/B/C 算法；原客户端继续发送原对象，不需要迁移。命名、开关、安全限制及完整示例见 [平台传输扩展](platform-mcp-compat.md)。尚未更新云服务、同步或发布兼容插件；不能因本地测试通过就改平台绑定。

## 6. 培养方案审计结果

输入计划仍使用 `DegreePlan.version` 和模块的 `min_credits`；审计输出统一使用：

```text
plan_id, plan_version, source_ref
modules[]:
  module_id, earned_credits, required_credits, remaining_credits
  missing_required_courses, counted_attempts, excluded_attempts
unallocated_courses, unresolved_rules, data_coverage
status: complete_under_supported_rules | incomplete | needs_policy
```

`plan_version` 是从输入 `version` 映射出的输出字段；`required_credits` 是从输入 `min_credits` 映射出的输出字段。两者不得混用或同时作为同义字段返回。

## 7. 变更流程

修改公共字段、路径、工具名或枚举时，必须同时更新：

1. `contracts/api.schema.json`
2. 领域夹具和正反例
3. REST/MCP 薄适配测试
4. 受影响 Agent 的 handoff

未完成上述同步前，不得在某一个 Agent 的代码中私自改名。

## 8. D04/D05 写入约定

- 固定虚构数据集 ID 为 `demo-v1`；服务端仍须按规范化内容 hash 检查真实夹具内容，不能只信任该 ID 或 `dataset_kind=demo`。
- 浏览器写请求使用 HttpOnly 会话 Cookie，并在 `X-CSRF-Token` 发送创建工作区时返回的 CSRF 值。
- 创建导入草稿使用 `Authorization: ImportTicket <opaque-token>`；票据只允许 `schedule_import`，服务器只保存 token hash。
- 创建草稿和确认使用 `Idempotency-Key` 请求头；任务/课表提交按既有契约在 JSON 中发送 `idempotency_key`。
- `review_url` 在 `APP_ORIGIN` 未配置时为 `null`，不得猜测线上域名。

## 9. D 逐用户 OAuth 候选（2026-10-02；默认关闭、仅本地）

2026-10-04 全功能参赛整合候选：身份工具站增加现有 `/tools/affairs`、`/tools/degree` 页面，
沿用既有 POST `/api/v1/degree/audit` 契约及 C 纯算法，仅固定公开 demo-workspace-01/
demo-cs-plan-v1/demo-transcript-01，不解析 PG owner 成绩或接任意 records。
其他 workspace、未知方案和额外字段拒绝；原 schema_version 与算法不改。
打包追加只读 degree/transcript 两夹具，不改变旧四个写入夹具或数据库迁移。
课程目录/经验卡由 C 既有公开虚构目录展示，同名不同编号、官方类型与学生经验分开。
该整合追加已于2026-10-04部署011/r10并正常100%切流；固定C云审计与学校学分正反例通过。
学校C知识库补两项官方后勤摘要及明确虚构课程/经验卡；不扩展个人成绩权限或改变契约字段。
010/r9已批准的OAuth兼容开关沿用。2026-10-04 013/r12已修复授权确认页来源策略及固定回调CSP冲突；学校真实OAuth授权、A本人records/free-slots/check均通过，不再把旧客户端屏蔽当最新状态。
主Agent草稿已绑定三项只读OAuth工具；A/B本人记录读回、退出401、空档、活动冲突与截止20分钟正向/缺耗时负向已实际通过。学校check输出必须保留conflicts与candidate_slots两可选分支，不能仅用活动样本解析丢弃截止字段。评委发布入口仍待验收，仍仅两个测试账号、demo:read与虚构数据，不增加真实个人成绩权限。

2026-10-03 参赛标准调整：负责人选择普通保密客户端授权码兼容学校现有五参数请求。
新增默认关闭的 `CLOUD_OAUTH_COMPETITION_COMPAT_ENABLED`，必须与云 OAuth 开关同时开启；
新独立 `nku_competition_oauth_v1` 三张授权表/固定后台 RPC，不替换严格 S256 模式或旧 15 表。
此模式仅 `demo:read`，两个已批准普通账号、固定虚构数据；接受 8–256 字符 state，原样回传；
token 支持 Basic/表单或 JSON 客户端认证，无 verifier/refresh/Agent 写入。
原 records/时间结果和 B 算法不变；scope、本人确认、一次性码和账号归属仍由服务器约束。
这是参赛互通候选，不宣称与 PKCE 等价或正式个人数据上线。启用前需具体线上变更确认。
按 §7 已同步 schema、五参数夹具、HTTP 正反例、A/B/C 交接；尚待学校实调用验收。

新增 loopback/test-only 授权码适配器，不变更现有公共 MCP/REST 或 A/B/C 算法。
OAuth 控制路径采用 RFC 6749 的标准响应/跳转，是第 4 节业务信封的明确协议例外；
records/task-drafts 业务端点继续 ApiEnvelope 1.0.0。不能在云端或主 Agent 中自行启用。
路径、PKCE、精确回调、逐用户同意、短期 token、无 refresh/commit 限制见
[OAuth 候选说明](../deploy/OAUTH-PILOT-ADAPTER.md) 与 api.schema.json 的 x-oauth-local-pilot。
受影响 A/B/C handoff 已同步；学校运行时协议、持久存储与权限配置尚未验收。

### 9.1 云 PostgreSQL 候选（002 身份版已部署，OAuth 未启用，业务待实测）

新增独立入口 `app.cloud_identity_site`，复用上述 OAuthPilot 正反例/schema 和协议例外，
不改变已有业务 REST/MCP 路径和 A/B/C 算法。默认两个 cloud pilot 开关均关闭。
后台固定 RPC `nku_identity_pilot_v1_rpc` 不向浏览器或 Agent 注册为公共工具。
在线批准的 CloudBase owner、会话、草稿、确认、幂等与短期授权由隔离 PG 存储约束；
只有本人浏览器能确认/提交。共享服务令牌和 SYS_USERID 不能访问用户空间。
当前仅固定虚构数据、24 小时可访问空间，无真实成绩或个人上传。
同意/令牌控制与已部署服务保持隔离；云权限、新客户端与学校逐用户实证完成前不启用。
打包/配置/验收见 [云身份候选](../deploy/cloudbase-identity-pilot/README.md)；
`api.schema.json` 的 x-oauth-cloud-pilot-candidate 与 ABC handoff 同步此阶段，不能据此声称上线。

候选补充 `POST /oauth/time/free-slots`、`POST /oauth/time/check`，使用
`OAuthPilotTimeQueryRequest` 的单个 `query_json` 字符串（最多 2048 字符）。其内容为
既有 `FreeTimeQuery` / `TimeCheckRequest` 去掉 `workspace_ref`；其余必填字段、null、数组
保持原契约。不接受 owner/user/workspace 或课表/任务覆盖，内部仅用授权 `demo:read`
对应账号已确认记录和 B 原算法。缺课表返回 NOT_FOUND，不借用公共演示课表。
结果仍为 ApiEnvelope/TimeResult，保留 calculation_version、coverage、needs_confirmation；
不把未知覆盖说成用户确定有空，不为日期补造截止时刻。
按 §7 同步 schema、oauth-pilot.demo.json、HTTP 正反例及 ABC 交接；只扩展云候选，
不注册公共 MCP、不修改 loopback OAuth 接口、不开放真实个人数据。

### 9.2 同源本人复核会话恢复候选（2026-10-03；本地候选，尚未部署）

新增 `GET /api/v1/auth/cloudbase/browser-session`，只在云身份试点入口注册；
没有 query/body/owner/bearer 参数。本人同源前端使用 `credentials=include` 和
`X-Campus-Session-Read: 1`；明确的外站 Origin/Fetch Metadata 拒绝，不开放 CORS。
业务信封 data 见 `CloudBrowserSession`，契约正反例见 `browser-session.demo.json`。

登录时追加一个 Secure/HttpOnly/SameSite=Strict 的 15 分钟上下文 Cookie，
包含原 workspace/CSRF/expiry，MAC 绑定原随机 HttpOnly 会话，不是独立凭证。
恢复先校验上下文签名和原期限，再用既有 PG `get_workspace` 验证原会话/owner；
不换会话或 CSRF、不延长有效期、不自动同意 OAuth 或保存草稿。
响应不含原会话 token、CloudBase token/UID，`Cache-Control=no-store`；退出清除两个 Cookie。
旧版本会话没有上下文时明确要求一次重新登录，不虚构 CSRF 或延长旧会话。
没有数据库迁移、RPC/角色变更，公共 MCP/旧服务不注册这个路径。

Tasks/Import 身份模式初始化不相信旧 sessionStorage；先恢复当前服务器身份，
跨 workspace 清旧草稿/幂等指针。401/到期才显示本人登录入口，依赖错误禁写、不退回匿名。
登录返回仅允许既有严格 OAuth 授权路径，或 `/tools/tasks`、`/tools/import` 的
唯一安全 `draft_id`；拒绝外站/重复额外参数/hash/令牌/owner/嵌套返回，不自动提交。
本节 schema、夹具、HTTP 正反例与 ABC handoff 按 §7 同步；云与学校链路仍须实测。
