"""Regression checks for the existing scaffold, not scanner behavior."""

from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from beforerun.app import STATIC_DIR, app


class ReviewFormParser(HTMLParser):
    """Read only the markup properties needed by the scaffold contract."""

    def __init__(self) -> None:
        super().__init__()
        self.disabled_fieldsets = 0
        self.command_options: list[str] = []
        self._in_command_select = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "fieldset" and "disabled" in attributes:
            self.disabled_fieldsets += 1
        if tag == "select" and attributes.get("name") == "command_context":
            self._in_command_select = True
        elif tag == "option" and self._in_command_select:
            value = attributes.get("value")
            if value is not None:
                self.command_options.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._in_command_select = False


def test_health_and_static_scaffold_routes() -> None:
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["phase"] == "scaffold"

    for path in (
        "/",
        "/static/styles.css",
        "/static/shell.js",
        "/static/icons.svg",
        "/static/mark.svg",
        "/static/review-illustration.svg",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content, path


def test_review_form_is_disabled_and_limited_to_the_master_scope() -> None:
    parser = ReviewFormParser()
    parser.feed(Path(STATIC_DIR, "index.html").read_text(encoding="utf-8"))

    assert parser.disabled_fieldsets == 1
    assert parser.command_options == ["review_only", "npm_install"]


def test_scaffold_does_not_advertise_a_review_api() -> None:
    client = TestClient(app)

    assert set(app.openapi()["paths"]) == {"/health"}
    assert client.get("/api/reviews").status_code == 404
