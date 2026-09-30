# D06：004 外部鉴权、主 Agent 探针和业务插件兼容检查

日期：2026-09-30，北京时间。后端源码/云端包不变，沿用 cda01c67 构建。状态：外部鉴权和主 Agent health_probe 通过；七工具发现成功；业务平台验收未通过。

## 范围及最终状态

按用户批准的本轮联调范围，只操作 nku-campus-mcp-probe 的默认 HTTPS 公网入口；内网入口保持关闭，最小0/最大1、8080、旧 Bearer、数据库配置、其他服务不变。不读取或展示正确服务令牌，学校平台使用此前用户输入的保密配置。未发布插件新版本、未发布主 Agent、未上架市场。

首次健康请求超时后立即关闭；确认新实例启动后在同一本轮范围内复测。景点 Debug 发现平台输出类型校验错误后立即关闭公网并核对公网/内网均关闭。随后仅查看参数定义，未改公共 Schema 或平台参数类型，未点击工具“完成”。

## 冷启动与外部鉴权

- 初始界面：004正常、100%流量、0实例，服务显示已暂停；始终自动扩缩容、最小0/最大1。
- 14:24:58：外部 GET /__tcb_probe__ 超时，30230ms、没有 HTTP 状态。前置脚本按门禁未发送无/错令牌 POST。
- 实例列表：新实例 nku-campus-mcp-probe-004-59c47f885d-h6bkj 创建于14:25:14，随后 Running。
- 14:26:16：新实例日志 Application startup complete、StreamableHTTP session manager started、Uvicorn 0.0.0.0:8080。距离首个请求约78秒，晚于30秒客户端超时；与冷启动相符，不能由此推断网络永远正常或保证所有冷启动耗时。
- 14:28:04复测：健康200（264.94ms）；无令牌401（108.77ms）；随机错误令牌401（209.81ms），均通过。后两项检查 WWW-Authenticate: Bearer。

执行 backend/scripts/preflight_mcp_auth.py，正确令牌未用于该脚本。没有为避免冷启动擅自提高实例下限；后续演示须预热并验收，或另行确认常驻实例及费用。

## 主 Agent 004 探针：真实通过

团队空间 datqfnm9t58vf5r4v1eg；主 Agent datqi1l4shh989l30fp0，草稿原绑定 campus-tools-dev/health_probe。

14:28:22发起，原始 Output（非仅模型回复）包含：

```json
{
  "isError": false,
  "structuredContent": {
    "nonce": "d06-004-20260930-1428-7d92f06a4b1c",
    "build_id": "cloudbase-demo-readonly-20260930-cda01c67",
    "server_time": "2026-09-30T14:28:23+08:00"
  }
}
```

content.text 内同样回显上述三字段。工具卡1.49s（模型1.26s、工具0.23s）；最终回复3.608s。云端14:28:24审计：method=tools/call、request_id=3、protocol_version=2025-06-18、tool_name=health_probe、outcome=ok、0.98ms。初始化请求声明2025-11-25；实际调用审计2025-06-18，不能混作同一协议记录。

## 七工具发现及景点业务 Debug 阻塞

插件 datsct54shh9f0j06qkg 的“同步工具”显示覆盖列表确认，完成后提示同步成功。14:29:50编辑列表出现：health_probe、validate_timetable、query_free_time、check_time_plan、search_scenic_spots、search_study_materials、audit_degree_progress。新工具显示未通过；同步不是新版本发布，也不是主 Agent 绑定完成。页面仍显示旧已发布状态和旧仅探针描述，不能据此认定六工具已经正式可用。

景点工具编辑标识 dauaonl4shh4egeg6g0g，使用代码模式输入，Request 实际显示：

```json
{"campus_id":"demo-campus","tags":["flower"],"month":3,"limit":5}
```

Debug Response 实际包含 isError=false、structuredContent.ok=true、error=null、data=[demo-spot-01]，meta.schema_version=1.0.0、data_version=demo-v1、request_id=6b6c26a5-b453-4b8c-b802-4ef7cb4f47b5；warnings 含 DEMO_DATA/NOT_REALTIME，calculation_version=null。content.text 同样含完整业务信封。仅返回固定虚构景点，无个人数据或实时花况。

但学校页面显示“调试失败”，Debug Details：

```text
None is not of type 'object'
schema['properties']['structuredContent']['properties']['error']
```

进入输出参数定义查看，发现平台导入表示：structuredContent.error 为必填 Object、data 为必填 String、meta.calculation_version 为必填 String。仓库实际边界：error 支持 ApiError/null（成功必须null）、data 为任意JSON业务数据、calculation_version 支持 string/null。平台类型下拉可见 String/Integer/Number/Object/Boolean 及数组，没有可见 Any/Null/联合类型选项。

云端对应审计：14:29:51 tools/list、request_id=3、protocol_version=2025-06-18、outcome=ok、3.44ms；14:32:21 tools/call、request_id=2、tool_name=search_scenic_spots、同协议、outcome=ok、2.8ms。MCP请求编号与业务信封UUID为不同层级，不能混用。

因此已确认本例的平台输出校验与冻结契约不一致；error 是本次明确报错点，data/calculation_version 的导入表示亦有潜在不兼容，但尚未取得这些字段的独立报错。不能声称算法失败、鉴权失败、全部六工具已通过，不能把 null 改成空对象或随意改公共字段绕过。

下一步需用户确认是否只修改学校插件参数映射/兼容层，保留服务器统一信封、错误标识、权限、算法和 REST/MCP 字段。先验正确业务、nullable/数组及失败结果，再决定插件发布/主 Agent 绑定；本轮未实施兼容修改。其他五工具未 Debug，主 Agent 业务未验收。

## 证据

本机忽略目录 deploy/cloudbase-demo-readonly/dist：

- D06-004-agent-probe-20260930.png：主 Agent 原始探针输出视图。
- D06-004-scenic-null-validation-20260930.png：Debug 的实际 Request/Response/isError=false，视口未覆盖底部完整错误；精确错误以上述已观察文本记录，不夸称截图完整覆盖。
- D06-004-closed-after-debug-20260930.png：公网默认域名、内网默认地址均关闭，8080不变。

正确令牌未读取或保存；不在记录内保存凭证、MCP session_id 或代理IP。后端214项回归在本轮开始前通过（见对话检查），没有新代码修改或新的容器发布。003回退保留，未执行回退。
