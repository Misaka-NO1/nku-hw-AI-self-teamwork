# C Agent 进度交接

## PR #9整合与日历联调补充（2026-10-06）

已收到新合并，HEAD/main=3a31ebd，calendar前端源码到位。前端150项、完整后端650项通过；真实隔离PG页面确认保存、0分钟提醒、完成/取消/恢复、刷新及虚构A/B切换均通过。只合入既有前端并处理导出冲突，未继续开发前端功能。服务合包准备，腾讯云控制台等待正常登录；线上未迁移或切流。见D15最新节。

## D日历接口交付（2026-10-06）

按交接实现列表/候选/状态写入和摘要候选，完整13字段notice、独立calendar_revision，等价UTC可返回；同键重试/CAS与保存后GET读回已验证。默认关闭、未部署。当前仓库/远端无frontend/src/features/calendar，请前端提供方给实际位置后合包；本轮未继续开发前端。 见[D日历交接](D-task-calendar-backend-2026-10-06.md)及契约§10.2。下文为历史记录。

## D后端接口交付（2026-10-06，前端由其他人负责）

负责人调整为只完成逻辑；本轮不再修改前端。新本人notice-text读/查、草稿更新/确认/提交/分页读回及PNG/JPEG/OCR接口候选已提供，现有登录/账号不重做。draft返回review_url=null/review_required=true，原固定页不能直接显示Plan；接入方应展示原文/缺项/覆盖/真实候选，字段改后重算并更新revision，最后本人点确认后才提交。来源OCR须保留source_kind/hash并明确ocr_review与关键时间，模型输入model_output字符串不丢原始证据；只读学校OAuth不能代保存。完整字段/路径和错误见D-notice-backend-interface-2026-10-06.md，默认关闭且尚未部署，无C算法/云权限改动。

## D通知文字试点同步（2026-10-05）

新增本地待办复核组件仅在VITE_NOTICE_TEXT_PILOT=true及/tools/tasks?notice_pilot=1同时满足时显示；原TasksPage、双入口导航及C页面保留。新文字来源/补充/实际候选以NoticePilotPlan包装，内部仍13字段NoticeDraft；复用Cookie/CSRF和本人草稿确认，修改立即清旧候选并需新revision。本轮不改C审计/课程契约或云权限；云PG/OAuth尚不支持包装。见契约§10、D操作说明与D13，学校及文件输入未验收。

## D 接口补充（2026-09-30，本地联调，不修改 C 页面/算法）

D 已注册 degree/audit REST/MCP，接收 workspace_ref/plan_id/transcript_ref，固定 demo 解析并复用 C 算法；本机对照通过，尚未云端发布。仅支持 demo-cs-plan-v1 / demo-transcript-01，不接任意 records，结果不等于毕业资格。用户确认景点/资料 GET 搜索用一个 query JSON 参数：new URLSearchParams({query: JSON.stringify(query)})；nullable 字段显式 null，MCP arguments 直接同一对象。详情/附件下载路径不变，附件成功不是 JSON 信封。C 后续仍需为公共页面注入真实接口结果，不能把默认 props 当作后端联调通过。详见 contracts/integration-conventions.md §5、backend/README.md 和 D06 证据。

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

## 测试实际结果（2026-09-27 复跑）

- 前端 Vitest：4 个文件 23 项全部通过（SHELL-01 路由导出、SHELL-02 401/403/422/503
  错误与 request_id、CAMPUS-01/02/03、COURSE-01，及 PR #3 审核回归：HTTP 失败不视为成功、
  响应体超时保护、officialUrl 展示一致性、有效评分样本门槛）
- 前端构建：`tsc --noEmit && vite build` 通过
- 后端 pytest：53 项全部通过（含 D 基线 23 项、A 合并入 main 后的 scenic 测试、
  DEGREE-01~06 及夹具/Schema 校验、KB 导出发布过滤 6 项、重复课程学分冲突顺序无关 2 项；
  DEGREE-06 与 `fixtures/expected-results.demo.json` 完全一致：已计 5.0、总缺口 7.0、
  缺必修 demo-CS102/demo-CS103）

## 待核验校园来源（2026-09-27 二次更新）

- 11 条官方入口已核验（10 条 2026-09-23 校外实测 HTTP 200 + 教务部「在校生业务」栏目
  2026-09-27 实测，清单与依据见 `docs/blockers/C-01-campus-sources.md`）
- 办事流程：8 条全部核验（`nku-proc-*`，verified_at=2026-09-27）——成绩单/在读证明、
  学生证补办、自修申请（在校生业务栏目文件 + 2026-08-17 选课通知）、选课/退课
  （选课通知，含期中退课记 W）、住宿申请与退宿（南发字〔2018〕37 号）、宿舍报修
  （学生生活指导中心官网：飞书后勤报修/电话 85358535/微信 nkuhqbzb，两校区）、
  校园网密码（网信办官网：自助系统 + 持证现场重置）、学分认定（南发字〔2019〕48 号：
  40% 上限、相似度 ≥70%、外校记 △ 不计 GPA）；数据集中仅剩 2 个故意保留的
  虚构测试夹具（demo-proc-05 过期提示、demo-proc-06 校区过滤）
- 2026-09-30 新增 9 条用户提供的日常指引（校园卡充值、电费充值、查看培养计划、
  体育场馆预约、教学评价、跳蚤市场、班车查询、出入校申请、心理咨询预约），
  按原则标 needs_verification，随核验清单 `docs/kb-review-2026-09-30.md` 发团队群
  验证，确认后升级 verified；涉及金钱的条目仅指引官方入口，不收录支付链接/二维码
- 真实培养方案：计算机科学与技术 2025 版已收集（截图 6 张），规则核验表
  `knowledge/degree/cs-2025/plan-rules.md`；repeat_policy/免修/学分认定已按
  《2026级南开大学本科学生手册（上册）》学则第十四/十五/十九/二十条核验；
  体育子模块规则已按选课手册「学生体育课选课说明」核验（类别制必修，无稳定
  course_code，引擎 needs_policy）；学分认定已按办法原文核验（南发字〔2019〕48 号）；
  四史「多选一」语义已确认（任选 1 门，用户口头确认待正式文件复核）；
  剩余缺口仅剩课程替代细则，见 `docs/blockers/C-02-degree-plan.md`

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
