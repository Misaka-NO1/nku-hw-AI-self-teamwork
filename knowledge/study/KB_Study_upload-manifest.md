# KB_Study 公开候选上传清单

| 文件 | 内容 | 权限 | 当前状态 |
| --- | --- | --- | --- |
| `exports/KB_Study_demo.md` | 自创笔记正文分块，包含材料 ID、版本、课程 ID、标题、无页码声明与原文定位 | owned/public | 本地可生成；D 需验证平台能否导入及检索引用 |
| `materials.json` 中的 `demo-index-02` | 只有目录索引 | public_link_only/public | 不进正文知识库 |
| `demo-private-03` | 私有可见性测试条目 | owned/private | 不进公开导出 |
| `demo-pending-04` | 权限未确认测试条目 | pending/public | 不进公开导出 |

生成命令（在 `backend/`）：`python -m app.domains.study.export`。来源文件为 `knowledge/study/sources/demo-note-01.md`。导出 Markdown 只是通用候选，D 必须在 NK-GeniOS 实际验证导入格式、分段和引用效果后才能标记平台通过。
