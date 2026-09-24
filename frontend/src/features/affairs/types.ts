/** 校园事务条目类型：与 knowledge/affairs/entries.json 对应（camelCase 内部形式）。 */

export type AffairKind = "entry" | "procedure";
export type TriState = "yes" | "no" | "unknown";
export type AffairStatus = "verified" | "needs_verification" | "expired";

export interface AffairSourceRef {
  label: string;
  url: string | null;
  locator: string | null;
}

export interface AffairEntry {
  entryId: string;
  kind: AffairKind;
  title: string;
  category: string;
  campusScope: string[];
  audience: string[];
  officialUrl: string | null;
  loginRequired: TriState;
  campusNetworkRequired: TriState;
  steps: string[];
  requiredMaterials: string[];
  sourceRefs: AffairSourceRef[];
  verifiedAt: string | null;
  validUntil: string | null;
  status: AffairStatus;
}

export const CATEGORY_LABELS: Record<string, string> = {
  academic: "教务学习",
  life: "生活服务",
  it: "网络信息",
  finance: "财务缴费",
  venue: "场馆预约",
  career: "就业实习",
};
