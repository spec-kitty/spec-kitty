"""Tests for the charter preflight hook in ``spec-kitty implement`` (T024 / T026).

Verifies the FR-006 caller contract: the preflight gate runs **before**
any worktree allocation or ``.kittify/`` modification. On failure we
exit 1 and ``create_lane_workspace`` is never invoked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer

from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
from tests.specify_cli.cli.commands._implement_fixtures import (
    LANE_BRANCH,
    LANE_WORKTREE,
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    git,
    init_repo,
)

# The command-level cases drive the real claim against a real repository.
pytestmark = pytest.mark.git_repo

#: The ``implement`` call the command-level cases make (``@_json_safe_output`` / ``@require_main_repo`` bypassed).
_IMPLEMENT_KWARGS: dict[str, Any] = {
    "wp_id": "WP01",
    "mission": SLUG,
    "auto_commit": None,
    "json_output": False,
    "recover": False,
    "base": None,
    "acknowledge_not_bulk_edit": False,
    "actor": None,
}


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real repository the command runs in (``find_repo_root`` walks up from the cwd)."""
    root = init_repo(tmp_path / "repo")
    activate_repo(root, monkeypatch, tmp_path)
    return root


def _assert_nothing_allocated(repo: Path) -> None:
    """No lane worktree and no lane branch: the claim never reached its allocation."""
    assert not (repo / ".worktrees").exists()
    assert LANE_BRANCH not in git(repo, "branch", "--list")



def _pass_result() -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=True,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
    )


def _fail_result(reason: str = "synthesized DRG missing; run: spec-kitty charter synthesize") -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=False,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=reason,
    )


def _call_implement_unwrapped(**kwargs):
    """Invoke ``implement`` bypassing ``@_json_safe_output`` and ``@require_main_repo``."""
    from specify_cli.cli.commands import implement as implement_mod

    fn = implement_mod.implement
    # Two decorators stacked → two ``__wrapped__`` hops.
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__  # type: ignore[attr-defined]
    return fn(**kwargs)


def test_hook_does_not_abort_on_fully_absent_charter_for_implement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#3498: a fully-absent charter (fresh project) must be advisory for implement too.

    Uses the REAL runner (no mocking of ``run_charter_preflight``) so this
    exercises the actual ``allow_missing_charter`` wiring the hook must
    pass through.
    """
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    result = hook_mod.run_preflight_or_abort(tmp_path, consumer="implement")

    assert result.passed is True
    assert result.blocked_reason is None
    assert "project charter is not initialized" in capsys.readouterr().err


def test_hook_does_not_abort_on_legacy_charter_bundle_for_implement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """#3498/#2831: a legacy ``charter.md``-only bundle must also be advisory for implement."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")

    result = hook_mod.run_preflight_or_abort(tmp_path, consumer="implement")

    assert result.passed is True
    assert result.blocked_reason is None
    warning = capsys.readouterr().err
    assert "charter.md-only bundle" in warning
    assert "spec-kitty charter generate --no-from-interview" in warning


def test_implement_still_blocks_and_no_worktree_alloc_on_invalid_charter_yaml(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-regression: genuinely broken charter state still blocks implement.

    Uses the REAL runner end-to-end through the ``implement`` command (not a mocked
    ``run_charter_preflight``) against a real, claimable mission: the gate must block before the
    claim, so no lane worktree and no lane branch exist afterwards.
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("not: [valid: yaml: at: all", encoding="utf-8")
    build_mission(repo, SLUG, MISSION_ID)

    with pytest.raises(typer.Exit) as excinfo:
        _call_implement_unwrapped(**_IMPLEMENT_KWARGS)

    assert excinfo.value.exit_code == 1
    assert "charter_source" in capsys.readouterr().err
    _assert_nothing_allocated(repo)


def test_implement_aborts_before_worktree_allocation_on_failure(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A blocked preflight exits 1 before the claim allocates anything."""
    build_mission(repo, SLUG, MISSION_ID)

    with (
        patch(
            "specify_cli.charter_runtime.preflight.hook.run_charter_preflight",
            return_value=_fail_result(),
        ),
        pytest.raises(typer.Exit) as excinfo,
    ):
        _call_implement_unwrapped(**_IMPLEMENT_KWARGS)

    assert excinfo.value.exit_code == 1
    assert "synthesized DRG missing" in capsys.readouterr().err
    _assert_nothing_allocated(repo)


def test_implement_proceeds_past_preflight_when_passed(repo: Path) -> None:
    """On success the gate releases control to the downstream stages: the claim runs to completion."""
    build_mission(repo, SLUG, MISSION_ID)

    with patch(
        "specify_cli.charter_runtime.preflight.hook.run_charter_preflight",
        return_value=_pass_result(),
    ):
        _call_implement_unwrapped(**_IMPLEMENT_KWARGS)

    assert (repo / LANE_WORKTREE).is_dir()
    assert LANE_BRANCH in git(repo, "branch", "--list")
