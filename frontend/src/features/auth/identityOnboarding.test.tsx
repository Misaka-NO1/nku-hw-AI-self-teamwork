// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import CloudbaseLoginPage from "./CloudbaseLoginPage";
import { useBrowserSession } from "./useBrowserSession";
import { apiClient, ApiError } from "../../shared/api/client";
vi.mock("./useBrowserSession", () => ({ useBrowserSession: vi.fn() }));
vi.mock("../../shared/api/client", async original => ({ ...await original<typeof import("../../shared/api/client")>(), apiClient: {get:vi.fn(),post:vi.fn()} }));
let host:HTMLDivElement, root:Root;
let state:{deviceCode:string;hasSpace:boolean;agentLinked:boolean;spaceLabel:string|null;schoolIdentityVerified:boolean};
const assign=vi.fn();
const location={origin:"https://pilot.example.invalid",search:"",assign};
const CODE='DEV'+ '-'+ 'A'.repeat(26), SPACE='SPACE-'+ 'A'.repeat(12);
const button=(label:string)=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent===label)!;
const posted=(suffix:string)=>vi.mocked(apiClient.post).mock.calls.filter(call=>call[0].endsWith(suffix));
const render=async()=>act(async()=>root.render(<CloudbaseLoginPage/>));
beforeEach(()=>{
 vi.clearAllMocks();vi.stubEnv("VITE_IDENTITY_PILOT","true");vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT",true);
 location.search="";state={deviceCode:CODE,hasSpace:false,agentLinked:false,spaceLabel:null,schoolIdentityVerified:false};
 vi.stubGlobal("window",new Proxy(window,{get:(target,key)=>key==='location'?location:Reflect.get(target,key)}));
 vi.mocked(useBrowserSession).mockReturnValue({session:null,setSession:vi.fn(),checking:false,needsLogin:true,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
 vi.mocked(apiClient.get).mockResolvedValue({visitorEnabled:true,agentDeviceBindingEnabled:true,visitorIdentityFirst:true});
 vi.mocked(apiClient.post).mockImplementation(async path=>{
   if(path.endsWith('/state')) return {...state};
   if(path.endsWith('/visitor/session')) throw new ApiError({code:'AUTH_REQUIRED',message:'unknown identity',status:401,requestId:'fixture-unknown'});
   return {status:'pending',deviceCode:CODE};
 });
 host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();vi.unstubAllEnvs();});
it('new browser has one identity-first page, with no new-space action or enrollment on mount',async()=>{
 await render();for(const text of ['1. 核验本人身份','2. 接入原私有空间','3. 进入本人课表与日历',CODE]) expect(host.textContent).toContain(text);
 expect(host.textContent).toContain('无痕窗口不等于新账号');
 expect(host.textContent).not.toContain('免注册建立私有空间');expect(host.textContent).not.toContain('第一次使用，建立空间');
 expect(posted('/start')).toHaveLength(1);expect(posted('/state')).toHaveLength(1);
 expect(posted('/visitor/session')).toHaveLength(0);expect(posted('/claim')).toHaveLength(0);
});
it('checking an unknown identity never creates or navigates',async()=>{
 await render();await act(async()=>button('核验身份并接入空间').click());
 expect(posted('/claim')).toHaveLength(1);expect(posted('/visitor/session')).toHaveLength(0);
 expect(host.textContent).toContain('未新建任何空间');expect(assign).not.toHaveBeenCalled();expect(host.querySelector('.identity-enter')).toBeNull();
 expect(host.querySelector('.identity-feedback [role=status]')?.textContent).toContain('未新建任何空间');
});
it('pending request has visible progress, no repeated submission and no navigation',async()=>{
 await render();let finish!:()=>void;
 const original=vi.mocked(apiClient.post).getMockImplementation()!;
 vi.mocked(apiClient.post).mockImplementation(async(path,...args)=>{
  if(path.endsWith('/claim')) await new Promise<void>(resolve=>{finish=resolve;});
  return original(path,...args);
 });
 await act(async()=>button('核验身份并接入空间').click());
 expect(button('正在处理…').disabled).toBe(true);
 expect(host.querySelector('.identity-feedback')?.textContent).toContain('完成前不会进入工具站');
 await act(async()=>button('正在处理…').click());expect(posted('/claim')).toHaveLength(1);
 await act(async()=>finish());expect(button('核验身份并接入空间').disabled).toBe(false);
 expect(assign).not.toHaveBeenCalled();
});
it('old create/session endpoint rejection is visible and cannot navigate',async()=>{
 await render();await act(async()=>button('恢复本浏览器原有身份').click());
 expect(posted('/visitor/session')[0]).toEqual(['/api/v1/auth/visitor/session',{}, {headers:{'X-Campus-Visitor':'1'}}]);
 expect(host.textContent).toContain('没有新建空间');expect(assign).not.toHaveBeenCalled();expect(host.querySelector('.identity-enter')).toBeNull();
});
it('known legacy browser restores its original space and waits for Agent binding',async()=>{
 const original=vi.mocked(apiClient.post).getMockImplementation()!;
 vi.mocked(apiClient.post).mockImplementation(async(path,...args)=>{
  if(path.endsWith('/visitor/session')) {state={...state,hasSpace:true,spaceLabel:SPACE};return {workspaceRef:'original-space',csrfToken:'fictional-csrf',expiresAt:'2099-01-01T00:00:00Z'};}
  return original(path,...args);
 });
 await render();await act(async()=>button('恢复本浏览器原有身份').click());
 expect(host.textContent).toContain(SPACE);expect(host.textContent).toContain('原空间已恢复');
 expect(host.querySelector('.identity-enter')).toBeNull();expect(assign).not.toHaveBeenCalled();
});
it('existing Agent owner gives the original space without enrollment',async()=>{
 location.search='?'+new URLSearchParams({return_to:'/tools/calendar'});await render();
 state={...state,hasSpace:true,spaceLabel:SPACE,agentLinked:true};await act(async()=>button('核验身份并接入空间').click());
 expect(posted('/visitor/session')).toHaveLength(0);expect(host.querySelector('.identity-enter')?.getAttribute('href')).toBe('/tools/calendar');
});
it('known but unbound owner has no entry until Agent binding is verified',async()=>{
 state={...state,hasSpace:true,spaceLabel:SPACE};await render();expect(button('恢复本浏览器原有身份')).toBeUndefined();
 expect(host.querySelector('.identity-enter')).toBeNull();state={...state,agentLinked:true};
 await act(async()=>button('核验身份并接入空间').click());expect(host.querySelector('.identity-enter')).not.toBeNull();
});
it('OAuth continuation requires a recovered owner, never anonymous enrollment',async()=>{
 const consent='/oauth/authorize?response_type=code&client_id=test-client&redirect_uri=https%3A%2F%2Fcoze.nankai.edu.cn%2Fproduct%2Fllm%2Finfo%2Foauth&scope=demo%3Aread&state=a123456789';
 location.search='?'+new URLSearchParams({return_to:consent});await render();
 expect(Array.from(host.querySelectorAll('a')).some(link=>link.getAttribute('href')===consent)).toBe(false);
 expect(host.textContent).toContain('请先接入原空间');expect(assign).not.toHaveBeenCalled();
 state={...state,hasSpace:true,spaceLabel:SPACE};await act(async()=>button('核验身份并接入空间').click());
 expect(Array.from(host.querySelectorAll('a')).some(link=>link.getAttribute('href')===consent)).toBe(true);
});
it('foreign ownership cannot replace a space',async()=>{
 state={...state,hasSpace:true,spaceLabel:SPACE};await render();
 vi.mocked(apiClient.post).mockRejectedValue(new ApiError({code:'FORBIDDEN',message:'wrong owner',status:403,requestId:'qa'}));
 await act(async()=>button('核验身份并接入空间').click());expect(host.textContent).toContain('不会覆盖或合并空间');expect(host.querySelector('.identity-enter')).toBeNull();
 expect(host.querySelector('.identity-feedback [role=alert]')?.textContent).toContain('绑定被拒绝');
});
it('unexpected owner transition fails closed',async()=>{
 state={...state,hasSpace:true,spaceLabel:SPACE,agentLinked:true};await render();state={...state,spaceLabel:'SPACE-'+ 'B'.repeat(12)};
 await act(async()=>button('核验身份并接入空间').click());expect(host.textContent).toContain('身份已改变');expect(host.querySelector('.identity-enter')).toBeNull();
});
it('failed recheck invalidates previous successful linkage even after copying',async()=>{
 state={...state,hasSpace:true,spaceLabel:SPACE,agentLinked:true};await render();expect(host.querySelector('.identity-enter')).not.toBeNull();
 vi.mocked(apiClient.post).mockRejectedValue(new Error('ownership check unavailable'));
 await act(async()=>button('核验身份并接入空间').click());expect(host.querySelector('.identity-enter')).toBeNull();
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn().mockResolvedValue(undefined)}});
 await act(async()=>button('复制设备码绑定请求').click());expect(host.querySelector('.identity-enter')).toBeNull();
});
it('focus recheck blocks all actions and never enrolls',async()=>{
 await render();const browser=vi.mocked(useBrowserSession).getMockImplementation()!(true);
 vi.mocked(useBrowserSession).mockReturnValue({...browser,checking:true});await render();expect(button('核验身份并接入空间').disabled).toBe(true);
 vi.mocked(useBrowserSession).mockReturnValue({...browser,checking:false});await render();expect(posted('/visitor/session')).toHaveLength(0);
});
it('dependency failure disables identity actions',async()=>{
 vi.mocked(useBrowserSession).mockReturnValue({session:null,setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:new Error('storage offline'),rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});
 await render();expect(apiClient.post).not.toHaveBeenCalled();expect(button('核验身份并接入空间').disabled).toBe(true);
});
it('visitor-disabled deployment retains existing account login',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue({visitorEnabled:false,agentDeviceBindingEnabled:true});await render();
 expect(host.textContent).toContain('当前仅限已批准账号');expect(apiClient.post).not.toHaveBeenCalled();
});
it('a partially updated old server cannot trigger its anonymous enrollment endpoint',async()=>{
 vi.mocked(apiClient.get).mockResolvedValue({visitorEnabled:true,agentDeviceBindingEnabled:true});await render();
 expect(host.textContent).toContain('服务端身份优先保护尚未启用');
 expect(button('恢复本浏览器原有身份').disabled).toBe(true);
 expect(button('核验身份并接入空间').disabled).toBe(true);
 expect(apiClient.post).not.toHaveBeenCalled();
});
it('unsupported school identity assertions cannot unlock the page',async()=>{
 state={...state,schoolIdentityVerified:true,hasSpace:true,spaceLabel:SPACE,agentLinked:true};await render();
 expect(host.textContent).toContain('身份状态无法核实');expect(host.querySelector('.identity-enter')).toBeNull();
});
