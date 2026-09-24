# 南开校园助手

这是团队共享仓库。开始任何模块开发前，先阅读：

- [`contracts/integration-conventions.md`](contracts/integration-conventions.md)：跨 Agent 的唯一命名、路由、配置和函数映射约定
- [`contracts/api.schema.json`](contracts/api.schema.json)：统一 API 信封、查询参数、时间结果和培养方案审计结果
- [`contracts/core.schema.json`](contracts/core.schema.json)：原始任务包内嵌的共享业务数据结构
- [`deploy/.env.example`](deploy/.env.example)：非秘密配置模板
- [`fixtures/`](fixtures/)：明确标注的虚构共享测试数据

个人任务书中的内部函数可以保留各自命名，但跨 REST、MCP、前端和扩展的边界必须按上述契约转换。公共 JSON 字段统一使用 `snake_case`。

## 前端工具站（C 维护）

一个 Vite + React + TypeScript 单页应用，包名 `web`，路由统一前缀 `/tools/`：

```bash
pnpm install --frozen-lockfile
pnpm dev          # 开发服务器
pnpm test         # Vitest 单元测试
pnpm build        # 类型检查 + 生产构建
```

构建变量见 `frontend/.env.example`：前端只用 `VITE_API_BASE_URL` 访问后端；`VITE_GENIOS_AGENT_URL` 未配置时“返回 NK-GeniOS”按钮禁用。后端命令见 `backend/README.md`。
