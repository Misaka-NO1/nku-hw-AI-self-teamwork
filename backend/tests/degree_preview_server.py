"""Loopback-only anonymous browser QA; no production auth or storage."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from app.api.degree_page import install_degree_page_routes
from app.core.envelope import success, failure
from app.core.errors import AppError

app = FastAPI()
analysis_requests = 0

@app.middleware("http")
async def count_analysis(request, call_next):
    global analysis_requests
    if request.method == "POST" and request.url.path == "/api/v1/degree/page/observation":
        analysis_requests += 1
    return await call_next(request)

@app.get("/qa/metrics")
def metrics():
    return {"scope": "loopback QA only", "analysis_requests": analysis_requests,
            "personal_data_persisted": False}
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5179"], allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-CSRF-Token", "X-Campus-Session-Read"])

@app.exception_handler(AppError)
async def error(request, exc):
    return JSONResponse(status_code=exc.status_code, content=failure(request_id="anonymous-local-qa", code=exc.code, message=exc.message).model_dump(mode="json"))

@app.get("/api/v1/auth/cloudbase/browser-session")
def session():
    return success({"workspace_ref": "anonymous-qa", "csrf_token": "fictional-local-qa", "expires_at": "2099-01-01T00:00:00Z",
                    "dataset_kind": "demo", "personal_uploads": False, "agent_paired": False}, request_id="anonymous-local-qa")

def authorize(request: Request):
    if request.headers.get("Origin") != "http://127.0.0.1:5179" or request.headers.get("X-CSRF-Token") != "fictional-local-qa":
        raise AppError(403, "FORBIDDEN", "Anonymous QA request only")

install_degree_page_routes(app, authorize)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8019, access_log=False)
