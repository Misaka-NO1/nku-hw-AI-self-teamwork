import { describe, expect, it } from "vitest";
import { cloudAuthFailure } from "./cloudAuthFailure";

describe("sanitised CloudBase login failures", () => {
  it.each([
    ["INVALID_CREDENTIALS", "测试账号凭证"], ["PRECONDITION_FAILED", "前置条件"],
    ["RATE_LIMITED", "停止重复点击"], ["CAPTCHA_REQUIRED", "本人完成"],
    ["MFA_REQUIRED", "本人完成"], ["PROVIDER_NOT_ENABLED", "未启用"],
  ])("reports approved category %s without vendor details", (category, hint) => {
    const output = cloudAuthFailure({ category, message: "private-password", helpMessage: "private-token", requestId: "private-user" });
    expect(output).toContain(category); expect(output).toContain(hint);
    expect(output).not.toContain("private-");
  });
  it.each([["invalid_password", "INVALID_CREDENTIALS"], ["unauthorized_client", "PRECONDITION_FAILED"], ["captcha_required", "CAPTCHA_REQUIRED"]])("classifies exact SDK code %s", (code, category) => {
    expect(cloudAuthFailure({ code })).toContain(category);
  });
  it.each([[4001, "CAPTCHA_REQUIRED"], [4022, "PRECONDITION_FAILED"], [8, "RATE_LIMITED"]])("classifies approved numeric error %s", (errorCode, category) => {
    expect(cloudAuthFailure({ errorCode })).toContain(category);
  });
  it.each([null, "private-token", { category: "private-token", code: "private-password", errorCode: 123456789, message: "private-user" }, { category: "__proto__", code: "constructor" }])("never echoes unrecognised fields", value => {
    const output = cloudAuthFailure(value);
    expect(output).toContain("UNKNOWN"); expect(output).not.toContain("private-");
    expect(output).not.toContain("123456789"); expect(output).not.toContain("constructor");
  });
  it("distinguishes success-shaped response without a session", () => {
    expect(cloudAuthFailure(null, true)).toContain("SESSION_MISSING");
  });
});
