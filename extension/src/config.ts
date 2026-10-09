/**
 * 扩展白名单配置（B06）。
 *
 * 安全边界：
 * - 只在用户点击扩展图标后读取页面（activeTab）；
 * - 只允许白名单 origin + path + 课程区域；
 * - 只允许已核查的南开教务课表页和团队导入页；
 * - 虚构测试页只允许出现在开发构建，不带入生产。
 */

export interface ExtractionWhitelist {
  origins: string[];
  paths: string[];
}

/** 生产白名单：2026-10-07 本人只读核查后启用（docs/evidence/B/adapter-observation.md）。 */
export const PRODUCTION_WHITELIST: ExtractionWhitelist = {
  origins: ["https://eamis.nankai.edu.cn"],
  paths: ["/eams/courseTableForStd"],
};

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

/**
 * 课表板块 App 的 origin（自动回传目标，EXT-B11）。
 * 观察值只回传到团队导入页本地核对，未经确认不写数据库。
 */
export const APP_ORIGINS = ["https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com"];
export const APP_IMPORT_PATH = "/tools/import";

export function isAppUrl(url: string): boolean {
  try {
    const parsed=new URL(url);
    return APP_ORIGINS.includes(parsed.origin) && parsed.pathname===APP_IMPORT_PATH;
  } catch {
    return false;
  }
}
