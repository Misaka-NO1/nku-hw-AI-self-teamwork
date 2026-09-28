# CloudBase Run：第一阶段 MCP 探针

此目录是针对仓库当前后端重建的、可审核的探针部署包。用户已提供一份早期 CloudBase 源码压缩包；逐文件核对见 `docs/evidence/platform/D03-platform-probe.md`。它没有部署版本指纹或云端配置，**不能据此声称本目录与云端 `002` 完全一致**；推送或重部署前仍须只读核对控制台。本目录不含密钥、数据库连接、学生数据、景点资产或前端。

2026-09-28 已现场核对 002 状态与默认域名，后续只准备安全接入，不修改云端；具体配置与发布门槛见 [安全接入准备单](SAFE-ACCESS-CHECKLIST.md)。

## 镜像内容和入口

在**仓库根目录**执行（有 Docker 的机器）：

```text
docker build -f deploy/cloudbase-mcp/Dockerfile -t nku-campus-mcp-probe:local .
```

镜像使用 Python 3.12、锁定 `backend/requirements.lock`，只复制 `backend/app`；以非 root 用户运行 `python -m app.mcp.http`，监听 `0.0.0.0:8080`。镜像默认 `APP_ENV=staging`、`MCP_REQUIRE_AUTH=true`，未安全配置公网 URL 或令牌就拒绝启动，不会意外以开发模式开放 MCP。本机尚无 Docker，因此此 Dockerfile **尚未进行本机镜像构建验证**。云端构建也必须另记真实结果。

如在 CloudBase 控制台使用“上传源码压缩包”，在仓库根目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File deploy/cloudbase-mcp/Build-Package.ps1`。脚本生成忽略提交的 `dist/` ZIP，根目录放 `Dockerfile`，仅包含锁定依赖与 `backend/app` 的 Python 源码；输出 SHA-256 供上传时核对。生成包不等于已经构建或部署。

健康探针 `GET /__tcb_probe__` 只返回 `ok`，不需要 Bearer；仅这个**精确方法和路径**豁免认证，`POST /__tcb_probe__` 和 `/mcp` 仍由鉴权保护。该路径不会调用任何 MCP 工具，也不查询数据库。

本镜像仅用于 D03 连通性验证，不承载 REST、课表、待办或 SQLite 持久数据。CloudBase 实例可能缩到 0，容器临时文件不可当成业务数据库。后续业务后端的数据库方案必须单独设计并测试；不得顺手连接或修改环境里已有应用的 PostgreSQL 业务表。

## 部署前设置

仅在用户授权更新 `nku-campus-mcp-probe` 后，根据云端现有服务配置填写：

- 容器端口：`8080`；服务名、环境 ID 与交接文档核对。
- `APP_ENV=staging`，`BUILD_ID` 取**新的**可追溯版本，不重用旧版 `002` 标识。
- `MCP_HOST=0.0.0.0`、`MCP_PORT=8080`、`MCP_PATH=/mcp`。
- `MCP_REQUIRE_AUTH=true`；`MCP_SERVICE_TOKEN` 使用云端保密配置注入的随机令牌，不写在部署包、日志或截图中。
- `MCP_PUBLIC_URL` 填实际 HTTPS 完整 `/mcp` 地址，需与服务对外域名和路径一致。公网仍关闭时可先配置计划使用的地址，但不得声称已可外部访问。
- `AUTH_MODE=demo_fixture`、`ALLOW_PERSONAL_UPLOADS=false`。
- 第一阶段不配置数据库或直接复用已有 PostgreSQL。不要打开任何已有数据库端口。

`MCP_PUBLIC_URL`、Bearer 开关和令牌在 staging 下缺失时服务应拒绝启动；非本机 MCP 监听即使被云端环境变量覆盖成 development/test，也必须满足同样门槛，不能绕过鉴权上线。

## 验收与记录

先确认新版本构建、实例运行、`GET /__tcb_probe__` 返回 `200 ok`。仅这一项**不**代表 MCP 联通。若获准开启公网，先用无令牌和错误令牌访问 `/mcp`，必须 401；然后安全注入正确令牌，使用 `backend/scripts/probe_mcp_url.py` 做官方 SDK 初始化、工具发现、随机 nonce 与 build_id 校验。再在比赛指定的 NK-GeniOS 空间中配置 Streamable HTTP + Bearer，让主 Agent 真实调用一次。结果写入 `docs/evidence/platform/D03-platform-probe.md`。

默认 CloudBase 域名仅用于此开发测试。[CloudBase 公网访问文档](https://docs.cloudbase.net/run/deploy/networking/public)说明该域名无内建鉴权，[腾讯云创建服务文档](https://cloud.tencent.com/document/product/1243/77191)说明默认域名不保证生产稳定性、容器无法持久保存文件，因此必须依赖服务自身 Bearer 保护；正式演示是否需自定义域名，以实际平台可达性和发布要求决定。

未验证前不要更改环境中其他应用、数据库、权限或已有 002 的流量。服务更新需保存旧版本号与回退入口，由云端版本/流量配置回滚，不能靠删除业务数据回滚。
