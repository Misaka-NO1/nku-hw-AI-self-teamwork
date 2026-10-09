import { useEffect, useRef, useState } from "react";
import type { TimetableImport } from "@campus/import-core";
import ImportPage from "./ImportPage";
import TimetablePage from "../timetable/TimetablePage";
import { scheduleApi, saveConfirmedSchedule, type ScheduleDraft } from "./connectedApi";
import type { DemoSession, SaveAttempt } from "../tasks/api";
import { ApiError } from "../../shared/api/client";
import { useBrowserSession } from "../auth/useBrowserSession";
import { toolReviewLoginUrl } from "../auth/toolReviewReturn";

const newKey=()=>`schedule-${crypto.randomUUID()}`;
function errorText(e:unknown) { return e instanceof ApiError ? `${e.message}（${e.code} · ${e.requestId ?? "无请求编号"}）` : e instanceof Error ? e.message : "课表操作失败，请重试。"; }
export default function ConnectedImportPage() {
 const auth=useBrowserSession(import.meta.env.VITE_IDENTITY_PILOT==="true");
 // Native file dialogs return focus to the browser and trigger an owner check.
 // Keep local state mounted, but hidden and non-writable until that check ends.
 const lastVerified=useRef<DemoSession|null>(null);
 if(!auth.checking) lastVerified.current=auth.recoveryError ? null : auth.session;
 const heldSession=auth.checking ? lastVerified.current : auth.session;
 const loginUrl=toolReviewLoginUrl(window.location.pathname+window.location.search,window.location.origin) ?? "/tools/login";
 return <section className="import-shell">
  {auth.checking && <p role="status">正在核验当前浏览器会话；完成前不能读写或确认。</p>}
  {auth.needsLogin && <p>请<a href={loginUrl}>登录本人账号</a>后导入。未登录时仍可本地核对，不会自动保存。</p>}
  {!!auth.recoveryError && <p role="alert">{errorText(auth.recoveryError)} <button onClick={auth.retryRecovery}>重新核验浏览器会话</button></p>}
  {(auth.checking || !!auth.recoveryError) && <button disabled>登录核验后可生成本人课表草稿</button>}
  {!auth.recoveryError && (!auth.checking || heldSession) && <div className="import-owned" data-auth-paused={auth.checking} aria-hidden={auth.checking}>
   <OwnedImport key={heldSession?.workspaceRef ?? "offline"} session={heldSession} paused={auth.checking} onAuthError={auth.rejectExpiredSession}/>
  </div>}
 </section>;
}
function OwnedImport({session,paused,onAuthError}:{session:DemoSession|null;paused:boolean;onAuthError:(e:unknown)=>void}) {
 const [draft,setDraft]=useState<ScheduleDraft|null>(null);
 const [saved,setSaved]=useState<TimetableImport|null>(null);
 const [edit,setEdit]=useState<TimetableImport|null>(null);
 const [preview,setPreview]=useState<TimetableImport|null>(null);
 const [editorKey,setEditorKey]=useState(0);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [message,setMessage]=useState("");
 const [fileStatus,setFileStatus]=useState<{message:string;error:boolean}|null>(null);
 const lock=useRef(false),alive=useRef(true);
 const gate=useRef({paused,epoch:0});
 if(gate.current.paused!==paused) gate.current={paused,epoch:gate.current.epoch+1};
 const pending=useRef<{json:string;key:string}|null>(null);
 const attempt=useRef<SaveAttempt|null>(null);
 const cache=`campus-own-schedule-attempt:${session?.workspaceRef ?? "offline"}`;
 useEffect(()=>{
  alive.current=true;
  if(!session) return ()=>{alive.current=false;};
  scheduleApi.current(session).then(item=>{if(item.workspaceRef!==session.workspaceRef) throw new Error("课表归属不一致");if(alive.current)setSaved(item.timetable);})
   .catch(e=>{if(alive.current && !(e instanceof ApiError && e.status===404)){onAuthError(e);setError(errorText(e));}});
  const id=new URLSearchParams(location.search).get("draft_id");
  if(id) scheduleApi.draft(id).then(item=>{
   if(item.workspaceRef!==session.workspaceRef || item.kind!=="schedule") throw new Error("不是本人的课表草稿");
   if(alive.current) setDraft(item);
  }).catch(e=>{if(alive.current){onAuthError(e);setError(errorText(e));}});
  return ()=>{alive.current=false;};
 },[session?.workspaceRef]);
 async function perform(action:(guard:()=>void)=>Promise<void>) {
  if(lock.current || paused) return;lock.current=true;setBusy(true);setError("");setMessage("");
  const epoch=gate.current.epoch;
  const guard=()=>{if(!alive.current || gate.current.paused || gate.current.epoch!==epoch) throw new Error("登录会话已重新核验，请核对当前进度后重试；不会继续自动保存。");};
  try {guard();await action(guard);} catch(e) {if(alive.current){onAuthError(e);setError(errorText(e));}}
  finally {lock.current=false;if(alive.current)setBusy(false);}
 }
 function generate(payload:TimetableImport) {void perform(async guard=>{
  if(!session) throw new Error("核对结果尚未上传，请先登录本人账号。");
  const json=JSON.stringify(payload);
  if(!pending.current || pending.current.json!==json) pending.current={json,key:newKey()};
  await scheduleApi.validate(payload);
  guard();
  const item=await scheduleApi.createDraft(session,payload,pending.current.key);
  guard();
  if(item.workspaceRef!==session.workspaceRef || item.kind!=="schedule") throw new Error("服务器草稿归属不一致");
  if(!alive.current)return;
  setDraft(item);attempt.current=null;
  setMessage("已生成云端草稿，尚未保存。请最后核对下方课表，再确认替换本人课表；待办日历保留。");
 });}
 function confirm() {void perform(async guard=>{
  if(!session || !draft) return;
  let old=attempt.current;
  if(!old) {try {old=JSON.parse(sessionStorage.getItem(cache) ?? "null");} catch { /* safe retry with a new receipt */ }}
  const value:SaveAttempt=old?.draftId===draft.draftId && old.revision===draft.revision && old.payloadHash===draft.payloadHash ? old : {
   draftId:draft.draftId,revision:draft.revision,payloadHash:draft.payloadHash,confirmationKey:newKey(),commitKey:newKey(),
  };
  const result=await saveConfirmedSchedule(session,draft,value,a=>{attempt.current=a;sessionStorage.setItem(cache,JSON.stringify(a));},guard);
  guard();
  const current=await scheduleApi.current(session);
  guard();
  if(current.workspaceRef!==session.workspaceRef || current.scheduleId!==result.scheduleId || current.revision!==result.revision)
   throw new Error("保存回执与数据库读回版本不一致，请刷新核验，不会假报成功。");
  if(!alive.current)return;
  setDraft({...draft,status:"committed"});setSaved(current.timetable);
  setMessage(`保存成功：已保存并从数据库读回本人课表，共 ${current.timetable.courses.length} 门课程 · 版本 ${current.revision}。刷新或重新登录后仍可查看。`);
 });}
 return <>
  <section className="import-progress" aria-label="导入进度" aria-live="polite">
   {error ? <p role="alert">{error}</p> : <p role={!busy && !message && fileStatus?.error ? "alert" : "status"}>{busy ? "正在上传 / 保存课表，请等待云端回执…" : message || (preview ? `文件读取成功：${preview.courses.length} 门课程。尚未上传保存，请核对下方预览。` : fileStatus?.message || "请选择课表文件；读取、上传草稿和正式保存都会在这里显示结果。")}</p>}
  </section>
  {saved && <button disabled={busy} onClick={()=>{setEdit(saved);setEditorKey(n=>n+1);setDraft(null);pending.current=null;setMessage("正在修改已保存课表；确认新版本前旧课表保持不变。");}}>修改已保存课表</button>}
  <fieldset disabled={busy || paused}><ImportPage key={editorKey} initialTimetable={edit} calendar={saved?.term} datasetKind="personal" onFileStatus={setFileStatus} onPreview={setPreview} onConfirmed={generate} onEdited={()=>{setDraft(null);setMessage("");attempt.current=null;pending.current=null;}}/></fieldset>
  {preview && !draft && <section className="import-commit" aria-label="原课表界面中的本地预览"><h2>课表效果预览（尚未保存）</h2><TimetablePage timetable={preview}/></section>}
  {(draft || error || message) && <section className="import-commit" aria-label="本人课表保存与读回">
   {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
   {busy && <p role="status">正在处理，请勿重复操作…</p>}
   {draft && <><p>当前云端草稿：{draft.status==="committed" ? "已保存" : "待确认保存"}。重新上传修改后的内容会生成新草稿。</p>
    <TimetablePage timetable={draft.payload}/>
    <button disabled={busy || paused || !session || draft.status==="committed"} onClick={confirm}>我已核对，确认替换本人课表并保存</button></>}
   <a href="/tools/timetable">打开已保存课表 →</a>
  </section>}
 </>;
}
