"""Reproduction of the diagnostic half of #7755 (fixed): a per-PR guard since the fix removed its ``p0_repro`` marker.

A lanes Mission has two independent lanes that edit adjacent hunks of one file.
``consolidate`` folds lane-a into the Mission branch first; lane-b is then
stale against the in-run Mission branch, so
:func:`specify_cli.lanes.consolidation.consolidate_lane_into_mission` runs the
in-run auto-rebase (``_try_auto_rebase_if_stale``). That auto-rebase halts, but
the caller returns the original stale result and discards ``report.halt_reason``.
The operator only sees the generic stale refusal, never learns that an
auto-rebase already ran and stopped, nor which sibling lane's content is the
cause.

Scope: this covers ONLY that diagnostic gap, at ``consolidate_lane_into_mission``.
The full ``consolidate`` CLI path (the rollback restores the pre-run Mission
branch, so the old remedy was a no-op and every re-run refused identically) is
covered by ``tests/consolidation/test_7755_stale_sibling_lane_recovery.py``,
which follows the printed remedy and re-runs to a landing.

The issue offers several fixes, so the assertion is fix-agnostic: the refusal
must carry ANY of the halt reason, the sibling lane that caused the staleness,
or a statement that the in-run auto-rebase already ran and stopped. The test
drives the pre-existing entry point on real git repositories and worktrees; the
only test double is a pass-through spy that records the real auto-rebase report.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.lanes import auto_rebase
from specify_cli.lanes.auto_rebase import AutoRebaseReport
from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path
from specify_cli.lanes.consolidation import consolidate_lane_into_mission
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

_SLUG = "alpha"
_MISSION_BRANCH = "kitty/mission-alpha"
_FILE = "src/components/Popup.vue"
_SEED = "<template>\n  <div>\n    <p>title</p>\n    <p>body</p>\n  </div>\n</template>\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def _lane(lane_id: str, wp_id: str) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=("src/**",),
        predicted_surfaces=("ui",),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _build_mission(repo: Path) -> LanesManifest:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / _FILE).parent.mkdir(parents=True)
    (repo / _FILE).write_text(_SEED, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", _MISSION_BRANCH)

    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01KZ7755000000000000000000",
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[_lane("lane-a", "WP01"), _lane("lane-b", "WP02")],
        computed_at="2026-11-20T00:00:00Z",
        computed_from="test",
    )
    edits = {"lane-a": ("<p>title</p>", "<p>Title A</p>"), "lane-b": ("<p>body</p>", "<p>Body B</p>")}
    for lane_id, (old, new) in edits.items():
        branch = lane_branch_name(_SLUG, lane_id, target_branch="main")
        wt = worktree_path(repo, _SLUG, lane_id=lane_id)
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-q", "-b", branch, str(wt), _MISSION_BRANCH)
        target = wt / _FILE
        target.write_text(target.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
        _git(wt, "commit", "-q", "-am", f"{lane_id}: edit Popup.vue")
    return manifest


def test_stale_refusal_says_the_in_run_auto_rebase_already_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    manifest = _build_mission(repo)

    reports: list[AutoRebaseReport] = []
    real: Callable[..., AutoRebaseReport] = auto_rebase.attempt_auto_rebase

    def _spy(*args: object, **kwargs: object) -> AutoRebaseReport:
        report = real(*args, **kwargs)
        reports.append(report)
        return report

    monkeypatch.setattr(auto_rebase, "attempt_auto_rebase", _spy)

    first = consolidate_lane_into_mission(repo, _SLUG, "lane-a", lanes_manifest=manifest)
    assert first.success, first.errors

    second = consolidate_lane_into_mission(repo, _SLUG, "lane-b", lanes_manifest=manifest)

    # Precondition: the in-run auto-rebase really ran and halted on the conflict.
    assert not second.success
    assert reports, "the stale lane-b should have triggered the in-run auto-rebase"
    halt_reason = reports[-1].halt_reason
    assert not reports[-1].succeeded and halt_reason, reports[-1]

    # Defect (#7755): the refusal drops the halt reason, so the operator never
    # learns the in-run auto-rebase stopped, or which sibling lane caused it.
    # The generic "If the auto-rebase stops on a conflict" advice and the
    # overlapping-file list are present today and deliberately do not count.
    refusal = "\n".join(second.errors)
    reports_halt = (
        halt_reason in refusal
        or "lane-a" in refusal
        or re.search(r"auto-?rebase[^.]{0,40}\b(ran|already|stopped|halted|failed|conflicted)\b", refusal, re.IGNORECASE)
    )
    assert reports_halt, f"stale refusal does not say the in-run auto-rebase stopped ({halt_reason!r}) or name sibling lane-a; refusal was:\n{refusal}"
