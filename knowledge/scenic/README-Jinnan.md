# 津南景点数据交接

本目录新增的 `catalog.jinnan.json` 是按 `contracts/core.schema.json` 中 `ScenicCatalog` 结构转换的 34 个用户录入景点；`KB_Scenic_Jinnan.md` 是面向 Agent 的逐点检索文本；`assets-manifest.jinnan.json` 是 91 张发布图的 SHA-256 清单。原始录入数据位于 `frontend/src/features/scenic/three-preview/data/scenic-spots.json`，展示图位于 `frontend/public/assets/scenic/`，完整三维地图位于 `frontend/src/features/scenic/three-preview/`。

查询时优先以 `spot_id` 关联，按 `name`、`tags`、`historical_bloom_months` 过滤；返回点位时可给出 `x_norm`、`y_norm` 和照片路径。月份由用户填写的建议观赏时间转换，只代表历史/经验性建议，不代表当前开花。`observation` 全部为 `null`，Agent 不应推断实时花况。文字和植物种类未逐条独立核实，`data_status` 为 `needs_verification`；原文保留在源数据和 Markdown 中，不擅自补充空白内容。

当前 D 服务默认仍加载 `catalog.demo.json`，前端 `ScenicPage` 默认仍使用演示目录；要正式供 REST/MCP 查询和主页面展示，需要负责人单独将上述真实数据源接入并回归测试。此处没有改动公共接口或 D 的业务代码。原始 2025 地图参考图和未修图照片不随 Git 发布。

更新录入后，在仓库根目录运行 `python knowledge/scenic/build_jinnan.py` 重建目录和文本；再于 `frontend/src/features/scenic/three-preview` 执行 `npm test` 和 `npm run export:overview`。提交前核对 `assets-manifest.jinnan.json` 的每张图片、肖像隐私与版权状态。
