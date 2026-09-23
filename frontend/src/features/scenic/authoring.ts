import type { ScenicCatalog, ScenicSpot } from "./geometry";

export interface AuthoringBundle { catalog: ScenicCatalog; assets: string[] }

export interface SpotDraft { name: string; description: string; tags: string }

export function createSpotFromDraft(
  map_id: string,
  x_norm: number,
  y_norm: number,
  draft: SpotDraft,
  spot_id: string,
  data_status: ScenicSpot["data_status"] = "demo",
): ScenicSpot {
  const name = draft.name.trim();
  const description = draft.description.trim();
  if (!name || name.length > 128) throw new Error("景点名称须为 1–128 个字符");
  if (!description) throw new Error("请填写景点简介");
  if (!Number.isFinite(x_norm) || !Number.isFinite(y_norm)
    || x_norm < 0 || x_norm > 1 || y_norm < 0 || y_norm > 1) {
    throw new Error("景点坐标必须位于底图内");
  }
  const tags = [...new Set(draft.tags.split(/[,，;；]/).map((tag) => tag.trim()).filter(Boolean))];
  return {
    spot_id, map_id, name, description, x_norm, y_norm, tags,
    photos: [], historical_bloom_months: [], observation: null,
    rights_status: "owned", data_status,
  };
}

export function buildAuthoringBundle(
  catalog: ScenicCatalog,
  safeAssetPath: (path: string | null) => string | null,
): AuthoringBundle {
  const assets = [
    ...catalog.maps.map((map) => map.asset_path),
    ...catalog.spots.flatMap((spot) => spot.photos.map((photo) => photo.asset_path)),
  ].filter((path): path is string => typeof path === "string" && safeAssetPath(path) !== null);
  return { catalog, assets: [...new Set(assets)] };
}

export function parseAuthoringBundle(
  raw: string,
  map_id: string,
  validateSpot: (value: unknown) => value is ScenicSpot,
): ScenicSpot[] {
  const parsed: unknown = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || !("catalog" in parsed)) throw new Error("缺少目录");
  const catalog = (parsed as { catalog: unknown }).catalog as Partial<ScenicCatalog>;
  if (catalog.schema_version !== "1.0.0" || !Array.isArray(catalog.spots)
    || !catalog.spots.every(validateSpot)
    || catalog.spots.some((spot) => spot.map_id !== map_id)
    || new Set(catalog.spots.map((spot) => spot.spot_id)).size !== catalog.spots.length) {
    throw new Error("目录结构、地图 ID 或点位不合法");
  }
  return catalog.spots;
}
