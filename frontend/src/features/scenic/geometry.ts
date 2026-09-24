export interface ScenicSpot {
  spot_id: string;
  map_id: string;
  name: string;
  x_norm: number;
  y_norm: number;
  tags: string[];
  description: string;
  photos: Array<{
    photo_id: string;
    asset_path: string | null;
    caption: string;
    captured_at: string | null;
    rights_status: "owned" | "authorized" | "public_link_only" | "pending";
  }>;
  historical_bloom_months: number[];
  observation: null | { observed_at: string; status: string; source_ref: string };
  rights_status: "owned" | "authorized" | "public_link_only" | "pending";
  data_status: "demo" | "verified" | "needs_verification";
}

export interface ScenicMap {
  map_id: string;
  campus_id: string;
  width: number;
  height: number;
  asset_path: string | null;
  rights_status: ScenicSpot["rights_status"];
  data_status: ScenicSpot["data_status"];
}

export interface ScenicCatalog {
  schema_version: "1.0.0";
  data_version: string;
  maps: ScenicMap[];
  spots: ScenicSpot[];
}

function requireGeometry(x: number, y: number, width: number, height: number): void {
  if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
    throw new RangeError("坐标和地图尺寸必须是有效数字，尺寸须大于 0");
  }
}

/** Image origin is top-left; Leaflet CRS.Simple receives [y, x]. */
export function toMapPoint(x_norm: number, y_norm: number, width: number, height: number): [number, number] {
  requireGeometry(x_norm, y_norm, width, height);
  if (x_norm < 0 || x_norm > 1 || y_norm < 0 || y_norm > 1) {
    throw new RangeError("归一化坐标必须位于 [0, 1]");
  }
  return [height * (1 - y_norm), width * x_norm];
}

export function fromMapPoint(y: number, x: number, width: number, height: number): [number, number] {
  requireGeometry(x, y, width, height);
  if (x < 0 || x > width || y < 0 || y > height) {
    throw new RangeError("地图点超出底图边界");
  }
  return [x / width, 1 - y / height];
}

export function safeAssetPath(path: string | null): string | null {
  if (path === null) return null;
  return /^assets\/[A-Za-z0-9._/-]+$/.test(path) && !path.split("/").includes("..")
    ? `/${path}`
    : null;
}

export function validateSpot(value: unknown): value is ScenicSpot {
  if (!value || typeof value !== "object") return false;
  const spot = value as Partial<ScenicSpot>;
  return typeof spot.spot_id === "string" && /^[A-Za-z0-9._-]{1,128}$/.test(spot.spot_id)
    && typeof spot.map_id === "string" && spot.map_id.length > 0
    && typeof spot.name === "string" && typeof spot.description === "string"
    && typeof spot.x_norm === "number" && Number.isFinite(spot.x_norm) && spot.x_norm >= 0 && spot.x_norm <= 1
    && typeof spot.y_norm === "number" && Number.isFinite(spot.y_norm) && spot.y_norm >= 0 && spot.y_norm <= 1
    && Array.isArray(spot.tags) && spot.tags.every((tag) => typeof tag === "string")
    && new Set(spot.tags).size === spot.tags.length
    && Array.isArray(spot.photos) && spot.photos.every((photo) => photo !== null && typeof photo === "object"
      && typeof photo.photo_id === "string" && typeof photo.caption === "string"
      && (photo.asset_path === null || safeAssetPath(photo.asset_path) !== null)
      && (photo.captured_at === null || typeof photo.captured_at === "string")
      && ["owned", "authorized", "public_link_only", "pending"].includes(photo.rights_status))
    && Array.isArray(spot.historical_bloom_months)
    && spot.historical_bloom_months.every((month) => Number.isInteger(month) && month >= 1 && month <= 12)
    && new Set(spot.historical_bloom_months).size === spot.historical_bloom_months.length
    && (spot.observation === null || (spot.observation !== undefined
      && typeof spot.observation.observed_at === "string"
      && typeof spot.observation.status === "string"
      && typeof spot.observation.source_ref === "string"))
    && ["owned", "authorized", "public_link_only", "pending"].includes(spot.rights_status ?? "")
    && ["demo", "verified", "needs_verification"].includes(spot.data_status ?? "");
}

export function findSpot(spot_id: string | null, catalog: ScenicCatalog): ScenicSpot | null {
  return catalog.spots.find((spot) => spot.spot_id === spot_id
    && ["owned", "authorized"].includes(spot.rights_status)) ?? null;
}

export function historicalBloomText(spot: ScenicSpot): string {
  const months = spot.historical_bloom_months;
  return months.length
    ? `历史花期资料：${months.join("、")} 月；暂无可据此判断的实时花况。`
    : "暂无可核验的历史花期或实时花况。";
}
