import { describe, expect, it, vi } from "vitest";

import { submitConfirmedDraft, TicketError, type ImportTicket } from "../src/tickets";

const ticket: ImportTicket = {
  token: "opaque-demo-ticket",
  workspaceRef: "demo-workspace-01",
  purpose: "schedule_import",
  expiresAt: 1_800_000_000_000,
};

describe("EXT-02 票据过期不上传", () => {
  it("过期票据直接拒绝，不发起任何网络请求，本地预览保留", async () => {
    const fetchSpy = vi.fn();
    await expect(
      submitConfirmedDraft(ticket, "demo-workspace-01", {}, {
        backendOrigin: "https://api.example.invalid",
        now: ticket.expiresAt + 1,
        fetchImpl: fetchSpy,
      }),
    ).rejects.toMatchObject({ code: "TOKEN_EXPIRED" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("工作区不匹配拒绝上传", async () => {
    const fetchSpy = vi.fn();
    await expect(
      submitConfirmedDraft(ticket, "other-workspace", {}, {
        backendOrigin: "https://api.example.invalid",
        now: ticket.expiresAt - 1000,
        fetchImpl: fetchSpy,
      }),
    ).rejects.toMatchObject({ code: "INVALID_TICKET" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("后端地址未配置时不猜链接，走离线导出降级", async () => {
    const fetchSpy = vi.fn();
    await expect(
      submitConfirmedDraft(ticket, "demo-workspace-01", {}, {
        backendOrigin: "",
        now: ticket.expiresAt - 1000,
        fetchImpl: fetchSpy,
      }),
    ).rejects.toMatchObject({ code: "UPLOAD_DISABLED" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("上传使用固定后端地址、ImportTicket 头且不携带 Cookie", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { draft_id: "d1", review_url: null } }),
    });
    const result = await submitConfirmedDraft(ticket, "demo-workspace-01", { demo: true }, {
      backendOrigin: "https://api.example.invalid",
      now: ticket.expiresAt - 1000,
      fetchImpl: fetchSpy,
    });
    expect(result.draftId).toBe("d1");
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.invalid/api/v1/schedules/import-drafts");
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).Authorization).toBe("ImportTicket opaque-demo-ticket");
  });

  it("后端返回 410 视为票据过期", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({ ok: false, status: 410 });
    await expect(
      submitConfirmedDraft(ticket, "demo-workspace-01", {}, {
        backendOrigin: "https://api.example.invalid",
        now: ticket.expiresAt - 1000,
        fetchImpl: fetchSpy,
      }),
    ).rejects.toSatisfy((error: unknown) => error instanceof TicketError && error.code === "TOKEN_EXPIRED");
  });
});

describe("PR #2 审核意见 3：幂等键不携带票据明文", () => {
  it("Idempotency-Key 是随机 UUID，不包含票据内容", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { draft_id: "d1", review_url: null } }),
    });
    await submitConfirmedDraft(ticket, "demo-workspace-01", {}, {
      backendOrigin: "https://api.example.invalid",
      now: ticket.expiresAt - 1000,
      fetchImpl: fetchSpy,
    });
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    const key = (init.headers as Record<string, string>)["Idempotency-Key"];
    expect(key).toBeDefined();
    expect(key).not.toContain(ticket.token);
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
  });
});
