import { createRoot } from "react-dom/client";
import ScenicPage from "../ScenicPage";
import { demoScenicCatalog } from "../demoCatalog";
import StudyPage from "../../study/StudyPage";
import { demoStudyItems } from "../../study/demoCatalog";

const results = document.getElementById("results");
const fixture = document.getElementById("fixture");
if (!results || !fixture) throw new Error("Review fixture elements missing");
const root = createRoot(fixture);

function report(name: string, ok: boolean, detail = "") {
  const item = document.createElement("li");
  item.textContent = `${ok ? "PASS" : "FAIL"} ${name}${detail ? `：${detail}` : ""}`;
  item.style.color = ok ? "#08745c" : "#aa2626";
  results?.append(item);
}

async function until(check: () => boolean, label: string) {
  const deadline = performance.now() + 2000;
  while (performance.now() < deadline) {
    if (check()) return;
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  }
  throw new Error(`${label} timed out`);
}

function pushInitial(search: string) {
  window.history.replaceState({}, "", `/review.html${search}`);
}

async function run() {
  try {
    pushInitial("");
    const emptyCatalog = { ...demoScenicCatalog, spots: [] };
    root.render(<ScenicPage key="async" catalog={emptyCatalog} />);
    await until(() => fixture?.textContent?.includes("此筛选条件下暂无点位。") ?? false, "empty map");
    const updatedCatalog = { ...demoScenicCatalog, spots: [...demoScenicCatalog.spots] };
    root.render(<ScenicPage key="async" catalog={updatedCatalog} />);
    await until(() => fixture?.querySelectorAll('button[aria-label^="查看示例"]').length === 3, "updated map");
    report("1. 异步目录更新后显示新点位", true);
  } catch (error) { report("1. 异步目录更新后显示新点位", false, String(error)); }

  try {
    pushInitial("?spot_id=review-second-spot");
    const first = demoScenicCatalog.maps[0];
    const second = { ...first, map_id: "review-map-02", campus_id: "second-campus" };
    const spot = { ...demoScenicCatalog.spots[0], spot_id: "review-second-spot",
      map_id: second.map_id, name: "第二张地图的景点" };
    root.render(<ScenicPage key="second-map" catalog={{ ...demoScenicCatalog,
      maps: [first, second], spots: [spot] }} />);
    await until(() => fixture?.querySelector('button[aria-label="查看第二张地图的景点"]') !== null,
      "second map marker");
    if (!fixture?.textContent?.includes("second-campus")) throw new Error("wrong map title");
    report("3. 深链接切换到景点所属底图并显示标记", true);
  } catch (error) { report("3. 深链接切换到景点所属底图并显示标记", false, String(error)); }

  try {
    const first = { ...demoStudyItems[0], course_id: "CS101", material_id: "review-old" };
    const second = { ...demoStudyItems[0], course_id: "CS102", material_id: "review-new" };
    pushInitial("?course_id=CS101&material_id=review-old");
    root.render(<StudyPage key="study" materials={[first, second]} enableDownloads
      downloadUrlFor={(id) => `https://api.example.test/api/v1/study/materials/${encodeURIComponent(id)}/download`} />);
    await until(() => fixture?.querySelector('a[href^="https://api.example.test/"]') !== null, "API link");
    report("5. 下载链接使用注入的后端域名", true);

    const select = fixture?.querySelector<HTMLSelectElement>('section[aria-label="资料检索"] select');
    if (!select) throw new Error("course selector missing");
    select.value = "CS102";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await until(() => new URLSearchParams(location.search).get("course_id") === "CS102", "course URL");
    if (new URLSearchParams(location.search).has("material_id")) throw new Error("stale material_id");
    report("4a. 切换课程同步 URL 且清除旧材料", true);

    const wentBack = new Promise<void>((resolve) => window.addEventListener("popstate", () => resolve(), { once: true }));
    history.back();
    await wentBack;
    await until(() => select.value === "CS101" && fixture?.textContent?.includes("程序设计示例笔记") === true,
      "browser back");
    const wentForward = new Promise<void>((resolve) => window.addEventListener("popstate", () => resolve(), { once: true }));
    history.forward();
    await wentForward;
    await until(() => select.value === "CS102", "browser forward");
    report("4b. 浏览器前进后退恢复课程与材料", true);
  } catch (error) { report("4/5. 资料页 URL 与下载链接交互", false, String(error)); }
}

void run();
