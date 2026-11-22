"""Prepared, explicitly authorized three-phase live proof over one inert memory fixture.

Preparation is safe: importing this module or invoking it without --authorize-live and
--authorization-reference neither reads .env nor creates an HTTP client. After the parent
reviews the dedicated profile and obtains live authorization, the proposed command is:

  .venv/bin/python tests/fixtures/demo/run_live_proof.py --authorize-live \
    --authorization-reference USER_MESSAGE_REFERENCE --max-requests 3 \
    --output docs/live-proof/authorized_read_proof.json

Scope: text smoke, one model-chosen br_read_excerpt, canonical continuation to a checked
source observation. All seven definitions from the real client remain intact, but this
runner rejects every returned operation except the exact expected inert read. It changes
no configuration or admission flag. The default three outgoing Gateway attempts include
the real client's retry; each attempt permits at most 512 output tokens. A failed prerequisite
stops the proof. No network destination except the configured Gateway is admitted; no source
is fetched or executed. Existing output files are never overwritten. This cap does not establish
Gateway-internal upstream retry counts, actual usage or provider spend.
Effective Gateway isolation, forbidden actions, cross-job history, active cancellation,
upstream provider identity, real GitHub retrieval and verified pricing are NOT proved here.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import (
    Assessment,
    CandidateReport,
    Completion,
    ErrorCode,
    ModelAttemptKind,
    PinnedRevision,
    ReviewInput,
    RevisionSide,
    StopReason,
    ToolName,
)
from beforerun.features.evidence import EvidenceLedger
from beforerun.features.github_source import Blob
from beforerun.features.investigator import InvestigationOutcome
from beforerun.features.openclaw_client import MAX_RESPONSE_BYTES, OpenClawClient
from beforerun.features.report import build_report
from beforerun.features.safe_tools import SnapshotTools
from beforerun.features.settings import Settings, _validate_gateway_url, get_settings
from beforerun.features.snapshot import Snapshot, issued_id
from beforerun.features.validate import ValidationContext, validate_finding

FIXTURE_MARKER = "INERT_SOURCE_PROOF_742"
FIXTURE_BYTES = (FIXTURE_MARKER + "\n").encode()
ROOT = Path(__file__).resolve().parents[3]


class ProofRefusal(RuntimeError):
    """Only fixed public codes enter exceptions or output, never upstream text."""


def _authorize(authorize_live: bool, authorization_reference: str, max_requests: int) -> str:
    if authorize_live is not True or not isinstance(authorization_reference, str):
        raise ProofRefusal("LIVE_NOT_AUTHORIZED")
    reference = authorization_reference.strip()
    if not reference or len(reference) > 500:
        raise ProofRefusal("AUTHORIZATION_REFERENCE_REQUIRED")
    if (
        isinstance(max_requests, bool)
        or not isinstance(max_requests, int)
        or not 1 <= max_requests <= 8
    ):
        raise ProofRefusal("REQUEST_LIMIT_INVALID")
    # Keep even accidentally pasted sensitive reference text out of artifacts/output.
    try:
        return hashlib.sha256(reference.encode("utf-8")).hexdigest()
    except UnicodeError:
        raise ProofRefusal("AUTHORIZATION_REFERENCE_REQUIRED") from None


def _public_model_identity(model: str) -> dict[str, str | None]:
    """Only the fixed reviewer alias is saved verbatim; custom identities are hashed."""

    if (
        not isinstance(model, str)
        or not model
        or len(model) > 160
        or any(ord(character) < 32 or ord(character) == 127 for character in model)
    ):
        raise ProofRefusal("CONFIGURATION_UNAVAILABLE")
    try:
        digest = hashlib.sha256(model.encode("utf-8")).hexdigest()
    except UnicodeError:
        raise ProofRefusal("CONFIGURATION_UNAVAILABLE") from None
    return {
        "value": model if model == "openclaw/beforerun-reviewer" else None,
        "sha256": digest,
    }


def _error_code(error: BaseException) -> str:
    if isinstance(error, ReviewError):
        return error.code.value
    if (
        isinstance(error, ProofRefusal)
        and error.args
        and error.args[0]
        in {
            "LIVE_NOT_AUTHORIZED",
            "AUTHORIZATION_REFERENCE_REQUIRED",
            "REQUEST_LIMIT_INVALID",
            "CONFIGURATION_UNAVAILABLE",
            "SMOKE_FAILED",
            "UNEXPECTED_TOOL_CALL",
            "INVALID_CITATION",
            "REPORT_NOT_COMPLETE",
            "INVALID_ARGUMENTS",
            "OUTPUT_REQUIRED",
            "OUTPUT_EXISTS",
        }
    ):
        return str(error.args[0])
    return "INVALID_MODEL_OUTPUT"


def _usage(value: Any) -> dict[str, int | None]:
    value = value if isinstance(value, dict) else {}
    return {
        key: number
        if isinstance(number := value.get(key), int)
        and not isinstance(number, bool)
        and 0 <= number <= 2**53 - 1
        else None
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


class _ObservedStream(httpx.AsyncByteStream):
    def __init__(
        self, stream: httpx.AsyncByteStream, row: dict, clock, expected_model: str
    ) -> None:
        self.stream, self.row, self.clock, self.expected_model = stream, row, clock, expected_model
        self.started = clock()
        self.raw = bytearray()
        self.closed = False

    async def __aiter__(self):
        try:
            async for chunk in self.stream:
                if self.row["first_body_byte_ms"] is None:
                    self.row["first_body_byte_ms"] = (self.clock() - self.row["_started"]) * 1000
                if len(self.raw) + len(chunk) > MAX_RESPONSE_BYTES:
                    self.row["error_code"] = "RESPONSE_LIMIT"
                    raise ReviewError(
                        ErrorCode.INVALID_MODEL_OUTPUT, "Proof response limit exceeded."
                    )
                self.raw.extend(chunk)
                self.row["response_bytes"] = len(self.raw)
                yield chunk
        finally:
            self._summarize()

    def _summarize(self) -> None:
        self.row["duration_ms"] = (self.clock() - self.row["_started"]) * 1000
        if self.raw:
            try:
                value = json.loads(bytes(self.raw))
            except (ValueError, UnicodeError, RecursionError):
                return
            if isinstance(value, dict):
                self.row["usage"] = _usage(value.get("usage"))
                model = value.get("model")
                self.row["response_model_matches_expectation"] = (
                    model == self.expected_model if isinstance(model, str) else None
                )
                # Unexpected response strings might contain private data; never save them.
                if model == self.expected_model:
                    identity = _public_model_identity(self.expected_model)
                    self.row["response_model"] = identity["value"]
                    self.row["response_model_sha256"] = identity["sha256"]

    async def aclose(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                await self.stream.aclose()
            finally:
                self._summarize()


class BoundedGatewayTransport(httpx.AsyncBaseTransport):
    """Count every outgoing attempt; only one configured origin/path can be contacted."""

    def __init__(
        self,
        settings: Settings,
        delegate: httpx.AsyncBaseTransport,
        max_requests: int,
        *,
        clock=time.monotonic,
    ) -> None:
        try:
            self.origin = httpx.URL(_validate_gateway_url(settings.openclaw_base_url))
        except (TypeError, ValueError, UnicodeError):
            raise ProofRefusal("CONFIGURATION_UNAVAILABLE") from None
        self.expected_model = settings.expected_response_model
        _public_model_identity(self.expected_model)
        self.route = "openclaw/" + settings.openclaw_agent
        self.delegate, self.max_requests, self.clock = delegate, max_requests, clock
        self.run_started = clock()
        self.phase = "text_smoke"
        self.rows: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.method != "POST"
            or request.url.scheme != self.origin.scheme
            or request.url.host != self.origin.host
            or request.url.port != self.origin.port
            or request.url.path != "/v1/chat/completions"
            or request.url.query
            or request.url.username
            or request.url.password
            or request.url.fragment
        ):
            raise ReviewError(
                ErrorCode.FORBIDDEN_TOOL, "Proof transport rejected an unrelated destination."
            )
        if len(self.rows) >= self.max_requests:
            raise ReviewError(ErrorCode.BUDGET_EXHAUSTED, "Proof request allowance exhausted.")
        started = self.clock()
        row = {
            "attempt": len(self.rows) + 1,
            "phase": self.phase,
            "start_offset_ms": (started - self.run_started) * 1000,
            "duration_ms": None,
            "first_body_byte_ms": None,
            "http_status": None,
            "response_bytes": 0,
            "response_model": None,
            "response_model_sha256": None,
            "response_model_matches_expectation": None,
            "usage": _usage(None),
            "cost": None,
            "error_code": None,
            "_started": started,
        }
        self.rows.append(row)
        try:
            if len(request.content) > 256 * 1024:
                raise ReviewError(
                    ErrorCode.SOURCE_LIMIT, "Proof request envelope exceeds its allowance."
                )
            payload = json.loads(request.content)
            if not isinstance(payload, dict) or payload.get("model") != self.route:
                raise ReviewError(ErrorCode.FORBIDDEN_TOOL, "Proof request route is inconsistent.")
            # The smoke needs no tools; preserve the client's complete seven-tool definitions.
            if self.phase == "text_smoke":
                payload["tool_choice"] = "none"
            payload["max_tokens"] = min(payload["max_tokens"], 512)
            headers = {
                key: value
                for key, value in request.headers.items()
                if key.lower() != "content-length"
            }
            bounded = httpx.Request(
                "POST", request.url, headers=headers, json=payload, extensions=request.extensions
            )
            response = await self.delegate.handle_async_request(bounded)
            row["http_status"] = response.status_code
            if response.status_code != 200:
                row["error_code"] = "HTTP_" + str(response.status_code)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                stream=_ObservedStream(response.stream, row, self.clock, self.expected_model),
                extensions=response.extensions,
                request=bounded,
            )
        except BaseException as error:
            row["duration_ms"] = (self.clock() - started) * 1000
            row["error_code"] = _error_code(error)
            raise

    async def aclose(self) -> None:
        await self.delegate.aclose()

    def public_rows(self) -> list[dict]:
        return [
            {key: value for key, value in row.items() if not key.startswith("_")}
            for row in self.rows
        ]


class MemorySource:
    """A fixed harmless text blob; it can never fetch or execute repository content."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.blob_id = hashlib.sha1(
            b"blob " + str(len(FIXTURE_BYTES)).encode() + b"\0" + FIXTURE_BYTES
        ).hexdigest()

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        self.budget.check()
        if expected_sha != self.blob_id:
            raise ReviewError(ErrorCode.INVALID_TOOL_ARGUMENTS, "Unknown proof blob.")
        self.budget.add_source(revision.repository_id, expected_sha, len(FIXTURE_BYTES))
        return Blob(expected_sha, FIXTURE_BYTES)


async def execute_proof(
    *,
    authorize_live: bool = False,
    authorization_reference: str = "",
    settings: Settings | None = None,
    max_requests: int = 3,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    reference_hash = _authorize(authorize_live, authorization_reference, max_requests)
    artifact = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "execution_mode": "offline_test" if transport is not None else "live",
        "authorization_reference_sha256": reference_hash,
        "scope": "text smoke; inert memory read; canonical continuation; checked source citation",
        "synthetic_source": True,
        "github_requests": 0,
        "max_gateway_requests": max_requests,
        "status": "failed",
        "phases": [],
        "attempts": [],
        "checked_report_created": False,
        "provider_cost": None,
        "provider_request_count": None,
        "release_ready": False,
        "limitations": [
            "Effective Gateway tool/bootstrap policy is not inspected by this runner.",
            "No forbidden-action, cross-job/session or active-cancellation challenge is performed.",
            "Matching response model is not independent upstream-provider proof.",
            "No real GitHub retrieval, queue/browser latency or verified provider pricing.",
            "Gateway-internal provider requests/retries and unknown usage/cost remain unknown.",
        ],
    }
    bounded = None
    started = time.monotonic()
    try:
        settings = settings or get_settings()
        if settings.openclaw_agent != "beforerun-reviewer" or not settings.openclaw_gateway_token:
            raise ProofRefusal("CONFIGURATION_UNAVAILABLE")
        settings = replace(
            settings, max_model_attempts=min(settings.max_model_attempts, max_requests)
        )
        # Validate settings before creating a real transport or serializing any origin.
        try:
            _validate_gateway_url(settings.openclaw_base_url)
        except (TypeError, ValueError, UnicodeError):
            raise ProofRefusal("CONFIGURATION_UNAVAILABLE") from None
        model_identity = _public_model_identity(settings.expected_response_model)
        bounded = BoundedGatewayTransport(
            settings, transport or httpx.AsyncHTTPTransport(retries=0), max_requests
        )
        artifact["gateway_origin"] = str(bounded.origin)
        artifact["request_route"] = "openclaw/beforerun-reviewer"
        artifact["expected_response_model"] = model_identity["value"]
        artifact["expected_response_model_sha256"] = model_identity["sha256"]
        budget = Budget(settings)
        source = MemorySource(budget)
        revision = PinnedRevision(
            revision_id=issued_id("rev"),
            repository_id=1,
            canonical_owner="example",
            canonical_name="inert-fixture",
            requested_ref="synthetic",
            commit_sha="a" * 40,
            tree_sha="b" * 40,
            resolution_timestamp=datetime.now(UTC),
            side=RevisionSide.TARGET,
        )
        snapshot = Snapshot({RevisionSide.TARGET: revision}, source)  # type: ignore[arg-type]
        snapshot.register_tree(
            RevisionSide.TARGET,
            [{"path": "fixture.txt", "mode": "100644", "type": "blob", "sha": source.blob_id}],
            False,
        )
        ledger = EvidenceLedger(issued_id("review"), snapshot, settings)
        file_id = snapshot.file_id(RevisionSide.TARGET, "fixture.txt")
        tools = SnapshotTools(snapshot, ledger, budget)
        async with httpx.AsyncClient(
            transport=bounded, trust_env=False, follow_redirects=False, timeout=30
        ) as http:
            client = OpenClawClient(settings, client=http)

            async def call(phase, messages, kind=ModelAttemptKind.DECISION):
                bounded.phase = phase
                phase_started = time.monotonic()
                record = {
                    "phase": phase,
                    "start_offset_ms": (phase_started - started) * 1000,
                    "duration_ms": None,
                    "status": "failed",
                    "error_code": None,
                }
                artifact["phases"].append(record)
                try:
                    reply = await client.complete(messages, budget, kind=kind)
                    record["status"] = "passed"
                    return reply
                except BaseException as error:
                    record["error_code"] = _error_code(error)
                    raise
                finally:
                    record["duration_ms"] = (time.monotonic() - phase_started) * 1000

            smoke = await call(
                "text_smoke",
                [
                    {
                        "role": "user",
                        "content": (
                            "Reply exactly CONNECTION_OK. "
                            "Do not use any tools or host capabilities."
                        ),
                    }
                ],
            )
            if smoke.message.get("content") != "CONNECTION_OK" or smoke.message.get("tool_calls"):
                raise ProofRefusal("SMOKE_FAILED")
            expected_args = {"file_id": file_id, "first_original_line": 1, "last_original_line": 1}
            messages = [
                {
                    "role": "system",
                    "content": (
                        "This is an inert source-reference proof. "
                        "Only br_read_excerpt is permitted here. "
                        "Never use host files, commands, callbacks, personal memory "
                        "or another operation."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": (
                                "Choose br_read_excerpt exactly once with these arguments "
                                "before answering."
                            ),
                            "arguments": expected_args,
                        }
                    ),
                },
            ]
            read = await call("inert_read_decision", messages)
            calls = read.message.get("tool_calls") or []
            if len(calls) != 1:
                raise ProofRefusal("UNEXPECTED_TOOL_CALL")
            raw = calls[0]
            function = raw["function"]
            if (
                function["name"] != ToolName.READ_EXCERPT.value
                or json.loads(function["arguments"]) != expected_args
            ):
                raise ProofRefusal("UNEXPECTED_TOOL_CALL")
            dispatch = await tools.dispatch(
                {
                    "calls": [
                        {
                            "tool_call_id": raw["id"],
                            "name": function["name"],
                            "arguments": expected_args,
                        }
                    ]
                },
                turn=1,
                record_delivery=False,
            )
            if not dispatch.results[0].succeeded:
                raise ProofRefusal("INVALID_CITATION")
            evidence_id = json.loads(dispatch.results[0].output)["evidence"][0]["evidence_id"]
            messages.extend(
                [
                    read.message,
                    {
                        "role": "tool",
                        "tool_call_id": raw["id"],
                        "content": dispatch.results[0].output,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "instruction": (
                                    "Return only CandidateReport JSON with one benign "
                                    "source_observation. Quote the returned marker exactly "
                                    "with its evidence_id and original line 1. "
                                    "No relationships, no comparison or runtime claim; "
                                    "consider a benign explanation. "
                                    "Use stop_reason finished and no tools."
                                ),
                                "schema": CandidateReport.model_json_schema(),
                            }
                        ),
                    },
                ]
            )
            final = await call("checked_citation", messages, ModelAttemptKind.FINAL)
            ledger.deliver([evidence_id], 2, raw["id"])
            candidate = CandidateReport.model_validate_json(final.message.get("content") or "")
            if len(candidate.findings) != 1 or candidate.assessment is not Assessment.BENIGN:
                raise ProofRefusal("INVALID_CITATION")
            finding = candidate.findings[0]
            intake = ReviewInput(repository_url="https://github.com/example/inert-fixture")
            context = ValidationContext(intake, ledger)
            checked = validate_finding(finding, context)
            if (
                finding.evidence_ids != (evidence_id,)
                or len(finding.evidence_quotes) != 1
                or finding.evidence_quotes[0].evidence_id != evidence_id
                or finding.evidence_quotes[0].exact_quote != FIXTURE_MARKER
                or finding.evidence_quotes[0].first_original_line != 1
                or finding.evidence_quotes[0].last_original_line != 1
                or finding.relationship_ids
                or candidate.stop_reason is not StopReason.FINISHED
            ):
                raise ProofRefusal("INVALID_CITATION")
            outcome = InvestigationOutcome(candidate, StopReason.FINISHED, (), ())
            report = build_report(context, outcome, budget, required_file_ids=frozenset({file_id}))
            if report.completion is not Completion.COMPLETE or len(report.findings) != 1:
                raise ProofRefusal("REPORT_NOT_COMPLETE")
            artifact.update(
                {
                    "status": "passed_inert_reference_proof",
                    "checked_report_created": True,
                    "checked_citation": {
                        "evidence_id": evidence_id,
                        "span": ledger.require(evidence_id).span.model_dump(),
                        "representation_sha256": ledger.require(evidence_id).representation_sha256,
                        "source_identity_checked": checked.validation.source_identity_checked,
                        "delivery_checked": checked.validation.delivery_checked,
                        "range_quote_checked": checked.validation.range_quote_checked,
                    },
                    "first_checked_evidence_ms": (time.monotonic() - started) * 1000,
                    "completion": report.completion.value,
                    "assessment": report.assessment.value,
                }
            )
    except BaseException as error:
        artifact["error_code"] = _error_code(error)
        if artifact["phases"]:
            artifact["phases"][-1].update(status="failed", error_code=_error_code(error))
    finally:
        artifact["total_wall_ms"] = (time.monotonic() - started) * 1000
        artifact["clock"] = "time.monotonic"
        if bounded:
            artifact["attempts"] = bounded.public_rows()
        artifact["gateway_requests"] = len(artifact["attempts"])
    return artifact


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ProofRefusal("INVALID_ARGUMENTS")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--authorize-live", action="store_true")
    parser.add_argument("--authorization-reference", default="")
    parser.add_argument("--max-requests", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    output = None
    try:
        args = parser.parse_args(argv)
        _authorize(args.authorize_live, args.authorization_reference, args.max_requests)
        if args.output is None:
            raise ProofRefusal("OUTPUT_REQUIRED")
        try:
            descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            output = os.fdopen(descriptor, "w")
        except FileExistsError:
            raise ProofRefusal("OUTPUT_EXISTS") from None
        # Private environment access starts after authorization and output reservation.
        load_dotenv(args.env_file, override=False)
        if not os.environ.get("OPENCLAW_BASE_URL"):
            raise ProofRefusal("CONFIGURATION_UNAVAILABLE")
        artifact = asyncio.run(
            execute_proof(
                authorize_live=True,
                authorization_reference=args.authorization_reference,
                max_requests=args.max_requests,
            )
        )
        output.write(json.dumps(artifact, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "status": artifact["status"],
                    "gateway_requests": artifact["gateway_requests"],
                    "error_code": artifact.get("error_code"),
                    "release_ready": False,
                }
            )
        )
        return 0 if artifact["checked_report_created"] else 1
    except SystemExit as error:
        # argparse's help action exits successfully without reading settings or creating output.
        return 0 if error.code == 0 else 2
    except BaseException as error:
        summary = {
            "status": "not_executed",
            "error_code": _error_code(error),
            "gateway_requests": 0,
        }
        if output:
            output.write(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))
        return 2
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
