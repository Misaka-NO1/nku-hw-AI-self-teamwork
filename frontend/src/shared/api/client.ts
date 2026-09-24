/**
 * 统一 API client。
 *
 * - 只读取公开构建变量 `VITE_API_BASE_URL`（不使用 APP_API_BASE）。
 * - 所有 feature 必须经由本 client 访问后端，不得各自实现 fetch 逻辑。
 * - 支持超时与 AbortSignal 取消。
 * - 任何失败都以 ApiError 抛出并携带 requestId，绝不把失败当成功返回。
 */

import { snakeToCamel } from "./convert";
import type { ApiEnvelope, ApiErrorBody, ApiErrorCode, FieldError } from "./types";

const DEFAULT_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number | null;
  readonly requestId: string | null;
  readonly fieldErrors: FieldError[];
  readonly retryable: boolean;

  constructor(args: {
    code: ApiErrorCode;
    message: string;
    status: number | null;
    requestId: string | null;
    fieldErrors?: FieldError[];
    retryable?: boolean;
  }) {
    super(args.message);
    this.name = "ApiError";
    this.code = args.code;
    this.status = args.status;
    this.requestId = args.requestId;
    this.fieldErrors = args.fieldErrors ?? [];
    this.retryable = args.retryable ?? false;
  }
}

const FALLBACK_CODE_BY_STATUS: Record<number, ApiErrorCode> = {
  401: "AUTH_REQUIRED",
  403: "FORBIDDEN",
  404: "NOT_FOUND",
  409: "STALE_REVISION",
  410: "TOKEN_EXPIRED",
  422: "VALIDATION_ERROR",
  429: "RATE_LIMITED",
  503: "DEPENDENCY_UNAVAILABLE",
};

export function apiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (!base) {
    throw new ApiError({
      code: "INTERNAL_ERROR",
      message: "未配置 VITE_API_BASE_URL，无法连接后端",
      status: null,
      requestId: null,
    });
  }
  return base.replace(/\/$/, "");
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: Record<string, string>;
}

function isEnvelope(value: unknown): value is ApiEnvelope {
  if (value === null || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.ok === "boolean" && v.meta !== null && typeof v.meta === "object";
}

/** 统一请求入口。成功返回 camelCase 的 data；失败抛出带 requestId 的 ApiError。 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, headers } =
    options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const onOuterAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onOuterAbort, { once: true });
  }

  const abortError = () =>
    new ApiError({
      code: "DEPENDENCY_UNAVAILABLE",
      message: "请求超时或已取消",
      status: null,
      requestId: null,
      retryable: true,
    });
  // 覆盖响应头与响应体两个阶段：controller 中止时两个 race 都会立即失败。
  const aborted = new Promise<never>((_resolve, reject) => {
    if (controller.signal.aborted) {
      reject(abortError());
      return;
    }
    controller.signal.addEventListener(
      "abort",
      () => reject(abortError()),
      { once: true }
    );
  });

  let response: Response;
  let payload: unknown = null;
  try {
    response = await Promise.race([
      fetch(`${apiBaseUrl()}${path}`, {
        method,
        credentials: "include",
        signal: controller.signal,
        headers: {
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...headers,
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      }),
      aborted,
    ]);
    // 响应体读取同样受超时保护；读取失败（非中止）按无信封处理。
    try {
      payload = await Promise.race([response.json(), aborted]);
    } catch (bodyErr) {
      if (bodyErr instanceof ApiError) throw bodyErr;
      payload = null;
    }
  } catch (err) {
    if (err instanceof ApiError) throw err;
    const abortedFetch = err instanceof DOMException && err.name === "AbortError";
    if (abortedFetch) throw abortError();
    throw new ApiError({
      code: "DEPENDENCY_UNAVAILABLE",
      message: "网络请求失败，请检查后端是否可达",
      status: null,
      requestId: null,
      retryable: true,
    });
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onOuterAbort);
  }

  if (isEnvelope(payload)) {
    const requestId = payload.meta?.request_id ?? null;
    // HTTP 状态与业务信封必须一致：HTTP 失败时即使信封 ok=true 也按失败处理。
    if (response.ok && payload.ok) {
      return snakeToCamel(payload.data) as T;
    }
    const error: ApiErrorBody | null = payload.error;
    throw new ApiError({
      code:
        error?.code ??
        FALLBACK_CODE_BY_STATUS[response.status] ??
        "INTERNAL_ERROR",
      message:
        error?.message ??
        (payload.ok
          ? `HTTP ${response.status} 与成功信封不一致，按失败处理`
          : `请求失败（HTTP ${response.status}）`),
      status: response.status,
      requestId,
      fieldErrors: error?.field_errors ?? [],
      retryable: error?.retryable ?? response.status >= 500,
    });
  }

  // 非信封响应：同样不当作成功。
  throw new ApiError({
    code: FALLBACK_CODE_BY_STATUS[response.status] ?? "INTERNAL_ERROR",
    message: `服务返回格式不符合统一信封（HTTP ${response.status}）`,
    status: response.status,
    requestId: null,
    retryable: response.status >= 500,
  });
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body: unknown, options?: Omit<RequestOptions, "method">) =>
    request<T>(path, { ...options, method: "POST", body }),
};
