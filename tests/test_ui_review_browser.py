"""Real Chrome DOM tests with a fresh profile and all application APIs mocked."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from beforerun.app import STATIC_DIR

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FIXTURES = Path(__file__).parent / "fixtures/jobs"


@pytest.mark.browser
def test_actual_browser_review_states_with_mocked_apis() -> None:
    executable = (
        str(CHROME)
        if CHROME.exists()
        else shutil.which("chromium") or shutil.which("google-chrome")
    )
    if not executable:
        pytest.skip("Chrome is unavailable; the browser gate remains unverified on this host.")
    fixture = json.loads((FIXTURES / "checked_result.json").read_text())
    driver = (FIXTURES / "browser_checks.js").read_text()
    bootstrap = (
        "const browserFixture = " + json.dumps(fixture).replace("<", "\\u003c") + ";\n" + driver
    )
    markup = (STATIC_DIR / "index.html").read_text()
    markup = markup.replace('"/static/', '"' + STATIC_DIR.as_uri() + "/")
    markup = markup.replace("<head>", "<head><script>" + bootstrap + "</script>", 1)
    with tempfile.TemporaryDirectory(prefix="beforerun-browser-") as directory:
        root = Path(directory)
        page = root / "review.html"
        page.write_text(markup)
        result = subprocess.run(
            [
                executable,
                "--headless",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--disable-extensions",
                "--disable-default-apps",
                "--disable-breakpad",
                "--host-resolver-rules=MAP * ~NOTFOUND",
                "--window-size=390,844",
                "--virtual-time-budget=10000",
                "--dump-dom",
                "--user-data-dir=" + str(root / "profile"),
                page.as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert result.returncode == 0, result.stderr[-1000:]
    assert 'data-browser-test="passed"' in result.stdout, result.stdout[-5000:]
