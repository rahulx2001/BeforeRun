"""One bounded analyst, canonical tool transcript, and one candidate format repair."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import (
    Assessment,
    CandidateReport,
    ErrorCode,
    ErrorRecord,
    Finding,
    InvestigationStep,
    ModelAttemptKind,
    StopReason,
)
from beforerun.features.openclaw_client import OpenClawClient
from beforerun.features.safe_tools import SnapshotTools

PROMPT = Path(__file__).with_name("prompts") / "investigator-v1.txt"


@dataclass(frozen=True)
class InvestigationOutcome:
    candidate: CandidateReport | None
    stop_reason: StopReason
    errors: tuple[ErrorRecord, ...]
    steps: tuple[InvestigationStep, ...]


def _load_json_object(content: str) -> Any:
    """Accept a raw object, or the same object wrapped in a fence or a short preface."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def parse_candidate(content: str) -> tuple[CandidateReport, tuple[ErrorRecord, ...]]:
    """Reject malformed findings individually without discarding valid siblings."""
    raw = _load_json_object(content)
    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        return CandidateReport.model_validate(raw), ()
    if len(raw["findings"]) > 8:
        return CandidateReport.model_validate_json(content), ()
    findings, errors = [], []
    for item in raw["findings"]:
        try:
            findings.append(Finding.model_validate(item))
        except ValidationError:
            errors.append(
                ErrorRecord(
                    code=ErrorCode.INVALID_MODEL_OUTPUT,
                    message="A finding failed its individual schema validation.",
                )
            )
    raw = {**raw, "findings": findings}
    if errors and not findings:
        raw["assessment"] = "undetermined"
    return CandidateReport.model_validate(raw), tuple(errors)


def _copy_sheet(ledger: Any) -> list[dict[str, Any]]:
    """Short delivered lines the candidate can quote without paraphrasing."""
    sheet: list[dict[str, Any]] = []
    for evidence_id in ledger.delivered:
        evidence = ledger.require(evidence_id)
        if evidence.parent_evidence_id:
            continue
        path = ledger.snapshot.require_file(evidence.file_id).record.path
        for offset, line in enumerate(evidence.representation.splitlines()):
            if not line.strip() or len(line) > 180:
                continue
            sheet.append(
                {
                    "evidence_id": evidence_id,
                    "path": path,
                    "exact_quote": line,
                    "first_original_line": evidence.span.first_line + offset,
                    "last_original_line": evidence.span.first_line + offset,
                }
            )
            break
        if len(sheet) >= 5:
            break
    return sheet


def _needs_quote_repair(
    candidate: CandidateReport, schema_errors: tuple[ErrorRecord, ...], ledger: Any
) -> bool:
    if schema_errors:
        return True
    if not ledger.delivered:
        return False
    if candidate.findings:
        return not _quotes_hold(candidate, ledger)
    return candidate.assessment is Assessment.UNDETERMINED


def _quotes_hold(candidate: CandidateReport, ledger: Any) -> bool:
    if not candidate.findings:
        return True
    for finding in candidate.findings:
        if not finding.benign_explanation_considered.strip() or not finding.evidence_quotes:
            return False
        for quote in finding.evidence_quotes:
            if quote.evidence_id not in ledger.delivered:
                return False
            if quote.exact_quote not in ledger.require(quote.evidence_id).representation:
                return False
    return True


def _final_request(ledger: Any) -> dict[str, Any]:
    sheet = _copy_sheet(ledger)
    instruction = (
        "Return only a CandidateReport JSON object. No markdown and no tools. "
        "Include one finding whose behavior_category is source_observation, "
        "priority is low, relationship_ids is empty, and change_status is not_compared. "
        "Set evidence_ids to a one-item list of the copied evidence_id. "
        "finding_id must match find_ plus at least 16 letters or digits. "
        "Copy exact_quote, evidence_id, first_original_line, and last_original_line "
        "from one copy_from item, character for character. "
        "Title, impact, priority_reason, trigger_context, and "
        "benign_explanation_considered each describe only that quoted line. "
        "Do not claim malware, theft, or install-time execution. "
        "When the quote is ordinary declared setup, use assessment benign and "
        "stop_reason finished. Do not answer undetermined after copy_from is present."
    )
    if sheet:
        instruction += " Prefer the first copy_from item."
    return {
        "instruction": instruction,
        "copy_from": sheet,
        "schema": CandidateReport.model_json_schema(),
    }


def _repair_message(ledger: Any, reason: str) -> dict[str, str]:
    return {
        "role": "user",
        "content": json.dumps(
            {
                "instruction": (
                    "Return one CandidateReport JSON object only. Copy exact_quote from "
                    "copy_from with the same evidence_id and line numbers. Do not paraphrase, "
                    "raise confidence, or invent IDs."
                ),
                "error": ErrorCode.INVALID_MODEL_OUTPUT.value,
                "reason": reason,
                "copy_from": _copy_sheet(ledger),
                "available_evidence_ids": list(ledger.delivered)[:64],
            }
        ),
    }


class Investigator:
    def __init__(self, client: OpenClawClient, tools: SnapshotTools) -> None:
        self.client, self.tools = client, tools

    async def run(self, seed_ids: list[str], context: dict[str, Any]) -> InvestigationOutcome:
        ledger, budget = self.tools.ledger, self.tools.budget
        bundle = json.loads(ledger.bundle(seed_ids))
        messages = [
            {"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "context": context,
                        "source_evidence": bundle,
                        "containers": [
                            {"container_id": key, "side": side.value}
                            for key, side in self.tools.containers.items()
                        ],
                        "instruction": "Use br_ tools to seek useful evidence, then br_finish.",
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        errors: list[ErrorRecord] = []
        steps: list[InvestigationStep] = []
        stop = StopReason.DECISION_LIMIT
        invalid = 0
        pending = [(None, tuple(seed_ids))] if seed_ids else []

        def delivered(turn):
            for call_id, ids in pending:
                ledger.deliver(list(ids), turn, call_id)
            pending.clear()

        try:
            for turn in range(1, budget.settings.max_decision_turns + 1):
                budget.reserve_decision()
                reply = await self.client.complete(messages, budget)
                delivered(turn)
                calls = reply.message.get("tool_calls")
                if not calls:
                    # The seed is already in the transcript. Ask for the report
                    # instead of discarding a text decision.
                    messages.append(reply.message)
                    if ledger.delivered:
                        stop = StopReason.FINISHED
                    break
                proposed = []
                for raw in calls:
                    if (
                        not isinstance(raw, dict)
                        or raw.get("type") != "function"
                        or not isinstance(raw.get("id"), str)
                        or not isinstance(raw.get("function"), dict)
                    ):
                        raise ReviewError(
                            ErrorCode.INVALID_MODEL_OUTPUT, "Tool response identity is malformed."
                        )
                    function = raw["function"]
                    try:
                        arguments = json.loads(function.get("arguments", ""))
                    except (ValueError, TypeError, RecursionError) as error:
                        raise ReviewError(
                            ErrorCode.INVALID_MODEL_OUTPUT, "Tool arguments are not complete JSON."
                        ) from error
                    proposed.append(
                        {
                            "tool_call_id": raw["id"],
                            "name": function.get("name"),
                            "arguments": arguments,
                        }
                    )
                messages.append(reply.message)
                try:
                    dispatched = await self.tools.dispatch(
                        {"calls": proposed},
                        turn=turn,
                        record_delivery=False,
                    )
                    pending.extend(dispatched.deliveries)
                except ReviewError as error:
                    if error.code in {ErrorCode.REVIEW_CANCELLED, ErrorCode.BUDGET_EXHAUSTED}:
                        raise
                    invalid += 1
                    errors.append(
                        ErrorRecord(
                            code=error.code,
                            message="An inadmissible analyst operation was rejected.",
                        )
                    )
                    for raw in calls:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": raw["id"],
                                "content": json.dumps({"error": error.code.value}),
                            }
                        )
                    if invalid >= 2:
                        stop = StopReason.INVALID_DECISIONS
                        break
                    continue
                for result in dispatched.results:
                    if result.error:
                        errors.append(
                            ErrorRecord(code=result.error.code, message=result.error.message)
                        )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": result.tool_call_id,
                            "content": result.output
                            if result.succeeded
                            else result.model_dump_json(),
                        }
                    )
                    steps.append(
                        InvestigationStep(
                            sequence=len(steps) + 1,
                            requested_operation=result.name.value,
                            short_reason="Bounded source operation returned."
                            if result.succeeded
                            else "Operation was rejected.",
                            elapsed_ms=budget.elapsed_ms,
                            accepted=result.succeeded,
                            rejection_code=result.error.code if result.error else None,
                        )
                    )
                if dispatched.finish_reason:
                    stop = StopReason.FINISHED
                    break
            messages.append({"role": "user", "content": json.dumps(_final_request(ledger))})
            for attempt in range(2):
                reply = await self.client.complete(
                    messages,
                    budget,
                    kind=(ModelAttemptKind.FINAL if attempt == 0 else ModelAttemptKind.REPAIR),
                )
                delivered(budget.decision_turns + 1)
                try:
                    candidate, schema_errors = parse_candidate(reply.message.get("content") or "")
                except (ValidationError, ValueError, RecursionError):
                    if attempt == 1:
                        break
                    messages.extend([reply.message, _repair_message(ledger, "formatting")])
                    continue
                if not _needs_quote_repair(candidate, schema_errors, ledger):
                    return InvestigationOutcome(candidate, stop, tuple(errors), tuple(steps))
                if attempt == 1:
                    errors.extend(schema_errors)
                    return InvestigationOutcome(candidate, stop, tuple(errors), tuple(steps))
                messages.extend(
                    [reply.message, _repair_message(ledger, "The quote was not delivered text.")]
                )
            raise ReviewError(
                ErrorCode.INVALID_MODEL_OUTPUT,
                "Candidate output remained invalid after one repair.",
            )
        except ReviewError as error:
            stop = (
                StopReason.CANCELLED
                if error.code is ErrorCode.REVIEW_CANCELLED
                else StopReason.BUDGET_EXHAUSTED
                if error.code is ErrorCode.BUDGET_EXHAUSTED
                else StopReason.UPSTREAM_ERROR
            )
            errors.append(
                ErrorRecord(code=error.code, message=error.message, retryable=error.retryable)
            )
            return InvestigationOutcome(None, stop, tuple(errors), tuple(steps))
