# A/B/C/D 共用开发入口

NK-GeniOS 是对话入口；腾讯云负责接口、文件和持久数据。工具网页只保留课表与地图导航，不把六项对话能力做成六套网页。仓库修改不会自动同步到腾讯云或学校平台，部署和平台配置需要分别更新。

2026-10-06 源码更新：新增第三项“待办日历”可视化入口，前端交互已交付；现网两入口是此前部署基线，不代表日历已上线。日历扩展接口和后端持久化仍需 D 接入，见 [待办日历前端与 D 接口对接](待办日历前端与D接口对接-2026-10-06.md)。

## 现有地址（不含秘密）

- 主 Agent：<https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg>
- 地图：<https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com/tools/map>
- 课表：<https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com/tools/timetable>
- 公开接口根地址：`https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com`
- 身份/课表/待办接口根地址：`https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com`

测试域名首次访问可能显示腾讯云提示；它不是项目的登录页。学校 Agent 仍按指定账号开放，不能因为能克隆仓库就假定取得学校或云管理员权限。负责人须提供团队/评委的准确学校账号后再加名单。不要共享负责人账号、数据库 service_role Key、用户密码或 OAuth client_secret。

## 拉取后本机开发

在仓库根目录运行以下命令；Python 3.12、Node 和项目声明的 pnpm 版本需预先安装：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
pnpm install --frozen-lockfile
pnpm --filter web test
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
Pop-Location
powershell -NoProfile -File deploy/Start-Demo.ps1 -Port 8012
```

本机演示绑定 `127.0.0.1`、只用虚构资料、个人上传关闭；SQLite 在忽略的 `backend/data/`。该模式不需要云数据库管理员密钥。页面登录及课表保存联调属于另外的身份试点，需要各自获准的普通测试账号，不以修改浏览器 SYS_USERID 代替认证。

## 公共数据直接调用

公开资料接口支持 `GET /api/v1/study/catalog` 返回完整9课程/33份原PDF元数据，以及 `GET /api/v1/study/materials/{material_id}/download` 下载允许的原文件。不要以搜索第一页代替全量目录，也不要生成模型讲解替代文件。资料是否公开以库内权限字段和后端 allowlist 为准。

赏景查询为 `GET /api/v1/scenic/spots?query=<URL编码的JSON>`，详情为 `GET /api/v1/scenic/spots/{spot_id}`。请求结构见 `contracts/api.schema.json`、`fixtures/scenic-query.demo.json`，实现与用途召回规则在 `backend/app/domains/scenic/service.py`。地点ID、地图坐标和照片必须沿用原库，不由模型编造。

云端 MCP 与个人接口仍要求相应授权。REST 公开目录能直接读，不代表所有接口可以免认证；Key 只在后台配置，禁止放入 `VITE_*`。独立开发者可以用本地虚构固定用例调试课表、待办、空闲时间与审计；更改公共契约时按 `contracts/integration-conventions.md` 的流程同步各模块。

## 分工与调节位置

- A：`knowledge/scenic/`、`knowledge/study/`、赏景/原文件接口与地图；点位用途允许交叉，不用僵硬的类别 AND 过滤自然语言意图。
- B：`packages/import-core/`、课表标准化及时间算法；推荐候选时间由后端计算。
- C：`knowledge/affairs/`、`knowledge/courses/`、培养方案及展示；不把 demo 审计当真实毕业结论。
- D：`backend/app/core/`、数据库、身份/OAuth、REST/MCP、学校工作流。通知阅读与课表联动的后续任务见 `../agent-prompts/D-通知阅读与课表联动推荐时间-任务书-2026-10-04.md`。
- 主对话与六方向路由：`prompts/main.md`、`docs/agent-prompts/`、`deploy/genios-workflows/`；实际学校配置需在草稿测试后发布，同步权限名单。

这列的是代码/数据维护位置，不是新增个人数据使用权限。

## 重建可视化工具站

使用 `deploy/Build-Visual-Tools.ps1`，必须显式选择 `public` 或 `identity` 并传入三个公开地址。脚本固定同源 API 地址为 `/`，避免空值使课表页面无法连接；输出分别为 `frontend/dist` 与 `frontend/dist-identity`。例如：

```powershell
powershell -NoProfile -File deploy/Build-Visual-Tools.ps1 `
  -Profile public `
  -GeniosUrl 'https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg' `
  -PublicContentOrigin 'https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com' `
  -TimetableOrigin 'https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com'
```

身份构建把 `-Profile` 改为 `identity`。然后调用相应 `backend/scripts/build_public_content_package.py` 或 `build_cloud_identity_package.py`，每次使用新的包名。公开服务运行 `BUILD_ID` 必须与包 manifest 的 build_id 精确相同。常规更新只上传新代码，保留现有后台凭证；不得重复执行首次建库迁移。

## 验收边界

当前公开地图及资料是已授权历史资料；真实花况、开放情况不保证实时。个人课表/待办仍以批准的虚构测试账号联调；通知通用文件读取→结构提炼→课表候选→确认保存闭环交给D任务书继续实现，不冒充现有固定用例已覆盖任意通知。

删除学校聊天历史是学校平台的功能，不在这个仓库里；重新登录后已验证指定测试会话删除成功，不能承诺通过本仓库修复学校所有 Network Error。最新线上实证见 `../evidence/platform/D12-conversation-delete-and-tool-navigation-2026-10-04.md`。
