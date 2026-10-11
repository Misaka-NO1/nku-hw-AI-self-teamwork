import { useEffect, useRef, useState } from "react";
import { useBrowserSession } from "../auth/useBrowserSession";
import type { PageReport } from "./pageApi";
import { degreeApi, saveConfirmedDegree, type DegreeDraft } from "./connectedApi";
import type { SaveAttempt } from "../tasks/api";
import { ApiError } from "../../shared/api/client";
import "./degree-page.css";

interface Observation {
  kind: string;
  source: { url: string; captured_at: string; coverage: string; adapter_verified: boolean };
  headers: string[];
  rows: { cells: string[]; locator: string }[];
}

function checked(value: unknown): value is Observation {
  if (!value || typeof value !== "object") return false;
  const v = value as Observation;
  if (Object.keys(v).some(key => !["kind", "source", "headers", "rows"].includes(key))) return false;
  if (!v.source || typeof v.source !== "object" || Object.keys(v.source).some(key => !["url", "captured_at", "coverage", "adapter_verified"].includes(key))) return false;
  let characters = 0;
  return v.kind === "degree-table-observation" && v.source?.url === "https://eamis.nankai.edu.cn/eams/myPlanCompl.action"
    && v.source.adapter_verified === false && ["unknown", "partial"].includes(v.source.coverage)
    && typeof v.source.captured_at === "string" && v.source.captured_at.length <= 64
    && Number.isFinite(Date.parse(v.source.captured_at)) && Array.isArray(v.headers)
    && v.headers.length <= 64 && v.headers.every(h => typeof h === "string" && h.length <= 4096)
    && Array.isArray(v.rows) && v.rows.length > 0 && v.rows.length <= 2000
    && v.rows.every(r => r && Object.keys(r).every(key => ["locator", "cells"].includes(key)) && typeof r.locator === "string" && r.locator.length <= 128
      && Array.isArray(r.cells) && r.cells.length <= 64 && r.cells.every(c => {
        if (typeof c !== "string" || c.length > 4096) return false;
        characters += c.length; return characters <= 262144;
      }));
}

export function DegreeReadPreview() {
  const auth = useBrowserSession(import.meta.env.VITE_IDENTITY_PILOT === "true");
  const [observation, setObservation] = useState<Observation | null>(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState<PageReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [shareMessage, setShareMessage] = useState("");
  const [draft, setDraft] = useState<DegreeDraft | null>(null);
  const [savedRevision, setSavedRevision] = useState<number | null>(null);
  const draftKey = useRef<string | null>(null);
  const attempt = useRef<SaveAttempt | null>(null);
  const lock = useRef(false);
  const restore = useRef<AbortController | null>(null);
  const freshReceipt = useRef(false);
  const request = useRef<AbortController | null>(null);
  const previousOwner = useRef<string | null>(null);
  const currentAuth = useRef(auth);
  currentAuth.current = auth;
  const canShowReceipt = !auth.checking && !!auth.session
    && previousOwner.current === auth.session.workspaceRef;
  useEffect(() => {
    request.current?.abort(); restore.current?.abort(); setBusy(false);
    // A focus recheck temporarily has no owner. Hide the receipt while checking,
    // but do not destroy an already consumed one-shot transfer for the same owner.
    if (auth.checking) return;
    const owner = auth.session?.workspaceRef ?? null;
    if (!owner || (previousOwner.current && previousOwner.current !== owner)) {
      setObservation(null); setReport(null); setShareMessage(""); setDraft(null); setSavedRevision(null);
      draftKey.current = null; attempt.current = null; freshReceipt.current = false;
    }
    previousOwner.current = owner;
  }, [auth.session?.workspaceRef, auth.session?.csrfToken, auth.checking]);
  useEffect(() => () => { request.current?.abort(); restore.current?.abort(); }, []);
  useEffect(() => {
    if (auth.checking || !auth.session) return;
    const controller = new AbortController(); restore.current = controller;
    const owner = auth.session.workspaceRef;
    degreeApi.current(controller.signal).then(item => {
      if (controller.signal.aborted || currentAuth.current.checking || currentAuth.current.session?.workspaceRef !== owner) return;
      if (item.workspaceRef !== owner || !checked(item.observation)) throw new Error("培养计划归属或结构不一致");
      setSavedRevision(item.revision);
      // Fresh transfers and pending drafts take precedence over a saved snapshot.
      if (!freshReceipt.current) { setObservation(item.observation as Observation); setReport(item.report); }
    }).catch(reason => {
      if (controller.signal.aborted) return;
      if (reason instanceof ApiError && reason.status === 404) return;
      auth.rejectExpiredSession(reason);
      setError("已保存培养计划暂时无法读回，请核对登录状态后重试。");
    });
    return () => controller.abort();
  }, [auth.checking, auth.session?.workspaceRef]);
  useEffect(() => {
    const receive = (event: Event) => {
      if (currentAuth.current.checking || !currentAuth.current.session) return;
      const value: unknown = (event as CustomEvent).detail;
      request.current?.abort(); restore.current?.abort(); setReport(null); setBusy(false); setShareMessage("");
      setDraft(null); draftKey.current = null; attempt.current = null;
      freshReceipt.current = true;
      setObservation(null);
      if (!checked(value)) { setError("培养计划读取结果无效，请重新读取。"); return; }
      setError(""); setObservation(JSON.parse(JSON.stringify(value)) as Observation);
    };
    const ready = () => {
      if (!currentAuth.current.checking && currentAuth.current.session)
        window.dispatchEvent(new Event("campus:degree-import-ready"));
    };
    const transferError = () => {
      request.current?.abort(); restore.current?.abort(); setReport(null); setObservation(null); setBusy(false); setShareMessage("");
      setDraft(null); draftKey.current = null; attempt.current = null;
      freshReceipt.current = false;
      setError("培养计划没有成功转交，可能已过期或被领取。请回到教务页重新主动读取。");
    };
    window.addEventListener("campus:degree-observation", receive);
    window.addEventListener("campus:degree-bridge-ready", ready);
    window.addEventListener("campus:degree-read-error", transferError);
    ready();
    return () => {
      window.removeEventListener("campus:degree-observation", receive);
      window.removeEventListener("campus:degree-bridge-ready", ready);
      window.removeEventListener("campus:degree-read-error", transferError);
    };
  }, []);
  useEffect(() => {
    if (!auth.checking && auth.session) window.dispatchEvent(new Event("campus:degree-import-ready"));
  }, [auth.checking, auth.session?.workspaceRef]);
  async function analyze() {
    if (!observation || !auth.session || auth.checking || lock.current) return;
    lock.current = true;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setReport(null); setError(""); setBusy(true); setShareMessage("");
    try {
      draftKey.current ??= `degree-${crypto.randomUUID()}`;
      const result = await degreeApi.createDraft(auth.session, observation, draftKey.current, controller.signal);
      if (!controller.signal.aborted) {
        if (result.workspaceRef !== auth.session.workspaceRef || result.kind !== "degree") throw new Error("培养计划草稿归属不一致");
        setDraft(result); setReport(result.report); attempt.current = null;
        setShareMessage("已生成云端草稿，尚未正式保存。请核对后确认保存，Agent 才能直接读取。");
      }
    } catch (reason) {
      if (!controller.signal.aborted) {
        setDraft(null); setError("生成草稿未成功，请核对登录状态和读取内容后重试。");
        auth.rejectExpiredSession(reason);
      }
    } finally { lock.current = false; if (request.current === controller) setBusy(false); }
  }
  async function save() {
    if (!draft || !auth.session || auth.checking || lock.current || draft.status === "committed") return;
    lock.current = true;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    const session = auth.session;
    const guard = () => {
      if (controller.signal.aborted || currentAuth.current.checking || currentAuth.current.session?.workspaceRef !== session.workspaceRef)
        throw new Error("登录会话已变化，请重新核对；不会继续自动保存");
    };
    setBusy(true); setError(""); setShareMessage("");
    try {
      const cache = `campus-own-degree-attempt:${session.workspaceRef}`;
      let value = attempt.current;
      if (!value) { try { value = JSON.parse(sessionStorage.getItem(cache) ?? "null"); } catch { /* no academic content is stored here */ } }
      if (!value || value.draftId !== draft.draftId || value.revision !== draft.revision || value.payloadHash !== draft.payloadHash)
        value = { draftId: draft.draftId, revision: draft.revision, payloadHash: draft.payloadHash,
          confirmationKey: `degree-${crypto.randomUUID()}`, commitKey: `degree-${crypto.randomUUID()}` };
      const result = await saveConfirmedDegree(session, draft, value, item => {
        attempt.current = item; sessionStorage.setItem(cache, JSON.stringify(item));
      }, guard, controller.signal);
      guard();
      const current = await degreeApi.current(controller.signal);
      guard();
      if (current.workspaceRef !== session.workspaceRef || current.degreeId !== result.degreeId || current.revision !== result.revision)
        throw new Error("保存回执与数据库读回版本不一致，请刷新核验");
      freshReceipt.current = false;
      setDraft({ ...draft, status: "committed" }); setReport(current.report); setSavedRevision(current.revision);
      setShareMessage(`保存成功：已从数据库读回本人培养计划，版本 ${current.revision}。回到校园助手即可直接询问还缺哪些模块或学分，无需复制表格。`);
    } catch (reason) {
      if (!controller.signal.aborted) { auth.rejectExpiredSession(reason); setError("保存未完成或读回尚未核实，请重试核验，不会假报成功。"); }
    } finally { lock.current = false; if (request.current === controller) setBusy(false); }
  }
  return <section className="degree-read-preview" aria-label="本人培养计划读取核对">
    <h3>我的培养计划</h3>
    <details open={!observation}>
      <summary>首次使用：安装原校园助手插件</summary>
      <p>培养计划和课表使用同一个“南开校园助手 · 教务课表读取”插件；已经安装且能看到“读取培养计划”按钮的同学直接使用，无须重复安装。</p>
      <p><a href="/assets/campus-schedule-reader.zip" download>下载校园助手读取插件（Chrome / Edge）</a></p>
      <ol>
        <li>下载 ZIP 并解压，找到包含 manifest.json 的文件夹。</li>
        <li>在 Edge 地址栏输入 edge://extensions，或在 Chrome 输入 chrome://extensions，打开扩展管理页。</li>
        <li>开启开发者模式，点击“加载解压缩的扩展”（Chrome 为“加载已解压的扩展程序”），选择上面的文件夹。</li>
        <li>核对插件名称“南开校园助手 · 教务课表读取”。在同一浏览器登录教务和校园助手，打开“计划完成情况”，刷新页面后点击“读取培养计划”；若按钮未显示，点击浏览器工具栏里的校园助手插件图标。</li>
      </ol>
      <p>请在电脑的 Chrome 或 Edge 操作，内置浏览器和手机浏览器无法按上述方式安装。</p>
      <p><a href="https://eamis.nankai.edu.cn/eams/myPlanCompl.action" target="_blank" rel="noreferrer">打开教务“计划完成情况”</a>，读取后在本页核对、生成草稿，再明确确认保存供本人 Agent 读取。</p>
    </details>
    <p>在本人已登录的教务“计划完成情况”页主动读取，再在这里核对；读取不会自动保存。</p>
    {error && <p role="alert">{error}</p>}
    {observation && canShowReceipt ? <>
      <p>读取时间：{observation.source.captured_at}。页面完整性尚待核对；在读不等于已经取得学分。</p>
      <details open><summary>核对已读取的原表格（{observation.rows.length} 行）</summary><div className="degree-table-wrap"><table><tbody>{observation.rows.map(row => <tr key={row.locator}>{row.cells.map((cell, i) => <td key={i}>{cell}</td>)}</tr>)}</tbody></table></div></details>
      <p>请确认上表来自自己的计划完成情况，再生成本人草稿；正式保存前 Agent 不会读取此草稿。</p>
      <button type="button" disabled={!auth.session || busy || auth.checking} onClick={analyze}>{busy ? "正在处理…" : "确认表格并生成草稿"}</button>
      {!auth.session && <p>请先登录校园助手，再分析读取结果。</p>}
    </> : <p>{auth.checking ? "正在核验登录身份，读取结果暂不显示。" : "尚未收到培养计划读取结果。"}</p>}
    {report && canShowReceipt && <>
      {draft && <button type="button" disabled={busy || auth.checking || draft.status === "committed"} onClick={save}>我已核对，确认替换本人培养计划并保存供 Agent 读取</button>}
      {savedRevision !== null && <p>本人已保存版本：{savedRevision}。确认新版本前保留旧版本。</p>}
      {shareMessage && <p role="status">{shareMessage}</p>}
      <h4>模块缺口</h4>
      <p>教务预审显示与已通过记录分列；在读不计入已通过。当前读取范围和方案版本仍待核实。</p>
      <div className="degree-table-wrap"><table><thead><tr>{["模块", "要求学分", "已通过", "在读", "仍需补修", "建议下一步"].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{report.modules.map(module => {
          const courses = report.courses.filter(course => course.moduleLocator === module.locator);
          const passed = courses.filter(course => course.state === "passed");
          const reading = courses.filter(course => course.state === "in_progress");
          const summary = report.moduleSummaries?.find(item => item.locator === module.locator);
          return <tr key={module.locator}>
            <td>{module.name || module.label}{module.parentLocator && <small>上级：{report.modules.find(parent => parent.locator === module.parentLocator)?.name || "待核实"}</small>}<small>（{module.locator}）</small></td>
            <td>{module.requiredCredits ?? "待核实"}</td>
            <td>{summary && <p>当前记录：{summary.observedPassedCredits ?? "待核实"} 学分</p>}{(summary?.passedCourseNames ?? passed.map(course => course.name || course.code)).join("、") || "未识别到已通过记录"}</td>
            <td>{summary && <p>{summary.observedInProgressCredits ?? "待核实"} 学分</p>}{(summary?.inProgressCourseNames ?? reading.map(course => course.name || course.code)).join("、") || "未识别到在读记录"}</td>
            <td>{module.gapText || "页面未明确显示缺口，需核实"}{summary?.optionalBranch && <p>此分支可选，页面缺口不代表必须补修本组。</p>}</td>
            <td>{summary?.nextStep || "核对必修及子模块条件"}</td>
          </tr>;
        })}</tbody></table></div>
      {report.moduleSummaries?.map(summary => <details key={summary.locator}>
        <summary>{report.modules.find(module => module.locator === summary.locator)?.name || "模块"}：必修与核算详情</summary>
        <p>{summary.statisticsScope}；{summary.requiredCourseCoverage}。</p>
        <p>教务显示实修：{report.modules.find(module => module.locator === summary.locator)?.pageEarnedCredits ?? "未知"} 学分；此原值不等同于独立已通过学分。</p>
        {summary.optionalBranch && <p>页面注明此分支可选。以下核算只描述本分支，是否需要选修仍以所属模块总学分和组合条件为依据。</p>}
        <p>缺明确标记的必修：{summary.missingRequiredCourses.filter(course => course.state !== "in_progress").map(course => `${course.name || course.code}（待完成或核实）`).join("、") || "未识别到，其他必修要求仍待核实"}</p>
        {!!summary.missingRequiredCourses.some(course => course.state === "in_progress") && <p>在读必修先跟进成绩：{summary.missingRequiredCourses.filter(course => course.state === "in_progress").map(course => course.name || course.code).join("、")}，不列为当前补修课程。</p>}
        {!!summary.requiredCategoryPendingCourses?.length && <p>必修模块中尚未通过的课程：{summary.requiredCategoryPendingCourses.map(course => course.name || course.code).join("、")}。在读先跟进成绩，补修或替代要求仍需核实。</p>}
        <p>待认定或状态未知：{summary.pendingCourses.map(course => course.name || course.code).join("、") || "未识别到"}</p>
        {summary.calculation ? <p>独立核算：子模块范围已计 {summary.calculation.subtreeEarnedCredits} 学分，仍缺 {summary.calculation.remainingCredits ?? "待核实"} 学分。</p> : <p>模块结构未核实，暂不提供独立核算结论。</p>}
        {summary.discrepancies.length > 0 && <><p>教务预审与独立核算存在差异，可能涉及在读或认定规则，请核对：</p><ul>{summary.discrepancies.map((item, i) => <li key={i}>{({page_earned_credits_mismatch: "实修学分", page_remaining_credits_mismatch: "剩余学分", page_satisfied_mismatch: "完成状态"} as Record<string, string>)[item.code] || "核算结果"}：教务显示 {String(item.page ?? "未知")}，独立核算 {String(item.calculatedSubtree ?? item.calculated ?? "未知")}</li>)}</ul></>}
      </details>)}
      <h4>优先建议</h4>
      <ol>{report.prioritySuggestions?.map((item, i) => <li key={i}>{item.moduleName}：{item.message}（依据：{item.evidence.locator}）</li>)}</ol>
      {report.recommendationLimits?.map((item, i) => <p key={i}>{item}</p>)}
      <h4>待核实</h4>
      <ul>{report.pendingVerification.map((item, i) => <li key={i}>{item.detail}</li>)}</ul>
      <p>未取得开课、先修和选课条件依据，暂不推荐具体课程或学期。此结果不构成学校最终毕业审核。</p>
    </>}
  </section>;
}
