# 南开校园助手

这是团队共享仓库。开始任何模块开发前，先阅读：

- [`contracts/integration-conventions.md`](contracts/integration-conventions.md)：跨 Agent 的唯一命名、路由、配置和函数映射约定
- [`contracts/api.schema.json`](contracts/api.schema.json)：统一 API 信封、查询参数、时间结果和培养方案审计结果
- [`contracts/core.schema.json`](contracts/core.schema.json)：原始任务包内嵌的共享业务数据结构
- [`deploy/.env.example`](deploy/.env.example)：非秘密配置模板
- [`fixtures/`](fixtures/)：明确标注的虚构共享测试数据

个人任务书中的内部函数可以保留各自命名，但跨 REST、MCP、前端和扩展的边界必须按上述契约转换。公共 JSON 字段统一使用 `snake_case`。
