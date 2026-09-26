"""Repro #5038 -- squash bookkeeping-projection proof false-REFUSEs a landed merge.

WP02 (terminus-reconciliation-attribution-integrity-01M3D4RW) found and honest-
xfailed this; WP01 of terminus-projection-driver-replay-01M3EC1K FIXES it via
driver-replay attribution (research.md Decisions 1/2, data-model.md).

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

The REFUSE reproduces when the target independently carries DIFFERENT content
for the SAME coord-partition path the mission's lane also touches (both sides
edit ``traces/WP01.md`` from a shared baseline). ``git merge --squash`` resolves
that overlap through the path's registered ``spec-kitty-traces`` merge driver
(``.gitattributes``: ``kitty-specs/**/traces/*.md merge=spec-kitty-traces`` ->
``merge_driver_traces``, a deterministic, lossless, order-preserving union --
see ``src/specify_cli/cli/commands/merge_driver.py``): the resulting target
blob equals NEITHER the checkpoint blob NOR the coord blob, but it IS the
driver's own reproducible output. The PRE-fix proof demanded raw
``coord_bytes == target_bytes`` and REFUSEd this legitimate union -- the true
(previously-unreproducible-as-filed) #5038.

**Fix disposition (this WP): driver-replay attribution.**
``bookkeeping_projection.projected_content_matches_target`` now proves, for a
path that diverged from the shared checkpoint baseline, that the landed target
blob equals the path's registered driver replayed on
``(checkpoint, pre-squash-target, coord)`` -- the SAME deterministic
computation git invoked during the real squash -- rather than demanding raw
byte equality with either parent. ``test_5038_p1_...`` below is no longer
xfailed: the legitimate union now PASSes. The proof stays fail-closed
(``git_probes.driver_replay_expected_bytes`` raises ``GitProbeError`` -> REFUSE)
for a diverged path with no registered driver, a missing blob, or a driver
error, and REFUSEs whenever the landed blob is NOT what the driver would have
produced (genuine non-landing / dropped content / tampering).
``test_5038_p2_genuine_projection_failure_still_refuses`` is RE-GROUNDED onto
that genuine-loss shape (operator ruling ``DM-01M3EC2FMWKCKGSBX1QHC7GFCJ``,
research.md Decision 2): P1's and P2's ORIGINAL scenarios were informationally
IDENTICAL to the proof (both a driver-governed lossless union), so fixing #5038
soundly necessarily flips both -- P2-as-originally-written could not stay a
REFUSE without re-introducing the false-REFUSE bug FR-001 fixes. The floor it
now guards (INV-FLOOR-1, data-model.md) is a landed blob the driver replay does
NOT reproduce -- content is genuinely dropped, not merely present-but-diverged
-- proven with real, on-disk git blobs (no git-layer mocking).

The sibling three-way-merge-content-divergence class Decision 5 already keeps
an honest ``xfail(strict=True)`` for on the blob-ATTRIBUTION axis
(``test_squash_three_way_merge_resolution_is_unattributable``,
``tests/merge/test_reconciliation.py``, #5021 residual-2) is untouched by this
fix: it is a STOCK-git conflict on a path with NO registered driver, soundly
unfixable (research.md Decision 3), and stays a distinct, narrowed xfail.

RED-first: ``test_5038_p1_...`` was driven through the REAL ``spec-kitty merge``
CLI pre-fix (no ``_run_git`` / subprocess mocking) and genuinely FAILED (not
merely xfailed) -- confirmed by re-running it under ``--runxfail`` against the
pre-fix source. It now PASSes for real through the same real CLI, post-fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.merge.bookkeeping_projection import projected_content_matches_target
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
    """Guard (P2, RE-GROUNDED onto genuine loss -- INV-FLOOR-1, data-model.md).

    A landed target blob that is NOT the registered driver's own replayed
    output on ``(checkpoint, pre-squash-target, coord)`` must still REFUSE --
    the #4981/#4970/#4973 "projected content did not actually land" class
    driver-replay attribution exists to catch. This is deliberately NOT the
    P1 shape: P1's divergence *is* the traces driver's real, reproducible
    output (a legitimate lossless union) and now PASSes (research.md
    Decision 2 -- P1's and this test's ORIGINAL scenarios were
    informationally identical to the proof, so a sound #5038 fix necessarily
    flips both; re-grounding P2 onto genuine loss is the operator-sanctioned
    disposition ``DM-01M3EC2FMWKCKGSBX1QHC7GFCJ``, not a green-wash). Here the
    landed blob is forced to drop the target's own post-checkpoint edit
    entirely -- content the deterministic union driver would ALWAYS have
    preserved -- so it can never equal the driver's replayed output. Real,
    on-disk git blobs throughout (no git-layer mocking); driven directly
    against :func:`projected_content_matches_target` (the exact seam the
    real-CLI-driven ``_assert_squash_projected_content_landed`` delegates to)
    since a real single ``spec-kitty merge`` squash of a driver-governed path
    can, by construction, only ever land the driver's own real output --
    genuine loss on THIS class of path is a distinct-mechanism failure
    (content dropped after/around the squash, not produced by it), not a
    fresh divergence shape the same real invocation can be coaxed into.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "commit.gpgsign", "false")

    slug = "terminus-01M5038B"
    trace_rel = f"kitty-specs/{slug}/{_TRACE_REL_PATH}"
    trace_path = repo / trace_rel
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text("baseline trace\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "checkpoint")
    checkpoint_sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    # Target diverges from the checkpoint after it was captured.
    trace_path.write_text("baseline trace\ntarget independently updated this trace\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "target update")
    pre_squash_target_sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    # Coord diverges from the SAME checkpoint, on a separate branch.
    git(repo, "branch", "coord", checkpoint_sha)
    git(repo, "checkout", "-q", "coord")
    trace_path.write_text("baseline trace\nlane WP01 updated this trace\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "coord update")
    git(repo, "checkout", "-q", "main")

    # Simulate a GENUINELY lossy landing: the coordination bytes verbatim,
    # silently dropping the target's own independent edit -- the naive
    # raw-copy-forward shape #4981/#4970/#4973 named, and NOT what the
    # registered ``spec-kitty-traces`` union driver would ever produce (its
    # own replay would preserve BOTH sides' lines).
    trace_path.write_text("baseline trace\nlane WP01 updated this trace\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "genuinely-lossy landing (simulated #4981-class bug)")

    assert not projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(trace_rel,),
        checkpoint_sha=checkpoint_sha,
        pre_squash_target_ref=pre_squash_target_sha,
    ), "P2 guard: a landed blob the registered driver replay does not reproduce must REFUSE, never silently PASS (C-001)."
