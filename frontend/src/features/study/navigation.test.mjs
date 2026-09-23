import test from "node:test";
import assert from "node:assert/strict";
import { readStudyRoute, studyRouteUrl } from "./navigation.ts";

test("review-4 course switch changes course_id and clears stale material_id", () => {
  const before = "https://app.example.test/tools/study?course_id=CS101&material_id=old&from=agent";
  const next = studyRouteUrl(before, { courseId: "CS102", materialId: "" });
  assert.deepEqual(readStudyRoute(new URL(next).search), { courseId: "CS102", materialId: "" });
  assert.equal(new URL(next).searchParams.get("material_id"), null);
  assert.equal(new URL(next).searchParams.get("from"), "agent");
  const selected = studyRouteUrl(next, { courseId: "CS102", materialId: "new" });
  assert.deepEqual(readStudyRoute(new URL(selected).search), { courseId: "CS102", materialId: "new" });
  // Reading the URL after refresh or popstate yields the route represented by that history entry.
  assert.deepEqual(readStudyRoute(new URL(before).search), { courseId: "CS101", materialId: "old" });
});
