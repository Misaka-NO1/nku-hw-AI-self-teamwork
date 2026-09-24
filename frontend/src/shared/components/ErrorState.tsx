import { ApiError } from "../api/client";

/** 错误态：任何接口错误都展示清楚的信息和 request_id，不把失败显示为成功。 */
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const isApi = error instanceof ApiError;
  const message = isApi
    ? error.message
    : error instanceof Error
      ? error.message
      : "发生未知错误";
  const requestId = isApi ? error.requestId : null;
  return (
    <div className="state state--error" role="alert">
      <p>操作未完成：{message}</p>
      {isApi ? <p className="state__hint">错误代码：{error.code}</p> : null}
      {requestId ? <p className="state__hint">request_id: {requestId}</p> : null}
      {retry ? (
        <button type="button" onClick={retry}>
          重试
        </button>
      ) : null}
    </div>
  );
}
