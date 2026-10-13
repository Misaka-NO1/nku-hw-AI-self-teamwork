# 南开校园助手

这是团队共享仓库。开始任何模块开发前，先阅读：

- [`contracts/integration-conventions.md`](contracts/integration-conventions.md)：跨 Agent 的唯一命名、路由、配置和函数映射约定
- [`contracts/api.schema.json`](contracts/api.schema.json)：统一 API 信封、查询参数、时间结果和培养方案审计结果
- [`contracts/core.schema.json`](contracts/core.schema.json)：原始任务包内嵌的共享业务数据结构
- [`deploy/.env.example`](deploy/.env.example)：非秘密配置模板
- [`fixtures/`](fixtures/)：明确标注的虚构共享测试数据

个人任务书中的内部函数可以保留各自命名，但跨 REST、MCP、前端和扩展的边界必须按上述契约转换。公共 JSON 字段统一使用 `snake_case`。

## 免账号密码使用、固定设备码与 Agent 关联（团队共用身份链路）

这不是废弃的演示功能，也不是学校 SSO。2026-10-12 最新实现以 Agent 隐藏的固定 GeniOS 平台身份查找唯一私有空间：已有账号只复用原空间，真正首次使用经本人明确确认才免注册创建空白空间，随后绑定浏览器。固定 `DEV-…` 码只定位设备，不是身份或密码；换浏览器或无痕窗口不代表新账号。已关联平台身份的 `existing_space` 经本人确认直接使用 `onboard_my_browser(intent=bind)`；只有 `legacy_authorization_required` 才用本人的原有效 OAuth 授权关联尚未接入平台身份的旧账号，不合并或删除旧数据。不能用共享 MCP token、学校登录状态或聊天中的账号文字替代可信身份。

- [完整流程、配置、源码索引与验收](docs/browser-visitor-rollout.md)
- [本轮交接：已有 PR 与缺失补交范围](docs/handoffs/browser-visitor-device-flow-2026-10-10.md)
- [最新交付与 PR 关系：最终身份绑定流程](docs/handoffs/native-identity-final-delivery-2026-10-12.md)
- [实际上线与验收记录（包含历史过程）](docs/handoffs/genios-native-identity-intake-2026-10-11.md)
- [旧版身份优先守卫（历史阶段）](docs/handoffs/unified-private-space-onboarding-2026-10-11.md)
- [正式 Agent 实际追加规则](deploy/genios-workflows/native-identity-agent-live-append.txt)
- [最新修复：绑定路径分流、共用拓展 0.3.4 与安装指引](docs/handoffs/shared-reader-native-binding-fix-2026-10-12.md)

维护课表（B）、日历（D）或公共页面（C）时须保留这套身份入口、Cookie 恢复、owner 校验及撤销行为。课表文件上传修复另见 PR #15；这套身份链路不属于课表解析器，不要因本地未启用配置而删除它。

## 前端工具站（C 维护）

一个 Vite + React + TypeScript 单页应用，包名 `web`，路由统一前缀 `/tools/`：

```bash
pnpm install --frozen-lockfile
pnpm dev          # 开发服务器
pnpm test         # Vitest 单元测试
pnpm build        # 类型检查 + 生产构建
```

构建变量见 `frontend/.env.example`：前端只用 `VITE_API_BASE_URL` 访问后端；`VITE_GENIOS_AGENT_URL` 未配置时“返回 NK-GeniOS”按钮禁用。后端命令见 `backend/README.md`。
