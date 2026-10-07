import { useState } from "react";
import { ConfirmSummary, StatusBanner } from "../../shared/components";
import { ApiError } from "../../shared/api/client";
import timetable from "../../../../fixtures/timetable.demo.json";
import { noticeApi, type Batch, type CheckResult, type Draft, type Plan, type ReadRequest,
  type Session, type Task } from "./api";
import "./tasks.css";

const SESSION_KEY = "notice-text-pilot-session-v1";
const LABELS: Record<string, string> = {
  source_review: "核对原文与拆分事项", reference_date: "通知的日期参照", date: "明确日期",
  due_time: "具体截止时刻", estimated_minutes: "预计耗时", earliest_start: "最早开始时间",
  event_time: "活动起止时间", changed_or_cancelled_notice: "通知含取消或变更，请先更正原文",
  multiple_dates: "多个日期，请先按事项拆分", mixed_actions: "活动与截止任务混合，请先拆分",
};
const label = (field: string) => LABELS[field] ?? field;
const stamp = (local: string) => local ? `${local}:00+08:00` : null;
const localTime = (iso: string | null) => iso?.slice(0, 16) ?? "";
const showTime = (iso: string | null) => iso ? iso.replace("T", " ").replace(/:00\+08:00$/, "") : "待确认";
const key = () => crypto.randomUUID();

function restoredSession(): Session | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? "null") as Session | null;
    return value && Date.parse(value.expiresAt) > Date.now() ? value : null;
  } catch { return null; }
}

export default function NoticePilotPage() {
  const [session, setSession] = useState<Session | null>(restoredSession);
  const [source, setSource] = useState("");
  const [reference, setReference] = useState("");
  const [readRequest, setReadRequest] = useState<ReadRequest | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [scheduleDraft, setScheduleDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(null); setMessage("");
    try { await action(); } catch (e) {
      setError({ message: e instanceof Error ? e.message : "请求失败", requestId: e instanceof ApiError ? e.requestId ?? undefined : undefined });
    } finally { setBusy(false); }
  }
  const refresh = async () => { if (session) setTasks(await noticeApi.list(session.workspaceRef)); };

  return <main className="notice-tasks">
    <h1>通知与待办</h1>
    <StatusBanner kind="demo" message="本地文字试点：仅使用自编虚构通知和演示课表。学校 Agent 与截图/PDF 读取尚未验收。" />
    {error && <StatusBanner kind="error" {...error} />}
    {message && <p role="status">{message}</p>}
    {!session ? <section className="card">
      <p>确认本次使用虚构内容后开始。固定演示课表覆盖2026年9月7日至10月4日。</p>
      <button disabled={busy} onClick={() => void run(async () => {
        const created = await noticeApi.createSession();
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(created)); setSession(created);
      })}>确认使用虚构数据并开始</button>
    </section> : <>
      <section className="card">
        <h2>课表与已保存待办</h2>
        <p>课表须先确认导入；缺少课表时会提示失败，不自动借用共享课表。</p>
        <div className="toolbar">
          <button disabled={busy} onClick={() => void run(async () => {
            setScheduleDraft(await noticeApi.scheduleDraft(timetable, session.csrfToken, key()));
          })}>查看演示课表导入摘要</button>
          <button disabled={busy} onClick={() => void run(refresh)}>重新读取待办</button>
        </div>
        {scheduleDraft && <ConfirmSummary title="确认导入虚构课表" items={[
          { label: "范围", value: "2026年9月7日起，4个教学周，3门虚构课程" },
          { label: "说明", value: "不是学校真实校历或本人真实课表" },
        ]} confirmDisabled={busy} onCancel={() => setScheduleDraft(null)} onConfirm={() => void run(async () => {
          const confirm = await noticeApi.confirm(scheduleDraft, session.csrfToken, key());
          const saved = await noticeApi.commit("schedule", confirm.confirmationId, session.csrfToken, key());
          setMessage(`演示课表已保存：${saved.scheduleId}`); setScheduleDraft(null);
        })} />}
        {tasks.map(task => {
          const plan = "planVersion" in task.notice ? task.notice as Plan : null;
          const notice = plan?.notice ?? task.notice as Exclude<Task["notice"], Plan>;
          return <article key={task.taskId} className="saved-task"><strong>{notice.title}</strong>
            <p>{plan?.selectedSlot ? `工作时间：${showTime(plan.selectedSlot.start)} — ${showTime(plan.selectedSlot.end)}`
              : notice.event.start ? `活动：${showTime(notice.event.start)} — ${showTime(notice.event.end)}`
                : `截止：${showTime(notice.due.at)}`}</p><small>已保存 · {task.taskId}</small></article>;
        })}
      </section>
      <section className="card">
        <h2>核对通知</h2>
        <p>粘贴新通知，尽量每句话写一项。文字读取保留全部段落；当前只能解析明确日期和HH:MM时刻，复杂事项需手动拆分。</p>
        <label>通知原文<textarea rows={5} maxLength={20000} value={source} onChange={e => {
          setSource(e.target.value); setBatch(null); setReadRequest(null);
        }} /></label>
        <label>已确认的日期参照（“本周五”等相对日期需要）<input type="datetime-local" value={reference}
          onInput={e => { setReference(e.currentTarget.value); setBatch(null); setReadRequest(null); }} /></label>
        <button disabled={busy || !source.trim()} onClick={() => void run(async () => {
          setBatch(null); setReadRequest(null);
          const request = { sourceText: source, sourceRef: "用户粘贴的虚构通知", referenceAt: stamp(reference) };
          const result = await noticeApi.read(request, session.csrfToken);
          setBatch(result); setReadRequest(request);
        })}>读取并逐项核对</button>
      </section>
      {batch && readRequest && <>
        <p>已读取 {batch.coverage.charactersRead}/{batch.coverage.charactersTotal} 字符；识别 {batch.items.length} 个事项。</p>
        {batch.unclassified.length > 0 && <section className="card"><h2>还需核对的段落</h2>
          <p>下列内容未识别成事项，请核对是否存在遗漏。</p>{batch.unclassified.map((p, i) => <blockquote key={i}>{p.quote}</blockquote>)}
        </section>}
        {batch.items.map((item, i) => <NoticeItem key={`${item.notice.noticeId}-${item.notice.extractedAt}`} item={item}
          index={i} source={readRequest} session={session} run={run} busy={busy} onSaved={refresh} />)}
      </>}
    </>}
  </main>;
}

function NoticeItem({ item, index, source, session, run, busy, onSaved }: {
  item: Batch["items"][number]; index: number; source: ReadRequest; session: Session;
  run: (action: () => Promise<void>) => Promise<void>; busy: boolean; onSaved: () => Promise<void>;
}) {
  const n = item.notice;
  const [reviewed, setReviewed] = useState(false);
  const [acceptConflicts, setAcceptConflicts] = useState(false);
  const [minutes, setMinutes] = useState(n.estimatedMinutes?.toString() ?? "");
  const [earliest, setEarliest] = useState("");
  const [due, setDue] = useState(localTime(n.due.at));
  const [eventStart, setEventStart] = useState(localTime(n.event.start));
  const [eventEnd, setEventEnd] = useState(localTime(n.event.end));
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftPlan, setDraftPlan] = useState<Plan | null>(null);
  const [dirty, setDirty] = useState(false);
  const [savedId, setSavedId] = useState("");
  // Any edit immediately hides old candidates/confirmation; backend revisions enforce it too.
  const invalidate = () => { setCheck(null); setSelected(null); setDirty(true); setDraftPlan(null); };
  const field = (title: string, value: string, setter: (s: string) => void) => <label>{title}<input type="datetime-local"
    disabled={busy || !!savedId} value={value} onInput={e => { setter(e.currentTarget.value); invalidate(); }} /></label>;
  return <section className="card">
    <h2>{index + 1}. {item.kind === "event_conflict" ? "固定活动" : "截止任务"}</h2>
    <blockquote>{n.title}</blockquote>
    <details><summary>查看完整原文证据</summary>{n.sourceSpans.map((s, i) => <p key={i}>{s.field}：{s.quote} <small>{s.sourceRef}</small></p>)}</details>
    {n.materials.length > 0 && <p>材料：{n.materials.join("；")}</p>}
    <p>首次读取需确认：{n.needsConfirmation.map(label).join("、")}</p>
    <label><input type="checkbox" checked={reviewed} disabled={busy || !!savedId}
      onChange={e => { setReviewed(e.target.checked); invalidate(); }} />我已核对原文、日期和事项拆分</label>
    {item.kind === "deadline_feasibility" ? <>
      {field("确认具体截止时间", due, setDue)}
      <label>确认预计耗时（分钟）<input type="number" min={1} max={10080} value={minutes} disabled={busy || !!savedId}
        onChange={e => { setMinutes(e.target.value); invalidate(); }} /></label>
      {field("最早开始时间", earliest, setEarliest)}
      <p>下方查询范围就是本次可用时间限制；只考虑晚上时填入实际晚间区间，多日可分次查询。</p>
    </> : <>{field("确认活动开始", eventStart, setEventStart)}{field("确认活动结束", eventEnd, setEventEnd)}</>}
    {field("查询开始", windowStart, setWindowStart)}{field("查询结束", windowEnd, setWindowEnd)}
    <button disabled={busy || !!savedId || !windowStart || !windowEnd} onClick={() => void run(async () => {
      setCheck(null); setSelected(null); setDirty(true); setDraftPlan(null);
      setCheck(await noticeApi.check({ ...source, itemId: n.noticeId,
        userConfirmations: { sourceReview: reviewed, acceptConflicts,
          estimatedMinutes: minutes ? Number(minutes) : null, earliestStart: stamp(earliest), dueAt: stamp(due),
          eventStart: stamp(eventStart), eventEnd: stamp(eventEnd) },
        window: { start: stamp(windowStart)!, end: stamp(windowEnd)! }, availableWindows: [],
      }, session.csrfToken));
    })}>重新计算冲突或候选时间</button>
    {check && <>
      <StatusBanner kind="partial" message={check.coverageMessage + (!check.timeResult.coverage.withinTerm ? "；查询超出演示学期，范围外课表未知" : "")} />
      {check.timeResult.needsConfirmation.length > 0 ? <p>还需确认：{check.timeResult.needsConfirmation.map(label).join("、")}</p>
        : item.kind === "deadline_feasibility" ? <>
          {(check.timeResult.candidateSlots?.length ?? 0) === 0 && <p>在本次查询与已知课表范围内没有足够的连续时间。</p>}
          {check.recommendations.map((r, i) => <label key={i}><input type="radio" name={n.noticeId} disabled={busy || !!savedId}
            checked={selected === r.candidateIndex} onChange={() => { setSelected(r.candidateIndex); setDirty(true); setDraftPlan(null); }} />
            {i + 1}. {showTime(r.slot.start)} — {showTime(r.slot.end)}（{r.slot.durationMinutes}分钟）<br />{r.reason}</label>)}
          {(check.timeResult.candidateSlots?.length ?? 0) > 3 && <details><summary>更多候选</summary>
            {check.timeResult.candidateSlots?.slice(3).map((s, i) => <label key={i}><input type="radio" name={n.noticeId}
              checked={selected === i + 3} disabled={busy || !!savedId}
              onChange={() => { setSelected(i + 3); setDirty(true); setDraftPlan(null); }} />{showTime(s.start)} — {showTime(s.end)}</label>)}
          </details>}
        </> : <>
          {check.timeResult.conflicts?.length ? check.timeResult.conflicts.map((c, i) => <p key={i}>
            与{check.conflictLabels[c.sourceEventId] ?? c.sourceEventId}冲突：{showTime(c.intersectionStart)} — {showTime(c.intersectionEnd)}</p>)
            : <p>在已导入课表与已确认活动范围内未发现冲突。</p>}
          {!!check.timeResult.conflicts?.length && <label><input type="checkbox" checked={acceptConflicts} disabled={busy || !!savedId}
            onChange={e => { setAcceptConflicts(e.target.checked); invalidate(); }} />我已了解冲突，仍要保存原活动（请重新计算后核对）</label>}
        </>}
      <button disabled={busy || !!savedId || !!check.timeResult.needsConfirmation.length || (item.kind === "deadline_feasibility" && selected === null)}
        onClick={() => void run(async () => {
          const plan = { ...check.plan, selectedSlot: selected === null ? null : check.timeResult.candidateSlots![selected] };
          const created = draft ? await noticeApi.update(draft, plan, session.csrfToken) : await noticeApi.draft(plan, session.csrfToken, key());
          setDraft(created); setDraftPlan(plan); setDirty(false);
        })}>{draft ? "更新待核对草稿" : "生成待核对草稿"}</button>
      <details><summary>查看本次计算依据</summary><pre>{JSON.stringify({ request: check.timeRequest, result: check.timeResult }, null, 2)}</pre></details>
    </>}
    {draft && draftPlan && !dirty && !savedId && <ConfirmSummary title="最后核对后保存" items={[
      { label: "事项", value: draftPlan.notice.title },
      { label: "原文", value: draftPlan.sourceText },
      { label: "时间", value: draftPlan.selectedSlot ? `${showTime(draftPlan.selectedSlot.start)} — ${showTime(draftPlan.selectedSlot.end)}`
        : `${showTime(draftPlan.notice.event.start)} — ${showTime(draftPlan.notice.event.end)}` },
      { label: "覆盖", value: check?.coverageMessage ?? "只覆盖已导入课表与已确认活动" },
    ]} warnings={["只有点击确认提交后才保存；修改字段后须重新计算和核对"]} confirmDisabled={busy}
      onCancel={() => { setDraftPlan(null); setDirty(true); }} onConfirm={() => void run(async () => {
        const confirmation = await noticeApi.confirm(draft, session.csrfToken, `confirm-${draft.draftId}-${draft.revision}`);
        const saved = await noticeApi.commit("task", confirmation.confirmationId, session.csrfToken, `commit-${draft.draftId}-${draft.revision}`);
        setSavedId(saved.taskId ?? ""); await onSaved();
      })} />}
    {savedId && <p role="status">已保存并可从待办列表读回：{savedId}</p>}
  </section>;
}
