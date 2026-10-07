/** Only resume the same-origin OAuth consent page, never auto-approve. */
export function oauthReturnPath(search: string, origin: string): string | null {
  try {
    const outer = new URLSearchParams(search);
    if (outer.getAll("return_to").length !== 1) return null;
    const raw = outer.get("return_to")!;
    if (raw.length > 4096 || !raw.startsWith("/oauth/authorize?") || /[\r\n]/.test(raw)) return null;
    const next = new URL(raw, origin);
    if (next.origin !== origin || next.pathname !== "/oauth/authorize" || next.hash) return null;
    const base = ["response_type", "client_id", "redirect_uri", "scope", "state"];
    const competition = !next.searchParams.has("code_challenge") && !next.searchParams.has("code_challenge_method");
    const consentScopes = new Set(["demo:read", "demo:read tasks:read", "demo:read tasks:read tasks:write"]);
    const required = competition ? base : [...base, "code_challenge", "code_challenge_method"];
    const keys = [...next.searchParams.keys()];
    if (keys.length !== required.length || required.some(key => next.searchParams.getAll(key).length !== 1)) return null;
    // Only resumes consent; server configuration decides whether this closed
    // competition mode is enabled. This never grants access or auto-approves.
    if (competition && (next.searchParams.get("response_type") !== "code" ||
      next.searchParams.get("redirect_uri") !== "https://coze.nankai.edu.cn/product/llm/info/oauth" ||
      !consentScopes.has(next.searchParams.get("scope")!) ||
      !/^[A-Za-z0-9._:-]{8,128}$/.test(next.searchParams.get("client_id")!) ||
      !/^[A-Za-z0-9._~-]{8,256}$/.test(next.searchParams.get("state")!))) return null;
    return next.pathname + next.search;
  } catch { return null; }
}
