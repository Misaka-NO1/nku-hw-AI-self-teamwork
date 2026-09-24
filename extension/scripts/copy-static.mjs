// 把预览页静态文件复制到 dist/，与打包后的 preview.js 放在一起。
// 扩展以仓库 extension/ 根目录加载（manifest.json 在根，引用 dist/*.js）。
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(resolve(root, "dist"), { recursive: true });
copyFileSync(
  resolve(root, "src/preview/preview.html"),
  resolve(root, "dist/preview.html"),
);
console.log("copied preview.html to dist/");
