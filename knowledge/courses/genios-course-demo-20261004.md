# 课程目录与经验卡：固定虚构演示

dataset_kind: demo
data_version: demo-courses-v1 / demo-experiences-v1
source_ref: knowledge/courses/catalog.json；knowledge/courses/experiences.json
用途：参赛演示检索与课程标识消歧。不是南开真实开课目录、官方教学大纲或学生评价调查。

## demo-CS101：程序设计基础（虚构示例）

学分 3.0；官方 course_code 未提供。
经验卡 demo-exp-01：来源类型 student_experience，样本仅 1；学期 demo-term-2026A，开课实例 demo-CS101-2026A。内容仅为演示个人学习节奏，不构成容易通过或保证高分的结论，无综合评分。
经验卡 demo-exp-02：来源类型 official，但其内容同样是虚构官方信息示例，仅演示教学大纲索引，没有真实链接。不可因 source_type=official 就说是学校已核实的课程信息。

## demo-CS102：离散结构（虚构示例）

学分 3.0；官方课号未知；没有经验卡，不能编造学生评价。

## demo-CS103：程序设计实验（虚构示例）

学分 2.0；官方课号未知；没有经验卡。

## demo-EL201 与 demo-EL202：英语拓展阅读（两个同名虚构课程）

两门各 2.0 学分，ID 不同，不能合并或把学分累加成同一门课程。用户只给课程标题而未明确标识时，应先消歧。二者官方课号未知，也没有经验卡。

这里只约束课程标识：两门不同ID的课程分别保留，不能合并为一条4.0学分课程记录。此处没有规定二选一、互斥、替代、重复计分或只能计一次，也不能据此说两门课程的学分不能在培养方案中分别认定。是否可以分别计入毕业要求，须有明确培养方案规则或本次审计依据；当前资料没有这些规则，应回答未知。

## 培养方案审计

仅在用户明确选择演示时，调用既有 platform_audit_degree_progress，使用 demo-workspace-01、demo-cs-plan-v1、demo-transcript-01。学分、模块差额与 request_id 必须取自本次工具结果，不能从本文件自行计算。
needs_policy 表示规则尚不足以算出可靠结论，应说明需要人工确认，不输出毕业完成结论。此库没有正式培养方案或真实成绩。
复习库的 y1-s1/y1-s2 标识是另一套公开材料目录，不能与 demo-CS101 等虚构课程静默混为同一课程。
