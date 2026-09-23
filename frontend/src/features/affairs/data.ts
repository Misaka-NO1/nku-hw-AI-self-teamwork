/**
 * 校园事务数据源：静态知识目录（knowledge/affairs/entries.json）。
 * 该目录由 C 人工维护核验；没有正式来源的条目一律 needs_verification，
 * 不得把第三方帖子写成学校规定。
 */
import raw from "../../../../knowledge/affairs/entries.json";
import { snakeToCamel } from "../../shared/api/convert";
import type { AffairEntry } from "./types";

interface AffairsFile {
  schemaVersion: string;
  datasetKind: string;
  dataVersion: string;
  note: string;
  entries: AffairEntry[];
}

const file = snakeToCamel(raw) as unknown as AffairsFile;

export const AFFAIRS_DATA_VERSION = file.dataVersion;
export const AFFAIRS_DATASET_KIND = file.datasetKind;

export function listAffairs(): AffairEntry[] {
  return file.entries;
}

export function listCategories(): string[] {
  return Array.from(new Set(file.entries.map((e) => e.category))).sort();
}

/** 是否过期：显式 expired，或 valid_until 早于参考日期。 */
export function isExpired(entry: AffairEntry, today: string = todayISO()): boolean {
  if (entry.status === "expired") return true;
  if (entry.validUntil && entry.validUntil < today) return true;
  return false;
}

export function todayISO(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * 条目展示状态：过期优先；其次待核验；最后已核验。
 * 无正式来源（source_refs 为空且 official_url 为空）的条目不得显示为官方事实。
 */
export function entryDisplayState(
  entry: AffairEntry,
  today?: string
): "expired" | "needs_verification" | "verified" {
  if (isExpired(entry, today)) return "expired";
  const hasSource = entry.sourceRefs.length > 0 || entry.officialUrl !== null;
  if (entry.status !== "verified" || !entry.verifiedAt || !hasSource) {
    return "needs_verification";
  }
  return "verified";
}

export interface DisplaySource {
  label: string;
  href?: string;
  locator?: string;
  verifiedAt?: string;
}

/**
 * 页面来源列表：official_url 作为正式入口优先展示，
 * 与 entryDisplayState() 的“有来源”判断保持一致；两者皆空时返回空数组，
 * 由页面显示“暂无正式来源”。
 */
export function entrySources(entry: AffairEntry): DisplaySource[] {
  const sources: DisplaySource[] = [];
  if (entry.officialUrl) {
    sources.push({
      label: `官方入口：${entry.title}`,
      href: entry.officialUrl,
      verifiedAt: entry.verifiedAt ?? undefined,
    });
  }
  for (const ref of entry.sourceRefs) {
    sources.push({
      label: ref.label,
      href: ref.url ?? undefined,
      locator: ref.locator ?? undefined,
      verifiedAt: entry.verifiedAt ?? undefined,
    });
  }
  return sources;
}

export interface AffairFilter {
  query?: string;
  category?: string;
  campus?: string;
}

/** 分类搜索 + 校区过滤。校区/人群规则不混用：限定校区时不返回其他校区专属条目。 */
export function filterAffairs(entries: AffairEntry[], filter: AffairFilter): AffairEntry[] {
  const query = filter.query?.trim().toLowerCase();
  return entries.filter((entry) => {
    if (filter.category && entry.category !== filter.category) return false;
    if (
      filter.campus &&
      entry.campusScope.length > 0 &&
      !entry.campusScope.includes(filter.campus)
    ) {
      return false;
    }
    if (!query) return true;
    return (
      entry.title.toLowerCase().includes(query) ||
      entry.steps.some((s) => s.toLowerCase().includes(query)) ||
      entry.requiredMaterials.some((m) => m.toLowerCase().includes(query))
    );
  });
}
