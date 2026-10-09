# 自建后端第一阶段检查与本地实测

## 结论与基线

检查日期：2026-09-27。GitHub 主分支检查基线为 `a5ada919eda7415734a7322e9a49d345616f283a`（已合并 PR #6）。原本机 main 停留在 `2985a11`，不能据此说 GitHub 没有后端。

结论：**可继续搭建并准备服务器探针测试；不满足完整业务上线条件。** 本次实现位于 `codex/d-mcp-local-readiness`，没有修改 A/B/C 领域算法、公共路由、业务契约或部署云端。

## 仓库现状

| 项目 | 检查结果 |
|---|---|
| Python 运行时/依赖 | Python 3.12.14；安装版本逐项匹配 requirements.lock；pip check 通过 |
| 变更前后端测试 | 85 passed，1 条第三方弃用警告 |
| 当前 MCP | 官方 mcp==2.2.0；只注册 health_probe |
| REST | 健康/就绪、演示工作区、票据、草稿、确认、课表提交/读取、任务提交/读取 |
| 未注册的业务 REST | 景点、资料、课表 validate、时间查询、培养方案 audit 等目标适配尚缺 |
| 真实景点源 | catalog.jinnan.json 经 A 的 load_catalog 结构及语义校验通过；34 点、91 照片引用，版本 jinnan-2026-09-26；公开查询 limit=20 返回20条 |
| 当前景点默认源 | Python 默认仍是 catalog.demo.json，不能把领域函数存在视为真实景点已经服务化 |
| 公共工具站 | frontend/src/app/pages.tsx 的 ScenicPage、StudyPage、TasksPage 仍为占位；独立三维地图不等于公共站/后端已对接 |
| 个人数据 | demo_fixture、个人上传关闭；没有验证真实学生身份绑定 |

这次关注已合并主分支；未将未合并 PR 计入已交付能力，未保证全部前端/平台流程可用。

整站回归补充：使用仓库指定的 pnpm 12.5.1，`install --frozen-lockfile --ignore-scripts` 完成锁定安装；未改 package.json、pnpm-workspace.yaml 或锁文件。前端 23 项、扩展（含产物检查）25 项、import-core 38 项均通过；前端 TypeScript/Vite 构建、扩展构建、import-core/extension 类型检查通过。加上本次后端 119 项共 **205 项通过**，不包含独立三维地图浏览器交互或学校平台回归。

实际运行脚本：`npm --prefix frontend test`、`npm --prefix frontend run build`；`pnpm --filter @campus/extension verify`、`pnpm --filter @campus/import-core test`；`npm --prefix packages/import-core run typecheck`、`npm --prefix extension run typecheck`。npm 在此仅运行本地已锁定安装的 package scripts，没有另装一套前端依赖。

保留非阻断警告：根 package.json 的旧 `pnpm.onlyBuiltDependencies` 被 pnpm 12 忽略；import-core 的 Ajv 报 date/date-time format 未注册（模块另有日期语义测试）。未越权改 C/B 的配置/算法，不把这些警告称为已修复。首次安装遇到用户 npm 配置里的失效本地代理，后用仅本次进程的独立配置完成，不修改用户全局代理。

## 本次补齐

1. 严格 MCP URL 探针：发现、调用、nonce、build_id、结果结构、时区、空输入拒绝；缺/错令牌负例；分页限制、超时、非零失败退出码及脱敏失败输出。
2. REST 启动也校验预发布配置，避免 REST 正常启动但 MCP 因配置错误起不来的误判。
3. MCP 接受配置中明确的公共 Host/Origin，保留 SDK 的 DNS rebinding 保护；没有 Origin 的合法服务端请求允许，未知 Host/Origin 拒绝，绑定 0.0.0.0 也不关闭保护。
4. 独立本地双进程测试脚本：动态本机端口、随机临时令牌、同一绝对 SQLite 路径、固定夹具草稿/确认/提交/幂等、重启持久化、完整性检查和进程清理。
5. Windows 一条命令测试入口、预发布空白保密配置模板、服务器信息表及实际验收手册。

业务 Schema 仍为 `1.0.0`，没有新增或改名 REST/MCP 业务字段。探针命令新增必填 `MCP_PROBE_EXPECTED_BUILD_ID`；它是测试客户端参数，不是平台工具参数。

## 已完成实测

命令（仓库根）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/Test-Local.ps1
```

2026-09-27 21:34:27 +08:00 的本地传输记录：

| 检查 | 真实结果 |
|---|---|
| 后端回归 | 119 passed，1 条 anyio/Starlette 弃用警告 |
| REST healthz/readyz | 成功信封、request_id、schema 1.0.0、构建编号一致 |
| 构建 | local-check-93a4112eccc9 |
| MCP 测试地址 | http://127.0.0.1:52397/mcp（临时本机端口，测试结束已停止） |
| 协议 | 2025-11-25 |
| 工具发现 | health_probe |
| nonce | Dda8i6gnEGY7QoyWLj4joA，原样返回 |
| 缺/错 Bearer | 均为 HTTP 401 |
| 错误 build_id | 探针进程退出 1，报告 ok=false |
| 空 nonce | SDK 工具错误，被拒绝 |
| 公共 Host / Origin | 单元测试：配置 Host 初始化 200；陌生 Host 421；陌生 Origin 403 |
| 已确认虚构任务 | REST 进程重启后仍保留同一 task_id；幂等重试没有重复任务 |
| SQLite | integrity_check=ok |
| 清理 | 仅结束测试进程、清理本次临时 SQLite；未使用/改动现有业务库或 .env |

## 未完成边界与下一步

- **平台状态仍为 WAITING_HUMAN，不是 PLATFORM_PASS_DEMO。** 没有服务器部署、HTTPS 证书或 NK-GeniOS 的真实调用证据。
- 用户已表示有云服务器；仍需系统/架构、现有服务和端口、Docker 情况、域名/证书、持久目录及访问授权信息。部署前不自行猜测。
- 比赛指定空间和主 Agent 需明确；平台 UI 存在 MCP 选项不代替真实工具调用。
- 服务器探针及平台验证后，再注册景点 REST/MCP、显式加载真实目录，并与 C/A 对接公共地图及照片/深链接。尚未做 REST/MCP 真实景点同源验收。
- 本次没有数据库引擎迁移、管理员公开写接口或真实学生身份绑定。

操作手册：`deploy/PREPARE-AND-TEST.md`。保留此前 D03 平台证据表，获得真实平台调用记录后再更新通过状态。
