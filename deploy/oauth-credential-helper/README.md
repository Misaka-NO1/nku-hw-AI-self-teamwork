# 本机 OAuth 凭据准备（由负责人操作）

用于负责人已批准的现有 OAuth 客户端凭据同步更换。不自动创建插件、提交凭据、启用云端开关或扩大权限。

启动：`D:/Node.js/node.exe deploy/oauth-credential-helper/serve.cjs`，打开 `http://127.0.0.1:8023/`。
由负责人亲自点击生成，填写学校 `client_secret` 并提交；新凭据不能由自动化代填/代提交。
密钥原文只进入学校保密 OAuth 配置，SHA-256 摘要只进入身份服务后端 `OAUTH_CLIENT_SECRET_HASH`。
不复用数据库 Key、登录密码或 MCP token，不在聊天发送、不写 Git/文档。

固定 client_id/audience：`nku-genios-identity-read-pilot-20261003`。
固定回调：`https://coze.nankai.edu.cn/product/llm/info/oauth`；无 refresh token。
现有 scope 保持 `demo:read tasks:read tasks:write devices:bind degree:read degree:write`。保留旧插件时同步替换其 client_secret，避免旧配置失配；不会自动撤销或重建私人空间。
令牌有效期取决于实际模式：严格试点（strict）或未启用持久授权时，最长600秒且不超过来源登录会话；当前启用 `CLOUD_PERSISTENT_AUTH_ENABLED` 的学校兼容模式使用长期本人授权，直至退出或撤销。不能用旧试点的600秒说明判断当前连接是否到期；客户端密钥是否匹配也不受该有效期影响。

本页无外部脚本、网络请求、存储或表单提交；服务仅绑定loopback、固定路径白名单、拒绝query/body/非GET。
密钥仍在本机内存及用户主动复制的剪贴板，不能防范已感染设备、扩展或屏幕旁观。
关闭/清空后不保存；若浏览器不允许剪贴板，应人工复制而非用工具读取密钥。

恢复时保持现有开关、权限及回调不变；不修改 `GENIOS_NATIVE_INTEGRATION_KEY`。完成两端保存后验收平台重新授权及真实读取，不降级身份校验。
