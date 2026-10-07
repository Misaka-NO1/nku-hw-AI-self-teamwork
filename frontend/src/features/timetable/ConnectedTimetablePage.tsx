import { useEffect, useState } from "react";
import TimetablePage from "./TimetablePage";
import { scheduleApi, type CurrentSchedule } from "../import/connectedApi";
import type { DemoSession } from "../tasks/api";
import { useBrowserSession } from "../auth/useBrowserSession";
import { ApiError } from "../../shared/api/client";

export default function ConnectedTimetablePage() {
  const identityPilot = import.meta.env.VITE_IDENTITY_PILOT === "true";
  const browserSession = useBrowserSession(identityPilot);
  const { session, checking, needsLogin, recoveryError } = browserSession;
  return <section>
    {checking && <p role="status">正在核验当前浏览器会话；完成前不能读取课表。</p>}
    {!!recoveryError && <p role="alert">{errorText(recoveryError)}</p>}
    {identityPilot && needsLogin && <p>当前浏览器会话已失效。<a href="/tools/login">登录本人账号</a>后重新打开课表；不会自动保存。</p>}
    {identityPilot && !!recoveryError && !needsLogin && <button disabled={checking} onClick={browserSession.retryRecovery}>重新核验浏览器会话</button>}
    {!checking && !recoveryError && <SessionTimetable key={session?.workspaceRef ?? "no-session"} session={session} onAuthError={browserSession.rejectExpiredSession} />}
  </section>;
}
function errorText(e: unknown) {
  return e instanceof ApiError ? `${e.message}（${e.code} · ${e.requestId ?? "无请求编号"}）` : "课表读取失败，请稍后重试。";
}
function savedTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "保存时间未提供" : new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}
function SessionTimetable({ session, onAuthError }: { session: DemoSession | null; onAuthError: (error: unknown) => void }) {
  const [saved, setSaved] = useState<CurrentSchedule | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!session);
  const [empty, setEmpty] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!session) return;
    let active = true;
    setLoading(true); setSaved(null); setEmpty(false); setError("");
    scheduleApi.current(session).then(item => {
      if (!active) return;
      // Existing read contract only. Never show a stale response from another workspace.
      if (item.workspaceRef !== session.workspaceRef) {
        setError("课表归属与当前账号不一致，请重新登录核对。"); return;
      }
      setSaved(item);
    }).catch(e => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 404) setEmpty(true);
      else { onAuthError(e); setError(errorText(e)); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session?.workspaceRef, reload]);
  if (!session) return <TimetablePage />;
  return <section>
    <div className="tt-connection-status"><span>{saved ? `已读取本人课表 · 版本 ${saved.revision} · 保存于 ${savedTime(saved.confirmedAt)}` : "本人课表"}</span><button className="tt-refresh" disabled={loading} onClick={() => setReload(n => n + 1)}>{loading ? "读取中…" : "刷新课表"}</button></div>
    {loading && <div className="tt-load-state" role="status">正在读取本人课表，请稍候…</div>}
    {!loading && error && <div className="tt-load-state" role="alert"><h2>课表暂时未能加载</h2><p>请刷新重试；不会使用虚构数据代替读取结果。</p><details><summary>查看错误详情</summary>{error}</details></div>}
    {!loading && !error && (empty || saved) && <TimetablePage timetable={saved?.timetable ?? null} />}
  </section>;
}
