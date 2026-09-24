import { useEffect, useState, type CSSProperties } from "react";
import { demoStudyItems, filterStudyItems, publicStudyItems, type StudyItem } from "./demoCatalog";
import { resolveDownloadUrl, type DownloadUrlFor } from "./downloadUrl";
import { readStudyRoute, studyRouteUrl } from "./navigation";

type Props = { materials?: StudyItem[]; enableDownloads?: boolean; downloadUrlFor?: DownloadUrlFor };
const card: CSSProperties = { background: "white", border: "1px solid #dce4ef", borderRadius: 16, padding: 20,
  boxShadow: "0 8px 28px rgba(30,52,77,.05)" };

function params() {
  return readStudyRoute(typeof window === "undefined" ? "" : window.location.search);
}

export default function StudyPage({ materials = demoStudyItems, enableDownloads = false, downloadUrlFor }: Props) {
  const initial = params();
  const availableCourses = [...new Set(publicStudyItems(materials).map((item) => item.course_id))];
  const [courseId, setCourseId] = useState(initial.courseId || availableCourses[0] || "");
  const [materialId, setMaterialId] = useState(initial.materialId);
  const [topic, setTopic] = useState("");
  const publicItems = publicStudyItems(materials);
  const courses = [...new Set(publicItems.map((item) => item.course_id))];
  const results = filterStudyItems(materials, courseId, topic);
  const selected = materialId ? publicItems.find((item) => item.material_id === materialId && item.course_id === courseId) : null;
  const downloadUrl = enableDownloads && selected?.content_available
    && ["owned", "authorized"].includes(selected.rights_status)
    ? resolveDownloadUrl(selected.material_id, downloadUrlFor) : null;

  useEffect(() => {
    const onBack = () => {
      const next = params();
      setCourseId(next.courseId || courses[0] || "");
      setMaterialId(next.materialId);
    };
    window.addEventListener("popstate", onBack);
    return () => window.removeEventListener("popstate", onBack);
  }, [courses[0]]);

  useEffect(() => {
    if (!initial.courseId && !courses.includes(courseId)) setCourseId(courses[0] || "");
  }, [courses.join("|"), courseId, initial.courseId]);

  function changeCourse(nextCourseId: string) {
    window.history.pushState({}, "", studyRouteUrl(window.location.href,
      { courseId: nextCourseId, materialId: "" }));
    setCourseId(nextCourseId);
    setMaterialId("");
    setTopic("");
  }

  function select(item: StudyItem | null) {
    window.history.pushState({}, "", studyRouteUrl(window.location.href,
      { courseId: item?.course_id ?? courseId, materialId: item?.material_id ?? "" }));
    if (item) setCourseId(item.course_id);
    setMaterialId(item?.material_id ?? "");
  }

  return <main style={{ fontFamily: "system-ui, sans-serif", padding: "clamp(16px,3vw,36px)",
    minHeight: "100vh", background: "#f5f7fb", color: "#213349" }}>
    <header><p style={{ color: "#4d58a5", fontWeight: 700 }}>南开校园助手 · 期末复习资料</p>
      <h1>按课程找复习资料</h1>
      <p>先选课程，再查主题。目录线索与可检索正文分开显示；没有正文时无法据此总结。</p>
      {materials.some((item) => item.material_id.startsWith("demo-")) && <p role="status" style={{ color: "#925223", fontWeight: 700 }}>
        DEMO：当前仅有自创测试笔记，不是南开教学资料或真题。</p>}</header>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(min(100%,340px),1fr))", gap: 18 }}>
      <section style={card} aria-label="资料检索">
        <label style={{ display: "block", marginBottom: 12 }}>课程 ID<br />
          <select value={courseId} onChange={(e) => changeCourse(e.target.value)}>
            {!courses.includes(courseId) && <option value={courseId}>{courseId || "请选择课程"}</option>}
            {courses.map((id) => <option key={id} value={id}>{id}</option>)}
          </select></label>
        <label>主题关键词<br /><input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="如：递归" /></label>
        <p>{results.length} 条公开结果</p>
        <ul style={{ padding: 0, listStyle: "none", display: "grid", gap: 10 }}>
          {results.map((item) => <li key={item.material_id}>
            <button type="button" onClick={() => select(item)} style={{ ...card, cursor: "pointer", width: "100%", textAlign: "left" }}>
              <strong>{item.title}</strong><span style={{ display: "block", marginTop: 6 }}>版本 {item.version} · {item.material_type}</span>
              <span style={{ display: "block", color: item.content_available ? "#08745c" : "#916225" }}>
                {item.content_available ? "有可核验正文" : "仅有索引，暂无正文"}</span>
            </button></li>)}
        </ul>
        {results.length === 0 && <p role="status">未找到该课程和主题下的公开资料，请检查课程 ID；不会转用其他课程材料。</p>}
      </section>
      <aside style={card} aria-label="资料详情">
        {materialId && !selected ? <><h2>找不到此材料</h2><p>材料不存在、课程不匹配或无公开权限。</p>
          <button type="button" onClick={() => select(null)}>返回列表</button></>
          : selected ? <><button type="button" onClick={() => select(null)}>← 返回列表</button>
            <h2>{selected.title}</h2>
            <p>课程：{selected.course_id} · 版本：{selected.version} · 权限：{selected.access_scope} / {selected.rights_status}</p>
            <p>来源：{selected.source_label}</p>
            <p>核验日期：{selected.reviewed_at ?? "未记录"}</p>
            {selected.content_available && selected.evidence.length ? <><h3>可定位的正文片段</h3>
              {selected.evidence.map((chunk) => <article key={chunk.chunk_id} style={{ borderTop: "1px solid #e4e9f1" }}>
                <h4>{chunk.heading}</h4><p>{chunk.excerpt}</p>
                <small>定位：{chunk.source_excerpt_ref}{chunk.page_label ? ` · 第 ${chunk.page_label} 页` : " · 原文无页码"}</small>
              </article>)}</> : selected.content_available
                ? <p role="status">此材料有可用正文，但本次检索未返回正文片段；不能把标题命中当作正文证据。</p>
                : <p role="status">此条只有目录索引，无法基于它生成正文总结或复习提纲。</p>}
            {downloadUrl
              ? <a href={downloadUrl}>下载已授权材料</a>
              : <p>下载接口待 D 接入，或当前资料不允许下载。</p>}
          </> : <><h2>选择一份材料</h2><p>点击左侧结果查看来源、版本和正文状态。</p></>}
      </aside>
    </div>
  </main>;
}
