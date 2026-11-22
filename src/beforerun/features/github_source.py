"""Fixed-origin, bounded GitHub REST retrieval. Target source is always treated as data."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from beforerun.features.budgets import Budget, ReviewError
from beforerun.features.contracts import (
    ErrorCode,
    PinnedRevision,
    RevisionSide,
)
from beforerun.features.settings import Settings

API_ORIGIN = "https://api.github.com"
_API_VERSION = "2026-03-10"
# The commits API can answer with only the SHA. Forty hex digits, plus room for a newline.
_COMMIT_SHA_MEDIA = "application/vnd.github.sha"
_COMMIT_SHA_LIMIT = 64
_OWNER = re.compile(r"\A[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
_REPOSITORY = re.compile(r"\A[A-Za-z0-9_.-]{1,100}\Z")


@dataclass(frozen=True, slots=True)
class Repository:
    repository_id: int
    owner: str
    name: str
    default_branch: str

    @property
    def root_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


@dataclass(frozen=True, slots=True)
class Blob:
    blob_id: str
    content: bytes


def parse_repository_url(value: str) -> tuple[str, str]:
    """Validate before any networking; only an exact public GitHub root is accepted."""

    if (
        len(value) > 2048
        or value != value.strip()
        or "%" in value
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ReviewError(
            ErrorCode.INVALID_URL,
            "Use an unencoded public GitHub repository root URL without control characters.",
        )
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as error:
        raise ReviewError(ErrorCode.INVALID_URL, "The repository URL is invalid.") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ReviewError(
            ErrorCode.INVALID_URL,
            "Only https://github.com/owner/repository is supported; "
            "no port, credentials, query, or fragment.",
        )
    parts = parsed.path.split("/")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) != 3 or parts[0] != "":
        raise ReviewError(
            ErrorCode.INVALID_URL,
            "Use a repository root URL, not a tree, blob, issue, pull-request, or release URL.",
        )
    owner, name = parts[1], parts[2]
    if name.endswith(".git"):
        name = name[:-4]
    if not _OWNER.fullmatch(owner) or not _REPOSITORY.fullmatch(name) or name in {".", ".."}:
        raise ReviewError(ErrorCode.INVALID_URL, "The GitHub owner or repository name is invalid.")
    return owner, name


def validate_ref(value: str | None) -> str | None:
    if value is None:
        return None
    invalid = ("..", "@{", "\\", " ", "~", "^", ":", "?", "*", "[")
    if (
        not value
        or len(value) > 256
        or value != value.strip()
        or value == "@"
        or value.startswith("-")
        or any(item in value for item in invalid)
        or any(unicodedata.category(character).startswith("C") for character in value)
        or value.startswith("/")
        or value.endswith("/")
        or value.endswith(".")
        or any(
            not part or part.startswith(".") or part.endswith(".lock") for part in value.split("/")
        )
    ):
        raise ReviewError(ErrorCode.INVALID_INPUT, "The requested Git ref is not valid.")
    return value


def _new_revision_id(side: RevisionSide) -> str:
    # Opaque IDs scope access; immutable commit/tree SHAs supply reproducibility.
    return f"rev_{side.value}_{secrets.token_urlsafe(18)}"


class GitHubSource:
    def __init__(
        self,
        settings: Settings,
        budget: Budget,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.budget = budget
        self._owned_client = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(20.0),
        )
        self._repositories: dict[tuple[str, str], Repository] = {}
        self._blob_cache: dict[tuple[int, str], bytes] = {}
        self._verified_revision_blobs: set[tuple[str, str]] = set()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "BeforeRun/0.1",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    async def close(self) -> None:
        if self._owned_client:
            await self.client.aclose()

    async def _read_body(
        self,
        path: str,
        *,
        byte_limit: int,
        inventory: bool = False,
        accept: str | None = None,
    ) -> bytes:
        self.budget.reserve_github()
        url = API_ORIGIN + path
        headers = self._headers()
        if accept is not None:
            headers["Accept"] = accept
        timeout = httpx.Timeout(max(0.01, min(20.0, self.budget.remaining_seconds)))
        try:
            async with self.client.stream("GET", url, timeout=timeout, headers=headers) as response:
                if response.is_redirect:
                    raise ReviewError(
                        ErrorCode.INVALID_URL,
                        "GitHub returned a redirect; it was not followed.",
                    )
                rate_limited = response.status_code == 429 or (
                    response.status_code == 403
                    and (
                        response.headers.get("Retry-After") is not None
                        or response.headers.get("X-RateLimit-Remaining") == "0"
                    )
                )
                if rate_limited:
                    raise ReviewError(
                        ErrorCode.GITHUB_RATE_LIMIT,
                        "GitHub rate limiting prevented this source read.",
                        retryable=True,
                    )
                if response.status_code == 403:
                    raise ReviewError(
                        ErrorCode.INVALID_URL,
                        "GitHub denied access to this public source request.",
                    )
                if response.status_code in {404, 422}:
                    raise ReviewError(
                        ErrorCode.REF_NOT_FOUND,
                        "The repository, ref, or object was not found.",
                    )
                if response.status_code >= 500:
                    raise ReviewError(
                        ErrorCode.OPENCLAW_UNAVAILABLE,
                        "The source service is temporarily unavailable.",
                        retryable=True,
                    )
                response.raise_for_status()
                length = response.headers.get("Content-Length")
                if length:
                    try:
                        declared_length = int(length)
                    except ValueError as error:
                        raise ReviewError(
                            ErrorCode.INVALID_INPUT,
                            "GitHub returned an invalid response length.",
                        ) from error
                    if declared_length < 0:
                        raise ReviewError(
                            ErrorCode.INVALID_INPUT,
                            "GitHub returned an invalid response length.",
                        )
                    if declared_length > byte_limit:
                        raise ReviewError(
                            ErrorCode.SOURCE_LIMIT,
                            "A GitHub response exceeds its size limit.",
                        )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    self.budget.check()
                    if inventory:
                        self.budget.add_tree_bytes(len(chunk))
                    size += len(chunk)
                    if size > byte_limit:
                        raise ReviewError(
                            ErrorCode.SOURCE_LIMIT,
                            "A GitHub response exceeded its streamed size limit.",
                        )
                    chunks.append(chunk)
        except ReviewError:
            raise
        except httpx.TimeoutException as error:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT,
                "A bounded GitHub request timed out.",
                retryable=True,
            ) from error
        except httpx.HTTPError as error:
            raise ReviewError(
                ErrorCode.OPENCLAW_UNAVAILABLE,
                "GitHub could not be reached safely.",
                retryable=True,
            ) from error
        return b"".join(chunks)

    async def _request(
        self,
        path: str,
        *,
        byte_limit: int,
        inventory: bool = False,
    ) -> dict[str, Any] | list[Any]:
        try:
            value = json.loads(
                await self._read_body(path, byte_limit=byte_limit, inventory=inventory)
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub returned malformed JSON.") from error
        if not isinstance(value, dict | list):
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub returned an unexpected JSON shape.")
        return value

    async def repository(self, owner: str, name: str) -> Repository:
        cached = self._repositories.get((owner.lower(), name.lower()))
        if cached:
            return cached
        value = await self._request(
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}",
            byte_limit=256 * 1024,
        )
        if not isinstance(value, dict):
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub metadata has an invalid shape.")
        owner_value = value.get("owner")
        try:
            repository_id = value["id"]
            canonical_owner = owner_value["login"]  # type: ignore[index]
            canonical_name = value["name"]
            default_branch = value["default_branch"]
            if (
                isinstance(repository_id, bool)
                or not isinstance(repository_id, int)
                or not isinstance(canonical_owner, str)
                or not isinstance(canonical_name, str)
                or not isinstance(default_branch, str)
            ):
                raise TypeError("repository identity fields have ambiguous types")
            repository = Repository(
                repository_id=repository_id,
                owner=canonical_owner,
                name=canonical_name,
                default_branch=default_branch,
            )
        except (KeyError, TypeError) as error:
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub metadata is incomplete.") from error
        if (
            repository.owner.casefold() != owner.casefold()
            or repository.name.casefold() != name.casefold()
        ):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub returned a different canonical repository without an admitted redirect.",
            )
        if repository.repository_id <= 0:
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub returned an invalid repository ID.")
        visibility = value.get("visibility")
        if value.get("private") is not False or (visibility is not None and visibility != "public"):
            raise ReviewError(ErrorCode.INVALID_URL, "Only public repositories are supported.")
        if not _OWNER.fullmatch(repository.owner) or not _REPOSITORY.fullmatch(repository.name):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub returned an invalid canonical repository name.",
            )
        validate_ref(repository.default_branch)
        self._repositories[(owner.lower(), name.lower())] = repository
        return repository

    async def pin(
        self,
        repository: Repository,
        requested_ref: str | None,
        side: RevisionSide,
    ) -> PinnedRevision:
        ref = validate_ref(requested_ref) or repository.default_branch
        owner = quote(repository.owner, safe="")
        name = quote(repository.name, safe="")
        # The commits API embeds every file patch. Pin only needs the commit and
        # tree SHAs, so resolve the SHA and then read the Git commit object.
        raw_sha = await self._read_body(
            f"/repos/{owner}/{name}/commits/{quote(ref, safe='')}",
            byte_limit=_COMMIT_SHA_LIMIT,
            accept=_COMMIT_SHA_MEDIA,
        )
        try:
            sha = raw_sha.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub returned an invalid full commit SHA.",
            ) from error
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub returned an invalid full commit SHA.",
            )
        value = await self._request(
            f"/repos/{owner}/{name}/git/commits/{sha}",
            byte_limit=self.settings.max_envelope_bytes,
        )
        if not isinstance(value, dict):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub commit metadata has an invalid shape.",
            )
        try:
            returned_sha = value["sha"]
            tree_sha = value["tree"]["sha"]
        except (KeyError, TypeError) as error:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub commit identity is incomplete.",
            ) from error
        if returned_sha != sha:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned Git commit identity did not match the resolved ref.",
            )
        if not isinstance(tree_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub returned an invalid tree SHA.")
        return PinnedRevision(
            revision_id=_new_revision_id(side),
            repository_id=repository.repository_id,
            canonical_owner=repository.owner,
            canonical_name=repository.name,
            requested_ref=requested_ref,
            commit_sha=sha,
            tree_sha=tree_sha,
            resolution_timestamp=datetime.now(UTC),
            side=side,
        )

    async def tree(self, revision: PinnedRevision) -> tuple[list[dict[str, Any]], bool]:
        path = (
            f"/repos/{quote(revision.canonical_owner, safe='')}/"
            f"{quote(revision.canonical_name, safe='')}/git/trees/{revision.tree_sha}?recursive=1"
        )
        value = await self._request(
            path,
            byte_limit=self.settings.max_tree_envelope_bytes,
            inventory=True,
        )
        if not isinstance(value, dict) or not isinstance(value.get("tree"), list):
            raise ReviewError(ErrorCode.INVALID_INPUT, "GitHub returned an invalid tree.")
        if value.get("sha") != revision.tree_sha:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned tree identity did not match the pinned commit tree.",
            )
        entries = value["tree"]
        admitted = self.budget.reserve_tree_entries(len(entries))
        provider_truncated = value.get("truncated", False)
        if not isinstance(provider_truncated, bool):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "GitHub returned an invalid truncation flag.",
            )
        truncated = provider_truncated or admitted < len(entries)
        return entries[:admitted], truncated

    async def blob(self, revision: PinnedRevision, expected_sha: str) -> Blob:
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
            raise ReviewError(ErrorCode.INVALID_INPUT, "A full lowercase Git blob SHA is required.")
        cache_key = (revision.repository_id, expected_sha)
        revision_cache_key = (revision.revision_id, expected_sha)
        cached = self._blob_cache.get(cache_key)
        if cached is not None and revision_cache_key in self._verified_revision_blobs:
            self.budget.add_source(revision.repository_id, expected_sha, len(cached))
            return Blob(blob_id=expected_sha, content=cached)
        path = (
            f"/repos/{quote(revision.canonical_owner, safe='')}/"
            f"{quote(revision.canonical_name, safe='')}/git/blobs/{expected_sha}"
        )
        value = await self._request(path, byte_limit=self.settings.max_envelope_bytes)
        if not isinstance(value, dict) or value.get("encoding") != "base64":
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT,
                "The selected blob uses an unsupported encoding.",
            )
        if value.get("sha") != expected_sha:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned Git blob identity did not match the tree.",
            )
        declared_size = value.get("size")
        if (
            isinstance(declared_size, bool)
            or not isinstance(declared_size, int)
            or declared_size < 0
        ):
            raise ReviewError(ErrorCode.INVALID_INPUT, "The returned blob size is invalid.")
        if declared_size > self.settings.max_file_bytes:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT,
                "The declared blob size exceeds the file-size limit.",
            )
        encoded = value.get("content")
        if not isinstance(encoded, str):
            raise ReviewError(ErrorCode.INVALID_INPUT, "The returned blob content is not text.")
        expected_encoded_length = 4 * ((declared_size + 2) // 3)
        # GitHub may wrap base64 at 60 columns, optionally with a final CRLF.
        wrapped_line_count = (expected_encoded_length + 59) // 60
        encoded_limit = expected_encoded_length + 2 * wrapped_line_count + 2
        try:
            ascii_encoded = encoded.encode("ascii")
        except UnicodeEncodeError as error:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned blob is not ASCII base64.",
            ) from error
        if len(ascii_encoded) > encoded_limit:
            raise ReviewError(
                ErrorCode.SOURCE_LIMIT,
                "The encoded blob exceeds its declared-size envelope.",
            )
        compact = ascii_encoded.replace(b"\r", b"").replace(b"\n", b"")
        if len(compact) != expected_encoded_length:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The encoded blob length did not match its declared size.",
            )
        try:
            content = base64.b64decode(compact, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned blob is not valid base64.",
            ) from error
        if declared_size != len(content):
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned blob length did not match its metadata.",
            )
        git_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if git_sha != expected_sha:
            raise ReviewError(
                ErrorCode.INVALID_INPUT,
                "The returned blob failed Git object integrity verification.",
            )
        self.budget.add_source(revision.repository_id, expected_sha, len(content))
        content = self._blob_cache.setdefault(cache_key, content)
        self._verified_revision_blobs.add(revision_cache_key)
        return Blob(blob_id=expected_sha, content=content)


def source_url(revision: PinnedRevision, path: str, first_line: int, last_line: int) -> str:
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    anchor = f"L{first_line}" if first_line == last_line else f"L{first_line}-L{last_line}"
    return (
        f"https://github.com/{quote(revision.canonical_owner, safe='')}/"
        f"{quote(revision.canonical_name, safe='')}/blob/{revision.commit_sha}/"
        f"{encoded_path}#{anchor}"
    )
