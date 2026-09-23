import { NavLink, Outlet } from "react-router-dom";
import { TOOL_NAV } from "./nav";

const GENIOS_AGENT_URL = import.meta.env.VITE_GENIOS_AGENT_URL as
  | string
  | undefined;

/**
 * 统一外壳：工具导航 + “返回 NK-GeniOS”。
 * 工具站不是产品主入口；GENIOS_AGENT_URL 未配置时按钮禁用并说明，不猜链接。
 */
export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>南开校园助手 · 工具站</h1>
        <nav className="app-nav" aria-label="工具导航">
          {TOOL_NAV.map((item) => (
            <NavLink key={item.path} to={item.path}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        {GENIOS_AGENT_URL ? (
          <a className="back-to-genios" href={GENIOS_AGENT_URL}>
            返回 NK-GeniOS
          </a>
        ) : (
          <button
            className="back-to-genios"
            disabled
            title="未配置 VITE_GENIOS_AGENT_URL，暂不提供返回平台链接"
          >
            返回 NK-GeniOS（未配置）
          </button>
        )}
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
