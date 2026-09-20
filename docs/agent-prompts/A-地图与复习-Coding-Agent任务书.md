# A 任务书：地图与期末复习

> 这份文件是给 Coding Agent 的完整任务说明。交给 AI 后，AI 负责检查仓库、写代码、运行测试和汇报结果。人员本人不需要会写代码，也不需要手工修改代码。

## 直接交给 Coding Agent 的开场指令

```text
你是本仓库的 A 模块 Coding Agent。

我不会写代码，请你直接完成任务，不要只给我教程或代码片段。你需要自己检查仓库、创建和修改文件、运行测试，并在最后告诉我实际完成了什么。

开始前先阅读：
1. README.md
2. contracts/integration-conventions.md
3. contracts/api.schema.json
4. 本文件全部内容

如果发现现有代码，先检查再修改，不要覆盖其他人的有效实现。如果缺少依赖、素材、登录权限或真实数据，不要编造；先记录 WAITING_HUMAN，然后继续完成不依赖这些条件的部分。

现在开始执行 A01 到 A08，完成后再根据实际结果继续 A09 到 A12。
```

## 你的角色

你负责“赏景地图”和“期末复习”两个模块，不负责整站、用户系统、平台发布、课表算法或培养方案算法。

## 允许修改的范围

```text
frontend/src/features/scenic/
frontend/src/features/study/
backend/app/domains/scenic/
backend/app/domains/study/
knowledge/scenic/
knowledge/study/
prompts/scenic-routing.md
prompts/study-answer.md
对应测试
docs/handoffs/A-progress.md
docs/blockers/A-*.md
```

不要直接修改公共路由、公共样式、数据库、认证、MCP 注册、B 的课表算法、C 的学分算法、D 的部署代码。

## 必须完成的功能

### 1. 地图模块

实现一个名为 `ScenicPage` 的页面，支持：

- 校园地图总览
- 点位列表和标签筛选
- 点位标记
- 点位详情卡片
- 照片和简介展示
- 从总览进入点位，再返回总览
- 通过 `spot_id` 深链接打开点位
- 点位不存在时显示明确错误，不随机替换成其他点位
- 没有底图或照片时显示待提供素材，不伪造真实校园图片

实现并测试：

```text
toMapPoint(x_norm, y_norm, width, height)
fromMapPoint(y, x, width, height)
validateSpot(spot)
```

必须覆盖四角、中心点、越界坐标和不同图片尺寸。

### 2. 复习模块

实现一个名为 `StudyPage` 的页面，支持：

- 按 `course_id` 筛选课程
- 按主题搜索材料
- 展示材料名称、版本、权限和正文可用状态
- 区分“只有索引”和“有正文”
- 展示来源卡片和定位信息
- 材料不存在或无权限时显示错误
- 没有正文时不能声称完成基于正文的总结

实现并测试以下内部函数：

```python
search_spots(query, catalog)
get_spot(spot_id, catalog)
search_materials(query, principal, catalog)
resolve_download(material_id, principal, catalog)
```

跨接口名称必须按仓库契约转换：

```text
search_spots      → search_scenic_spots
search_materials  → search_study_materials
```

## 数据和安全要求

- JSON 字段使用 `snake_case`。
- 点位只接受已有的 `spot_id`。
- 材料只接受已有的 `material_id`。
- `private`、`pending` 材料不得进入公开结果。
- 不允许任意文件路径、任意 URL 或 `javascript:` 链接。
- 历史花期不能写成实时花况。
- 所有虚构资料必须明显标记为 demo。
- 不抓取未授权课件，不生成真实考试题并称为真题。

## 测试要求

至少完成：

```text
MAP-01 坐标四角和中心
MAP-02 合法和非法深链接
MAP-03 无底图/无照片空状态
MAP-04 历史花期不能表示实时花况
STUDY-01 递归材料正文检索
STUDY-02 索引材料不能支持正文总结
STUDY-03 未知课程和主题返回未找到
STUDY-04 private/pending 材料不可公开
STUDY-05 无页码时不能编造页码
```

## 完成后的汇报格式

完成后请在 `docs/handoffs/A-progress.md` 写入：

```text
任务状态：LOCAL_PASS / WAITING_HUMAN / 未完成
修改文件：
新增页面和函数：
接口契约版本：
测试命令：
测试实际结果：
未解决问题：
需要人工提供的素材或权限：
给 C 的下一步：
给 D 的下一步：
```

不要把“代码已写”说成“平台已接入”。没有真实素材时要明确写 demo 或待提供。
