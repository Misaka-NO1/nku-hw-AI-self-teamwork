# 腾讯云独立登录封闭联调（非成品验收）

产品主体仍是学校 NK-GeniOS Agent。这个工具页只处理可信登录和必须由人确认的写入，
不另造聊天产品。当前先核验两名普通测试账号，用固定虚构数据，不接真实成绩、课表。

## 已实现

- 前端固定 `@cloudbase/js-sdk@3.10.1`，延迟加载，官方 SDK 密码登录。
- 当前源码使用 `persistence=none`、`debug=false`、关闭 URL 自动发现会话；
  密码框请求结束清空，后端会话建立后 SDK 退出并清理云临时令牌。
- 后端使用服务端指定环境的 HTTPS `GET /auth/v1/user/me` 在线核验，禁止重定向。
  不接受客户端 UID、仅解码的 JWT、SYS_USERID、管理员身份或共享 MCP Bearer。
- 仅私有配置白名单中的 ACTIVE / external 账号；默认 `legacy` 仍要求 generalUser / user 组。
  PG 环境用显式服务端 `pg_registered` 模式：先向固定腾讯云地址在线 `token/introspect`
  验证同一枚完整凭证有效、未撤销，再提取 JWT 并检查 subject、audience、project_id、
  expiry、authenticated、client_user、external、非管理员和非匿名；最后 `user/me` 核对当前激活身份。
  不用 JWT 解析代替验签，验签/撤销校验委托官方在线接口；任何一步失败都拒绝，令牌不落盘。
  PG 不以传统模式分组示例决定权限，不改数据库权限，不将 API Key 当用户登录。
  签发来源由固定环境在线验证器确认，不要求 JWT 的 `iss` 文本等于请求 API 的 URL。
  `authenticated + external + client_user`、非管理员和在线白名单当前资料都必须匹配。
  缺少/空的可选 `is_anonymous` 不替代这一正向验证，也不误判为匿名；显式 true 或畸形值拒绝。
  UID 环境化后哈希存储，不回传手机号、邮箱、角色对象。
- 最长 15 分钟 HttpOnly 会话、SameSite=strict、CSRF、同源校验、单进程登录限流。
  试点关闭或用户移出白名单后已有试点会话拒绝访问。
- 每个账号有独立虚构工作区；24 小时保留期内重新登录读回同一空间。
  原随机演示空间仍可用；真实数据门禁没有放开。
- 课表草稿与 Tasks 共用同一身份，只有明确确认才能提交，保存后读回。
  空闲查询用实际保存课表与确认活动；缺课表明确报错，不以公共夹具兜底。

## 私有运行配置

在被 Git 忽略的 `backend/data/` 下保存 JSON，只包含 `env_id` 和 `allowed_user_ids`。
不要放密码、服务角色密钥、MCP 令牌；该 JSON 不打包、不推送。

```json
{"env_id":"your-cloudbase-environment", "allowed_user_ids":["approved-test-user-a", "approved-test-user-b"]}
```

先按 `Start-Demo.ps1` 构建 `frontend/dist-demo`（与地图的 dist 分离）。本机启动示例：

```powershell
backend/.venv/Scripts/python.exe backend/scripts/run_demo_site.py --port 8014 --auth-pilot-config "C:/absolute/private/pilot-config.json"
```

已确认使用 PG 的环境，在此命令中加 `--auth-profile pg_registered`；未指定仍保持传统模式严格条件。
该选项由服务端选择，不接收前端/Agent 指定模式或修改环境；试点账号创建与登录不等于云持久库验收。

打开 `http://127.0.0.1:8014/tools/login`，由负责人本人填写测试密码并登录。
运行脚本只监听 loopback；数据库是忽略的本机 SQLite，**不是腾讯云生产数据库**。
云环境如要求来源白名单，应先停下核对并取得针对该来源授权，不关掉鉴权来解决。

## 验收与未完成项

自动测试已验证在线核验模拟响应的失败封闭、双账号隔离、旧会话轮换、退出失效、
重登录/重启读回、真实数据拒绝、过期和 CSRF。真实腾讯云账号登录仍需人工联调；
不能把 Mock 测试通过说成云身份验收通过。

需要依次完成：A 登录并保存虚构课表/活动；退出后 B 看不到 A 记录及草稿；B 保存；
重新登录 A 读回自己的记录；过期/退出/错误账号被拒绝；再验证云持久库版本。

NK-GeniOS 配对还没实施：不向模型交付长期登录令牌，不用 SYS_USERID 文本冒充可信主体；
后续须设计一次性配对、明确用户授权、短期限定能力、可撤销/可过期、跨用户负例。
生产方案还缺共享限流、持久 PostgreSQL 最小权限、备份恢复和真实 Agent 端到端验收。
不得把本机 SQLite 放进无持久挂载云容器冒称完成。

本轮新增 `/api/v1/auth/cloudbase/{config,session,logout}` 和 `/tools/login` 是关闭式联调扩展，
不是既有公共契约升级；接入正式产品前按契约 §7 审核，不更改现有 contracts Schema 或发布主 Agent。

参考：[官方 SDK 登录](https://docs.cloudbase.net/en/api-reference/webv3/authentication)、
[官方当前用户接口](https://docs.cloudbase.net/http-api/auth/user-me)。

PG 适配参考：[官方 PG 身份认证](https://docs.cloudbase.net/authentication-v2/auth/auth-pg)、
[官方在线凭证校验](https://docs.cloudbase.net/http-api/auth/auth-token-introspect)。
