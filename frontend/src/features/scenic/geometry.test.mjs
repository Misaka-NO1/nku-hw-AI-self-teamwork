import test from "node:test";
import assert from "node:assert/strict";
import { toMapPoint, fromMapPoint, validateSpot, findSpot, historicalBloomText, safeAssetPath } from "./geometry.ts";
import { demoScenicCatalog } from "./demoCatalog.ts";

test("MAP-01 four corners and centre round-trip at different image sizes", () => {
  for (const [width, height] of [[1000, 600], [375, 812]]) {
    for (const [x, y] of [[0, 0], [1, 0], [0, 1], [1, 1], [0.5, 0.5]]) {
      const [mapY, mapX] = toMapPoint(x, y, width, height);
      const [backX, backY] = fromMapPoint(mapY, mapX, width, height);
      assert.ok(Math.abs(backX - x) < 1e-12);
      assert.ok(Math.abs(backY - y) < 1e-12);
    }
  }
  assert.deepEqual(toMapPoint(0.25, 0.35, 1000, 600), [390, 250]);
});

test("MAP-01 invalid coordinates and sizes are rejected", () => {
  for (const bad of [-0.1, 1.1, NaN, Infinity]) assert.throws(() => toMapPoint(bad, 0.5, 1000, 600), RangeError);
  assert.throws(() => fromMapPoint(700, 5, 1000, 600), RangeError);
  assert.throws(() => toMapPoint(0.5, 0.5, 0, 600), RangeError);
});

test("MAP-02 unknown spot is not replaced", () => {
  assert.equal(findSpot("demo-spot-01", demoScenicCatalog)?.name, "示例花木点 A（虚构）");
  assert.equal(findSpot("unknown", demoScenicCatalog), null);
});

test("MAP-03/04 demo has no real map or photo and bloom remains historical", () => {
  assert.equal(demoScenicCatalog.maps[0].asset_path, null);
  assert.deepEqual(demoScenicCatalog.spots[0].photos, []);
  assert.match(historicalBloomText(demoScenicCatalog.spots[0]), /历史花期资料/);
  assert.match(historicalBloomText(demoScenicCatalog.spots[0]), /暂无可据此判断的实时花况/);
});

test("MAP-05 validates spot and rejects unsafe asset paths", () => {
  assert.equal(validateSpot(demoScenicCatalog.spots[0]), true);
  assert.equal(validateSpot({ ...demoScenicCatalog.spots[0], x_norm: 1.2 }), false);
  assert.equal(safeAssetPath("javascript:alert(1)"), null);
  assert.equal(safeAssetPath("assets/../private.png"), null);
  assert.equal(safeAssetPath("assets/photo.png"), "/assets/photo.png");
});
