# 日程单项删除（2026-10-09）

## 功能与边界

- 保留原「取消事项」，新增独立「删除事项」。未完成、已完成、已取消均可删除。
- 先点事项，再点删除；确认区展示实际标题，说明页面不可恢复及已导出 .ics 副本需要自行删除。
- 明确确认后服务端删除本人单条已保存事项及其日历状态，再重新查询确认不存在；不乐观移除，不把失败当成功。
- Agent 的现有已保存事项查询、日历与空闲时间查询不再读取已删除的活动记录。原始草稿和审计保留，不等于完整数据擦除。
- 新接口仅接受已有浏览器登录、Origin/CSRF、本人工作区、当前版本与幂等键；账号归属从服务端会话派生。
- 同一请求重试返回相同回执，旧版本拒绝；旧草稿提交重试不能使已删除事项复活。
- 不增加账号、密钥、OAuth 权限或名单。未修改 Agent 提示词或发布新的 Agent 版本。

## 文件

- 前端：`frontend/src/features/calendar/{CalendarPage.tsx,api.ts,model.ts}`。
- 服务端：`backend/app/api/task_calendar.py`、`backend/app/core/{task_calendar.py,cloud_identity_store.py}`。
- 契约：`contracts/api.schema.json` 新增可选 deletion 能力。
- 新迁移：`deploy/cloudbase-identity-pilot/task-delete-migration.sql`。
- 打包：`backend/scripts/build_task_delete_package.py`，基于已上线 r34，仅替换前端和四个明确列出的后端/契约文件，其他 96 个非前端文件及扩展 ZIP 校验保持一致。

## 测试

- 前端 203 项通过，生产构建通过；覆盖确认/保留、失败重试、读回不一致和请求/回执校验。
- 后端删除、日历与个人事项隔离回归共 36 项通过，使用隔离本地 PostgreSQL 测试数据库。
- 删除专项 8 项覆盖三种状态、两种旧数据来源、个人新事项、跨账号、错误 Origin/CSRF、旧版本、重启持久性、Agent 查询及旧草稿重放。
- `git diff --check` 通过。没有删除任何线上用户事项进行测试。

## 部署

- 包：`dist/cloudbase-identity-pilot-20261009-r35.zip`。
- SHA256：`5fbcca5d107bb6d25a56285552e8735ff660f0cd460cd5d959759398823f23dd`。
- JS / CSS：`index-DDfOH7k2.js` / `index-MpeLSLMM.css`。
- 数据库迁移执行成功，影响 0 行；只读验证 installed=true、回执表 RLS=true、anon/authenticated EXECUTE=false、service_role EXECUTE=true。
- 腾讯云部署 032：正常，100% 流量；实例详情核验 `nku-campus-identity-pilot-032-554bd7fdd-2jcjm` 为 Running。
- 公开新版 JS 返回 HTTP 200，包含删除按钮及 `/calendar/delete` 调用。`/healthz` 返回 HTTP 200、status=ok；build_id 沿用原环境 r33，不作为本次版本标识。
- 上线截图：`artifacts/calendar-delete-deploy-032-20261009.png`。
- 内置验收浏览器尚未绑定本人 Agent 账号，日历正确阻止访问；没有擅自绑定。已绑定的用户浏览器刷新后验收按钮。

## 使用

刷新待办日历，点任一事项打开详情 → 删除事项 → 核对标题 → 确认删除事项。取消仍保留记录；删除后不再显示，不能通过页面恢复。
