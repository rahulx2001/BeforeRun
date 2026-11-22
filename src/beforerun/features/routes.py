"""Owned, same-origin review API. No route proxies arbitrary source or Gateway requests."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import ErrorCode, ReviewInput
from beforerun.features.github_source import parse_repository_url, validate_ref
from beforerun.features.job_store import IdempotencyConflict, ReviewRecord, opaque_id
from beforerun.features.review_service import ReviewService

router = APIRouter(prefix="/api", tags=["reviews"])
_COOKIE = "beforerun_session"
_OWNER = re.compile(r"\Aowner_[A-Za-z0-9_-]{16,120}\Z")
_IDEMPOTENCY = re.compile(r"\A[A-Za-z0-9_-]{8,128}\Z")


def service_for(request: Request) -> ReviewService:
    return request.app.state.review_service


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _owner(request: Request) -> tuple[str, bool]:
    value = request.cookies.get(_COOKIE)
    if value and _OWNER.fullmatch(value):
        return value, False
    return opaque_id("owner"), True


def _mutation_guard(request: Request) -> None:
    if request.headers.get("x-beforerun-request") != "1":
        raise _error(
            403, "ORIGIN_REJECTED", "Same-origin review requests require the application header."
        )
    host = request.headers.get("host", "")
    try:
        hostname = urlsplit("//" + host).hostname
        local = hostname == "localhost" or bool(
            hostname and ipaddress.ip_address(hostname).is_loopback
        )
    except ValueError:
        local = False
    if not local:
        raise _error(403, "HOST_REJECTED", "This local MVP accepts only loopback Host values.")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc.lower() != host.lower():
            raise _error(403, "ORIGIN_REJECTED", "Cross-origin review mutations are not allowed.")


def _owned(request: Request, review_id: str) -> ReviewRecord:
    owner = request.cookies.get(_COOKIE, "")
    record = service_for(request).store.owned(review_id, owner)
    if record is None:
        raise _error(
            404,
            ErrorCode.REVIEW_NOT_FOUND.value,
            "Review not found, expired, or not owned by this session.",
        )
    return record


def _with_links(record: ReviewRecord) -> dict[str, Any]:
    value = record.public_status()
    root = f"/api/reviews/{record.review_id}"
    value.update(
        {
            "events_url": f"{root}/events",
            "cancel_url": f"{root}/cancel",
            "export_url": f"{root}/export?format=json",
        }
    )
    return value


@router.get("/capabilities")
def capabilities(request: Request) -> dict[str, Any]:
    service = service_for(request)
    settings = service.settings
    return {
        "repository": "Public https://github.com/owner/repository roots only",
        "commands": ["review_only", "npm_install"],
        "project_directory": ".",
        "comparison": "Optional independently pinned ref in the same repository",
        "npm_semantics": "Declared npm 11.21.3 root install semantics; static source only",
        "limits": {
            "runtime_seconds": settings.runtime_seconds,
            "queue_seconds": settings.queue_seconds,
            "max_active_reviews": settings.max_active_reviews,
            "max_queued_reviews": settings.max_queued_reviews,
            "job_ttl_seconds": settings.job_ttl_seconds,
        },
        "pipeline_connected": service.pipeline_connected,
        "review_enabled": service.reviews_enabled,
        "ephemeral_jobs": True,
        "gateway_model_policy": service.gateway_model_policy.public_data(),
        "model_processing": (
            "Selected source and questions go through the dedicated OpenClaw reviewer "
            "to its configured cloud provider; retention is not asserted by this app. "
            + (service.gateway_model_policy.disclosure or "")
        ),
        "browser_gateway_access": False,
        "unsupported": [
            "private repositories",
            "arbitrary commands or URLs",
            "package-registry/lockfile audit",
            "full application reachability",
            "dependency, native-binary, submodule, LFS, and downloaded-payload review",
            "install guard, incident response, and whole-repository safety certification",
        ],
    }


@router.post("/reviews", status_code=202)
async def create_review(request: Request) -> JSONResponse:
    _mutation_guard(request)
    owner, new_owner = _owner(request)
    key = request.headers.get("idempotency-key")
    if key is not None and not _IDEMPOTENCY.fullmatch(key):
        raise _error(
            422, ErrorCode.INVALID_INPUT.value, "The idempotency key has an invalid format."
        )
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16 * 1024:
                raise ReviewError(
                    ErrorCode.INVALID_INPUT, "Review intake exceeds its 16 KiB body limit."
                )
        intake = ReviewInput.model_validate_json(bytes(body))
        parse_repository_url(intake.repository_url)
        validate_ref(intake.target_ref)
        validate_ref(intake.baseline_ref)
        record, replay = await service_for(request).submit(owner, intake, key)
    except ReviewError as error:
        if error.code is ErrorCode.ADMISSION_LIMIT:
            status = 429
        elif error.code is ErrorCode.OPENCLAW_UNAVAILABLE:
            status = 503
        else:
            status = 422
        raise _error(status, error.code.value, error.message) from error
    except ValidationError as error:
        fields = [
            {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors(include_input=False, include_url=False)[:8]
        ]
        raise HTTPException(
            status_code=422,
            detail={
                "code": ErrorCode.INVALID_INPUT.value,
                "message": "Review input failed validation.",
                "fields": fields,
            },
        ) from error
    except IdempotencyConflict as error:
        raise _error(409, "IDEMPOTENCY_CONFLICT", str(error)) from error
    response = JSONResponse(status_code=202, content=_with_links(record))
    if replay:
        response.headers["X-Idempotent-Replay"] = "true"
    if new_owner:
        response.set_cookie(
            _COOKIE,
            owner,
            max_age=86400,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            path="/",
        )
    return response


@router.get("/reviews/{review_id}")
def review_status(review_id: str, request: Request) -> dict[str, Any]:
    value = _with_links(_owned(request, review_id))
    policy = service_for(request).gateway_model_policy
    value["gateway_model_policy"] = policy.public_data()
    value["model_processing"] = policy.disclosure
    return value


@router.get("/reviews/{review_id}/events")
async def review_events(
    review_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    record = _owned(request, review_id)
    try:
        return await service_for(request).store.event_page(record, after, limit)
    except ReviewError as error:
        raise _error(422, error.code.value, error.message) from error


@router.get("/reviews/{review_id}/evidence/{evidence_id}")
def review_evidence(review_id: str, evidence_id: str, request: Request) -> dict[str, Any]:
    record = _owned(request, review_id)
    evidence = service_for(request).evidence(record, evidence_id)
    if evidence is None:
        raise _error(
            404, "EVIDENCE_NOT_FOUND", "Evidence not found, expired, or not owned by this review."
        )
    return evidence


@router.post("/reviews/{review_id}/cancel", status_code=202)
async def cancel_review(review_id: str, request: Request) -> dict[str, Any]:
    _mutation_guard(request)
    record = _owned(request, review_id)
    await service_for(request).cancel(record)
    return _with_links(record)


@router.get("/reviews/{review_id}/export")
def export_review(review_id: str, request: Request, format: str = "json") -> JSONResponse:
    if format != "json":
        raise _error(422, ErrorCode.INVALID_INPUT.value, "Only JSON export is supported.")
    record = _owned(request, review_id)
    content = service_for(request).export(record)
    if content is None:
        raise _error(
            409, "CHECKED_REPORT_UNAVAILABLE", "A terminal checked report is required for export."
        )
    return JSONResponse(
        content=content,
        headers={
            "Content-Disposition": f'attachment; filename="beforerun-{review_id}.json"',
            "Cache-Control": "no-store",
        },
    )
