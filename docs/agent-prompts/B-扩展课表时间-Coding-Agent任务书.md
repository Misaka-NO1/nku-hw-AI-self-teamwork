# B 任务书：浏览器扩展、课表导入与时间计算

> 这份文件是给 Coding Agent 的完整任务说明。交给 AI 后，AI 负责写解析器、扩展骨架、时间算法、测试和交付报告。人员本人不需要会写代码。

## 直接交给 Coding Agent 的开场指令

```text
你是本仓库的 B 模块 Coding Agent。

我不会写代码，请你直接完成任务，不要只给我教程或代码片段。你需要自己检查仓库、创建和修改文件、运行测试，并在最后告诉我真实结果。

开始前先阅读：
1. README.md
2. contracts/integration-conventions.md
3. contracts/api.schema.json
4. 本文件全部内容

如果缺少真实教务页面、登录权限或样本，不要猜测南开教务域名、选择器或隐藏接口。把适配器标记为 disabled，记录 WAITING_HUMAN，然后继续使用虚构夹具完成解析器和时间算法。

现在开始执行 B01 到 B06，完成后再根据实际条件继续 B07 到 B12。
```

## 你的角色

你负责浏览器扩展、文件导入、课表展示、周次展开、空档查询、冲突检测和截止前可行性计算。

你不负责认证系统、数据库、MCP 注册、平台发布、通知提取或培养方案算法。

## 允许修改的范围

```text
extension/
packages/import-core/
frontend/src/features/import/
frontend/src/features/timetable/
backend/app/domains/schedule/
backend/app/domains/timeplan/
对应测试
docs/evidence/B/
docs/handoffs/B-progress.md
docs/blockers/B-*.md
```

## 必须完成的函数

```python
validate_timetable(payload)
expand_occurrences(calendar, courses, window)
find_free_slots(actual_events, window, min_minutes, buffers)
check_time_plan(calendar, courses, tasks, request)
```

公共接口映射固定为：

```text
validate_timetable → validate_timetable
find_free_slots    → query_free_time
check_time_plan    → check_time_plan
```

## 课表解析要求

实现：

- JSON/CSV 标准导入
- 周次解析，包括单双周、跳周、中文标点和非法周次
- 节次和星期校验
- `TimetableImport` 标准化
- `coverage` 覆盖范围判断
- 缺失字段列表
- 页面不支持时返回 `UNSUPPORTED_PAGE`
- 结构异常时不能导入空课表

TypeScript 内部可以使用 `adapterId`、`adapterVersion`，但写入标准 JSON 时必须转换为 `adapter_id`、`adapter_version`。

## 时间计算要求

- 时间区间使用半开区间 `[start, end)`。
- 前一个活动 10:00 结束、后一个活动 10:00 开始，不算冲突。
- 课程按教学周、星期和节次展开。
- 先应用调休日和替换规则，再生成实际课程。
- 空档只返回长度不少于 `min_minutes` 的连续时间段。
- 截止任务不是 busy block。
- 没有预计耗时，返回 `needs_confirmation`。
- 只有日期没有精确时刻，返回 `needs_confirmation`。
- 不擅自使用 23:59。
- 不自动移动课程或截止时间。

## 浏览器扩展安全要求

- 只在用户点击扩展后读取页面。
- 只允许白名单 origin、path 和课程区域。
- 不申请 cookies、debugger、webRequest 或 `<all_urls>`。
- 不读取密码、Cookie、SSO 字段、localStorage 认证项。
- 不执行用户 HTML 中的脚本。
- 不加载 HTML 中的远程资源。
- 页面结构变化时返回错误并提供文件导入降级。
- 没有真实页面时将 `nku-adapter-v1` 标记为 disabled。

## 测试要求

至少完成：

```text
TIME-01 单双周展开
TIME-02 半开区间不误报冲突
TIME-03 不同周次不误报冲突
TIME-04 非法周次和节次返回 422
TIME-05 截止前 20 分钟任务可安排在 09:40–10:00
TIME-06 缺少耗时或截止时刻时待确认
TIME-07 partial 课表保留覆盖范围提示
TIME-08 调休日替换不重复叠加
IMPORT-01 空页/登录页/未知表头拒绝导入
IMPORT-02 同课程不同 meeting 都保留
IMPORT-03 恶意 HTML 不执行、不联网
EXT-01 非白名单域名不注入
EXT-02 票据过期不上传
EXT-03 iframe/页面改版给出明确降级
```

## 完成后的汇报格式

在 `docs/handoffs/B-progress.md` 写入：

```text
任务状态：LOCAL_PASS / WAITING_HUMAN / 未完成
修改文件：
导出的函数和组件：
TimetableImport 字段映射：
时间算法版本：
测试命令：
测试实际结果：
真实教务页面是否验证：
适配器是否启用：
给 C 的下一步：
给 D 的下一步：
```

不要把虚构页面测试说成真实教务适配成功。
