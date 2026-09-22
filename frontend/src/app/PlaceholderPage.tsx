import { StatusBanner } from "../shared/components";

/**
 * 模块占位页：A/B/D 的页面组件未接入前使用明确占位，
 * 不伪造业务数据，也不会落到服务器默认 404。
 */
export function PlaceholderPage({
  componentName,
  owner,
}: {
  componentName: string;
  owner: string;
}) {
  return (
    <section>
      <StatusBanner
        kind="unverified"
        message={`页面组件 ${componentName} 尚未接入（由 ${owner} 交付后接入路由）。当前为明确占位，不展示虚构业务数据。`}
      />
    </section>
  );
}
