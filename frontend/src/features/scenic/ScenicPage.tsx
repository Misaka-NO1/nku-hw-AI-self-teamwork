import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent,
  type MouseEvent, type PointerEvent } from "react";
import { demoScenicCatalog } from "./demoCatalog";
import { buildAuthoringBundle, createSpotFromDraft, parseAuthoringBundle, type SpotDraft } from "./authoring";
import { findSpot, historicalBloomText, safeAssetPath, validateSpot,
  type ScenicCatalog, type ScenicSpot } from "./geometry";
import { activeMap, displaySpots, hasDraftConflict, type LocalDraft } from "./viewModel";

type Props = { catalog?: ScenicCatalog; enableAuthoring?: boolean };
type Point = { x_norm: number; y_norm: number };
type LocalMap = { url: string; width: number; height: number; fileName: string };
type PanStart = { pointerId: number; x: number; y: number; left: number; top: number; moved: boolean };
type ZoomAnchor = { x: number; y: number; offsetX: number; offsetY: number };

const panel: CSSProperties = { background: "#fff", border: "1px solid #dfe7f0", borderRadius: 18, padding: 20,
  boxShadow: "0 8px 30px rgba(31, 62, 83, .06)" };
const button: CSSProperties = { border: "1px solid #c4d5e5", background: "white", color: "#16466b",
  borderRadius: 10, padding: "9px 12px", cursor: "pointer" };
const field: CSSProperties = { width: "100%", boxSizing: "border-box", border: "1px solid #c4d5e5",
  borderRadius: 8, padding: "9px 10px", font: "inherit" };
const emptyDraft: SpotDraft = { name: "", description: "", tags: "" };

function querySpot(): string | null {
  return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("spot_id");
}

function queryMap(): string | null {
  return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("map_id");
}

export default function ScenicPage({ catalog = demoScenicCatalog, enableAuthoring = false }: Props) {
  const [localDraft, setLocalDraft] = useState<LocalDraft | null>(null);
  const [spotId, setSpotId] = useState<string | null>(querySpot);
  const [selectedMapId, setSelectedMapId] = useState<string | null>(queryMap);
  const [tag, setTag] = useState("all");
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [pendingPoint, setPendingPoint] = useState<Point | null>(null);
  const [draft, setDraft] = useState<SpotDraft>(emptyDraft);
  const [localMaps, setLocalMaps] = useState<Record<string, LocalMap>>({});
  const [authoringError, setAuthoringError] = useState("");
  const viewportRef = useRef<HTMLDivElement>(null);
  const panRef = useRef<PanStart | null>(null);
  const suppressClickRef = useRef(false);
  const zoomAnchorRef = useRef<ZoomAnchor | null>(null);
  const previousLocalMapsRef = useRef<Record<string, LocalMap>>({});

  const canAuthor = enableAuthoring && (import.meta as ImportMeta & { env?: { DEV?: boolean } }).env?.DEV === true
    && typeof window !== "undefined" && new URLSearchParams(window.location.search).get("mode") === "authoring";
  // Published data always comes from props. Unsaved edits are isolated to development authoring.
  const spots = displaySpots(catalog, localDraft, canAuthor);
  const hasCatalogConflict = hasDraftConflict(catalog, localDraft, canAuthor);
  const currentCatalog = useMemo(() => ({ ...catalog, spots }), [catalog, spots]);
  const current = findSpot(spotId, currentCatalog);
  const missing = spotId !== null && current === null;
  const map = activeMap(catalog.maps, current, selectedMapId);
  const visible = spots.filter((spot) => spot.map_id === map?.map_id && spot.rights_status !== "pending"
    && (tag === "all" || spot.tags.includes(tag)));
  const tags = [...new Set(spots.filter((spot) => spot.map_id === map?.map_id && spot.rights_status !== "pending")
    .flatMap((spot) => spot.tags))];
  const localMap = map ? localMaps[map.map_id] : undefined;
  const mapImage = localMap?.url ?? safeAssetPath(map?.asset_path ?? null);
  const mapWidth = localMap?.width ?? map?.width ?? 1000;
  const mapHeight = localMap?.height ?? map?.height ?? 600;
  const isDemo = map?.data_status === "demo" || spots.some((spot) => spot.data_status === "demo");
  useEffect(() => {
    const update = () => { setSpotId(querySpot()); setSelectedMapId(queryMap()); setTag("all"); };
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  useEffect(() => {
    for (const [id, previous] of Object.entries(previousLocalMapsRef.current)) {
      if (localMaps[id]?.url !== previous.url) URL.revokeObjectURL(previous.url);
    }
    previousLocalMapsRef.current = localMaps;
  }, [localMaps]);

  useEffect(() => () => {
    for (const image of Object.values(previousLocalMapsRef.current)) URL.revokeObjectURL(image.url);
  }, []);

  useEffect(() => {
    setZoom(1);
    setTag("all");
    viewportRef.current?.scrollTo({ left: 0, top: 0 });
  }, [map?.map_id]);

  useEffect(() => {
    const viewport = viewportRef.current;
    const anchor = zoomAnchorRef.current;
    if (!viewport || !anchor) return;
    viewport.scrollTo({ left: anchor.x * viewport.scrollWidth - anchor.offsetX,
      top: anchor.y * viewport.scrollHeight - anchor.offsetY });
    zoomAnchorRef.current = null;
  }, [zoom]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      changeZoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, event.clientX, event.clientY);
    };
    viewport.addEventListener("wheel", wheel, { passive: false });
    return () => viewport.removeEventListener("wheel", wheel);
  }, []);

  useEffect(() => {
    if (!current) return;
    setZoom((value) => Math.max(value, 1.5));
    const frame = requestAnimationFrame(() => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      viewport.scrollTo({ left: viewport.scrollWidth * current.x_norm - viewport.clientWidth / 2,
        top: viewport.scrollHeight * current.y_norm - viewport.clientHeight / 2,
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [current?.spot_id]);

  useEffect(() => {
    if (!pendingPoint) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPendingPoint(null);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [pendingPoint]);

  function openSpot(id: string | null) {
    const url = new URL(window.location.href);
    const target = id ? findSpot(id, currentCatalog) : current;
    if (target) {
      url.searchParams.set("map_id", target.map_id);
      setSelectedMapId(target.map_id);
    }
    if (id) url.searchParams.set("spot_id", id);
    else url.searchParams.delete("spot_id");
    window.history.pushState({}, "", url);
    setSpotId(id);
  }

  function selectMap(id: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("map_id", id);
    url.searchParams.delete("spot_id");
    window.history.pushState({}, "", url);
    setSelectedMapId(id);
    setSpotId(null);
    setAddMode(false);
  }

  function editSpots(update: (items: ScenicSpot[]) => ScenicSpot[]) {
    setLocalDraft((previous) => ({ sourceCatalog: previous?.sourceCatalog ?? catalog,
      spots: update(previous?.spots ?? catalog.spots) }));
  }

  function discardLocalDraft() {
    setLocalDraft(null);
    setPendingPoint(null);
    setAddMode(false);
    setAuthoringError("");
    if (spotId && !findSpot(spotId, catalog)) {
      const url = new URL(window.location.href);
      url.searchParams.delete("spot_id");
      window.history.replaceState({}, "", url);
      setSpotId(null);
    }
  }

  function changeZoom(factor: number, clientX?: number, clientY?: number) {
    const viewport = viewportRef.current;
    if (viewport) {
      const bounds = viewport.getBoundingClientRect();
      const offsetX = clientX === undefined ? viewport.clientWidth / 2 : clientX - bounds.left;
      const offsetY = clientY === undefined ? viewport.clientHeight / 2 : clientY - bounds.top;
      zoomAnchorRef.current = { x: (viewport.scrollLeft + offsetX) / viewport.scrollWidth,
        y: (viewport.scrollTop + offsetY) / viewport.scrollHeight, offsetX, offsetY };
    }
    setZoom((value) => Math.max(1, Math.min(3, Math.round(value * factor * 100) / 100)));
  }

  function startPan(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest("button, input, select, textarea")) return;
    panRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      left: event.currentTarget.scrollLeft, top: event.currentTarget.scrollTop, moved: false };
  }

  function movePan(event: PointerEvent<HTMLDivElement>) {
    const start = panRef.current;
    if (!start || start.pointerId !== event.pointerId) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (!start.moved && Math.hypot(dx, dy) < 5) return;
    if (!start.moved) {
      start.moved = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      setDragging(true);
    }
    event.currentTarget.scrollLeft = start.left - dx;
    event.currentTarget.scrollTop = start.top - dy;
    event.preventDefault();
  }

  function endPan(event: PointerEvent<HTMLDivElement>) {
    const start = panRef.current;
    if (!start || start.pointerId !== event.pointerId) return;
    if (start.moved) {
      suppressClickRef.current = true;
      window.setTimeout(() => { suppressClickRef.current = false; }, 0);
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    }
    panRef.current = null;
    setDragging(false);
  }

  function choosePoint(event: MouseEvent<HTMLDivElement>) {
    if (!canAuthor || !addMode || !map || suppressClickRef.current
      || event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    setPendingPoint({ x_norm: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
      y_norm: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) });
    setDraft(emptyDraft);
    setAuthoringError("");
    setAddMode(false);
  }

  function savePoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pendingPoint || !map) return;
    try {
      const id = `point-${crypto.randomUUID()}`;
      const next = createSpotFromDraft(map.map_id, pendingPoint.x_norm, pendingPoint.y_norm,
        draft, id, map.data_status === "demo" ? "demo" : "needs_verification");
      editSpots((old) => [...old, next]);
      setPendingPoint(null);
      setAuthoringError("");
      openSpot(id);
    } catch (error) {
      setAuthoringError(error instanceof Error ? error.message : "无法保存景点");
    }
  }

  function updateCurrent(changes: Partial<ScenicSpot>) {
    if (!current) return;
    editSpots((old) => old.map((spot) => spot.spot_id === current.spot_id ? { ...spot, ...changes } : spot));
  }

  async function loadLocalMap(file: File | undefined) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 20 * 1024 * 1024) {
      setAuthoringError("底图须为不超过 20 MB 的 PNG、JPEG 或 WebP 图片");
      return;
    }
    try {
      const bitmap = await createImageBitmap(file);
      const width = bitmap.width;
      const height = bitmap.height;
      bitmap.close();
      if (!width || !height) throw new Error("图片尺寸无效");
      if (!map) throw new Error("没有可编辑的底图");
      setLocalMaps((old) => ({ ...old, [map.map_id]: { url: URL.createObjectURL(file),
        width, height, fileName: file.name } }));
      setAuthoringError("");
      setZoom(1);
      viewportRef.current?.scrollTo({ left: 0, top: 0 });
    } catch {
      setAuthoringError("无法读取这张底图，请换一张有效图片");
    }
  }

  function exportCatalog() {
    const base = localDraft?.sourceCatalog ?? catalog;
    const blob = new Blob([JSON.stringify(buildAuthoringBundle({ ...base, spots }, safeAssetPath), null, 2)],
      { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "scenic-authoring-demo.json";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function importCatalog(file: File | undefined) {
    if (!file) return;
    try {
      const next = parseAuthoringBundle(await file.text(), catalog.maps.map((item) => item.map_id), validateSpot);
      setLocalDraft({ sourceCatalog: catalog, spots: next });
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
      <p style={{ margin: 0 }}>拖动地图浏览、滚轮或按钮缩放，点击标记查看点位。花期为历史资料，不代表现在正在开放。</p>
      {isDemo && <p role="status" style={{ color: "#9a5720", fontWeight: 700 }}>
        DEMO：虚构点位与示意坐标，当前无南开真实底图。
      </p>}
    </header>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 330px), 1fr))", gap: 18 }}>
      <section aria-label="地图总览" style={panel}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
          <strong>{map?.campus_id ?? "地图待提供"}</strong>
          <div style={{ display: "flex", gap: 4 }}>
            <button type="button" style={button} onClick={() => changeZoom(1 / 1.25)} aria-label="缩小地图">−</button>
            <button type="button" style={button} onClick={() => changeZoom(1.25)} aria-label="放大地图">＋</button>
          </div>
        </div>
        {catalog.maps.length > 1 && <label style={{ display: "block", marginBottom: 12 }}>
          选择底图：<select aria-label="选择底图" value={map?.map_id ?? ""}
            onChange={(event) => selectMap(event.target.value)}>
            {catalog.maps.map((candidate) => <option key={candidate.map_id} value={candidate.map_id}>
              {candidate.campus_id} · {candidate.map_id}
            </option>)}
          </select>
        </label>}
        {hasCatalogConflict && <div role="alert" style={{ border: "1px solid #bd7a23", borderRadius: 10,
          padding: 10, marginBottom: 12, background: "#fff8e9" }}>
          服务端目录已更新；本地编辑未自动合并。请先导出 JSON 备份，再选择使用新目录。
          <button type="button" style={{ ...button, marginLeft: 8 }} onClick={discardLocalDraft}>
            放弃本地编辑并使用新目录
          </button>
        </div>}
        {canAuthor && <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <button type="button" style={{ ...button, background: addMode ? "#0a7281" : "white",
            color: addMode ? "white" : "#16466b" }} onClick={() => { setAddMode((old) => !old); openSpot(null); }}>
            {addMode ? "取消添加" : "＋ 添加景点"}
          </button>
          <label style={{ ...button, display: "inline-block" }}>临时载入 2D 底图
            <input type="file" accept="image/png,image/jpeg,image/webp" aria-label="选择本地底图"
              onChange={(event) => void loadLocalMap(event.target.files?.[0])} style={{ display: "block", maxWidth: 210 }} />
          </label>
        </div>}
        {addMode && <p role="status" style={{ color: "#0a7281", fontWeight: 700 }}>在底图空白处点击，打开新增景点窗口。</p>}
        {localMap && <p role="status">当前本地底图：{localMap.fileName}（仅本次预览，不包含在 JSON 导出中）</p>}
        <div ref={viewportRef} onPointerDown={startPan} onPointerMove={movePan}
          onPointerUp={endPan} onPointerCancel={endPan}
          style={{ overflow: "auto", height: "clamp(300px, 55vh, 590px)", borderRadius: 14,
            border: "1px solid #c8d9e4", touchAction: "none", cursor: dragging ? "grabbing" : addMode ? "crosshair" : "grab" }}>
          <div onClick={choosePoint} style={{ width: `${zoom * 100}%`, aspectRatio: `${mapWidth} / ${mapHeight}`,
            minWidth: "100%", position: "relative", backgroundImage: mapImage
              ? `url("${mapImage}")` : "linear-gradient(145deg,#d9e9ec,#edf3df)",
            backgroundSize: "100% 100%", backgroundRepeat: "no-repeat" }}>
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
        <p style={{ fontSize: 13, color: "#5e7480" }}>拖动画布浏览；滚轮、触控板或按钮缩放（{zoom.toFixed(2)} 倍）。点位以相对坐标保存。</p>
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
              <h3 style={{ marginBottom: 0 }}>编辑此点位</h3>
              <label>名称<input style={field} value={current.name} onChange={(e) => updateCurrent({ name: e.target.value })} /></label>
              <label>简介<textarea style={field} value={current.description}
                onChange={(e) => updateCurrent({ description: e.target.value })} /></label>
              <label>标签（逗号分隔）<input style={field} value={current.tags.join(",")}
                onChange={(e) => updateCurrent({ tags: e.target.value.split(/[,，]/).map((v) => v.trim()).filter(Boolean) })} /></label>
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
          <h3>本地点位数据</h3><p>服务端目录为公开浏览的准确信息；此处编辑仅为开发模式的本地草稿。
            收到新目录时不会静默覆盖草稿，导出保存 JSON 与资产清单；底图文件需另外保存，页面不会上传。</p>
          <label>导入本地 JSON<input type="file" accept="application/json,.json"
            onChange={(e) => void importCatalog(e.target.files?.[0])} /></label>
          <button type="button" style={{ ...button, display: "block", marginTop: 10 }} onClick={exportCatalog}>
            导出 JSON 与资产清单
          </button>
          {authoringError && !pendingPoint && <p role="alert" style={{ color: "#a12424" }}>{authoringError}</p>}
        </div>}
      </aside>
    </div>
    {canAuthor && pendingPoint && <div style={{ position: "fixed", inset: 0, background: "rgba(11, 31, 44, .6)",
      display: "grid", placeItems: "center", zIndex: 10, padding: 16 }}>
      <section role="dialog" aria-modal="true" aria-labelledby="new-spot-title"
        style={{ ...panel, width: "min(100%, 480px)", maxHeight: "90vh", overflowY: "auto" }}>
        <form onSubmit={savePoint} style={{ display: "grid", gap: 14 }}>
          <h2 id="new-spot-title" style={{ margin: 0 }}>添加景点</h2>
          <p style={{ margin: 0, color: "#5e7480" }}>
            位置：横向 {(pendingPoint.x_norm * 100).toFixed(1)}%，纵向 {(pendingPoint.y_norm * 100).toFixed(1)}%
          </p>
          <label>名称 *<input style={field} autoFocus maxLength={128} value={draft.name}
            onChange={(event) => setDraft((old) => ({ ...old, name: event.target.value }))} /></label>
          <label>简介 *<textarea style={field} rows={4} value={draft.description}
            onChange={(event) => setDraft((old) => ({ ...old, description: event.target.value }))} /></label>
          <label>标签（逗号分隔）<input style={field} placeholder="赏花，拍照"
            value={draft.tags} onChange={(event) => setDraft((old) => ({ ...old, tags: event.target.value }))} /></label>
          <p style={{ margin: 0, color: "#5e7480", fontSize: 13 }}>照片、花期与来源待后续核验，不会自动编造。</p>
          {authoringError && <p role="alert" style={{ color: "#a12424", margin: 0 }}>{authoringError}</p>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" style={button} onClick={() => setPendingPoint(null)}>取消</button>
            <button type="submit" style={{ ...button, background: "#0a7281", color: "white" }}>保存点位</button>
          </div>
        </form>
      </section>
    </div>}
  </main>;
}
