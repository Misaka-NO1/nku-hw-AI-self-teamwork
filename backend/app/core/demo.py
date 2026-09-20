import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.core.errors import AppError
from app.core.security import payload_hash


FIXTURE_SET_ID = "demo-v1"
REPOSITORY_ROOT = Path(__file__).parents[3]
FIXTURES_ROOT = REPOSITORY_ROOT / "fixtures"


@lru_cache
def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_ROOT / name).read_text(encoding="utf-8"))


@lru_cache
def allowed_hashes(kind: Literal["schedule", "task"]) -> frozenset[str]:
    if kind == "schedule":
        names = ["timetable.demo.json"]
    else:
        names = [
            "notice-ambiguous.demo.json",
            "notice-deadline.demo.json",
            "notice-event.demo.json",
        ]
    return frozenset(payload_hash(load_fixture(name)) for name in names)


def enforce_demo_fixture(payload: dict[str, Any], kind: Literal["schedule", "task"]) -> str:
    digest = payload_hash(payload)
    if digest not in allowed_hashes(kind):
        raise AppError(
            status_code=403,
            code="DEMO_ONLY",
            message="This deployment only accepts checked-in fictional fixtures",
        )
    return digest
