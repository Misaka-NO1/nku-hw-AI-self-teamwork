import { useMemo, useState } from "react";
import type { ChangeEvent } from "react";

import {
  parseImportFile,
  type ImportFormat,
  type ParseResult,
  type TermCalendar,
} from "@campus/import-core";

import { validateTimetableRemote } from "./api";

/**
 * ImportPage（/tools/import，owner: B；路由接入由 C 负责）。
 *
 * 流程：选择 JSON/规范 CSV/HTML 导出文件 → 本地解析（不执行脚本、不联网）
 * → 编辑前预览 → 显示 issues / 缺失字段 / 覆盖范围 → 用户确认后才允许下一步。
 * 不支持的格式或结构给出明确错误，绝不展示空课表。
 */

const FORMAT_BY_EXT: Record<string, ImportFormat> = {
  ".json": "json",
  ".csv": "csv",
  ".html": "html",
  ".htm": "html",
};

export interface ImportPageProps {
  /** 可选：外部传入的学期日历；也可在页面内上传 TermCalendar JSON */
  calendar?: TermCalendar | null;
  datasetKind?: "demo" | "personal";
  /**
   * 服务端校验端点 /api/v1/schedules/validate 是否已由 D 接入。
   * 默认 false：按钮禁用并说明原因，绝不表现为已可用（PR #2 审核意见 4）。
   */
  serverValidateAvailable?: boolean;
}

function isTermCalendar(value: unknown): value is TermCalendar {
  const candidate = value as Partial<TermCalendar> | null;
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    typeof candidate.term_id === "string" &&
    typeof candidate.week1_monday === "string" &&
    typeof candidate.teaching_weeks === "number" &&
    Array.isArray(candidate.periods) &&
    Array.isArray(candidate.overrides)
  );
}

export default function ImportPage({
  calendar: initialCalendar = null,
  datasetKind = "demo",
  serverValidateAvailable = false,
}: ImportPageProps) {
  const [calendar, setCalendar] = useState<TermCalendar | null>(initialCalendar);
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remoteCheck, setRemoteCheck] = useState<string | null>(null);

  const blockingIssues = useMemo(
    () => result?.issues.filter((issue) => issue.blocking) ?? [],
    [result],
  );
  const warnings = useMemo(
    () => result?.issues.filter((issue) => !issue.blocking) ?? [],
    [result],
  );

  async function onCalendarFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setError(null);
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (!isTermCalendar(parsed)) {
        setError("该 JSON 不是有效的学期日历（TermCalendar），请核对后重试");
        return;
      }
      setCalendar(parsed);
      setResult(null);
      setFileName(null);
    } catch {
      setError("学期日历 JSON 解析失败");
    }
  }

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setResult(null);
    setRemoteCheck(null);
    setError(null);
    if (!file) return;
    setFileName(file.name);
    if (file.size > 5 * 1024 * 1024) {
      setError("文件超过 5MiB 上限，请先在教务系统导出更小范围的文件");
      return;
    }
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    const format = FORMAT_BY_EXT[ext];
    if (!format) {
      setError(`暂不支持的格式 ${ext}；请使用标准 JSON、规范 CSV 或教务导出的 HTML`);
      return;
    }
    if (!calendar) {
      setError("尚未确认学期日历：仅可查看原始星期/节次/周次，不能生成公历日期");
      return;
    }
    const content = await file.text();
    setResult(parseImportFile({ name: file.name, content }, format, calendar, { datasetKind }));
  }

  async function onValidateRemote() {
    if (!result?.payload) return;
    const envelope = await validateTimetableRemote(result.payload);
    setRemoteCheck(
      envelope.ok ? "服务端校验通过（尚未保存）" : `服务端校验失败：${envelope.error?.message}`,
    );
  }

  return (
    <main>
      <h1>导入课表</h1>
      <p>
        数据默认只在本地解析与预览（demo 模式）；上传前会再次核对内容。也可以从教务系统导出文件后在此导入，
        或使用浏览器扩展读取当前页面。
      </p>

      <section>
        <h2>第一步：关联学期日历</h2>
        {calendar ? (
          <p>
            当前学期：{calendar.term_id}（{calendar.calendar_status}）{" "}
            <button type="button" onClick={() => setCalendar(null)}>
              更换
            </button>
          </p>
        ) : (
          <p>
            请先上传你自己确认的学期日历 JSON（TermCalendar）。未关联日历前只做原始
            星期/节次/周次核对，不生成公历日期。
            <input type="file" accept=".json" onChange={onCalendarFileChange} />
          </p>
        )}
      </section>

      <section>
        <h2>第二步：选择课表文件</h2>
        <input type="file" accept=".json,.csv,.html,.htm" onChange={onFileChange} />
      </section>
      {fileName && <p>已选择文件：{fileName}</p>}
      {error && <p role="alert">{error}</p>}

      {blockingIssues.length > 0 && (
        <section role="alert">
          <h2>无法导入</h2>
          <ul>
            {blockingIssues.map((issue, index) => (
              <li key={index}>
                [{issue.code}] {issue.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {result?.payload && (
        <section>
          <h2>预览（尚未保存）</h2>
          <p>
            覆盖范围：{result.payload.source.coverage.scope} ·{" "}
            {result.payload.source.coverage.completeness} · 周次：
            {result.payload.source.coverage.week_numbers.join(",")}
          </p>
          {result.payload.source.coverage.completeness !== "complete" && (
            <p role="note">课表可能不完整：空闲时间结果只基于已导入内容，不代表全学期都有空。</p>
          )}
          {warnings.length > 0 && (
            <ul>
              {warnings.map((issue, index) => (
                <li key={index}>
                  [{issue.code}] {issue.message}
                </li>
              ))}
            </ul>
          )}
          <table>
            <thead>
              <tr>
                <th>课程</th>
                <th>星期</th>
                <th>节次</th>
                <th>周次</th>
                <th>地点</th>
              </tr>
            </thead>
            <tbody>
              {result.payload.courses.flatMap((course) =>
                course.meetings.map((meeting) => (
                  <tr key={meeting.meeting_id}>
                    <td>{course.title}</td>
                    <td>周{"一二三四五六日"[meeting.weekday - 1]}</td>
                    <td>
                      第{meeting.start_period}-{meeting.end_period}节
                    </td>
                    <td>{meeting.weeks.join(",")}</td>
                    <td>{meeting.location ?? "待确认"}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
          <button type="button" onClick={onValidateRemote} disabled={!serverValidateAvailable}>
            发送到服务端校验（不保存）
          </button>
          {!serverValidateAvailable && (
            <p role="note">
              服务端校验接口（POST /api/v1/schedules/validate）尚未由后端接入，暂不可用；
              本地解析与离线导出不受影响。
            </p>
          )}
          {remoteCheck && <p>{remoteCheck}</p>}
        </section>
      )}
    </main>
  );
}
