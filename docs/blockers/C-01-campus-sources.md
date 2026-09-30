# C-01：校园事务正式来源（主体已解除，2026-09-27；新增指引待核验，2026-09-30）

状态：办事流程 8 条已核验；2026-09-30 新增 4 条用户提供的日常指引，WAITING_HUMAN（团队核验中）

## 已完成：11 条官方入口（用户提供，已核验）

2026-09-23 从校外网络实测全部 HTTP 200 可达，域名均为 nankai.edu.cn 官方域：

| 条目 | 入口 | login_required 依据 |
|---|---|---|
| 教务系统（EAMIS） | https://eamis.nankai.edu.cn | 常识判断 yes |
| AI 融合门户 | https://i.nankai.edu.cn | 常识判断 yes |
| 图书馆 IC 空间管理 | https://libic.nankai.edu.cn | 常识判断 yes |
| 图书馆空间预约 | https://libroom.nankai.edu.cn/ | 常识判断 yes |
| 馆藏资源查询 | https://space.nankai.edu.cn | 公开查询 no |
| 体育理论考试系统 | https://tyxx.nankai.edu.cn/ | 常识判断 yes |
| 软件正版化平台 | https://ca.nankai.edu.cn | 首页检测到登录表单 yes |
| 网上办事大厅 | https://online.nankai.edu.cn | 实测跳转 iam.nankai.edu.cn 统一认证 yes |
| 志愿服务平台 | https://zyfw.nankai.edu.cn | 首页检测到登录表单 yes |
| 团委成长服务平台 | https://czfw.nankai.edu.cn | 首页检测到登录表单 yes |
| 教务部「在校生业务」栏目 | https://jwc.nankai.edu.cn/zxsyw/list1.htm | 公开页面 no（2026-09-27 实测） |

campus_network_required 均为 no（校外网络实测可达）。登录态内的功能未采集，
学号/密码/Cookie 不进仓库。

## 已完成：8 项办事流程（官方正式来源，2026-09-27 核验）

前五条来源为教务部正式文件（校外可达）：

| 条目 | 流程 | 正式依据 |
|---|---|---|
| `nku-proc-transcript` | 成绩单/在读证明办理 | 《本科生成绩单、在读证明及学历证书盖章等业务办理流程须知》（教务部，2026-03-11 修订），jwc.nankai.edu.cn/2022/0503/c35927a550628 |
| `nku-proc-student-card` | 学生证补办 | 教务部文件 教字〔2025〕1 号，jwc.nankai.edu.cn/2025/0225/c35927a563019 |
| `nku-proc-selfstudy` | 自修课程申请 | 《自修申请操作方法（学生）》（2022-02-18）+ 2026-08-17 选课通知「七、自修」（每学期门数以新文件为准：一般 ≤2 门） |
| `nku-proc-course-select` | 选课/退课（五阶段、期中退课记 W） | 教务部《南开大学 2026-2027 学年第一学期本科生选课通知》（2026-08-17，依据南发字〔2026〕82 号），jwc.nankai.edu.cn/2026/0817/c35933a601256 ，附件选课手册 PDF 第 2–4 页 |
| `nku-proc-dorm-housing` | 住宿申请与退宿 | 《南开大学学生住宿管理规定》（南发字〔2018〕37 号，用户提供正式文件；人工智能学院 2026-09-17 通知佐证现行适用，但其文号作〔2026〕37 号，疑为更新版本或笔误，以学校最新印发为准） |
| `nku-proc-dorm-repair` | 宿舍报修（后勤维修，两校区） | 学生生活指导中心官网报修指引：飞书「后勤报修」微应用 / 24 小时电话 85358535 / 后勤保障部微信公众号 nkuhqbzb，xgb.nankai.edu.cn/Shenghuo/News/info/id/234.html 及 id/248（2026-09-27 校外实测 HTTP 200） |
| `nku-proc-campus-network` | 校园网账号密码修改/重置 | 网信办《南开大学校园网密码更改方式》（2023-12-21），wxb.nankai.edu.cn/info/1155/1563.htm ；自助系统 netservice.nankai.edu.cn，忘记密码须持证到网信办服务中心（2026-09-27 校外实测 HTTP 200） |
| `nku-proc-credit-recognition` | 学分认定申请（校际交流/网络课程/转校/辅修/转专业） | 《南开大学本科课程学分认定管理办法》（南发字〔2019〕48 号），jwc.nankai.edu.cn/2024/0907/c35930a550108 ，附件 PDF 第 2–7 页：40% 上限、相似度 ≥70%、外校记 △ 不计 GPA（2026-09-27 校外实测 HTTP 200） |

另核验政策来源：
- 教务部《2026级南开大学本科学生手册（上册）》（2026-09-02，
  jwc.nankai.edu.cn/2026/0902/c35440a601698 ），含《南开大学本科生学则》全文，
  已用于培养方案 repeat_policy/免修/学分认定核验（见 `knowledge/degree/cs-2025/plan-rules.md`）。
- 教务部选课手册（2026.9.11 更新）第 10 页「学生体育课选课说明」，已用于培养方案
  体育子模块规则核验（类别制必修，无稳定 course_code，引擎返回 needs_policy）。

## 待核验：9 条用户提供的日常指引（2026-09-30）

用户提供、来源标注「在读学生日常路径」，按原则先标 needs_verification，
已随核验清单 `docs/kb-review-2026-09-30.md` 发团队群验证，确认后升级 verified：

| 条目 | 指引 | 备注 |
|---|---|---|
| `nku-proc-card-recharge` | 校园卡充值（南开大学一卡通微信服务号→卡片充值） | 涉及金钱安全：不收录任何支付链接/二维码，仅指引官方服务号入口 |
| `nku-proc-electricity-recharge` | 宿舍电费充值（飞书→南开微应用→充值） | 同上安全处理 |
| `nku-proc-view-plan` | 查看个人培养计划（eamis 深链，登录后直达） | 2026-09-30 实测校外 302 跳登录页，链接有效 |
| `nku-proc-venue-booking` | 体育场馆预约（tyggl.nankai.edu.cn） | 2026-09-30 实测校外 HTTP 200（用户类型选择页） |
| `nku-proc-teaching-eval` | 教学质量评价（飞书→南开微应用→教学质量平台） | 仅渠道路径，无直接链接 |
| `nku-proc-flea-market` | 跳蚤市场（飞书→南开微应用） | 同上 |
| `nku-proc-shuttle` | 校内班车时刻查询（飞书→南开微应用） | 同上 |
| `nku-proc-visitor-access` | 出入校申请/外校人员来访预约（飞书→南开微应用） | 同上 |
| `nku-proc-counseling` | 心理咨询预约（飞书→南开微应用） | 同上 |

注：后勤报修已有正式条目 `nku-proc-dorm-repair`（verified），飞书「后勤报修」
正是其官方三渠道之一，不重复收录。

## 仍待人工：无占位流程（仅保留测试夹具）

办事流程占位已全部消除。数据集中仅保留两个**故意虚构**的测试夹具：
`demo-proc-05`（过期提示测试）、`demo-proc-06`（校区过滤测试，仅津南）。
后续新增办事流程仍须遵循同一标准：官方通知或规章原文，标注适用校区、
适用人群、生效学期；官方网页打不开时保留 needs_verification，不使用第三方帖子替代。
