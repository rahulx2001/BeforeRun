"""Offline defaults fail on accidental networking or submitted-code execution."""

import os
import socket
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src/beforerun/static"


def pytest_ignore_collect(collection_path, config):
    # Live modules may load private .env settings during import. Keep them entirely
    # outside offline collection, not merely deselected after their import side effects.
    if collection_path.name.startswith("test_") and "live" in collection_path.stem:
        expression = config.getoption("markexpr") or ""
        return "live" not in expression or "not live" in expression
    return None


@pytest.fixture(autouse=True)
def offline_boundary(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        if (
            os.environ.get("BEFORERUN_RUN_LIVE_TESTS") != "1"
            and os.environ.get("BEFORERUN_LIVE_OPENCLAW") != "1"
        ):
            pytest.fail("Live tests require explicit BEFORERUN_RUN_LIVE_TESTS=1 authorization.")
        return

    def no_network(*args, **kwargs):
        raise AssertionError("An offline test attempted a real network connection.")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    original = subprocess.Popen

    def safe_process(args, *positional, **kwargs):
        if not isinstance(args, (tuple, list)) or not args:
            raise AssertionError("Offline tests cannot launch a shell or submitted code.")
        executable = Path(args[0]).name.lower()
        syntax = (
            executable == "node"
            and len(args) == 3
            and args[1] == "--check"
            and Path(args[2]).resolve() in {STATIC / "shell.js", STATIC / "reviews.js"}
        )
        browser = (
            request.node.get_closest_marker("browser")
            and "--headless" in args
            and "--host-resolver-rules=MAP * ~NOTFOUND" in args
            and any(
                str(value).startswith("--user-data-dir=") and "beforerun-browser-" in str(value)
                for value in args
            )
            and executable in {"google chrome", "chromium", "google-chrome"}
        )
        if not syntax and not browser:
            raise AssertionError("An offline test attempted an unapproved process launch.")
        return original(args, *positional, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", safe_process)
