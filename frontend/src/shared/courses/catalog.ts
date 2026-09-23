/**
 * 课程目录（knowledge/courses/catalog.json）共享读取与映射。
 * 同一课程在 A/B/C 间使用同一个 course_id；同名不同课不错误合并。
 */
import raw from "../../../../knowledge/courses/catalog.json";
import { snakeToCamel } from "../api/convert";

export interface CatalogCourse {
  courseId: string;
  courseCode: string | null;
  title: string;
  credits: string | null;
  aliases: string[];
}

interface CatalogFile {
  schemaVersion: string;
  datasetKind: string;
  dataVersion: string;
  note: string;
  courses: CatalogCourse[];
}

const file = snakeToCamel(raw) as unknown as CatalogFile;

export const COURSE_CATALOG_VERSION = file.dataVersion;

export function listCourses(): CatalogCourse[] {
  return file.courses;
}

/** 精确按 course_id 查找；不做按名称的模糊匹配合并。 */
export function findCourse(courseId: string): CatalogCourse | undefined {
  return file.courses.find((c) => c.courseId === courseId);
}

/** 同名课程可能有多个不同 course_id，全部返回，绝不合并。 */
export function findCoursesByTitle(title: string): CatalogCourse[] {
  return file.courses.filter((c) => c.title === title);
}
