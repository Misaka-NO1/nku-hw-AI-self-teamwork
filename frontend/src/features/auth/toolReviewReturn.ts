/** Review URLs contain only a public draft identifier. Identity and access are
 * always checked by the backend; this helper never accepts an owner or token. */
function reviewPath(raw: string, origin: string): string | null {
  try {
    if (raw.length > 512 || /[\u0000-\u0020\u007f\\#]/.test(raw)) return null;
    const path = raw.split("?")[0];
    if (path !== "/tools/tasks" && path !== "/tools/import") return null;
    const next = new URL(raw, origin);
    if (next.origin !== origin || next.pathname !== path || next.hash) return null;
    const keys = [...next.searchParams.keys()];
    if (keys.length === 0) return path;
    if (keys.length !== 1 || keys[0] !== "draft_id") return null;
    const id = next.searchParams.get("draft_id")!;
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) return null;
    return path + "?" + new URLSearchParams({ draft_id: id });
  } catch { return null; }
}

export function toolReviewReturnPath(search: string, origin: string): string | null {
  const outer = new URLSearchParams(search);
  if ([...outer.keys()].length !== 1 || outer.getAll("return_to").length !== 1) return null;
  return reviewPath(outer.get("return_to")!, origin);
}

export function toolReviewLoginUrl(path: string, origin: string): string | null {
  const target = reviewPath(path, origin);
  return target ? "/tools/login?" + new URLSearchParams({ return_to: target }) : null;
}
