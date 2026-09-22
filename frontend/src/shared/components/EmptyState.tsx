export function EmptyState({
  title = "暂无数据",
  hint,
}: {
  title?: string;
  hint?: string;
}) {
  return (
    <div className="state state--empty">
      <p>{title}</p>
      {hint ? <p className="state__hint">{hint}</p> : null}
    </div>
  );
}
