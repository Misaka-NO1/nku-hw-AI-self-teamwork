/** Separate loopback-only extension, never replaces the production manifest. */
import { build } from "esbuild";
import { mkdir, readFile, writeFile, copyFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const root = resolve(fileURLToPath(new URL("../../", import.meta.url)));
const output = resolve(root, ".review-cache/degree-local-plugin-20261010-r1");
await mkdir(output); // Refuse overwriting a previous candidate.
await mkdir(resolve(output, "dist"));
await writeFile(resolve(output, "manifest.json"), JSON.stringify({
  manifest_version: 3, name: "南开校园助手 · 培养计划本地验收（不发布）", version: "0.2.0",
  description: "仅把主动读取的培养计划送到127.0.0.1本机核对；不访问线上工具站。验收后移除。",
  permissions: ["storage", "tabs"],
  host_permissions: ["https://eamis.nankai.edu.cn/eams/myPlanCompl.action", "http://127.0.0.1:5179/tools/degree*"],
  background: { service_worker: "dist/worker.js" },
  content_scripts: [
    { matches: ["https://eamis.nankai.edu.cn/eams/myPlanCompl.action"], js: ["dist/degree-content.js"], run_at: "document_idle" },
    { matches: ["http://127.0.0.1:5179/tools/degree*"], js: ["dist/degree-app-bridge.js"], run_at: "document_idle" },
  ],
}, null, 2));
await copyFile(resolve(root, "extension/dist/degree-content.js"), resolve(output, "dist/degree-content.js"));
const entry = resolve(output, "worker-entry.ts");
await writeFile(entry, `import { handleDegreeMessage } from "../../extension/src/degree-transfer";
chrome.runtime.onMessage.addListener((raw, sender, respond) => {
 const route = handleDegreeMessage(raw, sender, chrome);
 if (!route.handled) return false;
 void route.response.then(respond);
 return true;
});\n`);
const localConfig = { name: "degree-local-origin-only", setup(builder) {
  builder.onResolve({ filter: /^\.\/config$/ }, args => {
    if (args.importer.endsWith("degree-transfer.ts")) return { path: "local-origin", namespace: "qa" };
  });
  builder.onLoad({ filter: /^local-origin$/, namespace: "qa" }, () => ({
    contents: 'export const APP_ORIGINS = ["http://127.0.0.1:5179"];', loader: "ts",
  }));
}};
await build({ entryPoints: [entry], outfile: resolve(output, "dist/worker.js"), bundle: true,
  format: "iife", target: "chrome110", plugins: [localConfig] });
await build({ entryPoints: [resolve(root, "extension/src/degree-app-bridge.ts")],
  outfile: resolve(output, "dist/degree-app-bridge.js"), bundle: true, format: "iife",
  target: "chrome110", plugins: [localConfig] });
const hashes = {};
for (const name of ["manifest.json", "dist/worker.js", "dist/degree-content.js", "dist/degree-app-bridge.js"]) {
  hashes[name] = createHash("sha256").update(await readFile(resolve(output, name))).digest("hex");
}
await writeFile(resolve(output, "local-qa-manifest.json"), JSON.stringify({
  status: "local_qa_only_not_for_deployment", destination: "http://127.0.0.1:5179/tools/degree",
  production_source_guard_unchanged: true, production_files_overwritten: false, files: hashes,
}, null, 2));
console.log(output);
