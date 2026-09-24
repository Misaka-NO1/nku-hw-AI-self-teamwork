export interface StudyRoute { courseId: string; materialId: string }

export function readStudyRoute(search: string): StudyRoute {
  const params = new URLSearchParams(search);
  return { courseId: params.get("course_id") ?? "", materialId: params.get("material_id") ?? "" };
}

export function studyRouteUrl(currentHref: string, route: StudyRoute): string {
  const url = new URL(currentHref);
  if (route.courseId) url.searchParams.set("course_id", route.courseId);
  else url.searchParams.delete("course_id");
  if (route.materialId) url.searchParams.set("material_id", route.materialId);
  else url.searchParams.delete("material_id");
  return url.toString();
}
