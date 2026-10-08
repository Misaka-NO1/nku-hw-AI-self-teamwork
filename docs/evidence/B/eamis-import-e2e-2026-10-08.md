# B 模块 · 教务真实课表导入全链路实测记录（2026-10-08）

测试人：B（Coding Agent）在 Kimi 内置浏览器中实测；账号为项目成员本人（已获本人授权操作）。

## 测试方式说明

Kimi 内置浏览器不支持安装 Chrome 扩展，因此本次用浏览器的 JS 执行能力扮演扩展角色：
**提取代码与 `extension/src/content.ts` / `packages/import-core/src/eamis.ts` 同一套逻辑**
（`extractEamisGridFromDoc` 的 rowSpan 展开与三列观察值输出），回传事件与扩展桥接一致
（`campus:schedule-observation` CustomEvent），核对页为仓库当前 `ImportPage` 真实代码。
扩展二进制本身由 31 项单元测试与 dist 产物检查覆盖（IIFE、无顶层 export、按钮逻辑在包内）。

## 实测步骤与结果

1. **教务提取**：登录统一身份认证后进入 `courseTableForStd!courseTable.action`，
   `#manualArrangeCourseTable` 网格存在（15 行）。提取到 **19 个占用格**，覆盖：
   - 双周写法：`信息安全数学基础 双2-16`
   - 停课条目：`数据结构 (5,停课)`、`Python语言程序设计 (2,停课)`、`刑事诉讼法 (1,停课)`、`信息安全数学基础 (3,停课)`
   - 分组后缀：`组1` / `组2`
   - 多地点逗号分隔：`津南实验楼A区203,津南实验楼A区204`
   - 同格多条目（周三 3-4 节两条硬件基础记录）
   - 单双周混合：`1 3-17` 与 `(2,停课)` 同格
   与页面逐格核对一致。仅读取课程表格文本，未读取密码 / Cookie / SSO 字段。

2. **核对页自动接收**：向 `http://localhost:7100/#/import?source=eamis-auto` 派发
   `campus:schedule-observation` 事件后，页面自动解析成功：
   - 状态提示："已从教务系统自动读取课表，请在下方核对（可修改）后确认。"
   - 覆盖范围：`term · complete · 周次 1-17`
   - 预览表 20 行可编辑记录，无阻断 issue。

3. **编辑修正**：将"信息安全数学基础"改名为"信息安全数学基础（实测改名）"，编辑即时生效。

4. **确认 → 周课表**：点"核对无误，确认导入"后自动跳转 `#/timetable`：
   - 改名后课程出现在周二第 1-2 节（津南公教楼B区423，08:00–09:40）；
   - 自动定位到**第 6 教学周**（测试日 2026-10-08，演示校历 week1_monday = 2026-08-31）。

5. **保存**：
   - 本地持久化成功（`localStorage["campus.schedule.saved.v1"]` 已写入）；
   - 云端保存如实降级：后端未启动时提示"后端未启动或不可达：已在本地保存，云端未保存"。
     不谎报。注：即使后端启动，当前 demo 部署对非虚构课表强制 `DEMO_ONLY`
     （`backend/app/domains/tasks/service.py` `_validate_draft_payload` → `enforce_demo_fixture`），
     个人课表云端落库待 D 侧开启个人上传后联调。

## 结论

教务页提取 → 核对页自动解析 → 可编辑修正 → 确认 → 周课表渲染（自动定位当前教学周）
→ 本地持久化，全链路实测通过。云端个人保存为已知跨模块缺口（依赖 D），UI 如实提示。
