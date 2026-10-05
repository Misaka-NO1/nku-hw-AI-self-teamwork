import {afterEach, beforeEach, expect, it, vi} from "vitest";
import {downloadOriginalPdf} from "../../shared/api/client";

beforeEach(() => vi.stubEnv("VITE_API_BASE_URL", "/"));
afterEach(() => {vi.unstubAllEnvs(); vi.unstubAllGlobals();});

it("fetches original bytes rather than navigating to another page", async () => {
  const fetch = vi.fn(async (_url: string, _options?: RequestInit) => new Response("%PDF-1.7\noriginal", {headers: {"Content-Type": "application/pdf"}}));
  vi.stubGlobal("fetch", fetch);
  const blob = await downloadOriginalPdf("note/a");
  expect(await blob.text()).toBe("%PDF-1.7\noriginal");
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/study/materials/note%2Fa/download");
});

it.each([
  ["text/html", "<html>登录/访问提醒</html>"],
  ["application/pdf", "<html>not a PDF</html>"],
])("rejects wrong format %s instead of saving a fake PDF", async (type, body) => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, {headers: {"Content-Type": type}})));
  await expect(downloadOriginalPdf("file")).rejects.toThrow(/未保存/);
});

it("surfaces a failed download, not a success message", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("failure", {status: 503})));
  await expect(downloadOriginalPdf("file")).rejects.toThrow("HTTP 503");
});
