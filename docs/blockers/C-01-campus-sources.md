# C-01 阻塞：校园事务正式来源缺失（WAITING_HUMAN）

状态：WAITING_HUMAN（不阻塞公共前端与其他模块联调）

`knowledge/affairs/entries.json` 当前 15 条全部为虚构 demo 模板，`official_url=null`、
`verified_at=null`、`status=needs_verification`。按任务书规定，没有正式来源时不得编造
流程，也不得用第三方帖子冒充学校规定。

需要人工提供（C 本人或团队）：

1. 学校正式站点的入口链接与页面标题（教务、门户、图书馆、财务、一卡通、学工、研究生院、
   场馆、校医院、就业等），逐条记录 URL 与访问日期。
2. 至少 5 项高频办事的正式流程依据（通知/规章原文或官方页面截图位置），标注适用校区、
   适用人群、生效学期、是否需要登录/校园网。
3. 每条来源填入 `source_refs`、`official_url`、`verified_at` 后，把 `status` 改为
   `verified`；过期规则填 `valid_until` 并改 `expired`。

官方网页打不开时保留 `needs_verification`，不做“修正”。
