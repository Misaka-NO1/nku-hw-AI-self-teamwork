import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../shared/api/client";
import { useBrowserSession } from "../auth/useBrowserSession";
import { loadCalendar, loadCandidates, updateCalendar, type CalendarUpdate } from "./api";
import { calendarErrorText as errorText, confirmationText } from "./messages";
import { calendarIcs, dueDay, exactCandidates, formatTime, isOverdue, monthDays, occursOn,
  plannedRange, plannedRanges, READ_ONLY, reminderKey, reminderTarget, remindersDue, shanghaiDay, shiftMonth, summary,
  type CalendarData, type Candidate, type TaskStatus } from "./model";
import "./calendar.css";

const empty:CalendarData={items:[],capabilities:READ_ONLY};
export default function CalendarPage() {
  const identity=import.meta.env.VITE_IDENTITY_PILOT==="true";
  const auth=useBrowserSession(identity);
  const today=shanghaiDay(new Date());
  const [month,setMonth]=useState(today.slice(0,7));
  const [day,setDay]=useState(today);
  const [data,setData]=useState<CalendarData>(empty);
  const [loading,setLoading]=useState(false);
  const [busy,setBusy]=useState(false);
  const busyRef=useRef(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [reload,setReload]=useState(0);
  const [statusFilter,setStatusFilter]=useState("pending");
  const [allDays,setAllDays]=useState(false);
  const [selected,setSelected]=useState<string|null>(null);
  const [candidates,setCandidates]=useState<Candidate[]>([]);
  const [choice,setChoice]=useState<Candidate|null>(null);
  const [confirmed,setConfirmed]=useState(false);
  const [reminder,setReminder]=useState<number|null>(15);
  const [notifications,setNotifications]=useState(false);
  const [notificationText,setNotificationText]=useState("");
  const [clock,setClock]=useState(()=>new Date());
  const delivered=useRef(new Set<string>());
  const writeAttempt=useRef<{signature:string;key:string}|null>(null);
  const scope=useRef("");
  const selectedRef=useRef(selected);
  selectedRef.current=selected;
  scope.current=auth.session?.workspaceRef??"";
  const task=data.items.find(t=>t.taskId===selected);
  const counts=summary(data.items,clock);
  const canWrite=!!auth.session;
  const editable=!data.legacy && canWrite && !busy;

  useEffect(()=>{
    setData(empty);setSelected(null);setCandidates([]);setChoice(null);setConfirmed(false);setMessage("");
    if(!auth.session) {setLoading(false);return;}
    let active=true;
    const controller=new AbortController();
    setLoading(true);setError("");
    loadCalendar(auth.session,controller.signal).then(value=>{if(active)setData(value);})
      .catch(reason=>{if(active){setData(empty);setError(errorText(reason));auth.rejectExpiredSession(reason);}})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;controller.abort();};
  },[auth.session?.workspaceRef,reload]);
  useEffect(()=>{
    setCandidates([]);setChoice(null);setConfirmed(false);setReminder(task?.reminderMinutes??null);
  },[selected,task?.calendarRevision]);
  useEffect(()=>{setNotifications(false);delivered.current.clear();},[auth.session?.workspaceRef]);
  useEffect(()=>{
    const tick=()=>setClock(new Date());
    const timer=window.setInterval(tick,30000);
    window.addEventListener("focus",tick);
    return ()=>{window.clearInterval(timer);window.removeEventListener("focus",tick);};
  },[]);
  useEffect(()=>{
    if(!notifications || error || loading || auth.checking || !auth.session || Date.parse(auth.session.expiresAt)<=clock.getTime()
      || typeof Notification==="undefined" || Notification.permission!=="granted") return;
    for(const item of remindersDue(data.items,clock)) {
      const key=scope.current+":"+reminderKey(item,clock);
      if(delivered.current.has(key)) continue;
      try {
        const notification=new Notification("南开校园助手 · 待办提醒",{
          body:`${item.notice.title} · ${formatTime(reminderTarget(item,clock))}`,tag:key});
        delivered.current.add(key);
        notification.onclick=()=>{window.focus();setSelected(item.taskId);const at=reminderTarget(item,clock)!;setDay(shanghaiDay(at));setMonth(shanghaiDay(at).slice(0,7));notification.close();};
      } catch {setNotificationText("此浏览器无法显示桌面通知；请使用页内提醒或导出日历。");}
    }
  },[clock,notifications,data,auth.session,auth.checking,error,loading]);

  async function perform(action:()=>Promise<void>) {
    if(busyRef.current)return;
    busyRef.current=true;setBusy(true);setError("");setMessage("");
    try {await action();} catch(reason) {
      setError(errorText(reason));
      auth.rejectExpiredSession(reason);
      // Keep a lost-response write's exact selection for an idempotent retry.
      // Identity/version failures invalidate candidates instead of replaying them.
      if(reason instanceof ApiError && [401,403,409,410].includes(reason.status??0)) {
        setCandidates([]);setChoice(null);setConfirmed(false);
        if(reason.status!==409)setData(empty);
      }
    } finally {busyRef.current=false;setBusy(false);}
  }
  async function queryCandidates() {
    if(!task || !data.capabilities.scheduling)return;
    const currentScope=scope.current, id=task.taskId;
    setChoice(null);setConfirmed(false);setCandidates([]);
    await perform(async()=>{
      if(!auth.session)return;
      const result=await loadCandidates(auth.session,id);
      if(scope.current!==currentScope || selectedRef.current!==id)return;
      if(result.needsConfirmation.length) {setMessage("还需要确认："+result.needsConfirmation.map(confirmationText).join("、"));return;}
      const values=exactCandidates(result.candidateSlots,task.notice.estimatedMinutes);
      setCandidates(values);setMessage(values.length?`在已知课表范围内找到 ${values.length} 个候选；覆盖：${result.coverage.completeness??"未知"}`:"本次未取得足够的连续空档；请核对耗时、截止和课表覆盖。");
    });
  }
  async function save(nextStatus:TaskStatus=task?.status??"pending") {
    if(!task || !editable)return;
    if(choice && !confirmed) {setError("请先勾选确认所选时间。");return;}
    const currentScope=scope.current;
    const update:CalendarUpdate={expected_revision:task.calendarRevision,status:nextStatus,
      scheduled_start:choice?.start??task.scheduledStart,scheduled_end:choice?.end??task.scheduledEnd,
      reminder_minutes:reminder};
    await perform(async()=>{
      if(!auth.session)return;
      if(Date.parse(auth.session.expiresAt)<=Date.now())throw new Error("会话已过期，请重新登录后保存。");
      const signature=JSON.stringify([currentScope,task.taskId,update]);
      if(writeAttempt.current?.signature!==signature) writeAttempt.current={signature,key:crypto.randomUUID()};
      await updateCalendar(auth.session,task.taskId,update,writeAttempt.current.key);
      if(scope.current!==currentScope)return;
      // Do not claim persisted success until a fresh server read returns the new state.
      const fresh=await loadCalendar(auth.session);
      if(scope.current!==currentScope)return;
      const saved=fresh.items.find(t=>t.taskId===task.taskId);
      const sameTime=(a:string|null,b:string|null)=>a===null||b===null?a===b:Date.parse(a)===Date.parse(b);
      if(!saved || fresh.legacy || saved.calendarRevision<=task.calendarRevision || saved.status!==nextStatus
        || !sameTime(saved.scheduledStart,update.scheduled_start) || !sameTime(saved.scheduledEnd,update.scheduled_end) || saved.reminderMinutes!==reminder)
        throw new Error("写入后读回不一致，请刷新核对；重试将沿用同一幂等键。");
      setData(fresh);setChoice(null);setConfirmed(false);writeAttempt.current=null;
      setMessage("安排已保存并从后端读回。");
    });
  }
  async function enableNotifications() {
    if(notifications) {setNotifications(false);setNotificationText("桌面提醒已关闭。");return;}
    if(typeof Notification==="undefined" || !window.isSecureContext) {setNotificationText("此环境不支持桌面通知，请使用页内提醒或导出日历。");return;}
    try {
      const permission=await Notification.requestPermission();
      setNotifications(permission==="granted");
      setNotificationText(permission==="granted"?"仅在本页面保持运行且登录有效时提醒；关闭页面后不保证提醒。":"通知未授权，可在浏览器设置中修改；页内提醒仍可使用。");
    } catch {setNotifications(false);setNotificationText("浏览器未能开启通知，请使用页内提醒或导出日历。");}
  }
  function downloadIcs() {
    const blob=new Blob([calendarIcs(data.items,clock)],{type:"text/calendar;charset=utf-8"});
    const url=URL.createObjectURL(blob),link=document.createElement("a");
    link.href=url;link.download="南开-待办安排.ics";
    document.body.append(link);link.click();link.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    setMessage("已交给浏览器下载。导入系统日历后由日历应用提醒；是否提醒取决于应用设置，导出后不会自动同步。");
  }
  const visible=data.items.filter(t=>(statusFilter==="all"||t.status===statusFilter)&&(allDays||occursOn(t,day)));
  const currentExpired=auth.session && Date.parse(auth.session.expiresAt)<=clock.getTime();
  const showData=!!auth.session && !currentExpired && !auth.checking;
  return <section className="task-calendar">
    <header className="calendar-heading"><div><p className="calendar-eyebrow">把建议变成看得见的安排</p><h1>我的待办日历</h1><p>先核对，再选择；每一件事，都有自己的时间。</p></div>
      <div className="calendar-actions"><button onClick={()=>{setDay(today);setMonth(today.slice(0,7));setAllDays(false);}}>回到今天</button>
        <button onClick={()=>setReload(n=>n+1)} disabled={loading||!auth.session}>刷新记录</button></div></header>
    <>
      {auth.checking && <p role="status">正在核验当前浏览器会话…</p>}
      {(!auth.session && !auth.checking || currentExpired) && <p className="calendar-warning">请先<a href="/tools/login?return_to=%2Ftools%2Fcalendar">登录后返回日历</a>。不会自动新建工作区、保存或排期。</p>}
      {auth.recoveryError!=null && <p role="alert">{errorText(auth.recoveryError)} <button onClick={auth.retryRecovery}>重新核验浏览器会话</button></p>}
      {data.legacy && <p className="calendar-warning">已读取现有待办。D 的日历扩展接口尚未接通：当前只读，不支持完成、改期或保存提醒；截止时间不是已安排时间。</p>}
    </>
    {error && <p className="calendar-error" role="alert">{error}</p>}
    {message && <p className="calendar-message" role="status">{message}</p>}
    {showData && <>
      {loading ? <p role="status">正在读取待办…</p> : <>
        <div className="calendar-stats" aria-label="待办摘要">{[["未完成",counts.pending],["今天",counts.today],["已逾期",counts.overdue],["待安排",counts.unplanned]].map(([label,value])=>
          <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        <p className="calendar-summary" role="status">{counts.pending?`你还有 ${counts.pending} 件未完成事项，今天 ${counts.today} 件${counts.overdue?`，其中 ${counts.overdue} 件已逾期`:""}。`:"当前没有未完成事项。"}</p>
        {remindersDue(data.items,clock).length>0 && <p className="calendar-warning">即将开始／正在进行：{remindersDue(data.items,clock).map(t=>t.notice.title).join("、")}</p>}
        <div className="calendar-workspace"><div className="calendar-month">
          <div className="calendar-month-toolbar"><button aria-label="上个月" onClick={()=>setMonth(shiftMonth(month,-1))}>‹</button><h2>{month.replace("-"," 年 ")} 月</h2><button aria-label="下个月" onClick={()=>setMonth(shiftMonth(month,1))}>›</button></div>
          <div className="calendar-weekdays">{["一","二","三","四","五","六","日"].map(d=><span key={d}>{d}</span>)}</div>
          <div className="calendar-grid">{monthDays(month).map(date=>{
            const items=data.items.filter(t=>t.status!=="cancelled"&&occursOn(t,date));
            return <button key={date} aria-label={`${date}，${items.length} 项`} aria-pressed={date===day}
              className={`calendar-day ${date.slice(0,7)!==month?"outside":""} ${date===today?"today":""}`}
              onClick={()=>{setDay(date);setAllDays(false);}}><span className="calendar-day-number">{Number(date.slice(-2))}</span>
              {items.slice(0,2).map(t=><span key={t.taskId} className={`calendar-day-item ${t.status} ${dueDay(t)===date?"deadline":""}`}>{dueDay(t)===date?"截止 · ":""}{t.notice.title}</span>)}
              {items.length>2&&<span className="calendar-day-more">另 {items.length-2} 项</span>}</button>;
          })}</div><p className="calendar-legend">紫色：截止日期　绿色：实际安排　灰色：已完成 · 北京时间</p>
        </div><aside className="calendar-agenda">
          <div className="calendar-agenda-title"><h2>{allDays?"全部事项":day}</h2><button onClick={()=>setAllDays(v=>!v)}>{allDays?"查看所选日":"查看全部"}</button></div>
          <label className="calendar-filter">显示 <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="pending">未完成</option><option value="completed">已完成</option><option value="cancelled">已取消</option><option value="all">全部状态</option></select></label>
          {visible.length===0&&<p className="calendar-empty">{allDays?"没有此状态的事项。":"这一天没有此状态的事项。可查看全部，找到尚未安排的待办。"}</p>}
          <div className="calendar-task-list">{visible.map(t=><button className={`calendar-task-card ${t.taskId===selected?"selected":""}`} key={t.taskId} onClick={()=>{setSelected(t.taskId);setMessage("");}}>
            <span className="calendar-task-status">{t.status==="completed"?"已完成":t.status==="cancelled"?"已取消":isOverdue(t,clock)?"已逾期":"未完成"}</span><strong>{t.notice.title}</strong>
            <span>{plannedRange(t)?`安排：${formatTime(plannedRange(t)!.start)}${plannedRanges(t).length>1?`，共 ${plannedRanges(t).length} 段`:""}`:t.reminderAt?`提醒：${formatTime(t.reminderAt)}`:"尚未安排时间"}</span><span>截止：{t.notice.due.at?formatTime(t.notice.due.at):t.notice.due.date??"无明确截止"}</span>
          </button>)}</div>
        </aside></div>
        {task && <article className="calendar-detail" key={task.taskId}>
          <div className="calendar-agenda-title"><h2>{task.notice.title}</h2><button onClick={()=>setSelected(null)}>收起详情</button></div>
          <dl><dt>实际安排</dt><dd>{plannedRanges(task).length?plannedRanges(task).map(r=><div key={r.start}>{formatTime(r.start)} — {formatTime(r.end)}</div>):"未安排；截止日期不代表工作时间"}</dd>
            {task.reminderAt&&<><dt>提醒点</dt><dd>{formatTime(task.reminderAt)}（不占用时间，无须结束时间）</dd></>}
            {task.notes&&<><dt>备注</dt><dd>{task.notes}</dd></>}
            <dt>截止要求</dt><dd>{task.notice.due.at?formatTime(task.notice.due.at):task.notice.due.date??"未确定"}</dd>{task.sourceKind!=="personal_task_v1"&&<><dt>预计耗时</dt><dd>{task.notice.estimatedMinutes?`${task.notice.estimatedMinutes} 分钟`:"需要补充"}</dd></>}
            <dt>准备材料</dt><dd>{task.notice.materials.join("、")||"未提供"}</dd></dl>
          {task.notice.sourceSpans.length>0 && <details><summary>查看提取来源</summary>{task.notice.sourceSpans.map((span,i)=><blockquote key={i}>{span.quote}<small>{span.sourceRef}</small></blockquote>)}</details>}
          {task.notice.needsConfirmation.length>0&&<p>待确认：{task.notice.needsConfirmation.map(confirmationText).join("、")}</p>}
          <div className="calendar-actions"><button disabled={!editable||!data.capabilities.scheduling||task.status!=="pending"||!!task.notice.event.start||task.sourceKind==="personal_task_v1"} onClick={queryCandidates}>根据课表重新查候选</button>
            <button disabled={!editable||!data.capabilities.status} onClick={()=>save(task.status==="pending"?"completed":"pending")}>{task.status==="pending"?"标记完成":"恢复未完成"}</button>
            <button disabled={!editable||!data.capabilities.status||task.status==="cancelled"} onClick={()=>save("cancelled")}>取消事项</button></div>
          {candidates.length>0&&<fieldset className="calendar-candidates"><legend>选择一个参考时间</legend>{candidates.map((c,i)=><label key={c.start}><input type="radio" name="calendar-slot" checked={choice?.start===c.start} onChange={()=>{setChoice(c);setConfirmed(false);}}/>方案 {i+1} · {formatTime(c.start)} — {formatTime(c.end)}（{c.durationMinutes} 分钟）</label>)}</fieldset>}
          <label className="calendar-filter">提前提醒 <select disabled={!editable||!data.capabilities.reminders} value={reminder??"none"} onChange={e=>setReminder(e.target.value==="none"?null:Number(e.target.value))}>
            <option value="none">不提醒</option>{[0,5,15,30,60].map(n=><option key={n} value={n}>{n===0?"开始时":`${n} 分钟`}</option>)}</select></label>
          {choice&&<label className="calendar-confirm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已核对并确认选定的时间；截止要求保持不变。</label>}
          <button className="calendar-primary" disabled={!editable||(!choice&&!data.capabilities.reminders)||(!!choice&&!confirmed)} onClick={()=>save()}>{busy?"保存中…":"确认保存安排 / 提醒"}</button>
        </article>}
        <footer className="calendar-reminders"><h2>记下来，也别忘了</h2><p>打开日历可看到待办摘要。桌面通知需要你主动授权，且只在本页面运行、登录有效时工作。</p>
          <div className="calendar-actions"><button onClick={enableNotifications}>{notifications?"关闭桌面提醒":"开启桌面提醒"}</button><button disabled={!data.items.some(t=>t.status==="pending"&&plannedRange(t))||!!error} onClick={downloadIcs}>导出已安排事项（.ics）</button></div>
          {notificationText&&<p role="status">{notificationText}</p>}<p className="calendar-muted">关闭网页后，可用系统日历提醒；需导入 .ics 并检查日历应用的通知设置。导出的安排不会自动更新。Agent 启动提醒还需要 D 接入摘要工具，不是本页已经实现的能力。</p>
        </footer>
      </>}
    </>}
  </section>;
}
