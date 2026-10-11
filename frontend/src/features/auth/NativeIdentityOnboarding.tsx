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
      setMessage(next.status === "bound" ? "已绑定本浏览器并登录账号原空间。课表和日历的数据读写仍须本人插件授权。"
        : next.status === "identity_pending" ? "尚未收到平台身份核验；未创建空间。请将核验请求发给 Agent。"
          : next.status === "existing_space" ? "已找到该平台账号原空间，只需确认绑定这台浏览器，不会重复创建。"
            : next.status === "legacy_authorization_required" ? "检测到原工具站账号，请通过原插件授权关联；没有创建新空间。"
              : "身份已核验。尚未创建或领取空间，请按下方下一步本人确认。");
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
    if (mounted.current && current === epoch.current) setMessage("请求已复制。请发到自己的 Agent 聊天框，再回到本页点击检查。复制本身不会创建空间。");
  }
  return <div className="identity-onboarding">
    <p className="identity-intro">核验 GeniOS 账号 → 查找或首次确认创建唯一空间 → 绑定本浏览器。新浏览器、无痕窗口不等于新账号。</p>
    <div className="identity-summary" role="status">
      {checking || blocked ? "身份正在核验或暂不可用，未创建或切换空间。" : !active ? "身份核验未完成，请重试。" : <>
        <strong>{active.status === "bound" ? "本浏览器已登录 · 使用账号原空间" : active.hasSpace ? "已找到账号原空间 · 不重复创建"
          : active.status === "identity_pending" ? "等待平台账号核验 · 不可创建空间" : "身份已核验 · 等待本人确认"}</strong>
        {active.spaceLabel && <p>空间标识：<code>{active.spaceLabel}</code>（不是登录密钥）</p>}
        <p>我的设备码：<code>{code}</code></p>
      </>}
    </div>
    <div className="identity-feedback" aria-live="polite" aria-atomic="true">
      {busy && <p role="status">正在核验或领取登录态，请稍候；完成前不会进入工具站。</p>}
      {message && !busy && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      {!active && !checking && !blocked && <button disabled={busy} onClick={() => setRetry(value => value + 1)}>重新核验当前浏览器</button>}
    </div>
    <ol className="identity-steps">
      <li><h2>1. 核验我的 GeniOS 账号</h2><p>Agent 将固定平台身份传给服务端；不按学校登录状态、昵称或设备码猜测账号。核验本身不建空间。</p>
        {active?.status === "identity_pending" && <p className="identity-command">{lookup}</p>}
        <a href={AGENT} target="_blank" rel="noopener noreferrer">打开南开 Agent ↗</a>
      </li>
      <li><h2>2. 使用账号唯一私有空间</h2>
        {active?.status === "identity_pending" ? <p>请先完成平台账号核验，之后才显示创建或绑定步骤。</p>
          : active?.status === "first_use_confirmation" ? <><p>尚未建立此平台账号的空间映射。若以前用过工具站，请先关联原账号，不要新建；只有真正首次使用才确认创建空白空间。</p>
            <button disabled={busy} onClick={() => void act(current => copy(adopt, current))}>我以前用过，关联原空间</button></>
            : active?.status === "legacy_authorization_required" ? <p>检测到旧账号。必须使用原插件授权核验关联，不会用新空间替换旧课表和日历。</p>
              : <p>已有账号只复用原空间。设备码不同不会产生另一个账号或空间。</p>}
        {active && active.status !== "bound" && <><p className="identity-command">{command}</p>
          <button disabled={busy || !code} onClick={() => void act(current => copy(command, current))}>
            {active.status === "identity_pending" ? "复制平台身份核验请求" : active.status === "first_use_confirmation"
              ? "首次使用：复制免注册创建确认" : active.status === "legacy_authorization_required" ? "复制原账号关联请求" : "复制原空间设备绑定确认"}</button></>}
        <p><button disabled={!active || busy} onClick={() => void act(recheck)}>{busy ? "正在处理…" : "已在 Agent 确认，检查绑定结果"}</button></p>
      </li>
      <li><h2>3. 进入我的课表与日历</h2>
        {active?.status === "bound" && !busy && !error ? <><a className="identity-enter" href={destination}>已绑定并登录，进入我的工具站 →</a>
          {consentReturn && <p><a href={consentReturn}>返回插件授权页，由我决定是否同意 →</a></p>}
          <p>浏览器登录不是自动授予 Agent 数据读写权限；插件授权仍由本人确认。</p></> : <p>绑定成功后显示进入按钮。没有成功提示时，不会当作已登录。</p>}
      </li>
    </ol>
    <p className="identity-boundary">一个平台账号只对应一个私有空间；不同浏览器可以复用。公开设备码不是密码；退出或撤销后须重新确认，不覆盖、合并或删除已有数据。</p>
  </div>;
}
