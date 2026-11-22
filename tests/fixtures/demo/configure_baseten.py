"""Explicit local Baseten setup. No model request, install, or service restart.

The key is read with getpass, never from a command-line argument. Private files are
merged atomically with mode 0600; the existing primary and tool policy are preserved.
"""

from __future__ import annotations

import argparse
import copy
import getpass
import json
import os
import re
import tempfile
from pathlib import Path

from beforerun.features.gateway_policy import BASETEN_FALLBACK, BASETEN_MODEL, CEREBRAS_PRIMARY

ROOT = Path(__file__).resolve().parents[3]
BASETEN_URL = "https://inference.baseten.co/v1"


def merge_gateway(config: dict, key: str) -> dict:
    """Pure merge for offline verification; callers must never print the resulting config."""

    if not key or len(key) > 512 or any(character.isspace() for character in key):
        raise ValueError("The provided Baseten credential is invalid.")
    updated = copy.deepcopy(config)
    reviewer = updated.get("agents", {}).get("entries", {}).get("beforerun-reviewer")
    if not isinstance(reviewer, dict):
        raise ValueError("The dedicated reviewer is missing.")
    model = reviewer.get("model")
    if not isinstance(model, dict) or model.get("primary") != CEREBRAS_PRIMARY:
        raise ValueError("The expected primary reviewer differs; preserve it for manual review.")
    if reviewer.get("tools") != {"deny": ["*"]}:
        raise ValueError("Inspect the reviewer isolation policy before changing its fallback.")
    providers = updated.setdefault("models", {}).setdefault("providers", {})
    provider = providers.setdefault("baseten", {})
    if provider.get("baseUrl", BASETEN_URL) != BASETEN_URL:
        raise ValueError("An unfamiliar Baseten endpoint already exists; preserve it.")
    if provider.get("api", "openai-completions") != "openai-completions":
        raise ValueError("An unfamiliar Baseten protocol already exists; preserve it.")
    provider.update(baseUrl=BASETEN_URL, api="openai-completions", apiKey=key)
    entries = provider.setdefault("models", [])
    if not any(entry.get("id") == BASETEN_MODEL for entry in entries):
        entries.append({"id": BASETEN_MODEL, "name": "Muse Spark Open", "input": ["text"]})
    fallbacks = model.setdefault("fallbacks", [])
    if BASETEN_FALLBACK not in fallbacks:
        fallbacks.append(BASETEN_FALLBACK)
    allowlist = updated.get("agents", {}).get("defaults", {}).get("models")
    if isinstance(allowlist, dict):
        allowlist.setdefault(BASETEN_FALLBACK, {})
    return updated


def merge_environment(original: str, key: str) -> str:
    values = {
        "BASETEN_API_KEY": key,
        "BASETEN_BASE_URL": BASETEN_URL,
        "BASETEN_MODEL": BASETEN_MODEL,
        "OPENCLAW_FALLBACK_MODEL": BASETEN_FALLBACK,
    }
    if not key or len(key) > 512 or any(character.isspace() for character in key):
        raise ValueError("The provided Baseten credential is invalid.")
    lines, replaced = [], set()
    for line in original.splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Z_]+)\s*=", line)
        name = match[1] if match else None
        if name in values:
            if name not in replaced:
                lines.append(name + "=" + values[name])
                replaced.add(name)
        else:
            lines.append(line)
    lines.extend(name + "=" + value for name, value in values.items() if name not in replaced)
    return "\n".join(lines) + "\n"


def private_replace(path: Path, original: bytes, updated: bytes) -> None:
    if path.is_symlink() or path.read_bytes() != original:
        raise ValueError("Private configuration changed concurrently; preserve it.")
    descriptor, temporary = tempfile.mkstemp(prefix=".beforerun-config-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        if path.is_symlink() or path.read_bytes() != original:
            raise ValueError("Private configuration changed during preparation; preserve it.")
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("Not applied; explicit --apply is required.")
        return 2
    profile = Path.home() / ".openclaw-beforerun/openclaw.json"
    environment = ROOT / ".env"
    try:
        if profile.is_symlink() or environment.is_symlink():
            raise ValueError("Inspect private configuration aliases before changing them.")
        before_profile, before_environment = profile.read_bytes(), environment.read_bytes()
        key = getpass.getpass("Baseten key (hidden): ")
        config = merge_gateway(json.loads(before_profile), key)
        dotenv = merge_environment(before_environment.decode(), key)
        # Reversible private backups remain outside publication scope and are never printed.
        for path, content in ((profile, before_profile), (environment, before_environment)):
            backup = path.with_name(path.name + ".before-baseten.bak")
            if not backup.exists():
                descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as output:
                    output.write(content)
        private_replace(profile, before_profile, (json.dumps(config, indent=2) + "\n").encode())
        private_replace(environment, before_environment, dotenv.encode())
        print(
            json.dumps(
                {
                    "configured_fallback": BASETEN_FALLBACK,
                    "key_saved_privately": True,
                    "primary_preserved": True,
                    "isolation_preserved": True,
                    "service_restart": False,
                    "live_inference_requests": 0,
                    "runtime_activation_verified": False,
                }
            )
        )
        return 0
    except (OSError, ValueError, EOFError):
        print(
            "Local setup could not complete; inspect private files without sharing their contents."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
