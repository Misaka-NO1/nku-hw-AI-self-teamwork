import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from "react";
import { demoScenicCatalog } from "./demoCatalog";
import { buildAuthoringBundle, parseAuthoringBundle } from "./authoring";
import { findSpot, historicalBloomText, safeAssetPath, validateSpot, type ScenicCatalog, type ScenicSpot } from "./geometry";

type Props = { catalog?: ScenicCatalog; enableAuthoring?: boolean };

const panel: CSSProperties = { background: "#fff", border: "1px solid #dfe7f0", borderRadius: 18, padding: 20,
  boxShadow: "0 8px 30px rgba(31, 62, 83, .06)" };
const button: CSSProperties = { border: "1px solid #c4d5e5", background: "white", color: "#16466b",
  borderRadius: 10, padding: "9px 12px", cursor: "pointer" };

function querySpot(): string | null {
  return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("spot_id");
}

export default function ScenicPage({ catalog = demoScenicCatalog, enableAuthoring = false }: Props) {
  const [spots, setSpots] = useState<ScenicSpot[]>(catalog.spots);
  const [spotId, setSpotId] = useState<string | null>(querySpot);
  const [tag, setTag] = useState("all");
  const [zoom, setZoom] = useState(1);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [authoringError, setAuthoringError] = useState("");
  const map = catalog.maps[0];
  const currentCatalog = useMemo(() => ({ ...catalog, spots }), [catalog, spots]);
  const current = findSpot(spotId, currentCatalog);
  const missing = spotId !== null && current === null;
  const tags = [...new Set(spots.flatMap((spot) => spot.tags))];
  const visible = spots.filter((spot) => spot.map_id === map?.map_id && spot.rights_status !== "pending"
    && (tag === "all" || spot.tags.includes(tag)));
  const mapImage = safeAssetPath(map?.asset_path ?? null);
  const isDemo = map?.data_status === "demo" || spots.some((spot) => spot.data_status === "demo");
  const canAuthor = enableAuthoring && (import.meta as ImportMeta & { env?: { DEV?: boolean } }).env?.DEV === true
    && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mode") === "authoring";

  useEffect(() => {
    const update = () => setSpotId(querySpot());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  useEffect(() => {
    if (!current) {
      setZoom(1);
      viewportRef.current?.scrollTo({ left: 0, top: 0 });
      return;
    }
    setZoom((old) => Math.max(old, 1.5));
    const frame = requestAnimationFrame(() => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const x = viewport.scrollWidth * current.x_norm - viewport.clientWidth / 2;
      const y = viewport.scrollHeight * current.y_norm - viewport.clientHeight / 2;
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      viewport.scrollTo({ left: x, top: y, behavior: reduced ? "auto" : "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [current?.spot_id, zoom]);

  function openSpot(id: string | null) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("spot_id", id);
    else url.searchParams.delete("spot_id");
    window.history.pushState({}, "", url);
    setSpotId(id);
  }

  function addPoint(event: MouseEvent<HTMLDivElement>) {
    if (!canAuthor || !map || event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x_norm = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y_norm = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    const id = `demo-new-${crypto.randomUUID().slice(0, 8)}`;
    setSpots((old) => [...old, { spot_id: id, map_id: map.map_id, name: "新示例点（虚构）",
      x_norm, y_norm, tags: [], description: "待填写；非真实校园点位", photos: [],
      historical_bloom_months: [], observation: null, rights_status: "owned", data_status: "demo" }]);
    openSpot(id);
  }

  function updateCurrent(changes: Partial<ScenicSpot>) {
    if (!current) return;
    setSpots((old) => old.map((spot) => spot.spot_id === current.spot_id ? { ...spot, ...changes } : spot));
  }

  function exportCatalog() {
    const blob = new Blob([JSON.stringify(buildAuthoringBundle({ ...catalog, spots }, safeAssetPath), null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "scenic-authoring-demo.json";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function importCatalog(file: File | undefined) {
    if (!file) return;
    try {
      const next = parseAuthoringBundle(await file.text(), map?.map_id ?? "", validateSpot);
      setSpots(next);
      setAuthoringError("");
      if (spotId && !next.some((spot) => spot.spot_id === spotId)) openSpot(null);
    } catch (error) {
      setAuthoringError(error instanceof Error ? error.message : "无法读取目录");
    }
  }

  return <main style={{ fontFamily: "system-ui, sans-serif", background: "#f4f8fb", minHeight: "100vh",
    padding: "clamp(16px, 3vw, 36px)", color: "#183447" }}>
    <header style={{ marginBottom: 20 }}>
      <p style={{ margin: 0, color: "#18747d", fontWeight: 700 }}>南开校园助手 · 赏景地图</p>
      <h1 style={{ margin: "8px 0" }}>校园赏景点位</h1>
      <p style={{ margin: 0 }}>按标签找地点，点击标记查看点位资料。花期为历史资料，不代表现在正在开放。</p>
      {isDemo && <p role="status" style={{ color: "#9a5720", fontWeight: 700 }}>DEMO：虚构点位与示意坐标，当前无南开真实底图。</p>}
    </header>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 330px), 1fr))", gap: 18 }}>
      <section aria-label="地图总览" style={panel}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
          <strong>{map?.campus_id ?? "地图待提供"}</strong>
          <div><button type="button" style={button} onClick={() => setZoom(Math.max(1, zoom - 0.25))} aria-label="缩小地图">−</button>{" "}
            <button type="button" style={button} onClick={() => setZoom(Math.min(2.5, zoom + 0.25))} aria-label="放大地图">＋</button></div>
        </div>
        <div ref={viewportRef} style={{ overflow: "auto", borderRadius: 14, border: "1px solid #c8d9e4" }}>
          <div onClick={addPoint} style={{ width: `${zoom * 100}%`, aspectRatio: `${map?.width ?? 1000} / ${map?.height ?? 600}`,
            minWidth: "100%", position: "relative", background: mapImage
              ? `center / cover url(${mapImage})` : "linear-gradient(145deg,#d9e9ec,#edf3df)" }}>
            {!mapImage && <span style={{ position: "absolute", top: 12, left: 12, pointerEvents: "none", color: "#526b72" }}>
              待提供授权底图 · 示意画布
            </span>}
            {visible.map((spot) => <button key={spot.spot_id} type="button" onClick={() => openSpot(spot.spot_id)}
              aria-label={`查看${spot.name}`} title={spot.name} style={{ position: "absolute", left: `${spot.x_norm * 100}%`,
                top: `${spot.y_norm * 100}%`, transform: "translate(-50%,-50%)", borderRadius: 20,
                border: "3px solid white", background: spot.spot_id === spotId ? "#ec7b52" : "#0a7281",
                color: "white", width: 28, height: 28, cursor: "pointer" }}>●</button>)}
          </div>
        </div>
        <p style={{ fontSize: 13, color: "#5e7480" }}>点位位置相对图片保存；更换底图尺寸时保持比例。当前放大 {zoom.toFixed(2)} 倍。</p>
      </section>
      <aside style={panel} aria-label="点位信息">
        {missing ? <><h2>找不到这个点位</h2><p>spot_id“{spotId}”不存在或未公开，未替换为其他地点。</p>
          <button type="button" style={button} onClick={() => openSpot(null)}>返回总览</button></>
          : current ? <><button type="button" style={button} onClick={() => openSpot(null)}>← 返回总览</button>
            <h2>{current.name}</h2><p>{current.description}</p>
            <p>{historicalBloomText(current)}</p>
            <p>标签：{current.tags.length ? current.tags.join("、") : "暂无"}</p>
            {current.photos.filter((photo) => photo.rights_status === "owned" || photo.rights_status === "authorized")
              .filter((photo) => safeAssetPath(photo.asset_path)).map((photo) => <figure key={photo.photo_id}>
                <img src={safeAssetPath(photo.asset_path) ?? ""} alt={photo.caption} loading="lazy" style={{ maxWidth: "100%" }} />
                <figcaption>{photo.caption}</figcaption></figure>)}
            {!current.photos.some((photo) => safeAssetPath(photo.asset_path) && ["owned", "authorized"].includes(photo.rights_status))
              && <p role="status">此点位尚无获授权的照片；素材待提供。</p>}
            {canAuthor && <div style={{ display: "grid", gap: 8, borderTop: "1px solid #ddd", paddingTop: 12 }}>
              <label>名称<input value={current.name} onChange={(e) => updateCurrent({ name: e.target.value })} /></label>
              <label>简介<textarea value={current.description} onChange={(e) => updateCurrent({ description: e.target.value })} /></label>
              <label>标签（逗号分隔）<input value={current.tags.join(",")} onChange={(e) => updateCurrent({ tags: e.target.value.split(",").map((v) => v.trim()).filter(Boolean) })} /></label>
              <label>照片资源路径（assets/ 下）<input placeholder="assets/example.jpg" onBlur={(e) => {
                const path = e.target.value.trim();
                if (path && safeAssetPath(path)) updateCurrent({ photos: [{ photo_id: `photo-${current.spot_id}`,
                  asset_path: path, caption: "待核验照片", captured_at: null, rights_status: "pending" }] });
                else if (path) setAuthoringError("只接受 assets/ 下的相对路径");
              }} /></label>
            </div>}
          </> : <><h2>全部点位</h2>
            <label>筛选标签：<select value={tag} onChange={(e) => setTag(e.target.value)}>
              <option value="all">全部</option>{tags.map((item) => <option key={item} value={item}>{item}</option>)}
            </select></label>
            <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 10 }}>
              {visible.map((spot) => <li key={spot.spot_id}><button type="button" style={{ ...button, width: "100%", textAlign: "left" }}
                onClick={() => openSpot(spot.spot_id)}>{spot.name}<small style={{ display: "block" }}>{spot.tags.join(" · ")}</small></button></li>)}
            </ul>{visible.length === 0 && <p>此筛选条件下暂无点位。</p>}
          </>}
        {canAuthor && <div style={{ borderTop: "1px solid #ddd", paddingTop: 12 }}>
          <h3>本地素材编辑（仅开发模式）</h3><p>点击示意画布添加点位；导出仅保存 JSON 和资产清单，不上传文件。</p>
          <label>导入本地 JSON<input type="file" accept="application/json,.json" onChange={(e) => void importCatalog(e.target.files?.[0])} /></label>
          <button type="button" style={button} onClick={exportCatalog}>导出 JSON 与资产清单</button>
          {authoringError && <p role="alert">{authoringError}</p>}
        </div>}
      </aside>
    </div>
  </main>;
}
