"""Static application and OpenAPI surface checks for the connected local MVP."""

from fastapi.testclient import TestClient

from beforerun.app import app


def test_health_static_routes_and_security_headers() -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["phase"] == "mvp"
        assert response.json()["readiness_claimed"] is False

        for path in (
            "/",
            "/static/styles.css",
            "/static/shell.js",
            "/static/reviews.js",
            "/static/icons.svg",
            "/static/mark.svg",
            "/static/review-illustration.svg",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.content, path
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["x-frame-options"] == "DENY"


def test_openapi_exposes_only_owned_api_surface() -> None:
    paths = set(app.openapi()["paths"])
    assert "/health" in paths
    assert "/api/capabilities" in paths
    assert "/api/reviews" in paths
    assert "/api/reviews/{review_id}" in paths
    assert "/api/reviews/{review_id}/events" in paths
    assert "/api/reviews/{review_id}/evidence/{evidence_id}" in paths
    assert "/api/reviews/{review_id}/cancel" in paths
    assert "/api/reviews/{review_id}/export" in paths
    assert not any("openclaw" in path.lower() or "cerebras" in path.lower() for path in paths)
    assert not any("questions" in path or "execute" in path for path in paths)
