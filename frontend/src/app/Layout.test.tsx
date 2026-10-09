import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router-dom/server";
import { Layout } from "./Layout";

afterEach(() => vi.unstubAllEnvs());

describe("工具站设备码入口", () => {
  it("身份工具站提供服务端设备码页链接，不在前端创建或修改绑定", () => {
    vi.stubEnv("VITE_IDENTITY_PILOT", "true");
    const page = renderToStaticMarkup(<StaticRouter location="/tools/calendar"><Layout /></StaticRouter>);
    expect(page).toContain('<a href="/tools/device">我的设备码</a>');
    expect(page).not.toContain("agent-device/start");
  });

  it("没有身份服务的公开前端不显示本站不存在的入口", () => {
    vi.stubEnv("VITE_IDENTITY_PILOT", "false");
    const page = renderToStaticMarkup(<StaticRouter location="/tools/map"><Layout /></StaticRouter>);
    expect(page).not.toContain("我的设备码");
  });
});
