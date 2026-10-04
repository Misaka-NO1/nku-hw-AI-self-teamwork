# 云端身份与业务持久库封闭试点

## 2026-10-04 13:47 更新：截止字段已修复并实际验收

主Agent本人截止检查20分钟/最早09:40实际Input与Output一致，真实candidate_slots为09:40–10:00，request_id=692e167f-79e8-42b4-a671-b9e18afd57f4。学校输出定义补齐candidate_slots并保留conflicts；修改后活动回归真实两交集，request_id=684b0723-a81b-43fe-b7b9-9c850c7a0b86。日期仅精确到天且耗时未知时返回空列表与due_time/estimated_minutes待确认，request_id=a61c5fd0-7187-464e-99a0-5f0a4c75624a；不补23:59或借历史耗时。此前输出字段遗漏导致的猜测回复不计入通过，失败记录保留在D11。

现有固定虚构数据链路通过不代表真实教务或全部功能成品。主Agent仍未发布；平台发布渠道提示须先发布配置，尚未执行。不同学校用户评委入口、数据库Key跨当日18:21:48续期仍需负责人明确授权；未整体验收不提交Git。后端013/r12、SQL、权限和密钥保持原样。

## 2026-10-04 13:12：013/r12学校与主Agent读通

线上既有服务013/r12正常100%。学校真实授权callback与A/B本人records、时间工具已通过，三只读工具已团队发布/主Agent草稿绑定；退出后401、B不含A记录。没有新迁移、Key、TTL或范围改变，仍仅虚构数据，指定Key当日18:21:48到期，未公开发布主Agent。详见[D11实证](../../docs/evidence/platform/D11-all-features-integration-2026-10-04.md)。

## 2026-10-04 12:06：013/r12实际生效

013正常100%流量/1实例，r12仅成功同意HTML采用same-origin来源策略并允许已批准精确学校callback的form-action；不接受null/missing/外站Origin，不新增scope或SQL。学校实际OAuth同意/回调/read_my_demo_records读A原数据成功，本人空档成功。Key仍当日18:21:48到期，不自动延期。完整后端574、专项80通过；学校B隔离和主Agent绑定待验，最新见docs/evidence/platform/D11-all-features-integration-2026-10-04.md。

## 2026-10-04 实际部署状态

011/r10已正常100%切流。r9批准的普通OAuth开关已启用；三表迁移已经执行，不重跑旧或新迁移。
完整导航/固定C审计已经上线，学校C知识库与学分正反例通过。OAuth同意提交被内置浏览器屏蔽，学校本人records尚待实测。
短期Key18:21:48到期；不自行续期或借用长期Key。下方“尚未启用”是历史候选，最新证据为docs/evidence/platform/D11-all-features-integration-2026-10-04.md。

## 当前参赛接入候选（2026-10-03；尚未启用线上）

负责人选择“先让学校 Agent 接通虚构演示”，新增普通保密客户端 OAuth 兼容模式。
原严格 S256 模式不变；不要重跑旧 database-migration.sql，不删除旧表/服务。
仅一次执行独立 **competition-oauth-migration.sql**：新增 nku_competition_oauth_v1
三张授权表和 service_role 固定 RPC；不修改旧 15 表或身份核验。
现有服务更新后，显式同时设置 CLOUD_OAUTH_PILOT_ENABLED=true、
CLOUD_OAUTH_COMPETITION_COMPAT_ENABLED=true，保留现有客户端 ID/密钥 hash/精确回调配置。
启动和健康检查验证新旧两个 schema；关掉兼容开关可回到严格模式（该模式仍需 PKCE）。
只读 demo:read，两个普通测试账号，已有本人课表/待办和时间查询；无 refresh、真实上传或 Agent 保存。
学校插件需逐用户登录授权后实测，不能仅用本地测试宣称上线。线上切换需具体确认。
测试域名、短期数据库 Key 保持现状；不买域名、不续长期授权、不公开发布主 Agent。

2026-10-03 19:05：009的A/B在线身份、原课表/两个独立任务更新后持久读回、双向新草稿NOT_FOUND通过；A本人时间检查3处冲突/coverage限制保留。正常新开/tools/login可用，不更改Cookie/Header或域名，不把健康提示页现象扩大成所有业务不可用。本次未重新确认保存/幂等重放/PG并发，不称学校OAuth通过。负责人选择保留测试域名，未购买或绑定域名。最新实际证据详见D10健康诊断补充；下方18:39未重验状态为历史。

2026-10-03 18:39：负责人自行填写新一期1天Key并提交009/task2281159，同一r8包已正常、100%流量、1实例。按完整009实例名查询，实际18:33:26启动完成，18:35:43 `/healthz` build=identity-pilot-20261003-r8 status=200/86ms，严格PG schema探针通过。未取得浏览器JSON正文，009两账号业务与学校逐用户授权未重验。内置浏览器仍停在腾讯云测试提示页；正式入口需已备案自定义域名，未购买、绑定或绕过。新Key到期2026-10-04 18:21:48，长期运行授权未解决。OAuth仍false、个人上传仍关闭，无Git提交。下方008/007失效状态为历史，详见docs/evidence/platform/D10-health-diagnostics-2026-10-03.md最新节。

2026-10-03 18:14：r8/008镜像构建成功但实际部署失败，容器lifespan的数据库probe返回DEPENDENCY_UNAVAILABLE后退出。原一天Key于17:53:36到期；只核对指定项名称和日期，未读值或借用长期Key。007仍是100%生效表版本，实际0实例/已暂停，不称恢复健康。新一期授权需负责人确认并自行创建/填写，表单已准备1天、未创建。完整后端503项、前端110项、类型检查通过，不能替代云验收。OAuth仍false，未提交Git/PR。详见docs/evidence/platform/D10-health-diagnostics-2026-10-03.md。

2026-10-03 健康诊断候选：仅GET `/healthz`、`/__tcb_probe__`增加固定到达/完成日志，记录route、非敏感build、真实HTTP状态及耗时；不记录URL查询、Cookie、Header、request_id、账号、异常正文或业务请求。`/healthz`重验预期PG schema，错误schema返回503，不假报健康；无数据库探针保持独立。6项本地正反例通过；云端未能启动，尚无请求到达验收。OAuth仍false，未修改账号、SQL、权限、个人数据门禁或旧服务。

2026-10-03 12:54：005/r7已实际生效（正常、100%流量、1实例）。新容器中的独立课表页恢复本人会话并读回004保存的课表，同ID/版本/保存时间；待办原记录读回与双向草稿拒绝仍通过。默认日期9月7日/至少20分钟空档计算通过；9月21日原生日期自动填充未可靠更新React状态，待正常选择器复验，不算指定日期通过。完整后端497、前端110、tsc/构建通过。OAuth仍关闭，学校逐用户配对、真实个人数据和生产发布未验收。

2026-10-03 12:43 更新：负责人添加精确 Web 安全域名后，A/B 均实际通过腾讯云在线核验。A 课表与活动待办确认保存并取得数据库读回，B 保存不同截止任务；B 读取 A 草稿、A 重登读取 B 草稿都返回 NOT_FOUND，A 本人列表仍只有原活动。未开启 OAuth、未开放个人数据或发布主 Agent。

实测发现 /tools/timetable 新标签页仍只读标签缓存，r7 候选改为复用后端 Cookie 会话核验，未验证前不读取课表或查空档，按工作区切换重置视图、错误时闭锁。110 项前端测试、类型检查、生产构建通过；尚未云部署，不能把本地修复当云端课表页通过。无需新表、RPC、权限或后台 Key。详见 D10 平台证据；下方失败/待补记录均为此前历史。

状态：隔离数据库已在腾讯云建立；独立服务 004/r6 身份版正常、100% 流量、1 实例；OAuth 仍关闭，云端两账号保存与学校逐用户授权未验收。
2026-10-03 09:57:56 负责人提交 004（task 2278752），实际部署与生效表确认正常、100% 流量、1 实例。登录页实际脚本与 r6 一致；真实测试 A 的 SDK 返回固定代码 `SERVICE_ERROR · unreachable`，尚未取得 session、未进入后台保存验收。不能据此认定密码错误或具体网络原因；不改账号、认证策略或绕过浏览器限制。
2026-10-03 09:40:17 负责人提交 003（task 2278703），现场部署详情与生效版本表分别核对正常、100% 流量、1 实例。新登录页面在切流时曾返回 503，刷新后正常打开，不再被风险提醒阻挡。
首次真实云 SDK A 登录未返回有效 session；现有页面未区分供应商错误，尚不能断定是密码、来源或策略问题。用户名密码方式现场确认已启用；未重建账号或改变权限。学校主 Agent 草稿登录也已恢复，未发布主 Agent。
只细分脱敏登录错误的 r6 已在 004 生效；后端、契约与迁移相对 r5 无改动。
更新：负责人填好原短期后台 Key 后提交 002（task 2277696），2026-10-03 00:11:07 实际容器日志显示 Application startup complete，监听 8080。
身份开启、bootstrap 关闭的源码 lifespan 在启动完成前执行 probe/configure_subjects；实际只读 SQL 已核对 15 表/RLS/2 批准测试用户/4 夹具、后台专属 RPC 权限，工作区与待办均为 0。这证明启动接库，不是两账号业务验收。
此前负责人报告自己浏览器已验证健康页，自动化浏览器显示测试域名提醒。当前登录页已实际打开；另开 /healthz 遭浏览器 ERR_BLOCKED_BY_CLIENT，未取得健康 JSON，不换通道绕过该限制，不冒充已自动实测。
真实域名已从控制台核对：`https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com`。
后台 Key 已由负责人自行填写，仅检查非空布尔值，未读取值；002 已生效。不读取旧服务密钥、不创建新 Key、不延长原 1 天授权。
当前 r5 已在 003 生效，补齐跨标签页本人复核会话恢复及登录返回；实际云账号保存验收仍未通过，不需数据库迁移或新密钥。r4 完整后端回归 476 项通过（1 项第三方弃用警告）。
r5 本机完整后端 497 项通过（1 项第三方警告，59.04 秒），完整前端 90 项与类型检查通过；不算实际云浏览器或学校验收。
r6 本机前端 107 项、类型检查、生产构建通过；164 个 manifest hash 一致，无私有路径，相对 r5 仅 3 个前端构建文件新增/变化。包 SHA256：`7c0d0de77b86f1c15457a126486ef71bb2815e9dedb8db88613ba2711643b58a`。不展示供应商原始错误消息、响应、请求 ID 或未知字段，只显示固定错误类别/枚举代码；验证码/MFA 要求本人处理，不自动绕过。现场已取得 unreachable 固定码，根因和云端业务验收仍未确认。
它是 NK-GeniOS 的后端，不是替代 Agent 的聊天网站。浏览器工具页仅用于登录、复核和显式保存。

## 隔离边界

- 复用已批准的上海环境 `sunner-wang-d8ght8niaaaea70b7` 和已有 PostgreSQL。
- 只新增 `nku_identity_pilot_v1` 的 15 张表和 `public.nku_identity_pilot_v1_rpc`，不改旧表或旧服务。
- 只有 `service_role` 能执行固定 RPC；匿名/登录用户不能直读表，所有表开启 RLS。
- 只接受两个后台白名单普通测试用户，CloudBase introspect/user-me 在线核验；不相信 SYS_USERID、昵称或请求里的 owner。
- 固定虚构夹具、无公开注册、无真实成绩/个人课表上传。工作区 24 小时后拒绝访问；当前没有物理清理任务，不承诺到期已删除。
- 浏览器会话最长 900 秒；OAuth 同意/授权码最长 120 秒；令牌最长 600 秒且不能超过来源会话，不提供刷新令牌。
- 只授权 `demo:read` 或 `demo:read demo:draft`；Agent 不能确认或提交，保存必须在本人浏览器复核。
- 地图/复习资料导航指向原有公开服务，不覆盖 34 景点、91 张照片、33 份 PDF 或其服务。共享前端构建会包含已授权的共用派生资产，但不打包原照片目录。

## 生成部署包（不含任何凭证）

前端构建环境：`VITE_API_BASE_URL=/`，`VITE_PUBLIC_CONTENT_ONLY=false`，`VITE_IDENTITY_PILOT=true`。
`VITE_PUBLIC_CONTENT_ORIGIN` 设为已验收的公开资料服务 HTTPS origin；不要把后台 key/token 放进 VITE 变量。
可选 `VITE_GENIOS_AGENT_URL` 必须是负责人确认的用户入口，不能拿草稿编排页充当公开 Agent 链接。

在 frontend 目录运行已安装的 TypeScript 检查和 Vite 构建，输出到 `dist-identity`；然后从 backend 运行：

```text
.venv/Scripts/python.exe scripts/build_cloud_identity_package.py --name cloudbase-identity-pilot-20261003-r5
```

产物在根目录忽略的 dist 下。压缩包含 Dockerfile、后端、固定夹具、前端、数据库迁移及 SHA256 manifest。
不包含 backend/data、私有 pilot 配置、.env、原件、SQL 测试 node_modules 或 OAuth client secret。
已有包名拒绝覆盖。生成成功不等于上线成功；本机无 Docker，但 r3 的 001 镜像构建已在腾讯云成功。后续包仍需逐版部署验收。

## 执行顺序与配置

1. 先审阅迁移，确认只新建上述隔离对象。授权后在腾讯云 SQL 编辑器执行 `database-migration.sql`。不是覆盖脚本：对象已存在时停止，不删除重建。
2. 验证 15 张表 RLS、固定 RPC 执行授权、4 个夹具 SHA256；用实际 PostgreSQL 双连接验证锁/并发，PGlite 单连接测试不能证明云并发。
3. 创建隔离服务 `nku-campus-identity-pilot`，8080、最小资源、0–1 实例，优先现有额度。遇购买/升级停下。
   若创建前控制台不显示实际域名，先设 `CLOUD_IDENTITY_BOOTSTRAP_ENABLED=true`，两个业务 pilot 开关保持 false。
   此模式不读取数据库 key，不注册登录/OAuth/业务接口；仅容器探针和 `configuration_pending` 配置检查。
   创建后从控制台读取实际域名再配置 APP_ORIGIN，并将 bootstrap 关闭，身份试点开启；不能把配置检查当业务验收。
4. 首次保持 `CLOUD_OAUTH_PILOT_ENABLED=false`。设定下面后台环境变量，再部署；不更新原 MCP005/Tasks003/Public002。
5. 实际健康、A/B 登录、自己的草稿/确认/保存、刷新、重登、服务重启读回、跨账号拒绝通过后，再进入学校 OAuth 联调。

必须配置（部署后台，不在 Git/前端/学校模型变量）：

| 变量 | 值/作用 |
|---|---|
| APP_ENV | staging |
| AUTH_MODE / ALLOW_PERSONAL_UPLOADS | demo_fixture / false |
| CLOUD_IDENTITY_PILOT_ENABLED | true，仅完成隔离库后 |
| CLOUDBASE_AUTH_PILOT_ENABLED | true |
| CLOUDBASE_AUTH_PROFILE | pg_registered |
| CLOUDBASE_AUTH_ENV_ID | 固定批准的环境 ID |
| CLOUDBASE_AUTH_PILOT_USER_IDS | 两个现有普通测试 UID 的 JSON 数组，由后台配置；不发布 raw UID |
| CLOUDBASE_AUTH_SESSION_SECONDS / DEMO_WORKSPACE_TTL_HOURS | 900 / 24 |
| APP_ORIGIN | 实际新服务 HTTPS origin，无路径/query/结尾斜杠；不能猜域名 |
| CLOUDBASE_APIKEY | 已批准、未过期的后台数据库 key，负责人自行在后台填写；不读取旧服务密钥 |
| BUILD_ID | 与部署包对应的版本号 |

默认 Docker 配置不启用身份试点，缺少任一门禁启动失败，而不是退回匿名/管理员身份。
service_role key 有环境级权限，不是假装只限这 15 表；沿用短期授权，到期停止，扩大权限/时长须另行确认。
共享数据库限流不信任 X-Forwarded-For；云代理可能把两个测试用户归为同一来源。正式使用前须验证受信网关限流设计。

## 学校 OAuth：仍需实际验证

学校已观察到 OAuth2 Authentication Code 表单和固定回调：
`https://coze.nankai.edu.cn/product/llm/info/oauth`。
表单存在不等于运行时支持 S256 PKCE 或逐用户隔离。先在草稿插件验证真实请求。
需要负责人确认新授权并自行填写新的 client secret；后端只保存其 SHA256 digest，学校保密配置保存原值。

额外后台配置：`CLOUD_OAUTH_PILOT_ENABLED=true`、`OAUTH_CLIENT_ID` 与 `AGENT_PAIRING_AUDIENCE` 完全一致、
`OAUTH_CLIENT_SECRET_HASH`、精确的 `OAUTH_REDIRECT_URI`。启用前同步契约 §7。

| 学校插件配置 | 后端路径 |
|---|---|
| auth_url | 新服务 /oauth/authorize |
| access_token_url | 新服务 /oauth/token |
| Scope | demo:read（需要草稿时才加 demo:draft） |
| refresh_token_url | 留空，不支持刷新 |
| 只读工具 | GET /oauth/records |
| 本人空闲时段 | POST /oauth/time/free-slots |
| 本人冲突/截止可行性 | POST /oauth/time/check |
| 通知夹具草稿 | POST /oauth/task-drafts |
| 撤销 | POST /oauth/revoke（客户端认证） |

回调携带一次性 code/state；令牌只走受保护的 OAuth 通道，不能进入 Agent 提示词、query、日志、截图或资料库。
缺 PKCE、错 state/回调、同意拒绝、令牌过期/撤销、退出、白名单移除都必须拒绝。
不能用 Client Credential 或 SYS_USERID 文本冒充用户完成。
跨站首次导航无 Cookie 时，严格验证 client/callback/S256 等参数后转到本人登录页，
再回到同源授权页面；只保存公开的授权请求参数，不带令牌，不自动同意。
前端拒绝外站/approve/任意工具页/重复参数作为 return_to，缺失 Cookie 不退回匿名用户。
r5 候选另允许严格 `/tools/tasks`、`/tools/import` 及唯一安全 draft_id；登录后只是回原草稿，不自动保存。

## 跨标签页本人复核恢复（r5/r7 已部署，仅虚构试点）

身份模式 Tasks/Import 不相信当前标签页旧 sessionStorage，先用 GET
`/api/v1/auth/cloudbase/browser-session` 恢复本人当前 Cookie 身份；请求不带任何
query/body/owner/bearer，并要求 `X-Campus-Session-Read: 1`，明确的外站 Origin/Fetch Metadata 拒绝。
无 CORS、响应 no-store；跨 workspace 清除旧草稿与幂等指针，依赖出错时禁写，不降级匿名。

登录时额外设置 Secure/HttpOnly/SameSite=Strict 的 15 分钟上下文 Cookie，MAC 绑定原随机会话，
记录原 workspace、CSRF 和期限。恢复同时验证签名、原期限、既有 PG owner，不轮换会话/CSRF、
不延长期限或使原 OAuth grant 失效；不含原主会话 token、CloudBase token/UID。
退出清两个 Cookie；r4 旧会话没有上下文时需要一次重新登录，不能虚构 CSRF。
不修改 15 表、RPC 或执行角色；契约/正反例/ABC handoff 见 integration-conventions §9.2。
仍只固定虚构数据，不开放个人上传。部署候选修复不等于学校 Agent→复核页实测通过。

时间工具使用 `OAuthPilotTimeQueryRequest`：单个 query_json 字符串，最多 2048 字符，
内容为既有 FreeTimeQuery / TimeCheckRequest 去掉 workspace_ref；其余必填字段和 null 不变。
HTTP 层拒绝重复键、额外字段与非有限数字，授权 demo:read 后只取本人的已确认课表/待办。
缺课表返回 NOT_FOUND，不借用公共夹具；B 原算法返回 calculation_version、coverage 和
needs_confirmation，不把“基于已保存安排”的空档说成确定有空。Agent 不可确认/提交。

## 上线剩余条件

此试点只验证可信身份和持久写入，不等于已经开放全部个人业务。
真实课表/成绩需要明确的个人数据同意、保留/清理策略、生产用户权限、持久库适配及正式验收。
通知需把实际抽取结果经草稿/复核接到保存链路；当前接口仅固定虚构夹具。
正式培养方案/事务来源仍需 C 交付，未知规则返回 needs_policy，不能猜毕业结论。
最后还需主 Agent 全功能正反例测试、正式域名/平台发布确认、交接文档与发布版本，主 Agent 当前不公开发布。

测试运行：`npm test`（sql-tests）以及后端 pytest。SQL 测试是官方 PGlite 的实际 PostgreSQL，HTTP 集成用独立数据库进程验证应用重启读回；CloudBase 身份在线接口在这些自动测试中被 mock，不能作为腾讯云身份/平台实证。
