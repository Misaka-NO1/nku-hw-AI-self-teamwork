/**
 * 上传票据（B06/B09）。
 *
 * 票据只存 chrome.storage.session 或内存，使用后清理；
 * 不进日志、不进同步存储、不进源码。票据过期或被取消时：
 * 不上传、不写后端，本地预览数据保留（EXT-02）。
 */

export interface ImportTicket {
  token: string;
  workspaceRef: string;
  purpose: string;
  /** epoch 毫秒 */
  expiresAt: number;
}

export class TicketError extends Error {
  readonly code: string;

  constructor(code: "TOKEN_EXPIRED" | "INVALID_TICKET" | "UPLOAD_DISABLED", message: string) {
    super(message);
    this.code = code;
  }
}

export function assertTicketUsable(ticket: ImportTicket, workspaceRef: string, now: number): void {
  if (ticket.purpose !== "schedule_import") {
    throw new TicketError("INVALID_TICKET", "票据用途不是 schedule_import");
  }
  if (ticket.workspaceRef !== workspaceRef) {
    throw new TicketError("INVALID_TICKET", "票据与当前工作区不匹配");
  }
  if (now >= ticket.expiresAt) {
    throw new TicketError("TOKEN_EXPIRED", "导入票据已过期；本地预览保留，请重新申请票据");
  }
}

export interface SubmitResult {
  draftId: string;
  reviewUrl: string | null;
}

/**
 * 由扩展 service worker 发起跨域上传；content script 永远拿不到票据。
 * 上传目标固定为后端 origin，不接受页面提供的任意 URL；
 * 不携带教务 Cookie（credentials: "omit"）。
 */
export async function submitConfirmedDraft(
  ticket: ImportTicket,
  workspaceRef: string,
  payload: unknown,
  options: { backendOrigin: string; now?: number; fetchImpl?: typeof fetch },
): Promise<SubmitResult> {
  const now = options.now ?? Date.now();
  assertTicketUsable(ticket, workspaceRef, now);
  if (!options.backendOrigin) {
    throw new TicketError("UPLOAD_DISABLED", "后端地址未配置，请使用离线 JSON 导出降级");
  }
  const fetchImpl = options.fetchImpl ?? fetch;
  const response = await fetchImpl(`${options.backendOrigin}/api/v1/schedules/import-drafts`, {
    method: "POST",
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
      Authorization: `ImportTicket ${ticket.token}`,
      "Idempotency-Key": `${ticket.token}:submit`,
    },
    body: JSON.stringify(payload),
  });
  if (response.status === 410) {
    throw new TicketError("TOKEN_EXPIRED", "导入票据已过期；本地预览保留，请重新申请票据");
  }
  if (!response.ok) {
    throw new TicketError("INVALID_TICKET", `后端拒绝草稿创建：HTTP ${response.status}`);
  }
  const body = (await response.json()) as {
    data?: { draft_id?: string; review_url?: string | null };
  };
  return { draftId: body.data?.draft_id ?? "", reviewUrl: body.data?.review_url ?? null };
}
