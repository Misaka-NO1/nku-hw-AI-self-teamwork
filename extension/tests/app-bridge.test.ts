// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { registerAppBridge, APP_OBSERVATION_EVENT } from "../src/app-bridge";

it("hands off when React mounts after the bridge, once only", async () => {
  const win = document.createElement("iframe");document.body.appendChild(win);
  const target=win.contentWindow!;
  const observation={rows:[["course"]]};
  const sendMessage=vi.fn().mockResolvedValue({ok:true,observation});
  const receive=vi.fn();target.addEventListener(APP_OBSERVATION_EVENT,receive);
  registerAppBridge({runtime:{sendMessage}} as unknown as typeof chrome,target);
  target.dispatchEvent(new Event("campus:schedule-import-ready"));
  target.dispatchEvent(new Event("campus:schedule-import-ready"));
  await Promise.resolve();
  expect(sendMessage).toHaveBeenCalledTimes(1);expect(receive).toHaveBeenCalledTimes(1);
  win.remove();
});

it("hands off when React already mounted before document_idle", async () => {
  const win = document.createElement("iframe");document.body.appendChild(win);
  const target=win.contentWindow!;
  const sendMessage=vi.fn().mockResolvedValue({ok:true,observation:{rows:[]}});
  target.addEventListener("campus:schedule-bridge-ready",()=>target.dispatchEvent(new Event("campus:schedule-import-ready")));
  registerAppBridge({runtime:{sendMessage}} as unknown as typeof chrome,target);
  await Promise.resolve();expect(sendMessage).toHaveBeenCalledTimes(1);
  win.remove();
});
