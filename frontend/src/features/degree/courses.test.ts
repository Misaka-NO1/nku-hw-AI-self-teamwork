/**
 * COURSE-01：同名课程不错误合并；单条评价不产生虚假总体结论。
 */
import { describe, expect, it } from "vitest";
import {
  aggregateRating,
  findCourse,
  findCoursesByTitle,
  listCourses,
  listExperienceCards,
} from "../../shared/courses";

describe("COURSE-01 同名课程不合并", () => {
  it("同名《英语拓展阅读（虚构示例）》保留两个不同 course_id", () => {
    const sameTitle = findCoursesByTitle("英语拓展阅读（虚构示例）");
    expect(sameTitle.map((c) => c.courseId).sort()).toEqual([
      "demo-EL201",
      "demo-EL202",
    ]);
  });

  it("course_id 全局唯一且精确查找", () => {
    const ids = listCourses().map((c) => c.courseId);
    expect(new Set(ids).size).toBe(ids.length);
    expect(findCourse("demo-CS101")?.title).toContain("程序设计基础");
    expect(findCourse("demo-CS999")).toBeUndefined();
  });

  it("一条学生体验不生成综合评分", () => {
    const cards = listExperienceCards("demo-CS101").filter(
      (c) => c.sourceType === "student_experience"
    );
    expect(cards).toHaveLength(1);
    expect(aggregateRating(cards)).toBeNull();
  });
});
