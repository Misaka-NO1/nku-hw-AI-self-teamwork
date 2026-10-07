/**
 * 统一页面导出（契约 §2）。A/B/D 的组件未交付前导出明确占位；
 * 队友组件落地后只需替换此处 import，路由不变。
 */
export { default as StudyPage } from "../features/study/ConnectedStudyPage";
export { AffairsPage } from "../features/affairs/AffairsPage";
export { DegreePage } from "../features/degree/DegreePage";
export { default as ImportPage } from "../features/import/ConnectedImportPage";
export { default as TimetablePage } from "../features/timetable/ConnectedTimetablePage";
export { default as CalendarPage } from "../features/calendar/CalendarPage";
import FixtureTasksPage from "../features/tasks/TasksPage";
import NoticePilotPage from "../features/notice-pilot/TasksPage";
export function TasksPage() {
  const pilot = import.meta.env.VITE_NOTICE_TEXT_PILOT === "true"
    && new URLSearchParams(window.location.search).get("notice_pilot") === "1";
  return pilot ? <NoticePilotPage /> : <FixtureTasksPage />;
}

export function ScenicPage() {
  const params = new URLSearchParams(window.location.search);
  const spot = params.get("spot_id");
  const source = `/campus-map/index.html${spot ? `?${new URLSearchParams({spot_id: spot})}` : ""}`;
  return <section><h1>南开 · 校园赏景地图</h1>
    <p>历史观赏建议不代表当前花况；点击景点查看实景照片。</p>
    <iframe title="南开校园三维地图" src={source} style={{width: "100%", height: "80vh", minHeight: 550, border: 0}} />
  </section>;
}
