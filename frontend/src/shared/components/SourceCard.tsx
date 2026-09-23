import type { SourceRef } from "./sourceRef";

const ALLOWED_SCHEMES = ["https:", "http:"];

function safeHref(href?: string): string | undefined {
  if (!href) return undefined;
  try {
    const url = new URL(href);
    return ALLOWED_SCHEMES.includes(url.protocol) ? href : undefined;
  } catch {
    return undefined;
  }
}

/** 展示来源标签、核验时间与定位；未知或非法协议链接降级为纯文本。 */
export function SourceCard({ source }: { source: SourceRef }) {
  const href = safeHref(source.href);
  return (
    <div className="source-card" data-testid="source-card">
      <span className="source-card__label">
        {href ? (
          <a href={href} target="_blank" rel="noreferrer">
            {source.label}
          </a>
        ) : (
          source.label
        )}
      </span>
      {source.locator ? (
        <span className="source-card__locator">（{source.locator}）</span>
      ) : null}
      <span className="source-card__verified">
        {source.verifiedAt ? `核验于 ${source.verifiedAt}` : "未核验"}
      </span>
    </div>
  );
}
