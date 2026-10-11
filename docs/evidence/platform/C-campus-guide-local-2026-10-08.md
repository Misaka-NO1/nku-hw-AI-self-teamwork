# C 校园事务指南本地交付验收

时间：2026-10-08。范围：指定C分支资料整合、知识导出、网页问题匹配。状态：LOCAL_PASS。本文件保留本地交付阶段记录；后续已完成平台导入、v0.2.14正式Web发布及学生证实测，最新证据见 `C-campus-guide-live-2026-10-08.md`，下方“尚待D接入”属于较早阶段。

## 资料与归属

原始清单：https://github.com/lihongyi0801-cloud/nku-hw-AI-self-teamwork/blob/feat/agent-c-campus-frontend/docs/kb-review-2026-09-30.md

通过公开raw地址读取同分支评审和 `knowledge/affairs/entries.json`，未执行其中任何代码。原清单归档 `docs/kb-review-2026-09-30.md`。源数据C维护，最终位置为 `knowledge/affairs/entries.json`；D只负责后续平台接入。

31条资料：11个官方入口、8个C历史核验流程、9个学生待核验指引、3个新增服务。两个demo夹具单独存放且不出现在用户页面或平台导出。历史核验日期原样保留。

本轮查阅公开正文（HTTP200，不是实际工单或办事提交验收）：

- https://hq.nankai.edu.cn/24030/listm.htm ：物业维修范围、三类报修途径；更新报修摘要与日期。
- https://hq.nankai.edu.cn/24032/listm.htm ：空调租赁开启服务、凭证领取，以及空调报修和“我的报修”；新增两条指南。
- https://wxb.nankai.edu.cn/info/1155/1563.htm ：能登录情况下自助修改与忘记密码本人有效证件现场重置；页脚官方校园卡业务联系方式，仅补窗口咨询指南，不推断挂失补办细则。
- https://jwc.nankai.edu.cn/2025/0225/c35927a563019/page.htm ：学生证文件页面可访问，未重新解析其PDF，因此该流程仍保留C原核验日期，不声称本轮重验材料与时限。

公开正文暂存工作区 `.review-cache/affairs-source-*.html`。未登录上述系统、未提交工单、未修改账号权限。

## 验证

- 前端事务测试14项通过：官方来源展示、校区过滤、过期夹具、自然语言学生证/校园卡分流、空调报修/租赁分流、未核验电费保留状态、本科规则不套研究生、未知事务不捏造。
- 后端知识导出测试7项通过：经验投稿发布约束、事务状态保留、新文本导出保留历史窗口警示与官方来源、排除demo夹具。
- TypeScript + Vite identity构建通过。第一次构建发现测试夹具类型转换问题，已修正后二次构建通过。现有大chunk提示仍存在，不影响本轮构建成功。
- `knowledge/scripts/build_exports.py --campus-only` 生成31条JSON与Markdown，不改课程知识库。

网页“查办事指南”是对已收录条目的匹配与展示，不是无限制生成模型。未命中或适用人群不符时明确没有相应流程；待核验指引保留提醒。

## 尚待D接入

实际已绑定知识库需核实；导入新版 `KB_Campus.md`，同步更新旧主提示词“两项后勤摘要”的限制，草稿回归再正式发布并取证。本轮未修改网站或学校Agent线上状态，不把本地测试记作平台实测。完整位置与回归步骤见 `knowledge/affairs/README.md`。

