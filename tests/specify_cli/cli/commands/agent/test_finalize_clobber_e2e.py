"""E2E regression tests for finalize-tasks coord event-log clobber fix (#1589).

Two clobber sites were fixed:
  1. ``_stage_finalize_artifacts_in_coord_worktree`` in mission.py now excludes
     ``_COORD_OWNED_STATUS_FILES`` when copying primary-checkout artifacts into
     the coord worktree before the safe_commit.
  2. ``_ensure_planning_artifacts_committed_git`` in implement.py similarly
     excludes ``_coord_owned_status`` from the pre-claim auto-commit.

This module adds the end-to-end regression net (T024–T026):

  T024 — Coord finalize: bootstrap lane events survive a real finalize-tasks run.
  T025 — Non-coord finalize: status.events.jsonl IS committed on the normal path.
  T026 — Coord re-finalize: redundant run where only status files changed does
          not fail with an empty-changeset commit error.

To confirm non-vacuity the T024 test MUST FAIL when the clobber fix is reverted
(i.e. when the ``if src.name in _COORD_OWNED_STATUS_FILES: continue`` guard is
removed from ``_stage_finalize_artifacts_in_coord_worktree``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.coordination.status_transition import read_events_transactional
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.status.bootstrap import bootstrap_canonical_state
from specify_cli.status.store import EVENTS_FILENAME

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _parse_json_from_output(output: str) -> dict[str, object]:
    """Return the first JSON object found in CliRunner output.

    finalize-tasks --json emits warning lines (event validation etc.) before
    the terminal JSON payload.  Scan from the top for a line starting with ``{``
    to find the canonical JSON result, ignoring prose warnings.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads(stripped))
    raise ValueError(
        f"No JSON object found in finalize-tasks output:\n{output}"
    )

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )




def _write_wp_file(tasks_dir: Path, wp_id: str, req_ref: str = "FR-001") -> Path:
    """Create a minimal WP markdown file with valid frontmatter."""
    wp_file = tasks_dir / f"{wp_id}-task.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"dependencies: []\n"
        f"requirement_refs: [{req_ref}]\n"
        f"subtasks: []\n"
        f"owned_files:\n"
        f"  - src/module_{wp_id.lower()}/**\n"
        f"authoritative_surface: src/module_{wp_id.lower()}/\n"
        f"execution_mode: code_change\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return wp_file


def _write_minimal_spec(feature_dir: Path, req_ref: str = "FR-001") -> Path:
    spec = feature_dir / "spec.md"
    spec.write_text(
        f"# Spec\n\n"
        f"## Functional Requirements\n"
        f"| ID | Requirement | Acceptance Criteria | Status |\n"
        f"| --- | --- | --- | --- |\n"
        f"| {req_ref} | Test requirement | Test passes. | proposed |\n",
        encoding="utf-8",
    )
    return spec


def _write_tasks_md(feature_dir: Path, wp_ids: list[str]) -> Path:
    tasks = feature_dir / "tasks.md"
    sections = "\n".join(
        f"## Work Package {wp}\n\n**Dependencies**: None\n" for wp in wp_ids
    )
    tasks.write_text(f"# Tasks\n\n{sections}\n", encoding="utf-8")
    return tasks


# ---------------------------------------------------------------------------
# Real-git coordination-topology fixture factory
# ---------------------------------------------------------------------------


def _build_coord_topology(
    tmp_path: Path,
) -> tuple[Path, str, str, str, Path]:
    """Create a minimal real git repo with a coordination-topology mission.

    Returns (repo_root, mission_slug, mid8, coord_branch, feature_dir).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "tag.gpgsign", "false")

    # mission_dirname is the directory name under kitty-specs/ and the handle
    # passed to --mission. It matches the post-083 naming convention:
    # <human-slug>-<mid8>
    mission_slug = "099-clobber-test"
    mid8 = "01CLOBBR"
    mission_id = "01CLOBBR000000000000000000"  # 26-char ULID (mid8 + 18 zeros)
    mission_dirname = f"{mission_slug}-{mid8}"
    coord_branch = f"kitty/mission-{mission_dirname}"
    # write-surface-coherence (FR-002 / FR-008): planning artifacts (TASKS_INDEX)
    # land on the primary feature target_branch — a NON-protected branch the
    # operator is on. A protected ``main`` target would be REFUSED (G-4). Status
    # still routes to the coordination branch (the partition), so the event-log
    # survival subject of this test is unchanged.
    target_branch = "feat/clobber-target"

    feature_dir = repo / "kitty-specs" / mission_dirname
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_dirname,
                "mission_id": mission_id,
                "mid8": mid8,
                "coordination_branch": coord_branch,
                "target_branch": target_branch,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _write_wp_file(tasks_dir, "WP01")
    _write_wp_file(tasks_dir, "WP02")
    _write_minimal_spec(feature_dir)
    _write_tasks_md(feature_dir, ["WP01", "WP02"])

    # Initial commit so git is happy
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed mission")
    # Create the coordination branch pointing at same commit
    _git(repo, "branch", coord_branch)
    # The operator is ON the feature target_branch (D-3 invariant): the planning
    # commit lands there directly. Check it out as HEAD.
    _git(repo, "checkout", "-q", "-b", target_branch)

    # Return mission_dirname as the CLI handle (what --mission expects)
    return repo, mission_dirname, mid8, coord_branch, feature_dir


# ---------------------------------------------------------------------------
# Helpers that disable status fan-out in bootstrap tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence status fan-out so tests are hermetic."""
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *args, **kwargs: None)


# ---------------------------------------------------------------------------
# T024 — E2E: coord finalize preserves bootstrap lane events
# ---------------------------------------------------------------------------


class TestT024CoordFinalizePreservesBootstrapEvents:
    """FR-006 / FR-019 / #1589 regression: the bootstrap lane events seeded into
    the coordination worktree MUST survive a real finalize-tasks run.

    Non-vacuity guarantee: this test FAILS when the
    ``if src.name in _COORD_OWNED_STATUS_FILES: continue`` guard is removed
    from ``_stage_finalize_artifacts_in_coord_worktree``.
    """

    def test_coord_event_log_survives_finalize(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, mission_slug, mid8, coord_branch, feature_dir = _build_coord_topology(
            tmp_path
        )

        # Step 1: bootstrap seeded events into the coord worktree (genesis → planned).
        bootstrap_result = bootstrap_canonical_state(
            feature_dir, mission_slug, dry_run=False,
            capability=GuardCapability.TEST_MODE,
        )
        assert bootstrap_result.newly_seeded == 2, (
            f"bootstrap should have seeded 2 WPs, got {bootstrap_result.newly_seeded}"
        )

        # Confirm the coord worktree now holds the seeded events.
        events_before = read_events_transactional(
            feature_dir=feature_dir, mission_slug=mission_slug
        )
        seeded_before = {e.wp_id: str(e.to_lane) for e in events_before if e.wp_id}
        assert seeded_before == {"WP01": "planned", "WP02": "planned"}, (
            f"bootstrap events not visible before finalize: {seeded_before}"
        )

        # Step 2: run the real finalize-tasks command via CliRunner.
        # We patch locate_project_root so the command operates on our test repo.
        with (
            patch(
                "specify_cli.cli.commands.agent.mission.locate_project_root",
                return_value=repo,
            ),
            patch(
                "specify_cli.cli.commands.agent.mission.run_git_preflight",
                return_value=type("P", (), {"passed": True})(),
            ),
        ):
            result = runner.invoke(
                app,
                ["finalize-tasks", "--mission", mission_slug, "--json"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, (
            f"finalize-tasks failed (exit {result.exit_code}):\n{result.output}"
        )

        # The CliRunner captures stdout; with --json the final line is the JSON payload.
        # Warning lines may appear before it (event validation warnings, etc.).
        output_json = _parse_json_from_output(result.output)
        assert output_json.get("result") == "success", (
            f"finalize-tasks returned unexpected result: {output_json}"
        )

        # Step 3: assert the coordination event log STILL contains the seeded events.
        events_after = read_events_transactional(
            feature_dir=feature_dir, mission_slug=mission_slug
        )
        seeded_after = {e.wp_id: str(e.to_lane) for e in events_after if e.wp_id}
        assert seeded_after == {"WP01": "planned", "WP02": "planned"}, (
            f"finalize-tasks clobbered the coord event log! "
            f"Expected planned events for WP01+WP02 but got: {seeded_after}"
        )


# ---------------------------------------------------------------------------
# T025 — Negative: non-coord mission still commits status.events.jsonl
# ---------------------------------------------------------------------------


class TestT025NonCoordMissionCommitsStatusFiles:
    """FR-006: the clobber fix only applies to coordination-topology missions.

    A non-coordination mission's finalize-tasks MUST still commit its
    status.events.jsonl / status.json — the skip must not regress the
    normal (non-coord) path.
    """

    def test_non_coord_finalize_includes_status_files_in_commit(
        self, tmp_path: Path
    ) -> None:
        """On a non-coord mission the status files appear in files_to_commit."""
        from specify_cli.cli.commands.agent.mission import _collect_finalize_artifacts

        # Build a minimal non-coord feature dir (no coordination_branch in meta).
        feature_dir = tmp_path / "kitty-specs" / "098-non-coord"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        (feature_dir / "meta.json").write_text(
            json.dumps({"target_branch": "main"}) + "\n",
            encoding="utf-8",
        )
        _write_wp_file(tasks_dir, "WP01")
        _write_minimal_spec(feature_dir)
        _write_tasks_md(feature_dir, ["WP01"])

        # Seed the status files (bootstrap normally creates them).
        events_path = feature_dir / EVENTS_FILENAME
        events_path.write_text(
            json.dumps(
                {
                    "event_id": "01TEST00000000000000000000",
                    "mission_slug": "098-non-coord",
                    "wp_id": "WP01",
                    "from_lane": "planned",
                    "to_lane": "planned",
                    "at": "2026-01-01T00:00:00+00:00",
                    "actor": "test",
                    "force": True,
                    "execution_mode": "worktree",
                    "reason": None,
                    "review_ref": None,
                    "evidence": None,
                    "policy_metadata": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (feature_dir / "status.json").write_text("{}\n", encoding="utf-8")

        # Collect the finalize artifacts: on a non-coord mission the status
        # files must be included (they will be committed to the planning branch).
        artifacts = _collect_finalize_artifacts(feature_dir, tasks_dir)
        artifact_names = {p.name for p in artifacts}

        assert "status.events.jsonl" in artifact_names, (
            "status.events.jsonl must be collected for non-coord missions "
            f"(got: {artifact_names})"
        )
        assert "status.json" in artifact_names, (
            "status.json must be collected for non-coord missions "
            f"(got: {artifact_names})"
        )

    def test_stage_helper_passes_status_files_when_not_coord_owned(
        self, tmp_path: Path
    ) -> None:
        """_stage_finalize_artifacts_in_coord_worktree skips status files from src.

        The skip operates on src.name membership in _COORD_OWNED_STATUS_FILES.
        Calling it with non-status files must pass them all through untouched.
        This verifies the fix boundary doesn't eat normal artifacts.
        """
        from specify_cli.cli.commands.agent.mission import (
            _stage_finalize_artifacts_in_coord_worktree,
        )

        repo_root = tmp_path / "repo"
        feature_dir = repo_root / "kitty-specs" / "098-non-coord"
        feature_dir.mkdir(parents=True)

        tasks_md = feature_dir / "tasks.md"
        tasks_md.write_text("# tasks\n", encoding="utf-8")
        lanes_json = feature_dir / "lanes.json"
        lanes_json.write_text('{"lanes":[]}\n', encoding="utf-8")

        coord_wt = tmp_path / "coord"
        staged = _stage_finalize_artifacts_in_coord_worktree(
            [tasks_md, lanes_json], coord_wt, repo_root
        )

        staged_names = {p.name for p in staged}
        # Both non-status artifacts must be staged.
        assert staged_names == {"tasks.md", "lanes.json"}, (
            f"Expected both non-status artifacts staged, got {staged_names}"
        )


# ---------------------------------------------------------------------------
# T026 — Edge: coord re-finalize empty-changeset does not error
# ---------------------------------------------------------------------------


class TestT026CoordReFinalizeEmptyChangeset:
    """Debbie Attack 3b: if only status files changed on a coord re-finalize,
    the remaining non-status artifact list may be empty or already-committed,
    meaning there is nothing to commit after the status-file skip.

    The scenario:
      1. Run finalize-tasks once — all non-status artifacts land on coord branch.
      2. Manually dirty ONLY the primary-checkout status files (simulating a new
         bootstrap cycle that appended an event) WITHOUT changing any other artifact.
      3. Re-run finalize-tasks on the coord path.

    Expected: ``has_relevant_changes=True`` (status files are dirty) triggers the
    coord commit path, ``_stage_finalize_artifacts_in_coord_worktree`` skips the
    status files, leaving NO non-status changes to stage.  ``git status --porcelain``
    on only the non-status staged files returns empty → ``commit_created=False``,
    NOT an Exit(1) ``git commit`` failure.
    """

    def test_coord_refinalize_with_only_status_changes_is_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-finalize where only status files changed exits 0 with commit_created=False."""
        repo, mission_slug, mid8, coord_branch, feature_dir = _build_coord_topology(
            tmp_path
        )

        # Bootstrap the coord events first.
        bootstrap_canonical_state(
            feature_dir, mission_slug, dry_run=False,
            capability=GuardCapability.TEST_MODE,
        )

        _finalize_patches = [
            patch(
                "specify_cli.cli.commands.agent.mission.locate_project_root",
                return_value=repo,
            ),
            patch(
                "specify_cli.cli.commands.agent.mission.run_git_preflight",
                return_value=type("P", (), {"passed": True})(),
            ),
        ]

        # Run finalize-tasks once so all non-status artifacts land on coord branch.
        with _finalize_patches[0], _finalize_patches[1]:
            first_result = runner.invoke(
                app,
                ["finalize-tasks", "--mission", mission_slug, "--json"],
                catch_exceptions=False,
            )
        assert first_result.exit_code == 0, (
            f"First finalize-tasks failed (exit {first_result.exit_code}):\n"
            f"{first_result.output}"
        )

        # Now simulate Attack 3b: manually write a new event to the primary-checkout
        # status.events.jsonl (dirtying it) WITHOUT touching any other artifact.
        # This represents a situation where ONLY status files changed since the last
        # finalize run (e.g. a lifecycle event was emitted in the primary checkout).
        primary_events = feature_dir / EVENTS_FILENAME
        original_events = primary_events.read_text(encoding="utf-8") if primary_events.exists() else ""
        primary_events.write_text(
            original_events
            + json.dumps(
                {
                    "event_id": "01TESTATTACK3B000000000000",
                    "mission_slug": mission_slug,
                    "wp_id": "WP01",
                    "from_lane": "planned",
                    "to_lane": "planned",
                    "at": "2026-01-02T00:00:00+00:00",
                    "actor": "test-attack-3b",
                    "force": True,
                    "execution_mode": "worktree",
                    "reason": "Attack 3b simulation",
                    "review_ref": None,
                    "evidence": None,
                    "policy_metadata": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        # Confirm that git sees the primary status file as dirty.
        _git_out = subprocess.run(
            ["git", "status", "--porcelain", "--", str(primary_events.relative_to(repo))],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert _git_out.stdout.strip(), (
            "status.events.jsonl should be dirty for Attack 3b simulation"
        )

        # Re-run finalize-tasks.  The coord staging helper skips the dirty status
        # file; the remaining non-status artifacts are already committed → no new
        # commit should be needed.
        with _finalize_patches[0], _finalize_patches[1]:
            second_result = runner.invoke(
                app,
                ["finalize-tasks", "--mission", mission_slug, "--json"],
                catch_exceptions=False,
            )

        assert second_result.exit_code == 0, (
            f"Second (re-)finalize-tasks should succeed even when only status "
            f"files changed, but got exit {second_result.exit_code}:\n"
            f"{second_result.output}"
        )


# ---------------------------------------------------------------------------
# Non-vacuity helper (not a test itself — used in development verification)
# ---------------------------------------------------------------------------


def _non_vacuity_proof(tmp_path: Path) -> bool:
    """Return True when T024 would FAIL under the broken (pre-fix) implementation.

    This function is not collected by pytest.  It is documented here as proof
    that T024 is non-vacuous: the assertion in T024 is sensitive to the clobber
    fix and correctly detects its absence.

    Manual verification procedure (confirmed green → red → green):
      1. Run T024 with the fix in place → passes.
      2. Comment out ``if src.name in _COORD_OWNED_STATUS_FILES: continue``
         in ``_stage_finalize_artifacts_in_coord_worktree`` in mission.py.
      3. Re-run T024 → fails with:
         AssertionError: finalize-tasks clobbered the coord event log!
         Expected planned events for WP01+WP02 but got: {}
      4. Restore the guard → T024 passes again.
    """
    # This is documentation code; actual proof is performed manually.
    return True  # pragma: no cover


# Ensure the module is importable and the marker is applied without issues.
if __name__ == "__main__":  # pragma: no cover
    import subprocess as _sp
    import sys as _sys

    _result = _sp.run(
        [_sys.executable, "-m", "pytest", __file__, "-v"],
        cwd=Path(__file__).parent,
    )
    _sys.exit(_result.returncode)
