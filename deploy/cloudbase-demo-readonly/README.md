# CloudBase 只读固定演示候选包

目标：更新已有 `nku-campus-mcp-probe`，保留 `003` 版可回退。用户已选择此方案，但发布、流量切换、公网开放须在操作前另外确认。本目录与原 `deploy/cloudbase-mcp/` 的单探针包分开，避免误将缺资源的旧包打开业务开关。

## 包里有什么、不能做什么

仅运行官方 Streamable HTTP MCP：health_probe 加六个已测试的只读领域工具（课表校验、空闲时间、时间计划检查、景点查询、资料查询、培养方案审计）。业务对象、工具名和信封沿用冻结 Schema 1.0.0，不重写 A/B/C 算法。

只接受预置虚构夹具和允许的公开演示资料；不代表真实课程、成绩、校园花况或官方毕业结论。服务令牌不是用户身份，即使知道浏览器工作区编号也拒绝访问。

容器不启动 REST、前端或写入接口，不提供 commit/save/SQL/任意 URL 抓取工具；不初始化业务数据库、不运行迁移、不挂载持久存储。`sqlite:///:memory:` 是强制配置门禁，不是已部署数据库。通知草稿、工作流、TasksPage、知识库平台导入和真实身份仍是后续步骤。

包保留 `/srv/campus/backend/app`、`contracts`、`fixtures`、`knowledge` 的相对层级。仅打包 Python 源码、锁定依赖清单、两个 Schema、13 个虚构夹具、3 项知识资源和根清单。不含 `.env`、令牌、数据库、日志、真实景点目录、私人资料正文、缓存、测试或前端。

## 生成与本地验收

在仓库根目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/cloudbase-demo-readonly/Build-Package.ps1
```

输出新 ZIP 路径、BUILD_ID、SHA256 和 `INCLUDED_SOURCE_DIRTY`。不覆盖已有包；候选发布包要求所包含源码已提交、dirty=false。包在被忽略的 `dist/` 中，不能提交 ZIP 或秘密到 Git。

在 backend 目录，将路径换成刚生成的 ZIP：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_domain_bundle.py <ZIP绝对路径>
```

验收先拒绝重复/越界/额外条目，校验清单 SHA 和当前源文件，再解压到独立临时目录。MCP 只导入解压包，REST 对照实例使用仓库源码，分别启动本机 HTTP；测试七组成功、一组失败的信封一致性、无/错令牌拒绝、nonce/构建号、浏览器工作区隔离、非夹具拒绝、公开正文/私人资料过滤。令牌随机生成在内存、不输出；临时资源结束清理，只停止本次进程。

此检查不是 Docker 镜像构建或云端/平台验收。本机无 Docker，因此镜像构建留待获准的 CloudBase 构建阶段。Dockerfile 的构建上下文必须是 ZIP 解压后的根目录（其中有生成的 `domain-bundle-manifest.json`），不能直接在仓库根目录构建。

## 获准后才执行的发布核对

1. 只更新既有服务，先记录当前版本和流量；保留 003，不删除或覆写旧版本。公网和内网入口保持关闭，端口8080、实例最小0/最大1不变。
2. 上传已验收的 ZIP，选择其根 Dockerfile 构建。先确认界面是否自动切100%流量，按用户批准范围执行。
3. 保留原服务令牌的隐藏配置，不读取、截图或打印其值。曾暴露的旧令牌仍有风险，扩大工具范围前明确告知；令牌持有人可调用虚构只读数据并消耗资源，不能据此访问个人工作区。
4. 逐项核对环境：

| 配置 | 值 |
|---|---|
| APP_ENV | staging |
| MCP_HOST / MCP_PORT / MCP_PATH | 0.0.0.0 / 8080 / /mcp |
| MCP_REQUIRE_AUTH | true |
| MCP_SERVICE_TOKEN | 保留保密配置，不在说明中写值 |
| MCP_PUBLIC_URL | 已批准的原默认 HTTPS 域名后加 /mcp；不意味着开启公网 |
| MCP_ENABLE_DOMAIN_TOOLS | true |
| DOMAIN_BUNDLE_MANIFEST_PATH | /srv/campus/domain-bundle-manifest.json |
| BUILD_ID | 必须与本次包清单完全一致 |
| AUTH_MODE / ALLOW_PERSONAL_UPLOADS | demo_fixture / false |
| DATABASE_URL | sqlite:///:memory: |

5. 配置或资源错误即拒绝启动，不把健康探针当作业务通过。校验是资源完整性检查，不是签名或供应链安全证明。
6. 构建和容器健康通过后，另行获准公网联调，再验无/错Bearer401、正确令牌的工具发现与固定案例。NK-GeniOS 插件仍只有旧 health_probe；发现/更新/发布六类业务工具及主 Agent 实际调用须分别验收，不能靠本机测试签收。
7. 本轮结束或需人工处理阻塞时关闭入口。主 Agent 仍不发布，不改其他服务/数据库。

## 回退

优先关公网，再将流量切回保留的003。该旧版只含health_probe，须恢复003对应 BUILD_ID，并关闭 `MCP_ENABLE_DOMAIN_TOOLS`、清空包清单路径；检查旧版健康/鉴权和平台工具绑定。保留其原HTTPS/Bearer配置，避免旧版加载新增业务资源。无业务数据库迁移需要反向执行。切回与配置变更均须按实际控制台行为核对，不凭推测宣称成功。
