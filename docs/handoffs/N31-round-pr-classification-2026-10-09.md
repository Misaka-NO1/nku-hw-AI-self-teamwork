# 本轮 PR 分类与交付状态

基线：main `5183645`（已合并 B 的 PR #12，包含 PR #11 的课表 UI）。

本 PR 是在 B 已有课表模块上补齐连接与修复，不把 B 的原提交重复归为本轮成果。以下课表部分明确属于 **给 B 做的补充**；身份绑定、日程、复习规则是另一类跨模块工作。

## 一、B 课表模块补充

| 范围 | 主要文件 | 交付内容 |
| --- | --- | --- |
| 教务解析与格式兼容 | `packages/import-core/src/{eamis,parse}.ts` 及相关测试 | 修复跨行单元格、停课周次、全部周覆盖判断，兼容 EAMS 导出 JSON；不执行导入 HTML，不夹带个人课表 |
| 扩展到原 UI 的交接 | `extension/src/`、`manifest.json`、扩展测试 | 点击后读取白名单教务课表区域，用独立交接编号和就绪握手传到工具站；不读取登录凭据，不自动保存 |
| 课表导入 UI 与校历 | `frontend/src/features/import/`、`frontend/ui-preview/import.html` | 先选文件后核对校历也能继续；错误入口有提示，支持逐节上课时间编辑、预览修正与明确保存 |
| 本人课表云端保存 | `personal-schedules-migration.sql`、`test_personal_schedules.py` | 私有课表、草稿、回执；明确确认、版本校验、幂等保存、按账号读回；继续使用已有周／日课表 UI |
| Agent 的课表识别规则 | `timetable-personal-agent-append.txt`、对应测试、`prompts/main.md` 课表段 | 按实际返回的 dataset_kind 和记录回答，说明真实导入入口，不把固定演示提示当来源依据 |

`backend/app/cloud_identity_site.py`、`core/cloud_identity_store.py`、`core/config.py`、打包脚本及 RPC 测试驱动是共享文件：其中个人课表开关、校验、保存/读回部分属于 B 补充；设备绑定和日程部分不归 B。提交按独立文件与共享文件分组，不能把整份共享后端都算作 B 的工作。

## 二、跨模块：身份绑定与日程

- 固定设备码：由当前浏览器生成；设备码是定位信息，不是登录凭据。必须由 Agent 当前有效 OAuth 授权确认归属，浏览器还须持有自身 HttpOnly Cookie，不能只凭学校 SSO 判断同一人。
- 查看设备码：工具导航提供只读入口，不自动新建设备、续期或切换账号。
- 旧的临时设备确认路线保留为默认关闭的兼容代码；固定设备绑定开启时不会安装该旧路线。不是要求用户再使用临时确认码。
- 日程删除：与取消分开，单项明确确认后删活动记录，再读回验证；支持未完成、已完成和已取消，保留原草稿/审计，不是完整数据擦除。
- 已保存日程按账号隔离；已删除事项不再被日历、Agent 已保存事项查询或空闲计算读取。重试幂等，旧草稿不能复活事项。
- 待办时间兼容补丁：仅规范化已明确日期、时刻及偏移的 ISO 时间，将 24:00 转为次日 00:00；不猜自然语言日期，字段错误不回显个人输入。

## 三、复习与 Agent 规则

- 复习模块仅查询目录和提供原文件下载，不读取材料讲解、解题或调用 `WF_StudyAnswer` / `KB_Study`。
- 推荐时段是建议，不是保存白名单；以用户明确给出的实际时间为准，歧义先问，冲突提示不擅自改时段。
- 所有写入仍经过草稿、本人明确确认、回执和读回，不把模型回复当数据库保存成功。

## 四、实际发布边界

- 工具站：部署 032（r35）已上线，100% 流量，实例 Running；删除按钮与接口的公开构建资源已核验。
- 前一轮本人课表读回及本轮 JSON/校历导入 UI 已上线，沿用原工具站与已有课表 UI；不把上传到聊天框当课表导入。
- 学校 Agent：v0.2.16 已通过并运行，包含复习仅下载与用户自选时间规则。**新增课表来源说明仍是本地待发布规则**；平台长富文本修改遇到安全审核拒绝后已恢复完整 v0.2.16，未发布不完整草稿。
- 后端时间兼容/字段错误改动作为源代码补丁提交，**尚未单独部署**。r35 是基于已部署 r34 的受限差量打包，不能因 PR 有这些源码就宣称线上全部已更新。
- 本轮创建 PR 不等于合并，不触发新部署，不修改用户已有课表/日程或访问名单。

## 五、复现与验收

```powershell
pnpm --filter web test
pnpm --filter @campus/import-core test
pnpm --filter @campus/extension verify
pnpm --filter @campus/import-core typecheck
pnpm --filter @campus/extension typecheck
pnpm --filter web build:identity
pnpm --dir deploy/cloudbase-identity-pilot/sql-tests test
node --test deploy/genios-workflows/calendar-time.test.mjs deploy/genios-workflows/study-download-only.test.mjs deploy/genios-workflows/timetable-personal.test.mjs
```

后端使用项目 Python 环境，在 `backend` 目录设置 `PYTHONPATH=.`，运行个人课表、设备绑定、个人时间、日程删除、日历、隔离和打包测试；新建隔离临时目录，不能复用生产数据库。

本轮重新验证：前端 203 通过；课表解析 57 通过、2 个可选本地个人文件测试默认跳过；扩展 33 通过；SQL 46 通过；提示词契约 6 通过；类型检查和 identity 构建通过。后端上述 8 个测试文件共 76 项通过（不是全量后端重测）。

真实桌面 Chrome/Edge 的完整扩展读取过程不能用内置浏览器模拟替代；真实教务课程区域解析、本人草稿保存和原 UI 刷新读回已分项验收，扩展原生点击链路还需用户在安装扩展的浏览器验收。

详细历史见 N28（原始连接及绑定/Agent 发布）、N29（JSON/校历 UI）、N30（日程删除）；历史中的“未提交/未部署”等记录对应当时节点，本页与 PR 描述为当前状态汇总。

## 六、上传排除项

不上传个人教务 JSON/HTML、个人课程截图、设备码/会话 Cookie、OAuth 令牌、环境密钥、`.test-tmp-*`、`artifacts/`、`dist/` 或测试数据库。可选真实文件测试仅接受本地环境变量路径，公共源码不包含实际课程名称与个人排课安排。
