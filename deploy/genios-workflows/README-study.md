# D09 公开复习解释工作流（团队联调版 0.1.0）

> 2026-10-09：用户取消复习正文读取与讲解。主 Agent 草稿解除 `WF_StudyAnswer` 和 `KB_Study` 引用，仅保留目录查询与原文件下载；本轮未发布。下文和旧节点代码仅为历史实现，不应按旧说明重新绑定。当前范围见 `prompts/study-answer.md` 和已更新的追加模板。

目标：通过NK-GeniOS主Agent使用公开复习库，而不是要求用户到独立网页完成问答。网页/公开资料接口负责精确资料索引与PDF访问；知识库负责正文召回；工作流负责课程来源过滤和有来源的解释。

数据版本：y1-070600fb47f92e70，33份公开材料。知识库ID：01a0ff86-b143-711e-8853-dd19de8952ca。工作流ID：db06eo54shhbpg8v3na0。

## 目标连线与变量

```text
Start: question(String必填), course_id(String必填), material_id(String可选)
→ 知识库检索01: query←Start.question, KB_Study, 5条, 0.50, 上下文扩展关闭
→ 代码01: outputList←检索.outputList, question/course_id/material_id←Start
   handler源码study-context-handler.js
   输出status/context/sources_json/question/data_version全部String
→ 大模型01: context/status/question←代码01对应输出
   系统/用户提示词见study-answer-*-prompt.txt，输出纯文本raw_output
→ 代码02: status/sources_json←代码01, answer←大模型01.raw_output
   handler源码study-answer-guard.js，输出result Object
→ End: result(Object)←代码02.result
```

学校完整链路已完成正向、指定材料、未知课程/材料、跨学期、无正文、重复运行与刷新配置读回。2026-10-03 11:53:02发布团队联调版0.1.0，11:53:36绑定主Agent草稿；主Agent本次实际调用返回grounded及第3/18页配对引用，执行详情确认三个直接入参与5个真实来源。主Agent未公开发布，不代表全部业务完成。

## 来源限制

- 内部课程ID不是官方课号；缺少学期必须由Agent澄清，不推测。
- 检索是语义召回，代码过滤为召回后的精确白名单，不承诺库内硬性预过滤或100%召回率。
- ID、课程、完整版本、chunk、页来源、文件名必须一致；目录/索引段、未知/私有材料不用于正文答案。
- 学校将Markdown多行元数据合并成一段，解析同时接受行式和已知字段分隔的内联格式，冲突字段仍拒绝。material_id可选，空值按课程；指定未知/私有/其他课程材料返回unknown_material，不回退相似文件。
- 回答必须使用实际[material_id@page]配对引用，校验失败不展示模型文本。保护不等于事实自动核验，需对照PDF。
- 不输出元数据内部签名URL，不拼仓库路径为下载地址。精确公开PDF链接继续使用已有公开资料工具实际返回。
- 历史资料不是今年考试范围；OCR、公式、图表、代码未逐页人工校验。演示验收笔记已禁用。

## 本地测试

```powershell
node deploy/genios-workflows/test-study-handlers.cjs
```

38项本地检查、33份逐份清单匹配通过；学校上述完整链路实操另有记录。代码02单节点构造伪造页码测试返回citation_check_failed，该测试是构造夹具，不是真实检索端到端。主Agent调用约束追加模板为study-agent-prompt-append.txt，不替换既有安全规则。实际平台记录见docs/evidence/platform/D09-study-knowledge-2026-10-03.md。
