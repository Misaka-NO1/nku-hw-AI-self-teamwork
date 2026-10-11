# GeniOS 原生身份接入：验证进展与未上线边界

状态：2026-10-11，**固定参数实测通过；两份新私有迁移已安装，r42 候选已部署；正式 Agent 和真实登录闭环尚未验收发布**。

## 真实平台验证

- 原 MCP 测试将系统用户 ID 引用到字符串 `query_json`，平台在发出请求前报 `objectMerge: Base is not an object`。不是服务端拒绝，也不证明系统变量不能用。
- 新建独立 REST 插件 `campus-native-id-rest-probe`，只有 `GET /healthz` 工具 `probe_native_identity`，无认证、无数据访问权限、无写入。
- 参数 `platform_user_id` 为 String/Header；在**未发布**测试 Agent 里引用 `平台用户ID(平台用户ID)`，关闭该参数“启用”，即不向模型开放填写。
- 测试聊天主动要求替换成 `TEST-ATTACKER-ID`。实际展开的工具 Input 含非空平台值，不是该假 ID；Output 实际返回当前 r41 `build_id`。不保存或输出实际平台 ID。
- 已恢复测试 Agent 原提示词；保留新增只读探针配置用于后续回归。正式 Agent 未改动、未发布新版本。诊断插件自身已发布，但不绑定正式 Agent。
- 本机截图 `dist/native-identity-fixed-parameter-20261011.png` 显示固定系统变量及隐藏参数。dist 不上传；无凭据、无实际平台 ID。

此测试只证明**当前本人草稿运行的一次隐藏参数传入**。没有证明跨学校账号唯一性、公开渠道配置继承、其他平台版本、服务端调用者可信性，不能当作原生登录验收。

## 本地准备代码

- `backend/app/core/genios_identity.py`：固定发行方 + 系统 ID 的稳定 hash；独立凭据认证、重复头/字段拒绝、浏览器 Origin/Cookie 拒绝、不接受 owner/workspace/user_id 覆盖、创建/绑定明确确认。
- 本地已安装受开关保护的 `genios_identity_site.py`：`onboard`（专用服务端 Bearer）、`associate`（原有效 OAuth + 专用私密头）、浏览器 `state/claim`（同源 + HttpOnly 私密 challenge）。`CLOUD_GENIOS_NATIVE_IDENTITY_ENABLED` 默认 false；不改变当前生产 r41。
- `native-identity-registry-migration.sql`：私有账号映射、identity 主键及 owner 唯一约束；只读 lookup、受确认保护的 create、根据实际原 OAuth grant adopt 旧账号。全局事务锁串行化检查与创建；同一账号再次点击 create 复用原空间；不复制课程/待办。
- `native-browser-binding-migration.sql`：固定身份核验、明确授权、私密浏览器领取及实际 OAuth owner 一致性校验；注销/撤销清理授权，旧 visitor_begin 不得复活原生绑定。两份新迁移已在原腾讯云依次执行一次；不重跑任何旧迁移。平台的通用 Supabase 角色提示经只读确认三个角色存在、用户明确确认后继续。
- 原生模式下每个私有课表/日历/通知/排期/待办请求均通过 `verify_grant` 核对固定平台身份与真实 OAuth owner。缺少隐藏身份头/独立私密头的旧 MCP 请求将拒绝；必须先替换为相应 OAuth REST 工具，不能直接打开生产开关。
- 本轮相关后端扩展回归 **111 项通过**（包含签名证明、身份边界、HTTP/真实隔离 PostgreSQL 接入及旧身份/设备/包回归）；前端此前 **255 项通过**，本轮重新构建身份前端通过；SQL此前 **64 项通过**。包含新浏览器复用、两身份隔离、旧空间接入、错 OAuth owner、注销/撤销、无身份私有读写拒绝。模拟数据不是生产注册成功。
- 候选工具定义：`deploy/genios-workflows/native-onboarding-tools.openapi.json`；候选 Agent 规则：`native-identity-agent-append.txt`，两者未绑定或发布到正式 Agent。

## 下一步上线前必须完成

1. 用户已批准接入和验收，已亲自提交专用插件 Token 和腾讯云 `GENIOS_NATIVE_INTEGRATION_KEY`。界面已确认云端退出编辑模式、变量标签保留；没有读取或记录任何值。`CLOUD_GENIOS_NATIVE_IDENTITY_ENABLED` 保持 false，直到工具替换、迁移及实测准备就绪。不复用公共 MCP token/数据库 key/个人 OAuth token。
2. 专用插件 `campus-genios-native-onboarding`（`db5m4gd4shhbpg90kmr0`）已保存两个草稿：`onboard_my_browser`（`db5m5qt4shhbpg90knkg`）、`attest_my_platform_identity`（`db5mn8l4shhas0alvu3g`）。原 OAuth 插件已保存 `associate_my_original_space`（`db5mhod4shhbpg90l1ig`）以及九个原工具的 `platform_user_id`/`platform_attestation` 请求头草稿，未发布。Agent 层的固定 SYS_USERID/模型隐藏还未逐工具配置，不能仅靠描述算完成。
3. 本地原子绑定/claim 与一致性守卫已实现并测试；两份新迁移和开关关闭的候选部署已完成，仍需启用后的真实平台验证。浏览器不能仅凭 DEV 码登录，不能只修改提示词。
4. 同一身份页显示“已找到原空间，只绑定新浏览器”或“首次使用，确认创建空白空间”。首次创建后完成原插件 OAuth，本人授权才可给 Agent 读写课表/日历；原 grant 不自动升权。
5. 跨账号、普通/无痕浏览器、退出/撤销、并行开户、错账号旧 grant、手机布局验收后，才能部署并发布正式 Agent。缺任何一项不可称为已完成。

特别注意：历史系统没有记录可信 GeniOS UID，因此映射缺失不等于该人从未有工具站空间。旧用户首次升级需用其原有效 OAuth 证明关联，不按昵称/姓名猜测或合并。无浏览器私密证明、无旧有效授权时不能凭学校姓名找回历史空间。

## OAuth 与专用凭据桥接（本轮新发现）

原 OAuth 插件的配置界面没有附加私密请求头输入，不能要求把长期 key 放进模型参数，也不能覆盖原 OAuth Authorization。现在增加只读 `POST /api/v1/auth/genios/attest`：专用插件的服务端 Bearer + 固定隐藏 SYS_USERID 签发 600 秒的 HMAC 证明，只含发行方域内身份 hash、签发/过期时刻与随机 nonce，不含实际 UID、长期 key 或 OAuth token。无请求体（兼容仅空 JSON 对象），禁止 owner/身份覆盖和 URL 参数。

原 OAuth 工具携带固定 `platform_user_id` 和本轮 `platform_attestation`。后端先验签、期限与固定身份，再验证实际 OAuth grant 和 canonical owner。证明不能替代 OAuth、不能给浏览器登录，也不能调用专用 onboard/attest 换取新证明。篡改、跨 UID、重复头、混用长期 key、过期、换 key及错 OAuth owner 都拒绝。Agent 不展示、长期保存或接受用户提供的证明；过期重新从专用工具获取。

这解决了配置互斥，但仍未完成正式 Agent 的真实验收。工具详情页此前“加载失败”在刷新学校现有登录后恢复。新插件未发布时，工具选择器的“添加”不可用，需明确区分插件草稿发布和正式 Agent 发布，不能将两者混称完成。

无参数 POST 兼容调整后，身份边界与实际隔离 PostgreSQL HTTP **49 项再次通过**。候选完整包：`cloudbase-identity-pilot-20261011-r42-native-identity-candidate.zip`，204 文件，SHA256 `adfd3533c3c5010c67183ed5ffd026f0dbe578eb3b75f77501990687812f7118`，不含凭据；已经上传腾讯云。部署 `043`（任务 `2333282`）及 `045`（任务 `2333425`）正常，045 流量100%，实际运行开关为 false。编辑服务配置保存 true 不代表更新服务表单已经继承它；需在上传完成后的最终部署表单核对。

用户批准先发布专用插件供草稿验收，但前提仍是只读签名通过。最终表单明确设置 true 后部署 `047`（任务 `2333516`），启动失败，平台诊断命中 `native_configuration` 的 `Native identity requires an independent private integration credential and private visitor gates`。只读核对 visitor/device-binding 两依赖开关均 true，专用凭据配置行存在；未读取任何凭据值，尚不能区分凭据未有效传入、格式错误或不独立。047 未接流量，线上仍为正常的045，开关 false。签名 Debug 仍404，未发布专用插件或正式 Agent，未进行真实绑定/创建。需由用户亲自核对两端同一条独立、43–128 位字母/数字/下划线/短横线凭据，再继续启用。

原 OAuth `associate_my_original_space` 草稿说明已改为本轮签名证明，不再要求模型传长期私密头；测试 Agent 提示词限制 lookup/confirmed=false，固定参数仍需在新增工具逐个配置。身份边界测试本次复跑 **36 项通过**。两份 native SQL 已安装，不得重跑。OAuth 草稿配置清单另存 `deploy/genios-workflows/native-oauth-tools.configuration.json`，不能把它导入专用 Bearer 插件替代原 OAuth。

新增表权限实测：registry/binding 均存在且 RLS=true；匿名、普通 authenticated 角色不能直接执行 native RPC，service_role 能执行。执行前后个人课表均为2份、日历条目均为5条，未创建、合并或删除个人数据。截图仅本机 `dist/native-migration-verified-20261011.png`，无账号标识或密钥。
