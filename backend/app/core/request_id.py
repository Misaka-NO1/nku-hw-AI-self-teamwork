import re
from uuid import uuid4

from starlette.requests import Request


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def resolve_request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid4())


def current_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))
