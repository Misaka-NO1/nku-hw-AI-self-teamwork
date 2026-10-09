# N26 当前成果与团队接入交接

更新时间：2026-10-07。本次负责人明确要求把现有成果上传 GitHub，补充到现有 PR #10；不自动合并。
N20–N25 记录各轮历史操作，本文件说明当前状态，不将旧的“未接通/未发布”描述当作现状。

## 已上线的当前版本

- 身份工具站：r23 / 部署版本 023，课表、地图导航、本人待办日历可用；删除前端演示入口及内存模拟保存分支。
- 学校主 Agent：v0.2.11，原两人渠道审批已通过。插件已发布并绑定本人日历读取、生成草稿、确认保存工具。
- 待办链路：通知整理 → 生成本人草稿 → 用户明确确认 → 数据库保存 → 工具读回 → 前端刷新可见。保存失败不得回复成功。
- 独立“查看待办时间”入口：实际读取本人未完成事项，按时间逐条列出，末尾给出本人日历链接。不是打开平台自动触发，不做后台推送。
- 长期本人授权：新登录及新同意可使用长期模式；退出、撤销授权、移出名单仍失效。旧会话/旧授权不会因迁移自动延期。
- 两账号数据隔离：owner 来自服务端核验的会话或 OAuth 授权，模型和前端不能指定另一人的 owner/workspace；跨账号切换先清除旧页面数据。

入口：

- [正式 Agent](https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg)
- [本人课表](https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com/tools/timetable)
- [本人日历](https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com/tools/calendar)
- [赏景地图](https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com/tools/map)

## 功能边界

六个方向仍为校园赏景、复习资料、课表、通知与待办、校园事务与课程经验、培养方案与学分。
课表模块负责显示课表与周次；查冲突及推荐完成时间属于通知与待办，不合并成“课表与空闲时间”模块。

通知场景区分如下：

1. DDL 作业/任务：读取本人课表和已有安排，给可选择的空档；不强制先填预计耗时，可选择多个时段。
2. 固定活动/集合提醒：保留通知给出的时间，单纯提醒无需结束时间，不凭空生成忙碌区间。
3. 多场次活动/任务：比较备选时段与本人已保存的占用，给候选，由用户选择后确认。

周内 12:00–14:00 不推荐安排；候选充足时优先较完整的空档，排除课间碎片。
晚上可描述为“空余时间直到睡觉前”，具体结束时刻由用户确定；未确定的自然语言不能假装已写成精确区间。
无年份的月日按参考时间的当年解析，历史日期明确提示，不自动滚到下一年；非法或矛盾日期需要核对。

课表/培养方案/成绩仍包含明确标注的虚构演示数据，不是学校教务实时接入。十月课表来自
`fixtures/timetable-october-2026.simulation.json`，不可把它宣称为用户照片里的真实课表。
当前不声称六模块全部完成正式生产验收，不声称有后台推送或平台打开自动提醒。
A 已通过正式用户端读取、确认保存和刷新读回；B 的首次长期登录与同意仍需本人执行。

## D、B、C 如何接着用

先检出 PR #10 的分支 `codex/calendar-notice-resume-20261006`。
现有学校访问名单不扩大，数据库不公开；未注册或不在名单的同学可运行本地测试、审阅源码和工具契约，
线上体验/编辑权限需负责人配置具体已注册成员，不能共用 A 的身份令牌来冒充 B/C/D。

- D：通知阅读与三场景工作流见 `deploy/genios-workflows/README-notice-three-scenarios.md`；主 Agent 六方向路由、本人待办规则、工具 OpenAPI 均在同目录。结合这些文件继续部署/调试，不手填虚构保存回执。
- B：时间与课表处理沿用后端计算接口，日历模型需保留一条事项的全部已选时段；提醒点/仅截止日期不占用全天。
- C：事务及培养方案规则继续沿用可追溯来源；演示学分和未知政策不能推断真实毕业结论。
- 前端：`CalendarPage.tsx` 只读核验后的本人数据；导航由 `frontend/.env.identity` 的公开地址配置。不要把凭证写入任何 `VITE_*` 变量。

本人待办工具契约：`deploy/genios-workflows/personal-task-tools.openapi.json`。
读取为 `GET /oauth/tasks/entries`；生成草稿为 `POST /oauth/tasks/entries/drafts`；确认保存为 `POST /oauth/tasks/entries/commit`。
读取使用 `tasks:read`，草稿/保存使用 `tasks:write`；沿用精确 OAuth 回调和既有客户端认证。
保存必须沿用工具实际返回的 `draft_id`、`payload_hash`，并带明确确认与幂等键；不能猜 ID 或只改提示词冒充写入。
浏览器同类接口前缀为 `/api/v1/tasks/entries`，仍需要本人会话及 CSRF 校验。

## 部署注意

当前环境已经执行所需增量迁移，接续开发不要重跑旧 `database-migration.sql` 或覆盖已包装的 RPC。
迁移源码包含 `task-oauth-scopes-migration.sql`、`personal-tasks-migration.sql`、
`persistent-auth-migration.sql` 和十月夹具迁移；新环境须审阅既有基础迁移与依赖顺序后单独执行，不能盲目整包重放。
长期开关默认关闭；只有满足已有本人日历/OAuth 配置并核对数据库迁移后才能开启。
保持现有两账号名单、逐用户归属、CSRF、同意、退出及撤销规则，不用“取消限制”替代身份安全。
后台数据库密钥、OAuth secret 仅在部署后台配置，仓库及前端不包含其值。

构建命令（分别在 frontend 和仓库根目录执行）：

```powershell
npm run build:identity
python backend/scripts/build_cloud_identity_package.py --name cloudbase-identity-pilot-NEW-UNIQUE-NAME
```

打包名称需改为唯一、小写字母/数字/连字符名称；已有包不覆盖。
本次上传源码、迁移、测试和交接，不上传 dist、node_modules、数据库测试目录、凭证或部署截图。

## 本次提交前回归

- 前端全量：19 文件、167 项通过，包含账号切换、日历显示与无演示回退。
- Node 通知校验、待办工具契约及 identity 导航配置：20 项通过。
- 后端长期授权/本人隔离/包装/十月课表：28 项通过，使用本地 PostgreSQL 与 HTTP 集成测试。
- 原有身份及两种 OAuth 回归：75 项通过；本次后端回归共 103 项。
- TypeScript 检查及 identity Vite 构建通过；存在单个大 chunk 体积警告，不是构建失败。

本地身份接口模拟不能代替线上 CloudBase 或学校验收。实际线上部署与 A 用户端记录见 N23–N25；
本次 GitHub 上传不再执行迁移、不修改权限、不重新发布学校配置。
