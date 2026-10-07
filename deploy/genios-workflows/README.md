# D06 固定课表参数工作流

目的：解决模型手抄长 JSON 时遗漏末尾括号的问题，不在后端修补无效输入，不放宽契约。

仅使用仓库公开虚构夹具 `fixtures/timetable.demo.json`。不接受真人课表、任意 URL、文件路径、令牌或身份参数；未知 `fixture_id` 必须报错。

## 本地检查

```powershell
node deploy/genios-workflows/test-timetable-fixture-handler.cjs
```

测试比较完整对象与原始夹具、精确字符串（1606 字符）、重复执行稳定性，以及未知/错误类型标识拒绝。夹具将来更新时需同步代码常量、长度断言并重新做平台验收，不能只更新其中一份。

## NK-GeniOS 草稿配置

- 名称：`WF_D06_TimetableFixture_Test`
- 工作流 ID：`davll3d4shhbpg8v1lm0`
- 所属：团队工作区 `datqfnm9t58vf5r4v1eg`
- 经负责人明确确认，2026-10-02 16:01:33 发布团队测试版本 `v0.1.0`，绑定主 Agent 测试草稿。主 Agent 未发布、未上架。

```text
Start.fixture_id (String, required)
  → 代码01.handler(params)
      fixture_id ← Start.fixture_id
      query_json (String) = JSON.stringify(固定夹具)
      fixture_id (String)
  → 插件01：campus-tools-dev / platform_validate_timetable
      query_json ← 代码01.query_json（变量引用，不二次 stringify）
      校验 isError 作为异常 = 开启
      异常忽略 = 无
  → End.result (Object) ← 插件01.structuredContent
```

代码节点源码见 `timetable-fixture-handler.js`。连好执行边后才能选择前置节点变量。

## 验收边界（2026-10-02）

1. 本地固定参数测试通过；学校代码节点单步正常、异常、重复执行通过。
2. 学校纯生成链 `Start → 代码01 → End.query_json` 整体测试通过：两次正常输出均与原始夹具精确相同，未知标识在代码节点停止，End 未执行。
3. 插件链初次配置遇学校会话过期。重新登录后读回发现插件选择/错误开关已保存，但执行边和变量映射未保存；已重新配置并完成真实端到端验证。
4. 完整链两次正常调用成功：输入精确1606字符，isError=false、Envelope ok=true/error=null、normalized_payload与夹具相同、payload_hash符合下述预期，重复响应data一致。未知标识在代码节点拒绝，插件业务节点和End未执行。
5. 刷新后读回三条执行边、query_json引用、isError错误开关及End.result对象映射，确认持久化。
6. 经明确授权发布后，主Agent草稿实际调用通过：显式工作流请求及自然语言重复请求都传入 `fixture_id=timetable.demo`，返回ok=true、相同payload_hash和各自真实request_id；unknown-fixture原样传入后失败，无成功回退。
7. 个人课表请求未进入演示工作流，不承诺获取/保存，不索取密码/Cookie。新增可信身份/授权接口未接入的边界说明后再次测试通过。
8. 当前仅修复并验收固定虚构课表的长JSON传参缺口，不等于个人课表、数据库或整个项目已经上线。主Agent最终发布、其他业务全量当前回归仍需单独验收。

已核对的预期 payload_hash：

```text
643fef057c3c6503a888a84727f2f9d7a497558b37b0087d6887b3973f725335
```

未知标识不得执行插件业务调用或得到成功结果（平台可能预先进行插件初始化/握手）。测试工作流已获授权发布并绑定；主Agent仅草稿，禁止将本次测试版本当作生产发布。

最新云健康、鉴权和平台实证见 `docs/evidence/platform/D06-takeover-preflight-2026-10-02.md`。
