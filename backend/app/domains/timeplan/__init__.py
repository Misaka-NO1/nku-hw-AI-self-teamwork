"""B 负责的时间规划领域：空档查询、事件冲突与截止前可行性。

公共接口映射（见 contracts/integration-conventions.md）：

- ``find_free_slots`` → REST ``POST /api/v1/time/free-slots`` / MCP ``query_free_time``
- ``check_time_plan`` → REST ``POST /api/v1/time/check`` / MCP ``check_time_plan``

纯函数，不处理 HTTP、数据库或身份。
"""

from app.domains.timeplan.service import check_time_plan, find_free_slots

__all__ = ["check_time_plan", "find_free_slots"]
