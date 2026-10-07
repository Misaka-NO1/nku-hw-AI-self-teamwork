# D06：学校插件输出兼容复测结果

日期：2026-09-30，北京时间。阶段结论：四类业务在插件Debug中通过；六类输出兼容映射持久化确认；两类必填空值的GUI输入仍阻塞。不是全部D06平台验收通过，不是主Agent六业务验收或新版插件发布。

## 范围、恢复及结束状态

沿用用户授权：仅调整学校平台参数映射，保持共用接口/算法不变，先测不发布；同一nku-campus-mcp-probe默认HTTPS入口本轮持续开放，结束或人工阻塞关闭。学校平台使用用户已经填入的保密配置，不读取正确令牌。旧令牌暴露风险仍存在，未声称轮换或删除历史工具输出。

14:43–14:44的网关403及学校登录过期是此前阶段，见[历史准备记录](D06-platform-output-compat-preparation-2026-09-30.md)。用户重新登录后重开景点定义发现子项仍在，证明之前过期保存没有持久化；重新调整并保存，再重开确认。获准范围内恢复测试入口，14:53:17前置验收：

| 项目 | HTTP | 客户端耗时 |
| --- | --- | --- |
| GET /__tcb_probe__ | 200 | 292.39ms |
| 无Bearer POST /mcp | 401 | 67.13ms |
| 随机错误Bearer POST /mcp | 401 | 172.69ms |

前置脚本不使用正确令牌。随后测试期间保持入口开启，结束一次关闭并核对公网/内网均关闭。未修改HTTP网关路由、其他服务、实例下限、数据库、凭据或后端代码。此前SERVICE_FORBIDDEN未再出现，具体原因未知，不宣称定位为欠费、权限、传播竞态或冷启动。

云端仍为004、build_id=cloudbase-demo-readonly-20260930-cda01c67，包源码cda01c6739d4104b6daf10769a7f8537284417d7。003回退版保留，未执行回退。新版插件和主Agent均未发布，没有主Agent业务绑定/调用证据。

## 只修改平台输出映射

六业务工具均完成以下编辑：保留isError:Boolean、content:Array<Object>及type/text；structuredContent保留Object根，不细分其data/error/meta/ok内部子类型。点“完成”保存工具编辑配置，最后逐一重开六工具输出定义，根内非空字段名均只有structuredContent，确认不是仅表单暂存。此操作不是发布。

平台误导入的nullable/Any子类型声明移除，**服务器实际字段没有删除**。服务器完整structuredContent与content.text业务JSON不变，成功error=null、错误data=null、数组、meta及warnings仍返回。公共Schema1.0.0、服务端outputSchema、算法、工具名、路径和身份边界均未改变。

代价：学校平台不再检查这些内部子项的具体类型；正确性仍依靠服务端严格契约/回归，以及对实际业务JSON的成功、失败和边界检查，不可只看绿色“调试成功”。“同步工具”可能覆盖此手工映射，重新同步后必须按本节复核。

## 四类正向Debug实证

全部使用仓库公开固定虚构数据，无学生账号/成绩/课表上传。下表request_id是业务信封UUID，不是MCP JSON-RPC id。

| 工具 | 实际输入摘要 | 实际业务结果 | 业务request_id |
| --- | --- | --- | --- |
| search_scenic_spots | demo-campus，tags=[flower]，month=3，limit=5 | ok=true/isError=false，data数组含demo-spot-01，error=null | 1d27029c-f0f7-489b-9fc5-6a90a503b6df |
| audit_degree_progress | demo-workspace-01/demo-cs-plan-v1/demo-transcript-01 | ok=true/error=null，status=incomplete，保留DEMO_DATA/NOT_GRADUATION_DECISION | cb6cbd37-7879-40c8-8610-4e451140e519 |
| search_study_materials | course_id=demo-CS101，topic=递归，limit=5 | ok=true/error=null，demo-note-01正文可用，返回真实自编资料摘录与锚点、page_label=null | 8ffd8a61-9741-4d87-8f4c-1f642a517622 |
| query_free_time | demo-workspace-01，2026-09-21 08:00–12:00+08:00，min_minutes=30，前后缓冲0 | ok=true/error=null，09:40–10:10的30分钟空档；覆盖selected_weeks/[3]/unknown，保留DEMO_DATA/calendar_not_official | f002a7a4-bd09-4e1c-bc06-2de16993f64c |

资料证据引用：knowledge/study/sources/demo-note-01.md#递归的两个必要部分，以及#数组下标检查。培养方案结果不是官方毕业判断；空档结果不是实时学生课表。未在本轮平台独立验证topic=null或INDEX_ONLY资料，不扩大验收结论。

### 景点边界及错误保真

- tags=[]、month=3、limit=5：实际Request为空数组，成功返回数组结果，error=null，DEMO_DATA/NOT_REALTIME保留；request_id=e25f9628-82e9-41a0-8b82-775e8eba560d。
- limit=0（其余为正向输入）：实际Request为0，平台能解析，但isError=true、ok=false、data=null、error.code=VALIDATION_ERROR、retryable=false；field_errors含limit/minimum，meta.data_version及calculation_version=null。request_id=bea15db5-3c4d-4ff7-b909-e0ab996eee9b。绿色“调试成功”只说明运输/解析通过，**不算业务成功**。
- month=null：代码编辑确认后GUI将month呈现为空必填项，Debug显示“不能为空”，没有新的Request/返回；仍显示的旧绿勾和旧结果不能记作此次空值通过。未改为0、假月份或省略字段。

## 两类输入GUI阻塞

| 工具 | 所用原始夹具 | 阻塞 |
| --- | --- | --- |
| check_time_plan | fixtures/time-event-query.demo.json | event.date、due、estimated_minutes、earliest_start等合法显式null被表单必填验证拒绝 |
| validate_timetable | fixtures/timetable.demo.json | 三门课程的course_code、teacher_display等合法null被表单必填验证拒绝 |

两类输出映射均已保存并重开确认，但原始夹具未通过Debug输入表单，未发送新的业务调用。相应输入类型/必填配置控件禁用；没有强制解除禁用、操作内部状态或修改公共Schema，更没有填假值制造通过。此证据定位的是平台GUI测试限制，尚不能推论主Agent/工作流运行时一定拒绝null。不能说两类算法错误，也不能签收两类平台端到端。

## 云端审计核对

004日志可对应下面六次调用，均method=tools/call、JSON-RPC request_id=2、protocol_version=2025-06-18。初始化声明2025-11-25与实际调用协议不混用。业务UUID与JSON-RPC id不混用。

| 云日志时间 | 工具/用例 | 审计耗时 | outcome |
| --- | --- | --- | --- |
| 14:53:29 | search_scenic_spots 正向 | 2.46ms | ok |
| 14:55:56 | search_scenic_spots limit=0 | 0.57ms | ok |
| 14:56:35 | search_scenic_spots tags=[] | 2.38ms | ok |
| 15:00:10 | audit_degree_progress | 2.16ms | ok |
| 15:01:21 | search_study_materials | 3.18ms | ok |
| 15:02:25 | query_free_time | 2.28ms | ok |

审计outcome=ok表示请求处理完成，limit=0仍是业务VALIDATION_ERROR，不能把审计成功等同业务成功。耗时是服务器处理时间，不是平台/模型总耗时。不保存传输会话ID、代理地址或令牌。

## 编辑列表状态与后续门禁

本轮整理证据后再次运行后端完整回归：214 passed，1条第三方弃用警告，5.84s；禁用pytest缓存写入。无后端代码变更。此回归不代替平台GUI/主Agent验收。

最终四类业务显示“通过”，check_time_plan/validate_timetable显示“未通过”。health_probe编辑状态仍未通过（同步后未在本轮重测），不否定[此前主Agent004真实探针通过](D06-cloudbase-004-platform-debug-2026-09-30.md)，但下次发布前需复测当前编辑版。列表“已发布”是旧探针插件状态，不等于本轮业务版已发布。

下一步需要用户决定新版测试插件发布/主Agent草稿绑定范围；发布前复测当前探针并处理两类nullable输入验收。可以进一步验证平台运行时是否存在同类限制，但不得无授权发布、绑定全部业务或改公共协议。四类Debug通过也不代替主Agent真实业务调用。工作流、知识库、前端、生产身份和数据库不在本轮已完成范围。

本机截图（忽略目录，不提交Git）：deploy/cloudbase-demo-readonly/dist/D06-compat-final-closed-20260930.png显示本轮结束公网/内网关闭、8080；D06-scenic-null-input-required-20260930.png、D06-timeplan-null-input-blocked-20260930.png、D06-timetable-null-input-blocked-20260930.png为窄视口GUI阻塞局部证据。D06-compat-four-pass-list-20260930.png仅拍到列表右侧，不作为工具名/通过状态的图片证明。
