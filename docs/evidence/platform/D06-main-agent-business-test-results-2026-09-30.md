# D06：主Agent业务联调执行记录

日期：2026-09-30，北京时间。当前只完成发布前探针复测及两类禁用；新版插件尚未发布，主Agent业务尚未绑定/验收。此记录不代替[测试计划](D06-main-agent-business-test-plan-2026-09-30.md)。

## 登录恢复与禁用保存

用户重新登录的是新插件标签页；旧标签页仍在IAM登录。切换到真实登录的工具列表，两类仍启用，证明前次网络错误禁用没有保存。仅将check_time_plan、validate_timetable禁用，页面两次“操作成功”，完成探针编辑后返回列表仍均禁用、未通过；四类业务保持通过/启用。两类配置保留，不修改公共接口或算法。

## 本轮探针复测

按本轮授权仅开放同一服务默认HTTPS入口，保留鉴权、内网关闭，其他服务/数据库/实例下限/令牌不变。

前置检查：15:30:31健康200（218.35ms），15:30:32无Bearer401（68.08ms）、随机错误Bearer401（149.4ms）。脚本未读取或测试正确令牌。

学校使用用户此前保存的保密配置Debug health_probe，实际返回isError=false，structuredContent及content.text均包含：

```json
{
  "nonce": "d06-ma-20260930-probe-4c813e7af029",
  "build_id": "cloudbase-demo-readonly-20260930-cda01c67",
  "server_time": "2026-09-30T15:30:47+08:00"
}
```

随机标识匹配，构建号与004一致；平台调试成功，点完成保存，列表health_probe显示通过/启用。云端004审计15:30:48：method=tools/call、JSON-RPC request_id=2、protocol_version=2025-06-18、tool_name=health_probe、duration_ms=0.53、outcome=ok；不混用历史id，也不记录传输会话ID。

## 发布范围确认阻塞

五个启用工具均通过，两类禁用工具未通过。点“发布”只打开确认框，平台仍提示“当前插件存在以下Debug未通过的工具，可能会影响智能体的调用，请谨慎操作”，并列出check_time_plan、validate_timetable。

不能由禁用开关推断两类一定不纳入发布配置，也不能由警告断言禁用失效。用户原授权仅发布已验证5类，因此未点最终“确定”，先取消；读回确定按钮不可见，确认取消。需要明确是否允许带两类禁用配置发布，再限制主Agent只绑定5类。

按人工阻塞门禁关闭服务公网并读回公网/内网均关闭。未发布新版插件或主Agent、未上架、未新增主Agent绑定、未更改数据权限。再次只读打开同一发布确认框供用户看具体警告，尚未确认；不会在等待时重新开启公网。

本机证据截图（忽略目录，不提交Git）：deploy/cloudbase-demo-readonly/dist/D06-publish-disabled-tools-warning-20260930.png，显示警告、两类工具名及确认/取消按钮，无令牌。
