// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import CloudbaseLoginPage from "./CloudbaseLoginPage";
import { useBrowserSession } from "./useBrowserSession";
import { apiClient } from "../../shared/api/client";
vi.mock("./useBrowserSession", () => ({ useBrowserSession: vi.fn() }));
vi.mock("../../shared/api/client", async original => ({ ...await original<typeof import("../../shared/api/client")>(), apiClient: {get:vi.fn(),post:vi.fn()} }));
let host:HTMLDivElement, root:Root;
const assign=vi.fn();
const location={origin:"https://pilot.example.invalid",search:"",assign};
beforeEach(()=>{
 vi.clearAllMocks();vi.stubEnv("VITE_IDENTITY_PILOT","true");vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);
 location.search="";
 vi.stubGlobal("window",new Proxy(window,{get:(target,key)=>key==='location'?location:Reflect.get(target,key)}));
 vi.mocked(useBrowserSession).mockReturnValue({session:null,setSession:vi.fn(),checking:false,needsLogin:true,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
 vi.mocked(apiClient.get).mockResolvedValue({visitorEnabled:true,agentDeviceBindingEnabled:true});
 host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();vi.unstubAllEnvs();});
it('does not create a visitor, login or authorize on mount',async()=>{
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 expect(host.textContent).toContain('免注册开始使用');expect(apiClient.post).not.toHaveBeenCalled();
 expect(host.textContent).toContain('清除本站全部浏览器数据会丢失访客身份');
});
it('explicit start uses empty same-origin request and returns to OAuth without auto-consent',async()=>{
 window.location.search='?'+new URLSearchParams({return_to:'/oauth/authorize?response_type=code&client_id=test-client&redirect_uri=https%3A%2F%2Fcoze.nankai.edu.cn%2Fproduct%2Fllm%2Finfo%2Foauth&scope=demo%3Aread&state=a123456789'});
 vi.mocked(apiClient.post).mockResolvedValue({workspaceRef:'visitor-own-space',csrfToken:'private-csrf',expiresAt:'2099-01-01T00:00:00Z'});
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='免注册开始使用')!.click());
 expect(apiClient.post).toHaveBeenCalledWith('/api/v1/auth/visitor/session',{}, {headers:{'X-Campus-Visitor':'1'}});
 expect(apiClient.post).toHaveBeenCalledTimes(1);expect(assign).toHaveBeenCalled();
 expect(String(assign.mock.calls[0][0])).toMatch(/^\/oauth\/authorize\?/);
});
it('does not bootstrap after dependency failure or expose a new-space fallback',async()=>{
 vi.mocked(useBrowserSession).mockReturnValue({session:null,setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:new Error('storage offline'),rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 expect(Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='免注册开始使用')!.disabled).toBe(true);
 expect(apiClient.post).not.toHaveBeenCalled();
});
it('keeps the registered-only path when visitors are disabled',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue({visitorEnabled:false,agentDeviceBindingEnabled:true});
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 expect(host.textContent).not.toContain('免注册开始使用');
 expect(host.textContent).toContain('当前仅限已批准账号');
 expect(apiClient.post).not.toHaveBeenCalled();
});
it('never creates a visitor over a recovered owner',async()=>{
 vi.mocked(useBrowserSession).mockReturnValue({session:{workspaceRef:'existing-owner',csrfToken:'fictional-csrf',expiresAt:'2099-01-01T00:00:00Z'},setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 expect(host.textContent).not.toContain('免注册开始使用');
 expect(apiClient.post).not.toHaveBeenCalled();
});
it('failed visitor start shows an error without navigating or authorizing',async()=>{
 vi.mocked(apiClient.post).mockRejectedValue(new Error('private storage unavailable'));
 await act(async()=>root.render(<CloudbaseLoginPage/>));
 await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='免注册开始使用')!.click());
 expect(host.querySelector('[role=alert]')?.textContent).toContain('private storage unavailable');
 expect(assign).not.toHaveBeenCalled();
 expect(apiClient.post).toHaveBeenCalledTimes(1);
});
