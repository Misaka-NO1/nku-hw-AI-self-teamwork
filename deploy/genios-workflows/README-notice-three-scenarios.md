# 通知与日程：三场景工作流

更新：2026-10-06。这是实现与接入记录，不是所有日历写入已上线的声明。

## 已创建的学校流程

| 流程 | 学校ID | 输入 | 作用 |
|---|---|---|---|
| WF_NoticeText_ReadOnly_20261006 | db2gktd4shhas0akpo9g | notice_input字符串 | 原文→模型阅读→证据/结构校验→逐事项、未覆盖原文、缺项 |
| WF_NoticeSchedule_Prepare_20261006 | db2gr854shhbpg8vf2qg | plan_input字符串 | 用户核对后的三个场景→确定性TimeCheckRequest列表 |

正文流程与请求编排均已发布1.0.1，两者已绑定主Agent草稿。正文1.0.1增加确定性时间追问白名单；编排1.0.1将非法输入转为结构化`invalid_input`，防止代码异常中断整个Agent。只读正文流程不把真实通知标为虚构，不依赖腾讯云授权。请求编排本身不查询课表；必须再逐项调用已绑定的`check_my_demo_time`，不能把编排成功当计算成功。真实个人教务尚未接通，课表比对只能使用本人已授权的演示课表。

源码与学校配置对应：

- 只读Start后代码：notice-readonly-school-input.js。
- 只读模型附加规则：notice-readonly-model-append.txt，配合prompts/notice-extract.md。
- 模型后校验：notice-readonly-validate.js。
- 三场景Start→代码→End：notice-schedule-prepare.js，End只输出result。
- 主Agent规则：notice-readonly-agent-append.txt、notice-schedule-agent-append.txt（覆盖旧D07仅固定fixture拒答规则）。

## 公共主流程

```text
粘贴通知全文
  → 原文阅读，拆出全部行动与原文证据
  → 判断择一活动 / DDL任务 / 固定活动（混合通知逐项走）
  → 用户核对、编辑缺项和偏好
  → 编排本次请求，记录revision/menu_id
  → 本人课表工具实际计算
  → 逐行展示候选、冲突、覆盖范围
  → 用户选择最新一轮结果
  → 受控页面复核标题、时间、DDL、地点、提醒
  → 后端再次计算并确认提交
  → task_id读回 → 日历展示 → 到期/未完成提醒
```

最后三步是保存接入规格；当前学校新流程尚没有任意真实通知写入工具，不能宣称已经完成。聊天“选1”表示选择，不等同代替本人签署保存。

## A. 多场活动，任选一场

适用于讲座、值班、面试、志愿活动等同一事项提供多个场次。

1. 保留每场名称、起止、地点；确认是“任选一场”而非“全部必须参加”。
2. 缺结束/日期先问；用户可以删除不想参加的场次，不改主办方时间。
3. scenario=alternatives，task=null；alternatives每场一项，option_id唯一。
4. 编排给每场单独event_conflict请求，再实际逐场查本人课表。
5. 每行一场，列冲突名称与区间、覆盖未知部分；不能把未查场次判为没空。
6. 用户只选一场。复核后只保存这一场；有冲突须本人明确接受，不能取消用户课程。
7. 若同一通知有独立必做事项，逐项保存；不因有多个时间就误认任选。

示例问法：“这两场我选一场参加，帮我分别和课表对一下。”

## B. 作业/任务有DDL，安排工作时间

1. 提取任务、截止、材料；截止与实际工作区间是不同字段。
2. 提供可编辑字段：具体DDL、预计分钟、最早开始、可安排范围、仅晚间等偏好。
3. 日期没有时刻不得补23:59；预计耗时不由模型擅自填默认值。缺项返回澄清。
4. scenario=deadline，alternatives=null；task含title/due_at/estimated_minutes/earliest_start。
5. 明确可用偏好转成available_windows内具体、互不重叠的区间；逐区间实际计算deadline_feasibility。
6. 只列真实candidate_slots，逐项完整保留start/end/duration_minutes及来源查询索引；最多先展示前三个，用户可要求更多。
7. 编辑DDL/耗时/偏好→revision加1→重新编排和查课表→旧菜单失效，不能沿用旧选择。
8. 用户选择工作区间后，复核同时展示“计划做：起止”和“截止：DDL”。DDL本身不是忙碌事件。
9. 后端提交前再查课表/任务版本；被新安排占用则409重新计算，不强行写入。

示例问法：“周五18:00前交报告，预计90分钟，只晚上有空，帮我给三个候选。把DDL改到17:00后再算。”

## C. 通知要求固定时段办事/参加

1. 提取固定起止、地点、所需材料；集合和正式活动为分别可核对的事项。
2. start-only只能展示已知开始，补齐结束前不调用完整区间冲突计算。
3. “约90分钟”仅是待确认估计；缺年份、相对日期参照先确认。
4. scenario=fixed_event，task=null，alternatives恰一项。
5. 实际event_conflict查指定区间；无冲突只说明本次已知覆盖内结果。
6. 有冲突列具体冲突，用户决定是否仍参加；不擅自把固定活动挪到空档。
7. 确认后保存固定区间，不再让用户从DDL工作候选中选择。

示例问法：“通知让我周三14:00—15:30去参加活动，看看课表会不会撞。”

## 编辑与选择状态

原文与补充分别保存，补充不冒充原文证据。状态：extracted→needs_review→ready_to_check→checked→selected→reviewing→committed。任意编辑返回ready_to_check并清空selected；不能将reviewed自动设true。

revision/menu_id只是客户端菜单版本标记，不是授权/确认票据。真正保存仍用D后端的draft revision、payload_hash、confirmation_id和幂等键。服务端重算及本人确认不可由这个FNV菜单标记替代。

过期通知保留历史日期并提示，不能搬到今天。历史算法测试必须明确给模拟参照日期，不把模拟结果当当前安排。

## 保存与日历接入约定（尚待完整联调）

现有D后端只接受明确自编虚构通知，浏览器Cookie/CSRF本人写；学校OAuth仍只读。真实正文可在学校读取，但不能为了保存伪造`fictional_data_confirmed:true`。

虚构演示接入顺序：`notice-text/read`取得服务器item_id→`check`取得服务端Plan与实际候选→用户选择→`drafts`→复核→`confirmations`→`commit`→GET task读回。不可将学校编排对象直接冒充服务端Plan。真实通知写入需另确定数据范围并实施适用后端，不移除虚构限制充当接通。

活动择一保存所选一场。DDL保存截止和选定工作区间，未选/未确认不占时间。日历聚合需包含新`/api/v1/notice-text/tasks`，不能只读取旧固定演示`/api/v1/tasks`。

提醒分三层：日历未完成/今日/逾期标记；页面打开时读本人摘要；Agent收到第一条消息时读摘要。打开Agent静态开场白本身不触发工具；关闭浏览器后不会后台推送。浏览器通知需要本人许可及实际调度支持，不能仅因保存就承诺准时外部推送。

## 验收与当前边界

学校Debug实际通过：正文拆分集合与观摩；合成通知包含活动、截止和相对日期缺项；编排正常DDL、两场独立请求、固定活动、DDL缺项不查、编辑后revision2与新menu_id、非法JSON返回结构化失败。

主Agent草稿实际调用链已见到：两场活动→编排一次→本人OAuth时间工具两次；DDL→编排一次→本人时间工具一次；固定活动→编排一次→本人时间工具一次，返回9月21日09:00—09:40与固定虚构课程的实际冲突。无保存请求。切换到doubao-seed-2-1-pro并打开平台当前时间，修复旧mini在短上下文中错误沿用历史通知的情况；并非据此保证所有用户输入都已验收。

编排测试的10月7日至9日仅验证请求序列化，未证明未来课表覆盖或候选可用。已部署演示学期不覆盖这些未来日期。活动B算法不支持buffers，非零值明确needs_confirmation=event_buffer_not_supported，不能声称已考虑通勤；DDL算法有buffers支持。

本地验证：27项全部通过（含时间追问白名单，模型附加的证件/返程/报名标记不能产生新的要求）。

```powershell
node --test deploy/genios-workflows/notice-readonly.test.mjs deploy/genios-workflows/notice-schedule-prepare.test.mjs deploy/genios-workflows/notice-text.test.mjs deploy/genios-workflows/notice-requests.test.mjs
```

修改后实际重算已验证：历史模拟9月21日任务从18:00截止/60分钟改到17:00截止/90分钟，重新调用编排与本人时间工具，候选从11:50—12:50变为11:50—13:20，revision1变为2。

上线验收还需：旧编号拒绝、任意通知本人确认保存/读回、日历显示、摘要计数更新、两账号隔离与失败路径。不能用代码节点绿勾替代这些结果。当前只能体验正文提取与演示课表比对，不应交付成“任意通知已自动写入日历”的成品。
