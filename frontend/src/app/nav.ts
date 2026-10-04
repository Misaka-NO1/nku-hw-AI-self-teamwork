/** 可视化工具导航；业务深链接仍由 routes.tsx 保留，主入口是 NK-GeniOS。 */
export interface ToolNavItem {
  path: string;
  label: string;
}

export const TOOL_NAV: ToolNavItem[] = [
  { path: "/tools/timetable", label: "课表" },
  { path: "/tools/map", label: "赏景地图" },
];

export interface ToolNavOptions {
  publicContentOnly: boolean;
  identityPilot: boolean;
  publicContentOrigin?: string;
  timetableOrigin?: string;
}

/** undefined 表示未配置跨服务地址，不能误导用户进入本服务不提供的页面。 */
export function toolNavHref(path: string, options: ToolNavOptions): string | undefined {
  const crossOrigin = path === "/tools/timetable" && options.publicContentOnly
    ? options.timetableOrigin
    : path === "/tools/map" && options.identityPilot
      ? options.publicContentOrigin
      : null;
  if (crossOrigin === null) return path;
  if (!crossOrigin) return undefined;
  try {
    const url = new URL(crossOrigin);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
    return url.origin + path;
  } catch {
    return undefined;
  }
}
