import { describe, expect, it } from "vitest";
import { oauthReturnPath } from "./oauthReturn";
const origin = "https://pilot.example.invalid";
const query = new URLSearchParams({response_type:"code", client_id:"fictional-agent", redirect_uri:"https://coze.nankai.edu.cn/product/llm/info/oauth", scope:"demo:read", state:"fictional-state-only", code_challenge:"fictional-public-challenge", code_challenge_method:"S256"});
const valid = "/oauth/authorize?"+query;
const outer = (value: string) => "?"+new URLSearchParams({return_to:value});
describe("OAuth login return target", () => {
  it("returns only the same-origin consent path", () => expect(oauthReturnPath(outer(valid),origin)).toBe(valid));
  it.each(["https://attacker.invalid/", "//attacker.invalid/", "/oauth/approve?decision=allow", "/tools/tasks", valid+"#secret", valid+"&access_token=secret", valid+"&state=duplicate", "/oauth/authorize?client_id=only"]) ("rejects unsafe or malformed destination %s", value => expect(oauthReturnPath(outer(value),origin)).toBeNull());
  it("rejects duplicate outer return parameters", () => expect(oauthReturnPath(outer(valid)+"&return_to="+encodeURIComponent(valid),origin)).toBeNull());
  it("resumes five-field read-only competition consent, never auto-approves", () => {
    const five = new URLSearchParams(query);
    five.delete("code_challenge"); five.delete("code_challenge_method"); five.set("state", "a123456789");
    const path = "/oauth/authorize?" + five;
    expect(oauthReturnPath(outer(path), origin)).toBe(path);
    for (const [key, value] of [["scope", "demo:read demo:draft"], ["state", "short"], ["redirect_uri", "https://attacker.invalid"]]) {
      const bad = new URLSearchParams(five); bad.set(key,value);
      expect(oauthReturnPath(outer("/oauth/authorize?"+bad),origin)).toBeNull();
    }
  });
  it.each(["demo:read tasks:read", "demo:read tasks:read tasks:write", "demo:read devices:bind", "demo:read tasks:read devices:bind", "demo:read tasks:read tasks:write devices:bind"])("resumes explicit personal-task consent %s without auto-approving", scope => {
    const five = new URLSearchParams(query);
    five.delete("code_challenge"); five.delete("code_challenge_method");
    five.set("scope", scope);
    const path = "/oauth/authorize?" + five;
    expect(oauthReturnPath(outer(path), origin)).toBe(path);
  });
  it.each(["tasks:write", "demo:read tasks:write", "demo:read tasks:read tasks:write admin", "demo:read  tasks:read"])("rejects unrecognized scope expansion %s", scope => {
    const five = new URLSearchParams(query);
    five.delete("code_challenge"); five.delete("code_challenge_method");
    five.set("scope", scope);
    expect(oauthReturnPath(outer("/oauth/authorize?" + five), origin)).toBeNull();
  });
});
