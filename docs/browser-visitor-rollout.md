# 独立浏览器访客（免注册）

本轮不依赖管理员 SSO，不创建腾讯云普通用户，不开放匿名数据库读写。

**维护入口：这是必须保留的团队身份基础设施。** 固定设备绑定已在 PR #13 合入；免注册访客的后续实现此前未上传，现单独补交。其源码并非 B 的课表解析逻辑；勿因缺配置、未执行迁移或只看到旧封闭测试说明而删掉它。

## 完整链路与源码索引

```text
Agent 给课表/日历链接 → 工具站未登录时进入固定设备码页
  ├─ 新用户：点击免注册开始使用 → 本浏览器空白私有空间
  │          → 在同一浏览器明确允许插件 OAuth → 发送设备绑定句
  └─ 已有 Agent 授权：先发送新浏览器设备绑定句 → 检查绑定并进入原空间
本人 OAuth grant → 服务端 owner → 本人的课表/日历
```

| 环节 | 代码/文件 |
| --- | --- |
| 免注册入口、保留原账号登录 | `frontend/src/features/auth/CloudbaseLoginPage.tsx` |
| 创建/恢复访客的同源 POST | `backend/app/visitor_site.py` |
| 固定码生成、绑定页、只读查看设备码 | `backend/app/agent_device_site.py` |
| 可信会话恢复、路由门禁与启动依赖检查 | `backend/app/cloud_identity_site.py` |
| Agent OAuth owner 与 devices:bind 校验 | `backend/app/core/competition_oauth_provider.py` |
| 身份 RPC 传输操作白名单（不能漏访客操作） | `backend/app/core/cloud_identity_store.py` |
| 新增私有访客登记表/服务端 RPC 包装 | `deploy/cloudbase-identity-pilot/browser-visitor-migration.sql` |
| 既有固定设备私有表/RPC | `deploy/cloudbase-identity-pilot/agent-device-binding-migration.sql` |
| 构建包必须携带新迁移 | `backend/scripts/build_cloud_identity_package.py` |
| 契约/虚构正反例 | `contracts/api.schema.json` 的 `BrowserVisitorStartRequest`、`fixtures/browser-visitor.example.json` |
| 后端真实本地 PG 集成/前端测试 | `backend/tests/test_browser_visitor.py`、`backend/tests/test_agent_device.py`、`frontend/src/features/auth/visitorLogin.test.tsx` |

接口入口：`/tools/device-login` 为固定码及首次开始页，`/tools/device` 只读查看设备码；访客开始请求 `POST /api/v1/auth/visitor/session` 的 JSON 必须是 `{}`，不得传 user、owner、workspace 或 DEV 码。返回复用 `CloudBrowserSession` 信封；DEV 码通过设备端点获得，不是会话密钥。

## 开发配置与依赖顺序

后端入口是 `app.cloud_identity_site`，不是公开地图/MCP 内容服务；前端使用 `pnpm --filter web build:identity`。原身份配置（HTTPS APP_ORIGIN、既有批准的两注册账号、服务端数据库权限、固定 OAuth client/callback）仍须完整。浏览器访客不扩这两注册账号，也不替代学校 Agent 体验名单。

以下是公开的功能开关名，不包含真实 UID、密钥或客户端秘密：

```dotenv
CLOUD_IDENTITY_PILOT_ENABLED=true
CLOUDBASE_AUTH_PILOT_ENABLED=true
CLOUDBASE_AUTH_PROFILE=pg_registered
CLOUD_OAUTH_PILOT_ENABLED=true
CLOUD_OAUTH_COMPETITION_COMPAT_ENABLED=true
CLOUD_NOTICE_TEXT_PILOT_ENABLED=true
CLOUD_TASK_CALENDAR_ENABLED=true
CLOUD_PERSONAL_TASKS_ENABLED=true
CLOUD_PERSISTENT_AUTH_ENABLED=true
CLOUD_PERSONAL_SCHEDULES_ENABLED=true
CLOUD_AGENT_DEVICE_BINDING_ENABLED=true
CLOUD_VISITOR_ENABLED=true
```

缺任一依赖、身份配置或迁移应拒绝启动，不允许通过取消校验或删除代码“修好”。默认开关均不因此变为 true。

仅全新测试库按顺序执行：`schema.sql` → `competition-oauth-migration.sql` → `notice-text-migration.sql` → `task-calendar-migration.sql` → `task-oauth-scopes-migration.sql` → `personal-tasks-migration.sql` → `persistent-auth-migration.sql` → `personal-schedules-migration.sql` → `device-login-migration.sql` → `agent-device-binding-migration.sql` → `task-delete-migration.sql` → `browser-visitor-migration.sql`。测试 driver 演示此顺序。
**已有云库不要重跑 schema 或任何已执行迁移。** 访客迁移非可重复执行脚本：先确认前置 RPC/表与应用记录，再按审阅和授权范围执行一次；已部署的原环境无需为本 PR 重跑迁移。

Agent 沿用同一插件 OAuth，`bind_my_browser` 必须保留。授权 Scope 包含 `devices:bind`，读写课表/待办仍按原相应权限；旧授权不会自动获得新权限，首次需要本人重新允许。追加规则见 `deploy/genios-workflows/browser-visitor-agent-append.txt`。不能用 MCP_SERVICE_TOKEN 或学校登录冒充本人 grant。

## 用户流程

1. 从 Agent 打开课表或待办日历。入口自动生成本浏览器固定设备码。
2. 首次点击“免注册开始使用”，生成独立空白私有空间，无需账号密码。
3. 在同一浏览器点击 Agent 的插件授权链接，允许访问当前工具站空间；然后发送页面生成的设备绑定请求。
4. Agent 根据已授权的服务端身份查询课表和日历，不根据学校学号、昵称、聊天文本或公开设备码猜测身份。
5. 换浏览器默认是另一身份；如明确绑定已有 Agent 授权身份，可读取同一空间。已经登录不同身份的浏览器不能被覆盖或静默合并。

公开 DEV 码只是定位符，不是登录凭证。随机私密凭证只保存在 Secure、HttpOnly、SameSite=Strict Cookie；不进入链接、Agent 或前端存储。
访客身份不是实名学校账号；共用同一浏览器配置会共用该身份，不适用于公共电脑。清除全部本站浏览器数据会丢失身份；无其他已绑定设备时无法找回。
退出会撤销来源会话和旧 Agent 授权。保留固定设备私密 Cookie 时，可主动重新开始同一访客空间，但不会复活旧授权。

## 部署范围与回退

- 执行 `deploy/cloudbase-identity-pilot/browser-visitor-migration.sql` 一次。只新增私有访客登记表和受 service_role 限制的 RPC 包装器；不迁移或删除既有课表、日历。
- 原服务更新部署包，新增 `CLOUD_VISITOR_ENABLED=true`。必须已有个人课表、日历、持久身份及固定设备 OAuth 功能；缺失即拒绝启动。
- 原注册账号校验与学校 Agent 名单保持不变。访客登记上限 5000；新建/恢复入口 10 次/分钟来源限流；每访客至多 20 个活动来源会话。公开运营前仍需评估网关真实来源、配额、清理和恢复方案。
- 回退关闭开关或恢复原容器版本；不删除访客表或用户数据。旧版配置同步由新 RPC 包装器保留访客登记。
- `dataset_kind: demo` 在旧会话接口中为兼容常量，不是已导入课程来源。真实课表的来源以 TimetableImport 的 personal 和本人确认校历为准。

## 验证状态

下段及云端记录是 2026-10-09 的历史验收，不是本 PR 新一轮上线。2026-10-10 源码 PR 的重新测试结果见交接和 PR 正文。

本地真实嵌入式 PostgreSQL：独立访客保存、跨空间拒绝、Agent 授权同源读取、设备绑定拒绝错账号、重启读回、退出撤销与不复活、公开设备码不能登录已通过。既有账号相关后端回归 60 项及前端 203 项通过；现场部署、真实学校平台授权验收不能以本地测试替代。

### 2026-10-09 云端上线记录

- 用户明确批准：新增私有访客表并启用免注册，不公开旧数据、不创建腾讯云用户、不扩学校 Agent 名单。
- 私有迁移已执行；RLS 开启，匿名和 authenticated 角色不能执行数据库 RPC。执行前后既有个人课表 1 份、个人事项 5 条、旧课表记录 5 条数量不变。
- 033 首次部署失败：生产传输白名单漏了 `visitor_probe / visitor_begin / visitor_status`。已补齐固定操作清单，新增传输层测试并让访客 SQL 联合测试实际经过该清单；没有绕过启动检查。
- 原服务 034 正常，100% 流量；`/healthz` 返回 `cloudbase-identity-pilot-20261009-r37-visitors`，访客开关启用。
- 包 SHA-256：`15c2cc5c14e7a7c75d3579c797c4d066918bc8af7fe84f62a3032da0c79aa8f7`，199 个文件，无凭证文件。
- 云端新建两个空白 QA 访客会话：各自无课表/日历数据、工作区不同、跨工作区 404、无登录私有读取 401、外站发起 403、伪造归属 422；设备码稳定、重复开始和会话恢复保留原工作区。没有写入或删除任何课程、待办。
- 本人既有浏览器刷新课表后仍显示原个人课表版本 3、原保存时间和本人确认校历；没有被访客身份覆盖。新入口显示“免注册使用校园助手”，原账号登录仅作为折叠入口保留。
- 测试凭证只存在检查进程内存，没有导出浏览器 Cookie。真实同伴的学校 Agent 插件授权仍须本人在同一浏览器明确点允许，不能据此宣称已代其完成授权。
