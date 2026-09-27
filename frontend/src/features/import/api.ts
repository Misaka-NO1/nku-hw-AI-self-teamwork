/**
 * B 的导入 feature 专用 API client。
 *
 * 只使用公开构建变量 VITE_API_BASE_URL；不接触任何令牌/教务凭据。
 * C 的共享 client 就绪后可整体替换为本模块的实现，调用签名保持不变。
 */

export interface ApiEnvelope<T> {
  ok: boolean;
  data: T | null;
  error: { code: string; message: string; field_errors: unknown[]; retryable: boolean } | null;
  meta: Record<string, unknown>;
}

const baseUrl = (): string => (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? "";

export async function validateTimetableRemote(payload: unknown): Promise<ApiEnvelope<unknown>> {
  const response = await fetch(`${baseUrl()}/api/v1/schedules/validate`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as ApiEnvelope<unknown>;
}

export async function createScheduleDraft(
  payload: unknown,
  idempotencyKey: string,
  csrfToken: string,
): Promise<ApiEnvelope<unknown>> {
  const response = await fetch(`${baseUrl()}/api/v1/schedules/import-drafts`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as ApiEnvelope<unknown>;
}
