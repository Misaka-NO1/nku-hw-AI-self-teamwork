// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect,it,vi } from 'vitest';
import { DegreePage } from './DegreePage';
it('old links only guide back to Agent, without import, demo or network calls',()=>{
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);vi.stubGlobal('fetch',vi.fn());
  const host=document.createElement('div');const root=createRoot(host);
  try{
    act(()=>root.render(<DegreePage/>));
    expect(host.textContent).toContain('degree-progress.json');
    expect(host.textContent).toContain('确认保存这份学分报告');
    expect(host.querySelector('input,button,table,details')).toBeNull();
    expect(host.textContent).not.toContain('演示');
    expect(fetch).not.toHaveBeenCalled();
  }finally{act(()=>root.unmount());vi.unstubAllGlobals();}
});
