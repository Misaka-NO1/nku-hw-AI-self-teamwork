import { useEffect, useRef, useState } from "react";
import eventNotice from "../../../../fixtures/notice-event.demo.json";
import deadlineNotice from "../../../../fixtures/notice-deadline.demo.json";
import ambiguousNotice from "../../../../fixtures/notice-ambiguous.demo.json";
import eventQuery from "../../../../fixtures/time-event-query.demo.json";
import deadlineQuery from "../../../../fixtures/time-deadline-query.demo.json";
import { snakeToCamel } from "../../shared/api/convert";
import { ApiError } from "../../shared/api/client";
import { tasksApi, saveConfirmedDraft, type DemoSession, type Notice, type SaveAttempt, type TaskDraft, type TaskRecord, type TimeCheckResult } from "./api";
import { useBrowserSession } from "../auth/useBrowserSession";
import { toolReviewLoginUrl } from "../auth/toolReviewReturn";
import "./tasks.css";

const STORAGE = "campus-demo-tasks-v1";
const examples = [eventNotice, deadlineNotice, ambiguousNotice];
const fieldLabels: Record<string, string> = {
  published_at_or_explicit_reference_date: "发布日期或明确参考日期", due_time: "具体截止时刻",
  estimated_minutes: "预计用时", event_time: "具体活动时间", earliest_start: "最早开始时间",
};
const fieldText = (fields: string[]) => fields.map((field) => fieldLabels[field] ?? field).join("、");
interface StateCache {
  session: DemoSession;
  draftId?: string;
  draftKeys: Record<string, string>;
  attempt?: SaveAttempt;
}
function loadCache(verifiedSession?: DemoSession): StateCache | null {
  try {
    const cached = JSON.parse(sessionStorage.getItem(STORAGE) ?? "null") as StateCache | null;
    return cached?.session?.workspaceRef && cached.session.csrfToken
      && (verifiedSession ? cached.session.workspaceRef === verifiedSession.workspaceRef : Date.parse(cached.session.expiresAt) > Date.now())
      && cached.draftKeys && typeof cached.draftKeys === "object" ? cached : null;
  } catch { return null; }
}
const key = () => `tasks-${crypto.randomUUID()}`;
function errorText(error: unknown): string {
  return error instanceof ApiError ? `${error.message}（${error.code}${error.requestId ? ` · 请求 ${error.requestId}` : ""}）`
    : error instanceof Error ? error.message : "操作失败，请重试";
}
function timeText(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }) : "未提供";
}
function NoticeSummary({ notice }: { notice: Notice }) {
  return <>
    <dl className="tasks-summary">
      <dt>活动时间</dt><dd>{notice.event.precision === "datetime" ? `${timeText(notice.event.start)} → ${timeText(notice.event.end)}` : notice.event.date ?? "未提供（不占用时间）"}</dd>
      <dt>截止时间</dt><dd>{notice.due.at ? timeText(notice.due.at) : notice.due.date ?? "未提供（不推测）"}</dd>
      <dt>预计用时</dt><dd>{notice.estimatedMinutes === null ? "未提供" : `${notice.estimatedMinutes} 分钟`}</dd>
      <dt>最早开始</dt><dd>{timeText(notice.earliestStart)}</dd>
    </dl>
    <details><summary>查看通知原文依据</summary>{notice.sourceSpans.map((span, index) => <blockquote key={index}>{span.quote}<footer>{span.sourceRef}</footer></blockquote>)}</details>
    {!!notice.needsConfirmation.length && <p className="tasks-warning" role="alert">仍需补充：{fieldText(notice.needsConfirmation)}。不会猜测日期，暂不能保存。</p>}
  </>;
}

export default function TasksPage() {
  const identityPilot = import.meta.env.VITE_IDENTITY_PILOT === "true";
  const browserSession = useBrowserSession(identityPilot);
  const { session, setSession, checking, needsLogin, recoveryError } = browserSession;
  const cache = useRef<StateCache | null>(loadCache());
  const busyRef = useRef(false);
  const [selected, setSelected] = useState(0);
  const [draft, setDraft] = useState<TaskDraft | null>(null);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [timeResult, setTimeResult] = useState<TimeCheckResult | null>(null);
  const [useSavedSchedule, setUseSavedSchedule] = useState(identityPilot);
  const loginUrl = toolReviewLoginUrl(window.location.pathname + window.location.search, window.location.origin)
    ?? toolReviewLoginUrl("/tools/tasks", window.location.origin)!;

  function persist() {
    // Short-lived fictional workspace / CSRF only. Never store a service bearer.
    sessionStorage.setItem(STORAGE, JSON.stringify(cache.current));
  }
  async function perform(action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError(null); setMessage(null);
    try { await action(); }
    catch (err) { browserSession.rejectExpiredSession(err); setError(errorText(err)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  useEffect(() => {
    setDraft(null); setTasks([]); setTimeResult(null);
    if (!session) { cache.current = null; return; }
    const restored = loadCache(identityPilot ? session : undefined);
    cache.current = restored?.session.workspaceRef === session.workspaceRef
      ? { ...restored, session } : { session, draftKeys: {} };
    let active = true;
    const requestedDraft = new URLSearchParams(window.location.search).get("draft_id") ?? cache.current?.draftId;
    // Mount/refresh only reads: never silently creates a workspace, confirmation or task.
    tasksApi.list(session).then((items) => { if (active) setTasks(items); }).catch((err) => {
      if (active) { browserSession.rejectExpiredSession(err); setError(errorText(err)); }
    });
    if (requestedDraft) tasksApi.draft(requestedDraft).then((item) => {
      if (item.kind !== "task" || item.workspaceRef !== session.workspaceRef) throw new Error("链接不是当前工作区的待办草稿");
      if (active) {
        setDraft(item);
        const index = examples.findIndex((example) => example.title === item.payload.title);
        if (index >= 0) setSelected(index);
      }
    }).catch((err) => { if (active) { browserSession.rejectExpiredSession(err); setError(errorText(err)); } });
    return () => { active = false; };
  }, [session]);

  function createSession() {
    if (identityPilot) return;
    void perform(async () => {
      const created = await tasksApi.createSession();
      cache.current = { session: created, draftKeys: {} };
      persist(); setSession(created); setDraft(null); setTasks([]);
      const url = new URL(window.location.href); url.searchParams.delete("draft_id"); window.history.replaceState(null, "", url);
      setMessage("虚构测试工作区已创建。尚未保存任何任务。");
    });
  }
  function createDraft() {
    void perform(async () => {
      if (!session || !cache.current) return;
      const fixture = examples[selected];
      const id = fixture.notice_id;
      cache.current.draftKeys[id] ??= key(); persist();
      const item = await tasksApi.createDraft(session, fixture, cache.current.draftKeys[id]);
      cache.current.draftId = item.draftId; persist(); setDraft(item);
      const url = new URL(window.location.href); url.searchParams.set("draft_id", item.draftId); window.history.replaceState(null, "", url);
      setMessage(item.status === "committed" ? "这份通知已经保存，请查看下方记录。" : "草稿已生成，还没有保存为待办。请核对后确认。");
    });
  }
  function cancelPreview() {
    if (cache.current) { delete cache.current.draftId; persist(); }
    const url = new URL(window.location.href); url.searchParams.delete("draft_id"); window.history.replaceState(null, "", url);
    setDraft(null); setMessage("已取消本次预览，没有提交待办。草稿到期后不能访问；本页不会删除记录。");
  }
  function selectExample(value: number) {
    setSelected(value); setTimeResult(null); setDraft(null); setMessage(null);
    if (cache.current) { delete cache.current.draftId; persist(); }
    const url = new URL(window.location.href); url.searchParams.delete("draft_id"); window.history.replaceState(null, "", url);
  }
  function save() {
    void perform(async () => {
      if (!session || !draft || !cache.current) return;
      const previous = cache.current.attempt;
      const attempt = previous?.draftId === draft.draftId ? previous : {
        draftId: draft.draftId, revision: draft.revision, payloadHash: draft.payloadHash,
        confirmationKey: key(), commitKey: key(),
      };
      const saved = await saveConfirmedDraft(session, draft, attempt, (value) => {
        if (cache.current) { cache.current.attempt = value; persist(); }
      });
      setMessage(`已保存到后端 · ${saved.taskId}`);
      setDraft({ ...draft, status: "committed" });
      // A failed list refresh must not misreport a successful commit as a failed save.
      try { setTasks(await tasksApi.list(session)); }
      catch (err) { setError(`保存已成功，但列表刷新失败：${errorText(err)}`); }
    });
  }
  const preview = snakeToCamel(examples[selected]) as unknown as Notice;
  return <section className="tasks-page">
    <header><p className="tasks-eyebrow">通知 → 草稿 → 人工确认 → 保存</p><h2>我的待办</h2><p>先核对，再安排。活动时间与提交截止时间分别记录，不把截止时间当作占用时段。</p></header>
    <aside className="tasks-warning">固定虚构数据测试版 · 不接收真实个人通知或课表。数据保存在后端测试数据库；工作区默认 24 小时后过期。</aside>
    {checking && <p role="status">正在核验当前浏览器会话；完成前不能读写或确认。</p>}
    {!!recoveryError && <div role="alert" className="tasks-error">{errorText(recoveryError)}</div>}
    {identityPilot && needsLogin && <p>当前浏览器会话已失效。<a href={loginUrl}>登录测试账号后返回此页核对</a>，不会自动保存。</p>}
    {identityPilot && !!recoveryError && !needsLogin && <button disabled={checking || busy} onClick={browserSession.retryRecovery}>重新核验浏览器会话</button>}
    {error && <div role="alert" className="tasks-error">{error}</div>}
    {message && <div role="status" className="tasks-message">{message}</div>}
    <div className="card"><h3>1 · 测试工作区</h3>{session ? <>
      <p>当前工作区：<code>{session.workspaceRef}</code></p><p>有效至 {timeText(session.expiresAt)} · 刷新页面会读回，不自动重新创建。</p>
      <button disabled={busy || checking} onClick={() => void perform(async () => { setTasks(await tasksApi.list(session)); setMessage("已从后端刷新列表。"); })}>刷新已保存任务</button>
      {!identityPilot && <details><summary>会话过期后的处理</summary><p>新建工作区会切换会话，不会删除旧数据；旧工作区不能用新会话访问。</p><button disabled={busy} onClick={createSession}>新建虚构工作区</button></details>}
    </> : !identityPilot && <button disabled={busy} onClick={createSession}>开始虚构数据测试</button>}</div>
    <div className="tasks-columns"><div className="card">
      <h3>2 · 选择通知</h3>
      <label htmlFor="notice-example">仅提供三份固定测试通知</label>
      <select id="notice-example" value={selected} onChange={(event) => selectExample(Number(event.target.value))} disabled={busy}>
        {examples.map((notice, index) => <option value={index} key={notice.notice_id}>{notice.title}</option>)}
      </select>
      <NoticeSummary notice={preview} />
      <div className="toolbar">
        <button disabled={!session || busy} onClick={createDraft}>生成待办草稿（不保存）</button>
        <button disabled={busy || checking || selected === 2 || (useSavedSchedule && !session)} onClick={() => void perform(async () => {
          const query = selected === 0 ? eventQuery : deadlineQuery;
          setTimeResult(await tasksApi.checkTime(useSavedSchedule && session
            ? { ...query, workspace_ref: session.workspaceRef } : query));
        })}>{useSavedSchedule ? "检查已保存课表与待办" : "检查公共虚构课表时间"}</button>
      </div>
      <label><input type="checkbox" checked={useSavedSchedule} disabled={busy || checking || identityPilot}
        onChange={event => { setUseSavedSchedule(event.target.checked); setTimeResult(null); }} />使用本工作区已确认的课表与待办</label>
      <p className="tasks-meta">{useSavedSchedule
        ? "只读取当前身份实际保存的课表与活动；没有保存课表时明确报错，不用公共夹具替代。仍为虚构数据测试。"
        : "时间检查只读取公共虚构课表 demo-workspace-01，不包含下方已保存任务，不代表你的真实空闲时间。"}</p>
      {timeResult && <div className="tasks-message">
        <strong>服务器时间检查结果</strong>
        {timeResult.needsConfirmation.length ? <p>需要确认：{fieldText(timeResult.needsConfirmation)}</p>
          : timeResult.kind === "event_conflict" ? <>
            <p>已知虚构课表冲突：{timeResult.conflicts?.length ?? 0} 处。</p>
            {timeResult.conflicts?.map((conflict, index) => <p key={index}>{timeText(conflict.intersectionStart)} → {timeText(conflict.intersectionEnd)}</p>)}
          </> : <>
            <p>候选安排（不是自动保存）：</p>
            {timeResult.candidateSlots?.length ? timeResult.candidateSlots.map((slot) => <p key={slot.start}>
              {timeText(slot.start)} → {timeText(slot.end)}（{slot.durationMinutes} 分钟）
            </p>) : <p>在已知虚构安排下，没有足够的连续空档。</p>}
          </>}
        <p>课表完整性：{timeResult.coverage.completeness === "complete" ? "完整" : timeResult.coverage.completeness === "partial" ? "部分覆盖" : "未确认"} · 范围：{timeResult.coverage.scope === "term" ? "学期已知课程" : "已知周次"}</p>
      </div>}
    </div>
    <div className="card"><h3>3 · 核对并确认</h3>{draft ? <><h4>{draft.payload.title}</h4><NoticeSummary notice={draft.payload} /><p className="tasks-meta">草稿版本 {draft.revision} · 状态 {draft.status === "committed" ? "已保存" : "未保存"}</p><div className="toolbar"><button className="tasks-primary" disabled={busy || checking || !session || draft.status !== "draft" || !!draft.payload.needsConfirmation.length} onClick={save}>{busy ? "处理中…" : draft.status === "committed" ? "已保存，无需重复提交" : "我已核对，确认保存待办"}</button>{draft.status === "draft" && <button disabled={busy} onClick={cancelPreview}>取消预览（不保存）</button>}</div><p className="tasks-meta">只有后端返回真实 task_id 才显示保存成功；失败重试复用同一幂等键。</p></> : <p>生成草稿后会在这里显示，不会自动提交。</p>}</div></div>
    <section><h3>4 · 已保存记录 <span className="tag">{tasks.length} 条</span></h3>{tasks.length === 0 ? <div className="state">暂无已确认的待办。草稿不会出现在这里。</div> : tasks.map((task) => <article className="card" key={task.taskId}><h4>{task.notice.title}</h4><NoticeSummary notice={task.notice} /><p className="tasks-meta">保存时间 {timeText(task.confirmedAt)} · <code>{task.taskId}</code></p></article>)}</section>
  </section>;
}
