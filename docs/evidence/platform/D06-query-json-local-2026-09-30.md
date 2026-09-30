# D06 query_json兼容层本地验收

状态：LOCAL_PASS；未更新云服务、未发布或同步兼容插件，学校平台兼容工具未验收。用户只批准本地实现/测试/准备候选。

修改D薄适配、配置、资源清单门禁、打包/解压验收脚本及测试；不改A/B/C算法、冻结api/core Schema、REST路径或原MCP输入输出。新增6个只读platform_*工具的唯一外层String参数query_json，完整解析为原对象后走相同execute_domain/权限/信封。默认关闭，兼容开关必须与业务开关、7或13工具清单匹配，否则拒绝启动。

详细契约及null/字符串null区别见 [传输扩展](../../../contracts/platform-mcp-compat.md)。兼容及清单新增53项测试先得到267 passed；另修复审计wire dict的isError识别并加8项测试，最终后端275 passed，1条既有第三方弃用warning，7.18秒。命令（backend目录）：

```powershell
.\.venv\Scripts\python.exe -m pytest -o "addopts=-p no:cacheprovider" -q
```

覆盖7组REST/原MCP/兼容MCP等价，真正null/空数组/中文/空字符串/字面"null"、数字/布尔不强转、重复键/非法JSON/非对象根/NaN/Infinity/溢出/Unicode/大小/深度限制、资源引用/浏览器工作区隔离/非夹具课表/依赖异常脱敏、默认关闭及清单开关匹配。首批兼容测试51项通过，另2项是清单测试。原7工具的input/output Schema保持逐项相等。

旧审计只读SDK模型的is_error，忽略公开middleware也可能收到wire dict中的isError；候选同时识别两种返回，真实SDK业务错误日志outcome=error回归通过。只改记录判断，不改响应或鉴权，不记录参数/异常正文；旧云端004日志仍是原值，不追改历史证据。

原源树7工具HTTP/MCP对照与单探针/本地虚构任务确认幂等/重启持久化检查也通过，均platform_verified=false；兼容开关在隔离基线脚本中显式关闭，不因外部环境变量改变测试范围。

打包命令（仓库根）：`Build-Package.ps1 -PlatformCompat`；解压包用临时随机令牌在本机HTTP实际验证，无云令牌/持久MCP数据库。正式候选的实际解压运行结果如下，不能将其冒充云端或Docker镜像通过。

## 最终兼容候选指纹与真实本机HTTP

- 源码提交：`853d17dd3557d8872f0f78e5f13a12acadc514f1`；后续证据文档提交不是此包源码。
- BUILD_ID：`cloudbase-demo-readonly-20260930-853d17dd-platform-compat`。
- ZIP：本机忽略目录 `deploy/cloudbase-demo-readonly/dist/cloudbase-demo-readonly-20260930-853d17dd-platform-compat-181928.zip`，不提交Git。
- SHA256：`b2d3da2c78009492644c8a5f611f1a90d7211569a25ac0bc1be2edf9ac30c0cb`。
- 63条目，included_source_dirty=false，source_sha_verified=true。
- 清单明确原7工具+新增6兼容工具；不包含令牌/.env/数据库/日志/测试/前端或私有资料。

实际命令（backend目录）：

```powershell
.\.venv\Scripts\python.exe scripts/check_domain_bundle.py "D:\code\华为ai比赛\deploy\cloudbase-demo-readonly\dist\cloudbase-demo-readonly-20260930-853d17dd-platform-compat-181928.zip"
```

结果ok=true，scope=extracted_zip_loopback_only；MCP导入解压包，不使用源码包冒充。无/错Bearer拒绝，正确临时令牌初始化/13工具发现/nonce/build通过；原REST/MCP7成功+1失败等价，原MCP/兼容MCP另外7成功+1失败等价。真正null/[]/中文保真，字面字符串"null"不强转，浏览器工作区及非夹具拒绝，正文/索引/私有资料过滤，重复键/NaN/错误根类型拒绝全部通过。

`platform_verified=false`、`container_image_verified=false`、personal_uploads=false、mcp_persistent_database=false。本机不进行Docker镜像构建；云服务004仍没有此兼容代码或修复后的审计。

另按同一已提交源码生成普通7工具回归包（未加PlatformCompat），实际解压HTTP检查也ok=true、7成功/1失败等价与身份/正文边界通过，兼容工具未发现。它仅证明默认关闭的向后兼容性，不是待部署的兼容候选：build=cloudbase-demo-readonly-20260930-853d17dd，63条目，dirty=false，SHA256=aa0db6a590de7af777633233906aeb80e87954834b30aa109b88223a62857c4d。候选发布时务必选上面的 `-platform-compat` 包。

下一步仍需单独确认云端发布及团队兼容插件范围，实际验证学校生成的query_json值和返回，再逐项启用原先禁用两类。此次没有开启公网、改数据库或发布主Agent。旧令牌风险未消除。
