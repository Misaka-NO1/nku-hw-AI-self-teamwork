// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {it,expect,vi} from 'vitest';
import ConnectedImportPage from './ConnectedImportPage';
import {restoreBrowserSession} from '../tasks/sessionCache';
import {scheduleApi} from './connectedApi';
import fixture from '../../../../fixtures/timetable.demo.json';
vi.mock('../tasks/sessionCache',()=>({restoreBrowserSession:vi.fn(),readDemoSession:vi.fn(),sessionExpired:vi.fn(),rejectUnauthenticatedBrowserSession:vi.fn()}));
vi.mock('./connectedApi',()=>({scheduleApi:{current:vi.fn(),draft:vi.fn(),validate:vi.fn(),createDraft:vi.fn()},saveConfirmedSchedule:vi.fn()}));
vi.mock('../timetable/TimetablePage',()=>({default:()=> <div>local timetable preview</div>}));
it('actual focus event during asynchronous native file read preserves its result through the real session hook',async()=>{
 vi.stubEnv('VITE_IDENTITY_PILOT','true');vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
 const session={workspaceRef:'focus-owner',csrfToken:'fictional',expiresAt:'2099-01-01T00:00:00Z'};
 let restore!:(s:typeof session)=>void,finishRead!:(text:string)=>void;
 vi.mocked(restoreBrowserSession).mockResolvedValueOnce(session).mockImplementationOnce(()=>new Promise(r=>restore=r));
 vi.mocked(scheduleApi.current).mockResolvedValue({workspaceRef:session.workspaceRef,scheduleId:'fixture',revision:1,confirmedAt:'',timetable:fixture as any});
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 try {
  await act(async()=>root.render(<ConnectedImportPage/>));
  const input=host.querySelector<HTMLInputElement>('input[aria-label="教务课表文件"]')!;
  const file=new File(['pending'],'timetable-import.json');Object.defineProperty(file,'text',{value:()=>new Promise<string>(r=>finishRead=r)});
  Object.defineProperty(input,'files',{value:[file]});await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));
  await act(async()=>window.dispatchEvent(new Event('focus')));
  expect(input.closest('[aria-hidden=true]')).not.toBeNull();expect(input.closest('fieldset')?.disabled).toBe(true);
  await act(async()=>finishRead(JSON.stringify({...fixture,dataset_kind:'personal',term:{...fixture.term,calendar_status:'user_confirmed'}})));
  await act(async()=>restore({...session,csrfToken:'fresh'}));
  expect(host.querySelector('input[aria-label="教务课表文件"]')).toBe(input);
  expect(input.closest('[aria-hidden=true]')).toBeNull();expect(host.textContent).toContain('文件读取成功');expect(host.textContent).toContain('已解析 timetable-import.json');
  expect(scheduleApi.createDraft).not.toHaveBeenCalled();
 } finally {await act(async()=>root.unmount());host.remove();vi.unstubAllEnvs();vi.unstubAllGlobals();vi.resetAllMocks();}
});
