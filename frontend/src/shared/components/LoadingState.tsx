export function LoadingState({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="state state--loading" role="status">
      {label}
    </div>
  );
}
