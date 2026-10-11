from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.cloud_tasks_site import RequestBodyLimit


def client():
    app = FastAPI()
    app.add_middleware(RequestBodyLimit)
    @app.post("/{path:path}")
    async def echo(request: Request, path: str):
        return {"bytes": len(await request.body())}
    return TestClient(app)


def test_degree_analysis_accepts_larger_table_without_widening_original_routes():
    c = client()
    data = b"x" * 40000
    assert c.post("/api/v1/degree/page/observation", content=data).json() == {"bytes": 40000}
    assert c.post("/api/v1/degree/page/analyze", content=data).status_code == 200
    assert c.post("/api/v1/degree/audit", content=data).status_code == 413
    assert c.post("/api/v1/schedules/import-drafts", content=data).status_code == 413


def test_degree_chunked_upload_still_has_one_megabyte_limit():
    c = client()
    body = (b"x" * 262144 for _ in range(5))
    assert c.post("/api/v1/degree/page/observation", content=body).status_code == 413
