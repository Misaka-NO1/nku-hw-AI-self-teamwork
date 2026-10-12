import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "../../shared/api/client";
import "./identityOnboarding.css";

interface IdentityState {
  deviceCode: string | null;
  hasSpace: boolean;
  agentLinked: boolean;
  spaceLabel: string | null;
  schoolIdentityVerified: false;
}
const DEVICE = "/api/v1/auth/agent-device/";
const deviceHeaders = { "X-Campus-Device": "1" };
const AGENT = "https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg";
function checkedIdentity(value: IdentityState): IdentityState {
  if (typeof value?.hasSpace !== "boolean" || typeof value.agentLinked !== "boolean" || value.schoolIdentityVerified !== false
    || (value.deviceCode !== null && (typeof value.deviceCode !== "string" || !/^DEV-[A-Z2-7]{26}$/.test(value.deviceCode)))
    || (value.hasSpace ? typeof value.spaceLabel !== "string" || !/^SPACE-[A-F0-9]{12}$/.test(value.spaceLabel) : value.spaceLabel !== null)
    || (value.agentLinked && (!value.hasSpace || !value.deviceCode))) throw new Error("身份状态无法核实，不能进入空间。");
  return value;
}
const failure = (error: unknown) => error instanceof ApiError
  ? error.code === "AUTH_REQUIRED"
    ? "尚未核实工具站账号。没有新建空间；请用原 Agent 授权绑定设备，或使用下方本人账号登录。"
    : error.code === "FORBIDDEN"
      ? `绑定被拒绝：当前授权或空间归属未通过核验。不会覆盖或合并空间。请保留原浏览器，不要再次创建账号；请求编号：${error.requestId ?? "未提供"}。`
      : `身份核验失败：${error.code}（${error.requestId ?? "无请求编号"}）。不会覆盖或合并空间。`
  : error instanceof Error ? error.message : "身份核验失败，未切换空间。";

export default function IdentityOnboarding({ checking, blocked, consentReturn, destination, resumeVisitor, sessionIdentity }: {
  checking: boolean; blocked: boolean;
  consentReturn: string | null; destination: string;
  resumeVisitor: () => Promise<void>; sessionIdentity: string | null;
}) {
  const [identity, setIdentity] = useState<IdentityState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [retry, setRetry] = useState(0);
  const epoch = useRef(0), lock = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++; }; }, []);
  useEffect(() => {
    const current = ++epoch.current;
    setIdentity(null); setError(""); setMessage("");
    if (checking || blocked) return;
    const controller = new AbortController();
    // Only register a public locator. Never enroll/claim/approve on mount.
    void apiClient.post(DEVICE + "start", {}, { headers: deviceHeaders, signal: controller.signal })
      .then(() => apiClient.post<IdentityState>(DEVICE + "state", {}, { headers: deviceHeaders, signal: controller.signal }))
      .then(value => { if (mounted.current && epoch.current === current) setIdentity(checkedIdentity(value)); })
      .catch(reason => { if (mounted.current && epoch.current === current) setError(failure(reason)); });
    return () => { controller.abort(); epoch.current++; };
  }, [checking, blocked, retry, sessionIdentity]);
  async function act(action: () => Promise<void>) {
    if (lock.current || checking || blocked || !identity) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    const current = epoch.current;
    try { await action(); } catch (reason) {
      if (mounted.current && epoch.current === current) {
        setError(failure(reason)); setIdentity(previous => previous ? { ...previous, agentLinked: false } : null);
      }
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function refresh(expectedSpace = identity?.spaceLabel) {
    const current = epoch.current;
    const next = checkedIdentity(await apiClient.post<IdentityState>(DEVICE + "state", {}, { headers: deviceHeaders }));
    if (expectedSpace && next.spaceLabel !== expectedSpace) throw new Error("当前浏览器身份已改变。请重新核验，不会自动进入另一空间。");
    if (!mounted.current || current !== epoch.current) return;
    setIdentity(next);
    setMessage(next.agentLinked ? "已核实 Agent 授权身份，并接入该账号的原私有空间。"
      : next.hasSpace ? "原空间已恢复，请在 Agent 完成本人插件授权和设备绑定，再核验。"
      : "尚未收到可信的账号授权，未新建任何空间。请在原 Agent 会话中完成设备绑定；学校登录本身不能核实工具站身份。");
  }
  async function checkBinding() {
    const current = epoch.current, priorSpace = identity?.spaceLabel;
    await apiClient.post(DEVICE + "claim", {}, { headers: deviceHeaders });
    if (mounted.current && current === epoch.current) await refresh(priorSpace);
  }
  async function restoreKnownBrowser() {
    const current = epoch.current, priorSpace = identity?.spaceLabel;
    await resumeVisitor(); // Server/SQL restore known private proof only; no enrollment fallback.
    if (mounted.current && current === epoch.current) await refresh(priorSpace);
  }
  const active = !checking && !blocked ? identity : null;
  const canEnter = !!active?.agentLinked && !busy && !error;
  const command = active?.deviceCode ? "确认将我的这台浏览器绑定到你当前授权的账号，设备码：" + active.deviceCode : "";
  return <div className="identity-onboarding">
    <p className="identity-intro">先核验本人授权身份 → 接入账号原有空间 → 确认设备绑定。新浏览器、无痕窗口不等于新账号，未核实身份不新建空间。</p>
    <div className="identity-summary" role="status">
      {blocked ? "当前无法安全核验身份，已停止接入；没有新建或切换空间。" : checking ? "正在核验浏览器身份，完成前不能进入或切换空间。" : !active ? error ? "身份核验未完成，请查看下面的提示。" : "正在核验空间与设备…" : <>
        <strong>{canEnter ? "已核实授权身份 · 可使用原空间" : active.hasSpace ? "检测到原空间 · 待核验 Agent 关联" : "身份待核验 · 未创建空间"}</strong>
        {active.spaceLabel && <p>空间标识：<code>{active.spaceLabel}</code>（只作核对，不是登录密钥）</p>}
        <p>设备码：<code>{active.deviceCode ?? "尚未生成"}</code></p>
      </>}
    </div>
    <div className="identity-feedback" aria-live="polite" aria-atomic="true">
      {busy && <p role="status">正在核验或处理，请稍候；完成前不会进入工具站。</p>}
      {!busy && message && <p role="status">{message}</p>}
      {error && <div role="alert"><p>{error}</p><button disabled={checking || blocked || busy} onClick={() => setRetry(value => value + 1)}>重新核验当前浏览器</button></div>}
    </div>
    <ol className="identity-steps">
      <li><h2>1. 核验本人身份</h2>
        <p>在你原来已授权的 Agent 聊天中发送下面的绑定请求。服务端以实际插件授权账号核验，不以学校登录、昵称或设备码猜测身份。</p>
        {!active?.agentLinked && <><p className="identity-command">{command || "身份核验完成后显示设备绑定请求。"}</p>
          <div className="identity-actions"><button disabled={busy || !command} onClick={() => void act(async () => {
            await navigator.clipboard.writeText(command); setMessage("绑定请求已复制，请发到你原有的 Agent 聊天框。");
          })}>复制设备码绑定请求</button><a href={AGENT} target="_blank" rel="noopener noreferrer">打开南开 Agent ↗</a></div>
        </>}
        {consentReturn && active?.hasSpace && <p><a href={consentReturn}>继续前往原空间的插件授权页，由我决定是否允许 →</a></p>}
        {consentReturn && active && !active.hasSpace && <p>请先接入原空间，再返回此页完成授权。不会在新浏览器建立另一个身份来替换原授权。</p>}
        <p className="identity-boundary">真正首次使用、没有任何已验证工具站身份时，请使用支持的本人账号登录；目前没有可信校园账号接口，不能匿名认定你是新用户并创建账号。</p>
      </li>
      <li><h2>2. 接入原私有空间</h2>
        <p>{active?.hasSpace ? "已找到本浏览器原空间，课表和日历保留，不重复创建。" : "绑定后接入授权账号已有的空间，不新建另一个空白空间。"}</p>
        <button disabled={!active || busy} onClick={() => void act(checkBinding)}>{busy ? "正在处理…" : "核验身份并接入空间"}</button>
        {!active?.hasSpace && <details><summary>本浏览器以前用过，但已退出？</summary>
          <p>仅凭本浏览器保留的私密身份恢复原空间。无痕浏览器或未知身份会被拒绝，不创建新空间。</p>
          <button disabled={!active || busy} onClick={() => void act(restoreKnownBrowser)}>恢复本浏览器原有身份</button>
        </details>}
      </li>
      <li aria-disabled={!canEnter}><h2>3. 进入本人课表与日历</h2>
        {canEnter ? <a className="identity-enter" href={destination}>身份已核验，进入我的工具站 →</a> : <p>核验授权身份、空间归属和设备绑定一致后，才出现进入按钮。</p>}
      </li>
    </ol>
    <p className="identity-boundary">一个服务端授权账号对应一个私有空间，不同设备可复用。公开设备码不是密码。身份不一致时拒绝接入，不覆盖、合并或删除空间。</p>
    <p className="identity-boundary">学校登录不等于工具站实名认证。清除本站全部浏览器数据可能丢失访客身份；没有其他已绑定设备时无法找回。退出或撤销授权后须重新本人授权。</p>
  </div>;
}
