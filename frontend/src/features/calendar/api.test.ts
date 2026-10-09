import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "../../shared/api/client";
import { tasksApi } from "../tasks/api";
import { loadCalendar, loadCandidates, updateCalendar } from "./api";
import { previewTasks } from "./model";
vi.mock("../../shared/api/client",async importOriginal=>{
  const original=await importOriginal<typeof import("../../shared/api/client")>();
  return {...original,apiClient:{get:vi.fn(),post:vi.fn()}};
});
vi.mock("../tasks/api",()=>({tasksApi:{list:vi.fn()}}));
const session={workspaceRef:"test-workspace",csrfToken:"fictional-csrf",expiresAt:"2099-01-01T00:00:00Z"};
describe("calendar adapter",()=>{
  beforeEach(()=>vi.clearAllMocks());
  it("reads capability-gated server data",async()=>{
    const data={items:previewTasks("2026-10-06"),capabilities:{scheduling:true,status:true,reminders:true}};
    vi.mocked(apiClient.get).mockResolvedValue(data);
    expect(await loadCalendar(session)).toEqual(data);expect(tasksApi.list).not.toHaveBeenCalled();
  });
  it("missing extension falls back only to explicit read-only existing records",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError({status:404,code:"NOT_FOUND",message:"Missing extension",requestId:"test"}));
    vi.mocked(tasksApi.list).mockResolvedValue(previewTasks("2026-10-06"));
    const result=await loadCalendar(session);
    expect(result.legacy).toBe(true);expect(result.capabilities.scheduling).toBe(false);expect(result.items[0].scheduledStart).toBeNull();
  });
  it("auth failure never substitutes demo tasks or another API",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError({status:401,code:"AUTH_REQUIRED",message:"Expired",requestId:"auth"}));
    await expect(loadCalendar(session)).rejects.toThrow("Expired");expect(tasksApi.list).not.toHaveBeenCalled();
  });
  it("503 and malformed responses are not empty success",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError({status:503,code:"DEPENDENCY_UNAVAILABLE",message:"Failed",requestId:"503"}));
    await expect(loadCalendar(session)).rejects.toThrow("Failed");
    vi.mocked(apiClient.get).mockResolvedValue({items:[],capabilities:{scheduling:"yes"}});
    await expect(loadCalendar(session)).rejects.toThrow("联调约定");expect(tasksApi.list).not.toHaveBeenCalled();
  });
  it("writes only explicit fields with CSRF, revision and stable idempotency key",async()=>{
    vi.mocked(apiClient.post).mockResolvedValue({});
    const update={expected_revision:2,status:"pending" as const,scheduled_start:null,scheduled_end:null,reminder_minutes:0};
    await updateCalendar(session,"task/a",update,"stable-key");
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/tasks/task%2Fa/calendar",{workspace_ref:session.workspaceRef,...update},
      {headers:{"X-CSRF-Token":"fictional-csrf","Idempotency-Key":"stable-key"}});
  });
  it("candidate read does not send identity supplied by chat or create any write",async()=>{
    vi.mocked(apiClient.get).mockResolvedValue({candidateSlots:[]});await loadCandidates(session,"task/a");
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tasks/task%2Fa/calendar/candidates?workspace_ref=test-workspace");
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
