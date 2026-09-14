"""Redaction, path policy, and secret exclusion — the content-safety tests.

The acceptance criterion, verbatim: "Redaction fixtures show token-bearing
arguments and excluded files never enter storage, logs or browser; safe
useful paths/results still arrive."
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.live_work.redaction import (
    REDACTED,
    is_excluded_path,
    redact_command_summary,
    relativize_path,
)

pytestmark = pytest.mark.fast


# ── command summaries ────────────────────────────────────────────────────────


def test_token_flag_value_is_redacted() -> None:
    result = redact_command_summary(["curl", "--api-key", "sk-abc123def456ghi789", "https://x"])
    assert result.value is not None
    assert "sk-abc123def456ghi789" not in result.value
    assert REDACTED in result.value
    assert "curl" in result.value  # the useful program name still arrives


def test_token_flag_inline_assignment_is_redacted() -> None:
    result = redact_command_summary("deploy --token=ghp_0123456789abcdef --env prod")
    assert result.value is not None
    assert "ghp_0123456789abcdef" not in result.value
    assert "--token=[redacted]" in result.value
    assert "--env prod" in result.value


def test_secret_named_environment_assignment_is_redacted() -> None:
    result = redact_command_summary("API_TOKEN=supersecretvalue make test")
    assert result.value is not None
    assert "supersecretvalue" not in result.value
    assert "API_TOKEN=[redacted]" in result.value


def test_benign_environment_assignment_survives() -> None:
    result = redact_command_summary("NO_COLOR=1 make test-fast")
    assert result.value == "NO_COLOR=1 make test-fast"


def test_high_entropy_bare_value_is_redacted() -> None:
    result = redact_command_summary("pytest -q")
    assert result.value == "pytest -q"
    sneaky = "AKIAIOSFODNN7EXAMPLE"
    result = redact_command_summary(["aws", "s3", "ls", sneaky])
    assert result.value is not None
    assert sneaky not in result.value


def test_bearer_prefixed_value_is_redacted() -> None:
    result = redact_command_summary(["publish", "Bearer", "eyJsomecredentialedvalue1234567890"])
    assert result.value is not None
    assert "eyJsomecredentialedvalue1234567890" not in result.value
    assert REDACTED in result.value


def test_summary_is_bounded_with_an_honest_truncation_marker() -> None:
    long = " ".join(f"arg{i}" for i in range(200))
    result = redact_command_summary(long)
    assert result.value is not None
    assert len(result.value) <= 240
    assert result.value.endswith("…")


def test_empty_command_is_excluded_not_empty_string() -> None:
    assert redact_command_summary("").excluded is True
    assert redact_command_summary([]).excluded is True


# ── path policy ─────────────────────────────────────────────────────────────


def test_relative_path_passes_with_spaces_and_unicode() -> None:
    result = relativize_path("docs/design notes.md", Path("/repo"))
    assert not result.excluded
    assert result.value == "docs/design notes.md"
    unicode_result = relativize_path("docs/Über 设计.md", Path("/repo"))
    assert not unicode_result.excluded
    assert unicode_result.value == "docs/Über 设计.md"


def test_absolute_path_inside_repo_is_relativized() -> None:
    result = relativize_path("/repo/src/module.py", Path("/repo"))
    assert not result.excluded
    assert result.value == "src/module.py"


def test_absolute_path_outside_repo_fails_closed() -> None:
    result = relativize_path("/etc/passwd", Path("/repo"))
    assert result.excluded
    assert result.value is None


def test_traversal_and_backslash_and_control_fail_closed() -> None:
    assert relativize_path("../outside.py", Path("/repo")).excluded
    assert relativize_path("a/../../etc", Path("/repo")).excluded
    assert relativize_path("src\\mod.py", Path("/repo")).excluded
    assert relativize_path("src/\x00mod.py", Path("/repo")).excluded
    assert relativize_path("", Path("/repo")).excluded


def test_secret_files_are_excluded_outright() -> None:
    for path in (
        ".env",
        ".env.local",
        "secrets.json",
        "config/production.pem",
        "keys/id_rsa",
        "deploy/server.key",
        "vault/credentials.yaml",
        "service-account-prod.json",
        "legacy.kdbx",
        ".netrc",
    ):
        assert is_excluded_path(path), path
        result = relativize_path(f"/repo/{path}", Path("/repo"))
        assert result.excluded, path
        assert result.value is None  # never even a redacted placeholder on the wire


def test_ordinary_source_files_are_not_excluded() -> None:
    for path in ("src/main.py", "docs/notes.md", "tests/test_env_loader.py", "environment.md"):
        assert not is_excluded_path(path), path


def test_path_length_bound() -> None:
    long = "a" * 300 + ".py"
    result = relativize_path(long, Path("/repo"))
    assert result.excluded
    assert "240" in (result.reason or "")
