import type { ScenicCatalog, ScenicMap, ScenicSpot } from "./geometry";

export type LocalDraft = { sourceCatalog: ScenicCatalog; spots: ScenicSpot[] };

/** The server catalog is authoritative outside local development authoring. */
export function displaySpots(catalog: ScenicCatalog, draft: LocalDraft | null, canAuthor: boolean): ScenicSpot[] {
  return canAuthor && draft ? draft.spots : catalog.spots;
}

export function hasDraftConflict(catalog: ScenicCatalog, draft: LocalDraft | null, canAuthor: boolean): boolean {
  return canAuthor && draft !== null && draft.sourceCatalog !== catalog;
}

/** A spot deep link always takes precedence over a manually selected map. */
export function activeMap(
  maps: ScenicMap[],
  currentSpot: ScenicSpot | null,
  selectedMapId: string | null,
): ScenicMap | undefined {
  if (currentSpot) return maps.find((map) => map.map_id === currentSpot.map_id);
  return maps.find((map) => map.map_id === selectedMapId) ?? maps[0];
}
