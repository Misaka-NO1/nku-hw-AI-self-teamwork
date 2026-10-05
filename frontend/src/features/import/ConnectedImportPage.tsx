import { useEffect, useRef, useState } from "react";
import type { TimetableImport } from "@campus/import-core";
import fixture from "../../../../fixtures/timetable.demo.json";
import ImportPage from "./ImportPage";
import TimetablePage from "../timetable/TimetablePage";
import { scheduleApi, saveConfirmedSchedule, type ScheduleDraft } from "./connectedApi";
import type { SaveAttempt } from "../tasks/api";
import { writeDemoSession } from "../tasks/sessionCache";
import { ApiError } from "../../shared/api/client";
import { useBrowserSession } from "../auth/useBrowserSession";
import { toolReviewLoginUrl } from "../auth/toolReviewReturn";

const CACHE = "campus-demo-schedule-v1";
const timetableFixture = fixture as TimetableImport;
const newKey = () => `schedule-${crypto.randomUUID()}`;
interface Progress { workspaceRef: string; draftKey?: string; draftId?: string; attempt?: SaveAttempt }
function readProgress(): Progress | null {
  try { return JSON.parse(sessionStorage.getItem(CACHE) ?? "null"); } catch { return null; }
}
export default function ConnectedImportPage() {
  const identityPilot = import.meta.env.VITE_IDENTITY_PILOT === "true";
  const browserSession = useBrowserSession(identityPilot);
  const { session, setSession, checking, needsLogin, recoveryError } = browserSession;
  const [draft, setDraft] = useState<ScheduleDraft | null>(null);
  const [candidate, setCandidate] = useState<TimetableImport | null>(null);
  const [localPreview, setLocalPreview] = useState<TimetableImport | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const progress = useRef<Progress | null>(readProgress());
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const loginUrl = toolReviewLoginUrl(window.location.pathname + window.location.search, window.location.origin)
    ?? toolReviewLoginUrl("/tools/import", window.location.origin)!;
  function errorText(e: unknown) {
    return e instanceof ApiError ? `${e.message}（${e.code} · ${e.requestId ?? "无请求编号"}）` : String(e);
  }
  function persist() { sessionStorage.setItem(CACHE, JSON.stringify(progress.current)); }
  async function perform(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (e) {
      browserSession.rejectExpiredSession(e); setError(errorText(e));
    } finally { lock.current = false; setBusy(false); }
  }
  useEffect(() => {
    setDraft(null); setCandidate(null);
    if (!session) { progress.current = null; return; }
    const restored = readProgress();
    progress.current = restored?.workspaceRef === session.workspaceRef ? restored : { workspaceRef: session.workspaceRef };
    const id = new URLSearchParams(location.search).get("draft_id")
      ?? (progress.current?.workspaceRef === session.workspaceRef ? progress.current.draftId : null);
    if (!id) return;
    let active = true;
    scheduleApi.draft(id).then(item => {
      if (item.kind !== "schedule" || item.workspaceRef !== session.workspaceRef) throw new Error("不是当前工作区的课表草稿");
      if (active) { setDraft(item); setCandidate(item.payload); }
    }).catch(e => { if (active) { browserSession.rejectExpiredSession(e); setError(errorText(e)); } });
    return () => { active = false; };
  }, [session]);
  function createSession() { void perform(async () => {
    if (identityPilot) return;
    const item = await scheduleApi.createSession();
    writeDemoSession(item); progress.current = { workspaceRef: item.workspaceRef }; persist();
    setSession(item); setDraft(null); setMessage("虚构工作区已创建，尚未保存课表。");
  }); }
  function createDraft() { void perform(async () => {
    if (!session || !candidate) return;
    // Personal previews stay local. The backend independently enforces the exact fixture.
    if (JSON.stringify(candidate) !== JSON.stringify(timetableFixture)) throw new Error("当前只允许固定虚构课表；个人文件不会发送到服务器。");
    await scheduleApi.validate(candidate);
    if (progress.current?.workspaceRef !== session.workspaceRef) progress.current = { workspaceRef: session.workspaceRef };
    progress.current.draftKey ??= newKey(); persist();
    const item = await scheduleApi.createDraft(session, candidate, progress.current.draftKey);
    progress.current.draftId = item.draftId; persist(); setDraft(item);
    setMessage("服务端已生成草稿，尚未保存。请核对下方课表后再确认。");
  }); }
  function confirm() { void perform(async () => {
    if (!session || !draft) return;
    if (progress.current?.workspaceRef !== session.workspaceRef) throw new Error("工作区已变化");
    const old = progress.current.attempt;
    const attempt: SaveAttempt = old?.draftId === draft.draftId && old.revision === draft.revision && old.payloadHash === draft.payloadHash ? old : {
      draftId: draft.draftId, revision: draft.revision, payloadHash: draft.payloadHash,
      confirmationKey: newKey(), commitKey: newKey(),
    };
    const result = await saveConfirmedSchedule(session, draft, attempt, value => { progress.current!.attempt = value; persist(); });
    const saved = await scheduleApi.current(session);
    if (saved.scheduleId !== result.scheduleId || saved.revision !== result.revision) throw new Error("保存回执与读回版本不一致，请重试核验");
    setDraft({ ...draft, status: "committed" });
    setMessage(`已保存并从数据库读回：${result.scheduleId} · 版本 ${result.revision}。`);
  }); }
  return <section>
    <h1>课表导入与确认</h1>
    <p role="note">当前为固定虚构演示，工作区保留 24 小时。个人课表只可本地预览，尚未开放云端上传。</p>
    {checking && <p role="status">正在核验当前浏览器会话；完成前不能读写或确认。</p>}
    {!!recoveryError && <p role="alert">{errorText(recoveryError)}</p>}
    {identityPilot && needsLogin && <p>当前浏览器会话已失效。<a href={loginUrl}>登录测试账号后返回此页核对</a>，不会自动保存。</p>}
    {identityPilot && !!recoveryError && !needsLogin && <button disabled={checking || busy} onClick={browserSession.retryRecovery}>重新核验浏览器会话</button>}
    {!session ? !identityPilot && <button disabled={busy} onClick={createSession}>创建虚构测试工作区</button> : <p>已连接当前浏览器的演示工作区；与“待办”共用，服务令牌不会进入浏览器。</p>}
    <button disabled={busy} onClick={() => { setCandidate(timetableFixture); setDraft(null); }}>预览固定虚构课表</button>
    <button disabled={busy || !session || !candidate || !!draft} onClick={createDraft}>校验并生成草稿（不保存）</button>
    {draft && <p>草稿版本 {draft.revision} · 状态 {draft.status === "committed" ? "已保存" : "未保存"} · 有效期 {draft.expiresAt}</p>}
    {draft && <button disabled={busy || checking || !session || draft.status === "committed"} onClick={confirm}>我已核对，确认保存课表</button>}
    <a href="/tools/timetable">查看已保存课表与空闲时间 →</a>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {candidate && <TimetablePage timetable={draft?.payload ?? candidate} />}
    <details><summary>本地解析自己的导出文件（不上传）</summary>
      <ImportPage onPreview={setLocalPreview} />
      {localPreview && <p>已在本地生成预览；真实用户身份接通前，不上传这份文件或假装已保存。</p>}
    </details>
  </section>;
}
