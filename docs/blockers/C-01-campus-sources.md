# C-01 阻塞：校园事务正式来源（部分解除，剩余 WAITING_HUMAN）

状态：部分完成（2026-09-27 更新）；办事流程 3 条已核验，3 条占位仍 WAITING_HUMAN

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

## 已完成：3 项办事流程（教务部正式文件，2026-09-27 核验）

来源均为教务部「在校生业务」栏目发布页（校外可达）及其附件 PDF：

| 条目 | 流程 | 正式依据 |
|---|---|---|
| `nku-proc-transcript` | 成绩单/在读证明办理 | 《本科生成绩单、在读证明及学历证书盖章等业务办理流程须知》（教务部，2026-03-11 修订），jwc.nankai.edu.cn/2022/0503/c35927a550628 |
| `nku-proc-student-card` | 学生证补办 | 教务部文件 教字〔2025〕1 号，jwc.nankai.edu.cn/2025/0225/c35927a563019 |
| `nku-proc-selfstudy` | 自修课程申请 | 《自修申请操作方法（学生）》，jwc.nankai.edu.cn/2022/0218/c35927a550802 |

另核验政策来源：教务部《2026级南开大学本科学生手册（上册）》（2026-09-02，
jwc.nankai.edu.cn/2026/0902/c35440a601698 ），含《南开大学本科生学则》全文，
已用于培养方案 repeat_policy/免修/学分认定核验（见 `knowledge/degree/cs-2025/plan-rules.md`）。

## 仍待人工：3 项办事流程的正式依据

`demo-proc-02`（选课退课）、`demo-proc-03`（宿舍报修）、`demo-proc-04`（校园网账号）
仍为虚构模板（needs_verification）；`demo-proc-05` 为故意保留的过期提示测试样例。
需要提供官方通知或规章原文，标注适用校区、适用人群、生效学期。

官方网页打不开时保留 needs_verification，不使用第三方帖子替代。
