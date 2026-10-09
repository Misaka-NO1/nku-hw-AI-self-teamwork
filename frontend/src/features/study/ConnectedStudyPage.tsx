import { useEffect, useState, type FormEvent } from "react";
import { apiClient, downloadOriginalPdf } from "../../shared/api/client";

interface Material {
  materialId: string; courseId: string; title: string; version: string;
  fileName: string; fileFormat: string; sourceLabel: string;
  evidence: {chunkId: string; heading: string; pageLabel: string; excerpt: string}[];
}
interface Course {courseId: string; title: string; semester: string; materialCount: number}
interface Catalog {courses: Course[]; materials: Material[]; total: number}

export default function ConnectedStudyPage() {
  const initial = new URLSearchParams(window.location.search);
  const [course, setCourse] = useState(initial.get("course_id") || "");
  const [topic, setTopic] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [items, setItems] = useState<Material[]>([]);
  const [query, setQuery] = useState({courseId: course, topic: ""});
  const [detail, setDetail] = useState<Material | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState("");
  const [downloadStatus, setDownloadStatus] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    apiClient.get<Catalog>("/api/v1/study/catalog", {signal: controller.signal})
      .then(value => {if (!controller.signal.aborted) setCatalog(value);})
      .catch(e => {if (!controller.signal.aborted) {setError(String(e.message)); setLoading(false);}});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const back = () => {
      const id = new URLSearchParams(window.location.search).get("course_id") || "";
      setCourse(id); setTopic(""); setQuery({courseId: id, topic: ""}); setDetail(null);
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  useEffect(() => {
    if (!catalog) return;
    const controller = new AbortController();
    setLoading(true); setError(""); setDetail(null);
    const selected = catalog.materials.filter(item => !query.courseId || item.courseId === query.courseId);
    if (!query.topic.trim()) {setItems(selected); setLoading(false); return () => controller.abort();}
    const courses = query.courseId ? [query.courseId] : catalog.courses.map(item => item.courseId);
    void Promise.all(courses.map(id => apiClient.get<Material[]>(`/api/v1/study/materials?${new URLSearchParams({query: JSON.stringify({course_id: id, topic: query.topic.trim(), limit: 20})})}`,
      {signal: controller.signal})))
      .then(results => {if (!controller.signal.aborted) setItems(results.flat());})
      .catch(e => {if (!controller.signal.aborted) {setItems([]); setError(String(e.message));}})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [catalog, query]);
  function navigate(id: string) {
    window.history.pushState({}, "", id ? `/tools/study?${new URLSearchParams({course_id: id})}` : "/tools/study");
    setCourse(id); setTopic(""); setQuery({courseId: id, topic: ""});
  }
  function search(e: FormEvent) {e.preventDefault(); setQuery({courseId: course, topic});}
  async function download(item: Material) {
    setDownloading(item.materialId); setDownloadStatus(`正在下载 ${item.fileName}…`);
    try {
      const blob = await downloadOriginalPdf(item.materialId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = item.fileName; document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloadStatus(`已交给浏览器下载：${item.fileName}，请查看浏览器下载列表`);
    } catch (e) {setDownloadStatus(e instanceof Error ? e.message : "下载失败，请重试");}
    finally {setDownloading("");}
  }
  async function preview(item: Material) {
    try {setDetail(await apiClient.get<Material>(`/api/v1/study/materials/${encodeURIComponent(item.materialId)}`));}
    catch(e) {setError(e instanceof Error ? e.message : "预览失败");}
  }
  const shownCourses = catalog?.courses.filter(item => items.some(file => file.courseId === item.courseId)) || [];
  return <section style={{maxWidth: 1100, margin: "auto", padding: "24px 16px"}}>
    <h1>大一期末复习资料库</h1>
    <p>全部原文件按课程展示，点击“下载”直接保存，不必进入详情页。</p>
    <p>历史复习资料，不代表今年考试范围。现有原文件为 PDF，保留原格式。</p>
    <form onSubmit={search} style={{display: "flex", flexWrap: "wrap", gap: 12, margin: "24px 0"}}>
      <label>课程与学期 <select aria-label="课程与学期" value={course} onChange={e => navigate(e.target.value)}>
        <option value="">全部课程（{catalog?.total ?? "…"} 份）</option>
        {course && !catalog?.courses.some(item => item.courseId === course) && <option value={course}>{course}（未收录）</option>}
        {catalog?.courses.map(item => <option key={item.courseId} value={item.courseId}>{item.title} · {item.materialCount} 份</option>)}
      </select></label>
      <label>关键词 <input aria-label="主题关键词" maxLength={500} value={topic} onChange={e => setTopic(e.target.value)} placeholder="不填则显示全部原文件" /></label>
      <button disabled={loading}>筛选</button>
      <button type="button" onClick={() => navigate("")}>显示全部资料</button>
    </form>
    {loading && <p role="status">正在加载资料…</p>}
    {error && <p role="alert">{error}</p>}
    {downloadStatus && <p role="status">{downloadStatus}</p>}
    {!loading && !error && <p>当前展示 {items.length} 份 / 资料库共 {catalog?.total ?? 0} 份</p>}
    {!loading && !items.length && !error && <p>未找到匹配的公开资料。点击“显示全部资料”查看完整目录。</p>}
    {shownCourses.map(group => <section key={group.courseId} style={{marginTop: 28}}>
      <h2>{group.title}</h2>
      <ul style={{listStyle: "none", padding: 0, display: "grid", gap: 12}}>
        {items.filter(item => item.courseId === group.courseId).map(item => <li key={item.materialId}
          style={{display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16, padding: 18, border: "1px solid #dce4ef", borderRadius: 12, background: "white"}}>
          <div style={{flex: "1 1 250px"}}><strong>{item.fileName}</strong><small style={{display: "block", marginTop: 6}}>PDF 原文件 · {item.sourceLabel}</small></div>
          <button type="button" disabled={Boolean(downloading)} onClick={() => void download(item)} aria-label={`下载 ${item.fileName}`}
            style={{padding: "10px 22px", color: "white", background: "#315c50", border: 0, borderRadius: 8, cursor: "pointer"}}>
            {downloading === item.materialId ? "下载中…" : "下载"}</button>
          <button type="button" onClick={() => void preview(item)}>查看文本（可选）</button>
        </li>)}
      </ul>
    </section>)}
    {detail && <article style={{marginTop: 32, overflowWrap: "anywhere"}}><button onClick={() => setDetail(null)}>收起文本</button>
      <h2>{detail.title} · 提取文本</h2><p>提取/OCR 未逐页校对；公式、代码、图表请以原文件为准。</p>
      {detail.evidence.map(chunk => <section key={chunk.chunkId}><h3>{chunk.heading}</h3><p style={{whiteSpace: "pre-wrap"}}>{chunk.excerpt}</p></section>)}
    </article>}
  </section>;
}
