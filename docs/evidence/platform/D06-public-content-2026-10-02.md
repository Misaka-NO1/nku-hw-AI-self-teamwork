# 公开地图/期末资料：2026-10-02 部署与学校插件实证

## 范围与版本

负责人批准同一CloudBase环境中新建隔离的公开内容服务，保留MCP005/Tasks003/现有数据库，只绑定主Agent草稿，不发布主Agent或上架市场；新增付费购买需再确认。本轮无购买、无Git提交/推送/PR。

- 服务：`nku-campus-public-content`，环境 `sunner-wang-d8ght8niaaaea70b7`。
- 实际域名：`https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com`。
- 构建：`cloudbase-public-content-20261002-r3`，ZIP SHA256 `56637af1c16a8c4755e772e8e469b7f8568bc4e973f153eb0abc1a6637a6cfe3`。
- 云版本002：19:29:45创建，任务2276308，正常/100%/1实例；001保留。r2/001遗漏地图模块，不作为完整地图验收。
- 数据：景点 `jinnan-2026-09-26`（34点/91照片/完成模型/36道路）；资料 `y1-070600fb47f92e70`（33公开PDF，含个人信息的一份原材料不入包）。
- SQLite资料索引为只读快照；无CloudBase service_role注入，不把容器当可写生产数据库。
- 源HEAD仍 `f6fe20977d60fbc85871bd07e52c810c5d399960`，代码及同步的main资料尚未提交；包清单如实记录此状态。

## 本地验收

后端完整334 passed/1 AnyIO第三方弃用警告，13.80秒。前端30项、类型检查及Vite构建先前通过，不冒充本轮重跑。

实际浏览器本机8013验证：资料上下学期消歧和构造函数关键词匹配、原PDF链接、地图34点与完成道路、点击思源道海棠直接打开实景。横图1920×1280与竖图1440×1920均加载成功。r3打包前增加相对地图模块依赖完整性门禁，避免再次遗漏 `road-surface.mjs`。

## 学校 MCP 真实调用

插件 `campus-public-content`，ID `davpgp54shhas0akdk7g`；负责人亲自输入Bearer并提交创建，值未读取/复制/写入仓库。实际同步13工具。初次景点查询错用campus_id=jinnan得到空目录，不作为命中成功；学校另将nullable的error误推断成不可空Object，输出校验失败。按既有005兼容方案，仅移除两个新查询的 `structuredContent` 下data/error/meta/ok子类型，保留Object根、isError/content及实际JSON，不修改公共契约或服务器数据。

| 用例 | 实际输入 / 输出 | request_id |
| --- | --- | --- |
| 健康 | nonce `public-content-20261002-1943-check` 原样回显；build r3；server_time 19:42:56+08:00 | 探针无业务UUID |
| 景点正常 | nku-jinnan / tags海棠 / month4 / limit5；思源道海棠、贴梗海棠、一颗低垂的海棠、楼内赏海棠、绝美小路；照片与spot_id深链接；ok=true/error=null | 40c564e4-018b-4b1a-ae33-5dac227628d5 |
| 景点非法 | limit0；isError=true/ok=false/VALIDATION_ERROR/limit minimum；不改为1 | 2ec07961-eaa7-4ecc-ad0e-e360f60018f2 |
| 资料正常 | y1-s2-programming / 构造函数 / limit2；期末复习2-2 1（PDF7/12/41）与cpp_review_notes_with_code（PDF3/3/8），真实原文可用/来源与警告 | 6385d550-f9f0-4c26-9054-5adb0fbf9154 |
| 资料不兜底 | demo-CS101 / topic真null / limit5；ok=true/data=[]，不返回旧演示资料 | 016cad0c-c63b-45e8-b390-16d146cde35a |

景点保留SCENIC_UNVERIFIED/NOT_REALTIME，不声称当前花况；资料保留STUDY_TEXT_UNREVIEWED/PARTIAL/OCR警告，不声称当前考试范围或官方真题身份。健康调用成功不等于全部13业务通过，也未重跑正确/缺/错Bearer全门禁。

## 当前发布边界与下一步

新插件只启用 `platform_search_scenic_spots` 与 `platform_search_study_materials`；其余11项禁用且配置保留。两个启用查询Debug显示通过。健康早前实际调用成功，但后续工具配置修改后平台列表重置了其Debug状态，当前禁用，不以历史调用冒充当前已发布工具状态。

此前点击团队发布只到确认框，提示仍存在未通过工具。最终提交被自动安全审查拒绝，已交给负责人；未通过其他浏览器或接口绕过。负责人随后回复“好了”，本轮实际查看插件已显示“已发布”，不再把此前待发布状态当作现状。没有发布主Agent。

本轮已把两个公开查询绑定主Agent草稿，解除旧两个同义演示查询；保留旧health/时间/培养/课表工具与固定虚构课表工作流。提示词增加真实目录、9个临时课程ID、上下学期消歧和来源/OCR/花期边界。本地 `prompts/main.md` 同步规则；平台另保留既有工作流及个人课表能力约束。

## 主Agent自然语言实证（19:58起）

实际展开“已完成”→工具调用→Input/Output读取，非仅凭模型答复判断成功：

| 请求 | 本次实际输入与结果 | request_id |
| --- | --- | --- |
| 四月津南拍海棠，推荐三处 | nku-jinnan / 海棠 / 4 / 3；思源道海棠、贴梗海棠、一颗低垂的海棠；三条实际map_url；回答保留未核验/非实时提示 | 7572068a-7025-4298-a723-b2c741897c24 |
| 大一下程序设计，构造函数，两份原文 | y1-s2-programming / 构造函数 / 2；期末复习2-2 1与cpp_review_notes_with_code；回答引用PDF7/3页及真实material_url，说明非官方真题/提取未校对 | 6b5dc1bc-b1ce-45ad-8beb-c6d9327e92fd |

两次分别返回真实版本 `jinnan-2026-09-26` / `y1-070600fb47f92e70`，ok=true/error=null。资料证据实际还包含PDF12/41/8页，回答只选其中片段；不声称已阅读所有PDF、涵盖今年考试或全部功能上线。

20:01仅说“高数复习资料”时，Agent先询问大一上/下，无工具查询，没有擅自选择课程。20:02异常测试首次把query_json误传Object（内含demo-CS101/topic=null/limit2），后端实际VALIDATION_ERROR，request_id `ba7e5d75-a644-49f4-8577-89d45e21798b`。Agent如实报告失败但不能作为“未知课程空结果通过”证据。已在平台/本地提示词补强外层字符串的正反例，不修改服务器校验；复测另行记录。字符串包装依赖模型仍是稳定性风险，不能凭一次正常调用宣称所有参数可靠。

20:03补强后复测实际Input为字符串 `{"course_id":"demo-CS101","topic":null,"limit":2}`；Output为ok=true/error=null/data=[]，版本y1-070600fb47f92e70，request_id `d094f306-670f-4b6d-851a-fa93d0de13cc`。模型没有把未知课程改成演示成功，也没有重复上次原文或request_id。此为一次复测通过，不删除上一条失败记录。后续批量稳定性测试仍须做；高可靠上线可考虑受控参数生成工作流，但尚未创建或声称完成。

此前健康浏览器页显示腾讯云测试域名风险提醒，已交负责人亲自点击。负责人回复“已确认”后，本轮在其已确认的标签22取得实际健康JSON并完成下节云端正例；没有自动点击提醒或修改安全设置。上文两类Agent自然语言查询与空结果/消歧已有独立实证；本机测试不替代未完成的云浏览器用例。主Agent草稿可测试这两类公开查询，但不能把待办写入、个人课表或正式培养审计宣称全部上线。

截图保存在忽略目录 `dist/d07-local-20261002/`：public-content-002-normal.png、public-plugin-health-pass.png、public-plugin-scenic-pass.png、public-plugin-scenic-limit-rejected.png、public-plugin-study-pass.png、public-plugin-study-no-fallback.png、public-plugin-publish-confirmation.png。均不包含令牌值。

本轮新增public-agent-scenic-output.png、public-agent-scenic-answer.png、public-agent-study-output.png、public-agent-study-answer.png、public-agent-study-wrong-parameter.png、public-agent-study-no-fallback.png。

刷新主Agent编排页后，草稿显示最后保存20:04:32，两个public-content查询、五个旧只读/演示工具与WF_D06工作流仍在，旧同义查询不存在；真实目录、严格字符串、工作流和身份边界提示词都保留。截图public-agent-bindings-saved.png。未点击主Agent“发布配置”。

## 负责人确认风险提示后的云端浏览器验收

- 实际健康JSON：status=ok、build_id=cloudbase-public-content-20261002-r3、personal_uploads=false，景点/资料版本与MCP查询一致。
- 按Agent返回的思源道海棠map_url进入：完成的三维地图正常呈现，34点、46建筑轮廓；自动打开对应景点详情，照片与文字加载成功。检查全校视图控件，没有改建筑或道路数据。
- 横图实际naturalWidth/Height=1920×1280，三张竖图缩略图均为1440×1920/complete=true；点击第2张主图实际为1440×1920/object-fit:contain，完整比例展示。不是只凭img标签存在判断加载。
- 按Agent返回的cpp_review_notes_with_code material_url进入：下学期程序设计已选中、正确资料详情/来源/版本/授权PDF链接均存在。主题“构造函数”实际检索5份，再点击该资料，正文定位PDF第3页，并保留OCR/历史范围警告。
- 点击“下载已授权原PDF”实际下载到 `C:/Users/29950/Downloads/study-s2-programming-f076c553a310a022.pdf`，435968字节；与仓库原件SHA256都为 `f076c553a310a02215ab24cc3cbaae9e6bbc764cf9b2bba07326450d9e4c8316`。该文件仅为本次验收下载副本，未上传或改写原件。
- 私有原件ID `study-s1-programming-7267a3cd0b2e11aa` 的云下载负例被浏览器以ERR_BLOCKED_BY_CLIENT拦截，**未取得服务器响应，不计404/权限拒绝通过**。没有换浏览器、CLI、接口或编码方式绕过。未知/私有云下载门禁及缺/错Bearer云门禁仍待独立授权验收；本地门禁测试已覆盖，不代替云实证。

新增截图：public-cloud-health-confirmed.png、public-cloud-map-scenic-landscape.png、public-cloud-map-scenic-portrait.png、public-cloud-map-full-campus.png、public-cloud-study-detail.png、public-cloud-study-search-loaded.png。`public-cloud-study-search.png` 为加载中的过程截图，不作为最终正文成功证据。

本轮无部署变更、无数据库更改、无Git提交/推送、无主Agent发布或购买；只追加验收记录。
