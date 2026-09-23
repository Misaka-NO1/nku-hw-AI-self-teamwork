import test from "node:test";
import assert from "node:assert/strict";
import { activeMap, displaySpots, hasDraftConflict } from "./viewModel.ts";
import { demoScenicCatalog } from "./demoCatalog.ts";

test("review-1 async catalog updates immediately unless a local authoring draft is active", () => {
  const empty = { ...demoScenicCatalog, spots: [] };
  const loaded = { ...demoScenicCatalog, spots: [...demoScenicCatalog.spots] };
  assert.equal(displaySpots(empty, null, false).length, 0);
  assert.equal(displaySpots(loaded, null, false).length, 3);
  const draft = { sourceCatalog: empty, spots: [demoScenicCatalog.spots[0]] };
  assert.equal(displaySpots(loaded, draft, true).length, 1);
  assert.equal(hasDraftConflict(loaded, draft, true), true);
  assert.equal(displaySpots(loaded, draft, false).length, 3);
  assert.equal(hasDraftConflict(loaded, draft, false), false);
});

test("review-3 deep-linked spot selects its own map rather than the first map", () => {
  const first = demoScenicCatalog.maps[0];
  const second = { ...first, map_id: "demo-map-02", campus_id: "second-campus" };
  const spotOnSecond = { ...demoScenicCatalog.spots[0], map_id: second.map_id };
  assert.equal(activeMap([first, second], spotOnSecond, first.map_id)?.map_id, second.map_id);
  assert.equal(activeMap([first, second], null, second.map_id)?.map_id, second.map_id);
  assert.equal(activeMap([first], spotOnSecond, first.map_id), undefined);
});
