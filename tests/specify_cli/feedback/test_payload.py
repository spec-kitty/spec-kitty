"""Unit tests for Feedback Submission payload validation and building (WP03 / T017)."""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.feedback.models import Rating, SurveyAnswers, SurveyTrigger, normalize_harness
from specify_cli.feedback.payload import (
    ALLOWED_KEYS,
    COMMENT_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    ContextFields,
    build_submission,
    collect_context,
    normalize_comment,
    parse_email,
    parse_rating,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, None),
        (1, 1),
        (5, 5),
        (6, None),
        ("3", 3),
        ("3.0", None),
        (True, None),
        (None, None),
    ],
)
def test_parse_rating_table(raw: Any, expected: int | None) -> None:
    if raw is None:
        # parse_rating only accepts str | int; None is rejected by the type
        # system but defensive callers may pass it — confirm via cast path.
        assert parse_rating(raw) is None  # type: ignore[arg-type]  # intentional negative control
        return
    result = parse_rating(raw)
    if expected is None:
        assert result is None
    else:
        assert result == Rating(expected)


@pytest.mark.parametrize(
    ("raw", "text", "truncated"),
    [
        (None, None, False),
        ("", None, False),
        ("   ", None, False),
        ("x" * COMMENT_MAX_LENGTH, "x" * COMMENT_MAX_LENGTH, False),
        ("x" * (COMMENT_MAX_LENGTH + 1), "x" * COMMENT_MAX_LENGTH, True),
        ("ä" * (COMMENT_MAX_LENGTH + 1), "ä" * COMMENT_MAX_LENGTH, True),
    ],
)
def test_normalize_comment(raw: str | None, text: str | None, truncated: bool) -> None:
    assert normalize_comment(raw) == (text, truncated)


@pytest.mark.parametrize(
    ("raw", "value", "ok"),
    [
        (None, None, True),
        ("", None, True),
        ("  ", None, True),
        ("user@example.test", "user@example.test", True),
        ("missing-at.example", None, False),
        ("has spaces@example.test", None, False),
        ("no-tld@example", None, False),
    ],
)
def test_parse_email(raw: str | None, value: str | None, ok: bool) -> None:
    assert parse_email(raw) == (value, ok)


def test_parse_email_rejects_255_char_local() -> None:
    # 255 chars total, otherwise well-shaped → length gate fires.
    long_email = "a" * (EMAIL_MAX_LENGTH - len("@e.co") + 1) + "@e.co"
    assert len(long_email) > EMAIL_MAX_LENGTH
    assert parse_email(long_email) == (None, False)


def _context(*, mission_type: str | None = "software-dev") -> ContextFields:
    return ContextFields(
        spec_kitty_version="9.9.9-test",
        distribution="spec-kitty-cli",
        trigger=SurveyTrigger.ON_DEMAND,
        harness=normalize_harness("cli"),
        os="darwin",
        mission_type=mission_type,
    )


def test_build_submission_omits_email_and_positive_control_with_email() -> None:
    without = build_submission(
        SurveyAnswers(rating=Rating(3), comment=None, email=None),
        _context(),
    )
    assert set(without) == ALLOWED_KEYS - {"email"}
    assert "email" not in without
    assert without["comment"] is None

    # Positive control: email present when provided.
    with_email = build_submission(
        SurveyAnswers(rating=Rating(3), comment="hi", email="a@b.co"),
        _context(),
    )
    assert set(with_email) == ALLOWED_KEYS
    assert with_email["email"] == "a@b.co"
    assert with_email["comment"] == "hi"


def test_collect_context_uses_installed_version_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("specify_cli.feedback.payload.get_version", lambda: "1.2.3-fixture")
    monkeypatch.setattr(
        "specify_cli.feedback.payload.resolve_distribution_profile",
        lambda: type("P", (), {"package_name": "fixture-dist"})(),
    )
    monkeypatch.setattr("specify_cli.feedback.payload.sys.platform", "linux")

    ctx = collect_context(SurveyTrigger.OP_CLOSE, normalize_harness("other"), None)
    assert ctx.spec_kitty_version == "1.2.3-fixture"
    assert ctx.distribution == "fixture-dist"
    assert ctx.os == "linux"
    assert ctx.mission_type is None
    assert ctx.trigger is SurveyTrigger.OP_CLOSE


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", "windows"),
        ("cygwin", "other"),
        ("aix", "other"),
        ("darwin", "darwin"),
    ],
)
def test_collect_context_os_family(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expected: str,
) -> None:
    monkeypatch.setattr("specify_cli.feedback.payload.get_version", lambda: "0")
    monkeypatch.setattr(
        "specify_cli.feedback.payload.resolve_distribution_profile",
        lambda: type("P", (), {"package_name": "x"})(),
    )
    monkeypatch.setattr("specify_cli.feedback.payload.sys.platform", platform)
    ctx = collect_context(SurveyTrigger.ON_DEMAND, normalize_harness("cli"), None)
    assert ctx.os == expected
