# D Agent 进度交接

任务状态：本地 `LOCAL_PASS`；平台 `WAITING_HUMAN`

修改文件：`backend/` 后端、MCP、SQLite 事务与写入工作流，`contracts/`、D 所有的 `fixtures/`、`deploy/`、本文件及平台证据模板。

REST 路由：

- `GET /healthz`
- `GET /readyz`
- `POST /api/v1/demo/workspaces`
- `POST /api/v1/import-tickets`
- `POST /api/v1/schedules/import-drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/confirmations`
- `POST /api/v1/schedules/commit`
- `GET /api/v1/schedules/current`
- `POST /api/v1/tasks/drafts`
- `POST /api/v1/tasks/commit`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`

MCP 工具：

- `health_probe(nonce)`

领域函数映射：第一轮 D01–D03 不注册 A/B/C 业务函数，避免领域实现尚未交付时发布假工具。

Schema 版本：`1.0.0`

测试命令：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\probe_mcp.py
```

测试实际结果：23 项通过。D01–D03 包含健康检查、统一信封、共享 Schema、官方 MCP 客户端发现/调用、空 nonce、Bearer 认证及真实本地 Streamable HTTP。D04/D05 另验证：通知和课表任意伪 demo 数据拒绝、CSRF、一次性导入票据只存 hash、票据过期/重放、跨浏览器 owner 隔离、旧 revision、篡改/过期确认回执、草稿/提交幂等和工作区清理。当前 Windows 工作区路径含中文，pytest 缓存插件会在该运行时的临时目录创建阶段卡住，因此项目配置明确关闭 cacheprovider；测试本身不受影响。

平台真实证据：无。原因和待填字段见 `docs/evidence/platform/D03-platform-probe.md`。

当前 `AUTH_MODE`：`demo_fixture`

未完成事项：用户已选择暂不部署，因此真实 HTTPS、NK-GeniOS 插件配置、平台协议协商记录和主 Agent 真实 nonce 调用继续保持 `WAITING_HUMAN`。A/B/C 领域服务尚未交付，不注册相应 REST/MCP 假工具。

回滚方式：本轮未执行数据库迁移或平台变更。代码可回滚到本分支前一提交；环境变量中的服务令牌应在回滚或泄露怀疑时轮换。后续已有平台配置后，必须先解除主 Agent 插件绑定，再回滚服务版本，避免旧 Schema 对接新服务。
