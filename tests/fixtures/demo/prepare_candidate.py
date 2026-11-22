"""Export only reviewed product files; never include the workspace's Git history."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise ValueError("Candidate paths must be relative product paths.")
    return path


def candidate_files(root: Path, scope: dict) -> dict[str, Path]:
    excluded = set(scope["exclude_path_components"])
    component_suffixes = tuple(scope.get("exclude_component_suffixes", []))
    suffixes = tuple(scope["exclude_suffixes"])
    result: dict[str, Path] = {}
    destinations: set[str] = set()
    manifest_key = "docs/release-candidate/manifest.json"

    def admit(target: str, source: str) -> None:
        destination, relative = _relative(target), _relative(source)
        destination_key = unicodedata.normalize("NFD", str(destination)).casefold()
        if destination_key == manifest_key:
            raise ValueError("Candidate manifest path is reserved.")
        if any(part in excluded for part in (*destination.parts, *relative.parts)):
            return
        if component_suffixes and any(
            part.endswith(component_suffixes) for part in (*destination.parts, *relative.parts)
        ):
            return
        if target.endswith(suffixes) or source.endswith(suffixes):
            return
        if any(part.startswith(".env") and part != ".env.example" for part in relative.parts):
            return
        path = root / relative
        if any(
            (root / Path(*relative.parts[:index])).is_symlink()
            for index in range(1, len(relative.parts) + 1)
        ):
            raise ValueError("Candidate export rejects symlinks.")
        if not path.is_file():
            raise ValueError("A required candidate file is missing.")
        if destination_key in destinations:
            raise ValueError("Candidate scope repeats an output path.")
        destinations.add(destination_key)
        result[str(destination)] = path

    for name in (*scope["root_files"], *scope["documents"]):
        admit(name, name)
    for name in scope["trees"]:
        tree = root / _relative(name)
        if tree.is_symlink() or not tree.is_dir():
            raise ValueError("A candidate source tree is unavailable.")
        for path in sorted(tree.rglob("*")):
            if path.is_file() or path.is_symlink():
                relative = str(path.relative_to(root))
                admit(relative, relative)
    for target, source in scope.get("mapped_files", {}).items():
        admit(target, source)
    return result


def build_candidate(root: Path, output: Path, scope: dict) -> dict:
    files = candidate_files(root, scope)
    root_resolved, output_resolved = root.resolve(), output.resolve()
    if output_resolved == root_resolved or root_resolved in output_resolved.parents:
        raise ValueError("Export outside the working repository.")
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for target, source in sorted(files.items()):
        content = source.read_bytes()
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        shutil.copymode(source, destination)
        records.append({"path": target, "sha256": hashlib.sha256(content).hexdigest()})
    fingerprint = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = {
        "mode": "offline product snapshot; live release blocked",
        "file_count": len(records),
        "content_sha256": fingerprint,
        "files": records,
        "git_history_included": False,
        "dependencies_bundled": False,
        "effective_project_license": scope["effective_project_license"],
        "publication": "not performed",
    }
    manifest_path = output / "docs/release-candidate/MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads((ROOT / "docs/release-candidate/SCOPE.json").read_text())
    manifest = build_candidate(ROOT, args.output, scope)
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}))


if __name__ == "__main__":
    main()
