# 学校平台 MCP JSON 文本传输扩展（005插件通过，主Agent部分验收）

当前续步：用户另明确要求重新开启并持续保留公网，已执行，内网仍关闭，不再自动按登录过期/本轮结束关闭。五类005主Agent业务实际通过；课表长JSON两轮末尾括号损坏，服务器严格拒绝，D06仍未全部通过。未新增部署/工具或修改算法。[最新补测与待修边界](../docs/evidence/platform/D06-005-main-retained-retest-2026-09-30.md)。下段的关闭状态是前一窗口历史记录。

最新：2026-09-30兼容候选已部署CloudBase005，正常100%流量、004/003保留。另获本轮授权后学校团队插件实际同步13工具，六兼容工具16项正反例及探针通过；只启用/发布六兼容和探针，主Agent草稿换绑七工具且提示词保存读回。主Agent资料topic:null的真实Input/Output通过，其余主Agent用例因会话过期未验完；公网/内网入口最终关闭。本轮未重新部署、未发布主Agent。[部署证据](../docs/evidence/platform/D06-cloudbase-005-deployment-2026-09-30.md)、[本轮平台结果与待验边界](../docs/evidence/platform/D06-005-platform-compat-results-2026-09-30.md)。下文最初授权描述本地阶段，不再代表当前云/插件状态。

2026-09-30 用户批准先实现、测试、准备候选包；不自动更新云服务或发布插件。原因是主 Agent 的资料查询两次把 JSON null 传成字符串 "null"。不能以提示词或服务器自动纠错掩盖此差异。

原 REST 路径、原 MCP 工具及其 input/output Schema、业务 Schema 1.0.0 和 A/B/C 算法完全保留。前端、扩展和现有客户端无需改变量或请求。兼容工具只是 D 的可选薄传输层：JSON 文本解码 → 原 `execute_domain` → 原权限检查/算法 → 原 `ApiEnvelope`。没有任意 operation、URL、SQL 或写入选择器。

| 新兼容工具 | 原业务工具 / 校验定义 |
|---|---|
| platform_validate_timetable | validate_timetable / TimetableImport |
| platform_query_free_time | query_free_time / FreeTimeQuery |
| platform_check_time_plan | check_time_plan / TimeCheckRequest |
| platform_search_scenic_spots | search_scenic_spots / ScenicQuery |
| platform_search_study_materials | search_study_materials / StudyQuery |
| platform_audit_degree_progress | audit_degree_progress / DegreeAuditRequest |

以实际 `OPERATIONS` 映射及冻结 Schema 为准。探针保持 `health_probe(nonce)`，不新增另一个探针。

## 唯一外层参数

外层对象只允许一个必需 String 字段 `query_json`。值是完整原请求对象的 JSON 文本。例如客户端：

```javascript
const query = { course_id: 'demo-CS101', topic: null, limit: 5 };
const args = { query_json: JSON.stringify(query) };
// 使用 platform_search_study_materials；不要再 stringify(args.query_json)。
```

实际 MCP arguments：

```json
{"query_json":"{\"course_id\":\"demo-CS101\",\"topic\":null,\"limit\":5}"}
```

景点空值/空数组：

```json
{"query_json":"{\"campus_id\":null,\"tags\":[],\"month\":null,\"limit\":5}"}
```

其余工具的 query_json 来自各自原始夹具的完整 JSON；不得省略必填 nullable 字段、补假值或把对象再包一层 payload/query。`topic:null` 表示不筛选主题；`topic:"null"` 仍是搜索字面文字，两者绝不互相转换。中文、空字符串、数组、布尔和数值原样解析，非法类型交由冻结校验拒绝。

解码错误使用原错误信封：`ok=false,data=null,error.code=VALIDATION_ERROR,isError=true`。拒绝额外外层字段、非 String 参数、非对象根、双重 JSON 编码、重复键（含嵌套）、NaN/Infinity/数值溢出、非法 Unicode、过深 JSON；错误不回显请求正文、键名或解析异常。传输上限为131072 UTF-8字节，最大结构深度64；字符上限也在工具 Schema 中声明，字节与深度由服务器执行。它们是传输限额，不改变原业务参数范围。

## 默认关闭与候选包

`MCP_ENABLE_PLATFORM_COMPAT_TOOLS=false` 默认不发现或执行新工具。设为true还必须同时开启 `MCP_ENABLE_DOMAIN_TOOLS`；没有业务开关时拒绝启动。两个开关均开时发现原7工具加兼容6工具，共13个，全部只读。共享服务令牌仍不是用户身份，不可读浏览器私人工作区，不接收任意成绩/课表或写入。

打包必须显式使用 `Build-Package.ps1 -PlatformCompat`。清单列13工具并记录构建号/source SHA；服务开关和清单必须一致，否则拒绝启动。普通包仍列原7工具，旧004不受影响。部署候选只运行MCP，仍强制固定演示、关闭个人上传和无持久业务库。

## 后续平台联调门禁

本地通过不等于学校平台已正确生成 query_json。获准部署后，先验健康/401/13工具发现，再配置团队测试兼容插件并检查实际Input/Output；nullable案例必须比较原工具和兼容工具结果，校验/时间计划两类需各自正反例通过后才启用。不要让主 Agent 同时绑定同义的原业务/兼容工具造成选择歧义；获准变更时平台草稿只选一种，但后端保留两种以兼容现有客户。

真实数据、数据库、主 Agent 发布和市场上架均不在此次授权中。回退需匹配服务版本、清单、开关和插件绑定；不得只关兼容开关却继续运行13工具清单的包。
