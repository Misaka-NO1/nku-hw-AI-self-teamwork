// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import NativeIdentityOnboarding from "./NativeIdentityOnboarding";
import { apiClient, ApiError } from "../../shared/api/client";
vi.mock("../../shared/api/client", async original => ({ ...await original<typeof import("../../shared/api/client")>(), apiClient:{post:vi.fn()} }));
let host:HTMLDivElement,root:Root;
let state:{status:string;hasSpace:boolean;created:boolean;spaceLabel:string|null};
const CODE='DEV-'+ 'A'.repeat(26), SPACE='SPACE-'+ 'A'.repeat(12);
const button=(label:string)=>Array.from(host.querySelectorAll('button')).find(e=>e.textContent===label)!;
const calls=(suffix:string)=>vi.mocked(apiClient.post).mock.calls.filter(c=>c[0].endsWith(suffix));
const writeText=vi.fn();
async function render(checking=false,blocked=false,consentReturn:string|null=null) {
 await act(async()=>root.render(<NativeIdentityOnboarding checking={checking} blocked={blocked} destination="/tools/calendar" consentReturn={consentReturn}/>));
}
beforeEach(()=>{
 vi.clearAllMocks();vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
 state={status:'identity_pending',hasSpace:false,created:false,spaceLabel:null};
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText}});writeText.mockResolvedValue(undefined);
 vi.mocked(apiClient.post).mockImplementation(async path=>path.endsWith('/start') ? {deviceCode:CODE}:path.endsWith('/state') ? {...state}:{status:'pending'});
 host=document.createElement('div');document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();});
it('unknown browser has identity lookup only, never creates or claims on mount',async()=>{
 await render();expect(host.textContent).toContain(CODE);expect(host.textContent).toContain('不可创建空间');
 expect(button('首次使用：复制免注册创建确认')).toBeUndefined();expect(calls('/start')).toHaveLength(1);expect(calls('/claim')).toHaveLength(0);
 await act(async()=>button('复制平台身份核验请求').click());expect(writeText).toHaveBeenCalledWith(expect.stringContaining('不创建空间'));
 expect(calls('/claim')).toHaveLength(0);
});
it('verified first use has explicit new-user confirmation and old-space alternative',async()=>{
 state={...state,status:'first_use_confirmation'};await render();
 await act(async()=>button('首次使用：复制免注册创建确认').click());
 expect(writeText).toHaveBeenCalledWith(expect.stringContaining('已有空间则只复用'));
 expect(host.textContent).toContain('复制本身不会创建空间');expect(calls('/onboard')).toHaveLength(0);
 await act(async()=>button('我以前用过，关联原空间').click());expect(writeText).toHaveBeenLastCalledWith(expect.stringContaining('原有的插件授权'));
});
it('existing platform account never shows create and only copies original-space bind',async()=>{
 state={...state,status:'existing_space',hasSpace:true,spaceLabel:SPACE};await render();
 expect(button('首次使用：复制免注册创建确认')).toBeUndefined();expect(host.textContent).toContain('不重复创建');
 await act(async()=>button('复制原空间设备绑定确认').click());expect(writeText).toHaveBeenCalledWith(expect.stringContaining('原私有空间'));
 expect(host.querySelector('.identity-enter')).toBeNull();
});
it('legacy owner cannot create and requires original OAuth association',async()=>{
 state={...state,status:'legacy_authorization_required'};await render();expect(button('首次使用：复制免注册创建确认')).toBeUndefined();
 await act(async()=>button('复制原账号关联请求').click());expect(writeText).toHaveBeenCalledWith(expect.stringContaining('不创建或合并空间'));
});
it('successful explicit claim has clear status and original destination with separate consent',async()=>{
 state={...state,status:'browser_authorized',hasSpace:true,spaceLabel:SPACE};await render(false,false,'/oauth/authorize?fixture');
 state={...state,status:'bound'};await act(async()=>button('已在 Agent 确认，检查绑定结果').click());
 expect(calls('/claim')).toHaveLength(1);expect(host.querySelector('.identity-enter')?.getAttribute('href')).toBe('/tools/calendar');
 expect(host.textContent).toContain('数据读写仍须本人插件授权');expect(host.querySelector('a[href="/oauth/authorize?fixture"]')).not.toBeNull();
});
it('pending check displays incomplete, no navigation or successful binding',async()=>{
 await render();await act(async()=>button('已在 Agent 确认，检查绑定结果').click());
 expect(host.textContent).toContain('尚未收到平台身份核验');expect(host.querySelector('.identity-enter')).toBeNull();
});
it('stale different-space state invalidates old successful entry',async()=>{
 state={...state,status:'bound',hasSpace:true,spaceLabel:SPACE};await render();expect(host.querySelector('.identity-enter')).not.toBeNull();
 state={...state,spaceLabel:'SPACE-'+ 'B'.repeat(12)};await act(async()=>button('已在 Agent 确认，检查绑定结果').click());
 expect(host.querySelector('.identity-enter')).toBeNull();expect(host.textContent).toContain('空间归属发生变化');
});
it('network failure is visible and invalidates entry until fresh verification',async()=>{
 state={...state,status:'bound',hasSpace:true,spaceLabel:SPACE};await render();
 vi.mocked(apiClient.post).mockRejectedValue(new ApiError({code:'FORBIDDEN',message:'wrong owner',status:403,requestId:'fixture-native'}));
 await act(async()=>button('已在 Agent 确认，检查绑定结果').click());expect(host.textContent).toContain('fixture-native');expect(host.querySelector('.identity-enter')).toBeNull();
});
it('checking or blocked page never enrolls or claims',async()=>{
 await render(true);expect(apiClient.post).not.toHaveBeenCalled();expect(button('已在 Agent 确认，检查绑定结果').disabled).toBe(true);
 await render(false,true);expect(apiClient.post).not.toHaveBeenCalled();
});
