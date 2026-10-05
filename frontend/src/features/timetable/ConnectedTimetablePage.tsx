import { useEffect, useState } from "react";
import TimetablePage from "./TimetablePage";
import { scheduleApi, type CurrentSchedule } from "../import/connectedApi";
import type { DemoSession } from "../tasks/api";
import { useBrowserSession } from "../auth/useBrowserSession";
import { apiClient, ApiError } from "../../shared/api/client";

interface FreeTime { slots: { start: string; end: string; durationMinutes: number }[]; coverage: { completeness?: string; scope?: string }; needsConfirmation: string[] }
export default function ConnectedTimetablePage() {
  const identityPilot = import.meta.env.VITE_IDENTITY_PILOT === "true";
  const browserSession = useBrowserSession(identityPilot);
  const { session, checking, needsLogin, recoveryError } = browserSession;
  return <section>
    {checking && <p role="status">正在核验当前浏览器会话；完成前不能读取课表或查询空档。</p>}
    {!!recoveryError && <p role="alert">{errorText(recoveryError)}</p>}
    {identityPilot && needsLogin && <p>当前浏览器会话已失效。<a href="/tools/login">登录测试账号</a>后重新打开课表；不会自动保存。</p>}
    {identityPilot && !!recoveryError && !needsLogin && <button disabled={checking} onClick={browserSession.retryRecovery}>重新核验浏览器会话</button>}
    {!checking && !recoveryError && <SessionTimetable key={session?.workspaceRef ?? "no-session"} session={session} onAuthError={browserSession.rejectExpiredSession} />}
  </section>;
}
function errorText(e: unknown) {
  return e instanceof ApiError ? `${e.message}（${e.code} · ${e.requestId ?? "无请求编号"}）` : String(e);
}
function SessionTimetable({ session, onAuthError }: { session: DemoSession | null; onAuthError: (error: unknown) => void }) {
  const [saved, setSaved] = useState<CurrentSchedule | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [date, setDate] = useState("");
  const [minutes, setMinutes] = useState(60);
  const [result, setResult] = useState<FreeTime | null>(null);
  useEffect(() => {
    if (!session) return;
    let active = true;
    scheduleApi.current(session).then(item => { if (active) { setSaved(item); setDate(item.timetable.term.week1_monday); } })
      .catch(e => { if (active) { onAuthError(e); setError(errorText(e)); } });
    return () => { active = false; };
  }, [session]);
  async function query() {
    if (!session || !saved || !date) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const next = new Date(`${date}T00:00:00Z`); next.setUTCDate(next.getUTCDate() + 1);
      const item = await apiClient.post<FreeTime>("/api/v1/time/free-slots", {
        workspace_ref: session.workspaceRef,
        window: { start: `${date}T00:00:00+08:00`, end: `${next.toISOString().slice(0, 10)}T00:00:00+08:00` },
        min_minutes: minutes, buffers: { before_minutes: 0, after_minutes: 0 },
      });
      setResult(item);
    } catch (e) { onAuthError(e); setError(errorText(e)); }
    finally { setBusy(false); }
  }
  return <section>
    <p>固定虚构演示；下方数据是本浏览器工作区实际保存后读回的课表，不用夹具替代失败。</p>
    {!session && <p>尚未创建工作区，请先<a href="/tools/import">导入并确认课表</a>。</p>}
    {error && <p role="alert">{error}</p>}
    {saved && <p>数据库记录 {saved.scheduleId} · 版本 {saved.revision} · 保存时间 {saved.confirmedAt}</p>}
    <TimetablePage timetable={saved?.timetable ?? null} />
    {saved && <section><h2>查找空闲时间</h2>
      <label>日期（北京时间）<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
      <label>至少分钟数<input type="number" min="1" max="1440" value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>
      <button disabled={busy || !date || minutes < 1 || minutes > 1440 || !Number.isInteger(minutes)} onClick={() => void query()}>查询已保存课表的空档</button>
      {result && <><p>覆盖：{result.coverage.scope} / {result.coverage.completeness}；仅基于已确认课表与活动，不代表没有其他安排。</p>
        {result.needsConfirmation.length > 0 && <p role="note">仍需确认：{result.needsConfirmation.join("、")}</p>}
        <ul>{result.slots.map(slot => <li key={slot.start}>{slot.start} → {slot.end}（{slot.durationMinutes} 分钟）</li>)}</ul>
        {result.slots.length === 0 && <p>本次没有符合条件的空档。</p>}</>}
    </section>}
  </section>;
}
