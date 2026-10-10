# 南开校园助手

这是团队共享仓库。开始任何模块开发前，先阅读：

- [`contracts/integration-conventions.md`](contracts/integration-conventions.md)：跨 Agent 的唯一命名、路由、配置和函数映射约定
- [`contracts/api.schema.json`](contracts/api.schema.json)：统一 API 信封、查询参数、时间结果和培养方案审计结果
- [`contracts/core.schema.json`](contracts/core.schema.json)：原始任务包内嵌的共享业务数据结构
- [`deploy/.env.example`](deploy/.env.example)：非秘密配置模板
- [`fixtures/`](fixtures/)：明确标注的虚构共享测试数据

个人任务书中的内部函数可以保留各自命名，但跨 REST、MCP、前端和扩展的边界必须按上述契约转换。公共 JSON 字段统一使用 `snake_case`。

## 免账号密码使用、固定设备码与 Agent 关联（团队共用身份链路）

这不是废弃的演示功能，也不是学校 SSO：浏览器创建独立私有空间，固定 `DEV-…` 码用于定位设备，Agent 经本人 OAuth 授权后关联同一个空间。不能用共享 MCP token 或学校登录替代本人授权，不能把不同浏览器的数据静默合并。

- [完整流程、配置、源码索引与验收](docs/browser-visitor-rollout.md)
- [本轮交接：已有 PR 与缺失补交范围](docs/handoffs/browser-visitor-device-flow-2026-10-10.md)
- [Agent 追加规则](deploy/genios-workflows/browser-visitor-agent-append.txt)

维护课表（B）、日历（D）或公共页面（C）时须保留这套身份入口、Cookie 恢复、owner 校验及撤销行为。课表文件上传修复另见 PR #15；这套身份链路不属于课表解析器，不要因本地未启用配置而删除它。

## 前端工具站（C 维护）

一个 Vite + React + TypeScript 单页应用，包名 `web`，路由统一前缀 `/tools/`：

```bash
pnpm install --frozen-lockfile
pnpm dev          # 开发服务器
pnpm test         # Vitest 单元测试
pnpm build        # 类型检查 + 生产构建
```

构建变量见 `frontend/.env.example`：前端只用 `VITE_API_BASE_URL` 访问后端；`VITE_GENIOS_AGENT_URL` 未配置时“返回 NK-GeniOS”按钮禁用。后端命令见 `backend/README.md`。
