# D Agent 进度交接

## 2026-09-30 D06当前：公网按用户要求持续开放，五类主Agent通过，课表长JSON失败

用户明确“重新开启并保留”，开放时长改为直到用户要求关闭，不因本轮结束或登录过期自动关闭。既有默认HTTPS入口实际重开并保存读回，内网仍关闭；20:01健康200、无/错Bearer401。本轮仍005，没有部署/重建/同步/发布新版本。

补测主Agent时间冲突、空闲、培养方案、景点的实际Input/Output通过；加之前资料真null，共五类005业务有成功证据。课表实际输入1604/1605字符，正确夹具1606字符；两轮均损坏末尾括号，后端VALIDATION_ERROR正确拒绝，不能说校验成功或算法失败。应另评估确定性工作流传参，不能靠无意义部署或自动补括号掩盖。

新探针已有工具卡但原始取值输出截断待补读；未知方案请求已发但结果未验；主Agent错误/身份分支未完成。22:55后学校再次跳IAM，一键登录未恢复，待用户登录；**未关闭公网**。详见[持续入口补测记录](../evidence/platform/D06-005-main-retained-retest-2026-09-30.md)。下文“入口关闭/等待重新开启许可/仅一类通过”是早前阶段，不是当前最新状态。

## 2026-09-30 D06当前：005六兼容工具插件通过并发布，主Agent部分验收，入口已关闭

续步：用户随后重新登录并要求未通知不要关闭。已核对学校登录和七绑定/提示词持久化（保存19:41:31）；前一窗口已经按旧约定关闭，新的“重新开启并保持到用户要求关闭，包括本轮结束后”时长确认待回复，尚未重开。MA-C01另只读核对005审计19:42:08/tools-call/id3/协议2025-06-18/3.15ms/ok；仍不把一个通过推断全部D06完成。

本轮获准后仅开放既有服务进行联调，**没有再次部署**：005正常100%、004/003保留。外部健康200、无/错Bearer401通过；团队插件同步实际发现13工具，六兼容工具的query_json/String及输出根映射保存后逐一重开核验。16项真实业务正反例及新探针通过，补齐此前受null表单阻塞的课表校验/时间计划插件验收；真null、字面"null"、[]、中文、类型错误、重复键、未知资源和未绑定身份均按实际返回记录。

六原业务仅在学校插件禁用且配置/后端保留；团队测试插件发布成功，主Agent添加面板实际只显示六兼容+health_probe共7项。草稿换绑七工具、删除旧同义绑定、更新JSON传参和禁止编造提示词，刷新确认保存（19:41:30）。主Agent未发布、未上架、未新增KB/工作流/个人数据/数据库。

主Agent MA-C01实际工具Input topic:null原样保留，Output isError=false/ok=true、request_id=30d7651a-cc80-400a-8392-3afbd55effac；正文和索引正确区分。随后批量及改单项请求都在工具卡前失败，刷新跳IAM，一次一键登录仍未恢复，需用户重新登录；**其他五类业务/新探针的005主Agent验收与云端审计关联尚未完成**，不能签收全部D06或个人数据。已关闭并读回公网/内网入口，旧令牌未读取/修改。

详见[005平台本轮结果](../evidence/platform/D06-005-platform-compat-results-2026-09-30.md)。下一轮登录后不重复同步/重建/部署，核对现有草稿并补验实际Input/Output，再推进原计划工作流/KB/TasksPage与持久化。下文均是历史阶段记录，其中“学校未同步/未发布”“主Agent五工具”等不再是当前状态。

## 2026-09-30 D06最新：CloudBase005兼容版部署完成，入口关闭

用户明确批准候选部署/100%生效/保留004和003/公网关闭。已按候选SHA核对上传，005/task2265500于18:47:38提交，18:48:43镜像推送、18:49:54容器启动及平台内部健康200。服务页005正常100%，004/003正常保留；公网默认域名与内网默认地址均关闭。只改变BUILD_ID和新增兼容开关true，其余鉴权、演示、上传关闭/无持久库、8080/min0max1门禁逐项读回，令牌未读取/修改；未删除/回退任何版本。出站“公网访问”服务页/版本页仍显示不同，不混同入站关闭，也未擅改。

候选源码853d17dd3557d8872f0f78e5f13a12acadc514f1、build=cloudbase-demo-readonly-20260930-853d17dd-platform-compat；完整镜像/包指纹、启动/配置/流量和截图见[005部署证据](../evidence/platform/D06-cloudbase-005-deployment-2026-09-30.md)。本次没有公网tools/list/call，13工具是包清单与配置范围而非本轮真实远程发现；学校插件未同步/发布兼容工具，主Agent仍原5工具草稿且未发布。

状态：云构建/启动/生效已核验，本地兼容LOCAL_PASS；学校D06仍待端到端验收，不是PLATFORM_PASS_PERSONAL。下一步另确认团队兼容插件和公网联调，再验证query_json真null/[]/中文及两类未验工具。后续工作流/KB/前端/真实身份库及最终发布尚未完成。保留历史阶段记录，不再把下文“兼容未部署”当当前云状态。

## 2026-09-30 D06最新：主Agent实测有通过也有失败；query_json本地候选

本轮主Agent真实探针及景点/资料正文/空闲时间/培养方案重测、索引无正文、景点null/[]和3类错误分支通过；培养方案首次无工具编造结果，加执行优先约束后才真实调用通过。资料topic:null两次变为String "null"，第二次模型还误称传了null，因此全部D06仍未通过；两类课表/时间计划仍未平台验收。日志错误分支outcome=ok不代替业务isError/ok。最终关闭并读回公网/内网，004/100%/8080/min0max1/003回退不变。学校刷新跳IAM，新增提示词最终持久化读回仍待下次登录；主Agent未发布。

用户明确批准先做query_json兼容层本地测试、候选包，不据此部署。已增加默认关闭的6个只读platform_*工具，仅1个完整JSON字符串参数，仍按原契约校验/身份/算法/信封；拒绝重复键/非法值/大小深度，null和字面"null"不转换。原6工具、REST、Schema1.0.0及A/B/C算法不变，无写工具/个人数据/持久库。另修复本地审计wire dict的isError识别，不追改云端历史日志。最终275后端测试通过（兼容/清单53+审计8新增），解压包验收及正式指纹见本地记录；云端没有此兼容层，尚未发布兼容插件。保留用户无关未跟踪文件，不创建PR或合并main。

任务状态：兼容层LOCAL_PASS，整体平台D06仍待修复/复测，不是PLATFORM_PASS_PERSONAL。详细[实际调用/失败证据](../evidence/platform/D06-main-agent-runtime-2026-09-30.md)、[本地兼容候选](../evidence/platform/D06-query-json-local-2026-09-30.md)、[新增传输约定](../../contracts/platform-mcp-compat.md)。下一步单独确认同一服务更新/流量与团队兼容插件/临时公网，验实际Input/Output后再决定两类启用；KB/通知工作流/前端/真实身份数据库与最终发布仍后续，不跳过门禁。下文按阶段保留历史记录。

## 2026-09-30 D06最新：团队测试插件已发布，主Agent五工具草稿绑定保存

用户对带两类禁用配置的发布确认回复“发布吧”，点最终确认后平台返回发布成功。主Agent自定义插件添加列表实际显示5工具，展开只有四类已验证业务和health_probe，两类禁用工具不在可添加清单。按此前批准范围添加四业务，保留探针；刷新后技能表完整读回5个名称，草稿保存显示15:40:40。没有发布主Agent或上架，没有发主Agent业务调用；公网本轮未重开且再次读回关闭，云配置/代码/数据边界不变。

发布后插件列表四业务通过/启用、两类未通过/禁用。health_probe启用但列表Debug状态又显示未通过，与15:30:47真实成功和发布前通过不一致；原因未知，不能用列表回退推断实际调用失败，下一轮需复核。下一步主Agent实际业务/nullable/错误/隔离验收，不能把草稿绑定当平台业务完成。详细新证据追加于[主Agent执行记录](../evidence/platform/D06-main-agent-business-test-results-2026-09-30.md)，下文是历史阶段。

## 2026-09-30 D06续测：五类通过/两类禁用，发布确认仍列未通过工具

新登录插件页已找到。check_time_plan与validate_timetable成功禁用并读回保存，其余四业务启用/通过；health_probe本轮15:30:47真实Debug成功、nonce=d06-ma-20260930-probe-4c813e7af029、build_id=cloudbase-demo-readonly-20260930-cda01c67，完成保存后通过/启用。前置健康200、无/错Bearer401通过。

点发布仅打开确认框，仍警告两类未通过工具。无法保证发布配置仅含5类，原授权只发布已验证工具，因此未点最终确定；已先取消并关闭公网、读回公网/内网均关闭。向用户确认是否允许带两类禁用配置发布、草稿仍仅绑定5类，不把禁用等同发布排除，也不说禁用失效。新版插件/主Agent未发布，业务未绑定。确认框重新只读展示供用户决策。详情：[本轮执行记录](../evidence/platform/D06-main-agent-business-test-results-2026-09-30.md)。

## 2026-09-30 D06续步：主Agent验收范围获准，学校登录再次过期

用户明确批准本轮仅发布4类已通过业务+复测后的health_probe到团队测试插件，暂禁用未通过2类（保留配置），绑定主Agent草稿并测试固定虚构数据；只开同一服务测试入口，保留鉴权，结束/人工阻塞关闭；不发布主Agent/上架/接个人数据或数据库。

现场主Agent仍只有health_probe绑定。尝试禁用check_time_plan后出现Network Error，刷新跳学校IAM登录，保存状态未确认；未操作第二类、未发布或绑定，公网未开启并再次读回关闭。等待用户在插件页重新登录，回来先检查实际开关，不能重复盲切。已准备主Agent正向/索引无正文/显式null/错误/身份隔离用例与提示词候选，未应用线上。见[D06主Agent验收准备](../evidence/platform/D06-main-agent-business-test-plan-2026-09-30.md)。后续段落为之前阶段结果。

## 2026-09-30 D06最新：六工具输出映射保存，四类Debug通过，两类输入表单阻塞

用户重新登录后，重做景点兼容映射，随后同样处理其余五类工具；六类均点“完成”保存，并逐一重开输出定义确认structuredContent:Object不再含误推断的子类型。保留isError/content及实际完整业务JSON；只改学校平台映射，公共Schema1.0.0、A/B/C算法、云端004包和身份门禁不变。

本轮恢复后14:53:17前置检查健康200、无/错Bearer401。固定虚构数据的search_scenic_spots、audit_degree_progress、search_study_materials、query_free_time真实Debug通过；云端004工具审计均可对应。景点tags=[]另测通过；limit=0返回isError=true/ok=false/VALIDATION_ERROR且平台能解析，不算业务成功。网关此前SERVICE_FORBIDDEN后来未重现，具体原因仍未证明。

check_time_plan与validate_timetable的原始夹具被平台Debug表单对必填空值的“不能为空”挡住，没有发送新的业务请求；景点month=null也被同类限制挡住。输入Schema控制项不可编辑，没有擅自改公共契约、填假值或强制启用控件。此证据只定位GUI测试限制，不能证明主Agent运行时也拒绝null，也不能宣布两类算法失败。

最终公网/内网入口均关闭；不读取正确令牌、不改数据库/实例下限/其他服务。新版插件未发布、六业务工具未绑定主Agent，主Agent业务调用/工作流/知识库/生产身份/数据库仍待验收。同步工具可能覆盖手工兼容映射，必须再核对。health_probe编辑列表未通过不推翻此前主Agent真实探针通过记录，但下次发布前应按当前编辑版复测。下一步须明确发布与草稿绑定范围，再验主Agent真实业务调用；不能跳过两个nullable输入阻塞。详情：[D06兼容复测](../evidence/platform/D06-platform-output-compat-results-2026-09-30.md)。下文按阶段保留历史状态，不应当作当前结论。

## 2026-09-30 D06：输出兼容准备，保存未确认/网关403/学校登录过期

用户已批准仅改学校参数映射、不改共用契约/算法、先测不发布。景点工具表单保留structuredContent:Object根及isError/content，仅移除其误推断子字段类型；尚未通过实际Debug。其他5业务工具未改。

获准公网复测：14:43:28及14:44:13健康403，网关cbrgw明确SERVICE_FORBIDDEN，未进401/业务测试；控制台同时显示004正常1实例、入口开启。具体原因未证实，未改HTTP网关/其他路由/实例/数据库。随后关闭并核对公网/内网。

点击工具完成尝试保存后Network Error，刷新实际进入学校IAM登录，持久化未知，不声称修复成功。等待学校重新登录核对保存；先排查服务网关403，再验nullable/数组及失败保真。未发布新插件或主Agent。详细操作/风险/下一轮验收见 docs/evidence/platform/D06-platform-output-compat-preparation-2026-09-30.md。

## 2026-09-30 D06：004鉴权/主Agent探针通过，业务插件类型兼容阻塞

本轮已真实复测外部健康200、无/错Bearer401；主Agent health_probe原始输出isError=false，nonce回显正确、build_id=cloudbase-demo-readonly-20260930-cda01c67。14:28:24云端tools/call审计request_id=3、protocol2025-06-18、outcome=ok。首次30秒超时发生在0实例冷启动，新实例14:26:16才启动完成；未改最小0/最大1或其他配置。

学校campus-tools-dev编辑列表同步成功发现7工具，未发布新版本、未发布主Agent。固定景点Debug返回isError=false/ok=true和demo-spot-01，但平台校验structuredContent.error=null为非Object，标为调试失败。导入定义还将任意data显示为String、nullable calculation_version显示String。业务平台尚不能签收，不能修改统一信封来绕过。

已关闭并核对公网/内网入口；不读取正确令牌、不改数据库/算法/其他服务。等待用户确认只做平台参数映射兼容并测试，兼容方案尚未实施；其他5业务工具/主Agent业务/工作流/KB/生产身份/数据库仍待验收。详情及截图位置见 docs/evidence/platform/D06-cloudbase-004-platform-debug-2026-09-30.md；下文发布记录为历史阶段，不代表尚未做外部鉴权。

## 2026-09-30 D06：CloudBase 004发布和启动完成

用户明确批准更新既有服务、可能100%新版本流量、保留003回退、入口关闭。实际发布004（task2262849，12:47:41），12:48:40镜像推送、12:49:56容器启动和平台健康200。服务概览004正常100%；003正常、0实例且回退可用，未删除旧版。

非秘密门禁值已逐行核对：BUILD_ID=cloudbase-demo-readonly-20260930-cda01c67、业务开关true、固定清单路径、demo_fixture、个人上传false、sqlite:///:memory:。8080、最小0/最大1、无存储挂载不变。公网默认域名/内网默认地址均关闭；无学校插件/主Agent/业务库/其他服务变更。

状态：本地LOCAL_PASS；CloudBase镜像及启动完成；D06平台业务仍WAITING_HUMAN。正确云端令牌未用于测试，本轮无外部MCP验收。旧令牌在定位上传input时被隐藏表单HTML再次带入工具输出，已告知用户；后续仅按名称读配置、令牌行不读，不在Git/截图保存明文，不声称历史输出已删除。旧令牌保留且入口关闭。

004版本配置页与服务配置页的“公网访问”（出站）显示不同，未擅改/解释，后续实际外部依赖前核实；入口关闭状态单独核对无混淆。详细日志时间、镜像/ZIP指纹、安全事件与截图见 docs/evidence/platform/D06-cloudbase-004-deployment-2026-09-30.md。

下一步：另获公网联调授权后再验六类只读业务及学校主Agent，插件仍只有原health_probe、主Agent未发布。无回退实操/生产身份或数据库通过记录；回退时入口关闭并核对003对应配置。

## 2026-09-30 D06：完整只读候选包本地验收

任务状态：LOCAL_PASS；云端业务/平台业务尚未通过。用户已选择更新既有 nku-campus-mcp-probe，保留003回退，仅为方案决定，不是发布许可。

新增独立 cloudbase-demo-readonly 资源白名单包、启动清单/完整性/配置门禁、解压包真实HTTP验收脚本和42项测试；保持A/B/C算法、Schema1.0.0、既有路径/变量/字段不变。后端214项通过，旧探针和D06回归通过，包内六类业务读取与REST一致，服务令牌不能读浏览器工作区、非夹具课表拒绝、公开正文和私有过滤通过。

包只运行MCP，不运行REST/前端，不连接持久业务库，不提供写工具。MCP_ENABLE_DOMAIN_TOOLS=true和固定清单路径仅为新包配置，不擅自打开现有云端旧包开关。旧服务令牌不读取、不打印、不打包。

证据：docs/evidence/platform/D06-readonly-bundle-2026-09-30.md；发布/回退核对：deploy/cloudbase-demo-readonly/README.md。platform_verified=false、container_image_verified=false；无Docker，本机仅验解压代码/资源，云端构建待批准发布时验证。

最终候选源码cda01c6739d4104b6daf10769a7f8537284417d7；BUILD_ID=cloudbase-demo-readonly-20260930-cda01c67，62条目，dirty=false。ZIP指纹与解压最终再验结果见上述证据。不提交ZIP，且不把后续文档提交号写成包源码号。

未完成：更新云端版本、业务插件同步与学校主Agent实际调用、前端/通知工作流/TasksPage/KB、可信身份、生产数据库和最终发布。后续发布须单独确认实际流量范围，公网联调须另获授权；保持其他服务/数据库不变。原003保留回退，配置和平台绑定一并核对。

## 2026-09-30 D06：只读业务适配本地通过

任务状态：LOCAL_PASS（D06）；D03 真实平台探针通过见下文，不混用。

修改文件：core/domain_adapter.py、api/domains.py、mcp/domains.py、入口/配置/契约助手、test_domain_adapters.py、check_domain_stack.py；既有本机探针检查显式保持业务工具关闭。README、环境模板、GET 编码约定、查询夹具及 A/B/C 交接同步。未改 A/B/C 算法和页面、云端或学校平台。

REST/MCP 六类函数映射按冻结表，另提供既定 REST 详情/白名单下载。MCP 默认仅 health_probe；显式 MCP_ENABLE_DOMAIN_TOOLS=true 才加六个只读业务工具。无 commit/save/SQL/抓取/下载工具；create_task_draft/get_task_status 的 MCP 身份/写入策略待后续工作流阶段，不能宣称完整 D07/D08。

Schema=1.0.0，AUTH_MODE=demo_fixture，个人上传关闭。GET 搜索的一个 query JSON 参数已获用户确认。demo-workspace-01 是只读公开虚构资源；浏览器随机工作区仍按会话 owner 校验并读已确认资源，MCP 服务令牌不可访问。未确认通知草稿不占时间，degree 只解析固定引用。

测试：后端172项通过（D06新增34），一条第三方弃用警告；真实双进程HTTP/MCP：7组成功、1组错误一致，无/错Bearer拒绝、nonce/build通过，platform_verified=false。详见 docs/evidence/platform/D06-local-domain-adapters-2026-09-30.md。

未完成：六类业务工具的云端/平台验收、前端注入、工作流/TasksPage、KB、真实身份/数据库/发布。现有探针包缺业务资源，不能直接开启业务开关。回滚为关闭开关并撤销本轮薄适配/路由，无线上迁移。

下一步：按已授权固定 demo 范围准备完整业务资源与联调；真实身份方案仍待用户选择，不因本地通过自动发布。

## 2026-09-30 更新：CloudBase / NK-GeniOS 联调现状

**当前 D03：`PLATFORM_PASS_DEMO`。** 10:38 已由团队空间唯一主 Agent 真实完成 `campus-tools-dev / health_probe`；原始 Output 为 `isError=false`、nonce `97db23526c2d4b3ca998c27d217608fe` 精确匹配、build_id 正确、server_time 为 `2026-09-30T10:38:14+08:00`。CloudBase tools/call 审计 request_id=3、protocol_version=2025-06-18、outcome=ok；外部健康 200、无/错 Bearer 均 401。本轮按用户新授权连续开放，未在重试间切换，完成后已保存关闭公网，内网仍关闭。原始证据与不同耗时口径见 D03 记录。下方未通过描述均为历史。

下一步按计划推进 D06：把已交付的 A/B/C 领域函数接入统一 REST/MCP 薄适配，并验证同一夹具结果一致；未经回归的业务工具不发布到现有探针服务。D04/D05 本地门禁和事务结果不代表云端身份/数据库验收。个人上传、云端业务库、主 Agent 发布均未开启；真实景点数据源及涉及身份/数据库的方案仍按既定要求确认，不猜测。此次技术探针通过不代替赛事方对团队空间资格的认定。

10:35 最新续测：普通预览恢复后获准短时开放，但健康请求得到 `403`，没有发 MCP 鉴权 POST 或主 Agent 工具请求；已按当时约定关闭公网并核对内网关闭。可能存在保存/入口配置生效竞态，原因未证实；云端可见日志无该轮请求。用户随后要求联调期间连续开放，正在确认新的持续时长范围，未擅自重新开启。D03 仍未通过。

当前更新：10:27 的短时开放已完成外部健康 `200`、无令牌与错误 Bearer 均 `401` 的验收。主 Agent 随后立即 `Failed to fetch`，普通无工具对话也失败；立即关闭公网并核对公网、内网关闭，云端日志未见对应成功工具调用。用户重新登录后，普通预览实际回复“预览正常”（1.097s），说明当前普通对话恢复，不能据此签收 MCP。新的只读 nonce 请求已准备但未发送，等待该次公网重开确认。D03 继续 `WAITING_HUMAN`；正确令牌未被读取，后端鉴权未修改。详细证据见 D03 平台记录；前置检查脚本 8 项本地回归通过。

10:16–10:18 更新：用户确认后已短时开启并执行无正确令牌的外部健康检查；该 GET 在约 30.175 秒后传输失败，没有 HTTP 状态码。立即关闭公网，未发主 Agent 请求。容器日志随后核对 `003` 于 10:17:21 才启动完成，晚于外部检查超时。实例启动后的重开续测被自动审批审查拦截，要求针对新暴露窗口确认；已取消编辑，公网和内网入口关闭。等待该次重开确认，D03 未通过。完整脱敏证据见 D03 平台记录。

最新：学校平台已恢复登录并核对主 Agent 的 `health_probe` 绑定，新的 nonce 请求已填入预览框但未发送。启用默认公网入口的点击被自动审批审查拒绝，要求本次操作前重新确认；已取消未保存的设置编辑并核对公网、内网入口仍关闭。当前等待本次短时开放确认，D03 继续 `WAITING_HUMAN`。主 Agent 的最近前端错误日志暂未见 `ChunkLoadError`，不据此签收工具调用。

本轮用户回复“都登陆了，继续吧”后，已现场确认腾讯云登录成功：`003` 正常、100% 流量、0 实例，公网和内网入口关闭，端口 8080、最小 0/最大 1。学校编排页在当前浏览器重新打开后仍转到统一身份认证页，等待用户完成该页登录。没有改动云端配置。本地补齐 `prompts/main.md`，并新增 `backend/scripts/preflight_mcp_auth.py`：不读取正确令牌，仅检查 CloudBase 健康探针与无/错 Bearer 的 401；7 项针对性测试通过。脚本准备完成不等于远程或平台检查通过。

CloudBase 上海环境中的 `nku-campus-mcp-probe` 已运行部署 `003`，只读 `health_probe` 曾在 NK-GeniOS 插件 Debug 中真实成功调用（随机 nonce 回显一致、build_id 匹配），但**唯一主 Agent 尚无真实工具调用成功证据**。团队空间 `南开校园助手` 的测试 MCP 插件 `campus-tools-dev` 已按用户授权发布，主 Agent 草稿已绑定其唯一 `health_probe` 工具并经页面刷新核对；主 Agent 未发布，插件未上架市场。

三次短时公网联调的结果和脱敏证据见 `docs/evidence/platform/D03-platform-probe.md`。最新一轮公开健康探针为 `200`，无/错 Bearer 均为 `401`；主 Agent 预览消息提交后学校平台出现 `ChunkLoadError`，CloudBase 日志中没有对应 `health_probe` 调用。因此 D03 仍为 `WAITING_HUMAN`，不能记为 `PLATFORM_PASS_DEMO`。每轮结束均已关回 CloudBase 默认公网入口；内网入口也关闭。旧服务令牌此前暴露，用户已知风险并选择暂不轮换；不得在文档、日志或对话中记录其值。再次开放公网前须重新取得针对该次操作的确认。目前 NK-GeniOS 登录又已过期，等待用户自行登录以核对平台对话记录。

2026-09-30 学校平台重新登录后，公网保持关闭时主 Agent 普通预览已正常回复“预览正常”；这不是工具调用，`ChunkLoadError` 不能再视为持续存在，但 D03 仍未通过。腾讯云标签页又显示登录入口，未把先前的公网关闭记录说成本次现场核验。本地复测：后端 130 项测试通过；`check_local_stack.py` 的 REST/MCP、错误令牌 401、虚构任务重启持久化均通过，输出明确 `platform_verified=false`。

下一步：用户在当前内置浏览器重新看到腾讯云服务概览后，先只读核对公网状态；再次短时公网开放必须获得新确认，随后才可重试主 Agent 真实 nonce 工具调用。可并行继续 D06 的本地领域函数 REST/MCP 薄适配；景点数据源选择需用户明确，未经回归的业务工具不发布到 CloudBase 或平台，个人数据仍保持关闭。D04/D05 本地门禁和事务测试的既有结果不等于云端数据库/身份验收。

## 2026-09-28 更新：CloudBase 私有探针交接

用户提供的腾讯云交接文档报告：目前没有 CVM/轻量服务器；已有上海 CloudBase 环境 `sunner-wang-d8ght8niaaaea70b7`，其中 `nku-campus-mcp-probe` 私有 002 版曾部署并通过容器探针，但公网关闭、数据库未接入、NK-GeniOS 未真实调用。控制台已现场核对服务详情与版本配置，实际镜像源码及 MCP 调用仍未核实。现已收到一份早期 CloudBase 源码 ZIP 并与仓库候选版逐文件比较；它缺少云端配置与版本指纹，**不能声称仓库候选版与云端 002 源码相同**。

初版候选代码已推送到 `origin/codex/d-mcp-local-readiness`（`b91ca41`）；后续现场核对与更正记录也在该分支。未创建 PR、未合并主分支。首次打开控制台曾被导向登录页，用户之后登录，现场结果如下。

用户登录后只读核对 CloudBase 云托管服务列表：`nku-campus-mcp-probe` 显示**已暂停**，公网访问**不允许**；随后进入详情页核查，见下段。没有恢复或更新服务。此现场状态与较早的交接描述须分开记录，不能称云端探针目前可用。

后续已打开服务详情：002 版**正常**、100% 流量、0 个实例，端口 8080；运行模式允许最小 0、最大 1，符合空闲自动缩容。默认公网、内网入口都关闭，也没有自定义域名。可见环境变量仅有 `APP_ENV`、`MCP_HOST`、`MCP_PORT`、`MCP_PATH`、`BUILD_ID`，值隐藏；未见 Bearer 相关配置。用户回复“恢复吧”后，未将最小实例擅自改为 1：这会持续计费且不能提供外部联调入口。用户随后选择先准备安全接入，保持实例下限 0，并同意默认域名只用于联调。没有云端配置变更，平台仍未通过。

本地变更：MCP 服务增加仅 `GET /__tcb_probe__` 返回 `ok` 的 CloudBase 健康检查，不更改工具名或业务 Schema；测试确认 `/mcp` 和错误方法/路径仍需 Bearer。新增 CloudBase Python 3.12/8080 Dockerfile 与操作说明，未连接已有 PostgreSQL，也不在容器中保存 SQLite。没有 Docker，本机镜像构建待云端或具备 Docker 的环境验证。

本地安全准备：非本机 MCP 监听现在即使 `APP_ENV` 被覆盖为 development/test，也强制 HTTPS 地址与 Bearer；见 `deploy/cloudbase-mcp/SAFE-ACCESS-CHECKLIST.md`。更新后的候选 ZIP 已在本机生成并逐项核对。`deploy/Test-Local.ps1` 再次通过：后端 126 项测试（1 条第三方弃用警告），真实本地 MCP 初始化、发现、nonce、错误令牌拒绝、错误构建号失败及虚构任务重启持久化均通过。平台端到端状态仍 `WAITING_HUMAN`。

下一步：待用户明确批准更新 `nku-campus-mcp-probe` 后，按准备单核对新候选版本、令牌、云端环境变量及流量策略；公开默认域名须另行批准，绝不把旧 002 直接公开。之后经独立 HTTPS 探针验证，最后在比赛空间让主 Agent 真调用。业务存储后续选独立 PostgreSQL 或用户确认的隔离实例与迁移方案，绝不改写现有应用的表/权限。

## 2026-09-27 历史更新：自建后端第一阶段

## 2026-09-27 更新：自建后端第一阶段

任务状态：本地 `LOCAL_PASS`；云端/学校平台 `WAITING_HUMAN`。检查基线为最新拉取的 main `a5ada91`，实现分支 `codex/d-mcp-local-readiness`。用户同意先搭建、准备测试，并表示已有云服务器，服务器详情尚待提供。

本次修改：严格 MCP 探针、公共 Host/Origin 白名单、REST 启动配置校验、双进程隔离测试脚本、预发布模板和测试手册。没有更改 A/B/C 算法、公共前端、业务 Schema、REST 路径或 MCP 工具名；仍只暴露 `health_probe`。

新增测试客户端配置：`MCP_PROBE_EXPECTED_BUILD_ID`。Schema：`1.0.0`；`AUTH_MODE=demo_fixture`，个人上传关闭。

实际测试：119 项后端测试通过；官方客户端真实本机 HTTP 初始化、发现、调用及缺/错令牌 401、错误 build_id 退出1、空 nonce 拒绝通过；固定虚构任务确认/幂等/重启持久化通过，SQLite integrity_check=ok。运行命令见 `deploy/PREPARE-AND-TEST.md`，完整证据见 `docs/evidence/platform/D03-local-readiness-2026-09-27.md`。

整站回归：前端23项、扩展25项、import-core38项通过，加后端共205项；前端生产构建、扩展构建及 B 两包类型检查通过。pnpm12旧配置警告、Ajv日期格式警告仍记录在证据中；没有修改前端依赖版本或锁文件。独立三维地图浏览器交互和平台回归不在此通过数量中。

当前 A/B/C 领域函数已有交付（下方早期记录的“尚未交付”不再代表现状）。真实景点目录已校验，但景点 REST/MCP 尚未注册，公共站地图/复习/待办还为占位；下一步先完成服务器与平台探针，再推进领域薄适配和公共前端同源数据联调。

平台真实调用证据：无。待提供服务器系统、运行方式、现有业务、域名/HTTPS、持久目录及授权；主 Agent 必须在比赛指定空间验收。没有远程部署、未迁移数据、不需要回滚线上服务；撤销本轮文件变更即可恢复本轮前代码，旧客户端探针命令需与对应版本说明配套。

## 2026-09-20 历史交接（保留，非最新全项目状态）

任务状态：本地 `LOCAL_PASS`；平台 `WAITING_HUMAN`

修改文件：`backend/` 后端、MCP、SQLite 事务与写入工作流，`contracts/`、D 所有的 `fixtures/`、`deploy/`、本文件及平台证据模板。

REST 路由：

- `GET /healthz`
- `GET /readyz`
- `POST /api/v1/demo/workspaces`
- `POST /api/v1/import-tickets`
- `POST /api/v1/schedules/import-drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/confirmations`
- `POST /api/v1/schedules/commit`
- `GET /api/v1/schedules/current`
- `POST /api/v1/tasks/drafts`
- `POST /api/v1/tasks/commit`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`

MCP 工具：

- `health_probe(nonce)`

领域函数映射：第一轮 D01–D03 不注册 A/B/C 业务函数，避免领域实现尚未交付时发布假工具。

Schema 版本：`1.0.0`

测试命令：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\probe_mcp.py
```

测试实际结果：23 项通过。D01–D03 包含健康检查、统一信封、共享 Schema、官方 MCP 客户端发现/调用、空 nonce、Bearer 认证及真实本地 Streamable HTTP。D04/D05 另验证：通知和课表任意伪 demo 数据拒绝、CSRF、一次性导入票据只存 hash、票据过期/重放、跨浏览器 owner 隔离、旧 revision、篡改/过期确认回执、草稿/提交幂等和工作区清理。当前 Windows 工作区路径含中文，pytest 缓存插件会在该运行时的临时目录创建阶段卡住，因此项目配置明确关闭 cacheprovider；测试本身不受影响。

平台真实证据：无。原因和待填字段见 `docs/evidence/platform/D03-platform-probe.md`。

当前 `AUTH_MODE`：`demo_fixture`

未完成事项：用户已选择暂不部署，因此真实 HTTPS、NK-GeniOS 插件配置、平台协议协商记录和主 Agent 真实 nonce 调用继续保持 `WAITING_HUMAN`。A/B/C 领域服务尚未交付，不注册相应 REST/MCP 假工具。

回滚方式：本轮未执行数据库迁移或平台变更。代码可回滚到本分支前一提交；环境变量中的服务令牌应在回滚或泄露怀疑时轮换。后续已有平台配置后，必须先解除主 Agent 插件绑定，再回滚服务版本，避免旧 Schema 对接新服务。
