"""Safe-command matrix tests (WP08 / T033).

Verifies that every command classified as SAFE in the compat.safety registry
exits 0 even against a ``fixture_project_too_new`` project (worst-case schema
mismatch).  The gate must NOT block safe commands regardless of schema state.

Design note: these tests invoke the gate function directly
(``check_schema_version``) rather than the full Typer app to avoid the heavy
bootstrap (``ensure_runtime``, etc.) and to keep tests fast.  The gate is the
relevant chokepoint for block decisions; the nag path is covered in
``test_ci_determinism.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.migration.gate import check_schema_version

# ---------------------------------------------------------------------------
# Representative safe-command list (per compat.safety.SAFETY_REGISTRY seeds)
# ---------------------------------------------------------------------------

# These commands are SAFE under schema mismatch per SAFETY_REGISTRY seeds.
# Note: ``None`` (no subcommand / empty command_path) is NOT safe — the
# safety registry requires an explicit command_path entry.  In practice,
# ``invoked_subcommand=None`` only happens when the user typed just
# ``spec-kitty`` with no args, which shows help (intercepted by typer's
# eager option handler before the gate runs).

pytestmark = [pytest.mark.integration]

_SAFE_COMMANDS: list[tuple[str, str]] = [
    # (invoked_subcommand, human_label)
    ("upgrade", "upgrade"),
    ("migrate", "migrate"),
    ("init", "init"),
    ("status", "status"),
    ("doctor", "doctor"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subcommand",
    [cmd for cmd, _ in _SAFE_COMMANDS],
    ids=[label for _, label in _SAFE_COMMANDS],
)
def test_safe_command_not_blocked_by_too_new_project(
    subcommand: str,
    fixture_project_too_new: Path,
) -> None:
    """SAFE commands must not be blocked when the project schema is too new.

    check_schema_version should return normally (no SystemExit) for every
    safe command, even when the project schema exceeds MAX_SUPPORTED_SCHEMA.
    """
    # Should not raise SystemExit
    check_schema_version(fixture_project_too_new, invoked_subcommand=subcommand)


@pytest.mark.parametrize(
    "subcommand",
    [cmd for cmd, _ in _SAFE_COMMANDS],
    ids=[label for _, label in _SAFE_COMMANDS],
)
def test_safe_command_not_blocked_by_stale_project(
    subcommand: str,
    fixture_project_stale: Path,
) -> None:
    """SAFE commands must not be blocked when the project schema is stale."""
    check_schema_version(fixture_project_stale, invoked_subcommand=subcommand)


@pytest.mark.parametrize(
    "subcommand",
    [cmd for cmd, _ in _SAFE_COMMANDS],
    ids=[label for _, label in _SAFE_COMMANDS],
)
def test_safe_command_not_blocked_by_compatible_project(
    subcommand: str,
    fixture_project_compatible: Path,
) -> None:
    """SAFE commands must not be blocked when the project schema is compatible."""
    check_schema_version(fixture_project_compatible, invoked_subcommand=subcommand)


def test_no_subcommand_not_blocked_by_compatible_project(
    fixture_project_compatible: Path,
) -> None:
    """check_schema_version(invoked_subcommand=None) on a compatible project passes.

    This exercises the ``invoked_subcommand=None`` path (no subcommand given).
    With a compatible project the gate always passes.  The no-subcommand case
    with an incompatible project is handled by typer's eager --help option
    before the gate is invoked, so we do not need to test that combination here.
    """
    check_schema_version(fixture_project_compatible, invoked_subcommand=None)


def test_help_flag_not_blocked_for_unsafe_command_on_stale_project(
    fixture_project_stale: Path,
) -> None:
    """--help must remain available even for unsafe commands in stale projects."""
    with patch.object(sys, "argv", ["spec-kitty", "next", "--help"]):
        check_schema_version(fixture_project_stale, invoked_subcommand="next")


def test_version_flag_not_blocked_for_unsafe_command_on_stale_project(
    fixture_project_stale: Path,
) -> None:
    """--version must remain available even when the current project is stale."""
    with patch.object(sys, "argv", ["spec-kitty", "--version"]):
        check_schema_version(fixture_project_stale, invoked_subcommand="next")


def test_orchestrator_contract_version_not_blocked_on_stale_project(
    fixture_project_stale: Path,
) -> None:
    """Read-only orchestrator-api contract negotiation stays available."""
    with patch.object(sys, "argv", ["spec-kitty", "orchestrator-api", "contract-version"]):
        check_schema_version(fixture_project_stale, invoked_subcommand="orchestrator-api")


def test_orchestrator_usage_errors_not_blocked_on_stale_project(
    fixture_project_stale: Path,
) -> None:
    """Unknown orchestrator-api verbs must reach the JSON usage-error handler."""
    with patch.object(sys, "argv", ["spec-kitty", "orchestrator-api", "unknown-command"]):
        check_schema_version(fixture_project_stale, invoked_subcommand="orchestrator-api")
