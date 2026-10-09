# N24 工具站顶部导航配置

## 请求和原因

负责人截图中的身份工具站“赏景地图”“返回 NK-GeniOS”被禁用，原因是前端构建时没有设置
`VITE_PUBLIC_CONTENT_ORIGIN` 和 `VITE_GENIOS_AGENT_URL`。不是本人授权失效，也不需要放宽访问权限。

## 本地修复和验证

- 新增 `frontend/.env.identity`：只有公开地址和前端模式，不含凭证。
- 新增 `npm run build:identity`，固定 identity 模式并输出到 `dist-identity`，防止后续手动构建遗漏。
- 地图指向既有公开内容服务 `/tools/map`；返回按钮指向正式聊天 `/product/llm/chat/db0ulft4shhbpg8v7rgg`。
- 课表与日历仍为本人身份服务的相对路径，不把私人数据搬到公开服务。
- 配置回归 2 项通过；路由、账号切换、日历回归 21 项通过；TypeScript 与 Vite identity 构建通过。
- 沙箱依赖解析报 EPERM，正常本地权限重跑通过；无新增依赖。
- 包 `cloudbase-identity-pilot-20261007-r22.zip`，189 文件，SHA256 `587bc8819e3fb053319a7e68ba1440c445da54e666072ea7b2ca4eef46405ec2`。
- 与 r21 manifest 对比只有前端 JS 与入口 HTML 变化，后端、迁移、Dockerfile 全部相同；不执行 SQL。
- 原服务更新只改部署包与 `BUILD_ID`，保留现有密钥、长期授权、两账号名单和资源参数。

## 线上验收

- 原服务 r22/版本 022，部署任务 2300735，开始时间 2026-10-07 16:15:50（北京时间）；云控制台显示正常，镜像和 pod 检查成功。
- 从地图点课表进入身份服务，课表顶部地图和返回 Agent 链接均已启用。
- 原课表数据库 ID `schedule_B_CGKn3ecTj9LDaEypFfWqX7`、版本 2、保存时间 14:47:30 保持不变。
- 依次实点赏景地图 → 待办日历 → 返回 NK-GeniOS，均到达真实页面；日历读取现有本人记录，不执行保存或状态修改。
- 用户原课表标签已刷新为新版；截图在仓库上级工作目录 `tool-navigation-fixed-20261007.png`。
- 不提交 Git 或 PR，不修改学校 Agent 配置，不执行 SQL、不改变账号权限。
