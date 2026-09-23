/** 工具导航表：与 contracts/integration-conventions.md §2 的路径一致。 */
export interface ToolNavItem {
  path: string;
  label: string;
}

export const TOOL_NAV: ToolNavItem[] = [
  { path: "/tools/import", label: "课表导入" },
  { path: "/tools/timetable", label: "课表" },
  { path: "/tools/tasks", label: "待办" },
  { path: "/tools/map", label: "赏景地图" },
  { path: "/tools/study", label: "期末复习" },
  { path: "/tools/affairs", label: "校园事务" },
  { path: "/tools/degree", label: "培养方案" },
];
