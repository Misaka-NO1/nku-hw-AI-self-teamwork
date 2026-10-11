# 免账号密码身份：统一页与身份优先保护

本轮不依赖管理员 SSO，不创建腾讯云普通用户，不开放匿名数据库读写。

**2026-10-11 当前源码行为：未知浏览器不能匿名创建账号或空间。** 原先按浏览器创建访客会导致同一使用者新开无痕窗口时得到第二个身份，本轮已关闭该入口。恢复既有身份、Agent 本人授权接入原空间及原账号登录保留。下面的 2026-10-09 上线记录为历史证据，不代表新版已经部署。

**维护入口：这是必须保留的团队身份基础设施。** 固定设备绑定已在 PR #13 合入；免注册访客的后续实现此前未上传，现单独补交。其源码并非 B 的课表解析逻辑；勿因缺配置、未执行迁移或只看到旧封闭测试说明而删掉它。

## 完整链路与源码索引

```text
Agent 给课表/日历链接 → 工具站未登录时进入统一身份页 /tools/login
  ├─ 原浏览器：保留私密身份 → 恢复原空间 → 必要时本人重新授权
  ├─ 新浏览器：生成公开设备码（不建身份） → 发送本人绑定句
  │          → 沿用原 Agent 插件授权 → 核验绑定 → 接入同一空间
  └─ 完全新用户：没有可信身份则拒绝创建，须先有支持的本人身份登录
本人 OAuth grant → 服务端 owner → 本人的课表/日历
```

| 环节 | 代码/文件 |
| --- | --- |
| 免注册入口、保留原账号登录 | `frontend/src/features/auth/CloudbaseLoginPage.tsx` |
| 三步统一页面、归属核验、已有空间分流 | `frontend/src/features/auth/IdentityOnboarding.tsx` |
| 创建/恢复访客的同源 POST | `backend/app/visitor_site.py` |
| 固定码生成、绑定页、只读查看设备码 | `backend/app/agent_device_site.py` |
| 可信会话恢复、路由门禁与启动依赖检查 | `backend/app/cloud_identity_site.py` |
| Agent OAuth owner 与 devices:bind 校验 | `backend/app/core/competition_oauth_provider.py` |
| 身份 RPC 传输操作白名单（不能漏访客操作） | `backend/app/core/cloud_identity_store.py` |
| 新增私有访客登记表/服务端 RPC 包装 | `deploy/cloudbase-identity-pilot/browser-visitor-migration.sql` |
| 拒绝未知浏览器匿名建立身份，保留既有访客恢复 | `deploy/cloudbase-identity-pilot/visitor-identity-first-migration.sql` |
| 既有固定设备私有表/RPC | `deploy/cloudbase-identity-pilot/agent-device-binding-migration.sql` |
| 构建包必须携带新迁移 | `backend/scripts/build_cloud_identity_package.py` |
| 契约/虚构正反例 | `contracts/api.schema.json` 的 `BrowserVisitorStartRequest`、`fixtures/browser-visitor.example.json` |
| 后端真实本地 PG 集成/前端测试 | `backend/tests/test_browser_visitor.py`、`backend/tests/test_agent_device.py`、`frontend/src/features/auth/visitorLogin.test.tsx` |

接口入口：开启访客和设备绑定时，`/tools/device-login` 校验返回地址后 303 到统一页面 `/tools/login`；`/tools/device` 仍只读查看设备码。`POST /api/v1/auth/agent-device/state` 使用同源 `{}` 与 `X-Campus-Device: 1`，仅核对当前 Cookie 会话、签名上下文与设备绑定；不创建、续期、领取或切换身份。返回公开设备码、是否有空间、是否完成 Agent 关联以及非凭证的空间核对标识，不返回 owner 或私密凭证。

原访客开始端点 `POST /api/v1/auth/visitor/session` 现在只恢复已有有效会话，或由服务端私密 Cookie 已登记的旧访客身份。没有私密证明或证明未知返回 401；已有其他授权待绑定返回 409；不新增账号或空间。JSON 仍必须是 `{}`，不得传 user、owner、workspace 或 DEV 码。返回复用 `CloudBrowserSession` 信封；DEV 码不是会话密钥。

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

仅全新测试库按顺序执行：`schema.sql` → `competition-oauth-migration.sql` → `notice-text-migration.sql` → `task-calendar-migration.sql` → `task-oauth-scopes-migration.sql` → `personal-tasks-migration.sql` → `persistent-auth-migration.sql` → `personal-schedules-migration.sql` → `device-login-migration.sql` → `agent-device-binding-migration.sql` → `task-delete-migration.sql` → `browser-visitor-migration.sql` → `visitor-identity-first-migration.sql`。测试 driver 演示此顺序。
**已有云库不要重跑 schema 或任何已执行迁移。** 新身份优先迁移在既有访客迁移之后执行一次，只包装 RPC，不删除、合并或迁移数据。服务端要求 `visitor_probe` 版本 `browser-visitor-identity-first-v2`；缺少新保护必须拒绝启动，不能偷偷回退旧匿名创建函数。旧函数对 PUBLIC/anon/authenticated/service_role 全部撤销执行权。

Agent 沿用同一插件 OAuth，`bind_my_browser` 必须保留。授权 Scope 包含 `devices:bind`，读写课表/待办仍按原相应权限；旧授权不会自动获得新权限，首次需要本人重新允许。追加规则见 `deploy/genios-workflows/browser-visitor-agent-append.txt`。不能用 MCP_SERVICE_TOKEN 或学校登录冒充本人 grant。

## 用户流程

1. 从 Agent 打开课表或待办日历。入口自动生成本浏览器固定设备码。
2. 统一页先核验本人身份，不提供匿名新建按钮。新浏览器生成设备码后，在原来已授权的 Agent 中发送绑定请求。
3. 回本页点击“核验身份并接入空间”，服务端用可信来源授权核验，进入原账号的空间；不会用一个新访客替换旧授权。原浏览器已退出但保留私密身份时可选择“恢复本浏览器原有身份”，未知身份仍拒绝。
4. Agent 根据已授权的服务端身份查询课表和日历，不根据学校学号、昵称、聊天文本或公开设备码猜测身份。
5. 学校插件新授权必须在已接入原空间或已登录本人账号后明确同意。核验失败或绑定身份不同，不创建覆盖、不静默合并；失败重检隐藏之前的进入按钮。

### 一账号一空间的准确边界

数据库 `owner_workspaces.subject_id` 主键保证一个**服务端 OAuth owner** 对应一个空间；同一授权账号绑定不同浏览器会复用它。学校 Agent 目前没有可验证的校园账号唯一标识，因此本轮阻断未知身份创建，而不是靠用户自称“首次”继续创建。已有多个旧访客空间不自动去重、删除或合并。真正首次用户没有可信工具站身份时仍需要受支持的身份登录；学校登录、昵称、学号或公开设备码不能代替该身份，不能声称完成了所有校园账号的免注册首次入驻。

2026-10-11 改动新增的是限制匿名创建的 RPC 包装迁移，不增加用户、密钥或权限，不清除任何已有课表/日历。源码和本地验证不是生产上线回执，部署须保留线上已有的 B 课表上传修复。

公开 DEV 码只是定位符，不是登录凭证。随机私密凭证只保存在 Secure、HttpOnly、SameSite=Strict Cookie；不进入链接、Agent 或前端存储。
访客身份不是实名学校账号；共用同一浏览器配置会共用该身份，不适用于公共电脑。清除全部本站浏览器数据会丢失身份；无其他已绑定设备时无法找回。
退出会撤销来源会话和旧 Agent 授权。保留固定设备私密 Cookie 时，可主动重新开始同一访客空间，但不会复活旧授权。

## 部署范围与回退

- 旧库仅审阅并执行 `visitor-identity-first-migration.sql` 一次；不要重跑原访客登记迁移。新包装器阻断匿名新建，不迁移或删除既有课表、日历。
- 原服务更新部署包，保留 `CLOUD_VISITOR_ENABLED=true` 以恢复既有访客身份。必须已有个人课表、日历、持久身份及固定设备 OAuth 功能；缺失即拒绝启动。
- 原注册账号校验与学校 Agent 名单保持不变。访客登记上限 5000；新建/恢复入口 10 次/分钟来源限流；每访客至多 20 个活动来源会话。公开运营前仍需评估网关真实来源、配额、清理和恢复方案。
- 回退必须保留身份优先数据库守卫；不能为兼容旧页面撤销守卫或恢复匿名创建。旧版容器可能因 probe 版本不匹配无法启动，需兼容新版保护的应用版本；不删除访客表或用户数据。
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
