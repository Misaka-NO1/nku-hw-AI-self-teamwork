# B 进度 handoff：扩展、课表导入与时间引擎

日期：2026-09-22｜分支：`feat/agent-b-schedule-time`

```text
任务状态：LOCAL_PASS（B01–B06 第一轮完成；B07–B12 依赖真实资源或队友接口，标注如下）
```

## 修改文件

- `backend/app/domains/schedule/{__init__,service}.py`：validate_timetable、expand_occurrences、export_ics
- `backend/app/domains/timeplan/{__init__,service}.py`：find_free_slots、check_time_plan
- `backend/tests/test_schedule_time.py`：TIME-01~08、IMPORT-02 后端侧、ICS、票据无关纯函数共 30 例
- `packages/import-core/`：TS 解析器（parseWeeks/recognizePage/parseObservation/parseImportFile/normalizeCourses/ajv 共享契约校验）+ 23 例测试
- `extension/`：MV3 骨架（manifest、白名单、消息协议、票据提交、独立预览页）+ 15 例测试
- `frontend/src/features/import/`、`frontend/src/features/timetable/`：ImportPage / TimetablePage
- `fixtures/term.demo.json`、`fixtures/time-free-query.demo.json`、`fixtures/time-event-query.demo.json`、`fixtures/time-deadline-query.demo.json`、`fixtures/expected-results.demo.json`
- `docs/evidence/B/adapter-observation.md`、本文件

## 导出的函数和组件

- Python：`validate_timetable(payload) -> {normalized_payload, issues, payload_hash, coverage}`；`expand_occurrences(calendar, courses, window) -> (actual_events, warnings)`；`find_free_slots(actual_events, window, min_minutes, buffers) -> {kind, slots, coverage, needs_confirmation, calculation_version}`；`check_time_plan(calendar, courses, tasks, request) -> {kind, conflicts|candidate_slots, coverage, needs_confirmation, calculation_version}`；`export_ics(calendar, courses, window) -> str`
- TS（`@campus/import-core`）：`parseWeeks`、`recognizePage`、`parseObservation`、`parseImportFile`、`normalizeCourses`、`extractHtmlTable`、`validateTimetableStructure`
- 扩展：`isExtractionAllowed`、`parseMessage`、`isSenderAllowed`、`extractCourseObservation`、`submitConfirmedDraft`
- 前端：默认导出 `ImportPage`（frontend/src/features/import/ImportPage.tsx）、`TimetablePage`（frontend/src/features/timetable/TimetablePage.tsx）

## 公共接口映射

```text
validate_timetable → validate_timetable（POST /api/v1/schedules/validate）
find_free_slots    → query_free_time（POST /api/v1/time/free-slots）
check_time_plan    → check_time_plan（POST /api/v1/time/check）
```

`TimeCheckRequest.kind` 使用 `event_conflict` / `deadline_feasibility`；TS 内部 `adapterId/adapterVersion` 写入标准 JSON 时已转换为 `adapter_id/adapter_version`。

## TimetableImport 字段映射

- `weeks`：解析器把“1-16单周”等原文转换为去重升序数组（如 `[1,3,...,15]`），非法输入报 blocking issue
- `source.coverage`：分页/虚拟列表/当前周 → `partial`；文件导入无法证明全量 → `unknown`；只抓一个分页绝不标 `complete`
- 缺失字段（地点/教师/学分）保持 `null` 并进 `issues`（`missing_fields`），不虚构
- 重复 meeting 按 `offering_id`+meeting 内容签名识别去重；同课程不同 meeting 全部保留（IMPORT-02）

## 时间算法版本

`calculation_version = time-v1`。半开区间 `[start,end)`；先应用调休 cancel/replace 再展开；due 不是 busy block；缺 `estimated_minutes` / 精确 `due_time` / `earliest_start` 时返回 `needs_confirmation`，不使用 23:59、不移动课程或截止时间。

## 测试命令

```bash
cd backend && uv venv .venv && uv pip install -e ".[dev]" && .venv/Scripts/python -m pytest
cd packages/import-core && npm install && npm test && npm run typecheck
cd extension && npm install && npm test && npm run typecheck
```

## 测试实际结果

- backend：`53 passed`（其中 B 新增 30 例；D 既有 23 例全部保持通过，未改动 D 代码）
- import-core：`23 passed`，tsc 无错误
- extension：`15 passed`，tsc 无错误
- TIME-01~08、IMPORT-01~03、EXT-01~03 全部覆盖且通过；预期值取自 `fixtures/expected-results.demo.json`，未改预期迎合实现

## 真实教务页面是否验证

未验证（WAITING_HUMAN）。虚构夹具测试不得表述为真实教务适配成功。

## 适配器是否启用

`nku-adapter-v1`：disabled（生产白名单为空）。待核查字段见 `docs/evidence/B/adapter-observation.md`。

## 给 C 的下一步

- 接入路由 `/tools/import` → `ImportPage`、`/tools/timetable` → `TimetablePage`（默认导出）
- `ImportPage` 需要 props：`calendar: TermCalendar | null`、`datasetKind`；`TimetablePage` 需要 `timetable: TimetableImport | null`
- 前端骨架就绪后，把 `@campus/import-core` 加入 workspace 依赖（file:../packages/import-core）

## 给 D 的下一步

- REST/MCP 薄适配：`POST /api/v1/schedules/validate`、`POST /api/v1/time/free-slots`、`POST /api/v1/time/check` 直接调用上述纯函数，错误按 `AppError` 既有信封映射（422 VALIDATION_ERROR）
- 本分支未改动 D 的任何文件；`AppError`/`FieldError`/`validate_contract` 为只读复用
- 上传票据端点联调（B09）待 D 的 import-tickets 就绪后进行

## 仍需人工提供的内容

- 真实教务页面只读核查（B07）、扩展真实浏览器加载验收（B12）
- 前端骨架（C）就绪后的浏览器端验证
