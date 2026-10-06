import { describe, expect, it } from "vitest";
import { oauthReturnPath } from "./oauthReturn";
import { toolReviewLoginUrl, toolReviewReturnPath } from "./toolReviewReturn";

const origin = "https://pilot.example.invalid";
const outer = (value: string) => "?" + new URLSearchParams({ return_to: value });
describe("controlled tool review login returns", () => {
  it.each(["/tools/tasks", "/tools/import", "/tools/calendar", "/tools/tasks?draft_id=draft_ABC-123", "/tools/import?draft_id=schedule_draft_123"])(
    "preserves only the review address %s", value => {
      expect(toolReviewReturnPath(outer(value), origin)).toBe(value);
      expect(toolReviewLoginUrl(value, origin)).toBe("/tools/login" + outer(value));
      expect(oauthReturnPath(outer(value), origin)).toBeNull();
    });
  it.each(["https://attacker.invalid/tools/tasks", "//attacker.invalid/tools/tasks", "/tools/tasks#hidden",
    "/tools/tasks?draft_id=", "/tools/tasks?draft_id=a&draft_id=b", "/tools/import?owner=other",
    "/tools/tasks?draft_id=a&access_token=hidden", "/tools/tasks?return_to=/oauth/approve",
    "/tools/tasks?draft_id=..%2Fother", "/tools/tasks?draft_id=" + "a".repeat(129),
    "/tools/tasks?draft_id=%0A", "/tools/tasks?draft_id=a#", "/tools/tasks?draft_id=a\tb",
    "/tools/calendar?owner=other", "/tools/calendar?draft_id=a", "/tools/calendar#fragment",
    "/tools/degree", "/tools/import/../tasks", "/oauth/approve?decision=allow"])(
    "rejects unsafe destinations %s", value => {
      expect(toolReviewReturnPath(outer(value), origin)).toBeNull();
      expect(toolReviewLoginUrl(value, origin)).toBeNull();
    });
  it("rejects duplicate or additional outer parameters", () => {
    const valid = outer("/tools/tasks?draft_id=draft_123");
    expect(toolReviewReturnPath(valid + "&return_to=%2Ftools%2Fimport", origin)).toBeNull();
    expect(toolReviewReturnPath(valid + "&owner=another", origin)).toBeNull();
  });
});
