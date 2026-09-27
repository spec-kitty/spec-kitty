"""Regression guard for issue #3086 (fixed): merge flattens coordination metadata.

``spec-kitty merge --delete-branch`` (the default) deletes a Mission's
coordination branch (``kitty/mission-<slug>``) from git inside
``_phase_cleanup_worktrees_and_branches``. Before the #3086 fix it left the
paired ``coordination_branch`` key in that Mission's
``kitty-specs/<slug>/meta.json``, so every merged coordination Mission was left
divergent — ``meta.json`` named a ``coordination_branch`` git no longer had —
and any later command routing through ``resolve_status_surface_with_anchor``
(``coordination/surface_resolver.py``) hit ``CoordState.DELETED`` and raised
``CoordinationBranchDeleted`` (``retrospect create --update``, ``agent
retrospect``, ``implement``).

The fix makes the branch-delete gate mirror the canonical flatten already
performed by ``spec-kitty mission close --discard`` and ``spec-kitty doctor
coordination --fix``: clear ``coordination_branch`` + pop ``topology`` + set
``flattened=True``. These tests are the permanent guard that the flatten stays
wired; they graduated out of ``tests/regression/`` when the fix landed.

The primary case anchors on the *absence of* ``coordination_branch`` — the
invariant ``surface_resolver`` keys its ``CoordState.DELETED`` hard-fail on — so
it cannot be satisfied by a downstream point-guard while the root-cause
divergence remains, and it asserts the flatten is committed (clean tree), not
merely written to the working tree. The companion case pins the idempotent
no-op for a non-coord Mission.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.mission_metadata import load_meta

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity (26-char ULID); ``mid8`` is the branch/worktree
# disambiguator, slug is ``<human>-<mid8>`` per the mission-identity model.
_MISSION_ID = "01JQANARZAP70V8DVJZ8XN0M3T"
_MID8 = _MISSION_ID[:8].lower()
_SLUG = f"coordination-flatten-repro-{_MID8}"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
            cwd=repo,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


@pytest.fixture
def merged_coord_repo(tmp_path: Path) -> Path:
    """A real git repo mirroring a lane/coord Mission *at merge time*.

    The coordination branch exists in git (so the cleanup phase can delete it),
    and ``meta.json`` declares that same branch as ``coordination_branch`` — the
    state that ``merge --delete-branch`` acts on.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty Test")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "seed")
    # HEAD stays on the default branch; the coordination branch is a *separate*
    # ref so ``git branch -D`` can delete it during cleanup.
    _git(repo, "branch", _MISSION_BRANCH)

    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MISSION_ID[:8],
                "mission_slug": _SLUG,
                "coordination_branch": _MISSION_BRANCH,
                "topology": "coord",
                "flattened": False,
            },
            indent=2,
        )
        + "\n"
    )
    return repo


def test_issue_3086_merge_delete_branch_flattens_coordination_metadata(
    merged_coord_repo: Path,
) -> None:
    repo = merged_coord_repo
    feature_dir = repo / "kitty-specs" / _SLUG

    lanes_manifest = SimpleNamespace(
        mission_slug=_SLUG,  # run.mission_slug must equal lanes_manifest.mission_slug
        target_branch="main",
        mission_branch=_MISSION_BRANCH,
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    state = ConsolidationState(
        mission_id=_MISSION_ID,
        mission_slug=_SLUG,
        target_branch="main",
        wp_order=["WP01"],
    )
    run = ex._MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        # #3131 T008/T011: the coord/mission branch + marker + worktree are now
        # ONE atomic unit gated by ``teardown_coordination`` (INV-2) — a coord
        # mission with ``delete_branch=True, remove_worktree=False`` alone no
        # longer tears any of the three down (see the new RETAINS-together case
        # below). Both must be True (and ``teardown_coordination`` set) to
        # exercise the #3086 flatten-atomicity this test pins.
        remove_worktree=True,
        teardown_coordination=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )

    # Fixture sanity: the coordination branch must exist before cleanup, else a
    # false-red (the fix is gated on the branch actually being deleted).
    assert _branch_exists(repo, _MISSION_BRANCH), (
        "fixture invalid: coordination branch must exist before cleanup"
    )

    ex._phase_cleanup_worktrees_and_branches(run)

    # Corroboration: the delete path actually fired (branch gone from git). This
    # guards against a name mismatch silently no-op'ing the cleanup.
    assert not _branch_exists(repo, _MISSION_BRANCH), (
        "cleanup did not delete the coordination branch — fixture/wiring error"
    )

    # ANCHOR: after deleting the coordination branch from git, merge MUST clear
    # ``coordination_branch`` from meta.json so the Mission is flattened and later
    # status-surface resolves route to primary instead of raising
    # CoordinationBranchDeleted. Read fresh from disk.
    meta = load_meta(feature_dir)
    assert meta is not None
    assert "coordination_branch" not in meta, (
        "issue #3086: merge deleted the coordination branch from git but left "
        "'coordination_branch' in meta.json — every later status-surface resolve "
        "(retrospect create --update, agent retrospect, implement) then raises "
        "CoordinationBranchDeleted on this merged Mission"
    )

    # Canonical flatten parity with ``mission close --discard`` /
    # ``doctor coordination --fix`` (the fix must do all three mutations).
    assert meta.get("flattened") is True, (
        "issue #3086: a flattened Mission must record flattened=True"
    )
    assert "topology" not in meta, (
        "issue #3086: flatten must pop the stale 'topology' key"
    )

    # PR #3218 landing fold: the flatten must be COMMITTED, not merely written to
    # the working tree — otherwise a merged coord Mission leaves the target branch
    # dirty (the docstring's "not left dirty" contract). The assertions above read
    # on-disk content, which ``write_meta`` produces *before* the bookkeeping
    # commit is reached; a regression that dropped only the commit would pass them
    # silently. Asserting a clean tree closes that gap.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain", "--", "kitty-specs"],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert porcelain == "", (
        "issue #3086: the coordination-metadata flatten was written but not "
        f"committed — merged target left dirty: {porcelain!r}"
    )


def test_partial_retention_retains_coord_triple_together(
    merged_coord_repo: Path,
) -> None:
    """#3131 T008/T011/INV-2: partial retention must NOT half-tear the coord triple.

    ``delete_branch=True, remove_worktree=False`` resolves
    ``teardown_coordination=False`` (the coupling is an AND). Pre-#3131 this
    combination deleted the coordination branch AND flattened the marker
    (only skipping the worktree teardown) — the exact "``--keep-worktree``-on-
    coord husk" this WP fixes. The corrected coupling must retain the branch,
    the marker, and the worktree TOGETHER: nothing is torn down until BOTH
    resolved flags are True.
    """
    repo = merged_coord_repo
    feature_dir = repo / "kitty-specs" / _SLUG

    lanes_manifest = SimpleNamespace(
        mission_slug=_SLUG,  # run.mission_slug must equal lanes_manifest.mission_slug
        target_branch="main",
        mission_branch=_MISSION_BRANCH,
        lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
    )
    state = ConsolidationState(
        mission_id=_MISSION_ID,
        mission_slug=_SLUG,
        target_branch="main",
        wp_order=["WP01"],
    )
    run = ex._MergeRunState(
        main_repo=repo,
        mission_slug=_SLUG,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=False,
        teardown_coordination=False,  # delete_branch AND remove_worktree == False
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )

    assert _branch_exists(repo, _MISSION_BRANCH), (
        "fixture invalid: coordination branch must exist before cleanup"
    )
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    ex._phase_cleanup_worktrees_and_branches(run)

    # The coord branch survives: partial retention must not delete it.
    assert _branch_exists(repo, _MISSION_BRANCH), (
        "INV-2 regression: the coordination branch was deleted even though "
        "teardown_coordination=False (partial retention: delete_branch=True, "
        "remove_worktree=False) — the coord triple was half-torn."
    )

    # The marker survives untouched: no flatten attempted.
    meta = load_meta(feature_dir)
    assert meta is not None
    assert meta.get("coordination_branch") == _MISSION_BRANCH, (
        "INV-2 regression: coordination_branch was flattened out of meta.json "
        "despite teardown_coordination=False — the marker was torn down while "
        "the branch (or worktree) was meant to be retained together."
    )
    assert meta.get("flattened") is False, (
        "INV-2 regression: 'flattened' provenance was set even though the "
        "flatten never ran (teardown_coordination=False)"
    )

    # No bookkeeping commit landed (the flatten never wrote/committed anything).
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, (
        "INV-2 regression: a bookkeeping commit landed on the target branch "
        "even though teardown_coordination=False — the flatten must not have "
        "run at all in the retained-together case."
    )


def test_issue_3086_flatten_is_noop_for_non_coord_mission(tmp_path: Path) -> None:
    """The flatten guard leaves a non-coord Mission untouched (PR #3218 fold).

    A ``SINGLE_BRANCH`` / ``LANES`` (or already-flattened) Mission carries no
    ``coordination_branch`` key, so there is nothing to strand: the helper must
    early-return before mutating ``meta.json`` or attempting a bookkeeping commit.
    Covers the guard branch the coord repro above does not exercise.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Spec Kitty Test")
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "seed")

    slug = "non-coord-repro-01jqanar"
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    original = {
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "mission_slug": slug,
        "topology": "single_branch",
    }
    (feature_dir / "meta.json").write_text(json.dumps(original, indent=2) + "\n")

    run = ex._MergeRunState(
        main_repo=repo,
        mission_slug=slug,
        canonical_id=_MISSION_ID,
        canonical_mission_id=_MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=SimpleNamespace(
            target_branch="main",
            mission_branch=f"kitty/mission-{slug}",
            lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])],
        ),
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=False,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=ConsolidationState(
            mission_id=_MISSION_ID,
            mission_slug=slug,
            target_branch="main",
            wp_order=["WP01"],
        ),
        is_resume=False,
        baseline_mission_id=_MISSION_ID,
    )

    ex._flatten_coordination_metadata_after_branch_delete(run)

    meta = load_meta(feature_dir)
    assert meta is not None
    # Untouched: no coordination_branch to clear, so the guard adds no
    # ``flattened`` provenance and leaves the authored ``topology`` in place.
    assert "coordination_branch" not in meta
    assert "flattened" not in meta, (
        "issue #3086: a non-coord mission must not be marked flattened"
    )
    assert meta.get("topology") == "single_branch", (
        "issue #3086: the no-op path must not pop a non-coord mission's topology"
    )
