/**
 * 扩展白名单配置（B06）。
 *
 * 安全边界：
 * - 只在用户点击扩展图标后读取页面（activeTab）；
 * - 只允许白名单 origin + path + 课程区域；
 * - 生产域名白名单默认为空：真实教务适配器未完成授权核查前不猜任何南开域名；
 * - 虚构测试页只允许出现在开发构建，不带入生产。
 */

export interface ExtractionWhitelist {
  origins: string[];
  paths: string[];
}

/** 生产白名单：故意为空（WAITING_HUMAN，见 docs/evidence/B/adapter-observation.md）。 */
export const PRODUCTION_WHITELIST: ExtractionWhitelist = { origins: [], paths: [] };

/** 开发/虚构测试白名单：仅用于 fixtures 页面，不得带入生产构建。 */
export const DEV_FIXTURE_WHITELIST: ExtractionWhitelist = {
  origins: ["http://localhost", "https://fixtures.example.invalid"],
  paths: ["/demo/timetable"],
};

/** 上传目标固定为本团队后端，不接受页面提供的任意 fetch URL。 */
export const BACKEND_ORIGIN = "";

export function isExtractionAllowed(url: string, whitelist: ExtractionWhitelist): boolean {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  const originOk = whitelist.origins.includes(parsed.origin);
  const pathOk = whitelist.paths.some((path) => parsed.pathname.startsWith(path));
  return originOk && pathOk;
}
