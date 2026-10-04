import type { DemoSession } from "./api";
import { apiClient, ApiError } from "../../shared/api/client";

export const DEMO_CACHE_KEY = "campus-demo-tasks-v1";
const SCHEDULE_CACHE_KEY = "campus-demo-schedule-v1";
function validSession(item: unknown): item is DemoSession {
  if (!item || typeof item !== "object") return false;
  const value = item as Partial<DemoSession>;
  return typeof value.workspaceRef === "string" && value.workspaceRef.length > 0
    && typeof value.csrfToken === "string" && value.csrfToken.length > 0
    && typeof value.expiresAt === "string" && Number.isFinite(Date.parse(value.expiresAt));
}
export function readDemoSession(): DemoSession | null {
  try {
    const item = JSON.parse(sessionStorage.getItem(DEMO_CACHE_KEY) ?? "null")?.session;
    return validSession(item) && Date.parse(item.expiresAt) > Date.now() ? item : null;
  } catch { return null; }
}
/** Share one explicit fictional browser workspace across Tasks and Import.
 * No service bearer, password or real student data is stored here. */
export function writeDemoSession(session: DemoSession): void {
  sessionStorage.setItem(DEMO_CACHE_KEY, JSON.stringify({ session, draftKeys: {} }));
}

export function clearDemoSession(): void {
  sessionStorage.removeItem(DEMO_CACHE_KEY);
  sessionStorage.removeItem(SCHEDULE_CACHE_KEY);
}

export function sessionExpired(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 410
    || error.code === "AUTH_REQUIRED" || error.code === "TOKEN_EXPIRED");
}

/** A business TOKEN_EXPIRED can refer to a draft or confirmation. Only a
 * rejected login identity invalidates the browser session and its local state. */
export function rejectUnauthenticatedBrowserSession(error: unknown): boolean {
  if (!(error instanceof ApiError) || (error.status !== 401 && error.code !== "AUTH_REQUIRED")) return false;
  clearDemoSession();
  return true;
}

/** Cookie identity is authoritative. Cached draft/commit keys survive only for
 * the same workspace; another account never inherits them. This GET neither
 * creates nor renews a session, and sends no bearer, owner or URL parameters. */
export async function restoreBrowserSession(signal?: AbortSignal): Promise<DemoSession> {
  let result: unknown;
  try {
    result = await apiClient.get("/api/v1/auth/cloudbase/browser-session", {
      signal, headers: { "X-Campus-Session-Read": "1" },
    });
  } catch (error) {
    if (sessionExpired(error)) clearDemoSession();
    throw error;
  }
  const checked = result as Partial<DemoSession> & { datasetKind?: unknown; personalUploads?: unknown; agentPaired?: unknown };
  if (!validSession(result) || checked.datasetKind !== "demo"
    || checked.personalUploads !== false || checked.agentPaired !== false) {
    clearDemoSession();
    throw new Error("服务端会话恢复状态不一致，已停止读写；请重试核验");
  }
  const session: DemoSession = { workspaceRef: checked.workspaceRef!, csrfToken: checked.csrfToken!, expiresAt: checked.expiresAt! };
  let cached: Record<string, unknown> | null = null;
  try { cached = JSON.parse(sessionStorage.getItem(DEMO_CACHE_KEY) ?? "null"); } catch { /* Drop invalid local state. */ }
  const previous = cached?.session as Partial<DemoSession> | undefined;
  if (previous?.workspaceRef === session.workspaceRef && cached?.draftKeys
    && typeof cached.draftKeys === "object" && !Array.isArray(cached.draftKeys)) {
    sessionStorage.setItem(DEMO_CACHE_KEY, JSON.stringify({ ...cached, session }));
  } else {
    sessionStorage.removeItem(DEMO_CACHE_KEY);
    writeDemoSession(session);
  }
  try {
    const progress = JSON.parse(sessionStorage.getItem(SCHEDULE_CACHE_KEY) ?? "null");
    if (progress && progress.workspaceRef !== session.workspaceRef) sessionStorage.removeItem(SCHEDULE_CACHE_KEY);
  } catch { sessionStorage.removeItem(SCHEDULE_CACHE_KEY); }
  return session;
}
