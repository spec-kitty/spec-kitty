"""Lane-hygiene guard content-diff vs planning-tip (WP06 / FR-007 / #2274).

The guard ``_list_wp_branch_mission_specs_changes`` must compare kitty-specs/
files by CONTENT against the planning-branch tip, not by commit-history
(merge-base) diff.

Background: after a planning-branch rebase the lane branch shares only an
ancient merge-base with the planning branch, so a merge-base diff surfaces any
kitty-specs/ file the lane branch touched — even when that file is
byte-identical to the planning tip.  This is a false positive that blocks
``move-task`` without ``--force`` and inflates ``force_count``.

Scenarios covered:

  T024 — RED (pre-fix): lane branch with a kitty-specs/ file byte-identical to
         the planning tip but with an ancient merge-base is FLAGGED (false
         positive).  The test asserts the desired behaviour (not flagged) and
         therefore FAILS on pre-fix code.
  T025 — content re-check against planning tip drops the byte-identical file
         after the WP06 fix.
  T026 — genuinely-divergent kitty-specs/ file IS still flagged after the fix;
         the guard's real signal is preserved.

All tests exercise ``_list_wp_branch_mission_specs_changes`` directly through
the real entry point (no monkeypatching of git).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks import _list_wp_branch_mission_specs_changes

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with standard test config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------


def _build_rebase_scenario(
    tmp_path: Path,
    *,
    lane_content: str = "spec content\n",
    planning_content: str | None = None,
) -> tuple[Path, str]:
    """Simulate a post-planning-branch-rebase setup.

    Layout::

        A (main / anchor) ──┬── planning: A → B  (adds kitty-specs/spec.md)
                            │
                            └── lane:     A → C  (adds kitty-specs/spec.md)

    ``planning`` and ``lane`` diverge from the same anchor ``A``, so
    ``merge-base(lane HEAD, planning)`` == ``A``.  When
    ``planning_content is None`` both branches use ``lane_content``, making the
    file byte-identical across the two branch tips — the false-positive scenario.

    Returns ``(repo_path, planning_branch_name)``.
    """
    if planning_content is None:
        planning_content = lane_content

    repo = _init_repo(tmp_path)

    # Anchor commit — no kitty-specs yet
    (repo / "README.md").write_text("anchor\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "anchor")

    anchor_sha = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Planning branch: add kitty-specs/spec.md with planning_content
    _git(repo, "checkout", "-q", "-b", "planning")
    ks_dir = repo / "kitty-specs" / "test-mission"
    ks_dir.mkdir(parents=True)
    (ks_dir / "spec.md").write_text(planning_content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning: add kitty-specs")

    # Lane branch: forked from the ANCHOR commit (simulates old fork point /
    # a planning-branch rebase that moved the base forward)
    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", "lane")
    lane_ks_dir = repo / "kitty-specs" / "test-mission"
    lane_ks_dir.mkdir(parents=True)
    (lane_ks_dir / "spec.md").write_text(lane_content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "lane: add kitty-specs")

    # Verify invariant: merge-base(lane HEAD, planning) == anchor, not planning tip
    mb = subprocess.run(
        ["git", "merge-base", "HEAD", "planning"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert mb == anchor_sha, (
        f"Scenario invariant violated: expected merge-base == anchor ({anchor_sha!r}), "
        f"got {mb!r}"
    )

    return repo, "planning"


# ---------------------------------------------------------------------------
# T024 / T025: byte-identical file after simulated rebase
# ---------------------------------------------------------------------------


class TestByteIdenticalNotFlagged:
    """T024 + T025: a kitty-specs/ file byte-identical to the planning tip must
    not be flagged, even when the merge-base is ancient.

    On pre-fix code (merge-base history diff only) this test FAILS (RED) because
    the guard surfaces the file.  After the WP06 content re-check it passes
    (GREEN).
    """

    def test_t024_byte_identical_file_is_not_flagged(self, tmp_path: Path) -> None:
        """T024 (RED pre-fix / GREEN post-fix): byte-identical kitty-specs/ not flagged.

        This is the primary red-first regression test for FR-007.  The lane
        branch has kitty-specs/test-mission/spec.md with the same content as
        the planning tip, but the merge-base is an ancient anchor commit.

        Pre-fix behaviour: the guard uses ``git diff merge-base..HEAD`` and flags
        the file (false positive) → assertion fails (RED).

        Post-fix behaviour: the content re-check detects an empty diff vs the
        planning tip and drops the file → assertion passes (GREEN).
        """
        repo, planning = _build_rebase_scenario(tmp_path, lane_content="spec content\n")

        flagged = _list_wp_branch_mission_specs_changes(repo, planning)

        assert flagged == [], (
            f"False positive: byte-identical kitty-specs/ file was flagged after rebase. "
            f"Flagged paths: {flagged!r}"
        )

    def test_t025_no_force_count_inflation_for_identical_file(self, tmp_path: Path) -> None:
        """T025: byte-identical file returns empty list (no force_count pressure).

        Confirms the content re-check produces an empty result, meaning no
        ``--force`` requirement is triggered for the false-positive case.
        """
        repo, planning = _build_rebase_scenario(
            tmp_path, lane_content="# Mission spec\n\nContent here.\n"
        )

        flagged = _list_wp_branch_mission_specs_changes(repo, planning)

        assert len(flagged) == 0, (
            f"Expected empty list (no force_count inflation), got {flagged!r}"
        )


# ---------------------------------------------------------------------------
# T026: genuinely-divergent file is still flagged
# ---------------------------------------------------------------------------


class TestGenuinelyDivergentStillFlagged:
    """T026: a kitty-specs/ file that genuinely diverges from the planning tip
    must still be flagged regardless of the content re-check.

    This asserts the guard's real signal is preserved after the WP06 fix.
    """

    def test_t026_divergent_content_is_flagged(self, tmp_path: Path) -> None:
        """T026: genuinely-divergent kitty-specs/ file is flagged after fix.

        The lane branch has different content from the planning tip.  The
        content re-check finds a non-empty diff and keeps the file in the
        flagged list.  This must hold both pre-fix and post-fix.
        """
        repo, planning = _build_rebase_scenario(
            tmp_path,
            lane_content="# Lane diverged\n\nThis content differs.\n",
            planning_content="# Planning tip\n\nOriginal content.\n",
        )

        flagged = _list_wp_branch_mission_specs_changes(repo, planning)

        assert len(flagged) > 0, (
            "Guard neutered: genuinely-divergent kitty-specs/ file was NOT flagged. "
            "The guard must retain its signal for real divergence."
        )
        assert any("spec.md" in p for p in flagged), (
            f"Expected 'spec.md' among flagged paths, got {flagged!r}"
        )

    def test_t026_mixed_files_only_divergent_flagged(self, tmp_path: Path) -> None:
        """T026 (extended): when one file is identical and one diverges, only the
        divergent file appears in the result.
        """
        repo = _init_repo(tmp_path)

        # Anchor commit
        (repo / "README.md").write_text("anchor\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "anchor")

        anchor_sha = subprocess.run(
            ["git", "rev-parse", "main"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()

        # Planning branch: add two kitty-specs files
        _git(repo, "checkout", "-q", "-b", "planning")
        ks_dir = repo / "kitty-specs" / "mission-x"
        ks_dir.mkdir(parents=True)
        (ks_dir / "spec.md").write_text("shared content\n", encoding="utf-8")
        (ks_dir / "plan.md").write_text("planning plan\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "planning: add two files")

        # Lane branch: identical spec.md, diverged plan.md
        _git(repo, "checkout", "-q", "main")
        _git(repo, "checkout", "-q", "-b", "lane")
        lane_ks_dir = repo / "kitty-specs" / "mission-x"
        lane_ks_dir.mkdir(parents=True)
        (lane_ks_dir / "spec.md").write_text("shared content\n", encoding="utf-8")  # identical
        (lane_ks_dir / "plan.md").write_text("lane-modified plan\n", encoding="utf-8")  # diverged
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "lane: add files (spec identical, plan diverged)")

        # Verify merge-base is the anchor
        mb = subprocess.run(
            ["git", "merge-base", "HEAD", "planning"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert mb == anchor_sha

        flagged = _list_wp_branch_mission_specs_changes(repo, "planning")

        flagged_names = [Path(p).name for p in flagged]
        assert "plan.md" in flagged_names, (
            f"Diverged file 'plan.md' should be flagged, got {flagged!r}"
        )
        assert "spec.md" not in flagged_names, (
            f"Identical file 'spec.md' should NOT be flagged, got {flagged!r}"
        )


# ---------------------------------------------------------------------------
# T027 / T028: coord-topology inheritance (#3271)
# ---------------------------------------------------------------------------


def _build_coord_inheritance_scenario(tmp_path: Path) -> tuple[Path, str, str]:
    """Simulate the #3271 coord-topology inheritance layout.

    Layout::

        A (main) ── README
          └── coord:  A → C   (adds kitty-specs/prior-mission/spec.md)
                └── target: C → T   (adds kitty-specs/this-mission/spec.md)
        lane: forked from coord (C), then MERGES the recorded planning commit T
              (ADR 2026-07-29-1 / #2993) → lane kitty-specs is byte-identical to
              target, with zero lane-authored delta.

    The coordination branch is minted at mission-create *before* the planning
    commit exists, so ``merge-base(lane, coord)`` predates ``this-mission``'s
    planning artifacts even though the lane holds them byte-identically to the
    planning tip. Diffing against ``coord`` therefore false-positives; diffing
    against ``target`` (the planning branch) is clean.

    Returns ``(repo, coord_branch, target_branch)``.
    """
    repo = _init_repo(tmp_path)

    (repo / "README.md").write_text("anchor\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "anchor")

    # Coordination branch: prior mission's committed kitty-specs, no planning yet.
    _git(repo, "checkout", "-q", "-b", "coord")
    prior = repo / "kitty-specs" / "prior-mission"
    prior.mkdir(parents=True)
    (prior / "spec.md").write_text("prior mission spec\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "coord: inherit prior-mission kitty-specs")

    # Target/planning branch: adds THIS mission's planning artifacts on top.
    _git(repo, "checkout", "-q", "-b", "target")
    this_mission = repo / "kitty-specs" / "this-mission"
    this_mission.mkdir(parents=True)
    (this_mission / "spec.md").write_text("this mission spec\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "target: record this-mission planning commit")
    planning_sha = subprocess.run(
        ["git", "rev-parse", "target"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Lane: forked from coord, then merges the recorded planning commit (#2993).
    _git(repo, "checkout", "-q", "coord")
    _git(repo, "checkout", "-q", "-b", "lane")
    _git(repo, "merge", "-q", "--no-edit", planning_sha)

    return repo, "coord", "target"


class TestCoordInheritanceNotFlagged:
    """#3271: a lane whose kitty-specs are byte-identical to the planning branch
    must not be flagged, even when the coordination base ref predates them."""

    def test_t027_coord_base_reproduces_the_false_positive(self, tmp_path: Path) -> None:
        """Characterisation: basing the delta on the coordination branch flags
        inherited/merged content — the pre-fix behaviour #3271 reports."""
        repo, coord, _target = _build_coord_inheritance_scenario(tmp_path)

        flagged = _list_wp_branch_mission_specs_changes(repo, coord)

        assert flagged, (
            "Scenario invariant: diffing against the coordination base ref must "
            "surface the inherited/merged kitty-specs (the #3271 false positive)."
        )

    def test_t028_planning_base_is_clean(self, tmp_path: Path) -> None:
        """The fix: basing the delta on the planning/target branch yields an empty
        result — inherited and #2993-merged artifacts are ancestors of it."""
        repo, _coord, target = _build_coord_inheritance_scenario(tmp_path)

        flagged = _list_wp_branch_mission_specs_changes(repo, target)

        assert flagged == [], (
            f"False positive: lane kitty-specs byte-identical to the planning "
            f"branch were flagged. Flagged paths: {flagged!r}"
        )


# ---------------------------------------------------------------------------
# Occurrence-map exception (#2980): a bulk-edit mission's own occurrence map is
# a permitted lane write and must not be flagged by the lane-hygiene guard.
# ---------------------------------------------------------------------------


class TestOccurrenceMapException:
    """#2980: the move-task lane-hygiene guard honours the same occurrence-map
    exception the pre-commit guard does — the lane may carry its own mission's
    ``kitty-specs/<mission>/occurrence_map.yaml`` without being flagged, while a
    sibling planning artifact on the lane is still flagged."""

    def test_own_occurrence_map_is_not_flagged(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)

        (repo / "README.md").write_text("anchor\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "anchor")

        # Planning branch has no occurrence map yet.
        _git(repo, "checkout", "-q", "-b", "planning")
        (repo / "kitty-specs" / "mission-x").mkdir(parents=True)
        (repo / "kitty-specs" / "mission-x" / "spec.md").write_text("spec\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "planning: spec")

        # Lane writes ONLY its own occurrence map (DIRECTIVE_035 sweep upkeep).
        _git(repo, "checkout", "-q", "-b", "lane")
        (repo / "kitty-specs" / "mission-x" / "occurrence_map.yaml").write_text(
            "target: {}\n", encoding="utf-8"
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "lane: keep occurrence map current")

        flagged = _list_wp_branch_mission_specs_changes(repo, "planning")

        assert flagged == [], (
            f"Occurrence map wrongly flagged as lane contamination: {flagged!r}"
        )

    def test_sibling_planning_artifact_still_flagged(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)

        (repo / "README.md").write_text("anchor\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "anchor")

        _git(repo, "checkout", "-q", "-b", "planning")
        (repo / "kitty-specs" / "mission-x").mkdir(parents=True)
        (repo / "kitty-specs" / "mission-x" / "spec.md").write_text("spec\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "planning: spec")

        # Lane writes its occurrence map AND edits spec.md (a real violation).
        _git(repo, "checkout", "-q", "-b", "lane")
        (repo / "kitty-specs" / "mission-x" / "occurrence_map.yaml").write_text(
            "target: {}\n", encoding="utf-8"
        )
        (repo / "kitty-specs" / "mission-x" / "spec.md").write_text(
            "spec EDITED on lane\n", encoding="utf-8"
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "lane: map + spec edit")

        flagged = _list_wp_branch_mission_specs_changes(repo, "planning")

        assert any("spec.md" in p for p in flagged), (
            f"Genuine spec.md edit on the lane must still be flagged, got {flagged!r}"
        )
        assert not any("occurrence_map.yaml" in p for p in flagged), (
            f"Occurrence map must be excepted even alongside a real violation, got {flagged!r}"
        )


# ---------------------------------------------------------------------------
# FIX-M2-04: COORD-partition inheritance from the coordination-branch lane
# parentage (#1348 WP04 / FR-009 / #2993) is never byte-identical to the
# planning branch and must not be flagged.
# ---------------------------------------------------------------------------


def _build_coord_status_state_scenario(tmp_path: Path) -> tuple[Path, str, str]:
    """Reproduce the real ``spec-kitty implement`` coord-topology lane DAG.

    Layout (matches the golden-path repro exactly — ``git log --graph`` on a
    real ``.worktrees/*-lane-*`` branch after ``spec-kitty implement WP01``)::

        A (main) ── README
          ├── coord:  A → S   (adds kitty-specs/test-mission/status.events.jsonl
          │                    + acceptance-matrix.json — the coordination
          │                    branch's OWN COORD-partition writes: the
          │                    finalize-tasks bootstrap event + implement's
          │                    claim transition + acceptance-matrix scaffold,
          │                    collapsed into one commit for test brevity)
          │
          └── planning: A → P (adds kitty-specs/test-mission/spec.md +
                                tasks.md — the PRIMARY-partition planning
                                artifacts; status.events.jsonl is NEVER
                                written here — it is coord-owned and lives
                                exclusively on the coordination branch, by
                                design (module docstring,
                                ``worktree_allocator.py``))
        lane: forked from coord (S), then FR-009-MERGES the recorded
              planning commit P (``PlanningCommitMergeConflictError``'s
              docstring, #2993) — exactly what
              ``allocate_lane_worktree``/``_merge_recorded_planning_commit``
              does for every coord-topology lane worktree.

    Because ``status.events.jsonl`` / ``acceptance-matrix.json`` are written
    ONLY on the coordination branch (never on planning), they can NEVER be
    byte-identical to the planning tip — ``_filter_by_planning_tip_content``'s
    exact-match rescue can never save them, which is exactly why every
    coord-topology mission tripped the "kitty-specs/ changes are not allowed
    on lane branches" guard structurally, independent of anything an
    implementer committed.

    Returns ``(repo, coord_branch, planning_branch)``.
    """
    repo = _init_repo(tmp_path)

    (repo / "README.md").write_text("anchor\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "anchor")

    # Coordination branch: COORD-partition bookkeeping only, no planning docs.
    _git(repo, "checkout", "-q", "-b", "coord")
    coord_ks = repo / "kitty-specs" / "test-mission"
    coord_ks.mkdir(parents=True)
    (coord_ks / "status.events.jsonl").write_text(
        '{"wp_id": "WP01", "to_lane": "planned"}\n'
        '{"wp_id": "WP01", "to_lane": "claimed"}\n'
        '{"wp_id": "WP01", "to_lane": "in_progress"}\n',
        encoding="utf-8",
    )
    (coord_ks / "acceptance-matrix.json").write_text('{"WP01": []}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "coord: bootstrap status + acceptance-matrix")

    # Planning branch: PRIMARY-partition artifacts only — forked from the SAME
    # anchor as coord, never touches status.events.jsonl / acceptance-matrix.json.
    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", "planning")
    planning_ks = repo / "kitty-specs" / "test-mission"
    planning_ks.mkdir(parents=True)
    (planning_ks / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (planning_ks / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning: record this-mission spec + tasks")
    planning_sha = subprocess.run(
        ["git", "rev-parse", "planning"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Lane: parented on coord (#1348 WP04), then FR-009-merges the recorded
    # planning commit on top (#2993) — the real allocate_lane_worktree shape.
    _git(repo, "checkout", "-q", "coord")
    _git(repo, "checkout", "-q", "-b", "lane")
    _git(repo, "merge", "-q", "--no-edit", planning_sha)

    return repo, "coord", "planning"


class TestCoordPartitionInheritanceNotFlagged:
    """Coord-inherited files are clean by fork provenance, not basename."""

    def test_status_events_and_acceptance_matrix_are_not_flagged(
        self, tmp_path: Path
    ) -> None:
        """Coord-only paths before the lane fork are outside the candidate set."""
        repo, coord, planning = _build_coord_status_state_scenario(tmp_path)

        flagged = _list_wp_branch_mission_specs_changes(
            repo, coord, planning_base_branch=planning
        )

        assert not any("status.events.jsonl" in p for p in flagged), (
            f"Coord-owned status.events.jsonl wrongly flagged as lane "
            f"contamination: {flagged!r}"
        )
        assert not any("acceptance-matrix.json" in p for p in flagged), (
            f"Coord-owned acceptance-matrix.json wrongly flagged as lane "
            f"contamination: {flagged!r}"
        )
        assert flagged == [], f"Expected no lane contamination, got {flagged!r}"

    def test_genuine_primary_artifact_edit_still_flagged(self, tmp_path: Path) -> None:
        """The coord-residue exemption must not swallow a REAL violation: an
        implementer editing spec.md directly on the lane (a PRIMARY-partition
        planning artifact) is still flagged, alongside the harmless coord
        inheritance from the same topology."""
        repo, coord, planning = _build_coord_status_state_scenario(tmp_path)

        # A genuine lane-authored edit to a PRIMARY artifact, on top of the
        # same coord-parented + FR-009-merged topology.
        (repo / "kitty-specs" / "test-mission" / "spec.md").write_text(
            "# Spec EDITED on lane\n", encoding="utf-8"
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "lane: edit spec.md (real violation)")

        flagged = _list_wp_branch_mission_specs_changes(
            repo, coord, planning_base_branch=planning
        )

        assert any("spec.md" in p for p in flagged), (
            f"Genuine spec.md edit on the lane must still be flagged, got {flagged!r}"
        )
        assert not any("status.events.jsonl" in p for p in flagged), (
            f"Inherited status.events.jsonl must stay outside candidates even "
            f"alongside a real violation, got {flagged!r}"
        )
        assert not any("acceptance-matrix.json" in p for p in flagged), (
            f"Inherited acceptance-matrix.json must stay outside candidates even "
            f"alongside a real violation, got {flagged!r}"
        )

    def test_unresolvable_coordination_base_is_not_treated_as_clean(
        self, tmp_path: Path
    ) -> None:
        repo, _coord, planning = _build_coord_status_state_scenario(tmp_path)

        flagged = _list_wp_branch_mission_specs_changes(
            repo,
            "deleted-coordination-ref",
            planning_base_branch=planning,
        )

        assert flagged is None, "Unknown fork base must be reported as unverifiable"
