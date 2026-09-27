# 津南校区三维地图 · 34 景点发布快照

这是 A 模块当前总图版的可运行快照，包含 46 个简化建筑组、原图道路与 36 条补充路线、旋转缩放、34 个用户录入景点及 91 张压缩实景照片。建筑平面按参考图人工对位，不是测绘成果；楼高和被遮挡建筑不保证准确。绘路工具已移除，路线作为静态 `scenic-roads.json` 随模型发布。

本目录目前独立于团队的 `ScenicPage`、公共路由和 D 的 REST/MCP 服务。可供 D 对接的契约兼容文件在 `knowledge/scenic/catalog.jinnan.json`，Agent 可读摘要在 `knowledge/scenic/KB_Scenic_Jinnan.md`。现有 `ScenicPage` 和 D 的默认查询仍使用虚构 demo 目录；提交数据不等于它们已经切换到真实景点。`data/scenic-spots.json` 是本编辑器源数据，不是公共契约。

## 本机运行

安装 Node.js 后，在本目录执行：

```powershell
npm ci --ignore-scripts --offline
npm start
```

打开 <http://127.0.0.1:5178/>。默认只读：可看模型、搜索景点、查看照片与简介；添加、编辑、删除、导入、导出入口均隐藏，写入 API 返回 403。运行 `npm test` 检查模型、道路、照片引用和只读写入边界。若 5178 端口已被原型占用，先停止原型服务，再启动本预览；不要同时运行两个实例。

Windows 免安装版位于 fork 的 `v0.2.1-jinnan-windows-preview` Release。下载 ZIP、完整解压后双击 `启动地图.cmd`，内置 Node.js 会自动挑选空闲端口并打开浏览器，无需另装 Node.js 或执行 `npm ci`。便携版强制只读、只监听本机；关闭启动窗口即可停止。打包脚本为仓库根目录的 `scripts/package-windows-portable.ps1`，只复制 Git 已跟踪的地图和照片文件、Three.js 必需运行模块，并包含 Node.js 与 Three.js 的许可证。

## 录入与交付边界

需要在自己电脑上录入景点时，先停止预览服务，再执行：

```powershell
$env:SCENIC_AUTHORING='1'
npm start
```

录入后停止服务，执行 `Remove-Item Env:SCENIC_AUTHORING -ErrorAction SilentlyContinue`，再运行 `npm start` 恢复只读。`SCENIC_AUTHORING` 只是本机开发开关，**不是身份认证**；此服务仅监听 `127.0.0.1`，不要把开启录入的实例代理到公网。

景点元数据写到已纳入 Git 的 `data/scenic-spots.json`；图片压缩后写到 `frontend/public/assets/scenic/`，每个模型最多引用 100 张。图片由本预览的 `/media/scenic/<uuid>.webp` 路由和正式前端的 `/assets/scenic/<uuid>.webp` 共同读取，不复制第二套图片。编辑后在仓库根目录运行 `python knowledge/scenic/build_jinnan.py`，重新生成契约兼容目录、图片哈希清单和 Agent 检索文本；然后执行 `npm run export:overview` 更新下载用 GLB。上传前检查 Git diff，不要把桌面原片、EXIF、未匿名化人像或未授权图片放进公开仓库。

## 数据边界

- `data/scenic-spots.json` 保留用户原文、花种／分类、建议时间、归一化坐标和照片顺序；`knowledge/scenic/catalog.jinnan.json` 是供 REST/MCP 后续接入的 `ScenicCatalog` 适配文件。
- `knowledge/scenic/KB_Scenic_Jinnan.md` 按景点组织文字，适合导入检索库。建议时间标为用户记录，**不是**实时花况；缺失描述保持空白，不补造事实。
- `knowledge/scenic/assets-manifest.jinnan.json` 记录公开 WebP 的路径、字节数和 SHA-256。私人未修原片及匹配记录只留在本机，不进 Git。
- 现有 D 服务硬编码 `catalog.demo.json`，本提交不擅自修改 D 的业务代码或公共接口；接入时由负责人决定何时切换到 `catalog.jinnan.json`，并完成来源／事实复核。
