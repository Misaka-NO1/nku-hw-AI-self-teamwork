/**
 * 课程经验卡（knowledge/courses/experiences.json）。
 * official 与 student_experience 分开；低样本不生成综合评分。
 */
import raw from "../../../../knowledge/courses/experiences.json";
import { snakeToCamel } from "../api/convert";

export type ExperienceSourceType = "official" | "student_experience";

export interface ExperienceCard {
  experienceId: string;
  courseId: string;
  offeringId: string | null;
  termId: string;
  sourceType: ExperienceSourceType;
  sampleCount: number;
  consent: boolean;
  reviewStatus: "pending" | "approved" | "rejected";
  summary: string;
  ratingAggregate: number | null;
}

interface ExperienceFile {
  schemaVersion: string;
  datasetKind: string;
  dataVersion: string;
  note: string;
  cards: ExperienceCard[];
}

const file = snakeToCamel(raw) as unknown as ExperienceFile;

/** 综合评分最少样本数；不足时一律不聚合。 */
export const MIN_SAMPLES_FOR_AGGREGATE = 3;

export function listExperienceCards(courseId: string): ExperienceCard[] {
  return file.cards.filter(
    (c) => c.courseId === courseId && c.reviewStatus === "approved"
  );
}

/**
 * 样本不足或来源混用时返回 null——一条评价不构成“总体结论”。
 * 最低样本门槛只统计真正带评分的样本：未评分卡不得把单条评分抬过门槛。
 */
export function aggregateRating(cards: ExperienceCard[]): number | null {
  const rated = cards.filter(
    (c) => c.sourceType === "student_experience" && c.ratingAggregate !== null
  );
  const ratedSamples = rated.reduce((sum, c) => sum + c.sampleCount, 0);
  if (rated.length === 0 || ratedSamples < MIN_SAMPLES_FOR_AGGREGATE) return null;
  const total = rated.reduce(
    (sum, c) => sum + (c.ratingAggregate ?? 0) * c.sampleCount,
    0
  );
  return total / ratedSamples;
}
