# 本机 OAuth 凭据准备（由负责人操作）

仅用于已批准的两个普通虚构账号、`demo:read` 封闭联调。不自动创建学校插件或启用云端 OAuth。

启动：`D:/Node.js/node.exe deploy/oauth-credential-helper/serve.cjs`，打开 `http://127.0.0.1:8023/`。
由负责人亲自点击生成，填写学校 `client_secret` 并提交；新凭据不能由自动化代填/代提交。
密钥原文只进入学校保密 OAuth 配置，SHA-256 摘要只进入身份服务后端 `OAUTH_CLIENT_SECRET_HASH`。
不复用数据库 Key、登录密码或 MCP token，不在聊天发送、不写 Git/文档。

固定 client_id/audience：`nku-genios-identity-read-pilot-20261003`。
固定回调：`https://coze.nankai.edu.cn/product/llm/info/oauth`；无 refresh token。
用户令牌最长600秒且不超过原登录会话。客户端凭据保留至撤销，测试结束需删除/禁用试点配置。

本页无外部脚本、网络请求、存储或表单提交；服务仅绑定loopback、固定路径白名单、拒绝query/body/非GET。
密钥仍在本机内存及用户主动复制的剪贴板，不能防范已感染设备、扩展或屏幕旁观。
关闭/清空后不保存；若浏览器不允许剪贴板，应人工复制而非用工具读取密钥。

协议测试通过前保持 `CLOUD_OAUTH_PILOT_ENABLED=false`。学校若缺S256/state，停下，不降级身份校验。
