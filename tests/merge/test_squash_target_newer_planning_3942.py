"""Red-first reproduction for #3942 (target-newer planning-file clobber).

Defect (LIVE on HEAD)
---------------------
``spec-kitty merge`` folds the mission branch into the target with a squash merge
implemented in ``specify_cli.lanes.merge._merge_branch_into`` as::

    git merge --squash -X theirs <mission_branch>   # lanes/merge.py:635

``-X theirs`` resolves every conflicting hunk in favour of the mission branch
(the *source*). The custom-driver registry (``_MERGE_DRIVERS``,
``lanes/merge.py:59-121``) reconciles only six allowlisted ``kitty-specs/**``
bookkeeping classes (event logs, ``meta.json``, traces, acceptance-matrix,
issue-matrix, review-cycle verdicts). Every *other* ``kitty-specs/`` file — the
PRIMARY-partition planning artifacts ``spec.md`` and ``tasks/WP*.md`` among them —
falls through to the blanket ``-X theirs`` resolution. There is **no recency
guard**: when the target branch carries a *newer* edit to such a file (because
planning was refined on the target after the mission branch forked), the *older*
mission-branch copy silently wins and the target-newer content is clobbered.

The sibling #2709 guard proves the ``meta.json`` case is reconciled (it carries a
driver). This test drives the SAME real, supported squash-merge entry point
``integrate_mission_into_target(..., strategy=MergeStrategy.SQUASH)`` against a
driver-uncovered primary-artifact-kind file and asserts the target-newer content
survives. On HEAD it FAILS (older lane copy wins); it turns GREEN only once WP02
adds the recency guard, at which point the ``xfail(strict=True)`` marker is
removed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from mission_runtime import is_primary_artifact_kind, kind_for_mission_file
from specify_cli.lanes.merge import integrate_mission_into_target
from specify_cli.lanes.models import LanesManifest
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "099-target-newer-planning"
SPEC_REL = f"kitty-specs/{MISSION_SLUG}/spec.md"
WP_REL = f"kitty-specs/{MISSION_SLUG}/tasks/WP01.md"
MISSION_BRANCH = "kitty/mission-target-newer-planning-01ABCDEF-lane-a"
TARGET_BRANCH = "main"

# The target-newer content that MUST survive the squash merge.
SPEC_TARGET_NEWER = "# Spec\n\nTarget-newer requirement paragraph (refined on main).\n"
WP_TARGET_NEWER = "# WP01\n\nTarget-newer task detail (refined on main).\n"
# The older mission-branch content that -X theirs currently forces to win.
SPEC_OLDER_MISSION = "# Spec\n\nStale mission-branch requirement paragraph.\n"
WP_OLDER_MISSION = "# WP01\n\nStale mission-branch task detail.\n"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit_all_at(repo: Path, message: str, committed_at: str) -> None:
    """Commit staged fixture changes with a deterministic committer timestamp."""
    _run(["git", "add", "-A"], repo)
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = committed_at
    env["GIT_COMMITTER_DATE"] = committed_at
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _read_on_target(repo: Path, rel: str) -> str:
    return subprocess.run(
        ["git", "show", f"{TARGET_BRANCH}:{rel}"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id="01KQ47E81PWNXS80MHWTD903G1",
        mission_branch=MISSION_BRANCH,
        target_branch=TARGET_BRANCH,
        lanes=[],
        computed_at="2026-09-14T00:00:00+00:00",
        computed_from="deadbeef",
    )


def test_squash_merge_preserves_target_newer_planning_files(tmp_path: Path) -> None:
    """Squash-merging an older mission branch into a target-newer branch must not
    clobber driver-uncovered PRIMARY-partition planning files (#3942)."""
    # Document the exact protected class: both specimens are primary-artifact
    # kinds, and neither is covered by a custom merge driver.
    for rel in (SPEC_REL, WP_REL):
        kind = kind_for_mission_file(rel)
        assert kind is not None and is_primary_artifact_kind(kind), f"{rel} must be a primary-artifact-kind specimen"

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET_BRANCH], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    # Base commit shared by both branches.
    _write(repo, SPEC_REL, "# Spec\n\nOriginal shared paragraph.\n")
    _write(repo, WP_REL, "# WP01\n\nOriginal shared detail.\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base planning artifacts"], repo)

    # Mission branch: older conflicting edit (mid-flight, will be squashed in).
    _run(["git", "branch", MISSION_BRANCH], repo)
    _run(["git", "checkout", MISSION_BRANCH], repo)
    _write(repo, SPEC_REL, SPEC_OLDER_MISSION)
    _write(repo, WP_REL, WP_OLDER_MISSION)
    _run(["git", "commit", "-am", "mission work (older planning edit)"], repo)

    # Target branch (main): NEWER conflicting edit — target is strictly newer.
    _run(["git", "checkout", TARGET_BRANCH], repo)
    _write(repo, SPEC_REL, SPEC_TARGET_NEWER)
    _write(repo, WP_REL, WP_TARGET_NEWER)
    _run(["git", "commit", "-am", "refine planning on target (newer)"], repo)

    # Drive the real, supported squash-merge entry point (no mocks).
    result = integrate_mission_into_target(
        repo,
        MISSION_SLUG,
        _manifest(),
        strategy=MergeStrategy.SQUASH,
    )
    assert result.success, f"merge failed: {result.errors}"

    # Target-newer planning content must survive the squash merge.
    merged_spec = _read_on_target(repo, SPEC_REL)
    merged_wp = _read_on_target(repo, WP_REL)
    assert merged_spec == SPEC_TARGET_NEWER, "target-newer spec.md was clobbered by the older mission-branch copy via -X theirs (lanes/merge.py:635)"
    assert merged_wp == WP_TARGET_NEWER, "target-newer tasks/WP01.md was clobbered by the older mission-branch copy via -X theirs (lanes/merge.py:635)"


def test_squash_merge_preserves_source_newer_planning_policy(tmp_path: Path) -> None:
    """#4892 review: the historical recency policy also lets source-newer win."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET_BRANCH], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    _write(repo, SPEC_REL, "# Spec\n\nShared planning paragraph.\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base planning artifact"], repo)

    _run(["git", "branch", MISSION_BRANCH], repo)
    _write(repo, SPEC_REL, "# Spec\n\nOlder target refinement.\n")
    _commit_all_at(
        repo,
        "target planning refinement",
        "2026-09-22T10:00:00+00:00",
    )

    _run(["git", "checkout", MISSION_BRANCH], repo)
    _write(repo, SPEC_REL, "# Spec\n\nNewer mission refinement.\n")
    _commit_all_at(
        repo,
        "mission planning refinement",
        "2026-09-22T12:00:00+00:00",
    )
    _run(["git", "checkout", TARGET_BRANCH], repo)

    result = integrate_mission_into_target(
        repo,
        MISSION_SLUG,
        _manifest(),
        strategy=MergeStrategy.SQUASH,
    )

    assert result.success, f"merge failed: {result.errors}"
    assert _read_on_target(repo, SPEC_REL) == "# Spec\n\nNewer mission refinement.\n"


def test_squash_noop_when_planning_resolves_entirely_to_target(tmp_path: Path) -> None:
    """#4892 review: a planning conflict that resolves ENTIRELY to the target is a
    no-op — never a fabricated empty squash commit.

    When the only divergence is a planning artifact the target owns (target-newer),
    the reconciliation resolves it to the target's copy, leaving nothing net-staged
    against the target tree. Before the fix, ``--allow-empty`` forced an empty
    squash commit and bypassed the FR-037 no-op check; now the merge reports
    ``already_applied`` and the target ref does not advance.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET_BRANCH], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    # Base, then an OLDER mission edit and a NEWER target edit to the SAME
    # paragraph — so recency resolves the whole file to the target's copy.
    _write(repo, SPEC_REL, "# Spec\n\nOriginal shared paragraph.\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base planning artifact"], repo)

    _run(["git", "branch", MISSION_BRANCH], repo)
    _run(["git", "checkout", MISSION_BRANCH], repo)
    _write(repo, SPEC_REL, SPEC_OLDER_MISSION)
    _commit_all_at(repo, "mission older planning edit", "2026-09-22T10:00:00+00:00")

    _run(["git", "checkout", TARGET_BRANCH], repo)
    _write(repo, SPEC_REL, SPEC_TARGET_NEWER)
    _commit_all_at(repo, "target newer planning edit", "2026-09-22T12:00:00+00:00")
    target_before = subprocess.run(
        ["git", "rev-parse", TARGET_BRANCH],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    result = integrate_mission_into_target(
        repo,
        MISSION_SLUG,
        _manifest(),
        strategy=MergeStrategy.SQUASH,
    )

    assert result.success, f"merge failed: {result.errors}"
    assert result.already_applied is True, "a resolve-entirely-to-target squash must report a no-op"
    assert result.commit is None, "a no-op squash must not create a commit"
    target_after = subprocess.run(
        ["git", "rev-parse", TARGET_BRANCH],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert target_after == target_before, "target ref advanced on a no-op — an empty squash commit was fabricated"
    assert _read_on_target(repo, SPEC_REL) == SPEC_TARGET_NEWER


def test_squash_preserves_disjoint_lane_and_target_edits(tmp_path: Path) -> None:
    """Both-sides-advanced with DISJOINT edits: the fix must not lose the lane's edit.

    Regression guard for the whole-blob-overwrite data loss: base ``spec.md`` has
    two well-separated sections; the mission branch edits only section B while the
    target edits only section A. ``git merge --squash`` already unions the two
    disjoint hunks losslessly — the recency reconciliation must PRESERVE that union
    (3-way merge favouring target on overlap only), never overwrite the whole file
    with the target blob (which would silently drop the lane's section-B edit).
    """
    base = "# Spec\n\n## Section A\n\noriginal A\n\n## Section B\n\noriginal B\n"
    lane = "# Spec\n\n## Section A\n\noriginal A\n\n## Section B\n\nB EDITED BY LANE\n"
    target = "# Spec\n\n## Section A\n\nA EDITED ON MAIN\n\n## Section B\n\noriginal B\n"

    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", TARGET_BRANCH], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    _write(repo, SPEC_REL, base)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "base spec (sections A + B)"], repo)

    # Mission branch edits ONLY section B (first commit → older tiebreak side).
    _run(["git", "branch", MISSION_BRANCH], repo)
    _run(["git", "checkout", MISSION_BRANCH], repo)
    _write(repo, SPEC_REL, lane)
    _run(["git", "commit", "-am", "lane edits section B"], repo)

    # Target edits ONLY section A (later commit → wins the recency tiebreak).
    _run(["git", "checkout", TARGET_BRANCH], repo)
    _write(repo, SPEC_REL, target)
    _run(["git", "commit", "-am", "target edits section A"], repo)

    result = integrate_mission_into_target(repo, MISSION_SLUG, _manifest(), strategy=MergeStrategy.SQUASH)
    assert result.success, f"merge failed: {result.errors}"

    merged = _read_on_target(repo, SPEC_REL)
    assert "A EDITED ON MAIN" in merged, "target's disjoint section-A edit was lost"
    assert "B EDITED BY LANE" in merged, (
        "lane's disjoint section-B edit was clobbered by a wholesale target overwrite — the recency reconciliation must 3-way-merge, not overwrite the whole blob"
    )
