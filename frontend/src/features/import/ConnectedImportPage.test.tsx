// @vitest-environment jsdom
import { act } from "react";
import { createRoot,type Root } from "react-dom/client";
import { beforeEach,afterEach,it,expect,vi } from "vitest";
import fixture from "../../../../fixtures/timetable.demo.json";
import ConnectedImportPage from "./ConnectedImportPage";
import { useBrowserSession } from "../auth/useBrowserSession";
import { scheduleApi,saveConfirmedSchedule } from "./connectedApi";
vi.mock('../auth/useBrowserSession',()=>({useBrowserSession:vi.fn()}));
vi.mock('./connectedApi',()=>({scheduleApi:{current:vi.fn(),draft:vi.fn(),validate:vi.fn(),createDraft:vi.fn()},saveConfirmedSchedule:vi.fn()}));
vi.mock('./ImportPage',()=>({default:(props:any)=><><button onClick={()=>props.onConfirmed(fixture)}>准备测试草稿</button><button onClick={()=>props.onEdited()}>修改预览内容</button></>}));
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
