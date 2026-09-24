export interface StudyItem {
  material_id: string;
  version: string;
  course_id: string;
  title: string;
  material_type: string;
  topics: string[];
  content_available: boolean;
  source_label: string;
  rights_status: "owned" | "authorized" | "public_link_only" | "pending";
  access_scope: "public" | "team_only" | "private";
  reviewed_at: string | null;
  evidence: Array<{ chunk_id: string; heading: string; page_label: string | null;
    source_excerpt_ref: string; excerpt: string }>;
}

/** Only public entries are bundled into the frontend. Real content must come from D's adapter. */
export const demoStudyItems: StudyItem[] = [
  {
    material_id: "demo-note-01", version: "1.0", course_id: "demo-CS101",
    title: "程序设计示例笔记（自创测试材料）", material_type: "note", topics: ["递归", "数组"],
    content_available: true, source_label: "本仓库自创测试材料，非南开课程讲义或真题",
    rights_status: "owned", access_scope: "public", reviewed_at: "2026-09-19",
    evidence: [
      { chunk_id: "demo-note-01-c1", heading: "递归的两个必要部分", page_label: null,
        source_excerpt_ref: "knowledge/study/sources/demo-note-01.md#递归的两个必要部分",
        excerpt: "递归函数包含终止条件和递归推进。递归推进把问题变为更小的子问题，并朝终止条件靠近。" },
      { chunk_id: "demo-note-01-c2", heading: "数组下标检查", page_label: null,
        source_excerpt_ref: "knowledge/study/sources/demo-note-01.md#数组下标检查",
        excerpt: "长度为 n 的数组，有效下标为 0 到 n-1。访问元素前需要检查下标是否在这一范围。" },
    ],
  },
  {
    material_id: "demo-index-02", version: "1.0", course_id: "demo-CS101",
    title: "只有索引的虚构材料条目", material_type: "index", topics: ["排序"],
    content_available: false, source_label: "无真实文件，仅测试索引空态",
    rights_status: "public_link_only", access_scope: "public", reviewed_at: "2026-09-19", evidence: [],
  },
];

export function publicStudyItems(items: StudyItem[]): StudyItem[] {
  return items.filter((item) => item.access_scope === "public"
    && ["owned", "authorized", "public_link_only"].includes(item.rights_status));
}

export function filterStudyItems(items: StudyItem[], course_id: string, topic: string): StudyItem[] {
  const needle = topic.trim().toLocaleLowerCase();
  return publicStudyItems(items).filter((item) => item.course_id === course_id
    && (!needle || [item.title, ...item.topics, ...item.evidence.flatMap((e) => [e.heading, e.excerpt])]
      .some((part) => part.toLocaleLowerCase().includes(needle))));
}
