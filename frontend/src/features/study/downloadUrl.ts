/** The caller must construct this from the shared API client's VITE_API_BASE_URL. */
export type DownloadUrlFor = (materialId: string) => string | null;

export function resolveDownloadUrl(materialId: string, buildUrl?: DownloadUrlFor): string | null {
  if (!buildUrl) return null;
  try {
    const value = buildUrl(materialId);
    if (!value) return null;
    // A same-origin API proxy can legitimately use a root-relative path.
    if (value.startsWith("/") && !value.startsWith("//") && !value.includes("\\")) return value;
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.toString() : null;
  } catch {
    return null;
  }
}
