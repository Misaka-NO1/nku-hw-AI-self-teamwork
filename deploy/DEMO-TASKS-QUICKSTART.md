# 本机待办闭环测试

在接手工作区根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deploy/Start-Demo.ps1 -Port 8012
```

然后打开 `http://127.0.0.1:8012/tools/tasks`。终端需保持运行。
脚本仅对本次进程使用 ExecutionPolicy Bypass，不修改系统执行策略；不自动安装软件。
需先有本仓库 backend/.venv 与 node_modules；端口已占用时选其他端口，不停止其他程序。

点击“开始虚构数据测试”，从三份通知中选择并生成草稿，核对后点确认保存。
只有服务器返回 task_id 才算成功。含糊通知可查看但不能保存；切换/取消/刷新不创建任务。
重复提交保留相同确认与提交幂等键，避免网络丢包或刷新产生重复。

本机记录存于忽略的 `backend/data/interactive-demo.db`，不是浏览器文件，也不是 Git 数据。
关闭/重启服务器不会抹除有效记录；工作区 24 小时后不可再访问，后端会清理过期测试数据。
sessionStorage 只缓存虚构 workspace/CSRF/幂等键，Cookie 为 HttpOnly，不包含云服务密钥。

这里只验收固定虚构数据。任意通知编辑、个人课表、可信学校账号、生产部署仍不开放。
独立云测试部署见 [CloudBase 待办测试站](cloudbase-tasks-demo/README.md)，不能把本机 SQLite
数据文件放进无持久挂载的云容器并冒称云端数据库。
