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
from app.core.platform_query import PLATFORM_OPERATIONS, decode_platform_query, platform_input_schema


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
        descriptions = dict(DESCRIPTIONS)
        if self.runtime.public_catalog_profile == "published":
            descriptions.update({
                "search_scenic_spots": "Search the authorized user-recorded Nankai Jinnan scenic catalog. Interpret user intent flexibly: strolling/relaxing uses activity:walk, couples/date uses activity:date, picnic activity:picnic, photos activity:photo, landmarks activity:landmark; physical scenes include scene:grassland, scene:bridge, scene:path, scene:garden, scene:grove, scene:plaza. These activity labels are curated recommendations, not official guarantees. A stroll is not restricted to buildings or lakes. Tags in one query mean ALL must match: alternatives require separate queries and union by spot_id, not an impossible conjunction. For general flowers use flower/month=null/limit=20; list distinct flower species excluding generic category and activity:/scene: tags. Buildings architecture, autumn foliage, lakeside waterside, lawns landscape. All 34 spots require union of these five categories; one limit=20 query may truncate. Return actual map_url after choosing a spot. Never invent navigation, quietness, access permissions or live bloom conditions.",
                "search_study_materials": "List ALL authorized original review files for the selected course and semester: default topic=null and limit=20, not 1 or 2. Return every file with download_url/file_name/file_format, not a best-file recommendation or lecture. Only filter a topic if explicitly requested. Query all 9 known course IDs separately for the whole library; no single query covers all courses. Original files download as attachments, not the material_url preview or the school application page. Never expose private or pending materials.",
            })
        for name, definition in OPERATIONS.items():
            tools.append(Tool(
                name=name, description=descriptions[name],
                input_schema=boundary_schema(definition), output_schema=boundary_schema("ApiEnvelope"),
                annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False),
            ))
        if self.runtime.mcp_enable_platform_compat_tools:
            for name, operation in PLATFORM_OPERATIONS.items():
                tools.append(Tool(
                    name=name, description="Platform JSON-text adapter. " + descriptions[operation],
                    input_schema=platform_input_schema(), output_schema=boundary_schema("ApiEnvelope"),
                    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False),
                ))
        return tools

    async def call_tool(self, name, arguments, context=None):
        platform_operation = (PLATFORM_OPERATIONS.get(name)
                              if self.runtime.mcp_enable_platform_compat_tools else None)
        if name not in OPERATIONS and platform_operation is None:
            return await super().call_tool(name, arguments, context)
        request_id = str(uuid4())
        try:
            payload = decode_platform_query(arguments) if platform_operation else arguments
            body = execute_domain(platform_operation or name, payload, public_principal(mcp=True), self.runtime, request_id)
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
