# C-01 阻塞：校园事务正式来源（部分解除，剩余 WAITING_HUMAN）

状态：部分完成（2026-09-23）；办事流程仍 WAITING_HUMAN

## 已完成：10 条官方入口（用户提供，已核验）

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

campus_network_required 均为 no（校外网络实测可达）。登录态内的功能未采集，
学号/密码/Cookie 不进仓库。

## 仍待人工：5 项办事流程的正式依据

`demo-proc-01` ~ `demo-proc-05` 仍为虚构模板（needs_verification / expired 示例）。
需要提供官方通知或规章原文：成绩单/在读证明开具、选课退课、宿舍报修、
校园网账号问题等，标注适用校区、适用人群、生效学期。

官方网页打不开时保留 needs_verification，不使用第三方帖子替代。
