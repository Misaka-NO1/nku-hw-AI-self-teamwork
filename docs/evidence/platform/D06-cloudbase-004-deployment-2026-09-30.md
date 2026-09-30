# D06：CloudBase 004 只读演示版发布记录

后续更新：004外部鉴权与主Agent探针已通过，编辑列表发现7工具；固定景点实际返回成功，但学校平台输出类型校验不兼容，未发布新插件/主Agent，入口已关闭。见 [后续平台联调记录](D06-cloudbase-004-platform-debug-2026-09-30.md)。下文是发布阶段的历史记录。

日期：2026-09-30（北京时间）。任务状态：本地LOCAL_PASS；CloudBase构建、发布和容器启动完成；学校平台业务验收仍WAITING_HUMAN。不把私有容器健康写成PLATFORM_PASS_DEMO。

## 授权与发布对象

用户针对更新现有 nku-campus-mcp-probe、可能100%新版本流量、保留003回退、保持公网/内网入口关闭的明确问题回复“确认”。本轮只更新此服务，没有改其他服务、业务数据库、学校插件或主Agent，没有开放入口。

环境：sunner-wang-d8ght8niaaaea70b7，既有上海CloudBase环境。发布前现场核对003正常、100%流量、默认公网/内网入口关闭、8080、最小0/最大1、无存储挂载。

上传已经独立解压验收的 cloudbase-demo-readonly-20260930-cda01c67-114511.zip，SHA256=a7576aba3820d2bbe3553d7b0574ced50cba19a1195283bd43a844bf64321116；源码cda01c6739d4104b6daf10769a7f8537284417d7，62条目、included_source_dirty=false。构建上下文“.”、Dockerfile根文件。

平台对话框为“发布版本并自动切换流量至新版本”（个人版手动切换为标准版选项），按已批准范围确认。实际新版本004、taskId=2262849、开始时间12:47:41。

## 实际构建与启动证据

- 12:47:55：ZIP解压，含源码、两个Schema、13个虚构夹具和3项知识资源、根清单。
- 12:48:26：Docker镜像完成，Python3.12-slim-bookworm；依赖锁定清单安装成功，pywin32按Linux条件跳过。只启动MCP。
- 12:48:40：镜像推送成功，标签nku-campus-mcp-probe-004-20260930124744，清单digest=`sha256:789d521db680770131fe6acba5017d7a0e606585fc497a9cdb96e10251a5551e`。
- 12:48:49：check_build_image=succ；12:48:50：check_eks_virtual_service=succ。
- 12:49:56：004容器日志明确Application startup complete、StreamableHTTP session manager started、Uvicorn监听0.0.0.0:8080、GET /__tcb_probe__ 200。
- 服务概览004“正常”、100%流量、1个实例；部署版本列表003仍“正常”、0实例、流量“-”，回退按钮启用。001/002亦未删除。没有为测试切回003。

容器成功启动与源码的fail-closed清单检查相符，但不代表每个业务工具已经真实从学校平台调用。镜像构建的AUTH_MODE/MCP_REQUIRE_AUTH字段名触发Docker SecretsUsedInArgOrEnv警告；对应Dockerfile值只是demo_fixture/true，不含服务令牌。pip构建root安装、useradd的UID范围提示等构建警告保留，运行用户仍为campus（10001），不因警告去掉门禁。

## 非秘密配置核对

仅逐行展开以下非秘密字段，未点“全部展示”或令牌行：

| 配置 | 004实际值 |
|---|---|
| BUILD_ID | cloudbase-demo-readonly-20260930-cda01c67 |
| MCP_REQUIRE_AUTH | true |
| MCP_ENABLE_DOMAIN_TOOLS | true |
| DOMAIN_BUNDLE_MANIFEST_PATH | /srv/campus/domain-bundle-manifest.json |
| DATABASE_URL | sqlite:///:memory: |
| AUTH_MODE | demo_fixture |
| ALLOW_PERSONAL_UPLOADS | false |

服务概览另确认端口8080、cpu1核/内存2G、最小0/最大1、无持久存储/VPC、会话亲和关闭。公网默认域名和内网默认地址均关闭，默认域名标注“已关闭公网访问”。

注意出站展示差异：004“版本配置”页将公网访问（容器出站）显示关闭，但“服务配置”页显示开启、与发布前服务页相同。本轮没有操作出站开关，不臆断差异原因或实际网络能力；公开入口是否关闭以独立的“公网默认域名/内网默认地址”核对为准。当前只读夹具业务不依赖出站，后续引入外部请求前需核实此差异。

## 凭证读取事件与补救

定位上传控件时，错误地读取了所有input的HTML，页面折叠区域仍包含旧MCP_SERVICE_TOKEN明文，导致旧令牌再次进入本会话工具输出。已立即向用户说明，不在文档中记录其值，不再读取该行，不将工具输出/原始表单截图提交到Git。后续编辑检查只返回变量名称，对令牌分支直接输出“保留，不读取”；非秘密字段单行核对。用户此前已知旧令牌暴露并选择不轮换，本轮按原方案保留；入口始终关闭。此次事件不能声称令牌从未被读取或历史输出已删除。后续公开联调前仍须说明旧令牌持有人可调用演示工具并消耗资源。

## 页面证据与未完成

本机忽略文件（截图中令牌掩码，不含明文）：

- deploy/cloudbase-demo-readonly/dist/D06-004-service-closed-20260930.png：004生效、默认域名/公网及内网入口关闭、配置范围。
- deploy/cloudbase-demo-readonly/dist/D06-004-003-rollback-20260930.png：004正常100%、003保留。

本轮container_image_verified=true、container_startup_verified=true；platform_business_verified=false、external_mcp_auth_verified=false。本轮没有外部POST /mcp或正确云端令牌调用。D03此前003探针通过的历史证据保留，不冒充004业务通过。

下一步需针对新版本及旧令牌风险另获公网联调授权：先外部健康与缺/错Bearer401，再正确鉴权发现七个工具与固定案例，最后学校插件业务同步/主Agent真实调用。插件campus-tools-dev仍只有原health_probe；不自动发布六类业务工具或主Agent。工作流、TasksPage、KB、可信身份和生产数据库仍分别待验收。

回退：入口保持关闭，使用保留003的回退功能，核对003的版本配置/BUILD_ID及平台绑定，仅探针模式；没有数据库迁移需要撤销。未实际执行回退，不能声称回退演练通过。
