"""BeforeRun local application: static product surface and owned review jobs."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from beforerun import __version__
from beforerun.features.pipeline import CheckedReviewPipeline
from beforerun.features.review_service import ReviewService
from beforerun.features.routes import router
from beforerun.features.settings import get_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


def reviews_enabled() -> bool:
    """Explicit operator opt-in; never derived from browser input or liveness."""
    return os.environ.get("BEFORERUN_ENABLE_REVIEWS") == "1"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    yield
    await application.state.review_service.close()


app = FastAPI(
    title="BeforeRun",
    version=__version__,
    description="Bounded, evidence-first public GitHub source reviews. Never a safety guarantee.",
    lifespan=lifespan,
)
app.state.review_service = ReviewService(
    get_settings(),
    CheckedReviewPipeline.with_npm(get_settings()),
    reviews_enabled=reviews_enabled(),
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/") else "no-cache"
    )
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health(request: Request) -> dict[str, str | bool]:
    """Liveness only. A healthy process does not imply model/source/scanner readiness."""

    connected = request.app.state.review_service.pipeline_connected
    return {
        "status": "ok",
        "phase": "mvp",
        "version": __version__,
        "review_pipeline_connected": connected,
        "readiness_claimed": False,
    }
