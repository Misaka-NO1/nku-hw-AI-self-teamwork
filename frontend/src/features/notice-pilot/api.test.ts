import { describe, expect, it, vi, afterEach } from "vitest";
import { noticeApi, toWire } from "./api";
import { apiClient } from "../../shared/api/client";

afterEach(() => vi.restoreAllMocks());

describe("通知确认接口", () => {
  it("保持事件、截止和候选对象结构，不把对象变成字符串或旧样例", () => {
    expect(toWire({ sourceText: "新通知", userConfirmations: { estimatedMinutes: null },
      selectedSlot: { start: "s", end: "e", durationMinutes: 20 },
      notice: { due: { at: null, date: "2026-09-21", precision: "date_only" } } })).toEqual({
      source_text: "新通知", user_confirmations: { estimated_minutes: null },
      selected_slot: { start: "s", end: "e", duration_minutes: 20 },
      notice: { due: { at: null, date: "2026-09-21", precision: "date_only" } },
    });
  });
  it("读回用服务器工作区，并通过共享客户端携带会话", async () => {
    const spy = vi.spyOn(apiClient, "get").mockResolvedValue([]);
    await noticeApi.list("own workspace&other");
    expect(spy).toHaveBeenCalledWith("/api/v1/tasks?workspace_ref=own+workspace%26other");
  });
});
