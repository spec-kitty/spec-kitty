"""The commit router never reports a coordination-dirty status log as ``unchanged``.

Intentional red-first P0 reproduction for #5513 (ADR 2026-07-17-1). Do not skip,
xfail or quarantine it: it stays red on ``main`` until the remediation lands, and
the fix PR turns it green.

Invariant: for a coordination-topology mission, a status-kind file
(``STATUS_STATE``: ``status.events.jsonl`` / ``status.json``) whose change exists
only in the coordination worktree (``.worktrees/<slug>-coord/``) and that is routed
through :func:`~specify_cli.coordination.commit_router.commit_for_mission` is
either committed on the coordination surface or refused loudly (an ``error`` /
``no_op_wrong_surface`` result, or a raised ``RuntimeError``). It is never
reported as ``unchanged`` while the coordination copy is still dirty.

The defect: the caller names the status log by its primary-checkout path
(``kitty-specs/<slug>/status.events.jsonl``). The coordination staging helper
(``_stage_artifacts_in_coord_worktree``) skips every ``STATUS_STATE`` file that
is not already inside the coordination worktree, so ``commit_paths`` comes back
empty. The wrong-surface guard (``_classify_no_commit_paths``) then inspects only
the primary checkout, finds it clean, and returns ``unchanged`` /
``no_op_already_committed``. Nothing is committed, no error surfaces, and the
caller believes the log landed.

Real git fixtures only: a real coord-topology mission
(:func:`tests.terminus.conftest.build_coord_mission`) with its materialised
coordination worktree; no mocks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.git.protection_policy import ProtectionPolicy

if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
    from tests.terminus.conftest import CoordMission

pytestmark = [pytest.mark.git_repo]

_STATUS_EVENTS = "status.events.jsonl"
_COORD_ONLY_ROW = '{"simulated": "row appended only in the coordination worktree (#5513)"}\n'
_LOUD_REFUSALS = frozenset({"error", "no_op_wrong_surface"})


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _porcelain(cwd: Path, rel: Path) -> str:
    return _git(cwd, "status", "--porcelain", "--untracked-files=all", "--", rel.as_posix())


def _coord_mission_with_coord_only_dirty_log(tmp_path: Path) -> tuple[CoordMission, Path, Path, Path]:
    """A real coord mission whose status log is dirty ONLY in the coordination worktree.

    Returns ``(mission, primary_log, coord_log, coord_worktree)``. Both copies of the
    log start committed and clean; then one row is appended to the coordination copy
    only, so the primary checkout stays clean.
    """
    from specify_cli.coordination.surface_resolver import resolve_status_surface
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from tests.terminus.conftest import build_coord_mission

    mission = build_coord_mission(tmp_path, target_branch="feature/router-5513")
    coord = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    coord_log = resolve_status_surface(mission.repo, mission.slug)
    primary_log = mission.feature_dir / _STATUS_EVENTS
    assert coord_log.is_relative_to(coord), f"fixture must put the canonical status log in the coord worktree: {coord_log}"
    assert primary_log.is_file(), f"fixture must carry a committed primary copy of the status log: {primary_log}"

    coord_rel = coord_log.relative_to(coord)
    _git(coord, "add", "--", coord_rel.as_posix())
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=coord, check=False, capture_output=True)
    assert _porcelain(coord, coord_rel) == "", "precondition: coord status log starts committed"

    with coord_log.open("a", encoding="utf-8") as fh:
        fh.write(_COORD_ONLY_ROW)

    assert _porcelain(coord, coord_rel) != "", "precondition: coord status log is dirty"
    primary_rel = primary_log.relative_to(mission.repo)
    assert _porcelain(mission.repo, primary_rel) == "", "precondition: primary status log is clean (dirty ONLY on coord)"
    return mission, primary_log, coord_log, coord


def _route_status_log(mission: CoordMission, primary_log: Path) -> CommitRouterResult:
    from specify_cli.coordination.commit_router import commit_for_mission

    return commit_for_mission(
        mission.repo,
        mission.slug,
        (primary_log,),
        "chore(status): commit the mission status log (#5513 reproduction)",
        ProtectionPolicy.resolve(mission.repo),
        kind=MissionArtifactKind.STATUS_STATE,
    )


@pytest.mark.regression
def test_router_never_reports_a_coord_only_dirty_status_log_as_unchanged(tmp_path: Path) -> None:
    """#5513: a status log dirty only in the coord worktree is committed there or refused, never ``unchanged``.

    Intentional red-first P0 reproduction for #5513 (ADR 2026-07-17-1). Do not
    skip, xfail or quarantine it; the fix PR turns it green.
    """
    mission, primary_log, coord_log, coord = _coord_mission_with_coord_only_dirty_log(tmp_path)
    coord_rel = coord_log.relative_to(coord)
    coord_head_before = _git(coord, "rev-parse", "HEAD")

    try:
        result = _route_status_log(mission, primary_log)
    except RuntimeError:
        # A raised refusal (e.g. CoordWorktreeResolutionError) is loud: the caller
        # cannot mistake it for a landed commit, so the invariant holds.
        return

    coord_dirty_after = _porcelain(coord, coord_rel)
    coord_head_after = _git(coord, "rev-parse", "HEAD")

    assert result.status != "unchanged", (
        f"commit_for_mission reported status={result.status!r} reason={result.reason!r} "
        f"placement_ref={result.placement_ref!r} for a status log that is dirty in the "
        f"coordination worktree ({coord_rel.as_posix()}: {coord_dirty_after!r}); nothing was "
        f"committed (coord HEAD unchanged: {coord_head_after == coord_head_before}) and no error "
        f"surfaced (#5513 silent skip)."
    )

    if result.status == "committed":
        assert coord_head_after != coord_head_before, "a 'committed' result must advance the coordination branch"
        assert coord_dirty_after == "", f"a 'committed' result must leave the coord status log clean: {coord_dirty_after!r}"
        committed = _git(coord, "show", f"HEAD:{coord_rel.as_posix()}")
        assert committed.endswith(_COORD_ONLY_ROW.rstrip("\n")), "the coord-only row must be in the committed log"
    else:
        assert result.status in _LOUD_REFUSALS, f"unexpected router status {result.status!r}"
        assert result.diagnostic, "a refusal must carry a diagnostic naming why the status log was not committed"
