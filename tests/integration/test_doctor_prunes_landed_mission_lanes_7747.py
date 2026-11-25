"""#7747: after a squash landing reaches the remote primary branch, ``doctor workspaces`` rates the lanes landed.

The remedy ``consolidate`` prints for a kept lane is ``spec-kitty doctor workspaces --prune``. Before
the fix it refused the same lanes (``not_landed`` / ``CONTENT_NOT_ON_PRIMARY``): each
``lanes_with_coord`` lane carries older copies of the Mission's bookkeeping, which a squash landing
does not keep in the target's history.

Drives the real ``spec-kitty`` CLI through the harness of
``test_default_mission_consolidate_lands_primary.py`` (three lanes, implement, review, approve, default
squash ``consolidate``). The run keeps the lanes with ``--keep-worktree --keep-branch`` (run flags, not a
Mission retention, so the Mission stays released), the target is pushed to ``origin/main``, and the
doctor assessment and prune run in process. Nightly-only directory (``tests/integration``); the unit
rules live in ``tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from specify_cli.workspace.landed_worktrees import Verdict, assess_worktrees, prune_landed
from specify_cli.workspace.process_probe import ProcessProbeResult
from tests.integration.test_default_mission_consolidate_lands_primary import (
    _TARGET,
    Built,
    _lane_worktree,
    _ok,
    _quiet,
    build,
    consolidate,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_LANE_INDICES = (1, 2, 3)


def _idle(paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


@pytest.fixture(scope="module")
def pushed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Built]:
    """A squash-landed three-lane Mission whose lanes the run kept, with the target pushed to ``origin/main``."""
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        base = tmp_path_factory.mktemp("doctor-7747")
        built = build(base)
        _ok(consolidate(built, "--keep-worktree", "--keep-branch"))
        origin = base / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        git(built.root, "remote", "add", "origin", str(origin))
        git(built.root, "push", "-q", "origin", f"{_TARGET}:main")
        git(built.root, "remote", "set-head", "origin", "main")
        git(built.root, "fetch", "-q", "origin")
        yield built


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)


def test_every_lane_of_the_landed_mission_is_rated_landed_and_pruned(pushed: Built) -> None:
    assessment = assess_worktrees(pushed.root, current_dir=pushed.root, probe=_idle)
    assert assessment.error is None, assessment.error
    by_path = {verdict.path.resolve(): verdict for verdict in assessment.verdicts}
    for index in _LANE_INDICES:
        verdict = by_path[_lane_worktree(pushed, index).resolve()]
        assert verdict.verdict is Verdict.LANDED, verdict
    outcomes = prune_landed(pushed.root, current_dir=pushed.root, probe=_idle)
    removed = {outcome.path.resolve() for outcome in outcomes if outcome.removed and outcome.branch_deleted}
    assert {_lane_worktree(pushed, index).resolve() for index in _LANE_INDICES} <= removed, outcomes
    assert git(pushed.root, "branch", "--list", f"kitty/mission-{pushed.slug}-lane-*") == ""
