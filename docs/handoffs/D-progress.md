# D Agent 进度交接

## 2026-09-28 更新：CloudBase 私有探针交接

用户提供的腾讯云交接文档报告：目前没有 CVM/轻量服务器；已有上海 CloudBase 环境 `sunner-wang-d8ght8niaaaea70b7`，其中 `nku-campus-mcp-probe` 私有 002 版已部署并通过容器探针，但公网关闭、数据库未接入、NK-GeniOS 未真实调用。当前会话尚未独立核验控制台状态。交接文档提及的原始 `deploy/cloudbase-mcp/` 不在已拉取的主分支，现已基于本仓库代码另建候选部署包，**不能声称与云端 002 源码相同**。

候选代码已于本轮推送到 `origin/codex/d-mcp-local-readiness`，代码提交 `b91ca41`。未创建 PR、未合并主分支。尝试只读查看腾讯云控制台时，当前会话被导向腾讯云登录页；用户接管登录前，云端 002 状态仍以交接文档为报告来源，不能写成已现场复核。

本地变更：MCP 服务增加仅 `GET /__tcb_probe__` 返回 `ok` 的 CloudBase 健康检查，不更改工具名或业务 Schema；测试确认 `/mcp` 和错误方法/路径仍需 Bearer。新增 CloudBase Python 3.12/8080 Dockerfile 与操作说明，未连接已有 PostgreSQL，也不在容器中保存 SQLite。没有 Docker，本机镜像构建待云端或具备 Docker 的环境验证。

测试：`deploy/Test-Local.ps1` 再次通过；后端 120 项测试通过（1 条第三方弃用警告），真实本地 MCP 初始化、发现、nonce、错误令牌拒绝、错误构建号失败及虚构任务重启持久化均通过。平台端到端状态仍 `WAITING_HUMAN`。

下一步：待用户登录当前云端控制台后只读核验 002 配置；确认原始部署包/云端版本差异和对 `nku-campus-mcp-probe` 的变更授权；再更新候选探针，安全配置令牌并经独立 HTTPS 探针验证，最后在比赛空间让主 Agent 真调用。公网开关未获确认前不启用。业务存储后续选独立 PostgreSQL 或用户确认的隔离实例与迁移方案，绝不改写现有应用的表/权限。

## 2026-09-27 历史更新：自建后端第一阶段

## 2026-09-27 更新：自建后端第一阶段

任务状态：本地 `LOCAL_PASS`；云端/学校平台 `WAITING_HUMAN`。检查基线为最新拉取的 main `a5ada91`，实现分支 `codex/d-mcp-local-readiness`。用户同意先搭建、准备测试，并表示已有云服务器，服务器详情尚待提供。

本次修改：严格 MCP 探针、公共 Host/Origin 白名单、REST 启动配置校验、双进程隔离测试脚本、预发布模板和测试手册。没有更改 A/B/C 算法、公共前端、业务 Schema、REST 路径或 MCP 工具名；仍只暴露 `health_probe`。

新增测试客户端配置：`MCP_PROBE_EXPECTED_BUILD_ID`。Schema：`1.0.0`；`AUTH_MODE=demo_fixture`，个人上传关闭。

实际测试：119 项后端测试通过；官方客户端真实本机 HTTP 初始化、发现、调用及缺/错令牌 401、错误 build_id 退出1、空 nonce 拒绝通过；固定虚构任务确认/幂等/重启持久化通过，SQLite integrity_check=ok。运行命令见 `deploy/PREPARE-AND-TEST.md`，完整证据见 `docs/evidence/platform/D03-local-readiness-2026-09-27.md`。

整站回归：前端23项、扩展25项、import-core38项通过，加后端共205项；前端生产构建、扩展构建及 B 两包类型检查通过。pnpm12旧配置警告、Ajv日期格式警告仍记录在证据中；没有修改前端依赖版本或锁文件。独立三维地图浏览器交互和平台回归不在此通过数量中。

当前 A/B/C 领域函数已有交付（下方早期记录的“尚未交付”不再代表现状）。真实景点目录已校验，但景点 REST/MCP 尚未注册，公共站地图/复习/待办还为占位；下一步先完成服务器与平台探针，再推进领域薄适配和公共前端同源数据联调。

平台真实调用证据：无。待提供服务器系统、运行方式、现有业务、域名/HTTPS、持久目录及授权；主 Agent 必须在比赛指定空间验收。没有远程部署、未迁移数据、不需要回滚线上服务；撤销本轮文件变更即可恢复本轮前代码，旧客户端探针命令需与对应版本说明配套。

## 2026-09-20 历史交接（保留，非最新全项目状态）

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
