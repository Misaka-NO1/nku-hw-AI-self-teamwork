/** C 独占的路由表。刷新任一 /tools/* 路径都应落到对应页面或明确占位。 */
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";
import {
  AffairsPage,
  DegreePage,
  ImportPage,
  ScenicPage,
  StudyPage,
  TasksPage,
  TimetablePage,
} from "./pages";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/tools/affairs" replace />} />
        <Route path="/tools/import" element={<ImportPage />} />
        <Route path="/tools/timetable" element={<TimetablePage />} />
        <Route path="/tools/tasks" element={<TasksPage />} />
        <Route path="/tools/map" element={<ScenicPage />} />
        <Route path="/tools/study" element={<StudyPage />} />
        <Route path="/tools/affairs" element={<AffairsPage />} />
        <Route path="/tools/degree" element={<DegreePage />} />
        <Route
          path="*"
          element={
            <section>
              <h2>页面不存在</h2>
              <p>未识别的工具路径，请从上方导航进入。</p>
            </section>
          }
        />
      </Route>
    </Routes>
  );
}
