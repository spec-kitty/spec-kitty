"""Repro #5051-ADJACENT -- a clean, DISJOINT-hunk 2-lane merge resolution on a
product path false-FAILs the DEFAULT squash content-attribution axis.

Mission ``terminus-merge-resolution-attribution-01M3EM3C`` WP01 (Seam A, T004).

## Scope -- this is NOT #5051's literal scenario

#5051's LITERAL pinned case is a genuine SAME-LINE conflict: two approved
lanes edit the identical line of a shared file, the squash resolves it to a
THIRD blob that is not a deterministic function of either lane's own
contribution, and that residual stays an honest ``xfail(strict=True)`` --
``test_squash_three_way_merge_resolution_is_unattributable`` in
``tests/merge/test_reconciliation.py``. This mission does **NOT** close that
xfail and this test does **NOT** claim to "close #5051"; it covers the
#5051-**adjacent** case research.md identified as the genuine, soundly-fixable
defect: two approved lanes editing **disjoint** regions of the SAME file,
whose squash resolution equals neither lane's own final blob but IS the
deterministic ``git merge-tree`` merge of the two lanes' own contributions.

## Why this repro needs TWO real ``spec-kitty merge`` invocations

``spec-kitty merge``'s lane-based fold (``lanes/merge.py::
consolidate_lane_into_mission``) processes lanes SEQUENTIALLY and its
overlap/staleness gate (``lanes/stale_check.py``) refuses a SECOND lane
whose own branch touches a file the mission branch already advanced on --
unless that lane's OWN branch first incorporates the mission branch. Doing
that incorporation on the lane branch itself would fold the earlier lane's
content INTO the later lane's own first-parent spine, which makes
``ApprovedWpCommitSet.authored_blobs`` already contain the FULL combined
blob under the (unmodified) single-lane fast path -- silently defeating this
very repro (confirmed empirically while building this fixture: that shape
stayed GREEN even with T003 reverted).

The genuinely-disjoint, neither-lane-aware-of-the-other shape this WP fixes
is real and reachable, but only via a real **interrupted-then-resumed**
merge:

1. A first, real ``spec-kitty merge`` attempt with two pure, never-merged
   lane branches genuinely FAILS the stale-lane gate on the second lane
   (before ever reaching the reconciliation gate this WP touches) -- this is
   itself a real, unavoidable product behavior, not a test artifact. Its
   failure persists ``pre_mutation_coord_sha`` (the coordination tip AT
   TRANSACTION START, i.e. BEFORE any lane folded) to
   ``.kittify/merge-state.json`` (``terminus-integrity-followups`` WP05).
2. The test harness then folds BOTH lanes into the MISSION/coordination
   branch directly (:func:`tests.terminus.conftest.fold_lanes_into_mission_
   branch`) -- never into either lane's OWN branch -- so each lane's own
   first-parent spine stays a pure, isolated edit while the mission branch's
   ancestry now covers both (satisfying ``_phase_merge_lanes``'s
   already-integrated skip on resume, so the stale gate never re-fires).
3. ``spec-kitty merge --resume`` anchors the reconciliation claim to the
   PERSISTED (step 1) pre-fold coordination tip -- never a live re-capture,
   which would by now already reflect the fold -- so
   ``ApprovedWpCommitSet.authored_blobs`` / ``multi_lane_paths`` are built
   from each lane's genuinely isolated commit, exactly the shape T001-T003
   fix.

## Root-cause (pre-fix) / post-fix

``MergeOutcomeVerifier._unattributable_content_squash``
(``src/specify_cli/merge/reconciliation.py``) pre-fix attributed an
Added/Modified target path only when ``(path, blob)`` is a member of the
flat, lane-collapsed ``authored_blobs`` set -- i.e. the path's target blob
had to equal EXACTLY ONE approved lane's own final content, byte-for-byte.
The disjoint-hunk merge's target blob matches NEITHER lane's own blob, so the
pre-fix axis named it un-attributable and FAILed the gate (CAS-reverting a
genuinely clean, lossless merge -- NFR-004 false-FAIL). Post-fix,
``ApprovedWpCommitSet.multi_lane_paths`` (T001) records the two lanes'
still-resolvable commits for a path touched by EXACTLY two approved lanes;
``is_legitimate_three_way_resolution`` (T003) simulates their deterministic
``git merge-tree --write-tree`` resolution (T002) and attributes the target
path when it matches. Everything unsound (>2 lanes, a real conflict, binary,
old git) stays fail-closed -- see ``tests/merge/test_reconciliation.py`` for
those unit-level fail-closed proofs; this file's job is only the real-CLI
green path.

RED-first: driven through the REAL ``spec-kitty merge`` CLI (``python -m
specify_cli`` against THIS worktree's own ``src`` -- see
``tests/terminus/conftest.py::run_terminus``, which sidesteps the stale-
installed-console-script trap by construction), never ``_run_git`` /
subprocess mocking. Confirmed RED (the resumed merge FAILed with an
"un-attributable" content divergence naming ``shared.py``) with T001-T003
reverted; GREEN once they landed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    blob_present_at,
    build_coord_mission_shared_file,
    fold_lanes_into_mission_branch,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_SHARED_PATH = "src/pkg/shared.py"
_WPS = ("WP01", "WP02")


def _blob_text_at(repo: Path, ref: str, path: str) -> str:
    """Read *path*'s content at *ref* via ``git show`` (never the working tree --
    the local checkout may not be sitting on *ref* after the merge command
    returns)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_5051_adjacent_clean_disjoint_hunk_merge_must_pass(tmp_path: Path) -> None:
    """Two approved lanes edit DISJOINT lines of one shared product file,
    genuinely never merging into each other; the resumed DEFAULT squash must
    PASS (exit 0) with the git-merged content on the target -- never a
    false-FAIL that CAS-reverts genuinely clean, lossless work."""
    mission = build_coord_mission_shared_file(
        tmp_path,
        wps=_WPS,
        mid8="01M5051A",
        shared_path=_SHARED_PATH,
        edits={
            "WP01": (0, "line 1 EDITED BY WP01\n"),
            "WP02": (9, "line 10 EDITED BY WP02\n"),
        },
    )

    # Step 1: a real first attempt genuinely fails the (unrelated, pre-existing)
    # stale-lane overlap gate on the second lane -- before the reconciliation
    # gate this WP touches ever runs. This persists the pre-fold coordination
    # tip to .kittify/merge-state.json (terminus-integrity-followups WP05).
    first = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])
    assert first.returncode != 0, f"expected the first attempt to hit the stale-lane gate: {first.stdout!r}"
    assert "stale" in first.stdout.lower(), f"expected a stale-lane refusal, got: {first.stdout!r}"

    # Step 2: fold both lanes into the MISSION branch itself (never into either
    # lane's own branch), so each lane's OWN first-parent spine stays a pure,
    # isolated edit while the mission branch's ancestry covers both.
    fold_lanes_into_mission_branch(mission, _WPS)

    # Step 3: resume -- the reconciliation claim anchors to the PERSISTED
    # pre-fold coordination tip, so ``multi_lane_paths`` sees each lane's
    # genuinely disjoint, never-combined contribution.
    result = run_terminus(mission, ["merge", "--resume", "--mission", mission.slug, "--yes"])

    assert result.returncode == 0, (
        "a clean, DISJOINT-hunk 2-lane merge resolution must PASS the default "
        f"squash content axis, not false-FAIL it: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert blob_present_at(mission.repo, mission.target_branch, _SHARED_PATH), (
        f"{_SHARED_PATH} must still be present on {mission.target_branch} after a PASSing merge"
    )
    merged = _blob_text_at(mission.repo, mission.target_branch, _SHARED_PATH)
    assert "EDITED BY WP01" in merged, "WP01's own disjoint-hunk edit must land on the target"
    assert "EDITED BY WP02" in merged, "WP02's own disjoint-hunk edit must land on the target"
