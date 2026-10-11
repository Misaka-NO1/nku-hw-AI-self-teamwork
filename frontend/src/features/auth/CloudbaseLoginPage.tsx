import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "../../shared/api/client";
import type { DemoSession } from "../tasks/api";
import { clearDemoSession, writeDemoSession } from "../tasks/sessionCache";
import { oauthReturnPath } from "./oauthReturn";
import { toolReviewReturnPath } from "./toolReviewReturn";
import { useBrowserSession } from "./useBrowserSession";
import { cloudAuthFailure } from "./cloudAuthFailure";
import IdentityOnboarding from "./IdentityOnboarding";
import NativeIdentityOnboarding from "./NativeIdentityOnboarding";

// Fixed official npm version, bundled and loaded only on this closed pilot page.
// No service_role/MCP key; password goes to CloudBase SDK, not our backend/Agent.
interface CloudAuth {
  signInWithPassword(input: { username: string; password: string }): Promise<{
    data?: { session?: { access_token?: string } }; error?: unknown;
  }>;
  signOut(): Promise<{ error?: unknown }>;
}
interface CloudSdk { init(input: { env: string; region: string; persistence: "none"; debug: false;
  auth: { detectSessionInUrl: false } }): { auth: CloudAuth | (() => CloudAuth) } }
interface PilotConfig { envId: string; region: string; persistentAuthorization?: boolean; deviceLoginEnabled?: boolean; agentDeviceBindingEnabled?: boolean; visitorEnabled?: boolean; visitorIdentityFirst?: boolean; geniosNativeIdentityEnabled?: boolean }
interface PilotSession extends DemoSession { datasetKind: "demo"; personalUploads: false; agentPaired: false }
async function loadSdk(): Promise<CloudSdk> {
  const sdk = await import("@cloudbase/js-sdk");
  return sdk.default as unknown as CloudSdk;
}

export default function CloudbaseLoginPage() {
  const identityPilot = import.meta.env.VITE_IDENTITY_PILOT === "true";
  const browserSession = useBrowserSession(identityPilot);
  const { session, setSession, checking, recoveryError } = browserSession;
  const [config, setConfig] = useState<PilotConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const auth = useRef<CloudAuth | null>(null);
  const lock = useRef(false);
  const username = useRef<HTMLInputElement>(null);
  const password = useRef<HTMLInputElement>(null);
  const reviewReturn = toolReviewReturnPath(window.location.search, window.location.origin);
  const consentReturn = oauthReturnPath(window.location.search, window.location.origin);
  const unified = !!config?.agentDeviceBindingEnabled && !!config?.visitorEnabled;
  useEffect(() => {
    let active = true;
    apiClient.get<PilotConfig>("/api/v1/auth/cloudbase/config").then(value => {
      if (active) setConfig(value);
    }).catch(() => { if (active) setError("本人账号登录暂不可用，不会开放个人数据。"); });
    return () => { active = false; };
  }, []);
  async function perform(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (e) {
      setError(e instanceof ApiError ? `${e.message}（${e.code} · ${e.requestId ?? "无请求编号"}）`
        : e instanceof Error ? e.message : "登录失败，请重试");
    } finally { lock.current = false; setBusy(false); }
  }
  async function prepare() {
    if (!config) return;
    const sdk = await loadSdk();
    const app = sdk.init({ env: config.envId, region: config.region, persistence: "none", debug: false,
      auth: { detectSessionInUrl: false } });
    auth.current = typeof app.auth === "function" ? app.auth() : app.auth;
    if (typeof auth.current?.signInWithPassword !== "function") throw new Error("腾讯云登录 SDK 版本不兼容");
    setReady(true); setMessage("登录组件已就绪。请填写自己的工具站账号密码；不是学校密码，也不是腾讯云管理员密码。");
  }
  async function login() {
    if (!auth.current || !username.current || !password.current) return;
    const loginName = username.current.value.trim();
    if (!loginName || loginName.length > 128 || !password.current.value) {
      throw new Error("请填写自己的工具站账号和密码；账号访问权限由服务端核验");
    }
    let result;
    try {
      result = await auth.current.signInWithPassword({ username: loginName, password: password.current.value });
    } catch (error) { throw new Error(cloudAuthFailure(error)); }
    finally { password.current.value = ""; }
    if (result.error || !result.data?.session?.access_token) throw new Error(cloudAuthFailure(result.error, true));
    let sdkCleared = false;
    try {
      const verified = await apiClient.post<PilotSession>("/api/v1/auth/cloudbase/session", {}, {
        headers: { Authorization: `Bearer ${result.data.session.access_token}` },
      });
      if (verified.datasetKind !== "demo" || verified.personalUploads !== false || verified.agentPaired !== false) {
        throw new Error("服务端测试状态不一致，停止使用");
      }
      // Clear only our own old account's draft pointers, not other app storage.
      sessionStorage.removeItem("campus-demo-schedule-v1");
      writeDemoSession(verified); setSession(verified);
      setMessage(`${loginName} 已完成身份核验。课表和日历只读取这个账号自己的已保存记录；本人待办须核对后明确确认保存。`);
    } finally {
      // Keep only the server-issued HttpOnly session. Revoke/clear SDK
      // tokens immediately; never copy them into our own storage or logs.
      try {
        const signedOut = await auth.current.signOut();
        if (signedOut.error) setError("后端会话已处理，但腾讯云临时登录态清理失败；请关闭此测试页并稍后重试。");
        else sdkCleared = true;
      } catch { setError("腾讯云临时登录态清理失败；请关闭此测试页并稍后重试。"); }
    }
    if (!sdkCleared) return;
    const next = consentReturn ?? reviewReturn;
    if (next) window.location.assign(next); // Consent still requires an explicit user decision.
  }
  async function logout() {
    if (!session) return;
    await apiClient.post("/api/v1/auth/cloudbase/logout", {}, { headers: { "X-CSRF-Token": session.csrfToken } });
    clearDemoSession();
    setSession(null); setMessage("已退出工具站会话。重新登录同一账号可读回自己的已保存记录。");
  }
  async function restoreVisitor() {
    if (config?.visitorIdentityFirst !== true) throw new Error("服务端身份优先保护尚未启用，未发送恢复请求，不会新建空间。");
    const verified = await apiClient.post<PilotSession>("/api/v1/auth/visitor/session", {}, {
      headers: { "X-Campus-Visitor": "1" },
    });
    if (!verified.workspaceRef || !verified.csrfToken) throw new Error("浏览器身份未完成，停止使用");
    sessionStorage.removeItem("campus-demo-schedule-v1");
    writeDemoSession(verified); setSession(verified);
    // This restores known server identity only. OAuth consent remains explicit.
    if (!unified) window.location.assign(consentReturn ?? reviewReturn ?? "/tools/timetable");
  }
  return <section>
    <h1>{unified ? "我的身份、私有空间与设备" : config?.visitorEnabled ? "免注册使用校园助手" : "登录并授权我的校园助手"}</h1>
    <p>课表和日历属于你自己的私有空间；学校登录不会自动关联工具站身份。</p>
    {config?.visitorEnabled && config.visitorIdentityFirst !== true && <p role="alert">服务端身份优先保护尚未启用。停止恢复和接入操作，避免旧接口重复创建空间。</p>}
    {unified && config?.geniosNativeIdentityEnabled === true && <NativeIdentityOnboarding checking={checking}
      blocked={config?.visitorIdentityFirst !== true || (!!recoveryError && !browserSession.needsLogin)}
      consentReturn={consentReturn} destination={reviewReturn ?? "/tools/timetable"} />}
    {unified && config?.geniosNativeIdentityEnabled !== true && <IdentityOnboarding checking={checking} blocked={config?.visitorIdentityFirst !== true || (!!recoveryError && !browserSession.needsLogin)}
      consentReturn={consentReturn} destination={reviewReturn ?? "/tools/timetable"}
      sessionIdentity={session?.workspaceRef ?? null} resumeVisitor={restoreVisitor} />}
    {!unified && config?.visitorEnabled && !session && <><p>仅恢复本浏览器已验证的原身份，不新建账号或私有空间。</p>
      <button disabled={busy || checking || config.visitorIdentityFirst !== true || (!!recoveryError && !browserSession.needsLogin)} onClick={() => void perform(restoreVisitor)}>恢复本浏览器原有身份</button>
      <p>新浏览器请先通过 Agent 本人授权绑定，不能凭学校登录或设备码新建身份。</p>
      <p>请勿使用公共电脑保存私人课表。清除本站全部浏览器数据会丢失访客身份；未另行绑定设备时无法找回。</p></>}
    {!unified && (config?.agentDeviceBindingEnabled ? <p><a href="/tools/device-login">使用固定设备码绑定这个浏览器 →</a> 首次由 Agent 当前授权账号绑定，不自动识别学校账号。</p>
      : config?.deviceLoginEnabled && <p><a href="/tools/device-login">已有登录设备？绑定这个浏览器 →</a> 首次由本人已登录设备确认，不自动识别 GeniOS 账号。</p>)}
    {consentReturn && <p>这是学校插件的授权登录步骤。登录后回到授权页；是否同意由你决定，不会自动授权。</p>}
    {reviewReturn && <p>登录后返回原来的课表、待办复核页或日历，仍须你核对并明确确认，不会自动保存。</p>}
    <p role="note">不共用账号或他人的授权。导入内容核对后明确确认保存。{config?.persistentAuthorization ? "退出或撤销授权仍会失效；已保存记录保留。" : "授权期限以实际授权页面为准。"}{!config?.visitorEnabled && "当前仅限已批准账号。"}不接收成绩上传。</p>
    {checking && <p role="status">正在核验当前浏览器会话。</p>}
    {!!recoveryError && !browserSession.needsLogin && <p role="alert">{recoveryError instanceof ApiError ? `${recoveryError.message}（${recoveryError.code} · ${recoveryError.requestId ?? "无请求编号"}）` : String(recoveryError)}</p>}
    {!!recoveryError && !browserSession.needsLogin && <button disabled={checking || busy} onClick={browserSession.retryRecovery}>重新核验浏览器会话</button>}
    {!ready && <details><summary>已有工具站账号？保留原账号和数据</summary><button disabled={busy || checking || !config || (identityPilot && !!recoveryError && !browserSession.needsLogin)} onClick={() => void perform(prepare)}>加载腾讯云登录组件</button></details>}
    {ready && <form onSubmit={event => { event.preventDefault(); void perform(login); }}>
      <label>本人账号 <input ref={username} name="username" autoComplete="username" placeholder="你的工具站用户名" disabled={busy} /></label>
      <label>账号密码 <input ref={password} name="password" type="password" autoComplete="off" disabled={busy} /></label>
      <button type="submit" disabled={busy || checking || (identityPilot && !!recoveryError && !browserSession.needsLogin)}>登录并验证身份</button>
    </form>}
    {session && <><p>当前浏览器已登录；账号身份以服务端验证为准。</p>
      {!unified && (consentReturn || reviewReturn) && <p><a href={consentReturn ?? reviewReturn!}>{consentReturn ? "返回授权页，由我决定是否同意" : reviewReturn === "/tools/calendar" ? "返回待办日历" : "返回原草稿复核页"}</a></p>}
      <button disabled={busy} onClick={() => void perform(logout)}>退出当前账号</button>
      {!unified && <p><a href="/tools/import">导入我的课表 →</a>　<a href="/tools/calendar">我的待办日历 →</a></p>}</>}
    {busy && <p role="status">正在处理，请勿重复点击。</p>}
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
