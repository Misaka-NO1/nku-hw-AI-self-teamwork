import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";

import {
  parseImportFile,
  parseWeeks,
  validateTermCalendarStructure,
  validateTimetableStructure,
  type ImportFormat,
  type ParseResult,
  type TermCalendar,
  type TimetableImport,
} from "@campus/import-core";

import { validateTimetableRemote } from "./api";

/**
 * ImportPage（/tools/import，owner: B；路由接入由 C 负责）。
 *
 * 流程：选择 JSON/规范 CSV/教务导出 HTML → 本地解析（不执行脚本、不联网）
 * → 可编辑预览（修正课程名/星期/节次/周次/地点，删除误识别条目）
 * → 显示 issues / 缺失字段 / 覆盖范围 → 用户确认后才允许下一步。
 * 不支持的格式或结构给出明确错误，绝不展示空课表。
 */

const FORMAT_BY_EXT: Record<string, ImportFormat> = {
  ".json": "json",
  ".csv": "csv",
  ".html": "html",
  ".htm": "html",
};

/** 教务系统课表页（学生需先登录统一身份认证） */
export const EAMIS_TIMETABLE_URL =
  "https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action";

/**
 * 「课表下载」书签小程序：拖到浏览器书签栏后，在教务「我的课表」页点击，
 * 自动把当前页面 HTML 下载为文件（纯前端无法跨域抓取已登录页面，书签是当前标签页内
 * 用户主动触发的本地下载，不上传任何内容）。找不到课表网格时给出明确提示。
 */
export const EAMIS_DOWNLOAD_BOOKMARKLET =
  "javascript:(()=>{var t=document.querySelector('#manualArrangeCourseTable');" +
  "if(!t){alert('未找到课表表格：请确认已登录教务系统，并打开「我的课表」页面、看到课表后再点我。');return;}" +
  "var h='<!DOCTYPE html>\\n'+document.documentElement.outerHTML;" +
  "var b=new Blob([h],{type:'text/html'});var a=document.createElement('a');" +
  "a.href=URL.createObjectURL(b);a.download='eamis-courseTable-'+new Date().toISOString().slice(0,10)+'.html';" +
  "document.body.appendChild(a);a.click();a.remove();})()";

const WEEKDAY_NAMES = "一二三四五六日";

export interface ImportPageProps {
  /** D's connection shell receives local previews; this callback never uploads. */
  onPreview?: (payload: TimetableImport | null) => void;
  /** 用户核对/修正完毕并点击“确认”后回调（payload 为编辑后的最终版本）。
   *  注意：payload 经编辑后，原 draft_hash 已失效；确认凭据/hash 的重生成
   *  属于 D 侧保存链路的职责（见 contracts 交接约定）。 */
  onConfirmed?: (payload: TimetableImport) => void;
  /** 可选：外部传入的学期日历；也可在页面内上传 TermCalendar JSON */
  calendar?: TermCalendar | null;
  datasetKind?: "demo" | "personal";
  /**
   * 服务端校验端点 /api/v1/schedules/validate 是否已由 D 接入。
   * 默认 false：按钮禁用并说明原因，绝不表现为已可用（PR #2 审核意见 4）。
   */
  serverValidateAvailable?: boolean;
}

export default function ImportPage({
  calendar: initialCalendar = null,
  datasetKind = "demo",
  serverValidateAvailable = false,
  onPreview,
  onConfirmed,
}: ImportPageProps) {
  const [calendar, setCalendar] = useState<TermCalendar | null>(initialCalendar);
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remoteCheck, setRemoteCheck] = useState<string | null>(null);
  // 可编辑草稿：解析结果的深拷贝，所有预览修改都作用在 draft 上
  const [draft, setDraft] = useState<TimetableImport | null>(null);
  // 周次文本草稿（meeting_id → 文本），确认时统一按 parseWeeks 校验
  const [weeksDraft, setWeeksDraft] = useState<Record<string, string>>({});
  const [editError, setEditError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (result?.payload) {
      const copy = JSON.parse(JSON.stringify(result.payload)) as TimetableImport;
      setDraft(copy);
      const texts: Record<string, string> = {};
      for (const course of copy.courses) {
        for (const meeting of course.meetings) {
          texts[meeting.meeting_id] = meeting.weeks.join(",");
        }
      }
      setWeeksDraft(texts);
    } else {
      setDraft(null);
      setWeeksDraft({});
    }
    setEditError(null);
    setConfirmed(false);
  }, [result]);

  // 壳层（D）收到的是编辑后的草稿，而不是原始解析结果
  useEffect(() => { onPreview?.(draft); }, [draft, onPreview]);

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
      // 按 TermCalendar 契约校验完整结构，拒绝畸形日历（如 periods: [null]）
      const validation = validateTermCalendarStructure(parsed);
      if (!validation.ok) {
        setError(`学期日历不符合 TermCalendar 契约：${validation.errors.join("；")}`);
        return;
      }
      setCalendar(parsed as TermCalendar);
      setResult(null);
      setFileName(null);
    } catch {
      setError("学期日历 JSON 解析失败");
    }
  }

  async function handleFile(file: File | undefined) {
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
    try {
      setResult(parseImportFile({ name: file.name, content }, format, calendar, { datasetKind }));
    } catch (parseError) {
      // 双保险：解析器本身已兜底，这里确保任何异常都变成可恢复的错误提示
      setError(`解析过程出现异常，已阻止导入：${parseError instanceof Error ? parseError.message : String(parseError)}`);
    }
  }

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    await handleFile(event.target.files?.[0]);
  }

  /** 拖放导入：下载的 HTML 直接拖回本页即解析 */
  async function onDropFile(event: React.DragEvent<HTMLElement>) {
    event.preventDefault();
    await handleFile(event.dataTransfer.files?.[0]);
  }

  async function onValidateRemote() {
    if (!draft) return;
    const envelope = await validateTimetableRemote(draft);
    setRemoteCheck(
      envelope.ok ? "服务端校验通过（尚未保存）" : `服务端校验失败：${envelope.error?.message}`,
    );
  }

  // ---- 预览编辑操作 ----

  function updateMeeting(courseId: string, meetingId: string, patch: Partial<TimetableImport["courses"][number]["meetings"][number]>) {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        courses: prev.courses.map((course) =>
          course.course_id !== courseId
            ? course
            : {
                ...course,
                meetings: course.meetings.map((meeting) =>
                  meeting.meeting_id !== meetingId ? meeting : { ...meeting, ...patch },
                ),
              },
        ),
      };
    });
    setConfirmed(false);
  }

  function updateCourseTitle(courseId: string, title: string) {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            courses: prev.courses.map((course) =>
              course.course_id === courseId ? { ...course, title } : course,
            ),
          }
        : prev,
    );
    setConfirmed(false);
  }

  function removeMeeting(courseId: string, meetingId: string) {
    setDraft((prev) => {
      if (!prev) return prev;
      // 课程最后一条 meeting 被删除时，整门课一并移除
      const courses = prev.courses
        .map((course) =>
          course.course_id !== courseId
            ? course
            : { ...course, meetings: course.meetings.filter((m) => m.meeting_id !== meetingId) },
        )
        .filter((course) => course.meetings.length > 0);
      return { ...prev, courses };
    });
    setConfirmed(false);
  }

  function addMeeting(courseId: string) {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        courses: prev.courses.map((course) =>
          course.course_id !== courseId
            ? course
            : {
                ...course,
                meetings: [
                  ...course.meetings,
                  {
                    meeting_id: `${courseId}-m${Date.now()}`,
                    weekday: 1,
                    start_period: 1,
                    end_period: 1,
                    weeks: [1],
                    location: null,
                    campus_id: null,
                  },
                ],
              },
        ),
      };
    });
    setConfirmed(false);
  }

  function onConfirm() {
    if (!draft) return;
    setEditError(null);
    // 1) 周次文本统一校验并写回
    const next: TimetableImport = JSON.parse(JSON.stringify(draft));
    for (const course of next.courses) {
      for (const meeting of course.meetings) {
        const text = weeksDraft[meeting.meeting_id] ?? "";
        const parsed = parseWeeks(text, calendar?.teaching_weeks);
        if (!parsed.weeks) {
          setEditError(
            `「${course.title}」周 ${WEEKDAY_NAMES[meeting.weekday - 1]} 第${meeting.start_period}节的周次无效：${parsed.issues[0]?.message ?? "无法解析"}`,
          );
          return;
        }
        meeting.weeks = parsed.weeks;
      }
    }
    // 2) 整体结构校验（契约兜底）
    const violations = validateTimetableStructure(next);
    if (violations.length > 0) {
      setEditError(
        `修正后的课表仍不符合契约：${violations.map((v) => `${v.field || "$"}: ${v.message}`).join("；")}`,
      );
      return;
    }
    setDraft(next);
    setConfirmed(true);
    onConfirmed?.(next);
  }

  // ---- 渲染 ----

  return (
    <main>
      <h1>导入课表</h1>
      <p>
        数据默认只在本地解析与预览（demo 模式）；确认前可在下方直接修正识别结果。
      </p>

      <section>
        <h2>第零步：从教务系统获取课表</h2>
        <ol>
          <li>
            把下面这个按钮<strong>拖到浏览器书签栏</strong>（只需一次）：{" "}
            <a
              href={EAMIS_DOWNLOAD_BOOKMARKLET}
              onClick={(e) => e.preventDefault()}
              title="拖到书签栏使用"
            >
              📥 课表下载
            </a>
          </li>
          <li>
            <a href={EAMIS_TIMETABLE_URL} target="_blank" rel="noreferrer">
              打开教务系统课表页 ↗
            </a>{" "}
            <button type="button" onClick={() => void navigator.clipboard?.writeText(EAMIS_TIMETABLE_URL)}>
              复制链接
            </button>
            ，登录统一身份认证，确认页面上<strong>已经看到课表网格</strong>。
          </li>
          <li>
            点击书签栏里的「📥 课表下载」，页面 HTML 会自动下载；把下载的文件
            <strong>拖回本页第二步</strong>（或点选择文件）即自动解析导入。
          </li>
        </ol>
        <p role="note">
          说明：课表页需要你的登录态，网页无法替你自动抓取；书签只在你主动点击时
          把当前页面保存为本地文件，不上传任何内容。也可以仍用 Ctrl+S “另存为”。
          如果解析提示“统一身份认证登录页”，说明保存时登录已失效，请登录后重试。
        </p>
      </section>

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

      <section
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => void onDropFile(e)}
      >
        <h2>第二步：选择课表文件</h2>
        <input type="file" accept=".json,.csv,.html,.htm" onChange={onFileChange} />
        <p role="note">也可以把下载好的 HTML / JSON / CSV 文件直接拖到这个区域。</p>
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

      {draft && (
        <section>
          <h2>预览与核对（尚未保存，可直接修改）</h2>
          <p>
            覆盖范围：{draft.source.coverage.scope} ·{" "}
            {draft.source.coverage.completeness} · 周次：
            {draft.source.coverage.week_numbers.join(",")}
          </p>
          {draft.source.coverage.completeness !== "complete" && (
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
                <th>起始节</th>
                <th>结束节</th>
                <th>周次（如 1-16、单2-16、1,3,5）</th>
                <th>地点</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {draft.courses.flatMap((course) =>
                course.meetings.map((meeting) => (
                  <tr key={meeting.meeting_id}>
                    <td>
                      <input
                        value={course.title}
                        onChange={(e) => updateCourseTitle(course.course_id, e.target.value)}
                      />
                    </td>
                    <td>
                      <select
                        value={meeting.weekday}
                        onChange={(e) =>
                          updateMeeting(course.course_id, meeting.meeting_id, { weekday: Number(e.target.value) })
                        }
                      >
                        {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                          <option key={d} value={d}>
                            周{WEEKDAY_NAMES[d - 1]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        value={meeting.start_period}
                        onChange={(e) =>
                          updateMeeting(course.course_id, meeting.meeting_id, {
                            start_period: Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        value={meeting.end_period}
                        onChange={(e) =>
                          updateMeeting(course.course_id, meeting.meeting_id, {
                            end_period: Number(e.target.value),
                          })
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={weeksDraft[meeting.meeting_id] ?? ""}
                        onChange={(e) => {
                          setWeeksDraft((prev) => ({ ...prev, [meeting.meeting_id]: e.target.value }));
                          setConfirmed(false);
                        }}
                      />
                    </td>
                    <td>
                      <input
                        value={meeting.location ?? ""}
                        placeholder="待确认"
                        onChange={(e) =>
                          updateMeeting(course.course_id, meeting.meeting_id, {
                            location: e.target.value || null,
                          })
                        }
                      />
                    </td>
                    <td>
                      <button type="button" onClick={() => removeMeeting(course.course_id, meeting.meeting_id)}>
                        删除
                      </button>
                      <button type="button" onClick={() => addMeeting(course.course_id)}>
                        添加安排
                      </button>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
          {editError && <p role="alert">{editError}</p>}
          <button type="button" onClick={onConfirm}>
            核对无误，确认导入
          </button>
          {confirmed && <p role="status">已确认：以上内容为最终版本（尚未上传保存）。</p>}
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
