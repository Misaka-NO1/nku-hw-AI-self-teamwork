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
