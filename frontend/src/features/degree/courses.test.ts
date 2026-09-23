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

  it("未评分样本不得把单条评分抬过最低门槛（PR #3 审核回归）", () => {
    const oneRated = [
      {
        experienceId: "t1",
        courseId: "demo-CS101",
        offeringId: null,
        termId: "demo-term-2026A",
        sourceType: "student_experience" as const,
        sampleCount: 1,
        consent: true,
        reviewStatus: "approved" as const,
        summary: "x",
        ratingAggregate: 5,
      },
      {
        experienceId: "t2",
        courseId: "demo-CS101",
        offeringId: null,
        termId: "demo-term-2026A",
        sourceType: "student_experience" as const,
        sampleCount: 2,
        consent: true,
        reviewStatus: "approved" as const,
        summary: "x",
        ratingAggregate: null,
      },
    ];
    // 总样本 3 但真正评分的只有 1 个，不得返回综合评分
    expect(aggregateRating(oneRated)).toBeNull();
  });

  it("有效评分样本达到门槛才计算加权平均", () => {
    const mk = (id: string, samples: number, rating: number) => ({
      experienceId: id,
      courseId: "demo-CS101",
      offeringId: null,
      termId: "demo-term-2026A",
      sourceType: "student_experience" as const,
      sampleCount: samples,
      consent: true,
      reviewStatus: "approved" as const,
      summary: "x",
      ratingAggregate: rating,
    });
    const cards = [mk("a", 2, 4), mk("b", 1, 5)];
    // (4*2 + 5*1) / 3 = 4.33…
    expect(aggregateRating(cards)).toBeCloseTo(13 / 3, 5);
  });
});
