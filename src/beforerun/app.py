"""Application skeleton: static interface and a health endpoint only."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from beforerun import __version__

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="BeforeRun scaffold",
    version=__version__,
    description="Development skeleton. Core investigation functionality is not implemented.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "scaffold", "version": __version__}
