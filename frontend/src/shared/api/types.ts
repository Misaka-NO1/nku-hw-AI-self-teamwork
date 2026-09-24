/** 统一 API 类型：与 contracts/api.schema.json 信封一致。 */

export interface FieldError {
  field: string;
  code: string;
  message: string;
}

export type ApiErrorCode =
  | "VALIDATION_ERROR"
  | "AUTH_REQUIRED"
  | "FORBIDDEN"
  | "IDENTITY_NOT_VERIFIED"
  | "DEMO_ONLY"
  | "NOT_FOUND"
  | "STALE_REVISION"
  | "CONFIRMATION_REQUIRED"
  | "TOKEN_EXPIRED"
  | "UNSUPPORTED_PAGE"
  | "NEEDS_POLICY"
  | "RATE_LIMITED"
  | "DEPENDENCY_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface ApiErrorBody {
  code: ApiErrorCode;
  message: string;
  field_errors: FieldError[];
  retryable: boolean;
}

export interface ApiMeta {
  schema_version: string;
  request_id: string;
  data_version: string | null;
  calculation_version: string | null;
  warnings: { code: string; message: string }[];
  evidence_refs: { label: string; source_ref: string; locator: string }[];
}

/** 线上信封结构（snake_case），只在 client 内部使用。 */
export interface ApiEnvelope<T = unknown> {
  ok: boolean;
  data: T | null;
  error: ApiErrorBody | null;
  meta: ApiMeta;
}
