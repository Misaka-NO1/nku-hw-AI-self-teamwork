// Pure request compiler. No identity, timetable, database, or inferred availability.
// Re-run after every edit. This is NOT a save endpoint or an authorization token.
function compilePlan(params) {
  const p = JSON.parse(params.plan_input);
  const fail = message => { throw new Error(message); };
  const object = (v, keys, name) => {
    if (!v || Array.isArray(v) || typeof v !== 'object'
      || Object.keys(v).some(k => !keys.includes(k))) fail('INVALID_' + name);
  };
  object(p, ['scenario','revision','reviewed','reference_at','window','available_windows','buffers','alternatives','task'], 'PLAN');
  if (!['alternatives','deadline','fixed_event'].includes(p.scenario)) fail('INVALID_SCENARIO');
  if (!Number.isSafeInteger(p.revision) || p.revision < 1) fail('INVALID_REVISION');
  if (typeof p.reviewed !== 'boolean') fail('INVALID_REVIEW');
  const time = v => {
    if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$/.test(v)
      || !Number.isFinite(Date.parse(v))
      || new Date(Date.parse(v)+8*3600000).toISOString().slice(0,19) !== v.slice(0,19)) fail('INVALID_TIME');
    return Date.parse(v);
  };
  const interval = w => {
    object(w, ['start','end'], 'WINDOW');
    const a=time(w.start), b=time(w.end);
    if (a >= b) fail('INVALID_INTERVAL');
    return [a,b];
  };
  const now = time(p.reference_at);
  const [begin,end] = interval(p.window);
  if (end-begin > 31*86400000) fail('WINDOW_TOO_LONG');
  object(p.buffers,['before_minutes','after_minutes'],'BUFFERS');
  for (const k of ['before_minutes','after_minutes']) {
    if (!Number.isSafeInteger(p.buffers[k]) || p.buffers[k]<0 || p.buffers[k]>1440) fail('INVALID_BUFFERS');
  }
  if (!Array.isArray(p.available_windows) || p.available_windows.length>20) fail('INVALID_AVAILABLE_WINDOWS');
  const restricted=p.available_windows.map(interval).sort((a,b)=>a[0]-b[0]);
  if (restricted.some(([a,b],i)=>a<begin || b>end || (i && a<restricted[i-1][1]))) fail('INVALID_AVAILABLE_WINDOWS');
  const checks=[], needs=[];
  const add = (optionId,title,query) => checks.push({option_id:optionId,title,query_json:JSON.stringify(query)});
  const base = {window:p.window,allow_split:false,buffers:p.buffers};
  if (!p.reviewed) needs.push('source_review');
  if (p.scenario==='deadline') {
    if (p.alternatives!==null) fail('DEADLINE_HAS_ALTERNATIVES');
    object(p.task,['title','due_at','estimated_minutes','earliest_start'],'TASK');
    if (typeof p.task.title!=='string' || !p.task.title.trim()) fail('INVALID_TITLE');
    const t=p.task;
    if (t.due_at===null) needs.push('due_time'); else if(time(t.due_at)<=now) needs.push('past_deadline');
    if (t.estimated_minutes===null) needs.push('estimated_minutes');
    else if (!Number.isSafeInteger(t.estimated_minutes) || t.estimated_minutes<=0 || t.estimated_minutes>1440) fail('INVALID_DURATION');
    if(t.earliest_start===null) needs.push('earliest_start');
    else if(time(t.earliest_start)<now) needs.push('earliest_start_before_reference');
    if (!needs.length) {
      const windows=p.available_windows.length?p.available_windows:[p.window];
      for (const [i,window] of windows.entries()) {
        add('deadline-window-'+(i+1),t.title,{...base,window,kind:'deadline_feasibility',event:null,
          due:{at:t.due_at,date:null,precision:'datetime'},estimated_minutes:t.estimated_minutes,earliest_start:t.earliest_start});
      }
    }
  } else {
    if (p.task!==null || !Array.isArray(p.alternatives) || !p.alternatives.length
      || p.alternatives.length>20 || (p.scenario==='fixed_event' && p.alternatives.length!==1)) fail('INVALID_ALTERNATIVES');
    if(p.available_windows.length) fail('EVENT_WINDOWS_NOT_SUPPORTED');
    // The existing B event checker ignores buffers. Do not advertise that check.
    const unsupportedBuffer=p.buffers.before_minutes>0 || p.buffers.after_minutes>0;
    if(unsupportedBuffer) needs.push('event_buffer_not_supported');
    const ids=new Set();
    for (const option of p.alternatives) {
      object(option,['option_id','title','start','end'],'OPTION');
      if(typeof option.option_id!=='string' || !option.option_id || ids.has(option.option_id)) fail('INVALID_OPTION_ID');
      ids.add(option.option_id);
      if(typeof option.title!=='string' || !option.title.trim()) fail('INVALID_TITLE');
      if(option.start===null || option.end===null) {needs.push(option.option_id+':event_time');continue;}
      const [a,b]=interval({start:option.start,end:option.end});
      if(a<begin || b>end) fail('EVENT_OUTSIDE_WINDOW');
      if(a<now) {needs.push(option.option_id+':past_event');continue;}
      if(p.reviewed && !unsupportedBuffer) add(option.option_id,option.title,{...base,kind:'event_conflict',event:{start:option.start,end:option.end,date:null,precision:'datetime'},due:null,estimated_minutes:null,earliest_start:null});
    }
  }
  // FNV fingerprint identifies edits, not users. Never use it as an auth token.
  const canonical=JSON.stringify(p);
  let h=2166136261;
  for(let i=0;i<canonical.length;i++){h^=canonical.charCodeAt(i);h=Math.imul(h,16777619);}
  return {result:{workflow_version:'notice-schedule-prepare-v1',scenario:p.scenario,revision:p.revision,
    menu_id:p.revision+'-'+(h>>>0).toString(16),status:checks.length?'checks_required':'clarification_required',
    needs_confirmation:[...new Set(needs)],checks,saved:false,time_check_performed:false,
    next:'Call check_my_demo_time once per checks entry; only real tool results are recommendations.',
    save_capability:'not_connected_for_arbitrary_notice'}};
}

// Platform can otherwise abort the entire Agent run on a code exception.
// An invalid request is a recoverable, explicit failure, never a recommendation.
function handler(params) {
  try { return compilePlan(params); }
  catch (error) {
    return {result:{workflow_version:'notice-schedule-prepare-v1',status:'invalid_input',
      error_code:error instanceof SyntaxError?'INVALID_JSON':String(error.message),
      checks:[],needs_confirmation:['correct_plan_input'],saved:false,time_check_performed:false,
      save_capability:'not_connected_for_arbitrary_notice'}};
  }
}
