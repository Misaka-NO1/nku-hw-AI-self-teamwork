import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import assert from "node:assert/strict";

const config = Object.fromEntries(
  readFileSync(new URL("../../.env.identity", import.meta.url), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => [line.slice(0, line.indexOf("=")), line.slice(line.indexOf("=") + 1)]),
);

describe("identity deployment navigation configuration", () => {
  it("enables the real public map without moving own timetable/calendar off-service", () => {
    const options = {
      identityPilot: config.VITE_IDENTITY_PILOT === "true",
      publicContentOnly: config.VITE_PUBLIC_CONTENT_ONLY === "true",
      publicContentOrigin: config.VITE_PUBLIC_CONTENT_ORIGIN,
      timetableOrigin: config.VITE_TIMETABLE_ORIGIN,
    };
    assert.equal(options.identityPilot, true);
    assert.equal(options.publicContentOnly, false);
    assert.equal(options.publicContentOrigin,
      "https://nku-campus-public-content-308235-6-1467707525.sh.run.tcloudbase.com");
    assert.equal(options.timetableOrigin,
      "https://nku-campus-identity-pilot-308235-6-1467707525.sh.run.tcloudbase.com");
  });

  it("returns to the existing user-facing Agent rather than a draft editor", () => {
    assert.equal(config.VITE_GENIOS_AGENT_URL,
      "https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg",
    );
    assert.equal(config.VITE_API_BASE_URL, "/");
  });
});
