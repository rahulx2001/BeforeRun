"""Offline Baseten setup preservation and honest configured-policy API disclosure."""

from __future__ import annotations

import copy
import importlib.util
import json
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_review_api import BASE_URL, FakePipeline, make_service, post_review, wait_terminal

from beforerun.app import app
from beforerun.features.gateway_policy import (
    BASETEN_FALLBACK,
    BASETEN_MODEL,
    CEREBRAS_PRIMARY,
    GatewayModelPolicy,
)

SPEC = importlib.util.spec_from_file_location(
    "baseten_setup", Path(__file__).parent / "fixtures/demo/configure_baseten.py"
)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def initial_config():
    return {
        "models": {"providers": {"cerebras": {"apiKey": "inert-existing-key"}}},
        "agents": {
            "entries": {
                "beforerun-reviewer": {
                    "model": {"primary": CEREBRAS_PRIMARY, "fallbacks": []},
                    "tools": {"deny": ["*"]},
                    "contextInjection": "never",
                    "skills": [],
                },
                "unrelated": {"model": "unchanged"},
            }
        },
        "gateway": {"bind": "loopback", "auth": {"token": "inert-gateway-key"}},
    }


def test_native_fallback_merge_preserves_primary_isolation_and_unrelated_work():
    config = initial_config()
    before = copy.deepcopy(config)
    updated = setup.merge_gateway(config, "inert-baseten-key")
    assert config == before
    assert updated["gateway"] == before["gateway"]
    assert updated["models"]["providers"]["cerebras"] == before["models"]["providers"]["cerebras"]
    reviewer = updated["agents"]["entries"]["beforerun-reviewer"]
    assert reviewer["model"] == {"primary": CEREBRAS_PRIMARY, "fallbacks": [BASETEN_FALLBACK]}
    assert reviewer["tools"] == {"deny": ["*"]} and reviewer["contextInjection"] == "never"
    assert updated["models"]["providers"]["baseten"]["models"] == [
        {"id": BASETEN_MODEL, "name": "Muse Spark Open", "input": ["text"]}
    ]
    assert setup.merge_gateway(updated, "inert-baseten-key") == updated


def test_existing_authorized_fallbacks_models_and_allowlist_are_merged():
    config = initial_config()
    config["agents"]["entries"]["beforerun-reviewer"]["model"]["fallbacks"] = ["approved/other"]
    config["agents"]["defaults"] = {"models": {"approved/other": {"alias": "keep"}}}
    config["models"]["providers"]["baseten"] = {"models": [{"id": "other", "name": "Keep"}]}
    result = setup.merge_gateway(config, "inert-baseten-key")
    assert result["agents"]["entries"]["beforerun-reviewer"]["model"]["fallbacks"] == [
        "approved/other",
        BASETEN_FALLBACK,
    ]
    assert result["models"]["providers"]["baseten"]["models"][0]["id"] == "other"
    assert result["agents"]["defaults"]["models"]["approved/other"] == {"alias": "keep"}
    assert BASETEN_FALLBACK in result["agents"]["defaults"]["models"]


@pytest.mark.parametrize("change", ["primary", "tools", "endpoint"])
def test_unfamiliar_runtime_settings_are_rejected_without_mutation(change):
    config = initial_config()
    if change == "primary":
        config["agents"]["entries"]["beforerun-reviewer"]["model"]["primary"] = "other/model"
    elif change == "tools":
        config["agents"]["entries"]["beforerun-reviewer"]["tools"] = {"allow": ["exec"]}
    else:
        config["models"]["providers"]["baseten"] = {"baseUrl": "https://unfamiliar.invalid/v1"}
    before = copy.deepcopy(config)
    with pytest.raises(ValueError):
        setup.merge_gateway(config, "inert-baseten-key")
    assert config == before


def test_private_environment_preserves_credentials_comments_and_blocks_line_injection():
    original = (
        "# Keep comment\nCEREBRAS_API_KEY=inert-existing\nOPENCLAW_AGENT=beforerun-reviewer\n"
    )
    result = setup.merge_environment(original, "inert-baseten-key")
    assert result.startswith(original)
    assert result.count("BASETEN_API_KEY=") == 1
    assert "OPENCLAW_FALLBACK_MODEL=" + BASETEN_FALLBACK in result
    assert setup.merge_environment(result, "inert-baseten-key") == result
    with pytest.raises(ValueError):
        setup.merge_environment(original, "inert\nINJECTED=1")


def test_private_config_write_keeps_mode_and_preserves_concurrent_change(tmp_path):
    path = tmp_path / "private.env"
    path.write_bytes(b"original")
    setup.private_replace(path, b"original", b"updated")
    assert path.read_bytes() == b"updated"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.write_bytes(b"someone-else")
    with pytest.raises(ValueError):
        setup.private_replace(path, b"updated", b"overwrite")
    assert path.read_bytes() == b"someone-else"


def test_provider_disclosure_reads_only_approved_server_configuration(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "inert-secret-not-for-disclosure")
    monkeypatch.setenv("OPENCLAW_FALLBACK_MODEL", BASETEN_FALLBACK)
    policy = GatewayModelPolicy.from_environment()
    assert policy.public_data()["fallback"] == BASETEN_FALLBACK
    assert policy.public_data()["actual_upstream_verified"] is False
    assert "inert-secret" not in json.dumps(policy.public_data())
    monkeypatch.setenv("OPENCLAW_FALLBACK_MODEL", "unapproved/provider")
    with pytest.raises(ValueError):
        GatewayModelPolicy.from_environment()


def test_private_write_preserves_a_change_during_temp_preparation(tmp_path, monkeypatch):
    path = tmp_path / "private.env"
    path.write_bytes(b"original")
    monkeypatch.setattr(setup.os, "fsync", lambda descriptor: path.write_bytes(b"concurrent"))
    with pytest.raises(ValueError):
        setup.private_replace(path, b"original", b"replacement")
    assert path.read_bytes() == b"concurrent"


def test_capabilities_and_export_disclose_configured_fallback_without_claiming_it_ran():
    service = make_service(FakePipeline())
    assumptions = tuple(f"Checked qualification {index}." for index in range(32))
    service.pipeline.result = service.pipeline.result.model_copy(
        update={
            "report": service.pipeline.result.report.model_copy(update={"assumptions": assumptions})
        }
    )
    service.gateway_model_policy = GatewayModelPolicy(fallback_model=BASETEN_FALLBACK)
    app.state.review_service = service
    with TestClient(app, base_url=BASE_URL) as client:
        capabilities = client.get("/api/capabilities").json()
        assert capabilities["gateway_model_policy"]["fallback"] == BASETEN_FALLBACK
        assert capabilities["gateway_model_policy"]["actual_upstream_verified"] is False
        assert capabilities["browser_gateway_access"] is False
        created = post_review(client).json()
        value = wait_terminal(client, created["review_id"])
        disclosure = value["model_processing"]
        assert BASETEN_FALLBACK in disclosure and "does not verify" in disclosure
        assert value["report"]["assumptions"] == list(assumptions)
        assert value["report"]["model_route"] == "fixture-only; no model call"
        export = client.get(f"/api/reviews/{created['review_id']}/export").text
        assert BASETEN_FALLBACK in export and "inert-secret" not in export
