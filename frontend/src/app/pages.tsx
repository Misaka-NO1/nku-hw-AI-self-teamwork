/**
 * 统一页面导出（契约 §2）。A/B/D 的组件未交付前导出明确占位；
 * 队友组件落地后只需替换此处 import，路由不变。
 */
import { PlaceholderPage } from "./PlaceholderPage";
export { AffairsPage } from "../features/affairs/AffairsPage";
export { DegreePage } from "../features/degree/DegreePage";
export { default as ImportPage } from "../features/import/ImportPage";
export { default as TimetablePage } from "../features/timetable/TimetablePage";

export function ScenicPage() {
  return <PlaceholderPage componentName="ScenicPage" owner="A" />;
}

export function StudyPage() {
  return <PlaceholderPage componentName="StudyPage" owner="A" />;
}

export function TasksPage() {
  return <PlaceholderPage componentName="TasksPage" owner="D" />;
}
