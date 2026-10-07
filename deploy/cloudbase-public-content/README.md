# 公开景点与复习资料：主 Agent 的只读数据服务

NK-GeniOS 是对话入口。这个服务不是另一套 Agent：MCP 提供检索结果，工具页展示地图、实景照片和原 PDF；二者读取同一批数据。

## 数据和隔离

- 景点 PR #6：34 点、91 张已授权照片、完成版模型与 36 条道路；版本 `jinnan-2026-09-26`。历史花期不是实时花况。
- 资料 PR #7：33 份公开 PDF，SQLite 只读全文索引；版本 `y1-070600fb47f92e70`。含个人信息的一份资料不入包、不允许下载。
- 课程 ID 为 A 的暂定内部标识，不代表教务正式课程号；上下学期必须先消歧。
- 复习默认交付原文件：按课程、上下学期及主题检索，直接返回 `download_url`、`file_name`、`file_format`。现有 33 份是 PDF，不能冒称 PPT；不默认总结、讲解或调用 StudyAnswer。用户明确请求讲解才使用正文并引用真实页码。文本提取/OCR 未逐页人工校对。
- 赏景采用“兴趣/花种 → 具体点位 → 地图位置”：泛赏花查询 `flower`、`month=null`、`limit=20`，从本次结果提取完整花种菜单；建筑用 `architecture`，秋景用 `foliage`，湖边用 `waterside`。用户已点名地点则跳过选项。地图标记不是 GPS 或实时步行导航。
- 不需要 CloudBase API Key。MCP 使用本服务专用 Bearer；公开内容 REST 和展示页不需要个人账户。
- 无个人资料上传、任务提交、任意 SQL 或任意 URL 抓取。旧 MCP 005 与 Tasks 003 保留。

## 构建

先在 `frontend` 按锁定依赖构建，设置 `VITE_API_BASE_URL=/`、`VITE_PUBLIC_CONTENT_ONLY=true`；返回 Agent 地址只填已审核的实际平台入口。

```powershell
# 仓库根目录；每次使用全新的包名，不覆盖旧证据
.\backend\.venv\Scripts\python.exe backend/scripts/build_public_content_package.py --name cloudbase-public-content-20261002-r3
```

生成 `dist/<包名>.zip` 及 SHA256。启动逐文件检查 hash、大小、路径和额外文件；打包前检查地图相对模块依赖，不能把 `.env`、私有 PDF、编辑服务器或原始照片混入。
候选包记录实际源 HEAD、数据 main commit 和未提交源码状态，不冒称已提交版本。

## CloudBase 配置

服务 `nku-campus-public-content`，8080、0.25 核/0.5G、实例 0–1；不启用数据库 API Key 注入。

| 配置项 | 值 |
| --- | --- |
| APP_ENV | staging |
| AUTH_MODE | demo_fixture（个人身份仍关闭；公开真实目录另行启用） |
| PUBLIC_CATALOG_PROFILE | published |
| ALLOW_PERSONAL_UPLOADS | false |
| DATABASE_URL | sqlite:///:memory:（业务工作区不持久化；资料索引是独立只读快照） |
| BUILD_ID | 与包清单完全相同 |
| DOMAIN_BUNDLE_MANIFEST_PATH | /srv/campus/public-content-manifest.json |
| MCP_HOST / MCP_PORT / MCP_PATH | 0.0.0.0 / 8080 / /mcp |
| MCP_REQUIRE_AUTH | true |
| MCP_ENABLE_DOMAIN_TOOLS / MCP_ENABLE_PLATFORM_COMPAT_TOOLS | true / true |
| APP_ORIGIN | 控制台实际 HTTPS 服务域名 |
| MCP_PUBLIC_URL | 实际 HTTPS 服务域名 + /mcp |
| MCP_SERVICE_TOKEN | 由负责人直接填写的新随机令牌，禁止进聊天/Git/前端 |

`healthz` 正常只证明启动和目录可读；不能替代 MCP 鉴权、插件 Debug、主 Agent 调用和照片/PDF 实测。公网测试域名提醒由负责人本人处理；不更改浏览器安全设置绕过。

## 学校绑定与验收

创建团队隔离插件，仅绑定新服务的 `platform_search_scenic_spots` 与 `platform_search_study_materials` 到主 Agent 草稿。二者仍采用契约的 `query_json` 字符串参数，根输出映射不变；资料项需保留新增的 `download_url`、`file_name`、`file_format` 三个字段，不能仅映射预览链接。
旧插件的两个同义 A 工具解绑以免歧义，旧时间/培养方案/课表工作流保持。令牌由负责人在学校插件输入，不上传 CloudBase service_role 密钥。

验收顺序：真实 nonce/build → 两个只读查询 → 未知/私有资源拒绝 → Agent 自然语言检索 → 实景与原 PDF 链接 → 不实时花况、不伪造今年考试范围。全部记录实际 request_id、数据版本、脱敏截图。
绑定新服务后才更新草稿数据说明；未验收不发布主 Agent或宣称个人数据接通。

## 回滚和更新

同一隔离服务新建版本，旧版本保留。失败时先解除对应草稿工具绑定，不把故障自动替换成假 demo 答案。
内容更新重新导出 A 的公开索引、打新包、逐项验收；这个容器不作为可写数据库或备份唯一来源。
资料 SQLite/PDF 与照片由主仓库及授权文件保存；生产可写个人数据库、可信身份、双账号隔离和持久备份需独立验收。
