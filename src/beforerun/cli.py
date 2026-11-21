"""Generic development-server entry point; no investigation behavior."""

import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BeforeRun interface scaffold.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)
    uvicorn.run("beforerun.app:app", host=args.host, port=args.port, reload=args.reload)
