import { ApiError, apiClient } from "../../shared/api/client";
import { tasksApi, type DemoSession } from "../tasks/api";
import { READ_ONLY, type CalendarData, type CalendarTask, type Candidate, type TaskStatus } from "./model";

/** Proposed D integration surface. Missing extension stays explicitly read-only. */
export async function loadCalendar(session:DemoSession,signal?:AbortSignal):Promise<CalendarData> {
  try {
    const result=await apiClient.get<CalendarData>(`/api/v1/tasks/calendar?${new URLSearchParams({workspace_ref:session.workspaceRef})}`,{signal});
    if(!Array.isArray(result.items) || !result.capabilities || ["scheduling","status","reminders"].some(k=>typeof result.capabilities[k as keyof typeof result.capabilities]!=="boolean")
      || result.items.some(t=>!t.taskId || !t.notice || !Number.isInteger(t.calendarRevision) || !["pending","completed","cancelled"].includes(t.status)
        || (t.reminderMinutes!==null && (!Number.isInteger(t.reminderMinutes)||t.reminderMinutes<0||t.reminderMinutes>10080))
        || (t.scheduledStart===null)!==(t.scheduledEnd===null) || (t.scheduledStart!==null && (!Number.isFinite(Date.parse(t.scheduledStart))||!(Date.parse(t.scheduledEnd!)>Date.parse(t.scheduledStart))))))
      throw new Error("日历响应不符合联调约定，已停止显示和写入");
    return result;
  } catch(error) {
    if(!(error instanceof ApiError) || ![404,501].includes(error.status??0)) throw error;
    if(signal?.aborted) throw error;
    const records=await tasksApi.list(session);
    return {legacy:true,capabilities:READ_ONLY,items:records.map(t=>({...t,calendarRevision:0,status:"pending",
      scheduledStart:null,scheduledEnd:null,reminderMinutes:null}))};
  }
}
export function loadCandidates(session:DemoSession,taskId:string) {
  return apiClient.get<{candidateSlots:Candidate[];needsConfirmation:string[];coverage:{completeness?:string}}>(
    `/api/v1/tasks/${encodeURIComponent(taskId)}/calendar/candidates?${new URLSearchParams({workspace_ref:session.workspaceRef})}`);
}
export interface CalendarUpdate {
  expected_revision:number;status:TaskStatus;scheduled_start:string|null;scheduled_end:string|null;reminder_minutes:number|null;
}
export function updateCalendar(session:DemoSession,taskId:string,update:CalendarUpdate,key:string):Promise<CalendarTask> {
  return apiClient.post(`/api/v1/tasks/${encodeURIComponent(taskId)}/calendar`,{workspace_ref:session.workspaceRef,...update},
    {headers:{"X-CSRF-Token":session.csrfToken,"Idempotency-Key":key}});
}
