# 待办日历后端交接

2026-10-06。对应《待办日历前端与D接口对接》，完成后端、存储和学校摘要接口候选，未继续开发前端。默认关闭，未云端迁移或发布。

## 接口

沿用 ApiEnvelope，meta.data_version=`task-calendar-v1`；候选外层 meta.calculation_version 使用 B 原版本。浏览器身份来自原 Cookie，workspace_ref 只校验当前本人工作区。契约见 contracts/api.schema.json 的 CalendarUpdateRequest、CalendarTask、CalendarTaskList、CalendarCandidates、CalendarSummary。

| 方法与路径 | 输入 | data |
|---|---|---|
| GET /api/v1/tasks/calendar | 唯一 workspace_ref 查询参数 | items 全量本人事项及完整13字段 notice；独立日历状态；capabilities 三项 true |
| GET /api/v1/tasks/{task_id}/calendar/candidates | 唯一 workspace_ref 查询参数 | candidate_slots、needs_confirmation、coverage；固定活动 fixed_event=true |
| POST /api/v1/tasks/{task_id}/calendar | 完整正文、同源 Origin、X-CSRF-Token、Idempotency-Key | 完整 CalendarTask，随后 GET 可读回 |
| GET /api/v1/tasks/calendar/summary | 唯一 workspace_ref 查询参数 | pending/today/overdue/unscheduled_count、total_count、next_task、as_of、background_push=false |
| GET /oauth/tasks/summary | 无 query/body，原 demo:read Bearer | 同一摘要，归属只来自严格或参赛 OAuth grant |

```json
{
  "workspace_ref": "本人已登录工作区",
  "expected_revision": 0,
  "status": "pending",
  "scheduled_start": "2026-09-21T09:45:00+08:00",
  "scheduled_end": "2026-09-21T10:05:00+08:00",
  "reminder_minutes": 0
}
```

这是历史虚构测试时间，只说明字段，今天直接提交会因过期拒绝。六字段都必填，额外 owner/user 字段拒绝；reminder_minutes 只允许 null/0/5/15/30/60，布尔值不能当数字。返回时间可标准化为等价 UTC，前端比较时间戳。

CalendarTask 包含 task_id、revision、confirmed_at、完整 notice、calendar_revision、status、scheduled_start/end、reminder_minutes。初始 pending、calendar_revision=0，与通知 revision 分开；安排初始取原固定活动起止或已确认 selected_slot。完成/取消保留通知和时间，但在后续空档、通知检查和提交中释放占用；恢复 pending 重新检查当前时间、课程和其他 pending 安排。冲突、旧版本、幂等键换正文返回409。旧会话401，跨工作区/任务404，缺 CSRF 或错误 Origin403，格式422；OAuth 额外参数400。

截止任务可清空安排，此时 reminder 必须 null；单纯 due 不占时间。固定活动不能改期/清空。完成、取消、修改提醒可处理历史事项，过期固定活动不能恢复占用。改期不改原 notice.due/materials/source_spans。

候选复用 B 算法，排除本事项旧占用，结合服务器当前时间、due、earliest_start、耗时、buffer、available_windows、本人课表和其他未完成已排事项；返回足够长窗口，提交工作区间须恰好等于耗时。缺关键字段不推荐；不自动平移历史日期。摘要与PR #9页面口径一致：today 统计pending安排跨越今天（结束不含）或截止日期为今天；overdue统计pending且精确due已过，或date_only日期早于今天，不补造具体时刻。next_task取未来最近的安排开始，缺安排时取活动开始或精确截止。

## 存储与开关

`CLOUD_TASK_CALENDAR_ENABLED=false` 默认关闭，同时要求 `CLOUD_NOTICE_TEXT_PILOT_ENABLED=true` 和原封闭两账号配置。日历开关关闭时不注册新增日历 API，访问返回404；缺迁移启动/健康检查拒绝。原15分钟会话、24小时工作区、退出和授权到期继续生效，未开放真实个人上传。静态 calendar/summary 在动态 task_id 前注册；本地/身份入口允许刷新 /tools/calendar。

`task-calendar-migration.sql` 在身份、参赛OAuth、notice-text迁移后单独审阅执行：新增 nku_task_calendar_v1.states/idempotency 两张 RLS 表及仅 service_role 可调用 RPC，**替换 nku_notice_text_v1.snapshot** 让本人时间、通知检查/提交看到同一日历状态。没有删除通知或改旧15表。安装后旧草稿 records_revision 会变化，须刷新重算。

Python 提交前重做 B 校验；SQL 在原 owner 锁内重读快照、校验独立版本 CAS，原子保存状态与幂等结果。计算后课表/其他待办变化拒绝旧快照；同键同正文取原结果，同键换正文409；失效工作区不能取缓存。新 RPC 是后台接口，不注册给浏览器或 Agent，Agent 只有摘要读取。

固定虚构课表范围 2026-09-07 至 2026-10-05 00:00（结束不含），不能证明10月6日以后没有课程。新候选返回 timetable_outside_term、无窗口，保存拒绝；需要后续提供覆盖当前日期且经批准导入的课表。没有全局取消 fixture 门禁或修改夹具日期。reminders capability 表示支持状态存储，页面外推送未部署。

## 尚需外部接入

1. 已再次同步并整合PR #9（origin/main与HEAD=3a31ebd），取得frontend/src/features/calendar/。唯一页面导出冲突已同时保留calendar和原通知试点，原本地修改恢复为未暂存状态，Git autostash备份保留。本轮前端150项通过、类型检查和双服务构建通过，不继续开发前端功能。
2. 审阅并执行新云迁移/后台权限，合入交付前端后部署默认关闭候选，再开启新功能；保留原两普通账号范围。现有线上接口未升级，不能直接按这组路径宣称可用。
3. 两账号线上验收改期、读回、重开、完成/取消释放、冲突恢复、CAS/幂等、跨用户访问、退出和到期。
4. 学校增加只读 GET /oauth/tasks/summary，新会话实测调用与未授权/过期拒绝。只有明确支持且实测打开会话触发工具，才能称“打开即提醒”；否则首次用户消息查询。工具与提示候选见 deploy/genios-workflows/calendar-summary-tool-candidate.json、prompts/calendar-summary.md。
5. 前端接入方验收通知权限、0分钟提醒、ICS 普通下载和实际导入；无定时、邮件/短信/Web Push服务。

页面已通过实际隔离PG联调：读取本人任务、B候选、勾选确认、0分钟提醒写入读回、完成/取消/恢复、刷新和两虚构账号切换。桥接仅用于loopback测试，虚构时钟9月21日；生产HTTPS/Origin/Cookie检查另由完整后端用例验证。ICS普通点击有页面提示但浏览器未返回下载事件，没有确认落盘或实际导入；未申请桌面通知权限。验证见 D15 验收记录。代码 backend/app/core/task_calendar.py、backend/app/api/task_calendar.py；迁移 deploy/cloudbase-identity-pilot/task-calendar-migration.sql。早期backend-only集成包保留；已整合PR #9并生成完整身份/公开两包。实际云预检显示两组新schema未装、身份016暂停；迁移与新后台RPC权限已准备，等待执行前确认。回滚先关闭两个新开关并回原016/公开009代码版本，旁表与原通知保留，不自动删除表或数据。两份迁移分事务执行，若第二份失败，保持开关关闭并修复迁移后再开启。
