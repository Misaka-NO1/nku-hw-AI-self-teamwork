# 共用拓展下载、安装指引与原空间绑定分流修复

## 与上一轮的关系和归属

本轮基于团队 main `386be90`（已包含 [PR #20](https://github.com/Misaka-NO1/nku-hw-AI-self-teamwork/pull/20)）。不重复提交上一轮学分功能、在读字段迁移或清除方案，也没有再次清除任何数据。

- **给 B 的课表补充**：导入页使用有版本号的共用拓展下载，安装步骤直接可见；不改变课表提取、校历、上传、预览确认或时间算法。
- **C 的培养计划接入补充**：第 6 项对话先说明安装、计划完成情况导出 JSON、上传给 Agent 和下一轮确认保存；保留六选四、艺术要求、在读与缺口等原规则。旧 degree 页面仅作为安装/回到 Agent 的兼容说明，不新增独立培养计划业务界面。
- **D / 共用身份基础设施**：修复 Agent 对原空间绑定和旧账号迁移的错误分流；新增回归测试和离线提示词修复工具，不弱化身份验证、OAuth 或数据库权限。

## 已证实的绑定故障原因

真实草稿调用树中，lookup 返回 `existing_space` 后，本人的“绑定到原私有空间”确认却触发 `attest_my_platform_identity → associate_my_original_space`，返回 403。后一工具是旧 OAuth 账号接入平台身份的迁移工具，不是已关联空间的新浏览器绑定工具。

历史正文中“所有设备绑定先 OAuth / bind_my_browser”的高优先级段落，与后加的简短 native 规则冲突；“原空间”措辞也没有明确区分状态。只读核验显示测试设备对应的平台账号已有身份映射和原空间，设备没有归属冲突，但没有有效旧 OAuth grant。因此错走旧迁移会被安全守卫拒绝。此证据解释本次复现的绑定 403，不能据此宣称历史每一个 401 都有同一原因。

这不是靠重试碰巧恢复：修复前后使用同一浏览器、同样的自然语言确认；修复后调用树仅使用 `onboard_my_browser`，得到 `browser_authorized, has_space=true, created=false`，原浏览器领取并显示绑定完成。未在确认语句里人为指定工具。

新规则按本次真实返回状态分流：

| lookup 状态 | 本人确认后的路径 | 禁止的误用 |
| --- | --- | --- |
| `existing_space` | `onboard_my_browser(intent=bind, confirmed=true)` | 不调用旧迁移，不需要 OAuth 或 attest 来绑定 |
| `legacy_authorization_required` | 本轮真实签名 + 本人原有效 OAuth + `associate_my_original_space` | 不能创建替代空间绕过原授权 |
| `first_use_confirmation` | 先核对旧账号历史，真正首次且明确确认才 create | 不能因换浏览器就当成新账号 |

lookup 不绑定；`browser_authorized` 还不等于浏览器登录，必须回生成设备码的浏览器领取。Agent 读写私人数据仍需要有效本人 OAuth 和本轮身份签名。隐藏的固定 `SYS_USERID`、服务凭据、HTTP 接口、参数和权限范围均未改变。

## 提示词和插件交接

- 最新分流块：`deploy/genios-workflows/native-identity-agent-live-append.txt`。
- 较完整设计参考：`native-identity-agent-append.txt`。
- 原生插件已发布工具说明更新；`native-onboarding-tools.openapi.json` 同步该说明。接口、认证、参数及隐藏身份配置未变。
- `native-oauth-tools.configuration.json` 更新的是仓库兼容说明，明确仅 legacy 状态可迁移；本轮未重发原 OAuth 插件的认证配置。
- `repair_native_binding_prompt.py` 是离线工具：对有精确历史锚点的导出提示词删除冲突绑定段、替换最终分流块，保留其他非空业务段落；缺锚点、歧义、超过 65,535 UTF-8 字节均失败，不覆盖输入或已有输出。

用法（先人工核对导出内容，无凭据）：

```powershell
python deploy/genios-workflows/repair_native_binding_prompt.py exported-prompt.txt repaired-prompt.txt
```

不要只在旧正文末尾再追加一个更短规则；必须移除冲突绑定段。工具只处理匹配的历史格式，不是通用提示词转换器，也不应对已修复正文重复运行。平台完整业务提示词不含在此次提交中；正文仍包含原有公开业务和学分规则。

## 共用拓展 0.3.4

新增统一 `ReaderInstallGuide`，课表导入页和旧 degree 说明页复用。新链接 `/assets/campus-reader-0.3.4.zip`，旧 `/assets/campus-schedule-reader.zip` 保留为同一二进制兼容别名。打包器从 manifest 版本生成新路径，并检查版本格式；包只包含原公开白名单文件。

安装指引直接可见：下载解压、Chrome/Edge 扩展管理页、开发者模式、加载含 manifest.json 的目录、停用旧副本、核对版本和刷新教务页。课表页“读取并导入课表”；计划完成情况页“导出计划完成情况 JSON”。学分 JSON 发 Agent 预览、下轮本人确认才保存，课表 JSON 在工具站导入。手机可上传电脑导出的 JSON，不可在手机 Chrome 或内置浏览器安装此电脑扩展。

本轮未修改扩展提取逻辑或权限，0.3.4 是下载入口/安装指引交付版本。此前检查到的线上包已为共用 0.3.3；没有足够证据把用户遇到的旧下载全部归因于 CDN 缓存。现在通过明确版本路径、可见版本号和实际下载校验消除歧义。

实际线上下载的 0.3.4 ZIP：manifest 名称为“南开校园助手 · 教务课表与培养计划”，同时包含课表和计划完成情况白名单；SHA-256 与本地包一致：

`f2b4edb2f9c011453faf2ac869d2a0d1a627cfe4e641d3aed3bd815c53efcecb`

## 已上线与真人验收

- 腾讯云原 `nku-campus-identity-pilot`：**064 / 正常 / 100% 流量 / 1 实例**，开始时间 2026-10-12 23:21:09；不改套餐、规格或实例设置。
- 发布包 `cloudbase-identity-pilot-20261012-r54-reader-install-guide.zip`，209 个白名单文件，SHA-256：`17ab6ee1d0f4dab62459520e8584e8a572014263699fae93120bcde60190f713`。
- 容器镜像 digest：`ecce7d0ae8b314c6cefadc79bd556317949b77ff6f95a442cf0ade78e740fe6d`。
- 正式 Agent **v0.2.25**，23:21:57 提交渠道申请，23:25:06 审批通过，发布页已显示 Web 服务运行中 v0.2.25。v0.2.24 是此前安装指引版本，不能作为绑定修复的最终版本。
- 正式新会话先只查原空间，再使用本人已授权的当前测试浏览器作自然语言绑定确认：lookup 成功，bind 返回 `browser_authorized / created=false`；原浏览器显示“本浏览器已绑定 · 使用账号原空间”，重新打开仍保持绑定。
- 正式新会话询问第 6 项第一次安装/导出：返回 0.3.4 下载、解压、Chrome/Edge、开发者模式、加载目录、停用旧版、计划完成情况、JSON 上传和本人确认步骤。一次流式页面显示网络中断，刷新后完整回复可见；不把学校页面网络中断当成身份校验成功或失败的证据。
- 线上导入页的安装区无需展开，即可看到版本下载与完整步骤。

## 测试与安全边界

- 前端全量：264 项、31 文件通过；最后文案调整后的安装组件测试和 identity 构建再次通过。
- 扩展：41 项、10 文件通过，verify/build 通过。
- 身份 HTTP / 隔离真实 PostgreSQL + 输出契约：21 项通过，新增“已有空间新浏览器无 OAuth 迁移即可绑定、未确认拒绝、原浏览器领取复用同一空间、无新增 owner、签名本身不能读取 OAuth 数据”回归。
- 提示词修复与白名单打包：12 项通过；包含最终换行的 65,535 字节边界测试。
- `git diff --check` 通过。

本轮只新增测试和分流/安装文案，**没有修改后端运行接口或 SQL、执行迁移或清除数据**。前端部署包含已有迁移文件不代表执行它们；不要拉取后重跑任何旧初始化或清除脚本。包、个人数据、凭据、完整私有调用记录、截图与缓存不提交 GitHub。

真人闭环限本人已存在平台空间及获明确许可的当前浏览器。其他真实账号、真正首次创建及旧账号迁移未在此轮重复真人验收；这些分支保留本地隔离测试，不能据此保证所有用户已验收。已曝光的专用凭据轮换风险仍存在，负责人选择暂不轮换，本轮未读取或更换它。

回退应按实际故障单独审阅：安装 UI 可恢复上一构建；身份路由不要退回已经证实错误的通用 OAuth 绑定段。无需回滚或重跑数据库迁移，不通过删除空间“解决”绑定失败。
