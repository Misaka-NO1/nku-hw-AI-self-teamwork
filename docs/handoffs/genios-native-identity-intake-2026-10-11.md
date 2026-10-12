# GeniOS 原生身份接入：上线验收与历史过程

状态：2026-10-11 接入验收，后续 UI 更新至 **r45/057 正常、100% 流量，沿用 native=true**。两插件已发布，正式 Web 渠道 v0.2.22；本人原空间关联、浏览器领取、重开复用及原聊天入口只读空间/课表/日历查询通过。独立账号/全新用户真人验收尚未完成；用户明确选择不轮换已曝光凭据，风险已说明。

2026-10-12 用户已追加授权提交新 PR。最新交付范围及 #16/#17/#18 的关系见 [最终交付说明](native-identity-final-delivery-2026-10-12.md)。下文“不 commit/push、不新增 PR”、候选未发布、部署创建中等描述是当时记录，不代表当前限制或上线状态；当前状态以上述摘要为准。本次源码提交不重新部署、不重跑 SQL、不改凭据、不合并或关闭旧 PR。

## 正式渠道补充核验

### 身份页导航修正（后续用户反馈）

- 用户要求身份/空间绑定页不显示顶部课表、赏景地图、待办日历、我的设备码四入口。`Layout` 按 pathname 在 `/tools/login` 隐藏整个功能导航，仅保留标题与返回平台入口；即使已有登录状态，身份页仍不显示这四入口。其他工具页原导航保持不变。
- 增加 identityPilot=true/false、含 return_to 参数的静态布局测试；本轮全部前端 **257 项通过**，identity 模式构建通过。仅改变显示，不改变身份、Cookie、空间归属或授权守卫；不发布新 Agent、不提交 PR。
- r44 包 `cloudbase-identity-pilot-20261011-r44-login-nav.zip` SHA256 `55feab2aae00ccc9f911b4a4bc143c0adf18fa67ad6ed14c6fd877b343aa5c7e`，205 entries；逐文件比较非 frontend/dist 与 manifest 部分和 r43 完全一致，没有新增非前端文件。沿用原配置，上传后核对 native=true；目前部署已提交，线上页面待确认。
- 凭据事项：用户后续明确拒绝轮换，要求保留当前值。没有更改或读取新值；此前曝光风险已说明。本次 UI 更新不继续操作凭据轮换。
- r44 已上线为 **056 / task2335026 / 正常 / 100%**，实际身份页已无工具导航。随后用户追加精简文案和清楚展示绑定流程，继续在同一轮前端修正，不改 Agent。
- 最终页面按阶段显示当前操作：第一步“复制核验请求 / 打开 Agent / 我已发送，检查核验结果”；核验后显示“复制浏览器绑定确认 / Agent 已确认，检查绑定结果”。首次创建和原账号关联各有明确按钮，不把未知身份当新用户。收到 browser_authorized 状态时仅显示“完成浏览器绑定”，不重复要求发送确认。绑定成功收起前两步，保留进入按钮、折叠设备/空间信息，以及单独插件同意入口。
- 删去原生页面重复的技术边界及旧登录说明；“检查”明确不代替发送请求。原 owner 变化/网络错误仍使进入按钮失效，不自动 claim；原业务页导航及旧登录兼容模式保留。
- 最终前端回归 **258 项通过**，identity 构建通过。r45 `cloudbase-identity-pilot-20261012-r45-onboarding-copy.zip` SHA256 `9d7ec0e47bb3655902eeb0d0781ee3cea4e1a422fde3afa60e72bf7b246d3fce`；205 entries，逐文件核对全部非前端内容仍与 r43 相同。当前已提交第二次 UI 更新，最终线上页面仍待核验。
- 最终线上已确认 **057 / task2335068 / 正常 / 100% / 1 实例**。实际绑定页为“绑定我的浏览器”，无顶部工具导航；原空间仍已绑定，成功后前两步隐藏，“进入我的工具站”可见，设备/空间信息折叠。点击该进入链接实际到 `/tools/timetable`，功能页导航四项仍完整，随后返回绑定页。仅检查导航，没有读回或截图课程明细、没有新 claim 或任何私有数据写入。
- 安全截图仅本机 `dist/native-onboarding-clean-success-20261012.png`；本轮不 commit/push，不新增 PR，不发布新 Agent。新/旧空间、未知身份、待确认、错 owner、网络失败等 UI 分支由上述合成测试覆盖，不能说成已用其他真实学校账号验收。

- 原 v0.2.21 已存在，因此完整身份守卫使用 v0.2.22。服务器重开确认主提示词 28456 字符，保留原业务正文及完整 249 字符身份规则；实际简版另存 `native-identity-agent-live-append.txt`。
- 配置成功不等于原 Web 入口已更新。渠道提交异步结束后，页面最终显示原聊天链接对应 Web 服务 **v0.2.22 / 运行中**；API/MCP/WebSDK 继续已停用，没有启用额外渠道或改访问名单。截图仅本机 `dist/native-agent-v022-web-live-20261011.png`。
- 学校会话约 40 分钟可能需要刷新；慢加载、异步提交弹窗及暂时旧版本不能直接判定为登录失效，应以真实登录跳转/认证报错为依据。
- r43 同一核验包上传后仅将 native 开关设置 true，提交 **055 / task2334813** 自动切流；截至此条记录仍创建中，旧 **054 / false / 正常 / 100%** 保持运行。不能提前声称新运行版本已生效。
- 安全待办：控制台编辑页会以明文展示服务凭据，本轮一次整页观察意外纳入该值；没有复制到源码或本记录。验收后须由用户亲自轮换两端专用凭据，不得回显或沿用该曝光值作为长期凭据。后续只做非敏感行的局部状态检查。
- 055 已完成：服务版本表显示正常、100% 流量、1 实例；单独展开 `CLOUD_GENIOS_NATIVE_IDENTITY_ENABLED` 行确认 true。随后原 Web 聊天入口新会话只读 lookup 返回 existing_space，声明未创建/绑定/关联；另一轮只读查询报告本人已保存课表（personal）及本人日历均读取成功，浏览器重开仍显示已绑定并登录、原空间。没有新增写入或复制私有数据。
- 正式入口证明截图仅本机 `dist/native-agent-v022-public-read-verified-20261011.png`，浏览器证明 `dist/native-original-space-bound-20261011.png`。正式回复是公开渠道结果；更底层 signer/私有读取调用树成功依据为此前正式草稿实际验证，不能把公开回复当成跨账号实测。
- 凭据轮换必须由用户在专用插件 Token 与腾讯云 `GENIOS_NATIVE_INTEGRATION_KEY` 私密页输入同一条新随机值并各自提交；助手不读取、复制或代填新值。整页插件观察已被安全审查拦截，未绕过；安全收尾保持局部读取及人工凭据提交。
- 保持暂不提交 PR 的要求：本轮修改与核验记录只保存在本地，没有 commit/push。

## 最新进展：r43 Header 兼容与平台 Body 阻塞

### 后续纠正：响应 nullable 校验已定位并通过真实 lookup

前轮“参数组装层”的判断不完整。2026-10-11 后续核对发现：成功 HTTP 信封的 `error` 为 null，首次/旧空间待关联时 `space_label` 也可能为 null；新插件将它们声明为普通 Object/String。OpenAPI 的 `nullable: true` 不等于 JSON Schema 接受 null。本地 Draft7 重现完全相同的 `None is not of type 'object'`，成功响应非空投影 **6 项通过**。

- 仅修改插件成功响应声明为 `ok,data(status,has_space,created),meta(request_id,data_version)`；不改完整浏览器 HTTP 信封，不放宽身份、OAuth 或私密 Cookie 校验，不把非2xx当成功。nullable 错误和空间标识不在插件成功字段中声明。
- 专用插件重新发布；测试 Agent 重新添加最新 onboard 工具，固定隐藏 SYS_USERID，intent=lookup / confirmed=false 锁定。真实运行日志显示 `调用工具 onboard_my_browser` 成功，实际输出 `ok=true, status=legacy_authorization_required, has_space=false, created=false`，没有 null Object 异常。这意味着需用原有效 OAuth 关联历史空间，不代表这个人没有旧空间。
- 同一 r43 后端包验收部署 **053 / task 2334153** 已正常；开启 native 身份仅供当前受控验收。若停止或失败，按原批准范围恢复运行开关 false，不能让旧正式 Agent 长期被新守卫拦住。
- `associate_my_original_space` 响应同步改为非空投影；九个原 OAuth 工具 Header 都已改为 `platform-user-id` / `platform-attestation`，不改业务请求体、原响应和授权配置。用户专项批准后原插件已发布。正式 Agent 十二项工具已逐项固定引用隐藏 SYS_USERID；签名由本轮实际 signer 输出传递，不设长期默认值。
- 用户明确确认本人原空间关联后，未发布测试 Agent 实际 signer 和 associate 调用均成功；输出 `browser_authorized, has_space=true, created=false`。本人原浏览器主动检查后显示“已绑定并登录”；重开浏览器和真实 Agent lookup 返回 `existing_space, has_space=true, created=false`。仅关联原映射及授权浏览器，没有创建、合并、删除课程/日历数据。
- 测试 associate 的一次性 confirmed=true 已改回锁定 false，提示词恢复只读，避免残留自动写入。正式 Agent 草稿已经实际调用 onboard 并返回同一已有空间；正式版尚未发布。不同学校账号、真正新浏览器、首次用户建空间不能由此推断已验收。
- 用户要求后续暂不提交 PR：本节、响应契约和新增测试仅本地保存，不 commit/push，不新建 PR。

后续正式编排保存核验：批量 fill/type/paste 只改变该富文本编辑器的 DOM，没有持久化主规则；逐键输入才触发有效保存事件。第一次长输入超时留下的标题和后续未完成片段均已撤回，原正文恢复到 28207 字符、原结尾完整。最终以一次完整编辑任务逐键输入 249 字符精简守卫（实际文本见 `native-identity-agent-live-append.txt`，原完整设计文件保留作参考），不是分段发布。为避免原渠道尚未升级时被新守卫拦住，已将同一 r43 包部署为 **054 / task2334633**，正常、100%流量，服务页面单独展开非敏感开关核验 native=false；不删除已验证的原空间映射与浏览器授权。

恢复学校过期会话后，正式草稿实际 signer → read_my_demo_records、signer → read_my_calendar_entries 均在调用树显示成功，未写入数据。无工具请求也报“请求异常”时，不能认定为后端或私人数据为空。完整本地回归 **62 项通过**（含真实隔离 PostgreSQL 和非空响应契约）；初次沙盒临时目录/Node子进程启动失败不算测试通过，改用独立临时目录及正常本机运行后全部通过。三份本轮生成的合成测试临时目录已移除，没有删除用户数据。

用户再次明确要求继续至完成，并批准发布 v0.2.21。当前正在核验配置和原 Web 渠道；成功弹窗不能替代渠道版本确认，不得仅据此声称正式上线。完成渠道验证前保持回退模式，不提交 PR。

以下 Body 阻塞段落留作历史记录；不得再当作当前根因或据此改写身份请求协议。

以下为最新状态；本文后续 043–047、未发布专用插件等描述是历史过程，不代表当前状态。

- 用户亲自重新提交两端独立凭据；启用 r42 的 049 正常，启动验证通过。没有读取或记录凭据内容。专用插件“开启”保持关闭：平台说明为调用者使用服务端默认凭据，而不是要求学生填写。
- 下划线身份 Header 在 Debug 中缺失。r43 改用 `platform-user-id` / `platform-attestation`；后端保留旧别名但拒绝重复或混发。身份、签名和 OAuth 一致性要求不变。相同私密配置使用新 Header 后，051 的只读签名 Debug 返回 600 秒证明；据此定位到 Header 传输兼容问题，未断言腾讯云具体网关配置。
- 后端本次回归：身份边界 **42 项通过**，真实隔离 PostgreSQL HTTP **14 项通过**；身份前端本次 **9 项通过**。这些是本地合成测试，不是生产绑定成功。
- r43 包 SHA256：`6fcbe667a7402ccb7ef35fb7bbc2386bf1c879a727463ca9168cffa5fff4c8d3`；205 archive entries（204 非 manifest 文件）。与 r42 仅 `backend/app/core/genios_identity.py` 和 manifest digest 不同。可用 `Build-Native-Header-Variant.ps1` 从已核验 r42 原包复现，不覆写原包、不含凭据。
- 按用户专项批准，专用插件 `campus-genios-native-onboarding` 已发布供**未发布**测试 Agent 验收；发布警告只剩 onboard Debug 未通过。正式 Agent 未改动、未发布。
- 学校会话过期导致已发布插件选择器空白；一键登录恢复后可正常添加。测试 Agent 两个新工具均固定引用 `平台用户ID(平台用户ID)`，参数对模型关闭。实际 Agent 的无 Body 签名调用成功，不展示证明。
- `onboard_my_browser` 的插件 Debug 可将完整 JSON 送到后端：合成不存在的设备按预期返回 `404 NOT_FOUND`。实际 Agent 的 lookup 则反复报 `None is not of type 'object'`，没有 HTTP 响应码。检查 Body=json、三字段必填、模型入参开关；把 intent=lookup / confirmed=false 锁定后，以及明确模型 JSON 对象重试，仍失败。**当前仅能定位到平台 Agent 参数组装层，尚未完成根因修复。** 不能通过自动创建、改 UID 或弱化身份校验绕过。
- 未创建真实空间映射、未进行旧空间 adopt、未绑定或 claim 真实浏览器，没有合并或删除个人数据。原 OAuth 插件九工具仍有旧 Header 名草稿需逐项升级；associate 草稿已使用新 Header，尚未发布。
- 根据已批准的失败回退范围，提交同一 r43 包的 **052 / task 2333963**，最终部署表单明确 native flag=false；已验证状态正常、100% 流量，单独展开该非敏感开关确认 false（其他环境变量未展开）。旧正式调用恢复到原模式。安全截图保存在本机 `dist/native-r43-restored-052-20261011.png`。SQL 不删除、不重跑。

下一步：修复学校 Agent 的 Body 对象组装，重测 lookup，再依序进行原 OAuth 一致性与实际 bind/claim；全程通过前不得发布正式 Agent 或声称免注册闭环完成。

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
