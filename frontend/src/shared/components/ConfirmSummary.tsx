/**
 * 草稿确认摘要：仅展示草稿内容并提供“确认/取消”回调。
 * 不在组件内部伪造确认 ID，也不绕过 D 的服务器校验。
 */
export interface ConfirmSummaryProps {
  title: string;
  items: { label: string; value: string }[];
  warnings?: string[];
  onConfirm: () => void;
  onCancel: () => void;
  confirmDisabled?: boolean;
}

export function ConfirmSummary({
  title,
  items,
  warnings = [],
  onConfirm,
  onCancel,
  confirmDisabled = false,
}: ConfirmSummaryProps) {
  return (
    <div className="confirm-summary">
      <h3>{title}</h3>
      <dl>
        {items.map((item) => (
          <div key={item.label} className="confirm-summary__row">
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {warnings.length > 0 ? (
        <ul className="confirm-summary__warnings">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      <div className="confirm-summary__actions">
        <button type="button" onClick={onConfirm} disabled={confirmDisabled}>
          确认提交
        </button>
        <button type="button" onClick={onCancel}>
          取消
        </button>
      </div>
    </div>
  );
}
