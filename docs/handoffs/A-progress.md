# A 模块进度交接：赏景地图与期末复习

任务状态：A01、A02、A05、A07、A08 `LOCAL_PASS`；A03、A04 已有独立地图预览，审核提出的异步目录更新与多底图深链接已通过浏览器回归，拖动手感和真实本地图片导入仍待人工验收；A06、A09 已完成本地纯函数、类型、服务端渲染空态检查，平台知识问答仍待联调；A10–A12 `WAITING_HUMAN` / 依赖其他成员。

修改文件：仅 `frontend/src/features/scenic/`、`frontend/src/features/study/`、`backend/app/domains/scenic/`、`backend/app/domains/study/`、A 对应测试、`knowledge/scenic/`、`knowledge/study/`、`prompts/scenic-routing.md`、`prompts/study-answer.md`、`docs/handoffs/A-progress.md`、`docs/blockers/A-assets.md`。未修改 `contracts/`、公共路由/样式、数据库、认证、MCP 注册或其他 Agent 的业务代码。

新增页面和函数：

- 默认导出 `frontend/src/features/scenic/ScenicPage.tsx` 的 `ScenicPage`：可拖动/缩放的 2D 示意地图、标签筛选、点位详情、按景点 `map_id` 定位所属底图的深链接、返回、无底图/照片状态；开发构建经 `enableAuthoring` 开启新增景点窗口、本地底图临时预览、点位编辑/导入导出。公开浏览的目录随传入 props 更新，本地编辑草稿不会被服务端更新静默覆盖；冲突时明确提示先导出再取舍。
- `frontend/src/features/scenic/preview/` 提供只依赖 A 模块的 Vite 独立预览入口；这是网页组件测试入口，不是已导入 NK-GenioS 的插件。
- 默认导出 `frontend/src/features/study/StudyPage.tsx` 的 `StudyPage`：课程与主题筛选、正文/索引区分、来源定位、无权限/不存在错误态。切换课程同步更新 URL 并移除旧 `material_id`，浏览器前进后退恢复选择；下载地址通过 `downloadUrlFor` 注入，避免硬编码当前前端域名。
- `geometry.ts`：`toMapPoint`、`fromMapPoint`、`validateSpot`、安全资产路径、花期历史表述；`authoring.ts`：新点位创建校验、本地目录导出/导入与校验。
- Python：`search_spots`、`get_spot`、`search_materials`、`get_material`、`resolve_download`、公共正文导出器。
- 公开数据：虚构 scenic 目录、资产清单、自创笔记与材料目录、KB 候选文件、15 条平台知识回归题。

接口契约版本：`1.0.0`。A 内部函数名保留；D 应依 `contracts/integration-conventions.md` 注册为 `search_scenic_spots`、`search_study_materials`，并接入 `/api/v1/scenic/spots` 和 `/api/v1/study/materials` 等既定路径。公共 schema 未更改。

测试命令和实际结果（2026-09-23）：

```powershell
cd backend
C:\Users\29950\AppData\Local\Temp\nku-a-venv-20260923\Scripts\python.exe -m pytest
# 35 passed, 1 third-party deprecation warning

cd ..
cd frontend/src/features/scenic/preview
npm ci
npm run test:logic
# 17 passed

npm run typecheck
npm run build
# 类型检查与独立预览构建通过
```

两个 TSX 页经 esbuild `transformSync(..., {loader:'tsx'})` 语法检查通过；A 独立预览的严格 TypeScript 检查 0 条诊断；React 服务端渲染检查验证未知点位、缺底图和私有材料深链接错误态。`/review.html` 在真实浏览器中完成五项审核回归：目录异步更新、多底图深链接、后端下载域名注入、课程切换 URL、浏览器前进后退，均为 `PASS`。独立预览也已检查点位详情、缩放按钮、新增窗口和保存后新标记。拖动手感、真实底图图片导入和 C 的公共路由尚未完整验收；不把独立预览等同于整站前端联调。

地图手工试用：在 `frontend/src/features/scenic/preview/` 运行 `npm run dev`，打开 `http://127.0.0.1:5173/?mode=authoring`。先放大再拖动画布；点击“添加景点”后点地图空白处，在弹窗输入名称、简介和标签并保存。底图可临时选本地 PNG/JPEG/WebP；点位 JSON 与图片必须分别保存，刷新前先导出 JSON。详见该目录 README。

GitHub 交付：原仓库对 `sunjx3316-cell` 无直接写权限，已通过 Fork 工作流将 `feat/agent-a-map-review` 推送到 `sunjx3316-cell/nku-hw-AI-self-teamwork`，并创建指向原仓库 `main` 的 [PR #4](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/4)。该 PR 已由仓库负责人合并；本次三维地图代码快照另开分支与 PR，不直接向 `main` 提交。

未解决问题：

- A10：D 的服务目前只有健康探针，未注册 A 的 REST/MCP 工具；真实 HTTPS、平台知识库导入和 GenioS 调用未完成。
- A11：没有真实底图、照片、花期来源或获授权的课程资料。页面和知识库明确为 demo。
- A12：B/C/D 尚未完成全体 P0 联调，不能替其签收最终演示范围。

需要人工提供的素材或权限：见 `docs/blockers/A-assets.md`。真实材料进入仓库前须确认来源、许可、日期、版本及位置。

给 C 的下一步：

1. 在公共路由中挂 `ScenicPage`→`/tools/map`、`StudyPage`→`/tools/study`；不要改 A 组件名称。
2. 用共享 API client 向两个组件传入已权限过滤的目录数据；当前默认 props 是本地虚构 demo。
3. 完整运行 React/TypeScript/Vite 构建并做深链接、浏览器后退和窄屏交互检查。
4. `StudyPage` 的 `enableDownloads` 默认关闭；D 接通下载路由后再启用，同时从 C 的共享 API client 注入 `downloadUrlFor`，例如：

   ```tsx
   downloadUrlFor={(id) => `${apiBaseUrl()}/api/v1/study/materials/${encodeURIComponent(id)}/download`}
   ```

   不要把私有目录传到浏览器，也不要从前端地址推测后端地址。同源 API 代理可使用根相对地址；独立后端需把 `VITE_API_BASE_URL` 配成完整后端域名。

给 D 的下一步：

1. 由后端可信 `Principal` 调用 A 的纯函数，构造统一信封并注册既定 REST/MCP 名称；`APP_ORIGIN` 经核验后再拼白名单深链接。
2. `resolve_download` 只返回被目录白名单校验过的本地文件路径，D 负责登录/访问控制和 FileResponse。
3. 在 GenioS 试导入 `knowledge/study/exports/KB_Study_demo.md` 和 `knowledge/scenic/KB_Scenic_demo.md`，再按 `A-knowledge-test-cases.md` 实测引用和工具返回；测试成功前不可说已接入平台。
4. 私人资料访问需另行审查身份绑定；当前 A 服务只暴露公开且已授权目录。

## 津南三维地图代码快照（待真实数据）

新增 `frontend/src/features/scenic/three-preview/`：从仓库外已验收的总图版原型提取当前可运行的三维模型与只读公测页面。只保留当前总图版、模型代码、已生成 GLB、离线 Three.js 安装包及回归测试；未复制本机 `data/`、高德代理、原始参考截图和其他历史模型。默认服务只读，服务端拒绝景点写入与照片上传；本机可显式开启录入模式，具体命令和风险见该目录 README。

这仍是**独立预览**，不替换既有 `ScenicPage`，未修改共享 `contracts/`。正式使用前需把真实景点/照片转换为 `ScenicCatalog`，确认发布授权及花期来源，再由 C/D 接通公共页面、REST/MCP 和 GenioS；不能因代码已提交而把地图或 Agent 查询标记为联调完成。
