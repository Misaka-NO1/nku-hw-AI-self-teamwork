# A 模块进度交接：赏景地图与期末复习

任务状态：A01、A02、A05、A07、A08 `LOCAL_PASS`；A03、A04、A06、A09 已写入并完成本地纯函数、类型、服务端渲染空态检查，但浏览器交互和平台知识问答仍待联调；A10–A12 `WAITING_HUMAN` / 依赖其他成员。

修改文件：仅 `frontend/src/features/scenic/`、`frontend/src/features/study/`、`backend/app/domains/scenic/`、`backend/app/domains/study/`、A 对应测试、`knowledge/scenic/`、`knowledge/study/`、`prompts/scenic-routing.md`、`prompts/study-answer.md`、`docs/handoffs/A-progress.md`、`docs/blockers/A-assets.md`。未修改 `contracts/`、公共路由/样式、数据库、认证、MCP 注册或其他 Agent 的业务代码。

新增页面和函数：

- 默认导出 `frontend/src/features/scenic/ScenicPage.tsx` 的 `ScenicPage`：示意地图、标签筛选、点位详情、深链接、返回、放大、无底图/照片状态；开发构建经 `enableAuthoring` 开启的本地编辑/导入导出。
- 默认导出 `frontend/src/features/study/StudyPage.tsx` 的 `StudyPage`：课程与主题筛选、正文/索引区分、来源定位、无权限/不存在错误态。
- `geometry.ts`：`toMapPoint`、`fromMapPoint`、`validateSpot`、安全资产路径、花期历史表述；`authoring.ts`：本地目录导出/导入与校验。
- Python：`search_spots`、`get_spot`、`search_materials`、`get_material`、`resolve_download`、公共正文导出器。
- 公开数据：虚构 scenic 目录、资产清单、自创笔记与材料目录、KB 候选文件、15 条平台知识回归题。

接口契约版本：`1.0.0`。A 内部函数名保留；D 应依 `contracts/integration-conventions.md` 注册为 `search_scenic_spots`、`search_study_materials`，并接入 `/api/v1/scenic/spots` 和 `/api/v1/study/materials` 等既定路径。公共 schema 未更改。

测试命令和实际结果（2026-09-23）：

```powershell
cd backend
C:\Users\29950\AppData\Local\Temp\nku-a-venv-20260923\Scripts\python.exe -m pytest
# 34 passed, 1 third-party deprecation warning

cd ..
node --experimental-strip-types --test frontend/src/features/scenic/geometry.test.mjs frontend/src/features/scenic/authoring.test.mjs frontend/src/features/study/demoCatalog.test.mjs
# 11 passed
```

两个 TSX 页经 esbuild `transformSync(..., {loader:'tsx'})` 语法检查通过；临时 TypeScript 5.9 + React 19 类型环境对 A 的六个 TS/TSX 文件做严格检查，0 条诊断；React 服务端渲染检查验证未知点位、缺底图和私有材料深链接错误态。仓库尚无 C 的 `frontend/package.json`/React 构建配置，因此未宣称完整前端构建、路由联调或浏览器端交互验收通过。

GitHub 交付：原仓库对 `sunjx3316-cell` 无直接写权限，已通过 Fork 工作流将 `feat/agent-a-map-review` 推送到 `sunjx3316-cell/nku-hw-AI-self-teamwork`，并创建指向原仓库 `main` 的 [PR #4](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/4)。等待负责人审查，未触碰或合并 `main`。

未解决问题：

- A10：D 的服务目前只有健康探针，未注册 A 的 REST/MCP 工具；真实 HTTPS、平台知识库导入和 GenioS 调用未完成。
- A11：没有真实底图、照片、花期来源或获授权的课程资料。页面和知识库明确为 demo。
- A12：B/C/D 尚未完成全体 P0 联调，不能替其签收最终演示范围。

需要人工提供的素材或权限：见 `docs/blockers/A-assets.md`。真实材料进入仓库前须确认来源、许可、日期、版本及位置。

给 C 的下一步：

1. 在公共路由中挂 `ScenicPage`→`/tools/map`、`StudyPage`→`/tools/study`；不要改 A 组件名称。
2. 用共享 API client 向两个组件传入已权限过滤的目录数据；当前默认 props 是本地虚构 demo。
3. 完整运行 React/TypeScript/Vite 构建并做深链接、浏览器后退和窄屏交互检查。
4. `StudyPage` 的 `enableDownloads` 默认关闭；D 接通下载路由后再启用。不要把私有目录传到浏览器。

给 D 的下一步：

1. 由后端可信 `Principal` 调用 A 的纯函数，构造统一信封并注册既定 REST/MCP 名称；`APP_ORIGIN` 经核验后再拼白名单深链接。
2. `resolve_download` 只返回被目录白名单校验过的本地文件路径，D 负责登录/访问控制和 FileResponse。
3. 在 GenioS 试导入 `knowledge/study/exports/KB_Study_demo.md` 和 `knowledge/scenic/KB_Scenic_demo.md`，再按 `A-knowledge-test-cases.md` 实测引用和工具返回；测试成功前不可说已接入平台。
4. 私人资料访问需另行审查身份绑定；当前 A 服务只暴露公开且已授权目录。
