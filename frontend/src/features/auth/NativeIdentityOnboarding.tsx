import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "../../shared/api/client";
import "./identityOnboarding.css";

const ROOT = "/api/v1/auth/genios/";
const HEADERS = { "X-Campus-Native": "1" };
const AGENT = "https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg";
const STAGES = ["identity_pending", "first_use_confirmation", "legacy_authorization_required", "existing_space", "browser_authorized", "bound"] as const;
type Stage = typeof STAGES[number];
interface NativeState { status: Stage; hasSpace: boolean; spaceLabel: string | null; created: boolean }
function checked(value: NativeState): NativeState {
  if (!value || !STAGES.includes(value.status) || typeof value.hasSpace !== "boolean" || typeof value.created !== "boolean"
    || (value.hasSpace ? typeof value.spaceLabel !== "string" || !/^SPACE-[A-F0-9]{12}$/.test(value.spaceLabel) : value.spaceLabel !== null)
    || (["existing_space", "browser_authorized", "bound"].includes(value.status) && !value.hasSpace)) {
    throw new Error("平台身份状态无法核实，未进入或切换空间。");
  }
  return value;
}
const errorText = (error: unknown) => error instanceof ApiError
  ? `核验未完成：${error.code}（请求编号 ${error.requestId ?? "未提供"}）。未进入或切换空间；身份不一致时不会覆盖或合并数据。`
  : error instanceof Error ? error.message : "无法核验身份，请重试。";

export default function NativeIdentityOnboarding({ checking, blocked, destination, consentReturn }: {
  checking: boolean; blocked: boolean; destination: string; consentReturn: string | null;
}) {
  const [code, setCode] = useState("");
  const [state, setState] = useState<NativeState | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [retry, setRetry] = useState(0);
  const lock = useRef(false), epoch = useRef(0), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; epoch.current++; }; }, []);
  useEffect(() => {
    const current = ++epoch.current;
    setState(null); setError(""); setMessage(""); setCode("");
    if (checking || blocked) return;
    const controller = new AbortController();
    void apiClient.post<{deviceCode:string}>("/api/v1/auth/agent-device/start", {}, {
      headers: { "X-Campus-Device": "1" }, signal: controller.signal,
    }).then(async result => {
      if (!/^DEV-[A-Z2-7]{26}$/.test(result.deviceCode)) throw new Error("设备码无法核实。");
      const identity = checked(await apiClient.post<NativeState>(ROOT + "state", {}, {headers:HEADERS,signal:controller.signal}));
      if (mounted.current && epoch.current === current) { setCode(result.deviceCode); setState(identity); }
    }).catch(reason => { if (mounted.current && current === epoch.current) setError(errorText(reason)); });
    return () => { controller.abort(); epoch.current++; };
  }, [checking, blocked, retry]);
  const active = !checking && !blocked ? state : null;
  async function act(action: (current: number) => Promise<void>) {
    if (lock.current || !active || !code) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    const current = epoch.current;
    try { await action(current); } catch (reason) {
      if (mounted.current && current === epoch.current) { setError(errorText(reason)); setState(null); }
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function recheck(current: number) {
    const before = active?.spaceLabel;
    // Explicit click only. Mount/refresh never creates an account or claims login.
    await apiClient.post(ROOT + "claim", {}, {headers:HEADERS});
    const next = checked(await apiClient.post<NativeState>(ROOT + "state", {}, {headers:HEADERS}));
    if (before && next.spaceLabel !== before) throw new Error("空间归属发生变化，已停止进入；不会切换到另一个空间。");
    if (mounted.current && current === epoch.current) {
      setState(next);
      setMessage(next.status === "bound" ? "绑定成功，可以进入工具站。"
        : next.status === "identity_pending" ? "尚未收到平台身份核验；未创建空间。请将核验请求发给 Agent。"
          : next.status === "existing_space" ? "已找到该平台账号原空间，只需确认绑定这台浏览器，不会重复创建。"
            : next.status === "legacy_authorization_required" ? "检测到原工具站账号，请通过原插件授权关联；没有创建新空间。"
              : "账号已核验，请完成下一步确认。");
    }
  }
  const lookup = `核验我的 GeniOS 平台账号并查找原私有空间，不创建空间，设备码：${code}`;
  const bind = `确认将我的这台浏览器绑定到当前 GeniOS 平台账号的原私有空间，不重复创建，设备码：${code}`;
  const create = `我确认此前没有工具站私有空间，免注册创建我的唯一空白空间并绑定本浏览器；已有空间则只复用，设备码：${code}`;
  const adopt = `确认通过我原有的插件授权关联当前 GeniOS 平台账号与原私有空间并绑定浏览器，不创建或合并空间，设备码：${code}`;
  const command = active?.status === "identity_pending" ? lookup
    : active?.status === "first_use_confirmation" ? create
      : active?.status === "legacy_authorization_required" ? adopt : bind;
  async function copy(value: string, current: number) {
    await navigator.clipboard.writeText(value);
    if (mounted.current && current === epoch.current) setMessage("已复制。请粘贴发送到自己的 Agent，等它回复后回到本页检查。复制不会创建或绑定空间。");
  }
  const bound = active?.status === "bound";
  const verified = !!active && active.status !== "identity_pending";
  const verifyLabel = "我已发送，检查核验结果";
  const bindingLabel = "Agent 已确认，检查绑定结果";
  return <div className="identity-onboarding">
    {!bound && <><ol className="identity-progress" aria-label="绑定进度">
      <li aria-current={!verified ? "step" : undefined} data-complete={verified}>1. 核验账号{verified && " ✓"}</li>
      <li aria-current={verified ? "step" : undefined}>2. {active?.status === "first_use_confirmation" ? "创建并绑定" : "绑定浏览器"}</li>
      <li>3. 进入工具站</li>
    </ol><p className="identity-intro">每一步：复制请求 → 发给自己的 Agent → 等它回复 → 回到这里检查。</p></>}
    <div className="identity-summary" role="status">
      {checking || blocked ? "身份正在核验或暂不可用，未创建或切换空间。" : !active ? "身份核验未完成，请重试。" : <>
        <strong>{bound ? "本浏览器已绑定 · 使用账号原空间" : active.hasSpace ? "已找到原空间 · 下一步绑定浏览器"
          : active.status === "identity_pending" ? "等待平台账号核验 · 不可创建空间" : "身份已核验 · 等待本人确认"}</strong>
        {bound ? <details><summary>查看设备码与空间标识</summary><p>设备码：<code>{code}</code></p>
          <p>空间标识：<code>{active.spaceLabel}</code></p></details>
          : <p>当前浏览器设备码：<code>{code}</code></p>}
      </>}
    </div>
    <div className="identity-feedback" aria-live="polite" aria-atomic="true">
      {busy && <p role="status">正在检查，请稍候…</p>}
      {message && !busy && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      {!active && !checking && !blocked && <button disabled={busy} onClick={() => setRetry(value => value + 1)}>重新核验当前浏览器</button>}
    </div>
    <ol className="identity-steps">
      {!bound && (!verified ? <li><h2>1. 核验账号</h2>
        <p>先确认你在 GeniOS 的账号，查找已有空间；这一步不会创建或绑定。</p>
        <div className="identity-actions"><button className="identity-primary" disabled={!active || busy || !code} onClick={() => void act(current => copy(lookup, current))}>复制核验请求</button>
          <a href={AGENT} target="_blank" rel="noopener noreferrer">打开南开 Agent ↗</a></div>
        <p className="identity-check-hint">发送后等 Agent 回复，再点击下面的检查按钮。它只查询结果，不代替发送。</p>
        <button disabled={!active || busy} onClick={() => void act(recheck)}>{busy ? "正在检查…" : verifyLabel}</button>
      </li> : <li><h2>2. {active?.status === "first_use_confirmation" ? "创建并绑定" : active?.status === "legacy_authorization_required" ? "关联原空间并绑定" : "绑定当前浏览器"}</h2>
        {active?.status === "browser_authorized" ? <p>已收到 Agent 的绑定确认。点击下方按钮，完成这台浏览器的登录。</p>
          : active?.status === "first_use_confirmation" ? <p>未找到已关联空间。第一次使用可创建空白空间；以前用过请关联原空间，勿重复创建。</p>
          : active?.status === "legacy_authorization_required" ? <p>请用原插件授权关联已有空间，保留原课表和日历。</p>
            : <p>本账号已有空间。这一步仅绑定当前浏览器，不会新建空间。</p>}
        {active?.status !== "browser_authorized" && <><div className="identity-actions"><button className="identity-primary" disabled={busy || !code} onClick={() => void act(current => copy(command, current))}>
          {active?.status === "first_use_confirmation" ? "首次使用，复制创建确认" : active?.status === "legacy_authorization_required" ? "复制原空间关联确认" : "复制浏览器绑定确认"}</button>
          <a href={AGENT} target="_blank" rel="noopener noreferrer">打开南开 Agent ↗</a></div>
        {active?.status === "first_use_confirmation" && <p><button disabled={busy} onClick={() => void act(current => copy(adopt, current))}>以前用过，复制原空间关联请求</button></p>}
        <p className="identity-check-hint">把确认请求发给 Agent。等它回复绑定成功，再回来检查。</p></>}
        <button disabled={!active || busy} onClick={() => void act(recheck)}>{busy ? "正在检查…" : active?.status === "browser_authorized" ? "完成浏览器绑定" : bindingLabel}</button>
      </li>)}
      <li aria-disabled={!bound}><h2>{bound ? "绑定完成" : "3. 进入工具站"}</h2>
        {bound && !busy && !error ? <><a className="identity-enter" href={destination}>进入我的工具站 →</a>
          {consentReturn && <p><a href={consentReturn}>返回插件授权页，由我决定是否同意 →</a></p>}
          <p>Agent 读取和保存数据仍需你本人同意插件授权。</p>
          <details><summary>重新检查绑定状态</summary><button disabled={busy} onClick={() => void act(recheck)}>检查当前绑定状态</button></details>
        </> : <p>完成浏览器绑定后，即可打开自己的课表和日历。</p>}
      </li>
    </ol>
    <p className="identity-boundary">一个账号一个空间，换浏览器不新建。设备码只标识浏览器，不是密码。</p>
  </div>;
}
