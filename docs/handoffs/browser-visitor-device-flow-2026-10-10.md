# 团队交接：免账号密码 + 固定设备码 + Agent 本人关联

## 仓库核对结论

2026-10-10 核对上游 `main`（`cadb7fd`）和全部近期 PR：

- PR #13 已合并，包含固定设备码、`bind_my_browser`、本人 OAuth、设备码查看入口及日程删除。
- PR #15 仍是独立课表 JSON 上传修复，不含浏览器访客免注册功能。
- 后续已部署的访客入口、私有访客表、RPC 包装、传输白名单和前端按钮此前留在本地未提交。这解释了同伴在 GitHub 找不到完整流程；不是这套功能应该删除。
- 本轮基于最新上游 main 独立补交访客部分，不叠加 PR #15 的课表解析/上传补丁，不替换 B/C/D 的领域算法。

## 团队分工 / 不可误删边界

本功能是工具站、Agent 和 B 课表 / D 日历共用的身份基础设施，不是 B 的课表文件解析器，也不是公开资料服务。
完整源码索引、配置和迁移说明见 [browser-visitor-rollout.md](../browser-visitor-rollout.md)。README 已设入口；Agent 配置追加规则见 [browser-visitor-agent-append.txt](../../deploy/genios-workflows/browser-visitor-agent-append.txt)。

保留：免注册显式入口、固定设备私密 Cookie、会话恢复、本人 OAuth 同意、devices:bind、owner/工作区隔离、注销与撤销、公开设备码不能登录的限制。
缺配置或依赖失败时修配置并禁止私有写入，不应删除这些判断或回退到大家共用的演示课表。

## 验证与发布边界

本轮测试结果在最终 PR 说明中记录。测试用独立本地 PostgreSQL 和虚构输入；不上传用户真实课表、设备私密凭证、云密钥、Cookie 或已构建环境配置。

已重新运行：后端本人身份/设备/课表/日历/打包回归 **69 项通过**，前端全量 **209 项通过**、TypeScript 类型检查通过，SQL 全量 **50 项通过**（含新增访客 RLS/角色隔离/恢复/会话上限 4 项）。Windows 初次沙箱运行被依赖软链接/子进程权限阻断，获准正常读取本地依赖后重跑通过；不是忽略失败后宣称成功。

复现（先安装仓库已有锁定依赖，测试不需要云密钥）：

```text
pnpm --filter web test
pnpm --filter web exec tsc --noEmit
cd deploy/cloudbase-identity-pilot/sql-tests
npm ci
npm test
cd ../../../backend
python -m pytest tests/test_browser_visitor.py tests/test_agent_device.py tests/test_cloud_identity_site.py tests/test_personal_schedules.py tests/test_personal_task_isolation.py tests/test_task_delete.py tests/test_persistent_auth.py tests/test_cloud_identity_package.py
```

`backend/scripts/verify_live_visitors.py` 是另外的线上冒烟工具，执行会在原服务新建两个空白 QA 访客，不是只读检查；本轮未运行，不应作为自动测试或随构建执行。它不写课表/日历，不导出 Cookie，仅输出状态和布尔结果。
历史 2026-10-09 云端部署记录保留在流程文档中；源码提交不是新一轮线上部署回执。本次只上传 GitHub 并发起 PR，不合并、不重跑生产迁移、不扩学校体验名单、不修改现有用户数据。

学校 Agent 的发布配置不是 Git 文件：联调时核对现有插件 `campus-identity-pilot-read` 的 OAuth auth/token 地址、Scope `demo:read tasks:read tasks:write devices:bind`（只开实际需要的权限）以及工具 `bind_my_browser`；不要把共享 MCP_SERVICE_TOKEN 填作用户 OAuth token，不复用别人的授权。
