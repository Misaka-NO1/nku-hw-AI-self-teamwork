/**
 * 产物加载验证（PR #2 复审 P1）：
 * chrome.scripting.executeScript({files}) 与未声明 "type":"module" 的
 * service worker 都按普通脚本加载，产物不得包含顶层 ESM 语法。
 * 用 node:vm 以经典脚本方式编译 dist 产物，真实复现浏览器的解析行为。
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import vm from "node:vm";

import { describe, expect, it } from "vitest";

const extRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distFiles = ["background.js", "content.js", "preview.js"].map((name) =>
  resolve(extRoot, "dist", name),
);

const distReady = distFiles.every((file) => existsSync(file));

describe("dist 产物可作为经典脚本加载", () => {
  it.skipIf(!distReady)("先运行 npm run build 生成产物（npm run verify 会自动构建）", () => {
    for (const file of distFiles) {
      const code = readFileSync(file, "utf-8");
      // 经典脚本解析：遇到顶层 export/import 会抛 SyntaxError
      expect(() => new vm.Script(code, { filename: file })).not.toThrow();
      expect(code).not.toMatch(/^export\s/m);
      expect(code).not.toMatch(/^import\s/m);
    }
  });
});
