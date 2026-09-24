# C Agent 进度交接

任务状态：LOCAL_PASS；校园正式来源与真实培养方案：WAITING_HUMAN（见 docs/blockers/C-01、C-02）

## 修改文件

- 前端骨架：`package.json`、`pnpm-workspace.yaml`、`pnpm-lock.yaml`、`frontend/`（包名 `web`）
- 公共前端：`frontend/src/app/`（Layout、routes、nav、占位页、统一页面导出）、
  `frontend/src/shared/`（API client、SourceCard、StatusBanner、LoadingState、EmptyState、
  ErrorState、ConfirmSummary、课程目录/经验读取、样式）
- 业务页：`frontend/src/features/affairs/`、`frontend/src/features/degree/`
- 知识库：`knowledge/affairs/entries.json`、`knowledge/affairs/qa-tests.demo.json`、
  `knowledge/courses/catalog.json`、`knowledge/courses/experiences.json`、
  `knowledge/degree/README.md`、`knowledge/scripts/build_exports.py`、
  `knowledge/exports/KB_Campus.json`、`knowledge/exports/KB_Course.json`
- 培养方案内核：`backend/app/domains/degree/`（纯函数，不动 D 的入口/DB/MCP）
- 夹具：`fixtures/degree-plan.demo.json`、`fixtures/transcript.demo.json`、
  `fixtures/expected-results.demo.json`
- 提示词：`prompts/campus-answer.md`
- 文档：本文件、`docs/blockers/C-01-campus-sources.md`、`docs/blockers/C-02-degree-plan.md`、
  README 增加前端命令小节、`.gitignore` 增加前端产物

未修改 A/B/D 的任何业务代码与 contracts 公共接口。

## 页面和组件导出路径

- 统一导出：`frontend/src/app/pages.tsx` → `ScenicPage`、`StudyPage`、`ImportPage`、
  `TimetablePage`、`TasksPage`（A/B/D 未交付前为明确占位）、`AffairsPage`、`DegreePage`（已实现）
- 路由：`frontend/src/app/routes.tsx`，前缀 `/tools/`，与契约 §2 一致
- 公共组件：`frontend/src/shared/components/index.ts`
- 公共 API client：`frontend/src/shared/api/client.ts`（只读 `VITE_API_BASE_URL`；
  统一信封；`meta.request_id` → `StatusBannerProps.requestId`；snake_case → camelCase；
  支持超时与取消；任何失败抛 `ApiError` 并携带 requestId）
- 说明：内嵌任务包 §4 写“API client 只认识 APP_API_BASE”，与契约
  `integration-conventions.md` §2 及 C 任务书冲突，按契约优先原则采用 `VITE_API_BASE_URL`。

## 公共 API client 配置

- `VITE_API_BASE_URL`：后端地址（见 `frontend/.env.example`）
- `VITE_GENIOS_AGENT_URL`：未配置时“返回 NK-GeniOS”按钮禁用，不猜链接

## 培养方案函数输入输出

- 函数：`audit_degree_progress(plan, records)`（`backend/app/domains/degree/audit.py`）
- 输入：已解析的 DegreePlan 字典 + 已授权 records（`transcript_ref` 由 D 解析，函数不接原始引用）
- 输出：`plan_id / plan_version / source_ref / modules[]（module_id, earned_credits,
  required_credits, remaining_credits, missing_required_courses, counted_attempts,
  excluded_attempts）/ unallocated_courses / unresolved_rules / data_coverage / status`
- status ∈ `complete_under_supported_rules | incomplete | needs_policy`；学分用 Decimal；
  结果明确“不替代学校审核”

## 测试命令

```bash
pnpm install --frozen-lockfile
pnpm --filter web test      # Vitest
pnpm --filter web build     # tsc --noEmit + vite build
cd backend && ./.venv/Scripts/python -m pytest
```

## 测试实际结果

- 前端 Vitest：4 个文件 23 项全部通过（SHELL-01 路由导出、SHELL-02 401/403/422/503
  错误与 request_id、CAMPUS-01/02/03、COURSE-01，及 PR #3 审核回归：HTTP 失败不视为成功、
  响应体超时保护、officialUrl 展示一致性、有效评分样本门槛）
- 前端构建：`tsc --noEmit && vite build` 通过
- 后端 pytest：41 项全部通过（含 D 基线 23 项、DEGREE-01~06 及夹具/Schema 校验、
  KB 导出发布过滤 6 项、重复课程学分冲突顺序无关 2 项；
  DEGREE-06 与 `fixtures/expected-results.demo.json` 完全一致：已计 5.0、总缺口 7.0、
  缺必修 demo-CS102/demo-CS103）

## 待核验校园来源

全部 15 条事务/入口为虚构 demo 模板，待人工核验清单见 `docs/blockers/C-01-campus-sources.md`；
真实培养方案见 `docs/blockers/C-02-degree-plan.md`。

## 给 A 的下一步

- 在 `frontend/src/features/scenic/`、`features/study/` 交付默认导出的 `ScenicPage`、
  `StudyPage`；路由占位已在 `app/pages.tsx`，落地后替换 import 即可
- 可直接复用 `shared/components` 与统一 API client；不要自己写 fetch
- 课程 ID 以 `knowledge/courses/catalog.json` 为准

## 给 B 的下一步

- 同上：`features/import/`、`features/timetable/` 默认导出 `ImportPage`、`TimetablePage`
- `pnpm-workspace.yaml` 已含 `extension` 与 `packages/*`，扩展与 import-core 直接加入即可

## 给 D 的下一步

- 领域函数已就绪：`audit_degree_progress(plan, records)`，请按契约做 REST
  `POST /api/v1/degree/audit` 与 MCP `audit_degree_progress` 薄适配（transcript_ref 解析在 D 侧）
- KB 上传清单：`knowledge/exports/KB_Campus.json`、`KB_Course.json`；答复提示词
  `prompts/campus-answer.md`；回归用例 `knowledge/affairs/qa-tests.demo.json`
- 已知不支持：C08–C12 依赖真实资料/平台，保持 WAITING_HUMAN；首版无匿名投稿与教师评分
