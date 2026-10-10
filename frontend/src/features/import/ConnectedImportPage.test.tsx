// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot,type Root } from "react-dom/client";
import { beforeEach,afterEach,it,expect,vi } from "vitest";
import fixture from "../../../../fixtures/timetable.demo.json";
import ConnectedImportPage from "./ConnectedImportPage";
import { useBrowserSession } from "../auth/useBrowserSession";
import { scheduleApi,saveConfirmedSchedule } from "./connectedApi";
vi.mock('../auth/useBrowserSession',()=>({useBrowserSession:vi.fn()}));
vi.mock('./connectedApi',()=>({scheduleApi:{current:vi.fn(),draft:vi.fn(),validate:vi.fn(),createDraft:vi.fn()},saveConfirmedSchedule:vi.fn()}));
vi.mock('./ImportPage',()=>({default:(props:any)=>{const [name,setName]=useState('');return <><span data-testid="owned-calendar">{props.calendar?.term_id}</span><input aria-label="local file state" value={name} onChange={e=>setName(e.target.value)}/><button onClick={()=>{setName('timetable-import.json');props.onPreview(fixture);}}>读取测试文件</button><button onClick={()=>props.onConfirmed(fixture)}>准备测试草稿</button><button onClick={()=>props.onEdited()}>修改预览内容</button></>;}}));
vi.mock('../timetable/TimetablePage',()=>({default:()=> <div>昨天的课表 UI</div>}));
let host:HTMLDivElement,root:Root;
const session={workspaceRef:'owner-a',csrfToken:'test',expiresAt:'2099-01-01T00:00:00Z'};
const draft={draftId:'draft-a',kind:'schedule' as const,workspaceRef:'owner-a',revision:1,payloadHash:'hash',status:'draft' as const,expiresAt:'2099-01-01T00:00:00Z',payload:fixture as any};
beforeEach(()=>{vi.clearAllMocks();vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);vi.mocked(useBrowserSession).mockReturnValue({session,setSession:vi.fn(),checking:false,needsLogin:false,recoveryError:null,rejectExpiredSession:vi.fn(),retryRecovery:vi.fn()});vi.mocked(scheduleApi.current).mockResolvedValue({workspaceRef:session.workspaceRef,scheduleId:'saved-a',revision:2,confirmedAt:'2026-10-08T17:00:00+08:00',timetable:fixture as any});vi.mocked(scheduleApi.createDraft).mockResolvedValue(draft);vi.mocked(saveConfirmedSchedule).mockResolvedValue({scheduleId:'saved-a',revision:2});host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();});
async function click(text:string){await act(async()=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent===text)!.click());}
it('explicit preview then save then matching database readback, no writes on mount',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));expect(scheduleApi.createDraft).not.toHaveBeenCalled();expect(saveConfirmedSchedule).not.toHaveBeenCalled();
 await click('准备测试草稿');expect(scheduleApi.createDraft).toHaveBeenCalled();expect(saveConfirmedSchedule).not.toHaveBeenCalled();expect(host.textContent).toContain('昨天的课表 UI');
 await click('我已核对，确认替换本人课表并保存');expect(host.textContent).toContain('从数据库读回本人课表');
});
it('editing invalidates an already-created server draft before confirmation',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));await click('准备测试草稿');await click('修改预览内容');
 expect(host.textContent).not.toContain('确认替换本人课表并保存');expect(saveConfirmedSchedule).not.toHaveBeenCalled();
});
it('mismatched readback never reports save success',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));await click('准备测试草稿');vi.mocked(scheduleApi.current).mockResolvedValue({workspaceRef:'owner-b',scheduleId:'saved-a',revision:2,confirmedAt:'',timetable:fixture as any});
 await click('我已核对，确认替换本人课表并保存');expect(host.textContent).toContain('读回版本不一致');expect(host.textContent).not.toContain('已保存并从数据库读回');
});
it('passes the asynchronously read owner calendar into file import without loading old courses into the editor',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));
 expect(host.querySelector('[data-testid="owned-calendar"]')?.textContent).toBe(fixture.term.term_id);
 expect(scheduleApi.createDraft).not.toHaveBeenCalled();expect(saveConfirmedSchedule).not.toHaveBeenCalled();
});
async function authChange(change:Record<string,unknown>){const results=vi.mocked(useBrowserSession).mock.results;vi.mocked(useBrowserSession).mockReturnValue({...results[results.length-1]!.value,...change});await act(async()=>root.render(<ConnectedImportPage/>));}
it('native file-dialog focus recheck hides and disables the same mounted editor, then restores its local file and preview',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));await click('读取测试文件');
 const input=host.querySelector('input')!;
 await authChange({checking:true,session:null});
 expect(host.querySelector('input')).toBe(input);expect(input.closest('[aria-hidden=true]')).not.toBeNull();expect(input.closest('fieldset')?.disabled).toBe(true);
 await click('准备测试草稿');expect(scheduleApi.createDraft).not.toHaveBeenCalled();
 await authChange({checking:false,session:{...session,csrfToken:'refreshed'}});
 expect(host.querySelector('input')).toBe(input);expect(input.value).toBe('timetable-import.json');expect(host.textContent).toContain('文件读取成功');expect(input.closest('[aria-hidden=true]')).toBeNull();
});
it('verified account change discards all previous import state',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));await click('读取测试文件');const input=host.querySelector('input');
 await authChange({checking:true,session:null});
 vi.mocked(scheduleApi.current).mockResolvedValue({workspaceRef:'owner-b',scheduleId:'saved-b',revision:1,confirmedAt:'',timetable:fixture as any});
 await authChange({checking:false,session:{...session,workspaceRef:'owner-b'}});
 expect(host.querySelector('input')).not.toBe(input);expect(host.querySelector('input')?.value).toBe('');expect(host.textContent).not.toContain('文件读取成功');
});
it('failed session verification removes the held editor and never offers old-owner confirmation',async()=>{
 await act(async()=>root.render(<ConnectedImportPage/>));await click('准备测试草稿');
 await authChange({checking:true,session:null});await authChange({checking:false,session:null,needsLogin:true,recoveryError:new Error('revoked')});
 expect(host.querySelector('input')).toBeNull();expect(host.textContent).not.toContain('确认替换本人课表并保存');expect(saveConfirmedSchedule).not.toHaveBeenCalled();
});
it('a focus check during validation stops the subsequent cloud write, even when the same owner returns',async()=>{
 let resolve!:()=>void;vi.mocked(scheduleApi.validate).mockReturnValue(new Promise<any>(r=>{resolve=()=>r({valid:true,issues:[]});}));
 await act(async()=>root.render(<ConnectedImportPage/>));await click('准备测试草稿');
 await authChange({checking:true,session:null});await authChange({checking:false,session});
 await act(async()=>resolve());expect(scheduleApi.createDraft).not.toHaveBeenCalled();expect(host.textContent).toContain('不会继续自动保存');
});
