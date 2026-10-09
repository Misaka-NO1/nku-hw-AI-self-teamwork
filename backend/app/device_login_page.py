"""Static same-origin device-binding UI; no third-party SDK or credential URLs."""


def device_login_html(nonce: str) -> str:
    return PAGE.replace("__NONCE__", nonce)


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>绑定我的浏览器 · 南开校园助手</title>
<style nonce="__NONCE__">
*{box-sizing:border-box}body{margin:0;background:#f4f7f9;color:#193a43;font:17px/1.65 system-ui,sans-serif}
main{max-width:700px;margin:5vh auto;padding:28px}section{background:white;border:1px solid #d9e5e7;border-radius:20px;padding:28px;margin:24px 0}
h1{font-size:30px;margin:10px 0}h2{font-size:22px}button,a{font:inherit}button{border:1px solid #cadbdc;border-radius:12px;padding:12px 20px;background:#fff;color:#193a43;cursor:pointer}
button.primary{background:#315f6d;color:white}button:disabled{opacity:.5;cursor:wait}input{width:100%;font:20px ui-monospace,monospace;padding:14px;border:1px solid #c2d5d8;border-radius:12px;margin:10px 0}
code{display:block;font-size:27px;letter-spacing:2px;overflow-wrap:anywhere;margin:20px 0;padding:15px;background:#f1f5f6;border-radius:12px}
.muted{color:#657e84;font-size:15px}.warning{padding:16px;background:#fff7e8;border-radius:12px}#message{white-space:pre-wrap}a{color:#285c72}label{display:block}label.check{display:flex;gap:12px;align-items:start;margin:20px 0}input[type=checkbox]{width:auto;flex:none;margin-top:8px}[hidden]{display:none!important}
</style><main><a href="/tools/timetable">← 返回课表</a><h1>绑定我的浏览器</h1>
<p>第一次绑定后，这个浏览器可直接打开你的课表和待办日历。数据仍属于各自账号，不会共享。</p>
<p class="warning">这不是 GeniOS 自动识别登录。首次需要已有登录设备确认；如果没有已登录设备，先完成一次<a href="/tools/login">本人账号登录</a>。无需管理员权限。</p>
<p id="message" role="status">正在检查当前浏览器登录状态…</p>
<section id="new" hidden><h2>在新浏览器上获取绑定码</h2><p>点击获取后，在你已经登录工具站的设备打开本页，输入这里的绑定码。</p>
<button id="start" class="primary">获取 5 分钟绑定码</button><code id="code" hidden></code><p id="expiry" class="muted"></p>
<button id="claim" hidden>已确认，检查绑定结果</button></section>
<section id="source" hidden><h2>用当前本人账号确认新设备</h2><p id="account"></p><label for="input">输入你自己新浏览器显示的绑定码</label><input id="input" maxlength="15" autocomplete="off" spellcheck="false" placeholder="DC-XXXXXXXXXXXX">
<button id="review">核对绑定</button><div id="consent" hidden><p class="warning">只确认你自己设备上的码。确认后，新浏览器可读取及操作当前账号的课表和日历。原登录退出或撤销后，绑定也会失效。</p>
<label class="check"><input id="checked" type="checkbox"><span>我已核对，这是我的新浏览器；允许它访问当前本人账号。</span></label><button id="approve" class="primary">确认绑定这台浏览器</button></div></section>
<p class="muted">请勿使用别人发来的绑定码，也不要在聊天中粘贴长期登录凭据。绑定码本身不能登录，过期后请重新获取。</p>
<script nonce="__NONCE__">
const el=id=>document.getElementById(id);let csrf='',receipt='',reviewCode='';
const message=text=>{el('message').textContent=text;};
async function api(op,value){const r=await fetch('/api/v1/auth/devices/'+op,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Campus-Device':'1',...(csrf?{'X-CSRF-Token':csrf}:{})},body:JSON.stringify(value)});const j=await r.json();if(!r.ok||!j.ok)throw Error(j.error?.message||j.error?.code||'操作失败，请检查登录状态或重新获取绑定码。');return j.data;}
async function action(button,run){button.disabled=true;try{await run();}catch(e){message(e.message);}finally{button.disabled=false;}}
el('start').onclick=()=>action(el('start'),async()=>{const v=await api('start',{});el('code').textContent=v.user_code;el('code').hidden=false;el('expiry').textContent='有效至 '+new Date(v.expires_epoch*1000).toLocaleTimeString('zh-CN');el('claim').hidden=false;message('请在已登录设备核对并确认，然后回来检查绑定结果。');});
el('claim').onclick=()=>action(el('claim'),async()=>{const v=await api('claim',{});if(v.status==='pending'){message('还未确认，请先在原已登录设备完成确认。');return;}message('绑定成功，可以打开自己的课表和日历。');el('new').hidden=true;const p=document.createElement('p');for(const [name,path]of[['打开课表','/tools/timetable'],['打开待办日历','/tools/calendar']]){const a=document.createElement('a');a.textContent=name;a.href=path;p.append(a,document.createTextNode('　'));}el('message').after(p);});
el('input').oninput=()=>{receipt='';reviewCode='';el('consent').hidden=true;el('checked').checked=false;};
el('review').onclick=()=>action(el('review'),async()=>{const code=el('input').value.trim().toUpperCase();const v=await api('review',{user_code:code});receipt=v.review_receipt;reviewCode=code;el('consent').hidden=false;el('checked').checked=false;message('已核对 '+code+'。请在 60 秒内明确确认；尚未授权新浏览器。');});
el('approve').onclick=()=>action(el('approve'),async()=>{if(!el('checked').checked||!receipt||el('input').value.trim().toUpperCase()!==reviewCode)throw Error('请先核对绑定码并勾选本人设备确认。');await api('approve',{user_code:reviewCode,review_receipt:receipt,confirm_device:true});receipt='';el('consent').hidden=true;message('已批准。请回到新浏览器点击“检查绑定结果”。');});
(async()=>{try{const r=await fetch('/api/v1/auth/cloudbase/browser-session',{credentials:'same-origin',headers:{'X-Campus-Session-Read':'1'}});const j=await r.json();if(r.ok&&j.ok){csrf=j.data.csrf_token;el('source').hidden=false;el('account').textContent='当前已登录工具站账号，工作区末尾：'+j.data.workspace_ref.slice(-8)+'。请确认这是你要绑定的账号。';message('当前浏览器已登录，可确认你自己的新设备。');}else{el('new').hidden=false;message('当前浏览器尚未登录。可从已有登录设备绑定；已有过期登录时，请先退出或重新登录。');}}catch{message('暂时无法检查登录，请刷新后重试。');}})();
</script></main></html>'''
