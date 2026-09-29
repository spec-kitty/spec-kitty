"""T023 – Validate-time guard: applies_to_languages [any]/[all] rejection.

FR-012: ``spec-kitty doctrine validate`` must reject an artifact that declares
``applies_to_languages: [any]`` (or ``[all]``) with an actionable message
pointing the author at the correct fix (omit the field to mean always-applicable).

Bug baseline (pre-fix): validate silently PASSes artifacts with ``[any]``/``[all]``
because there is no guard at validate time and the Pydantic schema has no enum
constraint on the list items.  The guard must fire *before* Pydantic validation,
so that the author sees the actionable language-token message rather than a
generic schema error.

RED-first discipline (DIRECTIVE-034): this test was written *before* the guard
implementation and proven to fail against pre-fix code (exit_code == 0, no
actionable "omit" / "always-applicable" message in output).  See commit message /
WP05 report for the captured pre-fix failing output.

Fixture strategy: use a *.tactic.yaml artifact that is otherwise
fully schema-valid but declares ``applies_to_languages: [any]``.  A tactic has
fewer required fields than a styleguide, making the fixture easier to keep
current without coupling the test to internal schema details.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctrine import app

runner = CliRunner()

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A minimal but schema-valid tactic YAML.  ``applies_to_languages`` is the
# only field under test here; the rest satisfies the Tactic schema so the
# guard is the FIRST thing that rejects the file.
_TACTIC_TEMPLATE = """\
schema_version: "1.0"
id: test-lang-guard
name: Test Language Guard Tactic
purpose: Fixture for apply_to_languages sentinel guard test.
steps:
  - title: Dummy step
    description: Placeholder step required by schema.
applies_to_languages:
  - {token}
"""


def _write_tactic(tmp_path: Path, token: str) -> Path:
    """Write a minimal *.tactic.yaml fixture using *token* as the language value."""
    # Use a safe filename for tokens like 'ANY' (uppercase)
    safe_name = token.lower().replace(" ", "-")
    artifact = tmp_path / f"test-{safe_name}-guard.tactic.yaml"
    artifact.write_text(
        _TACTIC_TEMPLATE.format(token=token), encoding="utf-8"
    )
    return artifact


# ---------------------------------------------------------------------------
# T023-a: ``any`` token is rejected with an actionable message
# ---------------------------------------------------------------------------


def test_validate_rejects_applies_to_languages_any(tmp_path: Path) -> None:
    """``doctrine validate`` must FAIL when applies_to_languages contains ``any``.

    FR-012: the guard is kind-agnostic and runs at validate time (post-YAML-load,
    pre-Pydantic) so authors see the actionable message rather than a schema error.

    RED-first proof: pre-fix output was a silent PASS (exit 0) because the
    Tactic Pydantic schema accepts ``["any"]`` as a valid list[str] without
    an enum constraint.  The guard makes this FAIL with the actionable message.
    """
    artifact = _write_tactic(tmp_path, "any")

    result = runner.invoke(app, ["validate", str(artifact)])

    assert result.exit_code != 0, (
        "Expected non-zero exit code but got 0.  "
        "Pre-fix: validate silently passes [any] as it satisfies list[str].  "
        f"Full output:\n{result.output}"
    )
    assert "any" in result.output.lower(), (
        f"Expected 'any' mention in error output.  Full output:\n{result.output}"
    )
    assert (
        "omit" in result.output.lower()
        or "always-applicable" in result.output.lower()
    ), (
        "Expected actionable remediation hint ('omit' or 'always-applicable') "
        f"in output.  Full output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# T023-b: ``all`` token is also rejected
# ---------------------------------------------------------------------------


def test_validate_rejects_applies_to_languages_all(tmp_path: Path) -> None:
    """``doctrine validate`` must FAIL when applies_to_languages contains ``all``.

    FR-012: both ``any`` and ``all`` are sentinel values, not language identifiers.
    """
    artifact = _write_tactic(tmp_path, "all")

    result = runner.invoke(app, ["validate", str(artifact)])

    assert result.exit_code != 0, (
        "Expected non-zero exit code but got 0.  "
        f"Full output:\n{result.output}"
    )
    # The message must mention the sentinel token class
    assert "any" in result.output.lower() or "all" in result.output.lower(), (
        f"Expected token mention in error output.  Full output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# T023-c: case-insensitive — ``ANY`` is also rejected
# ---------------------------------------------------------------------------


def test_validate_rejects_applies_to_languages_any_uppercase(tmp_path: Path) -> None:
    """Guard is case-insensitive; ``ANY`` must be rejected like ``any``."""
    artifact = _write_tactic(tmp_path, "ANY")

    result = runner.invoke(app, ["validate", str(artifact)])

    assert result.exit_code != 0, (
        "Expected non-zero exit for 'ANY' (case-insensitive guard).  "
        f"Full output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# T023-d: valid language token is still accepted (regression guard)
# ---------------------------------------------------------------------------


def test_validate_accepts_legitimate_language_token(tmp_path: Path) -> None:
    """``doctrine validate`` must NOT reject a legitimate language like ``python``.

    Regression guard: the language-token guard must not fire on real tokens.
    """
    artifact = _write_tactic(tmp_path, "python")

    result = runner.invoke(app, ["validate", str(artifact)])

    assert result.exit_code == 0, (
        "Expected exit 0 for a valid language token 'python'.  "
        f"Full output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# WP02 (#5284): reserved ``unknown`` language token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["unknown", "Unknown"])
def test_validate_rejects_reserved_unknown(tmp_path: Path, token: str) -> None:
    """RED (pins the fix): ``unknown`` is reserved and rejected with its own message.

    The message must say the value is reserved and must NOT be the any/all message.
    """
    artifact = _write_tactic(tmp_path, token)

    result = runner.invoke(app, ["validate", str(artifact)])

    out = result.output.lower()
    assert result.exit_code != 0, result.output
    assert "reserved" in out, result.output
    assert "unknown" in out, result.output
    assert "not language tokens" not in out, result.output


def test_validate_accepts_python_scope_control(tmp_path: Path) -> None:
    """GREEN control (pins unchanged behaviour): a real language token still validates."""
    artifact = _write_tactic(tmp_path, "python")

    result = runner.invoke(app, ["validate", str(artifact)])

    assert result.exit_code == 0, result.output
