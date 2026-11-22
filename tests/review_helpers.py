"""Inert pinned source and recorded reviewer helpers. Never performs networking."""

import hashlib
from datetime import UTC, datetime

from beforerun.features.budgets import Budget
from beforerun.features.contracts import PinnedRevision, RevisionSide
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.github_source import Blob
from beforerun.features.settings import Settings
from beforerun.features.snapshot import Snapshot


class MemorySource:
    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.blobs: dict[str, bytes] = {}
        self.calls: list[str] = []

    def entry(self, path: str, raw: bytes) -> dict[str, str]:
        sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.blobs[sha] = raw
        return {"path": path, "sha": sha, "mode": "100644", "type": "blob"}

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        self.budget.check()
        self.calls.append(expected_sha)
        return Blob(blob_id=expected_sha, content=self.blobs[expected_sha])


def context(
    target: dict[str, bytes] | None = None,
    baseline: dict[str, bytes] | None = None,
    *,
    settings: Settings | None = None,
    review_id: str = "review_1234567890123456",
) -> tuple[Snapshot, EvidenceLedger, Budget]:
    settings = settings or Settings()
    budget = Budget(settings)
    source = MemorySource(budget)
    revisions = {}
    for side, suffix in ((RevisionSide.TARGET, "a"), (RevisionSide.BASELINE, "b")):
        if side is RevisionSide.BASELINE and baseline is None:
            continue
        revisions[side] = PinnedRevision(
            revision_id=f"rev_{suffix * 24}",
            repository_id=1,
            canonical_owner="example",
            canonical_name="inert-fixture",
            requested_ref=side.value,
            commit_sha=suffix * 40,
            tree_sha=suffix * 40,
            resolution_timestamp=datetime.now(UTC),
            side=side,
        )
    snapshot = Snapshot(revisions, source)  # type: ignore[arg-type]
    for side, files in ((RevisionSide.TARGET, target or {}), (RevisionSide.BASELINE, baseline)):
        if files is not None:
            snapshot.register_tree(
                side, [source.entry(path, raw) for path, raw in files.items()], False
            )
    return snapshot, EvidenceLedger(review_id, snapshot, settings), budget


def call(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {"calls": [{"tool_call_id": call_id, "name": name, "arguments": arguments}]}
