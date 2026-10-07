# B 进度 handoff：扩展、课表导入与时间引擎

## PR #9整合与日历联调补充（2026-10-06）

已收到新合并，HEAD/main=3a31ebd，calendar前端源码到位。前端150项、完整后端650项通过；真实隔离PG页面确认保存、0分钟提醒、完成/取消/恢复、刷新及虚构A/B切换均通过。只合入既有前端并处理导出冲突，未继续开发前端功能。服务合包准备，腾讯云控制台等待正常登录；线上未迁移或切流。见D15最新节。

## D日历后端同步（2026-10-06）

日历候选复用B原算法和服务器当前时间，排除本事项旧占用；完成/取消释放busy，恢复检查冲突。原通知due不变。新两表RLS+owner锁/CAS/快照版本使REST/OAuth与通知提交共享状态；固定课表教学范围已过，范围外返回timetable_outside_term，未改变夹具门禁。默认关闭、未云迁移。 见[D日历交接](D-task-calendar-backend-2026-10-06.md)及契约§10.2。下文为历史记录。

## D后端逻辑扩展（2026-10-06）

按用户新要求不继续做前端。notice_plan纯映射/计算复用B，增加用户buffers和可用区间限制；本人云REST与两种OAuth在默认关闭文本开关下纳入已确认selected_slot。原核心/B算法不改、原demo门禁保留。新四表PG候选与旧owner锁共用，计算之后发生保存/课表改变则事务版本拒绝；本地真实PG测试覆盖该竞争。模型/OCR关键字段须用户明确确认，不接受不完整候选或自动拼接OCR数字。见契约§10.1及D后端接口；线上/学校新输入仍未验收。

## D通知文字试点同步（2026-10-05）

基于PR #8/main b4dbaec，新增默认关闭的本地虚构文字入口；13字段NoticeDraft与B算法不改。本次复核event/due、耗时、最早开始和查询范围直接映射TimeCheckRequest；推荐仅用真实candidate_slots。保存Plan包装中的selected_slot作为后续**试点**忙碌，due不占时间，未确认不占时间；提交重读本人记录再算。原云owned_time/PG及旧公共适配器尚不接此包装。契约§10、backend/tests/test_notice_pilot.py与D13已同步；真实学校两账号/主Agent新通知和截图尚未通过。

## D 接口补充（2026-09-30，本地联调，不修改 B 算法）

D 已注册既定 schedules/validate、time/free-slots、time/check REST 与对应 MCP，只用固定 demo；D06 本机对照通过，尚未云端发布。POST/MCP 直接同一契约 JSON，无 payload 嵌套。公共 demo-workspace-01 只读固定课表；浏览器随机工作区需会话 owner 校验且读取已确认课表/任务，MCP 服务令牌不能访问。课表非固定内容即使标 demo 也拒绝；通知草稿未确认不占时间，due 非忙碌，缺时刻/耗时需确认。时间 calculation_version 放外层 meta；下方早期 handoff 中的 data 内版本描述已不代表契约。详见 D06 证据。

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

- backend：`55 passed`（含 B 新增 33 例：30 例时间/导入 + 3 例 TimeResult 契约一致性；D 既有测试全部保持通过，未改动 D 代码）
- import-core：`31 passed`，tsc 无错误
- extension：`24 passed`，tsc 无错误；`npm run build` 产出 `dist/{background,content,preview}.js` 与 `dist/preview.html`
- TIME-01~08、IMPORT-01~03、EXT-01~03 全部覆盖且通过；预期值取自 `fixtures/expected-results.demo.json`，未改预期迎合实现

## PR #2 审核意见修复（2026-09-24）

1. 时间结果符合契约：`kind` 改为 `free_time`；`calculation_version` 移出 data（由适配层放 meta）；新增 `backend/tests/test_time_contract.py` 用真实返回值校验 `TimeResult`。
2. 扩展运行链路补全：content script 注册 `extract-visible-schedule` 监听并回传观察值/结构化错误；预览页 `initPreview` 从 `chrome.storage.session` 读取观察值并渲染；`npm run build`（esbuild）生成 `dist/`。
3. 幂等键改为 `crypto.randomUUID()`，不再把票据明文拼进 `Idempotency-Key`；提交时 workspace 取自票据本身。
4. 导入页服务端校验按钮默认禁用并说明“接口待后端接入”，不再表现为已可用。
5. 周课表：同格多课程并存、跨节课程在每个所占节次显示、选中周应用 cancel/replace 调休规则（`import-core` 新增 `getEffectiveTemplate`，与后端同语义）。
6. CSV 改为字符流解析（支持引号内换行/逗号/转义）；`captured_at` 默认输出 `+08:00` 而非 `Z`。

## 真实教务页面是否验证

未验证（WAITING_HUMAN）。虚构夹具测试不得表述为真实教务适配成功。

## 适配器是否启用

`nku-adapter-v1`：disabled（生产白名单为空）。待核查字段见 `docs/evidence/B/adapter-observation.md`。

## PR #2 第二轮复审修复（2026-09-24）

- P1 扩展产物无法作为经典脚本执行：`background/content/preview` 全部改为 IIFE 打包；新增 `tests/dist.test.ts` 用 node:vm 以经典脚本方式编译 dist 产物（`npm run verify` = 构建+测试，产物缺失时该用例显式跳过）。
- P1 合入 main 后整站编译失败：已合入 main（含 C 的前端骨架与 A 的地图），在 `frontend/package.json` 声明 `@campus/import-core: workspace:*` 并更新 `pnpm-lock.yaml`（应审核要求代办，已同步 C）；`pages.tsx` 按 C 预留的注释接入 B 的 `ImportPage`/`TimetablePage`。`pnpm --filter web build`（tsc --noEmit + vite build）通过，前端 23 项测试通过。本机 Windows 无符号链接权限，pnpm 工作区链接在本机用 junction 兜底验证，配置文件与锁文件均为标准 pnpm 格式。
- P2 离线导出无法回导：导入器现在识别扩展导出的 PageObservation JSON，在页面内关联学期日历后重新解析为标准 TimetableImport；预览页支持“未关联日历先导出观察值、之后在导入页闭环”。新增导出→导入双向回归测试。
- 其他：`ImportPage` 增加学期日历上传步骤（未关联日历不生成公历日期）；`captured_at` 输出 +08:00。

本轮测试：backend 55 passed；import-core 33 passed；extension 25 passed（含产物加载验证）；web build 通过、web 23 passed。

## PR #2 第三轮复审修复（2026-09-27）

- P2 上传日历完整校验：import-core 新增 `validateTermCalendarStructure`（按 TermCalendar 契约逐字段校验，含 periods/overrides 元素内部结构）；`ImportPage` 接收日历时使用该校验，畸形日历（如 `periods: [null]`）在接收阶段即拒绝并给出逐条错误。
- 解析入口异常兜底：`parseImportFile` 全函数体 try/catch，任何畸形日历/文件导致的异常都转换为 blocking 的 `import_exception` 结构化错误；`ImportPage` 文件解析调用再加一层 try/catch 双保险，页面始终显示可恢复提示。
- 新增 5 项非法日历测试（periods [null]、节次时间格式、overrides 元素、畸形日历导入 CSV 不抛异常等）。
- 本轮测试：import-core 38 passed；web build 通过、web 23 passed；extension 25 passed（verify 含构建与产物验证）。

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
