/**
 * 培养方案审计 API。
 * 公共接口只接受 transcript_ref（由 D 解析为已授权记录）；
 * 前端不得直接提交任意成绩记录。
 */
import { apiClient } from "../../shared/api/client";
import type { DegreeAuditResult } from "./types";

export interface DegreeAuditRequest {
  workspaceRef: string;
  planId: string;
  transcriptRef: string;
}

export function auditDegree(req: DegreeAuditRequest): Promise<DegreeAuditResult> {
  // 线上字段为 snake_case，client 会把响应转成 camelCase。
  return apiClient.post<DegreeAuditResult>("/api/v1/degree/audit", {
    workspace_ref: req.workspaceRef,
    plan_id: req.planId,
    transcript_ref: req.transcriptRef,
  });
}
