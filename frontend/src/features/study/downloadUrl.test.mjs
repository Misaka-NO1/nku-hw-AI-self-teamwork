import test from "node:test";
import assert from "node:assert/strict";
import { resolveDownloadUrl } from "./downloadUrl.ts";

test("review-5 download URL comes from an injected API-base-aware builder", () => {
  const base = "https://api.example.test";
  const url = resolveDownloadUrl("note/a", (id) =>
    `${base}/api/v1/study/materials/${encodeURIComponent(id)}/download`);
  assert.equal(url, "https://api.example.test/api/v1/study/materials/note%2Fa/download");
  assert.equal(resolveDownloadUrl("note/a"), null);
  assert.equal(resolveDownloadUrl("note/a", () => "/api/v1/study/materials/note/download"),
    "/api/v1/study/materials/note/download");
  assert.equal(resolveDownloadUrl("note/a", () => "//untrusted.example.test/file"), null);
  assert.equal(resolveDownloadUrl("note/a", () => "javascript:alert(1)"), null);
});
