# 最终身份绑定流程：累计交付与旧 PR 的区别

本文记录早先累计身份交付，版本号与“实际追加规则”长度为当时状态，不代表最新线上版本。后续 v0.2.25 的原空间绑定分流修复、共用拓展 0.3.4 与新增 PR 范围见 [最新修复交接](shared-reader-native-binding-fix-2026-10-12.md)；不要恢复本文历史提示词覆盖最新规则。

## PR 关系与合并建议

2026-10-12 只读核对团队仓库：main 为 `0051687`，#16/#17 已合并；#18 为未合并草稿，head 为 `6efac69`。本 PR 从 #18 的完整 head 延续，包含它全部提交，并追加真实平台接通修复、成功响应契约、实际 Agent 规则快照、绑定页导航和文案整理。不是只交付 UI，也不要求先合并 #18。

| 交付 | 作用 | 当前关系 |
| --- | --- | --- |
| [#16](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/16) | 旧免注册访客、固定设备码、Agent OAuth 本人绑定的完整源码 | 已合并 main，是基础；不能单独代表最新固定 GeniOS 身份流程 |
| [#17](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/17) | 本人课表来源规则、待办保存说明，B/D 分类 | 已合并 main，是独立业务补交；不是另一个登录方案，不能删除 |
| [#18](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/18) | 统一页面、身份优先保护、固定 GeniOS 身份接入候选 | 旧草稿，本 PR 累计包含并更新它；无需再单独合并 #18 |
| 本 PR | 完整身份后端/私有迁移/插件定义 + 已接通的原空间链路 + 最终分步 UI | 当前 main 上只需审阅合并本 PR，即可取得本轮最终实现 |

“最后只用这个”指：最终用户使用一个 `/tools/login` 入口，代码合并采用本累计 PR，不并行维护旧候选页。不是把 #16/#17 的已合并基础、旧账号兼容、OAuth 数据授权或业务模块删掉。本次未自动关闭/合并任何 PR。

## 用户实际操作

1. 打开工具站绑定页，自动得到本浏览器固定设备码；此时不创建空间。
2. 复制核验请求，发给自己的南开 Agent，等回复后回页面检查。Agent 使用隐藏的固定 `SYS_USERID`，服务端查账号唯一空间，不凭设备码、学校登录 Cookie 或用户填写的账号猜身份。
3. 已有空间：复制绑定确认发给 Agent，只复用原空间。原工具站旧账号：使用本人原有效 OAuth 授权关联原空间。真正首次使用：本人确认后才创建唯一空白空间；已有映射依然只复用。
4. Agent 确认后，在原浏览器点击检查/完成绑定；服务端还需该浏览器的私密 Cookie。只复制、只查询或者只收到工具回复，不等于浏览器已登录。
5. 页面显示绑定成功后进入工具站。换浏览器或无痕窗口仍先核验同一平台账号、复用原空间，不创建第二账号。Agent 读取/保存课表日历仍需本人同意插件授权。

未绑定时显示进度和当前操作；绑定成功收起前两步，只保留进入按钮与折叠的设备/空间信息。身份页不显示课表、地图、日历、设备码四个全局导航入口；进入业务页后原导航正常显示。检查按钮不是自动注册或自动同意，失败/归属变化时不显示进入链接。

## 完整源码与部署索引

- 身份规则与签名：`backend/app/core/genios_identity.py`、`backend/app/genios_identity_site.py`；原 OAuth 一致性守卫在 `backend/app/core/cloud_oauth_provider.py` 等原模块。
- 身份优先浏览器保护：`backend/app/visitor_site.py`、`backend/app/agent_device_site.py`、`backend/app/core/cloud_identity_store.py`。
- 唯一映射及事务：`deploy/cloudbase-identity-pilot/native-identity-registry-migration.sql`、`native-browser-binding-migration.sql`；保留此前 `visitor-identity-first-migration.sql`。
- 页面：`frontend/src/features/auth/NativeIdentityOnboarding.tsx`、`CloudbaseLoginPage.tsx`、`identityOnboarding.css`，导航隔离在 `frontend/src/app/Layout.tsx`。旧 `IdentityOnboarding.tsx` 为 native=false 兼容分支，不是当前线上第二个流程。
- 专用插件：`deploy/genios-workflows/native-onboarding-tools.openapi.json`；原 OAuth 工具身份参数清单：`native-oauth-tools.configuration.json`。
- 正式 Agent v0.2.22 实际追加的 249 字符规则：`native-identity-agent-live-append.txt`。`native-identity-agent-append.txt` 是完整设计参考，不是平台提示词逐字快照；平台原业务正文未在此 PR 重写。
- 构建白名单：`backend/scripts/build_cloud_identity_package.py`，Header 变体复现：`deploy/cloudbase-identity-pilot/Build-Native-Header-Variant.ps1`；包、截图、缓存、个人课表、凭据均不上传。

已有环境三份身份迁移均已执行过，不得因拉取源码重跑。新环境必须先按部署 README 建好原库/访客/OAuth 前置，再审阅追加身份优先守卫、native registry、native browser binding 的迁移顺序；不是将 SQL 文件全部自动执行。两插件私密凭据只由负责人在私密配置页管理，不复制到 GitHub。固定身份必须来自平台隐藏系统参数，不向模型开放或设为个人 ID 常量；实际短期签名使用 `platform-user-id` / `platform-attestation` 连字符 Header，禁止混发旧别名。

## 本轮修复与已完成验收

- Header 传输：旧下划线 Header 在平台链路丢失，改用连字符；保留后端兼容但拒绝重复/混发，没有弱化身份验证。
- 平台输出校验：成功信封中的 `error=null` / `space_label=null` 被普通 Object/String 声明拒绝。插件成功响应只声明非空投影 `ok,data(status,has_space,created),meta`；完整浏览器 HTTP 协议不变，非 2xx 不当成功。
- 正式发布：核验真实持久化提示词与 Web 渠道版本，而非只看编辑器 DOM 或保存弹窗。正式 Web v0.2.22；其他停用渠道没有开启。
- 线上为 **r45 / 057 / 正常 / 100% / 1 实例 / native=true**；最后两次部署只改前端，实际 ZIP 的所有非前端非 manifest 文件与 r43 完全相同。本次 PR 提交不再部署、不重跑 SQL、不改权限/名单或个人数据。
- 本人原空间关联返回 `browser_authorized,has_space=true,created=false`；浏览器领取、重开复用、实际 lookup 已通过。正式草稿 signer → 本人课表/日历调用树成功，原公开聊天入口只读查询通过。未因此创建、合并或删除私有课表/日历。
- 最终前端 **258 项 / 29 文件通过**，identity 类型检查与构建通过。身份后端、HTTP/真实隔离 PostgreSQL、响应契约 **62 项通过**，其中新增成功响应契约 6 项。UI 新/旧空间、未知状态、归属变化与错误分支是本地合成测试。

## 明确保留的边界

- 独立真实学校账号及真正首次用户建空间，尚未完成真人闭环验收；不能用本人原空间成功或合成测试宣称“所有平台用户已验收”。
- 一个稳定平台身份对应一个空间，设备码只是浏览器定位；公开设备码本身不能登录。公用浏览器不自动识别换了哪个人；退出/撤销需要重新明确确认。
- 专用服务凭据曾曝光，已建议私下轮换；负责人明确选择暂不更换，风险未消除。源码不含其值，本次不代为轮换。
- 课表解析/JSON 上传/校历/课程 UI 属于 B，日历业务属于 D；它们既有交付保留。本 PR 新增范围属于身份/平台及对应入口 UI，不更改 B 的解析和 D 的待办业务规则。
