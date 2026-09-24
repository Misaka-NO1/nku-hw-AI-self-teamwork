import test from "node:test";
import assert from "node:assert/strict";
import { demoStudyItems, filterStudyItems, publicStudyItems } from "./demoCatalog.ts";

test("STUDY-01 recursive topic finds one authorized body entry", () => {
  const items = filterStudyItems(demoStudyItems, "demo-CS101", "递归");
  assert.equal(items.length, 1);
  assert.equal(items[0].evidence[0].heading, "递归的两个必要部分");
  assert.equal(items[0].evidence[0].page_label, null);
});

test("STUDY-02 index-only entry is not body evidence", () => {
  const items = filterStudyItems(demoStudyItems, "demo-CS101", "排序");
  assert.equal(items.length, 1);
  assert.equal(items[0].content_available, false);
  assert.deepEqual(items[0].evidence, []);
});

test("STUDY-03 wrong course or topic gives no result", () => {
  assert.deepEqual(filterStudyItems(demoStudyItems, "unknown", "递归"), []);
  assert.deepEqual(filterStudyItems(demoStudyItems, "demo-CS101", "量子计算"), []);
});

test("STUDY-04 pending and private are never public", () => {
  const extra = [{ ...demoStudyItems[0], material_id: "private", access_scope: "private" },
    { ...demoStudyItems[0], material_id: "pending", rights_status: "pending" }];
  assert.deepEqual(publicStudyItems([...demoStudyItems, ...extra]).map((item) => item.material_id),
    ["demo-note-01", "demo-index-02"]);
});
