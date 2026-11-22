from __future__ import annotations

import pytest

from beforerun.features.budgets import ReviewError
from beforerun.features.contracts import ErrorCode
from beforerun.features.github_source import parse_repository_url, validate_ref


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/example/project",
        "https://www.github.com/example/project",
        "https://github.com:443/example/project",
        "https://user@github.com/example/project",
        "https://user:pass@github.com/example/project",
        "https://github.com/example/project?ref=main",
        "https://github.com/example/project#readme",
        "https://github.com/example/project/tree/main",
        "https://github.com/example/project/blob/main/package.json",
        "https://github.com/example/project/issues/1",
        "https://github.com/example/project/pulls/1",
        "https://github.com/example/project/releases/latest",
        "https://github.com/example%2Fproject",
        "https://github.com/exa_mple/project",
        "https://github.com/example/project//",
        "https://github.com/exa\nmple/project",
        "https://github.com/example/pro\u202eject",
        "git@github.com:example/project.git",
        "file:///tmp/project",
        "/tmp/project",
        "https://github.com/example/.git",
    ],
)
def test_repository_intake_rejects_non_roots_and_authority(value: str) -> None:
    with pytest.raises(ReviewError) as caught:
        parse_repository_url(value)
    assert caught.value.code in {ErrorCode.INVALID_URL, ErrorCode.INVALID_INPUT}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/example/project", ("example", "project")),
        ("https://GitHub.com/example/project/", ("example", "project")),
        ("https://github.com/example/project.git", ("example", "project")),
        ("https://github.com/example/project.git/", ("example", "project")),
        ("https://github.com/exa-mple/pro-ject.name", ("exa-mple", "pro-ject.name")),
    ],
)
def test_repository_intake_accepts_only_documented_normalization(
    value: str, expected: tuple[str, str]
) -> None:
    assert parse_repository_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "main ",
        " main",
        "a" * 257,
        "main..next",
        "main@{upstream}",
        "main\\next",
        "main next",
        "main~1",
        "main^2",
        "refs:heads/main",
        "main?",
        "main*",
        "main[0]",
        "/main",
        "main/",
        "main.",
        "main//next",
        ".main",
        "main/.next",
        "main/next.lock",
        "main\nnext",
        "main\u202enext",
        "@",
        "-main",
    ],
)
def test_ref_validation_rejects_git_syntax_and_controls(value: str) -> None:
    with pytest.raises(ReviewError) as caught:
        validate_ref(value)
    assert caught.value.code is ErrorCode.INVALID_INPUT


@pytest.mark.parametrize(
    "value",
    [
        "main",
        "release/v1.2.3",
        "refs/heads/feature/topic",
        "a" * 40,
        "v1.0.0",
        "100%-literal",
    ],
)
def test_ref_validation_accepts_bounded_literal_references(value: str) -> None:
    assert validate_ref(value) == value
    assert validate_ref(None) is None
