import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CalendarPage from "./CalendarPage";
import { useBrowserSession } from "../auth/useBrowserSession";
import { ApiError } from "../../shared/api/client";
vi.mock("../auth/useBrowserSession",()=>({useBrowserSession:vi.fn()}));
const state=(overrides:Partial<ReturnType<typeof useBrowserSession>>={})=>({session:null,setSession:vi.fn(),checking:true,needsLogin:false,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn(),...overrides});
describe("calendar page identity boundaries",()=>{
  beforeEach(()=>{vi.stubEnv("VITE_IDENTITY_PILOT","true");vi.mocked(useBrowserSession).mockReturnValue(state());});
  afterEach(()=>vi.unstubAllEnvs());
  it("waits for identity and provides opt-in preview only",()=>{
    const html=renderToStaticMarkup(createElement(CalendarPage));
    expect(html).toContain("正在核验当前浏览器会话");expect(html).toContain("查看前端演示");
    expect(html).not.toContain("提交课程报告");expect(html).not.toContain("未完成事项，今天");
  });
  it("no session shows login rather than creating a workspace",()=>{
    vi.mocked(useBrowserSession).mockReturnValue(state({checking:false,needsLogin:true}));
    const html=renderToStaticMarkup(createElement(CalendarPage));
    expect(html).toContain("/tools/login?return_to=%2Ftools%2Fcalendar");expect(html).toContain("不会自动新建工作区");
    expect(html).not.toContain("提交课程报告");
  });
  it("dependency failure is visible and retryable, with no live task data",()=>{
    vi.mocked(useBrowserSession).mockReturnValue(state({checking:false,recoveryError:new ApiError({status:503,code:"DEPENDENCY_UNAVAILABLE",message:"Dependency unavailable",requestId:"test-503"})}));
    const html=renderToStaticMarkup(createElement(CalendarPage));
    expect(html).toContain("test-503");expect(html).toContain("重新核验浏览器会话");expect(html).not.toContain("calendar-task-card");
  });
});
