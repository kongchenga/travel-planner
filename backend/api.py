import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.agent_runner import AgentRunner
from backend.auth import verify_token
from src.tools.cache import get_cache_stats, clear_cache
from src.tools.amap import amap_poi_search as search_pois

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

# -- Rate limiter --
limiter = Limiter(key_func=get_remote_address)

# -- App --
app = FastAPI(title="Travel Planner API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# -- Auth middleware (for /api/*) --
app.middleware("http")(verify_token)

# -- CORS --
ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
custom_origin = os.getenv("CORS_ORIGIN")
if custom_origin:
    ALLOWED_ORIGINS.append(custom_origin)

use_wildcard = not custom_origin and not os.getenv("API_AUTH_TOKEN")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if use_wildcard else ALLOWED_ORIGINS,
    allow_credentials=not use_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

if use_wildcard:
    log.warning("CORS allow_origins=* (no auth token, no CORS_ORIGIN set)")

# -- Runner --
runner = AgentRunner()
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# -- Models --
class PlanRequest(BaseModel):
    destination: str | None = Field(None, max_length=100)
    origin: str | None = Field(None, max_length=100)
    start_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    travelers: int = Field(default=1, ge=1, le=100)
    budget: float | None = Field(None, ge=0, le=1_000_000)
    currency: str = Field(default="CNY", max_length=10)
    interests: list[str] = Field(default=["观光"], max_length=20)
    special_requirements: str | None = Field(None, max_length=2000)
    selected_pois: list[dict] = Field(default_factory=list, max_length=50)


class PoiSearchRequest(BaseModel):
    keywords: str = Field(..., max_length=100)
    city: str = Field("", max_length=50)
    types: str = Field("", max_length=20)
    offset: int = Field(25, ge=1, le=25)
    page: int = Field(1, ge=1, le=5)


class PoiData(BaseModel):
    id: str = ""
    name: str = ""
    address: str = ""
    location: str = ""
    tel: str = ""
    type: str = ""
    rating: str = ""
    cost: str = ""


# -- Routes --
@app.post("/api/plan")
@limiter.limit("30/minute; 100/hour; 300/day")
async def create_plan(req: PlanRequest, request: Request):
    travel_request = req.model_dump()
    try:
        session_id = await runner.start_plan(travel_request)
        return {"session_id": session_id}
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


@app.post("/api/poi/search")
@limiter.limit("60/minute")
async def poi_search(req: PoiSearchRequest, request: Request):
    try:
        results = search_pois(
            keywords=req.keywords,
            city=req.city,
            types=req.types,
            offset=req.offset,
            page=req.page,
            extensions="all",
        )
        return {"results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache")
async def cache_status():
    return get_cache_stats()


@app.delete("/api/cache")
async def cache_clear():
    clear_cache()
    return {"status": "cleared"}


@app.get("/api/plan/{session_id}/stream")
async def plan_stream(session_id: str, request: Request):
    async def generate():
        async for chunk in runner.event_stream(session_id):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    full_path = full_path.strip("/")
    if full_path.startswith("api/") or full_path == "api" or ".." in full_path or "~" in full_path:
        raise HTTPException(status_code=404)
    fpath = FRONTEND_DIR / full_path
    if fpath.exists() and fpath.is_file():
        return FileResponse(fpath)
    return FileResponse(FRONTEND_DIR / "index.html")


# -- Startup / Shutdown --
@app.on_event("startup")
async def startup():
    log.info("server starting on port %s", os.getenv("PORT", "8000"))


@app.on_event("shutdown")
async def shutdown():
    log.info("server shutting down")


# -- Health check --
@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.api:app", host="0.0.0.0", port=port, reload=False)
