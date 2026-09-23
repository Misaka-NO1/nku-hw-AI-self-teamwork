import type { ScenicCatalog } from "./geometry";

/** Virtual fixture mirrored from knowledge/scenic/catalog.demo.json; never a real NKU location. */
export const demoScenicCatalog: ScenicCatalog = {
  schema_version: "1.0.0",
  data_version: "demo-v1",
  maps: [{ map_id: "demo-map-01", campus_id: "demo-campus", width: 1000, height: 600,
    asset_path: null, rights_status: "pending", data_status: "demo" }],
  spots: [
    { spot_id: "demo-spot-01", map_id: "demo-map-01", name: "示例花木点 A（虚构）",
      x_norm: 0.25, y_norm: 0.35, tags: ["flower", "quiet"], description: "仅用于测试点位交互，不指向南开真实地点。",
      photos: [], historical_bloom_months: [3, 4], observation: null, rights_status: "owned", data_status: "demo" },
    { spot_id: "demo-spot-02", map_id: "demo-map-01", name: "示例晚景点 B（虚构）",
      x_norm: 0.65, y_norm: 0.25, tags: ["sunset"], description: "仅用于测试点位交互，不指向南开真实地点。",
      photos: [], historical_bloom_months: [], observation: null, rights_status: "owned", data_status: "demo" },
    { spot_id: "demo-spot-03", map_id: "demo-map-01", name: "示例步道点 C（虚构）",
      x_norm: 0.5, y_norm: 0.8, tags: ["quiet"], description: "仅用于测试点位交互，不指向南开真实地点。",
      photos: [], historical_bloom_months: [], observation: null, rights_status: "owned", data_status: "demo" },
  ],
};
