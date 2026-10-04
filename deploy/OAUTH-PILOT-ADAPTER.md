# D：NK-GeniOS 逐用户 OAuth 接入候选

2026-10-03实际进展：独立云身份服务已部署、浏览器虚构数据A/B保存隔离已验证；负责人创建OAuth插件后首次平台授权请求缺S256 challenge、state低于项目要求。未发用户grant，已将云OAuth开关保存false；默认测试域名健康仍503，不能宣称运行时全验收。详见[D10实际兼容记录](../docs/evidence/platform/D10-genios-oauth-compatibility-2026-10-03.md)。下方“本地/未部署”状态为10月2日历史阶段。

状态：**本地接口/协议测试通过，默认关闭；未部署到腾讯云，未给学校插件发放授权。**
这不是另做一个聊天网站。目标仍是 NK-GeniOS 主 Agent → 用户授权的工具 → 自建后端 → 用户自己的数据库记录。
工具页只负责登录、授权、导入和人工确认。

## 本轮实现

- `app/core/oauth_local.py`：严格注册的 client/redirect，S256 PKCE、一次性授权码、短期访问令牌、账号与来源会话绑定。
- `app/oauth_pilot_site.py`：授权同意页和 OAuth/业务适配端点；JSON/form token 请求，Basic/body 客户端认证（二选一）。
- OAuth 控制端点按协议返回标准错误/跳转，不使用业务信封；读记录/建草稿仍使用 ApiEnvelope 1.0.0。
- 控制端点禁止缓存，拒绝重复参数、超限请求、未知字段、URL 中的 access token；错误不回显凭证。
- 服务端只保存同意随机数/授权码/令牌/client secret 的摘要。没有 refresh token，授权最多 600 秒且不超过原浏览器会话期限。
- 读自己的虚构课表和待办；最多创建经过 hash 核验的固定通知草稿。没有 Agent 确认/提交接口；保存仍需浏览器 owner 确认。
- 退出、会话轮换、移出试点白名单、过期或撤销令牌后拒绝访问。绝不退回他人的记录或公共课表。
- SQLite 事务保证并发兑换只能成功一次。生产不得把这个 SQLite 文件当云托管持久数据库。

## 路径（候选；不在现有云端公共 API 或 MCP 中注册）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/oauth/authorize` | 校验参数、要求普通测试用户登录、显示显式授权页 |
| POST | `/oauth/approve` | 原浏览器 + 同源 Origin + 单次随机数同意/拒绝；303 到唯一注册地址 |
| POST | `/oauth/token` | 平台后端凭 client secret 和 PKCE verifier 单次兑换，不在模型中传令牌 |
| POST | `/oauth/revoke` | 经客户端认证撤销本 client 的 token；未知 token 不泄露存在性 |
| GET | `/oauth/records` | Bearer token 只读 owner 的已保存课表/待办；不接受 workspace/user 参数 |
| POST | `/oauth/task-drafts` | Bearer + `fixture_id`/`idempotency_key`；仅固定虚构草稿 |

本地 demo site 只有 `OAUTH_LOCAL_ENABLED=true` 时才挂载候选；普通 `run_demo_site.py` 强制关闭。
main API/MCP 不导入这个适配器。必须同时开启既有 CloudBase 普通账号试点/内部配对门禁，
配置同一个 audience/client id、已注册回调及 client secret SHA-256 摘要。只能 HTTP loopback/testserver，
test/development；staging/production、真实个人上传、任意远程入口均被拒绝。
不要在浏览器前端构建变量、Git、命令行参数或文档中放密码、client secret 或 access token。

## 学校平台实际查看结果

2026-10-02 查看**空白、未提交**的创建插件表单：

- OAuth2 的 grant_type 下拉显示 `Authentication Code` 和 `Client Credential`。
- 字段为 client_id、client_secret、redirect_url、auth_url、access_token_url、Scope、refresh_token_url、auth_content_type。
- 回调固定 `https://coze.nankai.edu.cn/product/llm/info/oauth`，内容类型默认 application/json。
- 未见 PKCE 专用设置入口。这只能证明配置界面，不证明运行时有没有自动生成 PKCE，也不证明它不支持。
- 已取消表单；没有创建插件、填写密钥、提交授权或改变主草稿绑定。

本地授权页目前在未验证会话时提供登录链接，登录完成后返回/刷新授权页；尚无自动返回交互。
现有浏览器 Cookie 保持 SameSite=Strict，学校跨站首次跳转的实际会话行为必须在平台联调中验收，
不能把 TestClient 协议测试当作浏览器跨站 Cookie、学校 state 校验或令牌存储行为已通过。

**不能把 Client Credential 用作用户身份**：它证明调用方是这个插件，不证明调用方代表哪个用户。
同样，SYS_USERID、workspace_ref、模型自己输出的 user_id 和共享 MCP bearer 都不能提供用户隔离。

## 后续实际接通门槛

1. 云端另建隔离的 OAuth/身份存储，使用已有 CloudBase PG，不能改 MCP005/Tasks003/Public002 或其他业务表。
   授权事务、会话、owner 工作区、草稿/确认、令牌撤销与幂等必须共享持久存储，跨实例原子处理。
2. 部署 HTTPS 测试服务、仅两个普通账号、仅虚构数据、无公开注册；不要放开真实成绩/个人课表。
   创建新客户端凭证或授予学校插件逐用户权限前，须在实际操作点确认；新增凭证由负责人填写/提交。
3. 只给未发布的测试插件配置固定 callback、短期 client secret；不发布主 Agent。
4. 验证平台发出的授权请求确有随机 state、S256 challenge，token 兑换确有同一事务的 verifier；
   验证 token 位于平台保密后端、不是模型输入/输出或普通工具参数。缺少则停止并反馈，不降级到无 PKCE。
5. 平台用户 A/B 分别授权；读取自己的课表/任务，交叉引用拒绝；建草稿后用户确认才能保存。
   重放拒绝、拒绝授权不发码、登出/撤销失效、云服务重启仍按 owner 读回全部要实测。
6. 正式个人数据权限、C 的正式培养方案/校园事务来源、真实通知、最终发布单独验收。

## 可复测命令

在 backend 目录使用项目现有虚拟环境：

```powershell
.venv/Scripts/python.exe -m pytest tests/test_oauth_pilot.py -o addopts='' -q --disable-warnings
.venv/Scripts/python.exe -m pytest -o addopts='' -q --disable-warnings
```

测试只生成虚构 client credentials 和身份，不调用学校/腾讯云，不读取负责人给出的密码。
正反例和请求/响应 schema 已同步到 `fixtures/oauth-pilot.demo.json` 与 `contracts/api.schema.json`。
最终完整后端 444 项通过（OAuth 专项 37 项；1 项第三方弃用警告），git diff --check 通过。
前端本轮没有改动，未把此前前端结果当作新 OAuth 浏览器端到端验证。

设计依据：[RFC 6749 授权码与客户端认证](https://www.rfc-editor.org/rfc/rfc6749)、
[RFC 7636 PKCE](https://www.rfc-editor.org/rfc/rfc7636)、
[RFC 9700 OAuth 安全建议](https://www.rfc-editor.org/rfc/rfc9700)。
自建适配器不是经过第三方安全审计的生产授权服务器，不能凭测试通过就开放个人数据。
