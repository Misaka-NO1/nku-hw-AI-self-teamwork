"""Official SDK extension exposing the exact frozen business schemas."""

import json
import logging
from uuid import uuid4

from mcp.server import MCPServer
from mcp_types import CallToolResult, TextContent, Tool, ToolAnnotations

from app.core.config import Settings
from app.core.contracts import boundary_schema
from app.core.domain_adapter import OPERATIONS, execute_domain, public_principal
from app.core.envelope import failure
from app.core.errors import AppError


logger = logging.getLogger(__name__)
DESCRIPTIONS = {
    "validate_timetable": "Validate the fixed fictional timetable only; never save or import personal data.",
    "query_free_time": "Read fixed demo arrangements; availability is limited to known arrangements, not a student's live schedule.",
    "check_time_plan": "Check demo event conflicts or deadline feasibility; missing times require confirmation; never save tasks.",
    "search_scenic_spots": "Search fictional demo spots only; historical bloom periods are not live observations.",
    "search_study_materials": "Search authorized public demo materials with real source excerpts; index-only entries cannot support body answers.",
    "audit_degree_progress": "Audit fixed demo plan/transcript references only; not an official graduation decision.",
}


class DomainMCPServer(MCPServer):
    """Extend SDK public list/call methods; do not mutate its private tool registry."""

    def __init__(self, runtime: Settings, **kwargs):
        self.runtime = runtime
        super().__init__(**kwargs)

    async def list_tools(self):
        tools = await super().list_tools()
        for name, definition in OPERATIONS.items():
            tools.append(Tool(
                name=name, description=DESCRIPTIONS[name],
                input_schema=boundary_schema(definition), output_schema=boundary_schema("ApiEnvelope"),
                annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False),
            ))
        return tools

    async def call_tool(self, name, arguments, context=None):
        if name not in OPERATIONS:
            return await super().call_tool(name, arguments, context)
        request_id = str(uuid4())
        try:
            body = execute_domain(name, arguments, public_principal(mcp=True), self.runtime, request_id)
        except AppError as exc:
            body = failure(request_id=request_id, code=exc.code, message=exc.message,
                           field_errors=exc.field_errors, retryable=exc.retryable)
        except Exception:
            # Do not log arguments, file contents or exception text.
            logger.error("Domain dependency failed", extra={"request_id": request_id, "tool_name": name})
            body = failure(request_id=request_id, code="DEPENDENCY_UNAVAILABLE",
                           message="Domain dependency unavailable", retryable=True)
        data = body.model_dump(mode="json")
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
                              structured_content=data, is_error=not body.ok)
