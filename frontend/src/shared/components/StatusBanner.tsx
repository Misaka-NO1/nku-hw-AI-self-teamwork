export type StatusBannerKind = "demo" | "unverified" | "partial" | "error";

export interface StatusBannerProps {
  kind: StatusBannerKind;
  message: string;
  /** 由 API client 从 meta.request_id 映射而来，便于排障。 */
  requestId?: string;
}

const KIND_LABEL: Record<StatusBannerKind, string> = {
  demo: "演示数据",
  unverified: "待核验",
  partial: "部分数据",
  error: "错误",
};

/** 页面级状态条：演示/待核验/部分/错误四类明显标识。 */
export function StatusBanner({ kind, message, requestId }: StatusBannerProps) {
  return (
    <div className={`status-banner status-banner--${kind}`} role="alert">
      <strong>{KIND_LABEL[kind]}</strong>
      <span>{message}</span>
      {requestId ? <code>request_id: {requestId}</code> : null}
    </div>
  );
}
