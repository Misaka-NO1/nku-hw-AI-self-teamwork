# 自建后端第一阶段：准备与测试

目标：按《NK-GeniOS 自建后端与数据库接入指南》先验收 `health_probe`，保持 SQLite、`demo_fixture` 和个人上传关闭。此阶段不注册全部业务、不迁移 MySQL、不修改 A/B/C 的算法和公共前端。

## 1. 本机复测（不需要云服务器）

本机已安装 Python 3.12 以及 `backend/requirements.lock` 的依赖后，在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/Test-Local.ps1
```

`ExecutionPolicy Bypass` 仅作用于这一次 PowerShell 进程，不修改系统执行策略。跨平台也可直接运行：

```text
python backend/scripts/check_local_stack.py
```

这里的 `python` 必须是已安装后端锁定依赖的 Python 3.12。脚本会：

1. 使用系统分配的两个空闲本机端口，启动真正的 REST、MCP 进程。
2. 在独立临时目录创建 SQLite；两个进程使用同一个绝对路径，不读取已有 `.env` 或业务库。
3. 在内存中生成随机服务令牌，不打印、写入仓库或传到命令行参数。
4. 验证健康/就绪信封、官方 MCP 初始化、工具发现、nonce、build_id、带时区时间及空 nonce 拒绝。
5. 验证缺令牌/错令牌返回 401；故意提供错误 build_id 时探针以非零退出码失败。
6. 用固定虚构通知执行草稿→确认→提交→幂等重试；重启 REST 后检查已确认任务仍在且没有重复，检查数据库完整性。
7. 停止自己启动的进程，清理本次临时数据。不停止已有服务、不触碰已有数据库。

成功会显示 `LOCAL_PASS` / `ok: true`。这不是云端或学校平台通过。自动测试结束后不会留下常驻服务；手动常驻启动方式仍见 `backend/README.md`。

## 2. 2026-09-28 CloudBase 交接更新

用户提供的《D同学_腾讯云后端交接.md》报告：当前**没有 CVM/轻量服务器**，目标是上海地域 CloudBase 环境 `sunner-wang-d8ght8niaaaea70b7`；`nku-campus-mcp-probe` 的 002 版已作为私有探针部署，公网入口关闭。这是交接文档报告，尚未通过当前账号控制台独立核验。环境已有其他应用和 PostgreSQL 业务数据，**不改动它们**。

用户现已提供一份 CloudBase 源码压缩包；它的锁定依赖及 37 个 Python 源文件中，除 `main.py`、`config.py`、`mcp/http.py` 外均与当前仓库一致，Dockerfile 也不同。仓库候选版保留了更严格的部署校验与容器默认值；压缩包不包含云端运行配置，无法证明它就是现行 002 镜像。差异见 `docs/evidence/platform/D03-platform-probe.md`。CloudBase 云托管容器文件不是正式持久库，本手册下文的 SQLite 单实例路线仅适用于有可靠持久磁盘的其他托管环境；在 CloudBase 上先只运行无数据库的 MCP 健康探针。公开业务数据或个人工作流需要独立数据库方案与迁移测试，优先独立环境/实例，不能复用已有应用的业务表。

## 3. 原服务器方案核对表（仅用于非 CloudBase 持久主机）

以下信息仍不能从交接文档确定，暂不安装软件、改端口、覆盖配置或部署：

| 项目 | 待填写内容 |
|---|---|
| 系统 | Linux/Windows、发行版/版本、CPU 架构 |
| 运行方式 | 是否已有 Docker；若不用容器，Python/服务管理器情况 |
| 现有业务 | 当前站点、服务和端口，避免干扰其他项目 |
| 入口 | 实际域名、DNS 权限、HTTPS 证书/现有反向代理 |
| 数据 | 一个绝对持久化目录、备份位置、磁盘容量 |
| 访问权限 | 授权访问方式；密码/私钥/服务令牌不要粘贴到聊天或 Git |
| 学校平台 | 比赛指定空间、主 Agent、插件配置权限，外部服务范围确认 |

不根据空白项猜域名、购买资源或暴露数据库端口。

## 4. 服务配置与反向代理要求（有持久磁盘的非 CloudBase 主机）

使用 `deploy/.env.staging.example` 准备服务器保密配置（空值须补齐，不是可直接上线配置）：

- REST 和 MCP 分别运行 `python -m app.main`、`python -m app.mcp.http`；使用同一份配置、同一构建和同一个**绝对 SQLite 文件路径**。代码部署须保留仓库内 contracts/fixtures/knowledge 的相对位置，不能只复制 app/。
- 设置 `APP_ENV=staging`，明确 `BUILD_ID`，保持 `AUTH_MODE=demo_fixture`、`ALLOW_PERSONAL_UPLOADS=false`、`MCP_REQUIRE_AUTH=true`。
- `MCP_PUBLIC_URL` 必须是实际 HTTPS 完整路径，路径与 `MCP_PATH` 完全一致，不含查询令牌；例如配置路径为 `/mcp` 就不要填 `/mcp/` 或 `/healthz`。
- 同宿主反向代理可保留 loopback 监听；跨容器时再根据实际网络设置监听地址和持久卷，不能照搬宿主机 loopback。
- 代理 `/mcp` 到 MCP 进程、`/api/`、`/healthz`、`/readyz` 到 REST，保留 `Authorization`、外部 `Host`、MCP 会话/协议请求头；禁止缓存、响应缓冲和截断流，正确支持 POST/GET/DELETE。
- SDK 保留 Host/Origin 校验：允许本机及 `MCP_PUBLIC_URL` 中明确配置的公共地址；平台服务器请求可以不带 Origin，陌生 Origin 仍拒绝。不要通过关闭鉴权/来源检查解决代理问题。
- 当前前端跨域联调尚未验收；不要把“APP_ORIGIN 已填”误认为 CORS 已配置。前端接入时明确同源代理或经过验证的跨域方案。
- 不发布三维地图本地录入服务的写接口，不开放 SQLite 文件下载，不开启多实例。

这不是已经应用到服务器的代理配置。服务器类型确定后才生成对应的实际配置并实测。

CloudBase 探针的具体启动方式、端口和保护边界见 [`cloudbase-mcp/README.md`](cloudbase-mcp/README.md)，不能直接照搬这一节的双进程/SQLite 配置。

## 5. 云端独立探针

在安装了锁定依赖的客户端通过环境变量配置：

```dotenv
MCP_PROBE_URL=<实际 HTTPS MCP 地址>
MCP_PROBE_TOKEN=<通过保密方式注入，与服务器一致>
MCP_PROBE_EXPECTED_BUILD_ID=<本次服务器 BUILD_ID>
```

运行 `python backend/scripts/probe_mcp_url.py`。退出码必须为 0，报告 `ok/nonce_matches/build_id_matches/empty_nonce_rejected=true`，且缺/错令牌均 401。任何工具错误、结构错误、nonce/build 不符、超时/传输失败都以退出码 1 失败，不允许只看到一段 JSON 就认定通过。非本机 URL 必须 HTTPS；TLS 证书校验不关闭。

## 6. 学校平台验收（尚未执行）

在比赛指定空间的“插件 → 自定义插件 → 接入 MCP 插件”选择 Streamable HTTP，填写实际 `/mcp` HTTPS 地址和 Bearer 保密配置。发现 `health_probe` 后绑定主 Agent，发起随机 nonce 的真实调用，并与服务器 build_id、协议、方法/request_id 日志对照。

独立探针与本地测试均不能代替这一步。证据保存到 `docs/evidence/platform/D03-platform-probe.md`，通过前保持 `WAITING_HUMAN`。

平台探针通过后，下一阶段才接真实 `catalog.jinnan.json`、景点 REST/MCP 薄适配和公共地图同源数据；再决定数据库迁移和其他业务。
