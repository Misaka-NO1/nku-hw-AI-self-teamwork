# D06：完整只读演示 MCP 候选包本地验收

日期：2026-09-30；状态：LOCAL_PASS，不是云端或平台业务通过。

用户决定复用 nku-campus-mcp-probe，保留003回退。此选择只确定方案，当前没有发布、切流量、开启公网、改平台插件或数据库。原D任务书和冻结契约继续有效，D03平台探针通过不替代本阶段。

## 实现

独立 deploy/cloudbase-demo-readonly 包，保留 backend/app 与 contracts/fixtures/knowledge 的相对目录。62 个 ZIP 条目：41个Python源码、锁定依赖、Dockerfile、18项白名单资源和1个生成清单。资料正文仅仓库自创的公开示例笔记，无私人正文或真实学生记录。

新增启动门禁：非本机部署启用业务时必须指定清单；固定根目录与BUILD_ID精确一致，SHA256/长度/模块清单通过，否则拒绝启动。拒绝路径越界、额外Python模块、缺资源、重复清单和危险配置（个人上传/可信身份模式/持久数据库）。该检查提供资源完整性，不提供签名或外部身份认证。

Docker仅启动MCP，不运行REST、初始化业务库、迁移或挂载数据。强制demo_fixture / personal=false / sqlite:///:memory:。无commit/save/SQL/任意抓取工具。原探针包与默认业务开关保持不变。

## 实际检查

backend目录：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_local_stack.py
.\.venv\Scripts\python.exe scripts/check_domain_stack.py
.\.venv\Scripts\python.exe scripts/check_domain_bundle.py <候选ZIP绝对路径>
```

214项后端测试通过（本轮新增42项），一条第三方弃用警告。原探针回归及D06双进程HTTP回归均通过，默认工具仍仅health_probe；临时虚构任务幂等/重启持久化测试是本机REST测试，不是MCP包连接了数据库。

包检查拒绝未知ZIP条目后校验所有源码/资源SHA，解压到临时目录。MCP运行解压代码，REST对照运行仓库源码；七组正常、一组错误的结果一致（仅去掉各自request_id）。Bearer缺失/错误拒绝、nonce与BUILD_ID通过。另验证实际浏览器工作区不可通过服务令牌读取、修改的非夹具课表拒绝、公开正文确实可读、索引不冒充正文、私人/待授权资料不返回。无MCP数据库文件产生。

脚本明确 platform_verified=false、container_image_verified=false。本机没有Docker，Linux镜像/CloudBase构建、版本状态、学校工具发现/主Agent业务调用仍未验收。正确云端令牌没有被读取、打印或打包；本机测试只用一次性随机内存令牌。

生成包、构建号、源码提交、ZIP SHA、included_source_dirty记录由检查脚本实际输出，发布只使用源码已提交且dirty=false的最终包。未提交源码的中间包不可拿来宣称可追溯发布。最终包指纹另见本文件后续补充。

### 最终包实际指纹

- 包：`deploy/cloudbase-demo-readonly/dist/cloudbase-demo-readonly-20260930-cda01c67-114511.zip`（本机忽略文件，不提交ZIP）。
- BUILD_ID：`cloudbase-demo-readonly-20260930-cda01c67`。
- 包含源码提交：`cda01c6739d4104b6daf10769a7f8537284417d7`。
- ZIP SHA256：`a7576aba3820d2bbe3553d7b0574ced50cba19a1195283bd43a844bf64321116`。
- 条目62，included_source_dirty=false，source_sha_verified=true。
- 最终包再验ok=true：七组正常/一组错误一致、Bearer缺/错拒绝、nonce/build、浏览器工作区拒绝、非夹具拒绝、公开正文/私有过滤全部true；platform_verified=false、container_image_verified=false。

本补充是后续文档提交，未改变包内源码；包清单指向上述实际代码提交，不将补充文档的提交号冒充包源码。重建包会生成新的提交/指纹，应重新验收，不能复用此SHA。

## 下一步与回退

待明确批准再更新现有服务，保持公网/内网关闭、最小0/最大1和8080不变，保留003，不触及其他服务/业务库。旧Bearer曾暴露，用户选择不换；扩大只读工具范围后持有人可能读取公开虚构结果并消耗资源，仍不能访问个人工作区。公网联调/插件业务更新/主Agent发布分别需验收与相应授权。

回退优先关闭入口，切回003，恢复003对应BUILD_ID与仅探针配置（新开关false、清单路径空）；核对平台工具绑定，避免仍挂新增工具。无业务数据库迁移需撤销。操作说明见 deploy/cloudbase-demo-readonly/README.md。
