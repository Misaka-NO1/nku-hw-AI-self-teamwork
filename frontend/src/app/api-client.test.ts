/**
 * SHELL-02：401/403/422/503 显示正确错误——client 把失败信封转成
 * 带 requestId 的 ApiError 抛出，绝不按成功解析；snake_case → camelCase。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const BASE = "http://test.local";

function envelopeError(status: number, code: string, requestId: string) {
  return new Response(
    JSON.stringify({
      ok: false,
      data: null,
      error: { code, message: `失败:${code}`, field_errors: [], retryable: false },
      meta: {
        schema_version: "1.0.0",
        request_id: requestId,
        data_version: null,
        calculation_version: null,
        warnings: [],
        evidence_refs: [],
      },
    }),
    { status, headers: { "Content-Type": "application/json" } }
  );
}

describe("SHELL-02 API client 错误处理", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", BASE);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it.each([
    [401, "AUTH_REQUIRED"],
    [403, "FORBIDDEN"],
    [422, "VALIDATION_ERROR"],
    [503, "DEPENDENCY_UNAVAILABLE"],
  ] as const)("HTTP %i 抛出带 request_id 的 %s", async (status, code) => {
    const { apiClient, ApiError } = await import("../shared/api/client");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => envelopeError(status, code, `req-${status}`))
    );
    try {
      await apiClient.get("/api/v1/anything");
      expect.unreachable("失败响应不得按成功返回");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as InstanceType<typeof ApiError>;
      expect(apiErr.code).toBe(code);
      expect(apiErr.status).toBe(status);
      expect(apiErr.requestId).toBe(`req-${status}`);
      expect(apiErr.message).toContain(code);
    }
  });

  it("成功响应的 snake_case 字段转换为 camelCase", async () => {
    const { apiClient } = await import("../shared/api/client");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              ok: true,
              data: { plan_id: "p1", module_list: [{ earned_credits: "3.0" }] },
              error: null,
              meta: {
                schema_version: "1.0.0",
                request_id: "req-ok",
                data_version: null,
                calculation_version: null,
                warnings: [],
                evidence_refs: [],
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
      )
    );
    const data = await apiClient.get<Record<string, unknown>>("/api/v1/x");
    expect(data.planId).toBe("p1");
    expect((data.moduleList as Record<string, unknown>[])[0].earnedCredits).toBe("3.0");
  });

  it("非信封响应不当作成功", async () => {
    const { apiClient, ApiError } = await import("../shared/api/client");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>502</html>", { status: 502 }))
    );
    await expect(apiClient.get("/api/v1/x")).rejects.toBeInstanceOf(ApiError);
  });
});
