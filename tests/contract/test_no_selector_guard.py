"""Regression tests: every in-scope command exits cleanly on no --mission (FR-008).

Each test asserts the no-selector-error contract:
1. exit_code != 0 (prefer == 2)
2. A human-readable error message is present in the output
3. The exception is NOT a TypeError (guards against the PR #1985 crash class)

Authority: spec.md FR-008 and contracts/no-selector-error-contract.md
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.contract, pytest.mark.integration]

runner = CliRunner()


def _assert_no_selector_contract(result: Result) -> None:
    """Assert the no-selector-error contract for any command."""
    assert result.exit_code != 0, (
        f"Expected non-zero exit, got {result.exit_code}"
    )
    assert not isinstance(result.exception, TypeError), (
        f"Got TypeError (traceback risk): {result.exception}"
    )
    assert (
        "--mission" in result.output
        or "required" in result.output.lower()
        or "error" in result.output.lower()
    ), f"No user-readable error in output: {result.output!r}"


# ---------------------------------------------------------------------------
# T021 — implement and merge (WP01 source commands)
# ---------------------------------------------------------------------------


def test_implement_no_mission_exits_cleanly() -> None:
    """implement WP01 without --mission must exit non-zero cleanly (no TypeError).

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["implement", "WP01"])
    _assert_no_selector_contract(result)


def test_implement_no_mission_exits_2() -> None:
    """implement WP01 without --mission must exit with code 2 (SC-003).

    The no-selector guard raises typer.Exit(2) to match the contract used
    by all other in-scope commands (accept, next, research, etc.).
    Authority: SC-003; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["implement", "WP01"])
    assert result.exit_code == 2, (
        f"Expected exit code 2 (SC-003 no-selector contract), got {result.exit_code}"
    )


def test_merge_no_mission_exits_cleanly() -> None:
    """merge without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["consolidate"])
    _assert_no_selector_contract(result)


# ---------------------------------------------------------------------------
# T022 — next and research (WP02 source commands)
# ---------------------------------------------------------------------------


def test_next_no_mission_exits_cleanly() -> None:
    """next without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["next"])
    _assert_no_selector_contract(result)


def test_research_no_mission_exits_cleanly() -> None:
    """research without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["research"])
    _assert_no_selector_contract(result)


# ---------------------------------------------------------------------------
# T023 — context mission-resolve and accept (WP02 source commands)
# ---------------------------------------------------------------------------


def test_context_mission_resolve_no_mission_exits_cleanly() -> None:
    """context mission-resolve without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["context", "mission-resolve"])
    _assert_no_selector_contract(result)


def test_accept_no_mission_exits_cleanly() -> None:
    """accept without --mission must exit non-zero cleanly.

    accept uses typer.Exit(2) after the D-02 fix (WP02), so exit_code should be 2.
    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["accept"])
    _assert_no_selector_contract(result)


# ---------------------------------------------------------------------------
# T024 — lifecycle plan, lifecycle tasks, mission-type current (WP03 source)
# ---------------------------------------------------------------------------


def test_lifecycle_plan_no_mission_exits_cleanly() -> None:
    """lifecycle plan without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["lifecycle", "plan"])
    _assert_no_selector_contract(result)


def test_lifecycle_tasks_no_mission_exits_cleanly() -> None:
    """lifecycle tasks without --mission must exit non-zero cleanly.

    Authority: FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["lifecycle", "tasks"])
    _assert_no_selector_contract(result)


def test_mission_type_current_no_mission_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mission-type current without --mission must exit 2 (SC-003 no-selector guard).

    Creates a minimal project context (``.kittify/``) so ``get_project_root_or_exit``
    succeeds and the real no-selector guard (``raise typer.Exit(2)``) fires instead
    of the project-root guard (``raise typer.Exit(1)``).
    Authority: SC-003; FR-008; no-selector-error-contract.md.
    """
    (tmp_path / ".kittify").mkdir()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["mission-type", "current"])
    _assert_no_selector_contract(result)
    assert result.exit_code == 2, (
        f"Expected exit code 2 (SC-003 no-selector guard), got {result.exit_code}"
    )


def test_implement_recover_no_mission_exits_2() -> None:
    """implement --recover without --mission must exit 2 (SC-003 no-selector guard).

    The no-selector guard must fire BEFORE the ``--recover`` path so that
    ``implement --recover`` with no ``--mission`` also exits 2 (not 1 via
    ``detect_mission_context``).
    Authority: SC-003; FR-008; no-selector-error-contract.md.
    """
    result = runner.invoke(app, ["implement", "WP01", "--recover"])
    assert result.exit_code == 2, (
        f"Expected exit code 2 (SC-003 no-selector guard before --recover), "
        f"got {result.exit_code}"
    )
    assert not isinstance(result.exception, TypeError)
    assert "--mission" in result.output or "required" in result.output.lower()
