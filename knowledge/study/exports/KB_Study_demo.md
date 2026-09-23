# KB_Study 公开正文候选

> 仅供 D 在平台验证导入；所有 demo 内容均为自创夹具。

## 程序设计示例笔记（自创测试材料） · 递归的两个必要部分

- material_id: demo-note-01
- version: 1.0
- course_id: demo-CS101
- chunk_id: demo-note-01-c1
- source_label: 本仓库自创测试材料，非南开课程讲义或真题
- source_excerpt_ref: knowledge/study/sources/demo-note-01.md#递归的两个必要部分
- page_label: 无页码

在这个例子中，递归函数包含终止条件和递归推进。终止条件决定何时不再调用自身；递归推进把问题变为更小的子问题，并朝终止条件靠近。

例如对非负整数 n 计算阶乘：0 的阶乘定义为 1；n 大于 0 时用 n 乘以 n-1 的阶乘。调用前应验证 n 为非负整数。只有写了终止分支却没有让每次调用朝它推进，仍可能不终止。

## 程序设计示例笔记（自创测试材料） · 数组下标检查

- material_id: demo-note-01
- version: 1.0
- course_id: demo-CS101
- chunk_id: demo-note-01-c2
- source_label: 本仓库自创测试材料，非南开课程讲义或真题
- source_excerpt_ref: knowledge/study/sources/demo-note-01.md#数组下标检查
- page_label: 无页码

本例采用从 0 开始的数组下标。长度为 n 的数组，有效下标为 0 到 n-1。访问元素前需要检查下标是否在这一范围。下标检查与递归终止条件是不同问题，不应因材料同时出现而混为一谈。
