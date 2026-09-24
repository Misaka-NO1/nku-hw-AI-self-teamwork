"""B 负责的课程表领域：TimetableImport 校验与课表周次展开。

公共接口映射（见 contracts/integration-conventions.md）：

- ``validate_timetable`` → REST ``POST /api/v1/schedules/validate`` / MCP ``validate_timetable``
- 本模块只做纯业务计算，不处理 HTTP、数据库或身份；薄适配由 D 负责。
"""

from app.domains.schedule.service import (
    SHANGHAI_TZ,
    expand_occurrences,
    export_ics,
    validate_timetable,
)

__all__ = [
    "SHANGHAI_TZ",
    "expand_occurrences",
    "export_ics",
    "validate_timetable",
]
