# 文档导航与阅读顺序

本页整理仓库阅读入口，保留原文件路径。交接文档、设计方案和测试证据各自记录当时状态；最新状态须结合对应模块更晚的记录和实际验收判断，不能仅凭文件名、源码存在或本地测试推断线上已完成。

## 开始开发

1. 阅读根目录的 [AGENTS.md](../AGENTS.md) 和 [跨模块对接约定](../contracts/integration-conventions.md)。
2. 用 [团队开发入口](handoffs/TEAM-DEVELOPMENT-ENTRY.md)了解本机开发、分工与部署边界；其中线上地址和状态是文档记录，使用前仍需核实。
3. 查找下表对应模块的交接和证据。培养计划与学分模块先读 [用户流程约定](handoffs/第6模块-用户流程约定.md)。

## 按工作内容查找

| 工作内容 | 阅读入口 |
|---|---|
| 前端启动与构建 | [仓库说明](../README.md#前端工具站c-维护) |
| 后端运行与本地检查 | [后端说明](../backend/README.md)、[部署准备与测试](../deploy/PREPARE-AND-TEST.md) |
| 接口与数据结构 | [对接约定](../contracts/integration-conventions.md)、[API Schema](../contracts/api.schema.json)、[核心数据 Schema](../contracts/core.schema.json) |
| 浏览器访客、设备码与本人授权 | [完整身份流程](browser-visitor-rollout.md)、[2026-10-10 交接](handoffs/browser-visitor-device-flow-2026-10-10.md) |
| 教务课表插件与文件导入 | [B 模块说明](../frontend/src/features/README-B.md)、[插件闭环记录](handoffs/N28-eamis-import-ui-closed-loop-2026-10-08.md)、[JSON 导入记录](handoffs/N29-timetable-json-import-2026-10-09.md) |
| 待办与日历 | [后端接口交接](handoffs/D-task-calendar-backend-2026-10-06.md)、[前端对接](handoffs/待办日历前端与D接口对接-2026-10-06.md)、[任务删除记录](handoffs/N30-calendar-task-delete-2026-10-09.md) |
| 通知读取与时间推荐 | [通知工作流交接](handoffs/D-notice-workflow-2026-10-06.md)、[平台工作流说明](../deploy/genios-workflows/README-notice.md) |
| 培养计划与学分 | [用户流程约定](handoffs/第6模块-用户流程约定.md)、[目标验收对照](handoffs/第6模块-目标验收对照-2026-10-10.md)、[2026-10-11 连接故障交接](handoffs/第6模块-培养计划与课表账号连接故障-修复交接-2026-10-11.md)、[学校旧授权缓存处理](handoffs/第6模块-学校平台旧授权缓存处理.md) |
| 地图与景点 | [津南知识库说明](../knowledge/scenic/README-Jinnan.md)、[地图预览说明](../frontend/src/features/scenic/preview/README.md)、[三维地图说明](../frontend/src/features/scenic/three-preview/README.md) |
| 复习资料 | [一年级资料说明](../knowledge/study/README-Year1.md)、[平台复习工作流](../deploy/genios-workflows/README-study.md) |
| 校园事务与课程资料 | [事务知识库说明](../knowledge/affairs/README.md)、[课程数据](../knowledge/courses/) |
| 云部署与平台接入 | [身份服务](../deploy/cloudbase-identity-pilot/README.md)、[公共内容服务](../deploy/cloudbase-public-content/README.md)、[MCP 接入](../deploy/cloudbase-mcp/README.md)、[平台工作流](../deploy/genios-workflows/README.md) |

## 交接和验收资料

- [交接目录](handoffs/)：按模块和日期定位。跨模块成果可从 [N26 交接](handoffs/N26-current-release-and-team-use-2026-10-07.md)和 [2026-10-08 收尾记录](handoffs/收尾执行记录-2026-10-08.md)开始，再查看后续模块记录。
- [证据目录](evidence/)：浏览器检查、平台调用和回归记录；是否覆盖完整链路须阅读证据正文。
- [阻塞项](blockers/)：记录当时缺失的来源、资产或方案，需结合后续记录判断是否仍存在。
- [任务书](agent-prompts/)：A/B/C/D 原始职责和任务要求，不等同于完成情况。
- [2026-10-01 文档包索引](handoffs/项目文档总索引-2026-10-01.md)：历史交接包入口，保留其原有范围和日期。

## 整理文件时的边界

源码、构建与部署脚本、SQL 迁移、知识库数据、图片和模型、锁文件以及验收证据都可能有路径或版本依赖。看似重复、带有 `demo`、`pilot`、`preview` 或 `dist` 名称的文件不能据此判为废弃。移动或删除前应核查引用及对应功能回归；无法确认时保留原文件。

本次整理仅增加本页与根目录导航，不改变功能、配置、依赖或部署，也不代表培养计划的完整链路已验收。
