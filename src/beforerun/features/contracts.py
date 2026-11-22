"""Strict data contracts shared by trusted services and candidate model output.

These models do not retrieve source or validate behavioral claims. Later stages bind the
records to real GitHub objects, delivered evidence, and supported execution relationships.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

MAX_SOURCE_EXCERPT_BYTES = 12 * 1024
MAX_DERIVED_EXCERPT_BYTES = 16 * 1024
MAX_RECEIPT_BYTES = 64 * 1024


class CommandContext(StrEnum):
    REVIEW_ONLY = "review_only"
    NPM_INSTALL = "npm_install"


class RevisionSide(StrEnum):
    TARGET = "target"
    BASELINE = "baseline"


class Assessment(StrEnum):
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    BENIGN = "benign"
    UNDETERMINED = "undetermined"


class Completion(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    CANCELLED = "cancelled"


class ChangeStatus(StrEnum):
    INTRODUCED = "introduced"
    CHANGED = "changed"
    EXISTING = "existing"
    REMOVED = "removed"
    UNKNOWN = "unknown"
    NOT_COMPARED = "not_compared"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RelationshipSupport(StrEnum):
    SUPPORTED = "supported"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"


class EvidenceKind(StrEnum):
    SOURCE = "source"
    REDACTED = "redacted"
    DECODED = "decoded"
    STRING = "string"
    DIFF = "diff"


class FetchStatus(StrEnum):
    PENDING = "pending"
    FETCHED = "fetched"
    SKIPPED = "skipped"


class EncodingStatus(StrEnum):
    PENDING = "pending"
    UTF8 = "utf8"
    BINARY = "binary"
    OVERSIZED = "oversized"
    UNSUPPORTED = "unsupported"


class GitMode(StrEnum):
    BLOB = "100644"
    EXECUTABLE_BLOB = "100755"
    TREE = "040000"
    SYMLINK = "120000"
    SUBMODULE = "160000"


class GitObjectType(StrEnum):
    BLOB = "blob"
    TREE = "tree"
    COMMIT = "commit"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    TERMINAL = "terminal"


class JobPhase(StrEnum):
    ACCEPTED = "accepted"
    RESOLVING = "resolving"
    INVENTORY = "inventory"
    STATIC_ANALYSIS = "static_analysis"
    INVESTIGATING = "investigating"
    VALIDATING = "validating"
    TERMINAL = "terminal"


class EventType(StrEnum):
    ACCEPTED = "accepted"
    REVISION_PINNED = "revision_pinned"
    FILE_FETCHED = "file_fetched"
    EVIDENCE_DELIVERED = "evidence_delivered"
    TOOL_REJECTED = "tool_rejected"
    BUDGET_WARNING = "budget_warning"
    REPORT_VALIDATED = "report_validated"
    PHASE_CHANGED = "phase_changed"
    TERMINAL = "terminal"


class ErrorCode(StrEnum):
    INVALID_URL = "INVALID_URL"
    INVALID_INPUT = "INVALID_INPUT"
    REF_NOT_FOUND = "REF_NOT_FOUND"
    SOURCE_LIMIT = "SOURCE_LIMIT"
    GITHUB_RATE_LIMIT = "GITHUB_RATE_LIMIT"
    OPENCLAW_UNAVAILABLE = "OPENCLAW_UNAVAILABLE"
    MODEL_ACCESS_DENIED = "MODEL_ACCESS_DENIED"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    REVIEW_EXPIRED = "REVIEW_EXPIRED"
    REVIEW_NOT_FOUND = "REVIEW_NOT_FOUND"
    ADMISSION_LIMIT = "ADMISSION_LIMIT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    REVIEW_CANCELLED = "REVIEW_CANCELLED"
    FORBIDDEN_TOOL = "FORBIDDEN_TOOL"
    INVALID_TOOL_ARGUMENTS = "INVALID_TOOL_ARGUMENTS"


class StopReason(StrEnum):
    FINISHED = "finished"
    DECISION_LIMIT = "decision_limit"
    INVALID_DECISIONS = "invalid_decisions"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UPSTREAM_ERROR = "upstream_error"
    VALIDATION_FAILED = "validation_failed"
    SOURCE_ERROR = "source_error"


class ToolName(StrEnum):
    LIST_FILES = "br_list_files"
    READ_EXCERPT = "br_read_excerpt"
    SEARCH_SOURCE = "br_search_source"
    STATIC_DECODE = "br_static_decode"
    EXTRACT_STRINGS = "br_extract_strings"
    READ_DIFF = "br_read_diff"
    FINISH = "br_finish"


class DecodeOperation(StrEnum):
    BASE64 = "base64"
    HEX = "hex"
    ESCAPE = "escape"
    CHARACTER_CODE = "character_code"


class ModelAttemptKind(StrEnum):
    DECISION = "decision"
    FINAL = "final"
    REPAIR = "repair"


class StrictModel(BaseModel):
    # JSON enum strings and arrays are valid external representations. Authority-sensitive
    # scalar constraints (notably integers) remain explicitly strict in their annotations.
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
Sha1 = Annotated[str, StringConstraints(pattern=r"\A[0-9a-f]{40}\z")]
Sha256 = Annotated[str, StringConstraints(pattern=r"\A[0-9a-f]{64}\z")]
ReviewID = Annotated[str, StringConstraints(pattern=r"\Areview_[A-Za-z0-9_-]{16,120}\z")]
RevisionID = Annotated[str, StringConstraints(pattern=r"\Arev_[A-Za-z0-9_-]{16,120}\z")]
# Owner identifiers are server-issued opaque strings. Their syntax is not an
# authorization boundary; exact ownership comparison in the job store is.
OwnerID = Annotated[
    str,
    StringConstraints(min_length=1, max_length=120, pattern=r"\A[A-Za-z0-9_.:@-]+\z"),
]
FileID = Annotated[str, StringConstraints(pattern=r"\Afile_[A-Za-z0-9_-]{16,120}\z")]
EvidenceID = Annotated[str, StringConstraints(pattern=r"\Aev_[A-Za-z0-9_-]{16,120}\z")]
ReceiptID = Annotated[str, StringConstraints(pattern=r"\Arcpt_[A-Za-z0-9_-]{16,120}\z")]
RelationshipID = Annotated[str, StringConstraints(pattern=r"\Arel_[A-Za-z0-9_-]{16,120}\z")]
FindingID = Annotated[str, StringConstraints(pattern=r"\Afind_[A-Za-z0-9_-]{16,120}\z")]
ContainerID = Annotated[str, StringConstraints(pattern=r"\A(?:dir|snap)_[A-Za-z0-9_-]{16,120}\z")]
ChunkID = Annotated[str, StringConstraints(pattern=r"\Achunk_[A-Za-z0-9_-]{16,120}\z")]
FilePairID = Annotated[str, StringConstraints(pattern=r"\Apair_[A-Za-z0-9_-]{16,120}\z")]
ToolCallID = Annotated[str, StringConstraints(pattern=r"\A[A-Za-z0-9._:-]{1,128}\z")]
VersionText = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ReasonText = Annotated[str, StringConstraints(min_length=1, max_length=500)]


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


class ReviewInput(StrictModel):
    repository_url: str = Field(min_length=1, max_length=2048)
    target_ref: str | None = Field(default=None, max_length=256)
    baseline_ref: str | None = Field(default=None, max_length=256)
    command_context: CommandContext = CommandContext.REVIEW_ONLY
    project_directory: Literal["."] = "."

    @field_validator("target_ref", "baseline_ref")
    @classmethod
    def valid_ref_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value or value != value.strip():
            raise ValueError("refs must be nonempty and have no surrounding whitespace")
        if any(unicodedata.category(character).startswith("C") for character in value):
            raise ValueError("refs cannot contain control characters")
        return value

    @field_validator("repository_url")
    @classmethod
    def reject_url_controls(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("repository URL cannot have surrounding whitespace")
        if any(unicodedata.category(character).startswith("C") for character in value):
            raise ValueError("repository URL cannot contain control characters")
        return value


class PinnedRevision(StrictModel):
    revision_id: RevisionID
    repository_id: PositiveInt
    canonical_owner: str = Field(min_length=1, max_length=100)
    canonical_name: str = Field(min_length=1, max_length=100)
    requested_ref: str | None = Field(default=None, max_length=256)
    commit_sha: Sha1
    tree_sha: Sha1
    resolution_timestamp: AwareDatetime
    side: RevisionSide


class SourceLine(StrictModel):
    line: PositiveInt
    start_byte: NonNegativeInt
    end_byte: NonNegativeInt

    @model_validator(mode="after")
    def ordered_offsets(self) -> SourceLine:
        if self.end_byte < self.start_byte:
            raise ValueError("line end cannot precede its start")
        return self


class SourceFile(StrictModel):
    file_id: FileID
    revision_id: RevisionID
    path: str = Field(min_length=1, max_length=4096)
    mode: GitMode
    object_type: GitObjectType
    blob_id: Sha1 | None = None
    raw_byte_length: NonNegativeInt | None = None
    raw_sha256: Sha256 | None = None
    encoding_status: EncodingStatus = EncodingStatus.PENDING
    line_map: tuple[SourceLine, ...] = Field(default=(), max_length=131072)
    selected: bool = False
    fetch_status: FetchStatus = FetchStatus.PENDING
    skip_reason: str | None = Field(default=None, max_length=500)

    @field_validator("path")
    @classmethod
    def source_path_not_filesystem_authority(cls, value: str) -> str:
        if value.startswith("/") or any(
            unicodedata.category(character).startswith("C") for character in value
        ):
            raise ValueError("source path must be a relative Git tree path")
        if any(part in {"", ".", ".."} for part in value.split("/")):
            raise ValueError("source path contains an invalid segment")
        return value

    @model_validator(mode="after")
    def fetched_files_have_identity(self) -> SourceFile:
        if self.fetch_status is FetchStatus.FETCHED:
            if self.blob_id is None or self.raw_byte_length is None or self.raw_sha256 is None:
                raise ValueError("fetched files require blob identity, byte length, and digest")
            if any(line.end_byte > self.raw_byte_length for line in self.line_map):
                raise ValueError("line map exceeds the fetched byte length")
        if self.fetch_status is FetchStatus.SKIPPED and not self.skip_reason:
            raise ValueError("skipped files require a reason")
        return self


class SourceSpan(StrictModel):
    first_line: PositiveInt
    first_column: PositiveInt
    last_line: PositiveInt
    last_column: PositiveInt
    first_byte_offset: NonNegativeInt | None = None
    last_byte_offset: NonNegativeInt | None = None

    @model_validator(mode="after")
    def ordered_span(self) -> SourceSpan:
        if (self.last_line, self.last_column) < (self.first_line, self.first_column):
            raise ValueError("source span end cannot precede its start")
        if self.first_byte_offset is not None and self.last_byte_offset is not None:
            if self.last_byte_offset < self.first_byte_offset:
                raise ValueError("byte span end cannot precede its start")
        return self


class Evidence(StrictModel):
    evidence_id: EvidenceID
    file_id: FileID
    revision_id: RevisionID
    side: RevisionSide
    span: SourceSpan
    representation: str
    raw_sha256: Sha256
    representation_sha256: Sha256
    kind: EvidenceKind
    parent_evidence_id: EvidenceID | None = None
    counterpart_evidence_id: EvidenceID | None = None
    decoding_operations: tuple[DecodeOperation, ...] = Field(default=(), max_length=2)

    @field_validator("representation")
    @classmethod
    def bounded_representation(cls, value: str) -> str:
        if _utf8_size(value) > MAX_DERIVED_EXCERPT_BYTES:
            raise ValueError("evidence representation exceeds the derived excerpt byte bound")
        return value

    @model_validator(mode="after")
    def derived_evidence_has_parent(self) -> Evidence:
        derived = self.kind in {EvidenceKind.DECODED, EvidenceKind.STRING, EvidenceKind.DIFF}
        if derived and self.parent_evidence_id is None:
            raise ValueError("derived evidence requires a parent source span")
        if not derived and self.parent_evidence_id is not None:
            raise ValueError("source evidence cannot have a derived parent")
        if self.kind is EvidenceKind.DIFF:
            if self.counterpart_evidence_id == self.parent_evidence_id:
                raise ValueError("diff counterpart evidence must have distinct provenance")
        elif self.counterpart_evidence_id is not None:
            raise ValueError("only diff evidence can carry counterpart provenance")
        if self.kind is EvidenceKind.DECODED and not self.decoding_operations:
            raise ValueError("decoded evidence requires its decoding parameters")
        if self.kind is not EvidenceKind.DECODED and self.decoding_operations:
            raise ValueError("only decoded evidence carries decoding parameters")
        limit = MAX_DERIVED_EXCERPT_BYTES if derived else MAX_SOURCE_EXCERPT_BYTES
        if _utf8_size(self.representation) > limit:
            raise ValueError("evidence representation exceeds its kind-specific byte bound")
        return self


class DeliveredEvidence(StrictModel):
    evidence_id: EvidenceID
    representation: str
    representation_sha256: Sha256

    @field_validator("representation")
    @classmethod
    def bounded_delivery(cls, value: str) -> str:
        if _utf8_size(value) > MAX_DERIVED_EXCERPT_BYTES:
            raise ValueError("delivered representation exceeds the excerpt byte bound")
        return value


class DeliveryReceipt(StrictModel):
    receipt_id: ReceiptID
    review_id: ReviewID
    turn: PositiveInt
    delivered_at: AwareDatetime
    model_route: VersionText
    tool_call_id: ToolCallID | None = None
    items: tuple[DeliveredEvidence, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def receipt_size_and_uniqueness(self) -> DeliveryReceipt:
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("a receipt cannot contain duplicate evidence IDs")
        if sum(_utf8_size(item.representation) for item in self.items) > MAX_RECEIPT_BYTES:
            raise ValueError("receipt representations exceed their aggregate byte bound")
        return self


class Relationship(StrictModel):
    relationship_id: RelationshipID
    caller_evidence_id: EvidenceID
    callee_evidence_id: EvidenceID
    kind: str = Field(min_length=1, max_length=80)
    support: RelationshipSupport
    assumptions: tuple[str, ...] = Field(default=(), max_length=16)
    analyzer_version: VersionText

    @field_validator("assumptions")
    @classmethod
    def bounded_assumptions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not item or len(item) > 500:
                raise ValueError("assumptions must contain 1-500 characters")
        return value


class SignalPointer(StrictModel):
    file_id: FileID
    note: str = Field(min_length=1, max_length=500)


class Signal(StrictModel):
    rule_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_id: EvidenceID | None = None
    pointer: SignalPointer | None = None

    @model_validator(mode="after")
    def points_to_source(self) -> Signal:
        if self.evidence_id is None and self.pointer is None:
            raise ValueError("a signal requires evidence or a non-citation pointer")
        return self


class EvidenceQuote(StrictModel):
    """A model-supplied quote, checked against delivered representation and source lines."""

    evidence_id: EvidenceID
    exact_quote: str = Field(min_length=1, max_length=2000)
    first_original_line: PositiveInt | None = None
    last_original_line: PositiveInt | None = None

    @model_validator(mode="after")
    def ordered_original_lines(self) -> EvidenceQuote:
        if (self.first_original_line is None) != (self.last_original_line is None):
            raise ValueError("both original-line boundaries are required together")
        if (
            self.first_original_line is not None
            and self.last_original_line is not None
            and self.last_original_line < self.first_original_line
        ):
            raise ValueError("last quoted line cannot precede the first")
        return self


class Finding(StrictModel):
    finding_id: FindingID
    title: str = Field(min_length=1, max_length=200)
    behavior_category: str = Field(min_length=1, max_length=100)
    impact: str = Field(min_length=1, max_length=2000)
    priority: Priority
    priority_reason: str = Field(min_length=1, max_length=1000)
    evidence_ids: tuple[EvidenceID, ...] = Field(min_length=1, max_length=24)
    evidence_quotes: tuple[EvidenceQuote, ...] = Field(default=(), max_length=24)
    trigger_context: str = Field(min_length=1, max_length=2000)
    relationship_ids: tuple[RelationshipID, ...] = Field(default=(), max_length=24)
    benign_explanation_considered: str = Field(max_length=2000)
    change_status: ChangeStatus
    unknowns: tuple[str, ...] = Field(default=(), max_length=16)

    @field_validator("evidence_ids", "relationship_ids")
    @classmethod
    def unique_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("finding references must be unique")
        return value

    @field_validator("evidence_quotes")
    @classmethod
    def unique_quotes(cls, value: tuple[EvidenceQuote, ...]) -> tuple[EvidenceQuote, ...]:
        identities = [
            (
                quote.evidence_id,
                quote.exact_quote,
                quote.first_original_line,
                quote.last_original_line,
            )
            for quote in value
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("finding evidence quotes must be unique")
        return value

    @field_validator("unknowns")
    @classmethod
    def bounded_unknowns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("unknowns must contain 1-500 characters")
        return value


class CandidateReport(StrictModel):
    """Model-owned proposal; no server authority fields are accepted here."""

    assessment: Assessment
    summary: str = Field(max_length=4000)
    findings: tuple[Finding, ...] = Field(default=(), max_length=8)
    stop_reason: StopReason

    @model_validator(mode="after")
    def empty_assessment_is_undetermined(self) -> CandidateReport:
        if not self.findings and self.assessment not in {
            Assessment.BENIGN,
            Assessment.UNDETERMINED,
        }:
            raise ValueError("an empty non-benign assessment requires findings")
        return self


class ReferenceValidation(StrictModel):
    schema_checked: Literal[True]
    source_identity_checked: Literal[True]
    delivery_checked: Literal[True]
    range_quote_checked: Literal[True]
    execution_context_support: RelationshipSupport
    change_claim_support: RelationshipSupport
    interpretation_notes: tuple[str, ...] = Field(default=(), max_length=16)


class ValidatedFinding(StrictModel):
    finding: Finding
    validation: ReferenceValidation
    display_summary: str = Field(min_length=1, max_length=4000)


class BudgetUsage(StrictModel):
    elapsed_ms: NonNegativeInt
    remaining_ms: NonNegativeInt
    github_attempts: NonNegativeInt
    model_attempts: NonNegativeInt
    decision_turns: NonNegativeInt
    tool_operations: NonNegativeInt
    distinct_blobs: NonNegativeInt
    source_bytes: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    final_attempts: NonNegativeInt
    repairs: NonNegativeInt
    tree_entries: NonNegativeInt = 0
    tree_envelope_bytes: NonNegativeInt = 0


class ErrorRecord(StrictModel):
    code: ErrorCode
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False


class Coverage(StrictModel):
    inventory_complete: bool
    listed_files: NonNegativeInt
    selected_files: NonNegativeInt
    fetched_files: NonNegativeInt
    model_shown_files: NonNegativeInt
    skipped_files: NonNegativeInt
    required_unresolved_files: tuple[FileID, ...] = Field(default=(), max_length=500)
    excluded_surfaces: tuple[str, ...] = Field(default=(), max_length=64)
    errors: tuple[ErrorRecord, ...] = Field(default=(), max_length=100)
    budget: BudgetUsage

    @model_validator(mode="after")
    def internally_consistent_counts(self) -> Coverage:
        if self.selected_files > self.listed_files:
            raise ValueError("selected files cannot exceed listed files")
        if self.fetched_files > self.selected_files:
            raise ValueError("fetched files cannot exceed selected files")
        if self.model_shown_files > self.fetched_files:
            raise ValueError("model-shown files cannot exceed fetched files")
        if self.skipped_files > self.selected_files:
            raise ValueError("skipped files cannot exceed selected files")
        return self

    @field_validator("excluded_surfaces")
    @classmethod
    def bounded_exclusions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 200 for item in value):
            raise ValueError("excluded surfaces must contain 1-200 characters")
        return value


class InvestigationStep(StrictModel):
    sequence: PositiveInt
    requested_operation: str = Field(min_length=1, max_length=80)
    short_reason: str = Field(min_length=1, max_length=500)
    issued_ids: tuple[str, ...] = Field(default=(), max_length=64)
    result_count: NonNegativeInt = 0
    elapsed_ms: NonNegativeInt
    accepted: bool
    rejection_code: ErrorCode | None = None

    @model_validator(mode="after")
    def accepted_steps_are_known_tools(self) -> InvestigationStep:
        if self.accepted:
            ToolName(self.requested_operation)
            if self.rejection_code is not None:
                raise ValueError("accepted steps cannot have a rejection code")
        return self


class Report(StrictModel):
    review_id: ReviewID
    review_input: ReviewInput
    target: PinnedRevision
    baseline: PinnedRevision | None = None
    findings: tuple[ValidatedFinding, ...] = Field(default=(), max_length=8)
    assessment: Assessment
    completion: Completion
    assumptions: tuple[str, ...] = Field(default=(), max_length=32)
    coverage: Coverage
    openclaw_version: VersionText
    model_route: VersionText
    prompt_version: VersionText
    tool_policy_version: VersionText
    analyzer_version: VersionText
    created_at: AwareDatetime
    duration_ms: NonNegativeInt
    report_version: PositiveInt

    @model_validator(mode="after")
    def revisions_have_distinct_sides(self) -> Report:
        if self.target.side is not RevisionSide.TARGET:
            raise ValueError("target revision must have target provenance")
        if self.baseline is not None and self.baseline.side is not RevisionSide.BASELINE:
            raise ValueError("baseline revision must have baseline provenance")
        if self.baseline is None:
            uncomparable = {ChangeStatus.NOT_COMPARED, ChangeStatus.UNKNOWN}
            if any(finding.finding.change_status not in uncomparable for finding in self.findings):
                raise ValueError("an absent baseline cannot support a comparison claim")
        return self

    @field_validator("assumptions")
    @classmethod
    def bounded_report_assumptions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("assumptions must contain 1-500 characters")
        return value


class JobStatus(StrictModel):
    review_id: ReviewID
    owner_id: OwnerID
    state: JobState
    phase: JobPhase
    review_input: ReviewInput
    created_at: AwareDatetime
    updated_at: AwareDatetime
    cancel_requested: bool = False

    @model_validator(mode="after")
    def terminal_state_has_terminal_phase(self) -> JobStatus:
        if (self.state is JobState.TERMINAL) != (self.phase is JobPhase.TERMINAL):
            raise ValueError("terminal job state and terminal phase must agree")
        return self


class ReviewEvent(StrictModel):
    sequence: PositiveInt
    review_id: ReviewID
    event_type: EventType
    timestamp: AwareDatetime
    message: str = Field(min_length=1, max_length=500)
    data: dict[str, str | int | bool] = Field(default_factory=dict, max_length=32)


class BrListFilesArgs(StrictModel):
    container_id: ContainerID
    side: RevisionSide
    cursor: NonNegativeInt = Field(default=0, le=20000)


class BrReadExcerptArgs(StrictModel):
    file_id: FileID
    first_original_line: PositiveInt | None = None
    last_original_line: PositiveInt | None = None
    chunk_id: ChunkID | None = None

    @model_validator(mode="after")
    def exactly_one_range_form(self) -> BrReadExcerptArgs:
        by_lines = self.first_original_line is not None or self.last_original_line is not None
        by_chunk = self.chunk_id is not None
        if by_lines == by_chunk:
            raise ValueError("provide either an original-line range or one admitted chunk ID")
        if by_lines:
            if self.first_original_line is None or self.last_original_line is None:
                raise ValueError("both original-line boundaries are required")
            if self.last_original_line < self.first_original_line:
                raise ValueError("last line cannot precede first line")
            if self.last_original_line - self.first_original_line + 1 > 160:
                raise ValueError("an excerpt cannot exceed 160 original lines")
        return self


class BrSearchSourceArgs(StrictModel):
    terms: tuple[str, ...] = Field(min_length=1, max_length=6)
    file_ids: tuple[FileID, ...] | None = Field(default=None, max_length=24)

    @field_validator("terms")
    @classmethod
    def bounded_literal_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not term or len(term) > 60 for term in value):
            raise ValueError("search terms must contain 1-60 characters")
        return value

    @field_validator("file_ids")
    @classmethod
    def unique_files(cls, value: tuple[FileID, ...] | None) -> tuple[FileID, ...] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("search file IDs must be unique")
        return value


class BrStaticDecodeArgs(StrictModel):
    source_evidence_id: EvidenceID
    operations: tuple[DecodeOperation, ...] = Field(min_length=1, max_length=2)


class BrExtractStringsArgs(StrictModel):
    file_id: FileID


class BrReadDiffArgs(StrictModel):
    file_pair_id: FilePairID
    hunk_cursor: NonNegativeInt = Field(default=0, le=200)


class BrFinishArgs(StrictModel):
    reason: ReasonText


class BrListFilesInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.LIST_FILES]
    arguments: BrListFilesArgs


class BrReadExcerptInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.READ_EXCERPT]
    arguments: BrReadExcerptArgs


class BrSearchSourceInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.SEARCH_SOURCE]
    arguments: BrSearchSourceArgs


class BrStaticDecodeInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.STATIC_DECODE]
    arguments: BrStaticDecodeArgs


class BrExtractStringsInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.EXTRACT_STRINGS]
    arguments: BrExtractStringsArgs


class BrReadDiffInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.READ_DIFF]
    arguments: BrReadDiffArgs


class BrFinishInvocation(StrictModel):
    tool_call_id: ToolCallID
    name: Literal[ToolName.FINISH]
    arguments: BrFinishArgs


ToolInvocation: TypeAlias = Annotated[
    BrListFilesInvocation
    | BrReadExcerptInvocation
    | BrSearchSourceInvocation
    | BrStaticDecodeInvocation
    | BrExtractStringsInvocation
    | BrReadDiffInvocation
    | BrFinishInvocation,
    Field(discriminator="name"),
]
TOOL_INVOCATION_ADAPTER = TypeAdapter(ToolInvocation)


class DecisionBatch(StrictModel):
    calls: tuple[ToolInvocation, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def bounded_call_array(self) -> DecisionBatch:
        call_ids = [call.tool_call_id for call in self.calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("tool call IDs must be unique within a response")
        if len(self.calls) > 1 and any(call.name is ToolName.FINISH for call in self.calls):
            raise ValueError("br_finish must be the only operation in a response")
        return self


class ToolError(StrictModel):
    code: ErrorCode
    message: str = Field(min_length=1, max_length=500)


class ToolResult(StrictModel):
    tool_call_id: ToolCallID
    name: ToolName
    succeeded: bool
    output: str = Field(max_length=16 * 1024)
    error: ToolError | None = None

    @model_validator(mode="after")
    def failures_have_structured_errors(self) -> ToolResult:
        if self.succeeded and self.error is not None:
            raise ValueError("successful tool results cannot contain an error")
        if not self.succeeded and self.error is None:
            raise ValueError("failed tool results require a structured error")
        if _utf8_size(self.output) > 16 * 1024:
            raise ValueError("tool output exceeds its UTF-8 byte bound")
        return self


def parse_tool_invocation(value: dict[str, object]) -> ToolInvocation:
    """Parse one proposed call; no parsed call is executed by this module."""

    return TOOL_INVOCATION_ADAPTER.validate_python(value)
