# Agent 配对内部原型（默认关闭，未发布）

本机真实 A/B 登录和虚构记录隔离已经通过；仍不能将 SYS_USERID 文本、共享 MCP Bearer、
Cookie/session_id 或工作区编号当作学校用户身份。NK-GeniOS 仍是产品对话入口。

## 已实现的内部逻辑

`backend/app/core/agent_pairing_local.py` 是仅测试使用的函数库，没有 REST 路由、MCP 工具、前端按钮或云部署。
`agent_pairing_local_enabled=false` 为默认；显式开启后仍只准 test/development、固定虚构数据、
CloudBase 激活白名单和服务端固定 audience。生产与 staging 直接拒绝。

- 浏览器侧必须是已验证普通用户、当前会话、同源和 CSRF，且拥有固定虚构工作区。
- 生成 32 字节随机的一次性码，最多 120 秒；数据库仅存摘要，重新生成废除该会话旧码/授权。
- 经独立认证的集成 Principal 与预配置 audience 必须一致；共享公开读取 Principal 不能兑换。
  该 Principal 在测试中构造，**尚无生产平台身份适配器，不代表学校已有签名身份机制**。
- 原子兑换生成独立短期授权，最多 600 秒且不晚于来源浏览器会话/工作区到期。
- 每次调用重查当前白名单、源会话、工作区、固定夹具、到期时间、audience 和范围。
  退出/会话轮换/撤销/移除白名单/工作区到期后失效，无长期刷新令牌。
- 只读或只读+建草稿；无 demo:commit。确认与提交服务自身也只允许 browser_user + demo:commit，
  防止内部误调用绕过网页确认。原 B 时间算法和原草稿/hash/revision/幂等链路不重写。
- 读取仅服务器授权绑定的工作区；没有课表返回 null，不用别人的课表或公共夹具兜底。
- SecretStr 隐藏凭证的 repr；SQLite 不存明文配对码、授权、CloudBase UID 或用户密码。

## 上线前明确未完成

1. 按契约 §7 同步新增路由/工具的 Schema、正反例、REST/MCP 适配测试和 A/B/C handoff。
   目前没有对外注册/修改任何公共契约，函数库不是已接通的学校插件。
2. 在学校平台实际验证受保护的每用户授权通道；不能把授权放模型提示词、聊天、URL、普通变量、
   环境共享令牌或日志。现草稿仅看到了 SYS_USERID/SYS_USERNAME 文本变量，没有取得签名身份实证。
   本轮随后只读空白“创建插件”表单，已确认授权方式枚举含 OAuth2，授权码模式显示以下配置：
   client_id、client_secret、redirect_url、auth_url、access_token_url、Scope、refresh_token_url、
   auth_content_type（默认 application/json）。固定回调为
   `https://coze.nankai.edu.cn/product/llm/info/oauth`。没有填秘密、创建插件或提交授权。
   这只证明表单入口存在，不证明每用户隔离、客户端认证传输、PKCE/state、令牌保密/撤销/刷新行为。
   下一步优先验证 OAuth2 接入：浏览器独立登录/明确同意 → 授权码 → 平台保密令牌 → 限定资源调用。
   本内部配对码不能直接当标准 OAuth 授权码接口；必须补严格回调绑定、客户端认证、一次性兑换、
   支持的 PKCE/state 机制和实际 HTTP 契约，不能凭表单直接宣布兼容。共享 Bearer 不作个人授权。
   上文禁止 URL 凭证指完整 access_token/refresh_token/服务密钥；OAuth 协议中的短期一次性 code
   仅能按已验证的严格回调协议传输，不能放任意 URL 或日志。若无安全通道，保留浏览器操作模式。
3. 将身份、工作区、草稿、授权和撤销状态迁移到已批准的隔离持久库，并实现最小权限、共享限流、
   备份/恢复与云重启测试；本机 SQLite 不可直接塞入无持久卷的云容器。
4. 新权限、云部署、凭证配置及正式 Agent 发布到操作时仍需负责人明确确认。
   内部测试通过不自动授予云端调用或开放个人课表/成绩权限。

## 复测

在 backend 目录运行 `.venv/Scripts/python.exe -m pytest tests/test_agent_pairing_local.py`。
测试为合成身份/临时数据库：双用户、一次性并发兑换、到期、注销、轮换、撤销、同源/CSRF、
只读越权、范围升级、非夹具、无确认保存、摘要存储和重启读回。无真实密码或云资源变更。
测试运行器不启用此原型；回退可移除未注册的函数库/测试并保持默认开关 false。
