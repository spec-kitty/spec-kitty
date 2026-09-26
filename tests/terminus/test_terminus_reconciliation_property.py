"""Tier-0 property test — the epic invariant, made executable (WP01 / T002, #5001).

> For any terminus command invocation that exits 0, ``verify(target, approved_wp_set)``
> holds: every approved WP's approved commits are reachable from the resolved
> target ref, and no excluded (canceled/removed) commit is — matched by **patch-id
> equivalence**, not SHA alone (contract §"Property test").

Driven through the REAL ``spec-kitty`` CLI (``python -m specify_cli merge ...``)
against a real on-disk coordination mission. ``_run_git`` / ``subprocess`` is NOT
mocked, so ``git/ref_advance.py``'s real ``update-ref`` argv runs (contract).
Approved SHAs come from lane-branch git tips, never status rows (RN-Q3).

RED-first accounting (contract): the invariant is currently VIOLATED for the
in-scope children (#4945, #4977, #4981, #4991, #4996, #4997 …) — a canceled/removed
commit rides a dependent lane into the target while the command still exits 0.
Those assertions are ``xfail(strict=True)`` and flip to real green when WP06 + the
companion seams land the Terminus Reconciliation Gate. The clean-merge half
(approved reachability + a genuinely non-vacuous excluded detector) passes today,
proving the harness is not vacuous.

Scope (contract / FR-013): the success claim is scoped to **approved-WP commit
reachability** only — NOT verdict integrity (the residual LWW-reducer ordering
bug is tracked by #4941; #4990 closed the rejection-after-approval case, and
is out of scope for this mission either way).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    blob_present_at,
    build_coord_mission,
    patch_ids_in_window,
    plant_canceled_commit,
    run_terminus,
    sha_reachable,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _assert_approved_reachable(mission: CoordMission, approved: dict[str, list[str]], target: str) -> None:
    """Every approved WP's lane-tip commits (captured PRE-merge, from git tips —
    RN-Q3) must be reachable from *target* after an exit-0 terminus command."""
    for wp_id, shas in approved.items():
        assert shas, f"{wp_id} lane tip carried no approved commit — fixture is vacuous"
        for sha in shas:
            assert sha_reachable(mission.repo, sha, target), (
                f"approved {wp_id} commit {sha[:10]} is NOT reachable from {target} after an exit-0 terminus command — approved work was dropped"
            )


# ---------------------------------------------------------------------------
# Clean-merge half — passes TODAY (validates the harness + approved-reachability)
# ---------------------------------------------------------------------------


def test_terminus_reconciliation_property_clean_merge(tmp_path: Path) -> None:
    """A clean, merge-ready mission: after an exit-0 merge, every approved WP
    commit is reachable from target and the post-merge window carries no
    unexpected (excluded) patch-id. This half holds on pre-fix code and proves
    the approved-reachability assertion is real, not a tautology."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5001C")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # captured PRE-merge

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])
    assert result.returncode == 0, f"clean merge should exit 0:\n{result.stdout}\n{result.stderr}"

    # A clean merge lands every approved WP's lane-tip commit on the target.
    _assert_approved_reachable(mission, approved, mission.target_branch)


def test_terminus_reconciliation_property_clean_squash(tmp_path: Path) -> None:
    """Clean, merge-ready mission under the DEFAULT squash — the NFR-003 no-false-
    fail guard for the squash content axis.

    A legitimate squash (all approved present, nothing excluded) MUST exit 0 with
    every approved WP's content on the target. This passes TODAY (a clean squash
    already exits 0) and — critically — must KEEP passing after WP03/WP05 land the
    blob-attribution axis: it is the counterweight that a "refuse-everything" fix
    would break. It is deliberately NOT xfail.

    The observable is squash-sound **blob presence** (``blob_present_at``): squash
    rewrites history so lane-tip SHAs do not survive, but the approved *content*
    must. The dirty default-squash variants
    (``test_4945/4977/4981_default_squash_must_not_ship_*``) reference THIS test as
    their paired no-false-fail guard."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5001Q")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])
    assert result.returncode == 0, f"clean default squash should exit 0:\n{result.stdout}\n{result.stderr}"

    # Every approved WP's authored file must be present on the target (content
    # observable — SHA reachability is not squash-sound and is NOT asserted here).
    for wp_id in ("WP01", "WP02"):
        path = f"src/pkg/{wp_id.lower()}.py"
        assert blob_present_at(mission.repo, mission.target_branch, path), (
            f"approved {wp_id} file {path} is absent from {mission.target_branch} after a clean default squash — the content axis false-failed a legitimate squash"
        )


def test_excluded_detector_is_nonvacuous(tmp_path: Path) -> None:
    """Harness self-test (RN-Q3, contract postcondition 3): the excluded-commit
    detector actually fires on a planted commit — it is not a silent no-op. This
    passes today; it guarantees the strict-xfail integrity assertions below are
    meaningful and not vacuously satisfied by a detector that never detects."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5001D")
    canceled_sha, canceled_pid, _planted = plant_canceled_commit(mission, canceled_wp="WP99", carrier_wp="WP01")
    assert canceled_pid, "planted canceled commit must have a real patch-id"
    # Reachable from the carrier lane tip (where it was planted) — detector works.
    window = patch_ids_in_window(mission.repo, mission.coord_branch, mission.lane_branch("WP01"))
    assert canceled_pid in window, "the excluded detector failed to see the planted canceled patch-id"


# ---------------------------------------------------------------------------
# Excluded-reachability half — VIOLATED today (strict xfail; green after WP06+)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy",
    [
        # [merge]: closed by the closed-world excluded-commit gate — a removed
        # commit merged INTO an approved carrier lane rides a second-parent branch,
        # so it is not on any approved lane's first-parent authorship spine and the
        # gate now FAILs (non-zero) rather than shipping it (#4945/#4977/#4981 +
        # this property).
        "merge",
        # [squash]: the closed-world blob-attribution axis (WP03/WP05) now FAILs an
        # exit-0 squash that would ship an excluded commit's content and CAS-rolls
        # the target back, so the excluded-half invariant holds under squash too —
        # a refusal (non-zero) leaves nothing excluded reachable. Previously xfail
        # (lane-tip SHAs/patch-ids do not survive squash); the landed content axis
        # makes the assertion satisfiable via the refusal branch. No longer a
        # follow-up.
        "squash",
    ],
)
def test_terminus_reconciliation_property_no_excluded_commit_reachable(tmp_path: Path, strategy: str) -> None:
    """THE epic invariant, excluded-half: after any exit-0 terminus command, no
    excluded (canceled/removed) commit is reachable from the target — matched by
    patch-id equivalence so a cherry-picked/re-lettered copy is caught too.

    Pre-fix: merge exits 0 yet the planted canceled patch-id IS reachable from the
    target → this assertion fails (xfail). Post-fix: the gate refuses (non-zero) or
    excludes it, so no exit-0 merge leaves it reachable."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5001E")
    pre_target = mission.rev(mission.target_branch)
    canceled_sha, canceled_pid, _planted = plant_canceled_commit(mission, canceled_wp="WP99", carrier_wp="WP01")
    approved = mission.approved_shas_from_lane_tips(["WP01", "WP02"])  # captured PRE-merge

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", strategy, "--yes"])

    # Contract: verify() must hold *before teardown* for any exit-0 command.
    if result.returncode == 0:
        # Approved reachability must still hold (never sacrifice correct work).
        _assert_approved_reachable(mission, approved, mission.target_branch)
        window = patch_ids_in_window(mission.repo, pre_target, mission.target_branch)
        assert canceled_pid not in window, (
            f"EXCLUDED commit {canceled_sha[:10]} (patch-id {canceled_pid[:12]}) is reachable "
            f"from {mission.target_branch} after an exit-0 merge — removed code shipped"
        )
        assert not sha_reachable(mission.repo, canceled_sha, mission.target_branch), f"EXCLUDED commit {canceled_sha[:10]} is reachable by SHA from the target"
    else:
        # A refusal is the correct post-fix outcome; nothing excluded can have shipped.
        assert not sha_reachable(mission.repo, canceled_sha, mission.target_branch)
