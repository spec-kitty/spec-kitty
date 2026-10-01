"""FIX 2 regression tests — nested safe agent commands not blocked under schema mismatch.

Before FIX 2, check_schema_version built the Invocation command_path from only
``ctx.invoked_subcommand`` (one token), so ``spec-kitty agent mission branch-context``
reached the planner as ``("agent",)`` which is NOT in SAFETY_REGISTRY, causing
a fail-closed UNSAFE → block even though the full path is explicitly registered.

After FIX 2, _build_command_path() reads sys.argv[1:] to produce the full path
tuple, and the safety registry correctly matches the nested safe commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.migration.gate import _build_command_path, check_schema_version


# ---------------------------------------------------------------------------
# Unit tests for _build_command_path()
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

class TestBuildCommandPath:
    def test_nested_command_with_flag(self) -> None:
        """Nested command path stops at first flag; argv agrees with invoked_subcommand."""
        with patch.object(sys, "argv", ["spec-kitty", "agent", "mission", "branch-context", "--json"]):
            assert _build_command_path("agent") == ("agent", "mission", "branch-context")

    def test_simple_command(self) -> None:
        with patch.object(sys, "argv", ["spec-kitty", "upgrade"]):
            assert _build_command_path("upgrade") == ("upgrade",)

    def test_flag_only_invocation_falls_back(self) -> None:
        """When argv has only flags, falls back to invoked_subcommand."""
        with patch.object(sys, "argv", ["spec-kitty", "--help"]):
            assert _build_command_path("doctor") == ("doctor",)

    def test_no_args_no_subcommand(self) -> None:
        with patch.object(sys, "argv", ["spec-kitty"]):
            assert _build_command_path(None) == ()

    def test_three_level_no_flags(self) -> None:
        with patch.object(sys, "argv", ["spec-kitty", "agent", "context", "resolve"]):
            assert _build_command_path("agent") == ("agent", "context", "resolve")

    def test_stops_before_short_flag(self) -> None:
        with patch.object(sys, "argv", ["spec-kitty", "agent", "tasks", "status", "-q"]):
            assert _build_command_path("agent") == ("agent", "tasks", "status")

    def test_argv_mismatch_falls_back_to_invoked_subcommand(self) -> None:
        """When argv[1] disagrees (pytest context), falls back to invoked_subcommand."""
        with patch.object(sys, "argv", ["/usr/bin/pytest", "tests/cli_gate/foo.py"]):
            assert _build_command_path("doctor") == ("doctor",)
            assert _build_command_path("status") == ("status",)

    def test_no_invoked_subcommand_no_argv_subcommand(self) -> None:
        """No subcommand in either sys.argv or invoked_subcommand → empty tuple."""
        with patch.object(sys, "argv", ["spec-kitty", "--version"]):
            assert _build_command_path(None) == ()


# ---------------------------------------------------------------------------
# Integration: nested safe commands must not be blocked under TOO_NEW project
# ---------------------------------------------------------------------------

_NESTED_SAFE_COMMANDS = [
    # (argv_tail, human_label)
    # NOTE: "setup-plan" is intentionally excluded — it scaffolds plan.md and
    # commits to the target branch, making it a project mutation.  It is
    # therefore UNSAFE and must block under schema mismatch.  See FIX A.
    (["agent", "check-prerequisites"], "agent_check-prerequisites_alias"),
    (["agent", "mission", "branch-context"], "agent_mission_branch-context"),
    (["agent", "mission", "check-prerequisites"], "agent_mission_check-prerequisites"),
    (["agent", "context", "resolve"], "agent_context_resolve"),
    (["agent", "tasks", "status"], "agent_tasks_status"),
]


@pytest.mark.parametrize(
    "argv_tail",
    [args for args, _ in _NESTED_SAFE_COMMANDS],
    ids=[label for _, label in _NESTED_SAFE_COMMANDS],
)
def test_nested_safe_command_not_blocked_by_too_new_project(
    argv_tail: list[str],
    fixture_project_too_new: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested safe agent commands must pass gate even when schema is too new.

    Regression: previously the gate sent only the top-level subcommand ('agent')
    to the planner, which is NOT in SAFETY_REGISTRY, causing a block. FIX 2
    sends the full path so registry lookup matches.
    """
    monkeypatch.setattr(sys, "argv", ["spec-kitty"] + argv_tail)
    # Must NOT raise SystemExit.
    check_schema_version(fixture_project_too_new, invoked_subcommand=argv_tail[0])


@pytest.mark.parametrize(
    "argv_tail",
    [args for args, _ in _NESTED_SAFE_COMMANDS],
    ids=[label for _, label in _NESTED_SAFE_COMMANDS],
)
def test_nested_safe_command_not_blocked_by_stale_project(
    argv_tail: list[str],
    fixture_project_stale: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested safe agent commands must pass gate on stale project too."""
    monkeypatch.setattr(sys, "argv", ["spec-kitty"] + argv_tail)
    check_schema_version(fixture_project_stale, invoked_subcommand=argv_tail[0])


# ---------------------------------------------------------------------------
# FIX A (P2): setup-plan is UNSAFE — it must block under schema mismatch
# ---------------------------------------------------------------------------


def test_setup_plan_blocked_by_too_new_project(
    fixture_project_too_new: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent mission setup-plan scaffolds plan.md and commits — it is UNSAFE.

    It must NOT be classified as safe.  Under a too-new schema it should
    block with exit code 5 (BLOCK_CLI_UPGRADE), not pass through.
    """
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "agent", "mission", "setup-plan"])
    with pytest.raises(SystemExit) as exc_info:
        check_schema_version(fixture_project_too_new, invoked_subcommand="agent")
    assert exc_info.value.code == 5, (
        f"Expected exit 5 (BLOCK_CLI_UPGRADE) for setup-plan, got {exc_info.value.code!r}"
    )


def test_setup_plan_blocked_by_stale_project(
    fixture_project_stale: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent mission setup-plan must also block on a stale project (BLOCK_PROJECT_MIGRATION, exit 4)."""
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "agent", "mission", "setup-plan"])
    with pytest.raises(SystemExit) as exc_info:
        check_schema_version(fixture_project_stale, invoked_subcommand="agent")
    assert exc_info.value.code == 4, (
        f"Expected exit 4 (BLOCK_PROJECT_MIGRATION) for setup-plan on stale project, "
        f"got {exc_info.value.code!r}"
    )
