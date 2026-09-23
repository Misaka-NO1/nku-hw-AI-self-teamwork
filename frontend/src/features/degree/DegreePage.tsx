import { useState } from "react";
import { ErrorState, StatusBanner } from "../../shared/components";
import { auditDegree } from "./api";
import { DEMO_PLAN_ID, DEMO_PLAN_VERSION, demoAuditResult } from "./demoData";
import { STATUS_LABELS, type DegreeAuditResult } from "./types";

function ModuleTable({ result }: { result: DegreeAuditResult }) {
  return (
    <table className="module-table">
      <thead>
        <tr>
          <th>模块</th>
          <th>已计学分</th>
          <th>要求学分</th>
          <th>剩余缺口</th>
          <th>缺必修</th>
          <th>计入记录</th>
          <th>排除记录</th>
        </tr>
      </thead>
      <tbody>
        {result.modules.map((m) => (
          <tr key={m.moduleId}>
            <td>{m.moduleId}</td>
            <td>{m.earnedCredits}</td>
            <td>{m.requiredCredits}</td>
            <td>{m.remainingCredits}</td>
            <td>
              {m.missingRequiredCourses.length > 0
                ? m.missingRequiredCourses.join("、")
                : "无"}
            </td>
            <td>{m.countedAttempts.join("、") || "无"}</td>
            <td>{m.excludedAttempts.join("、") || "无"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * 培养方案页：展示规则版本、导入说明、模块缺口、依据与未知项。
 * 不展示“保证毕业”；不同 plan 版本不混用。
 */
export function DegreePage() {
  const [result, setResult] = useState<DegreeAuditResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(false);

  async function runAudit() {
    setLoading(true);
    setError(null);
    setIsDemo(false);
    try {
      const audited = await auditDegree({
        workspaceRef: "demo-workspace-01",
        planId: DEMO_PLAN_ID,
        transcriptRef: "demo-transcript-01",
      });
      setResult(audited);
    } catch (err) {
      // 任何真实请求失败（认证/权限/参数/服务不可用）都保留错误与 request_id，
      // 不用夹具结果顶替。
      setResult(null);
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  function showDemoFixture() {
    // 离线演示是用户明确选择的模式，只在开发模式提供。
    setError(null);
    setIsDemo(true);
    setResult(demoAuditResult());
  }

  return (
    <section>
      <h2>培养方案进度</h2>
      <StatusBanner
        kind="demo"
        message={`当前仅有虚构演示方案（${DEMO_PLAN_ID} / ${DEMO_PLAN_VERSION}）。正式培养方案核验前，结果不代表学校审核结论。`}
      />
      <p className="state__hint">
        成绩记录由后端按 transcript_ref 授权解析，本页面不接收任意成绩数据；
        结果仅反映“所选规则下的学习进度”，不构成毕业资格结论。
      </p>
      <div className="toolbar">
        <button type="button" onClick={runAudit} disabled={loading}>
          {loading ? "审计中…" : "请求后端审计"}
        </button>
        {import.meta.env.DEV ? (
          <button type="button" onClick={showDemoFixture} disabled={loading}>
            查看夹具演示结果（离线 demo）
          </button>
        ) : null}
      </div>
      {error ? <ErrorState error={error} retry={runAudit} /> : null}
      {result ? (
        <div className="card">
          {isDemo ? (
            <StatusBanner
              kind="demo"
              message="以下为夹具预期结果的离线演示（demo），不是实际审计输出。"
            />
          ) : null}
          <h3>
            方案 {result.planId}（版本 {result.planVersion}）：
            {STATUS_LABELS[result.status]}
          </h3>
          <p className="state__hint">规则来源：{result.sourceRef}</p>
          <ModuleTable result={result} />
          {result.unallocatedCourses.length > 0 ? (
            <p>未归属课程（保留待规则确认）：{result.unallocatedCourses.join("、")}</p>
          ) : null}
          {result.unresolvedRules.length > 0 ? (
            <div>
              <h4>未决规则</h4>
              <ul>
                {result.unresolvedRules.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="state__hint">
            {String(result.dataCoverage.note ?? "")}
            {result.dataCoverage.totalRemainingCredits
              ? `　总缺口：${result.dataCoverage.totalRemainingCredits} 学分`
              : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
