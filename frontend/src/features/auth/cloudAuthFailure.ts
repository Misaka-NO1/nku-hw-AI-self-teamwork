// CloudBase 3.10.1 AuthError categories. Never render vendor messages, response
// bodies, request IDs, URLs or tokens: even an error object may contain secrets.
const categories: Record<string, string> = {
  PROVIDER_NOT_ENABLED: "此环境未启用对应登录方式，请检查腾讯云登录配置",
  INVALID_CREDENTIALS: "测试账号凭证被腾讯云拒绝，请核对测试密码；不会退回匿名身份",
  USER_NOT_FOUND: "测试账号不存在，请核对账号配置",
  USER_STATUS_ABNORMAL: "测试账号状态异常，请在腾讯云核对状态",
  SERVICE_ERROR: "腾讯云身份服务异常，请稍后重试",
  INVALID_PARAMS: "登录请求参数未被腾讯云接受，请核对 SDK 接入",
  AUTH_METHOD_MISMATCH: "账号与登录方式不匹配，请核对腾讯云登录配置",
  RATE_LIMITED: "腾讯云登录频率受限，请停止重复点击，稍后重试",
  CAPTCHA_REQUIRED: "腾讯云要求人工验证码验证，需本人完成；不会自动绕过",
  CAPTCHA_INVALID: "腾讯云验证码未通过，需本人重新验证",
  MFA_REQUIRED: "腾讯云要求多因素验证，需本人完成；不会自动绕过",
  PRECONDITION_FAILED: "腾讯云登录前置条件未满足，请核对来源域名、登录策略及账号状态",
  VERIFICATION_FAILED: "腾讯云身份验证未通过，请核对登录配置",
};
const codes: Record<string, string> = {
  invalid_password: "INVALID_CREDENTIALS", invalid_username_or_password: "INVALID_CREDENTIALS",
  invalid_credentials: "INVALID_CREDENTIALS", wrong_password: "INVALID_CREDENTIALS",
  user_not_found: "USER_NOT_FOUND", user_blocked: "USER_STATUS_ABNORMAL", user_pending: "USER_STATUS_ABNORMAL",
  provider_not_enabled: "PROVIDER_NOT_ENABLED", login_method_disabled: "PROVIDER_NOT_ENABLED",
  login_type_disabled: "PROVIDER_NOT_ENABLED", captcha_required: "CAPTCHA_REQUIRED",
  captcha_invalid: "CAPTCHA_INVALID", two_factor_required: "MFA_REQUIRED", mfa_phone_required: "MFA_REQUIRED",
  resource_exhausted: "RATE_LIMITED", failed_precondition: "PRECONDITION_FAILED",
  unauthorized_client: "PRECONDITION_FAILED", permission_denied: "PRECONDITION_FAILED",
  invalid_argument: "INVALID_PARAMS", unavailable: "SERVICE_ERROR", temporarily_unavailable: "SERVICE_ERROR",
  internal: "SERVICE_ERROR", server_error: "SERVICE_ERROR", unreachable: "SERVICE_ERROR",
};
const numericCodes = new Set([3, 5, 7, 8, 9, 10, 12, 13, 14, 16, 4000, 4001, 4002, 4019, 4022, 4042, 4045]);
const numericCategories: Record<number, string> = {
  3: "INVALID_PARAMS", 7: "PRECONDITION_FAILED", 8: "RATE_LIMITED", 9: "PRECONDITION_FAILED",
  13: "SERVICE_ERROR", 14: "SERVICE_ERROR", 4000: "INVALID_PARAMS", 4001: "CAPTCHA_REQUIRED",
  4002: "CAPTCHA_INVALID", 4022: "PRECONDITION_FAILED", 4042: "MFA_REQUIRED", 4045: "PROVIDER_NOT_ENABLED",
};
const hasOwn = (map: object, key: string) => Object.prototype.hasOwnProperty.call(map, key);
const own = (map: Record<string, string>, key: unknown) => typeof key === "string" && hasOwn(map, key) ? map[key] : undefined;

export function cloudAuthFailure(error: unknown, missingSession = false): string {
  if (!error && missingSession) return "腾讯云登录响应缺少有效凭证（SESSION_MISSING）；停止使用，不建立匿名会话";
  if (!error || typeof error !== "object") return "腾讯云登录未成功（UNKNOWN）；请检查网络与登录配置，不会退回匿名身份";
  const value = error as { category?: unknown; code?: unknown; errorCode?: unknown };
  const number = typeof value.errorCode === "number" && numericCodes.has(value.errorCode) ? value.errorCode : undefined;
  const category = own(categories, value.category) ? value.category as string
    : own(codes, value.code) ?? (number === undefined ? undefined : numericCategories[number]);
  // Return only constants from the allowlists; unrecognised error fields are ignored.
  const label = category && own(categories, category) ? category : "UNKNOWN";
  const detail = typeof value.code === "string" && hasOwn(codes, value.code) ? value.code : undefined;
  const hint = own(categories, label) ?? "腾讯云登录未成功，请核对网络、登录方式与账号配置；不会退回匿名身份";
  return `${hint}（${label}${detail ? ` · ${detail}` : ""}${number === undefined ? "" : ` · ${number}`}）`;
}
