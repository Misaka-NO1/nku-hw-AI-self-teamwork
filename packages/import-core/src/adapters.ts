import type { PageObservation, ParseIssue } from "./types";

/**
 * 适配器注册表。
 *
 * nku-adapter-v1：未取得本人授权的真实教务页面核查记录前必须保持 disabled，
 * 白名单为空。不得在这里猜测任何南开真实域名、路径或选择器。
 * （状态记录见 docs/evidence/B/adapter-observation.md，当前为 WAITING_HUMAN。）
 *
 * demo-fixture-adapter：仅用于虚构夹具页面/文件的单测与离线演示。
 */

export type AdapterStatus = "enabled" | "disabled";

export interface AdapterDescriptor {
  id: string;
  version: string;
  status: AdapterStatus;
  /** 精确 origin 白名单；为空表示不允许任何真实页面 */
  originWhitelist: string[];
  /** 精确 path 前缀白名单（配合 origin 使用） */
  pathWhitelist: string[];
  /** 课程表必需表头（结构特征判断之一） */
  requiredHeaders: string[];
  disabledReason: string | null;
}

export const ADAPTERS: AdapterDescriptor[] = [
  {
    id: "nku-adapter-v1",
    version: "1.0.0",
    status: "disabled",
    originWhitelist: [],
    pathWhitelist: [],
    requiredHeaders: [],
    disabledReason:
      "WAITING_HUMAN：尚未完成有授权的真实教务页面只读核查（B07），不猜测域名与选择器",
  },
  {
    id: "demo-fixture-adapter",
    version: "1.0.0",
    status: "enabled",
    originWhitelist: ["http://localhost", "https://fixtures.example.invalid"],
    pathWhitelist: ["/demo/timetable"],
    requiredHeaders: ["课程", "星期", "节次", "周次"],
    disabledReason: null,
  },
];

export function getAdapter(id: string): AdapterDescriptor | undefined {
  return ADAPTERS.find((adapter) => adapter.id === id);
}

export interface Recognition {
  supported: boolean;
  reason: string;
  adapterId: string | null;
}

/**
 * 三重判断：精确 origin → 明确 path → 课程表结构特征。
 * 任一不满足都返回 UNSUPPORTED_PAGE，绝不导入空课表。
 */
export function recognizePage(observation: PageObservation): Recognition {
  for (const adapter of ADAPTERS) {
    const originOk = adapter.originWhitelist.some((origin) => observation.origin === origin);
    const pathOk = adapter.pathWhitelist.some((path) => observation.pathname.startsWith(path));
    if (!originOk || !pathOk) {
      continue;
    }
    if (adapter.status === "disabled") {
      return {
        supported: false,
        reason: `ADAPTER_DISABLED: ${adapter.disabledReason ?? adapter.id}`,
        adapterId: adapter.id,
      };
    }
    if (observation.frameOrigin !== null && observation.frameOrigin !== observation.origin) {
      return {
        supported: false,
        reason: "UNSUPPORTED_PAGE: 课程区域位于跨源 iframe，无法安全读取，请改用文件导入",
        adapterId: adapter.id,
      };
    }
    const headersOk = adapter.requiredHeaders.every((header) =>
      observation.tableHeaders.includes(header),
    );
    if (!headersOk) {
      return {
        supported: false,
        reason: "UNSUPPORTED_PAGE: 缺少必需表头（可能为登录页、空页或页面已改版）",
        adapterId: adapter.id,
      };
    }
    if (observation.rows.length === 0) {
      return {
        supported: false,
        reason: "UNSUPPORTED_PAGE: 课程区域没有数据行（空页或登录页），拒绝导入空课表",
        adapterId: adapter.id,
      };
    }
    return { supported: true, reason: "OK", adapterId: adapter.id };
  }
  return {
    supported: false,
    reason: "UNSUPPORTED_PAGE: 非白名单域名或路径，不注入、不解析、不上传",
    adapterId: null,
  };
}

export function unsupportedIssue(reason: string): ParseIssue {
  return { code: "UNSUPPORTED_PAGE", field: "page", message: reason, blocking: true };
}
