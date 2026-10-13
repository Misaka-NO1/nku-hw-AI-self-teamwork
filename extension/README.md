# 教务共用拓展（课表＋培养计划）

## 安装（0.3.4，课表与培养计划共用一份）

下载 `campus-reader-0.3.4.zip` 并解压。电脑 Chrome 地址栏打开 `chrome://extensions`，Edge 打开 `edge://extensions`；启用开发者模式，点击“加载已解压的扩展程序”，选择含 `manifest.json` 的文件夹。核对名称“南开校园助手 · 教务课表与培养计划”、版本 0.3.4；停用或移除旧副本，刷新已经打开的教务页。手机可接收电脑导出的 JSON，再上传给 Agent，不支持在手机 Chrome 安装此拓展。

0.3.4 统一显式版本下载入口和可见安装引导；旧 `campus-schedule-reader.zip` 地址兼容返回同一份新版。提取逻辑、权限和确认保存流程不变。

## 使用流程

1. 使用原课表拓展，不安装第二个。构建：pnpm --filter @campus/extension verify，Chrome重新加载整个extension目录。
2. 本人登录教务，打开 https://eamis.nankai.edu.cn/eams/myPlanCompl.action 的“计划完成情况”，等待表格加载。
3. 点右下角“导出计划完成情况 JSON”或拓展图标，得到 degree-progress.json。
4. 把JSON上传给南开Agent（手机也可上传），Agent先显示分类学分核对，不保存。
5. 本人明确确认这份预览后，才保存到账号原私有空间；已有报告需明确替换提示。成功需真实版本和读回核验，随后对话查询。

0.3.2 修复教务页面不重载切换时的旧按钮/旧地址残留：先培养计划再课表、反向及往返均支持。更新原拓展后须刷新已经打开的教务页，让旧版脚本退出；不要同时安装两个版本。共享入口 eamis-content.js 只观察页面切换，不自动提取或上传。课表页只显示课表按钮，计划完成情况页只显示学分导出按钮。

旧/tools/degree链接仅保留简短Agent使用引导，不再挂业务导航，不提供独立培养计划导入/演示框架。
旧degree-completion.json课程明细文件应重新导出，不应发给私有进度后端。
拓展下载只表示生成本地文件，不自动上传或保存。实际Agent若无法完整读取JSON附件，应提示粘贴完整JSON，不得猜数据。

## 数据与规则

导出kind=degree_credit_progress，只含专业/年级、学校总览、分类要求/教务实修/原状态/备注及在读标记。
0.3.3 新增分类“在读学分”和“直属在读学分”汇总，只统计明确标为在读的课程；层级不明或重复归类时保留未知。直属在读学分只包括本分类下、子分类之前的课程，不擅自分配给通识六模块。扣除明确在读后的值仍不是正式已取得学分。
旧 JSON 没有这两个字段时按未知处理，不能用父子差额反推；需要更新原拓展、刷新教务页并重新导出，经本人核对确认后才替换原报告。
不导出课程明细或成绩、姓名学号、审核人、Cookie/密码、隐藏表单、令牌或整页HTML。
源解析器局部读完成表以识别在读，但课程行不进入导出文件和私有进度存储。
预审/实修可能含在读；暂计差额不等于最终未取得学分。未知不补零，父子分类不相加，不作毕业资格审核。
C08通识选修规则单独保留（knowledge/degree/cs-2025/plan-rules.md，提交4805f6e）：
六模块至少选四、所选四个各≥2；2023级起艺术类课程另≥2，艺术审美模块总分不能代替艺术类认定。
总要求以本人方案为准，14仅计算机科学与技术2025版参考；未核实归属/年级/艺术类型/学校认定时needs_policy。

## 实现与上线边界

B原课表提取/导入保持不变；C规则为问答来源；D身份、OAuth及持久化防串空间。
共用提取：packages/import-core/src/degree.ts；学分导出投影：degree-progress.ts。
当前部署的学分提示块以deploy/genios-workflows/degree-progress-qa-fit-live.txt为准；其余append/compact文件为历史候选，不要同时叠加。
工具规范：degree-progress-tools.openapi.json，复用read_my_degree_records，新增preview_my_degree_import和confirm_my_degree_import。
本人固定隐藏SYS_USERID＋本轮服务签名＋匹配的OAuth归属，用户/模型不能指定owner。
读取需degree:read，预览/确认保存需独立degree:write，新授权须本人确认，旧授权不升级。
先运行degree-progress-migration.sql一次（生产已安装）；新增写入迁移degree-agent-import-migration.sql也只执行一次，不重跑旧迁移。
degree-in-progress-migration.sql 仅兼容新增两个可选分类字段，保留原权限和数据；必须单独确认并执行一次，不重跑旧迁移。
CLOUD_DEGREE_PROGRESS_ENABLED和CLOUD_DEGREE_AGENT_WRITE_ENABLED分别控制读取与Agent写入；写入还要求native身份核验开启，默认关闭。
草稿10分钟有效，只确认本次真实ID和hash；版本冲突重新核对；超时同草稿幂等重试；退出/撤销/身份不一致安全拒绝。
私有表RLS，anon/authenticated无直接读写，service_role只执行受保护固定RPC。课程成绩/姓名学号不允许进入报告契约。

当前：云端062（r52）已上线，0.3.3 下载包与部署包哈希一致；分类在读汇总兼容迁移已成功，旧个人报告未自动改写。Agent v0.2.23 配置已发布，渠道状态以平台记录为准。真实报告须重新导出、预览并由本人确认替换。
禁止把候选代码、单元测试或虚构数据当作生产上线成功。真实个人JSON不提交GitHub。
