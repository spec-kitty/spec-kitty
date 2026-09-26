"""Repro #5038 -- squash bookkeeping-projection proof false-REFUSEs a landed merge.

WP02 (terminus-reconciliation-attribution-integrity-01M3D4RW). research.md
Decision 4 / contract P1, P2.

## Root-cause finding (T009, documented per WP02 Risk R3)

The WP02 prompt describes #5038 as: "a clean single-approved-lane DEFAULT-squash
merge is false-REFUSEd on the coord-bookkeeping projection proof... a coord-
partition bookkeeping path the target legitimately does not carry."

T009 built the DESCRIBED "clean single-approved-lane" shape (a bare
``build_coord_mission`` squash, and separately a lane-authored coord-partition
tracer file added post-checkpoint) through the REAL CLI. Neither reproduces a
REFUSE: ``_post_checkpoint_mission_paths`` is empty for a bare clean merge (the
only coord-side post-checkpoint changes are ``status.events.jsonl`` /
``status.json`` / ``meta.json``, all excluded by basename), and a lane-authored
tracer file lands on the target via the ordinary full-tree squash (which runs
BEFORE the projection proof) with byte-identical content, so the proof PASSes.

The REFUSE (this repro's ``test_5038_...`` below) DOES reproduce when the
target independently carries DIFFERENT content for the SAME coord-partition
path the mission's lane also touches (both sides edit ``traces/WP01.md`` from
a shared baseline). ``git merge --squash`` resolves that overlap as an ordinary
textual merge (auto-merge non-conflicting hunks, or -- for a genuinely
same-line conflict -- a driver-level union of both hunks); either way the
resulting target blob equals NEITHER the checkpoint blob NOR the coord blob.
``_assert_squash_projected_content_landed`` then demands byte-for-byte
coord-vs-target equality for that path and REFUSEs.

This is the SAME fundamental problem class Decision 5 already keeps an honest
``xfail(strict=True)`` for on the blob-ATTRIBUTION axis
(``test_squash_three_way_merge_resolution_is_unattributable``,
``tests/merge/test_reconciliation.py``): a target blob that equals neither
parent requires either a git-merge-simulation probe or relaxing the
disjoint-write-scope invariant the whole content-soundness model rests on --
an architectural change, not a bounded precision fix. Making THIS proof pass
on a genuine three-way-merged divergence would be the C-001 direction (weaken
a FAIL-closed gate on a genuinely ambiguous case) precisely because the
divergence is real -- narrowing ``_post_checkpoint_mission_paths`` cannot
distinguish "legitimately unprojected" from "genuinely diverged" here, since
BOTH shapes present identically (``coord_bytes present, target_bytes
different``) to the proof.

**Disposition (WP02 Risk R3): kept HONEST xfail, not fixed this WP.**
Recommend splitting #5038 back to its own issue to determine whether
production's real trigger is this three-way-content-divergence class (in
which case it converges with Epic #5001's tracked 3-way follow-up, Decision 5)
or a distinct, still-undiscovered clean trigger this investigation did not
find.

RED-first: driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking) -- no ``--resume`` needed; the REFUSE fires on the FIRST,
non-resumed run. ``test_5038_p2_genuine_projection_failure_still_refuses`` is
the P2 guard: it is not xfailed -- it asserts the SAME REFUSE fires (the gate
must never weaken), so it passes both before and after any future fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    build_coord_mission,
    run_terminus,
)
from tests.terminus.conftest import _git as git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_TRACE_REL_PATH = "traces/WP01.md"
_PROJECTION_REFUSE_TEXT = "projected coordination bookkeeping content did not land"


def _output_names_projection_refuse(stdout: str) -> bool:
    """True iff *stdout* names the squash bookkeeping-projection REFUSE.

    Whitespace is collapsed to single spaces first so a rich-console line-wrap
    (``...bookkeeping content\\ndid not land...``) still matches -- mirrors
    ``conftest.output_names_content_fail``'s same rationale for the
    reconciliation-FAIL line.
    """
    return _PROJECTION_REFUSE_TEXT in " ".join(stdout.split())


def _plant_conflicting_trace_edits(mission: CoordMission, *, baseline: str) -> None:
    """Diverge ``traces/WP01.md`` on BOTH the target and the WP01 lane branch
    from the same *baseline* (already committed at mission bootstrap via
    ``extra_base_files``), so the mission->target squash produces a target
    blob equal to NEITHER the pre-mutation checkpoint NOR the coord tip -- the
    #5038 trigger this repro's module docstring documents.
    """
    trace_path = mission.repo / "kitty-specs" / mission.slug / _TRACE_REL_PATH

    git(mission.repo, "checkout", "-q", mission.target_branch)
    trace_path.write_text(f"{baseline}\ntarget independently updated this trace\n", encoding="utf-8")
    git(mission.repo, "add", str(trace_path))
    git(mission.repo, "commit", "-q", "-m", "chore: target-side trace update (independent)")

    lane_branch = mission.lane_branch("WP01")
    git(mission.repo, "checkout", "-q", lane_branch)
    trace_path.write_text(f"{baseline}\nlane WP01 updated this trace\n", encoding="utf-8")
    git(mission.repo, "add", str(trace_path))
    git(mission.repo, "commit", "-q", "-m", "chore: WP01 trace update")
    git(mission.repo, "checkout", "-q", mission.target_branch)


@pytest.mark.xfail(
    strict=True,
    reason="#5038: the squash bookkeeping-projection proof REFUSEs a clean, "
    "first-run (non-resumed) merge when a coord-partition path (traces/WP01.md) "
    "was independently edited on BOTH the target and the approved WP01 lane "
    "from a shared baseline. The squash resolves the overlap to a blob equal "
    "to neither parent (a three-way-merge-content divergence) -- the SAME "
    "problem class Decision 5 already keeps an honest xfail for on the blob-"
    "attribution axis. Kept honest per WP02 Risk R3: fixing this precisely "
    "would weaken the gate on a genuinely divergent case (C-001); recommend "
    "splitting #5038 back to its own issue.",
)
def test_5038_p1_clean_single_lane_squash_must_not_false_refuse(tmp_path: Path) -> None:
    mission = build_coord_mission(
        tmp_path,
        wps=("WP01",),
        mid8="01M5038A",
        extra_base_files={f"kitty-specs/terminus-01M5038A/{_TRACE_REL_PATH}": "baseline trace\n"},
    )
    _plant_conflicting_trace_edits(mission, baseline="baseline trace")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, (
        "#5038: a squash merge whose bookkeeping-projection divergence is "
        "legitimately resolvable must PASS, not REFUSE with "
        f"'projected coordination bookkeeping content did not land'. "
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert not _output_names_projection_refuse(result.stdout)


def test_5038_p2_genuine_projection_failure_still_refuses(tmp_path: Path) -> None:
    """Guard (P2): the SAME divergent-content shape must still REFUSE -- proves
    any future #5038 fix narrows precision without weakening the gate on a
    genuine failed/ambiguous projection (C-001). This test is NOT xfailed: it
    must hold both before and after a fix, so it is the regression floor a
    future #5038 fix must not cross.
    """
    mission = build_coord_mission(
        tmp_path,
        wps=("WP01",),
        mid8="01M5038B",
        extra_base_files={f"kitty-specs/terminus-01M5038B/{_TRACE_REL_PATH}": "line one\nline two\nline three\n"},
    )
    trace_path = mission.repo / "kitty-specs" / mission.slug / _TRACE_REL_PATH

    # Same-line edits on both sides -- an unambiguous, unresolvable divergence
    # (stronger than P1's additive-line overlap): whatever the squash produces
    # for this path, it cannot legitimately equal coord's content AND
    # preserve target's independent edit at once.
    git(mission.repo, "checkout", "-q", mission.target_branch)
    trace_path.write_text("line one\nTARGET EDIT\nline three\n", encoding="utf-8")
    git(mission.repo, "add", str(trace_path))
    git(mission.repo, "commit", "-q", "-m", "chore: target-side conflicting edit")

    lane_branch = mission.lane_branch("WP01")
    git(mission.repo, "checkout", "-q", lane_branch)
    trace_path.write_text("line one\nLANE EDIT\nline three\n", encoding="utf-8")
    git(mission.repo, "add", str(trace_path))
    git(mission.repo, "commit", "-q", "-m", "chore: WP01 conflicting edit")
    git(mission.repo, "checkout", "-q", mission.target_branch)

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert result.returncode != 0, (
        "P2 guard: a genuine, unresolvable coord/target content divergence on a "
        "projected bookkeeping path must REFUSE, never silently PASS "
        f"(C-001). stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert _output_names_projection_refuse(result.stdout), (
        f"P2 guard: the REFUSE must be the projection-proof divergence, not some unrelated failure. stdout={result.stdout}"
    )
