# D10 云身份登录来源检查

## 后续停留点：新 OAuth 凭据由负责人填写/提交

负责人回复继续后，沿用此前明确的两普通账号、虚构本人数据、demo:read、主 Agent 草稿范围准备配置，没有公开发布或开启个人上传。学校创建插件表单仍未提交、client_secret为空。云身份服务005/r7仍是生效版本；在“服务配置/编辑”表单暂存CLOUD_OAUTH_PILOT_ENABLED=true，以及固定OAUTH_CLIENT_ID、AGENT_PAIRING_AUDIENCE、OAUTH_REDIRECT_URI，新增空白OAUTH_CLIENT_SECRET_HASH。没有点击保存，不能把表单中的true认作线上OAuth已启用。

新增deploy/oauth-credential-helper：loopback固定静态文件白名单、本机WebCrypto随机生成/SHA-256；只在负责人主动点击时生成，未由自动化点击生成。无外网请求、存储或自动提交，CSP禁止connect/form/frame。Node三项测试通过（只使用测试常量/假随机源，没有签发真实凭据）。页面http://127.0.0.1:8023/已打开，所有凭据字段空白。

负责人需亲自生成新客户端密钥，把原文填入学校client_secret并点确定；将同一密钥的摘要填入身份服务OAUTH_CLIENT_SECRET_HASH，并亲自保存/确认云配置。这是新增认证凭据的交接，不能由自动化读取剪贴板、代填或代提交。后台既有API Key选择未改动，未读取其值或延长期限。

截图oauth-client-school-handoff-20261003.png、oauth-client-cloud-handoff-20261003.png、oauth-credential-helper-blank-20261003.png均在忽略目录，保存于字段空白时。学校插件、OAuth用户grant、平台S256/state/token保密与双账号Agent验收尚未完成。凭据准备不是接通证据。

## 2026-10-03 12:35 更新：域名已添加，A 登录已通过

负责人自行提交精确域名后，控制台列表已出现 `nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com`，没有新增通配符。刷新现有登录组件后，普通测试 A 实际登录返回“nku-demo-a 已经腾讯云在线核验”，页面显示已有后端测试会话；密码框已清空。OAuth 尚未开启，未与 Agent 配对。

同一浏览器的新课表导入标签页已恢复当前演示工作区，并实际取得版本 1 的未保存课表草稿。此时尚不能声称 B 隔离、保存读回或服务重启验收完成；下方未提交/失败记录是此前历史状态。

## 2026-10-03 12:39 云业务实测

- A 的固定虚构课表版本 1 已确认保存，页面明确“已保存并从数据库读回”，返回真实 schedule_id。
- A 的虚构活动草稿经显式确认后返回真实 task_id，已保存记录 1 条；再次提交按钮禁用。本人时间检查读到已保存安排，返回 3 处冲突并保留课表完整性未确认说明，不等于实际有空或完整课表。
- 退出 A 后，B 用现有普通账号实际通过腾讯云在线核验。B 打开 A 的原草稿链接返回 NOT_FOUND、本人列表 0 条；没有课表时检查返回 NOT_FOUND / Save your fixture timetable first，没有借用 A 或公共课表。
- 当前未做云服务重启，未开启 OAuth，未把上述浏览器业务通过混称学校 Agent 配对完成。

忽略目录截图：cloud-identity-domain-added-20261003.png、cloud-identity-a-schedule-saved-20261003.png、cloud-identity-a-task-saved-20261003.png、cloud-identity-b-rejects-a-draft-20261003.png。截图仅固定虚构测试记录，不含密码、令牌、后台 Key。

## 12:49 修复部署进行中

B 独立保存虚构截止任务，取得真实 task_id、本人记录1条。退出B重登A后，A仍只读回自己12:37:30保存的原活动，B草稿地址返回NOT_FOUND，双向草稿隔离通过。

发现新标签 /tools/timetable 未接后端会话恢复（仍读旧标签缓存）。本地r7复用 useBrowserSession 并按 workspace key 重建视图，核验前/依赖错误闭锁、401要求重新登录；新增3项门禁测试。完整前端110项、tsc和生产构建通过，复习代码38项+33清单通过。后端与SQL未改。

r7包164项manifest全部匹配，未包含私有目录。包SHA256：48ef76184863e14aaa7b70f1dbf9eaf771e41aef8530c08eb1efcdbf4ac0e69b。上传现有身份服务，BUILD_ID改为identity-pilot-20261003-r7，8080/OAuth=false/个人上传=false不变；后台密钥仅沿用原配置，未读取、创建或延长。发布确认页后实际进入005/task2279540，开始2026-10-03 12:49:15，仍构建中。控制台确认按钮调用返回已无该元素，不能仅以此工具调用认定提交成功；实际部署详情才是已提交依据。

尚未把005构建算作生效、云重启读回或新课表页通过。学校逐用户OAuth仍未启用，需新的明确授权与负责人亲自创建/填写新客户端凭据。

## 12:54 更新：005 生效，新容器读回通过

刷新部署详情实际状态正常，服务生效表为005、100%流量、1实例。新开课表标签页先显示服务器会话核验，随后读回与更新前相同的schedule_id、版本1、保存时间12:35:56。A待办页刷新仍只有12:37:30的原活动，B草稿地址仍NOT_FOUND。因此完成的是004→005新容器更新后的原记录读回，不是手动重启按钮测试或学校OAuth实证。

课表页实际空档计算通过，输入窗口为默认2026-09-07、最少20分钟，返回480/30/730分钟三段及selected_weeks/unknown覆盖提示。自动化尝试改为9月21日时原生日期填充没有可靠更新React状态，点击后回到9月7日；不能把这次结果说成9月21日测试。尚未确认这是浏览器输入驱动还是产品事件问题，后续用正常日期选择器复验，未以脚本派发事件绕过。

497项完整后端回归退出0（1项第三方弃用警告），110项前端、tsc、生产构建、复习38项+33清单通过。包及服务门禁不变。云A/B在线核验、显式保存、跨标签会话、重登读回、双向草稿隔离和更新新容器读回已有实证；主Agent逐用户OAuth配对未完成，个人上传仍关闭。

截图cloud-identity-r7-timetable-readback-20261003.png、cloud-identity-r7-a-task-readback-20261003.png在忽略目录。下一步需要行动时确认只在两个虚构普通账号范围创建独立OAuth客户端/草稿插件，先demo:read（个人保存仍须本人复核，生产数据不开）；新凭据由负责人直接填写，不发送聊天。S256/state/回调拒绝链若平台无法支持须保持关闭，不能降级为SYS_USERID文本或共享令牌冒充逐用户身份。

## 本轮停留点：只读 OAuth 表单未提交

学校会话已正常过期并用现有飞连一键登录恢复，没有索取学校密码。团队自定义插件“创建插件”表单仅填写名称campus-identity-pilot-read、公开服务origin、预定client_id=nku-genios-identity-read-pilot-20261003、Authentication Code、精确authorize/token地址及demo:read；学校固定回调读回为https://coze.nankai.edu.cn/product/llm/info/oauth。client_secret留空、refresh_token_url留空、没有点击确定，后台OAuth开关未改，没有实际新增插件/客户端或grant。截图genios-identity-oauth-read-pending-20261003.png已展示本次权限目标，等待行动时授权；凭据创建/输入/提交必须由负责人亲自完成。

保持004/r6服务及旧数据库不变。只使用负责人已批准的普通测试账号及虚构数据，未开放个人上传、OAuth、注册或新增管理员权限。没有读取或延长后台短期Key。

## 实际观察

云待办页可打开，但明确显示AUTH_REQUIRED、当前浏览器会话失效，不是登录成功证据。普通A账号在现有云登录页重试后仍返回SERVICE_ERROR · unreachable，密码已由页面清空，未取得后端会话。仅提取浏览器日志的固定类别布尔值，有网络Failed to fetch类警告，没有足以确认CORS/CSP/5xx的证据，不保存原始日志或凭证。

控制台004仍正常、100%流量、1实例。身份认证/登录方式加载后“用户名密码”已启用；不以加载中的默认文案判断未启用。环境存在其他项目及原有匿名登录设置，未修改这些全局开关。

HTTP网关/跨域设置现有列表没有nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com。添加授权域名弹窗明确要求网页身份验证来源进入白名单，并提示约10分钟生效。

官方参考：[CloudBase Web v3 身份认证](https://docs.cloudbase.net/api-reference/webv3/authentication)、[Web v2 错误码与安全域名](https://docs.cloudbase.net/api-reference/webv2/authentication)。unreachable表示网络错误；安全域名通常涉及permission_denied。缺少来源配置确需检查，但当前没有证据证明它是全部故障的唯一根因。

## 待确认的精确变更

只添加上述完整身份服务域名，不使用泛域名、IP或通配符。该变更允许此来源网页使用本环境身份认证，仍需账号与数据库权限核验；属于安全敏感授权，按computer-use行动时确认要求先征得负责人同意。

已填写域名，表单通过格式检查；尚未点击“确定”。截图cloud-identity-domain-confirm-20261003.png保存在忽略目录dist/d07-local-20261002，并向负责人展示确认目标。获确认后提交并核对列表，按正常生效时间做一次普通账号登录，再继续两账号隔离与保存读回验收。不得用本地Mock或运行状态替代云端验收。
