# D 任务书：后端、MCP、工作流与部署

> 这份文件是给负责 D 模块的 Coding Agent 的完整任务说明。AI 负责后端、接口适配、MCP、任务确认、部署配置和测试。没有平台权限时必须如实记录阻塞，不能假装部署成功。

## 直接交给 Coding Agent 的开场指令

```text
你是本仓库的 D 模块 Coding Agent。

请直接完成工程任务，不要只给我方案。你需要自己检查仓库、创建和修改文件、运行测试，并在最后汇报实际结果。

开始前先阅读：
1. README.md
2. contracts/integration-conventions.md
3. contracts/api.schema.json
4. 本文件全部内容

第一轮只完成 D01 到 D03：后端骨架、统一响应、healthz/readyz、官方 SDK 的 health_probe、测试和部署检查表。

没有平台账号、域名、密钥或部署权限时，写 WAITING_HUMAN，继续完成本地代码和测试，不得声称已接通平台。
```

## 你的角色

你负责：

- 后端配置和身份层
- 数据库、事务和迁移
- REST 注册
- MCP 注册
- 草稿、确认、幂等提交
- 通知待办工作流
- TasksPage 后端接口
- A/B/C 领域函数的薄适配
- GenioS 平台接入和发布证据
- 部署、持久化、备份和回滚说明

你不负责重写 A/B/C 的领域算法和页面。

## 允许修改的范围

```text
backend/app/core/
backend/app/db/
backend/app/api/
backend/app/mcp/
backend/app/domains/tasks/
workflows/
prompts/main.md
prompts/notice-extract.md
deploy/
contracts/
对应测试
docs/evidence/
docs/releases/
docs/handoffs/D-progress.md
```

## 第一阶段必须完成

实现：

```text
GET /healthz
GET /readyz
MCP health_probe(nonce)
```

`health_probe` 必须返回：

```json
{
  "nonce": "原样回显",
  "build_id": "非敏感构建标识",
  "server_time": "带时区时间"
}
```

必须完成：

- FastAPI 基础结构
- 配置加载
- 统一 API 信封
- 统一错误码
- 日志脱敏
- 官方 MCP SDK 客户端测试
- 本地启动说明
- `deploy/.env.example`

## 领域函数适配

不得重写领域算法，只做薄适配：

```text
A search_spots       → search_scenic_spots
A search_materials   → search_study_materials
B find_free_slots    → query_free_time
B check_time_plan    → check_time_plan
C audit_degree_progress(plan, records)
  → audit_degree_progress(workspace_ref, plan_id, transcript_ref)
```

适配过程必须：

1. 从服务器身份层构造 Principal
2. 检查 workspace 和资源权限
3. 加载允许的数据
4. 调用领域函数
5. 按 `contracts/api.schema.json` 包装结果

## 安全和数据门禁

- 默认 `AUTH_MODE=demo_fixture`
- demo 模式只允许固定虚构夹具
- 不能仅凭 `dataset_kind=demo` 放行任意数据
- 不能使用 `user_id`、`workspace_ref`、`SYS_USERID` 或 MCP session_id 推断真实身份
- 真实数据身份绑定通过前保持关闭
- 所有写入必须有草稿、确认、revision、payload_hash 和幂等键
- 同一幂等键重试不能产生第二条记录
- 旧 revision、错误 owner、过期票据必须拒绝
- 服务密钥不得进入前端、扩展、Git、日志或截图

## MCP 工具注册顺序

只有对应领域函数和测试已经交付后才能注册：

```text
health_probe
validate_timetable
query_free_time
check_time_plan
search_scenic_spots
search_study_materials
create_task_draft
get_task_status
audit_degree_progress
```

不能发布：

```text
save_todo
commit_task
commit_schedule
任意 SQL 工具
任意 URL 抓取工具
```

## 平台接入要求

只有真实操作成功后才能写平台通过。需要记录：

- 平台空间和 Agent 标识
- MCP 地址
- 协议版本
- 工具发现结果
- 脱敏后的请求方法和 request_id
- nonce 调用结果
- build_id
- AUTH_MODE
- 未完成事项

没有账号或权限时，记录：

```text
WAITING_HUMAN
需要人工提供：平台账号、工作空间、HTTPS 地址、密钥配置权限
```

## 测试要求

至少完成：

```text
D01 健康检查和统一响应
D02 health_probe 本地客户端发现和调用
D03 错误输入和认证失败
D04 demo 模式拒绝任意非夹具数据
D05 草稿确认和幂等提交
D06 REST/MCP 对同一夹具结果一致
D07 通知 event/due 语义分离
D08 旧 revision 和错误 owner 拒绝
```

## 完成后的汇报格式

在 `docs/handoffs/D-progress.md` 写入：

```text
任务状态：LOCAL_PASS / PLATFORM_PASS_DEMO / PLATFORM_PASS_PERSONAL / WAITING_HUMAN
修改文件：
REST 路由：
MCP 工具：
领域函数映射：
Schema 版本：
测试命令：
测试实际结果：
平台真实证据：
当前 AUTH_MODE：
未完成事项：
回滚方式：
```
