# 津南校区三维地图 · 独立只读预览

这是 A 模块当前总图版的可运行快照，包含 46 个简化建筑轮廓、道路/水面、旋转缩放、景点搜索、实景照片详情及本机录入后端。原始高德截图、用户参考图、本机高德代理和未核验的真实景点资料**没有**放入此目录。建筑平面按参考图人工对位，不是测绘成果；楼高和被遮挡建筑不保证准确。

本目录目前独立于团队的 `ScenicPage`、公共路由和 D 的 REST/MCP 服务。提交它是为了先保存并审查模型与交互代码，**不代表**三维地图已上线或 Agent 已能查询真实景点。现有 `ScenicPage` 仍使用虚构 demo 目录；正式接入需要适配 `contracts/core.schema.json` 中的 `ScenicCatalog`，不能直接把本预览的 `data/scenic-spots.json` 当公共契约。

## 本机运行

安装 Node.js 后，在本目录执行：

```powershell
npm ci --ignore-scripts --offline --cache .npm-cache
npm start
```

打开 <http://127.0.0.1:5178/>。默认只读：可看模型、搜索景点、查看照片与简介；添加、编辑、删除、导入、导出入口均隐藏，写入 API 返回 403。运行 `npm test` 检查旋转中心与只读写入边界。若 5178 端口已被原型占用，先停止原型服务，再启动本预览；不要同时运行两个实例。

## 录入与交付边界

需要在自己电脑上录入景点时，先停止预览服务，再执行：

```powershell
$env:SCENIC_AUTHORING='1'
npm start
```

录入后停止服务，执行 `Remove-Item Env:SCENIC_AUTHORING -ErrorAction SilentlyContinue`，再运行 `npm start` 恢复只读。`SCENIC_AUTHORING` 只是本机开发开关，**不是身份认证**；此服务仅监听 `127.0.0.1`，不要把开启录入的实例代理到公网。

景点元数据写到忽略 Git 的 `data/scenic-spots.json`；图片压缩后写到 `data/scenic-photos/`，每个模型最多引用 100 张。导出的景点 JSON 不包含图片二进制。迁移前须同时备份 JSON 和图片目录。照片、花期与来源核验后，再把数据转换为正式 `ScenicCatalog`、生成知识库文本，并由 D 将既定 `search_scenic_spots` 工具接到同一数据源；未经授权或含私人信息的图片不能直接提交公开仓库。
