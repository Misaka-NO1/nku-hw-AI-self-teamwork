import test from "node:test";
import assert from "node:assert/strict";
import { buildAuthoringBundle, createSpotFromDraft, parseAuthoringBundle } from "./authoring.ts";
import { demoScenicCatalog } from "./demoCatalog.ts";
import { safeAssetPath, validateSpot } from "./geometry.ts";

test("A04 authoring export and import preserve coordinates and description", () => {
  const edited = structuredClone(demoScenicCatalog);
  edited.spots[0].x_norm = 0.73;
  edited.spots[0].y_norm = 0.42;
  edited.spots[0].description = "编辑后的虚构点位说明";
  edited.spots[0].photos = [{ photo_id: "demo-photo", asset_path: "assets/demo-photo.jpg",
    caption: "待核验示意", captured_at: null, rights_status: "pending" }];
  const bundle = buildAuthoringBundle(edited, safeAssetPath);
  assert.deepEqual(bundle.assets, ["assets/demo-photo.jpg"]);
  const imported = parseAuthoringBundle(JSON.stringify(bundle), "demo-map-01", validateSpot);
  assert.deepEqual(imported[0], edited.spots[0]);
});

test("A04 import rejects wrong map, duplicate IDs, and unsafe file paths", () => {
  const bundle = buildAuthoringBundle(structuredClone(demoScenicCatalog), safeAssetPath);
  assert.throws(() => parseAuthoringBundle(JSON.stringify(bundle), "other-map", validateSpot));
  bundle.catalog.spots.push(structuredClone(bundle.catalog.spots[0]));
  assert.throws(() => parseAuthoringBundle(JSON.stringify(bundle), "demo-map-01", validateSpot));
  bundle.catalog.spots.pop();
  bundle.catalog.spots[0].photos = [{ photo_id: "p", asset_path: "javascript:alert(1)",
    caption: "bad", captured_at: null, rights_status: "owned" }];
  assert.throws(() => parseAuthoringBundle(JSON.stringify(bundle), "demo-map-01", validateSpot));
});

test("A04 map authoring creates a valid point and rejects incomplete or off-map entries", () => {
  const point = createSpotFromDraft("demo-map-01", 0.3, 0.7,
    { name: "  示例樱花点  ", description: "自建测试点", tags: "赏花，拍照,赏花" }, "demo-new-01");
  assert.equal(validateSpot(point), true);
  assert.equal(point.name, "示例樱花点");
  assert.deepEqual(point.tags, ["赏花", "拍照"]);
  assert.deepEqual([point.x_norm, point.y_norm], [0.3, 0.7]);
  assert.throws(() => createSpotFromDraft("demo-map-01", 0.3, 0.7,
    { name: " ", description: "有简介", tags: "" }, "bad"));
  assert.throws(() => createSpotFromDraft("demo-map-01", 1.1, 0.7,
    { name: "有名称", description: "有简介", tags: "" }, "bad"));
});
