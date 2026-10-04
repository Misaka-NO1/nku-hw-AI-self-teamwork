# 隔离的 CloudBase 待办测试站

这不是既有 `nku-campus-mcp-probe` 的升级包，不能上传到 MCP 005 服务。
仅用于三份固定虚构通知的 TasksPage 测试，不接受真实个人数据，不发布主 Agent。

## 数据和安全边界

- 复用环境 `sunner-wang-d8ght8niaaaea70b7` 的 PostgreSQL 共享实例。
- 新 Schema `nku_tasks_demo_v1` 的 7 张表，与原业务表隔离。
- 唯一公开 RPC 名 `nku_tasks_demo_v1_rpc`；函数内必须核验 JWT 的 `service_role`。
  不依赖网关检查 EXECUTE 权限；底层表无匿名/普通用户授权，并启用 RLS。
- 后端用 CloudBase API Key 调用，浏览器只持有自己的短期 HttpOnly/Secure 会话
  Cookie 和 CSRF；共享 MCP Bearer 不能替代浏览器身份。
- 每次保存/确认/幂等返回为单次 PostgreSQL 事务，按 owner 使用 advisory lock。
  确认 token 一次性，错误 revision/hash、跨工作区、过期资源拒绝。
- 三份夹具由迁移脚本写入，只以允许的 payload_hash 选择，不能修改真实通知。
- 24 小时工作区，上限 100 个有效会话，每工作区至多 10 草稿；请求体上限 32 KiB。
  新建会话时仅清理本测试 Schema 的过期会话及关联测试记录。
- 时间检查仍调用 B 的现有算法，但只用 `demo-workspace-01` 公共虚构课表，
  不包含已保存任务，不能说是个人真实空闲时间。
- 本服务不开放 MCP、课表导入、其他工具页、原始 SQL 或公共管理操作。

**重要：CloudBase service_role API Key 可绕过 RLS，权限覆盖整个环境，
不是仅此 Schema 的受限凭据。** 负责人已授权仅 1 天测试密钥；由负责人直接在
控制台创建；新服务按密钥名称自动注入，不读取或复制密钥值到聊天/Git/前端/学校平台。到期后必须停止
测试或另行授权更新；本包不能称为正式生产部署或最小权限最终方案。

## 构建

先使用本机 `deploy/Start-Demo.ps1` 构建前端并完成本机测试，或直接在 frontend 目录
运行已安装的 `node node_modules/typescript/bin/tsc --noEmit`、
`node node_modules/vite/bin/vite.js build --outDir dist-demo`（同源 API、公开内容限定标志关闭）。
本机测试产物与公开地图的 `frontend/dist` 分开，避免互相覆盖。不要把开发依赖打进 release。

2026-10-02 后续本机新增的账号登录、课表与自有时间查询不属于已部署 r4 云站的能力。
此包的云端入口仍只开放 Tasks 和固定公共时间夹具；不能因为前端有页面就声称云 API 已接通。

在仓库根目录：

```powershell
backend\.venv\Scripts\python.exe backend/scripts/build_cloud_tasks_package.py --name cloudbase-tasks-demo-20261002-r4
```

输出 ZIP、逐文件 SHA256 清单及 `database-migration.sql` 均在被忽略的 `dist/`。
脚本拒绝覆盖已有目录，不含 `.env`、数据文件、node_modules 或 API Key。

## 数据库部署

1. 只读确认 `to_regnamespace('nku_tasks_demo_v1')` 尚不存在。
2. 将包内 `database-migration.sql` 放入 SQL 编辑器执行。它创建新 Schema、7 表、
   固定夹具及角色受控 RPC；不使用 DROP/覆盖旧函数或业务表。
3. 复核表数 7、夹具数 3、函数存在；重复执行会拒绝，而不是覆盖数据。
4. 运行本目录 `smoke-test.sql`；所有断言完成后 ROLLBACK，不保留模拟任务。
   这是数据库层验证，不等于服务端密钥、HTTPS 或学校平台闭环验证。

## 新服务部署配置（待实际验收）

新服务名建议 `nku-campus-tasks-demo`，不能选 `nku-campus-mcp-probe`。
部署 ZIP 中的根 Dockerfile；端口 8080，最小实例 0、最大 1，选择现有套餐内小规格。
出现新增付费购买/升级或法律协议时停止，请负责人处理。

| 环境变量 | 值 |
| --- | --- |
| APP_ENV | staging |
| AUTH_MODE | demo_fixture |
| ALLOW_PERSONAL_UPLOADS | false |
| DEMO_WORKSPACE_TTL_HOURS | 24 |
| APP_ORIGIN | 新服务实际 HTTPS 域名的 origin，不带路径、参数 |
| BUILD_ID | 包清单对应的独立测试版本号 |
| CLOUDBASE_APIKEY | 控制台勾选 API Key 设置，按名称选择负责人创建的 1 天密钥，自动注入后端 |

后端兼容手动秘密配置的 `CLOUDBASE_API_KEY` 别名，但优先使用自动注入项。
若首次建服务时域名尚未生成，临时设置 `APP_ORIGIN=https://tasks.example.test`；
此时健康检查可运行，但真实浏览器写操作会被 Origin 门禁拒绝，不算可用。
取得实际 HTTPS 域名后必须更新新服务 APP_ORIGIN 并重新部署，再进行浏览器验收。
不能以请求 Host/Origin 自动信任替代这个配置。
MCP 服务 token/旧服务环境变量不要复制进来；没有凭据或 RPC 不通时启动失败。
先核验 `/__tcb_probe__` 精确 `ok` 和 `/healthz` 数据库探针，再开放 HTTPS 测试。

## 验收与停用

浏览器创建虚构工作区 → 生成草稿（列表仍为空）→ 人工确认 → 得到真实 task_id
→ 刷新 → 新服务实例重启后同会话读回 → 同幂等键重试只返回原 task_id。
再验证含糊通知无法保存、他人会话访问拒绝、缺 CSRF/Origin 拒绝。
学校 Agent 不应获得写操作或服务密钥，只能指引用户打开测试站，不冒充个人账号。

停用时可关闭**新测试服务** HTTPS 或停止新实例，不动 MCP 005。
数据库清理涉及永久删除时另行确认；本次建表及回滚测试未删除旧业务数据。
未来 D11 正式验收仍需受限运行身份、备份恢复演练、限流监控和真实双账号授权。
