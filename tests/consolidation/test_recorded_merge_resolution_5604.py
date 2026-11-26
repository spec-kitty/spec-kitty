"""#5604 review fold A2: the claim skips a recorded tool merge only when the reconciliation gate would accept it.

The gate never reads the auto-rebase record: it judges a recorded merge's resolved bytes like any
other content. A resolution that wrote bytes neither parent (nor the target) has, made after the
approval, is attributable to no approved work package, so the gate FAILs it (after the run's
mutations, then rolls back). Evidence: the additive ``pyproject.toml`` auto-rebase and the
``merge=union`` merge in ``test_5604_auto_rebase_merge_attributes_e2e.py`` both reached
``Reconciliation FAILED`` before this fold.

So the claim now skips a recorded merge only when each of its own non-bookkeeping paths kept one
parent's entry or the claim's pre-run target tip's entry (the shapes the gate can attribute: a
take-one-side or target-owned resolution); otherwise it refuses with ``RESOLUTION_MERGE_UNREVIEWED``
before any branch moves, naming the re-review route (claim stays at least as strict as the gate).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import approved_bound
from specify_cli.consolidation.approved_bound import BoundRefusalCode
from specify_cli.lanes import auto_rebase_record
from tests.lanes.test_auto_rebase_record import _LANE, _MISSION, _commit, _git, _init_repo, _lane_worktree

pytestmark = pytest.mark.git_repo

_TEN = "".join(f"l{i} = {i}\n" for i in range(10))
_LANE_SIDE = _TEN.replace("l5 = 5", "l5 = 'LANE'")
_MISSION_SIDE = _TEN.replace("l5 = 5", "l5 = 'MISSION'")


def _recorded_resolution(tmp_path: Path, resolved: str, *, target_text: str | None = None) -> tuple[Path, str, str]:
    """A recorded merge of the Mission branch into the lane that resolves the ``code.py`` conflict to *resolved*.

    With *target_text* the target (``main``) commits that text after the lane and the Mission branch were cut.
    Returns the repository, the merge and the target tip.
    """
    root = _init_repo(tmp_path)
    _commit(root, "code.py", _TEN, "seed code")
    _git(root, "branch", "-f", _MISSION, "main")
    worktree = _lane_worktree(root)
    _commit(worktree, "code.py", _LANE_SIDE, "lane: edit l5")
    _git(root, "checkout", "-q", _MISSION)
    _commit(root, "code.py", _MISSION_SIDE, "mission: edit l5")
    _git(root, "checkout", "-q", "main")
    if target_text is not None:
        _commit(root, "code.py", target_text, "target: code.py")
    subprocess.run(["git", "-C", str(worktree), "merge", "--no-ff", "--no-commit", _MISSION], capture_output=True, check=False)
    (worktree / "code.py").write_text(resolved, encoding="utf-8")
    _git(worktree, "add", "code.py")
    _git(worktree, "commit", "-q", "--no-edit")
    merge = _git(worktree, "rev-parse", "HEAD")
    assert auto_rebase_record.record(root, _LANE, merge)
    return root, merge, _git(root, "rev-parse", "main")


def _refusals(root: Path, merge: str, target: str) -> list[BoundRefusalCode]:
    refusals = approved_bound.unreviewed_resolution_merges(
        root,
        lane_id="lane-a",
        branch=_LANE,
        wp_ids=("WP01",),
        merges=[merge],
        is_recorded=lambda sha: auto_rebase_record.is_recorded(root, _LANE, sha),
        is_bookkeeping=lambda _path: False,
        attributes_source=target,
    )
    return [refusal.code for refusal in refusals]


def test_a_recorded_merge_with_a_novel_resolution_is_refused_at_claim(tmp_path: Path) -> None:
    """Red before the fold: the record skipped it at claim and the gate FAILed it after the run's mutations."""
    both = _TEN.replace("l5 = 5", "l5 = 'LANE'\nl5b = 'MISSION'")
    root, merge, target = _recorded_resolution(tmp_path, both)

    assert _refusals(root, merge, target) == [BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED]


@pytest.mark.parametrize("side", [_LANE_SIDE, _MISSION_SIDE], ids=["kept_the_lane_side", "kept_the_mission_side"])
def test_a_recorded_merge_that_kept_one_side_is_still_skipped(tmp_path: Path, side: str) -> None:
    """Control: a take-one-side resolution's bytes are a parent's, which the gate attributes; the record still skips it."""
    root, merge, target = _recorded_resolution(tmp_path, side)

    assert _refusals(root, merge, target) == []


def test_a_recorded_merge_that_took_the_target_entry_is_still_skipped(tmp_path: Path) -> None:
    """Control: a target-owned resolution (the target tip's bytes, neither parent's) is unchanged on landing; skipped."""
    target_text = _TEN.replace("l5 = 5", "l5 = 'TARGET'")
    root, merge, target = _recorded_resolution(tmp_path, target_text, target_text=target_text)

    assert _refusals(root, merge, target) == []


def test_a_recorded_merge_without_a_target_tip_is_refused(tmp_path: Path) -> None:
    """No pre-run target tip: the record cannot be trusted at all (a hand merge), so the target-owned resolution refuses."""
    target_text = _TEN.replace("l5 = 5", "l5 = 'TARGET'")
    root, merge, _target = _recorded_resolution(tmp_path, target_text, target_text=target_text)

    refusals = approved_bound.unreviewed_resolution_merges(
        root,
        lane_id="lane-a",
        branch=_LANE,
        wp_ids=("WP01",),
        merges=[merge],
        is_recorded=lambda sha: auto_rebase_record.is_recorded(root, _LANE, sha),
        is_bookkeeping=lambda _path: False,
        attributes_source=None,
    )
    assert [refusal.code for refusal in refusals] == [BoundRefusalCode.RESOLUTION_MERGE_UNREVIEWED]
