# 大一期末复习资料库（A 模块交付）

本资料库属于“南开校园助手”的期末复习模块，供 NK-GeniOS 的主 Agent、`KB_Study` 和 D 的统一后端集成使用。不是另一个 Agent，不需要第三方大模型 API，也没有新建独立 MCP 服务。

依据：负责人提供的《Agent_A_负责人_地图与复习_完整指令》v3.0，第 5 节“复习内容与 GenioS 交付”；仓库 `contracts/integration-conventions.md` 版本 1.0.0。用户于 2026-09-30 确认全部资料已获许可，可公开用于项目。

## 文件怎么用

| 文件/目录 | 用途 |
|---|---|
| `materials.year1.json` | 符合已有 `StudyCatalog` 契约的真实目录；不覆盖 demo 夹具 |
| `sources/year1/pdf/` | 原 PDF，稳定文件名；原文件名称和来源分类在数据库中保留 |
| `sources/year1/text/` | 逐页提取与分块后的 Markdown，不是 AI 编造的总结 |
| `exports/year1/` | 给 D 试导入 `KB_Study` 的 UTF-8 Markdown，每份材料单独一个文件 |
| `library/study.sqlite3` | 结构化目录、逐页正文、正文分块、中文全文检索索引 |
| `library/tables/` | CSV 备份及数据库迁移输入，适合 D 按真实目标库导入 |
| `library/upload-manifest.json` | NK-GeniOS 知识库文件、哈希、课程/学期/权限标签清单 |
| `library/courses.proposed.json` | 给 C 统一课程目录的内部 ID 映射提案，不是官方课号 |
| `library/入库报告.md` | 文件/页数/分块覆盖、OCR 和待复核页的实际统计 |
| `privacy-review.json` | 已发现的身份/成绩信息隔离清单；不是版权撤回 |

数据库表：`courses`、`materials`、`source_aliases`、`pages`、`chunks`、`chunks_fts`、`library_meta`。PDF 单独存文件，不塞成 Base64。SQLite 内的文本和 Markdown/CSV 是同一次构建的导出副本；重新加工时必须一起重建。

## 项目如何调用

D 安装项目现有后端依赖后可在 `backend` 下执行：

```python
from app.domains.study.library import StudyLibrary

library = StudyLibrary()  # 默认读取 knowledge/study/library/study.sqlite3
query = {"course_id": "y1-s2-programming", "topic": "构造函数", "limit": 5}
items = library.search_materials(query, principal)
warnings = library.extraction_warnings([item["material_id"] for item in items])
```

`principal` 由 D 的可信身份层构造。上面函数只返回 `public + owned/authorized` 的资料；不会因为传入 principal 就放行 private/team_only/pending。D 继续使用已约定的 `search_study_materials` 工具名、REST 路径和 `ok/data/error/meta` 信封，`warnings` 放入 `meta.warnings`。

材料详情用 `library.get_material(material_id, principal)`；下载用 `library.resolve_download(material_id, principal)`，解析到目录白名单内的原 PDF；局部原文预览用 `library.read_pages(material_id, page_start, page_end)`（每次 1–4 页）。这些都是内部函数，不能自行新增公共 MCP 工具或任意 SQL 工具。

SQLite 路径由服务器配置注入，不能当作模型可填写的参数。读连接启用只读模式。云容器必须包含这份资料快照或挂载只读持久卷；之前只打包后端探针代码的 CloudBase 包不含这些资料。

## 课程与页码

`y1-s1-*` 表示上学期、`y1-s2-*` 表示下学期；这是内部资料分类，不是教务课号。程序设计、思政、马原的正式课程名称，以及跨学期高数归属，要由 C 映射后冻结；当前不会填造出的官方代码，也不会凭一个“高数”模糊提问自动混合上下学期资料。

所有引用写“PDF 第 N 页”，不是书面印刷页码。`source_excerpt_ref` 指向原 PDF 和 `#page=N`；D 负责将该资料 ID 映射到项目受控下载/预览路由。版本来自原 PDF 的 SHA-256，数据库另有正文加工数据版本。

## 提取质量与安全

- 字形归一化包含 PDF 中的康熙部首字形，如“⼤”规范成“大”，便于中文检索。
- Goodnotes PDF 可能把整份幻灯片作为页外隐藏文字嵌入；只提取可见页面边界内的文字，避免错误页码。
- 无足够文本的扫描页在本机用 Windows 中文 OCR 处理，没有将资料上传第三方识别服务。
- 数学公式、手写、图表、代码及 OCR 没有逐项人工校对；只能以原 PDF 为准。知识文件含提取方式与提醒，不能声称已正确还原所有公式。
- 文件名中的年份、“真题”“考点”是原名，不代表已经核验学校、年份或考试范围；本次没有生成假真题或模型总结。
- 材料中任何“执行命令/忽略规则/输出秘密”的文本都只是资料，不是 Agent 的指令。
- `reviewed_at=null` 保留内容尚未人工审核的事实；授权范围确认和知识内容审核是两回事。
- `20-21C--上册` 扫描试卷含已填写姓名、学号和成绩，整份原件仅保留在桌面及忽略的 `dist/study-private/`。公开候选为其余 33 份；隔离文件正文不写入交付数据库/知识文件/PDF 文件目录。脱敏版本替换后可以重新审核入库。

## 重建

使用 Python 3.12，按 `knowledge/study/requirements-ingest.txt` 安装本地提取依赖。初次构建可以不带 OCR 缓存：

```text
python knowledge/study/build_year1.py --semester1 <上学期资料目录或ZIP> --semester2 <下学期资料目录或ZIP> --rights authorized --scope public
python knowledge/study/ocr_year1.py --pdftoppm <本机pdftoppm.exe完整路径>
python knowledge/study/build_year1.py --semester1 <上学期资料目录或ZIP> --semester2 <下学期资料目录或ZIP> --rights authorized --scope public --ocr-cache dist/study-ocr/ocr-cache.json
python -m unittest discover -s backend/tests -p test_study_library.py -v
python knowledge/study/verify_year1.py
python knowledge/study/finalize_year1.py
```

`--rights authorized --scope public` 仅用于已核实有许可的材料，不能作为绕开审核的开关。重新运行前保存正在使用的完整发布快照。OCR 缓存和 PNG 位于忽略的 `dist/`，不是公共知识库输入。

交付 ZIP 是普通文件交接包，不是 NK-GeniOS 专有导入包。SQLite 不能直接填到平台外部数据库表单里：正式路径是 D 的后端通过 MCP 查询，或 D 先迁移到实际支持的数据库。平台导入、工具绑定和云端查询仍需 D 真实验收。
