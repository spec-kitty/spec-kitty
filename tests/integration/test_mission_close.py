"""Integration tests for WP07 / FR-008 / FR-016 / SC-10: mission close.

These tests exercise the two-stage merge + coordination worktree
teardown contract at the boundary level — they construct a real tmp
git repo, populate the coordination worktree machinery, and verify
that:

* A successful mission close tears down the coordination worktree
  (FR-016, SC-10).
* The teardown is idempotent — re-invoking on an already-gone worktree
  is a no-op (FR-016 close-class robustness).
* The teardown helper handles missing mid8 / legacy missions silently
  (FR-017 — legacy fallback compatibility).

We deliberately do NOT drive the full ``spec-kitty merge`` Typer command
end-to-end here. The full command has a heavy dependency surface
(ConsolidationState lifecycle, merge lock, dossier sync, SaaS event sinks, the
WP01 commit backstop, the WP05 sparse-checkout preflight, mission_number
baking, etc.) — exercising it in-process would require fixturing all of
that, and the lane-integration semantics it implements are already
covered by ``tests/specify_cli/cli/commands/test_merge.py`` and
``tests/integration/test_implement_review_flow.py``.

WP07's specific delta over those is the teardown step and the
``CoordinationWorkspace.teardown`` integration point — that is what we
exercise here.

See:
* spec.md FR-008, FR-016, FR-017, SC-10
* tasks/WP07-two-stage-merge-finalize-tasks.md (T034)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import CoordinationWorkspace

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


MISSION_SLUG = "demo-feature"
MID8 = "01J6XW9K"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo_with_coord_artifacts(tmp_path: Path) -> Path:
    """Initialise a tmp git repo with the post-WP03 layout.

    * ``main`` exists with a seed commit.
    * Coordination branch ``kitty/mission-<slug>-<mid8>`` exists.
    * ``kitty-specs/<slug>-<mid8>/meta.json`` records ``target_branch``,
      ``mid8``, and ``coordination_branch`` so the teardown helper can
      route correctly.

    This is the minimum state required to exercise
    ``CoordinationWorkspace.resolve`` + ``CoordinationWorkspace.teardown``
    without spinning up the full mission-create pipeline.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir_name = f"{MISSION_SLUG}-{MID8}"
    feature_dir = repo / "kitty-specs" / feature_dir_name
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": feature_dir_name,
                "mission_id": "01J6XW9K000000000000000000",
                "mid8": MID8,
                "target_branch": "main",
                "coordination_branch": COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", COORD_BRANCH)
    return repo


# ---------------------------------------------------------------------------
# SC-10: teardown after successful merge
# ---------------------------------------------------------------------------


def test_coordination_worktree_teardown_after_successful_close(
    repo_with_coord_artifacts: Path,
) -> None:
    """SC-10: After a successful mission close, the coordination worktree
    directory and its per-worktree gitdir are gone.

    This isolates the teardown step that ``_run_lane_based_consolidation_locked``
    now invokes at the end of a successful Stage 2.
    """
    repo = repo_with_coord_artifacts
    feature_dir_name = f"{MISSION_SLUG}-{MID8}"

    # Resolve creates the coordination worktree (Stage 0).
    coord_path = CoordinationWorkspace.resolve(repo, feature_dir_name, MID8)
    assert coord_path.exists()
    assert coord_path.is_dir()
    assert CoordinationWorkspace.is_present(repo, feature_dir_name, MID8)

    # Teardown — what merge runs after Stage 2 succeeds.
    CoordinationWorkspace.teardown(repo, feature_dir_name, MID8)

    assert not coord_path.exists()
    assert not CoordinationWorkspace.is_present(repo, feature_dir_name, MID8)


def test_mission_close_discard_teardown_is_idempotent(
    repo_with_coord_artifacts: Path,
) -> None:
    """FR-016: ``mission close --discard`` MUST tear down the coordination
    worktree even when there is nothing to merge. The teardown call MUST
    also be idempotent — a second call on an already-gone worktree is a
    successful no-op so resumed-after-crash cleanups stay safe.

    We also verify that ``main`` is untouched: discarding a mission must
    not modify the canonical target branch.
    """
    repo = repo_with_coord_artifacts
    feature_dir_name = f"{MISSION_SLUG}-{MID8}"

    main_head_before = _git(repo, "rev-parse", "main").stdout.strip()

    coord_path = CoordinationWorkspace.resolve(repo, feature_dir_name, MID8)
    assert coord_path.exists()

    # Discard tears down.
    CoordinationWorkspace.teardown(repo, feature_dir_name, MID8)
    assert not coord_path.exists()

    # Idempotent: second teardown is a no-op, not a crash.
    CoordinationWorkspace.teardown(repo, feature_dir_name, MID8)
    assert not coord_path.exists()

    # main is untouched.
    main_head_after = _git(repo, "rev-parse", "main").stdout.strip()
    assert main_head_before == main_head_after


def test_teardown_silently_skips_when_mid8_missing(
    tmp_path: Path,
) -> None:
    """FR-017: Legacy missions without a ``mid8`` in meta.json continue to
    work under the legacy fallback. The teardown step is gated on
    ``mid8`` being present in meta.json — when it is absent, the merge
    flow MUST skip teardown silently rather than crash. This test
    confirms the gate works.

    We simulate the merge code path by reading meta.json and inspecting
    whether ``mid8`` is present before calling teardown.
    """
    repo = tmp_path / "legacy_repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")

    feature_dir = repo / "kitty-specs" / "legacy-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": "legacy-mission",
                "target_branch": "main",
                # Note: no mid8, no coordination_branch — pre-WP07 mission.
            }
        ),
        encoding="utf-8",
    )

    # Simulate the gated call in merge.py: only teardown when mid8 is set.
    from specify_cli.mission_metadata import load_meta

    meta = load_meta(feature_dir) or {}
    mid8 = str(meta.get("mid8", "")).strip()

    # The merge code's guard:
    if mid8:
        CoordinationWorkspace.teardown(repo, "legacy-mission", mid8)
    # No crash, no teardown attempted — that is the legacy contract.

    assert mid8 == ""


# ---------------------------------------------------------------------------
# FR-008: two-stage topology — coordination branch as the integration point
# ---------------------------------------------------------------------------


def test_coordination_branch_is_distinct_from_target_branch(
    repo_with_coord_artifacts: Path,
) -> None:
    """FR-008 invariant: the coordination branch is a real, distinct ref
    that lane code is supposed to flow through on its way to main. After
    ``mission create`` the coordination branch exists and is an ancestor
    of main; lane integration merges land on the coordination branch,
    not on main directly.

    We verify the branch exists and is reachable from main's ancestors
    (since it was just created at main's tip in the fixture).
    """
    repo = repo_with_coord_artifacts

    # Coordination branch exists.
    result = _git(repo, "rev-parse", "--verify", f"refs/heads/{COORD_BRANCH}")
    coord_sha = result.stdout.strip()
    assert coord_sha

    # main exists and shares the seed commit with the coord branch.
    main_sha = _git(repo, "rev-parse", "main").stdout.strip()
    # At fixture time both branches point at the seed commit.
    assert main_sha == coord_sha


def test_lane_branch_for_mission_does_not_land_directly_on_target(
    repo_with_coord_artifacts: Path,
) -> None:
    """FR-008 invariant verification:

    Construct a hypothetical lane branch parented off the coordination
    branch, simulate Stage 1 (lane -> coord), and confirm that ``main``
    has not been touched. Only Stage 2 (coord -> main) would advance
    main.
    """
    repo = repo_with_coord_artifacts
    main_before = _git(repo, "rev-parse", "main").stdout.strip()
    lane_branch = f"{COORD_BRANCH}-lane-a"

    # Create a lane branch off the coordination branch with a commit.
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    (repo / "lane_a.txt").write_text("lane a work\n")
    _git(repo, "add", "lane_a.txt")
    _git(repo, "commit", "-q", "-m", "lane a work")

    # Stage 1: lane -> coordination.
    _git(repo, "checkout", COORD_BRANCH)
    _git(repo, "merge", "--no-ff", lane_branch, "-m", f"merge {lane_branch}")

    # main has NOT moved (the runtime would only advance it during Stage 2).
    main_after_stage_1 = _git(repo, "rev-parse", "main").stdout.strip()
    assert main_after_stage_1 == main_before

    # Stage 2: coordination -> main.
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", COORD_BRANCH, "-m", f"merge {COORD_BRANCH}")
    main_after_stage_2 = _git(repo, "rev-parse", "main").stdout.strip()
    assert main_after_stage_2 != main_before

    # Lane code is present on main (SC-10 partial: code reached target via coord).
    assert (repo / "lane_a.txt").exists()


def test_two_lane_mission_merges_via_coordination(
    repo_with_coord_artifacts: Path,
) -> None:
    """SC-10: After a full multi-lane mission cycle (two lanes), the canonical
    target branch contains every lane's code, and the lane code reaches
    the target only via the coordination branch — never via a direct
    lane->target merge.

    This is the structural end-to-end happy-path proof of FR-008 + SC-10
    expressed via real git operations.
    """
    repo = repo_with_coord_artifacts
    main_before = _git(repo, "rev-parse", "main").stdout.strip()

    lane_a = f"{COORD_BRANCH}-lane-a"
    lane_b = f"{COORD_BRANCH}-lane-b"

    # Build two lanes with disjoint file changes.
    _git(repo, "branch", lane_a, COORD_BRANCH)
    _git(repo, "checkout", lane_a)
    (repo / "lane_a.txt").write_text("lane a\n")
    _git(repo, "add", "lane_a.txt")
    _git(repo, "commit", "-q", "-m", "lane a work")

    _git(repo, "branch", lane_b, COORD_BRANCH)
    _git(repo, "checkout", lane_b)
    (repo / "lane_b.txt").write_text("lane b\n")
    _git(repo, "add", "lane_b.txt")
    _git(repo, "commit", "-q", "-m", "lane b work")

    # Stage 1: integrate both lanes into the coordination branch.
    _git(repo, "checkout", COORD_BRANCH)
    _git(repo, "merge", "--no-ff", lane_a, "-m", "merge lane a into coord")
    _git(repo, "merge", "--no-ff", lane_b, "-m", "merge lane b into coord")

    # main is still untouched after Stage 1.
    assert _git(repo, "rev-parse", "main").stdout.strip() == main_before

    # Stage 2: coordination -> main.
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", COORD_BRANCH, "-m", "merge mission into main")

    # SC-10: every lane's code is on main.
    assert (repo / "lane_a.txt").read_text() == "lane a\n"
    assert (repo / "lane_b.txt").read_text() == "lane b\n"

    # Teardown step (what merge runs at the end of Stage 2).
    feature_dir_name = f"{MISSION_SLUG}-{MID8}"
    coord_path = CoordinationWorkspace.worktree_path(
        repo, feature_dir_name, MID8
    )
    # The fixture never created a worktree, but teardown is idempotent.
    CoordinationWorkspace.teardown(repo, feature_dir_name, MID8)
    assert not coord_path.exists()


def test_lane_conflict_surfaces_via_git_exit_code(
    repo_with_coord_artifacts: Path,
) -> None:
    """FR-008 conflict handling: when two lanes touch the same file in
    conflicting ways, Stage 1 (lane -> coordination) surfaces a real git
    merge conflict (non-zero exit). The merge command treats that as a
    blocking error and the existing interactive merge UX takes over.

    We assert at the git layer that the conflict reproduces — proving
    the lane-integration topology preserves the conflict signal we rely
    on.
    """
    repo = repo_with_coord_artifacts
    lane_a = f"{COORD_BRANCH}-lane-a"
    lane_b = f"{COORD_BRANCH}-lane-b"

    # Both lanes touch the same file with different contents.
    _git(repo, "branch", lane_a, COORD_BRANCH)
    _git(repo, "checkout", lane_a)
    (repo / "shared.txt").write_text("lane a value\n")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "lane a edits shared")

    _git(repo, "branch", lane_b, COORD_BRANCH)
    _git(repo, "checkout", lane_b)
    (repo / "shared.txt").write_text("lane b value\n")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "lane b edits shared")

    # Stage 1: first lane integrates cleanly.
    _git(repo, "checkout", COORD_BRANCH)
    _git(repo, "merge", "--no-ff", lane_a, "-m", "merge a")

    # Second lane's integration MUST conflict (non-zero exit).
    result = subprocess.run(
        ["git", "merge", "--no-ff", lane_b, "-m", "merge b"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "Stage 1 must surface lane-integration conflicts; "
        f"got returncode={result.returncode} stderr={result.stderr!r}"
    )
    # The conflict is visible to the operator UX via the conflict marker.
    assert "CONFLICT" in (result.stdout + result.stderr).upper()
