"""A product snapshot must exclude credentials/history and reject filesystem aliases."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "fixtures/demo/prepare_candidate.py"
SPEC = importlib.util.spec_from_file_location("candidate_export", SCRIPT)
assert SPEC and SPEC.loader
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def scope():
    return {
        "root_files": [".env.example"],
        "documents": [],
        "trees": ["src"],
        "mapped_files": {"README.md": "public.md"},
        "exclude_path_components": [".git", "memory", "__pycache__"],
        "exclude_component_suffixes": [".egg-info", ".dist-info"],
        "exclude_suffixes": [".log", ".pyc"],
        "effective_project_license": "unresolved",
    }


def prepared(tmp_path):
    root = tmp_path / "working"
    (root / "src").mkdir(parents=True)
    (root / ".env.example").write_text("SERVER_SETTING=placeholder\n")
    (root / "public.md").write_text("Public product overview\n")
    (root / "src/app.py").write_text("# Inert source\n")
    return root


def test_snapshot_excludes_nested_credentials_caches_and_private_history(tmp_path):
    root = prepared(tmp_path)
    for name in (
        ".env",
        ".env.private",
        "provider.log",
        "__pycache__/a.pyc",
        "memory/a.md",
        ".git/config",
        "generated.egg-info/PKG-INFO",
        "generated.dist-info/METADATA",
    ):
        path = root / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PRIVATE_FIXTURE_DO_NOT_EXPORT")
    output = tmp_path / "candidate"
    manifest = export.build_candidate(root, output, scope())
    assert {item["path"] for item in manifest["files"]} == {
        ".env.example",
        "README.md",
        "src/app.py",
    }
    assert manifest["git_history_included"] is False
    assert (output / "README.md").read_text() == "Public product overview\n"
    assert all(
        b"PRIVATE_FIXTURE_DO_NOT_EXPORT" not in p.read_bytes()
        for p in output.rglob("*")
        if p.is_file()
    )


def test_snapshot_rejects_symlink_to_private_host_file_before_writing(tmp_path):
    root = prepared(tmp_path)
    private = tmp_path / "private.txt"
    private.write_text("PRIVATE_FIXTURE_DO_NOT_EXPORT")
    (root / "src/alias.py").symlink_to(private)
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="symlinks"):
        export.build_candidate(root, output, scope())
    assert not output.exists()


def test_snapshot_rejects_traversal_and_preserves_existing_output(tmp_path):
    root = prepared(tmp_path)
    invalid = {**scope(), "mapped_files": {"../leak.txt": "public.md"}}
    with pytest.raises(ValueError, match="relative"):
        export.build_candidate(root, tmp_path / "candidate", invalid)
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "user-work.txt"
    marker.write_text("preserve")
    with pytest.raises(FileExistsError):
        export.build_candidate(root, existing, scope())
    assert marker.read_text() == "preserve"


@pytest.mark.parametrize("target", ["readme.md", "docs/release-candidate/MANIFEST.json"])
def test_snapshot_rejects_case_alias_and_generated_manifest_collision(tmp_path, target):
    root = prepared(tmp_path)
    invalid = {**scope(), "mapped_files": {**scope()["mapped_files"], target: "public.md"}}
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="repeats|reserved"):
        export.build_candidate(root, output, invalid)
    assert not output.exists()
