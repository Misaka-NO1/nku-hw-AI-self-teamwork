import { useState } from "react";
import { listCourses, listExperienceCards } from "../../shared/courses";

/** Existing C catalogue only; distinct IDs and source types stay distinct. */
export function CourseCatalog() {
  const [query, setQuery] = useState("");
  const courses = listCourses().filter(course =>
    `${course.title} ${course.courseId}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section aria-label="课程目录与经验">
    <h3>课程目录与学习经验</h3>
    <p>以下为虚构课程目录演示，不是当前开课列表。课程名称相同也不合并编号；个人经验不是学校规定。</p>
    <input type="search" aria-label="搜索课程名称或编号" placeholder="搜索课程名称或编号" value={query} onChange={event => setQuery(event.target.value)} />
    {courses.length === 0 && <p>没有匹配的课程，不推测同名课程的编号。</p>}
    {courses.map(course => <article className="card" key={course.courseId}>
      <h4>{course.title}</h4>
      <p>课程编号：{course.courseId} · 演示学分：{course.credits ?? "未知"}</p>
      {listExperienceCards(course.courseId).map(card => <div key={card.experienceId}>
        <p>{card.sourceType === "official" ? "虚构官方信息示例" : "虚构学生经验示例"} · 学期：{card.termId ?? "未知"} · 样本：{card.sampleCount}</p>
        <p>{card.summary}</p>
      </div>)}
      {listExperienceCards(course.courseId).length === 0 && <p>暂无经验资料。</p>}
      <p className="state__hint">不生成教师排名或“保证高分”结论。</p>
    </article>)}
  </section>;
}
