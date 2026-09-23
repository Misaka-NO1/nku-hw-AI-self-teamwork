import type { ScenicCatalog, ScenicSpot } from "./geometry";

export interface AuthoringBundle { catalog: ScenicCatalog; assets: string[] }

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
