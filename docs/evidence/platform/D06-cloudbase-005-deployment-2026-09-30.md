# D06 CloudBase005兼容候选部署

日期：2026-09-30，北京时间。用户明确确认：部署兼容候选，允许新版本100%生效，保留004和003回退，公网保持关闭。本次不发布学校插件/主Agent、不开放公网、不改其他服务或数据库。

## 输入与提交

候选源码853d17dd3557d8872f0f78e5f13a12acadc514f1；BUILD_ID=cloudbase-demo-readonly-20260930-853d17dd-platform-compat。ZIP本机忽略目录cloudbase-demo-readonly-20260930-853d17dd-platform-compat-181928.zip；上传前重新核对SHA256=b2d3da2c78009492644c8a5f611f1a90d7211569a25ac0bc1be2edf9ac30c0cb，与本地验收一致，63条目，dirty=false。

仅更新上海环境sunner-wang-d8ght8niaaaea70b7的nku-campus-mcp-probe。提交前只读确认公网默认域名/内网默认地址关闭，版本004正常100%，003正常且保留；不删除任何版本。构建目标目录`.`、Dockerfile根文件、端口8080、实例min0/max1均保持。

配置仅改变BUILD_ID、新增MCP_ENABLE_PLATFORM_COMPAT_TOOLS=true；其余非秘密值逐项读回：staging、0.0.0.0/8080/mcp、MCP_REQUIRE_AUTH=true、MCP_ENABLE_DOMAIN_TOOLS=true、AUTH_MODE=demo_fixture、ALLOW_PERSONAL_UPLOADS=false、DATABASE_URL=sqlite:///:memory:、DOMAIN_BUNDLE_MANIFEST_PATH=/srv/campus/domain-bundle-manifest.json，MCP_PUBLIC_URL保留原默认HTTPS地址/mcp。令牌行完全跳过，不读取/截图/复制或修改原值。旧令牌风险仍未消除。

更新表单环境变量区带旧令牌明文，严禁整页文本/DOM/截图；只读标签、键名、指定非秘密行，上传控件定位也不读取HTML。提交前折叠并确认令牌输入不可见。版本发布方式确认框默认选择“发布版本并自动切换流量至新版本”，与本次授权一致，点击最终确定。

平台生成部署005/task2265500，开始时间2026-09-30 18:47:38。部署日志18:47:56解压完成，含新增platform_query.py与清单，进入镜像构建。

## 已核对的部署结果

18:48:43 Image pushed successfully；镜像tag=nku-campus-mcp-probe-005-20260930184745，digest=sha256:c08d1d5f421099f33debaf6b095976015aad76d84d1786df50030c6af2af5693。18:48:50 check_build_image:succ，随后check_eks_virtual_service:succ，部署详情状态正常。

005容器日志18:49:54实际显示StreamableHTTP session manager started、Application startup complete、Uvicorn监听0.0.0.0:8080；同刻平台内部GET /__tcb_probe__返回200。没有从公网发送这些请求，内部平台健康不代替Bearer/工具/学校业务验收。启动清单与13工具配置未导致拒绝启动；本轮没有远程tools/list或tools/call，不能把配置清单当真实远程发现结果。

服务配置页生效版本实际读回005正常/100%/1实例；部署版本列表005正常100%，004正常0实例，003正常0实例，旧版未删。服务入口再次逐项读回公网默认域名关闭、内网默认地址关闭。没有公网健康/MCP请求、流量回退或秘密变更。

005版本配置页逐行揭示并读回全部13项非秘密环境变量，构建号、业务/兼容开关true、鉴权true、固定清单路径、演示模式、个人上传false、sqlite内存库均匹配。令牌保持掩码，不点其显示按钮。端口8080、实例min0/max1、无存储挂载/私有网络、目标目录`.`、根Dockerfile再次确认。版本页“公网访问”（实例出站）显示关闭，此项沿用更新表单默认值、未主动切换；服务页该项曾与004版本页显示不同，不能把它与公网默认域名入口混同，后续有出站依赖时再核实。当前全部MCP夹具在本地，不据此扩大网络配置。

服务页出站项本轮仍显示开启，与005版本页关闭不同（此前004也如此），原因未证实，未改两处网络项。**入站默认域名已明确关闭**，与这个显示差异无混淆。

本机忽略目录截图（不提交Git，无令牌）：`deploy/cloudbase-demo-readonly/dist/D06-cloudbase-005-versions-20260930.png` 显示005正常100%、004/003仍正常保留；`D06-cloudbase-005-closed-20260930.png` 同屏显示005正常100%及公网默认域名/内网默认地址关闭、8080。最终服务页留在该只读状态供后续工作。

## 验收范围和后续

本次只做镜像构建/容器启动/配置/流量/关闭入口核验，不发公网健康或MCP请求。新增13工具的公网鉴权、学校query_json真实Input/Output尚未验证，不能由容器健康替代。学校插件仍为原团队测试版，兼容工具没有同步/发布，主Agent草稿绑定仍5个旧工具。

回退候选：004原7工具（恢复004 BUILD_ID与原清单、兼容开关false），或003仅探针（同时关闭业务/兼容开关、清空清单路径并恢复003构建号）；保留原鉴权和关闭入口，不实施回退、不删版本。实际回退和后续平台/公网联调均需按操作范围确认。

任务状态：CloudBase005镜像构建、容器启动及100%生效核验完成；D06兼容层LOCAL_PASS，学校端到端仍未通过。个人数据/生产数据库/工作流/知识库/前端和最终主Agent发布均不在此完成范围。下一步确认团队兼容插件配置/发布与获准公网联调，按真null/[]/中文/校验错误/身份隔离及两类未验工具的用例逐项签收。
