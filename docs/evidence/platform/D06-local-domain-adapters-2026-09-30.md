# D06：REST / MCP 固定演示领域适配

日期：2026-09-30（北京时间）；状态：LOCAL_PASS。

D03 的 PLATFORM_PASS_DEMO 只覆盖云端 health_probe，不代替本阶段业务验收。遵循原始 D 文档、仓库任务书、integration-conventions 及 API/core Schema；未修改 A/B/C 算法/页面、云端、数据库或学校平台。

## 实现和门禁

六类领域入口：validate_timetable、query_free_time、check_time_plan、search_scenic_spots、search_study_materials、audit_degree_progress，路径/字段不变。用户明确确认 GET 搜索用一个 query JSON 参数，已同步契约、正例夹具、测试和交接。另有既定 REST 详情/白名单附件下载，无下载 MCP。

MCP_ENABLE_DOMAIN_TOOLS 默认 false，只提供探针；隔离本机联调显式启用领域工具。输入/输出 Schema 直接取 contracts，扩展官方 SDK 的公开 list_tools/call_tool 方法，不修改 SDK 私有注册表；未知字段和类型错误不能静默忽略。

- demo-workspace-01 只指预置公开虚构资源，不是登录身份或浏览器可写工作区。
- MCP 服务只构造 mcp_service/public:read，知道浏览器工作区编号也不能读取。user_id/SYS_USERID/session_id 不充当身份。
- 浏览器工作区按会话、owner、有效期、固定夹具集校验，读已确认课表/任务；缺课表返回 NOT_FOUND，不回退成公共 demo。
- 通知夹具是草稿，不自动占时间。新增回归实际执行草稿→确认→提交，再检查时间变化。
- 课表按规范化 hash 限固定夹具，修改标题仍标 demo 也拒绝。degree 只解析固定 plan/transcript 引用，不接 records、文件路径或任意成绩。
- event/due 分离，due 非忙碌区间，缺预计耗时需确认；历史花期非实时；索引无正文证据；私有/待授权资料不能查询或下载。
- 统一信封、request_id、版本、演示警告、适用来源；MCP 业务失败 isError=true。依赖失败脱敏，日志无参数/正文/令牌。
- trusted_binding 未验证时 fail closed，不自动允许真实业务。

## 实际测试

backend 目录命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_domain_stack.py
```

后端 **172 项通过**，D06 新增 34 项；一条 Starlette/AnyIO 第三方弃用警告。

真实双进程 HTTP：ok=true、scope=local_only、platform_verified=false。官方 SDK 经 Bearer 完成 Streamable HTTP 初始化/发现/调用、nonce/build 核验，7 组正常输入与 1 组错误输入 REST/MCP 一致，无/错 Bearer 拒绝通过。对照仅剔除各自生成的 meta.request_id，其余 data/error/meta 全部一致。使用临时 SQLite、随机内存令牌，避开用户 .env/业务库，结束停止自己的进程。

工具清单：health_probe、validate_timetable、query_free_time、check_time_plan、search_scenic_spots、search_study_materials、audit_degree_progress；默认模式仍只有 health_probe。

## 未完成与回滚

业务工具未更新到 CloudBase/NK-GeniOS，主 Agent 未发布。现有探针包缺业务 contracts/fixtures/知识目录，不能直接打开新开关。前端数据注入、KB、通知工作流、TasksPage、可信身份、云端持久化、最终发布分别待验收。真实景点/课程/成绩材料不在本轮范围。

回滚：关闭新 MCP 开关恢复仅探针；撤销本轮薄适配、路由注册及查询编码补充恢复本地接口。没有线上变更或业务数据迁移。
