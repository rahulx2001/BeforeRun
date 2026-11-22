from __future__ import annotations

import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from beforerun.app import STATIC_DIR


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.disabled_fieldsets = 0
        self.commands: list[str] = []
        self.scripts: list[str] = []
        self._command_select = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "fieldset" and "disabled" in attributes:
            self.disabled_fieldsets += 1
        if tag == "select" and attributes.get("name") == "command_context":
            self._command_select = True
        elif tag == "option" and self._command_select and attributes.get("value"):
            self.commands.append(attributes["value"] or "")
        elif tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._command_select = False


def test_form_is_enabled_for_supported_commands_and_real_review_script() -> None:
    parser = FormParser()
    markup = Path(STATIC_DIR, "index.html").read_text(encoding="utf-8")
    parser.feed(markup)
    assert parser.disabled_fieldsets == 0
    assert parser.commands == ["review_only", "npm_install"]
    assert "/static/reviews.js" in parser.scripts
    assert "We read selected source as data; we do not run it." in markup
    assert "cloud model through OpenClaw" in markup
    assert "this form is inactive" not in markup


def test_renderer_uses_inert_dom_writes_and_stale_job_guards() -> None:
    script = Path(STATIC_DIR, "reviews.js").read_text(encoding="utf-8")
    for forbidden in (".innerHTML", ".outerHTML", "insertAdjacentHTML", "eval(", "new Function"):
        assert forbidden not in script
    assert ".textContent" in script
    assert "replaceChildren" in script
    assert "ticket !== generation" in script
    assert "activeJob !== jobId" in script
    assert 'parsed.hostname !== "github.com"' in script
    assert 'value.rel = "noopener noreferrer"' in script
    assert 'fetch("http' not in script
    assert "fetch('http" not in script
    assert "OPENCLAW_GATEWAY_TOKEN" not in script
    assert "CEREBRAS_API_KEY" not in script
    assert "BASETEN_API_KEY" not in script
    assert "automatic_fallback_configured" in script
    assert "Muse Spark Open on Baseten" in script


def test_real_line_numbers_replace_virtual_source_counters() -> None:
    script = Path(STATIC_DIR, "reviews.js").read_text(encoding="utf-8")
    styles = Path(STATIC_DIR, "styles.css").read_text(encoding="utf-8")
    assert "evidence.span.first_line + index" in script
    assert 'derived ? "·" : evidence.span.first_line + index' in script
    assert "rows are not literal source lines" in script
    assert ".actual-line-number" in styles
    assert ".actual-source" in styles


def test_new_review_cancels_the_active_server_job() -> None:
    script = Path(STATIC_DIR, "reviews.js").read_text(encoding="utf-8")
    assert "const previousJob = activeJob;" in script
    assert "api(`/api/reviews/${previousJob}/cancel`" in script


def test_javascript_syntax_with_available_node() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable; static DOM contracts still ran, syntax check did not.")
    for name in ("shell.js", "reviews.js"):
        result = subprocess.run(
            [node, "--check", str(Path(STATIC_DIR, name))],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr
