"""``consolidate --dry-run`` refuses when the Mission branch is missing (#7267).

Before the 2026-11-08 operator ruling, the dry run deliberately allowed a
preview before the Mission branch existed, so it reported a clean forecast for
a Mission whose real ``consolidate`` run then refused with "Missing mission
branch" (``executor.py``'s ``_check_mission_branch`` preflight). The ruling
closed that forecast/real-run gap: the dry run now refuses with the SAME
"Missing mission branch" refusal as the real run, instead of reporting a clean
forecast.

Driven through the real ``spec-kitty consolidate --dry-run`` typer command on a
coord-topology Mission whose coordination worktree is gone and whose
mission/coordination branch has been deleted (the post-landing /
never-created window).

Provenance: #7267 (parent: the dry-run parity cluster, #7394).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.consolidation.test_issue_4764_terminus_safety import (
    MID8,
    MISSION_SLUG,
    _approved_event,
    _bootstrap_coord_mission,
    _git,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_MISSING_BRANCH_CODE = "MISSION_BRANCH_MISSING"


@pytest.fixture
def missing_branch_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_approved_event())
    coord_path = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "remove", "--force", str(coord_path))
    # The mission branch of a coord-topology Mission IS the coordination branch.
    _git(repo, "branch", "-D", f"kitty/mission-{MISSION_SLUG}")
    monkeypatch.chdir(repo)
    return repo


def _dry_run(*extra: str) -> tuple[int, str, BaseException | None]:
    result = CliRunner().invoke(cli_app, ["consolidate", "--mission", MISSION_SLUG, "--dry-run", *extra])
    return result.exit_code, result.output, result.exception


def test_dry_run_on_missing_mission_branch_exits_1_with_real_run_refusal(
    missing_branch_repo: Path,
) -> None:
    code, output, exc = _dry_run()

    assert code == 1, f"expected a handled exit 1, got {code} ({exc!r}):\n{output}"
    assert isinstance(exc, SystemExit), f"the dry run raised instead of failing closed: {exc!r}"
    assert "Missing mission branch" in output, output
    # The refusal names the branch and its remediation, like the real run.
    assert f"kitty/mission-{MISSION_SLUG}" in output, output
    assert "Traceback" not in output


def test_dry_run_json_on_missing_mission_branch_emits_error_code(
    missing_branch_repo: Path,
) -> None:
    code, output, exc = _dry_run("--json")

    assert code == 1, f"expected a handled exit 1, got {code} ({exc!r}):\n{output}"
    assert isinstance(exc, SystemExit), f"the dry run raised instead of failing closed: {exc!r}"
    payload = json.loads(output.strip().splitlines()[-1])
    assert payload["error_code"] == _MISSING_BRANCH_CODE, payload
    assert "Missing mission branch" in payload["error"], payload
