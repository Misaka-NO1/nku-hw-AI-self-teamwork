# 2026-10-10 遗漏规则补交与维护边界

## GitHub 交付归类

- PR #16：免注册浏览器私有空间、固定设备码、Agent 本人授权绑定、私有访客 SQL、部署开关、隔离测试与恢复说明。属于共享身份基础设施，不能当成演示功能删除。
- PR #15：课表 JSON 选择文件、焦点变化与上传反馈修复，属于给 B 的课表补充。
- 本次独立补交：此前本地已修改、未随上述 PR 上传的 Agent 规则及公开赏景服务恢复记录；不包含新密钥、用户课表、日历记录或云端数据库备份。

## 本次文件职责

| 类别 | 文件 | 目的 |
| --- | --- | --- |
| B / 课表 | `deploy/genios-workflows/timetable-personal-agent-append.txt`、`timetable-personal.test.mjs` | 以本次授权记录的 `dataset_kind` 判断来源；本人已保存课表不再套用旧演示免责声明，测试夹具仍明确标注 |
| D / 待办与通知 | `calendar-summary-agent-prompt-append.txt`、`personal-task-agent-append.txt`、三个 `notice-*-agent-append.txt` | 区分只读提取、本人草稿、明确确认、实际提交与读回；依据实际本人课表安排，不编造保存或后台推送 |
| A / 主 Agent | `prompts/main.md` | 与上述来源与保存语义一致；未授权或工具失败仍不能读取、猜测或兜底 |
| 公开赏景运维 | `docs/evidence/platform/public-map-503-recovery-2026-10-09.json` | 保存 10 月 9 日已获批准的最小实例 1 台常驻记录；仅是历史证据，不承诺今后不会出现 503 |

## 验证与发布边界

运行以下八组 Node 测试：`timetable-personal`、`personal-task-tools`、`calendar-time`、`notice-readonly`、`study-download-only`、`notice-schedule-prepare`、`notice-requests`、`notice-text`。

结果：48 个测试通过，无失败、无跳过。覆盖实际来源判断、非虚构通知阅读、用户选定时间、ISO 时间规范化、草稿确认读回和复习模块仅下载。

上传源码不等于学校平台 Agent 已重新发布。本 PR 不再次发布 Agent、不扩学校名单、不调整 OAuth 权限、不修改云端本人数据。

## 避免再次误删

不要从“工具名有 demo”“腾讯云登录页出现测试账号”推断免注册私有空间是可删除的演示实现。先审查 PR #16 的完整链路文档与测试，再修改身份功能。

云端恢复应先检查当前版本与 `visitor_enabled`，再决定回退或重新部署。已有访客迁移不能重复执行；回退应用镜像不等于回退数据库，也不能借此恢复用户已明确删除的课表。
