# B 的前端 feature（import / timetable）

这两个目录是 B 拥有的前端 feature，遵守以下约定（见 contracts/integration-conventions.md）：

- 默认导出页面组件：`ImportPage`（`/tools/import`）、`TimetablePage`（/tools/timetable），路由接入由 C 负责。
- 解析逻辑全部来自 `@campus/import-core`（B01/B02），页面不重复实现周次/节次解析。
- 只使用公开构建变量 `VITE_API_BASE_URL`；不接触票据、MCP token 或教务凭据。
- 当前仓库尚无前端骨架（C 负责 `frontend/src/app` 与根配置），本 feature 以纯 React + TypeScript 编写，
  未在浏览器中验证；待 C 的骨架就绪后接入路由并排期端到端验证。

## 文件

| 文件 | 说明 |
|---|---|
| `import/ImportPage.tsx` | 文件导入 → 本地解析 → 预览 → 缺失字段/覆盖范围提示 → 用户确认后才允许服务端校验 |
| `import/api.ts` | feature 内 API client（validate/import-drafts）；C 共享 client 就绪后可替换 |
| `timetable/TimetablePage.tsx` | 周课表网格：星期 × 节次、课程卡片、周次选择、coverage 与未确认提示 |
