import { validateDegreePlanImport, type DegreePlanImport } from "./degree";

/** C's policy evidence is separate from a user's credit snapshot. It must not
 * turn a school's preliminary report into our own graduation determination. */
export const GENERAL_ELECTIVE_POLICY = {
  id: "nku-general-elective-c08-v1",
  repository_source: "knowledge/degree/cs-2025/plan-rules.md",
  source_url: "https://jwc.nankai.edu.cn/2026/0119/c35436a589267/page.htm",
  source_location: "选课指南附件第 5 页，四、修读原则（C 已收录）",
  module_names: ["公能素质和服务中国", "艺术审美与文化思辨", "科学精神与健康生活",
    "社会发展与国家治理", "工程素养与未来科技", "世界文明与国际视野"],
  minimum_modules: 4,
  minimum_credits_per_selected_module: "2",
  art_requirement: { cohort_from: 2023, minimum_credits: "2", course_kind: "艺术类课程" },
  checks: [
    "六个模块中至少选修四个，每个所选模块至少 2 学分；不是六个模块都必须修满。",
    "2023 级起，艺术审美与文化思辨模块中的艺术类课程另须至少 2 学分；该模块总学分不能代替艺术类课程认定。",
    "其余学分可继续修通识选修，或按学校认定计入跨学院、国际交流、境外课程；不自动认定或重复计入。",
    "总要求学分以本人方案为准；C 收录的计算机科学与技术 2025 版为 14 学分，不推广为所有专业统一要求。",
  ],
} as const;

export function isGeneralElectiveModule(title: string): boolean {
  // Match the category, not a course mentioning it or a similarly named minor.
  return /^(?:(?:[一二三四五六七八九十百]+|\d+)[、.．\s]*|[（(][一二三四五六七八九十\d]+[）)]\s*)?通识(?:教育)?选修(?:课|课程|部分)?(?:$|[（(\s])/.test(title.trim());
}

function units(value: string): number {
  const [whole, fraction = ""] = value.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}
function creditsFromUnits(value: number): string {
  return `${Math.floor(value / 100)}${value % 100 ? `.${String(value % 100).padStart(2, "0").replace(/0$/, "")}` : ""}`;
}
/** Only explicit 在读 notes. No grade-based guesses or course details leave the browser. */
function inProgressCredits(plan: DegreePlanImport, start: number) {
  const level = (title: string): number | null => {
    if (/^[一二三四五六七八九十]+[、.．\s]/.test(title)) return 1;
    if (/^[（(][一二三四五六七八九十]+[）)]/.test(title)) return 2;
    const numeric = title.match(/^(\d+(?:\.\d+)*)\s/);
    if (numeric) return 3 + numeric[1].split(".").length - 1;
    return null;
  };
  const parent = plan.rows[start];
  if (parent.kind !== "module") throw new Error("Expected module");
  const depth = level(parent.title);
  let total = 0, direct = 0, insideChild = false;
  const codes = new Set<string>();
  for (const row of plan.rows.slice(start + 1)) {
    if (row.kind === "module") {
      const nextDepth = level(row.title);
      if (depth === null || nextDepth === null) return { total: null, direct: null };
      if (nextDepth <= depth) break;
      insideChild = true;
      continue;
    }
    // Duplicate allocation cannot safely be counted twice.
    if (codes.has(row.course_code)) return { total: null, direct: null };
    codes.add(row.course_code);
    if (/在读/.test(row.note ?? "")) {
      total += units(row.actual_credits);
      if (!insideChild) direct += units(row.actual_credits);
    }
  }
  if (total > units(parent.actual_credits)) return { total: null, direct: null };
  return { total: creditsFromUnits(total), direct: creditsFromUnits(direct) };
}
export function reportedCreditGap(required: string | null, counted: string | null): string | null {
  if (required === null || counted === null) return null;
  // Inputs have already passed the bounded decimal validator; avoid float gaps.
  const gap = Math.max(units(required) - units(counted), 0);
  return `${Math.floor(gap / 100)}${gap % 100 ? `.${String(gap % 100).padStart(2, "0").replace(/0$/, "")}` : ""}`;
}

/** Minimal question-answering input: no courses, grades, name, ID or credentials.
 * Retain ordered parent/child modules, but never sum them or infer completion.
 * User-provided titles/notes remain DATA, not Agent instructions. */
export function degreeProgressForQuestions(value: DegreePlanImport) {
  const plan = validateDegreePlanImport(value);
  const modules = plan.rows.map((row, index) => ({ row, index })).filter(({row}) => row.kind === "module").map(({row, index}, sourceIndex) => {
    if (row.kind !== "module") throw new Error("Expected module");
    const ongoing = inProgressCredits(plan, index);
    return ({
    source_index: sourceIndex,
    title: row.title,
    required_credits: row.required_credits,
    school_actual_credits: row.actual_credits,
    provisional_credit_gap: reportedCreditGap(row.required_credits, row.actual_credits),
    school_status: row.reported_status,
    school_note: row.note,
    school_in_progress_credits: ongoing.total,
    school_direct_in_progress_credits: ongoing.direct,
    policy_id: isGeneralElectiveModule(row.title) ? GENERAL_ELECTIVE_POLICY.id : null,
  }); });
  if (!modules.length) throw new Error("报告缺少分类学分，不能用课程明细猜测各模块进度。");
  const hasGeneral = modules.some(row => row.policy_id !== null);
  return {
    schema_version: "1.0.0" as const,
    kind: "degree_credit_progress" as const,
    program: plan.program,
    cohort: plan.cohort,
    summary: { ...plan.summary,
      credit_gap: reportedCreditGap(plan.summary.required_credits, plan.summary.completed_credits) },
    modules,
    has_in_progress_courses: /在读/.test(`${plan.summary.reported_result ?? ""} ${plan.summary.note ?? ""}`) || plan.rows.some(row => /在读/.test(row.note ?? "")),
    limitations: ["总览完成学分与模块实修学分为不同原始口径；实修及预审可能包含在读课程。",
      "模块差额仅为要求减教务实修，不表示最终未取得学分；缺必修或政策条件仍以学校审核为准。",
      "按学校分类顺序展示，不相加父子模块；未知值不补零，不作毕业资格结论。"],
    policies: hasGeneral ? [{ ...GENERAL_ELECTIVE_POLICY, verification_status: "needs_policy" as const,
      note: "仅保留规则说明；尚未核实模块归属、艺术类课程标记、年级适用性与学校学分认定，不自动判定满足。" }] : [],
  };
}

export type DegreeCreditProgress = ReturnType<typeof degreeProgressForQuestions>;

/** Agent upload/storage contract: no course rows, grades or derived answers. */
export function degreeProgressForStorage(plan: DegreePlanImport) {
  const value = degreeProgressForQuestions(plan);
  const { credit_gap: _gap, ...summary } = value.summary;
  return { schema_version: value.schema_version, kind: value.kind,
    program: value.program, cohort: value.cohort, summary,
    modules: value.modules.map(({title, required_credits, school_actual_credits, school_status, school_note,
      school_in_progress_credits, school_direct_in_progress_credits}) =>
      ({title, required_credits, school_actual_credits, school_status, school_note,
        school_in_progress_credits, school_direct_in_progress_credits})),
    has_in_progress_courses: value.has_in_progress_courses };
}
