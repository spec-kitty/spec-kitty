"""Regression tests for idempotent mission-number assignment (WP04 / FR-010, FR-011, FR-012).

Covers the three scenarios from T027:

1. partial-merge resume — meta.json already has mission_number=N; the
   assignment step must detect this (idempotency check, T025) and NOT produce
   an additional commit. Per #4900, this seam never marks
   mission_number_baked itself -- only the executor does, after verifying
   the number on the target.

2. fresh-merge happy path — meta.json has mission_number=null; the step
   writes and commits, again without marking mission_number_baked itself
   (#4900).

3. resume short-circuit — merge_state.mission_number_baked=True; the
   assignment step returns immediately without reading meta.json (T026).

The fourth implicit test (negative path / #983 reproduction) is embedded in
test 1 as an assertion that git_log_count did NOT increase.

These tests exercise the logic directly via
``_bake_mission_number_into_mission_branch`` and the ConsolidationState helpers.
They do NOT spin up a full merge flow — that surface is covered by the
rest of tests/merge/.  The git operations inside
``_bake_mission_number_into_mission_branch`` are unavoidable (it calls into
``git worktree add``), so we use a real minimal git repo fixture.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.state import ConsolidationState, load_state, save_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*, raising on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def _init_repo(repo: Path) -> None:
    """Initialise a throwaway git repo with a single initial commit."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # Silence GPG signing so the test repo can commit without a key.
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")


def _write_meta(feature_dir: Path, *, mission_slug: str, mission_number: int | None) -> None:
    """Write a minimal meta.json into *feature_dir*."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": "01ABCDEFGHIJKLMNOPQRSTUVWX",
        "mission_number": mission_number,
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-05-12T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _commit_count(repo: Path, ref: str = "HEAD") -> int:
    """Return the number of commits reachable from *ref*."""
    result = subprocess.run(
        ["git", "rev-list", "--count", ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.strip())


def _make_mission_branch(repo: Path, mission_slug: str) -> str:
    """Create a mission branch containing a meta.json and return its name."""
    branch_name = f"kitty/mission-{mission_slug}"
    # Start from main and create the branch.
    _git(repo, "checkout", "-b", branch_name)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug=mission_slug, mission_number=None)
    _git(repo, "add", str(feature_dir / "meta.json"))
    _git(repo, "commit", "-m", f"add {mission_slug} meta.json (mission_number=null)")
    # Return to main.
    _git(repo, "checkout", "main")
    return branch_name


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Return a minimal git repo rooted at tmp_path / 'repo'."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    return repo


# ---------------------------------------------------------------------------
# Helpers that call the function under test
# ---------------------------------------------------------------------------


def _run_bake(
    repo: Path,
    mission_slug: str,
    mission_branch: str,
    target_branch: str = "main",
    *,
    merge_state: ConsolidationState | None = None,
) -> int | None:
    """Thin wrapper that imports and calls ``_bake_mission_number_into_mission_branch``."""
    # Import here to avoid pulling in typer/rich at module collect time.
    from specify_cli.cli.commands.consolidate import _bake_mission_number_into_mission_branch

    return _bake_mission_number_into_mission_branch(
        main_repo=repo,
        mission_slug=mission_slug,
        mission_branch=mission_branch,
        target_branch=target_branch,
        dry_run=False,
        merge_state=merge_state,
    )


def _read_mission_number(repo: Path, mission_slug: str) -> int | None:
    """Read mission_number from the working-tree meta.json of the mission branch."""
    feature_dir = repo / "kitty-specs" / mission_slug
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return meta.get("mission_number")


# ---------------------------------------------------------------------------
# T027 Test 1: partial-merge resume — idempotency check (FR-010 / #983)
# ---------------------------------------------------------------------------


class TestPartialMergeResumeIsIdempotent:
    """Reproduces the #983 bug scenario: first attempt wrote mission_number=N,
    then crashed; resume must NOT produce a second commit.

    Negative path: if the idempotency check is disabled, the assertion that
    commit count stays the same would fail — proving the test exercises the fix.
    """

    def test_idempotency_check_skips_write_when_number_already_matches(
        self, git_repo: Path
    ) -> None:
        mission_slug = "test-mission-01ABCDEF"
        mission_branch = _make_mission_branch(git_repo, mission_slug)

        # Simulate: first run wrote mission_number=1 into meta.json on the
        # mission branch, but crashed before finishing. Manually set the number.
        _git(git_repo, "checkout", mission_branch)
        feature_dir = git_repo / "kitty-specs" / mission_slug
        meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        meta["mission_number"] = 1
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _git(git_repo, "add", str(feature_dir / "meta.json"))
        _git(git_repo, "commit", "-m", f"chore({mission_slug}): assign mission_number=1")
        _git(git_repo, "checkout", "main")

        # Count commits on the mission branch AFTER the manual write.
        commits_after_first_write = _commit_count(git_repo, mission_branch)

        # Build a merge state that doesn't yet have the baked flag set.
        state = ConsolidationState(
            mission_id="01ABCDEFGHIJKLMNOPQRSTUVWX",
            mission_slug=mission_slug,
            target_branch="main",
            wp_order=["WP01"],
            mission_number_baked=False,
        )
        save_state(state, git_repo)

        # Run the assignment step as resume would: the target branch has no
        # mission with mission_number=1 yet (the mission isn't merged), so
        # `assign_next_mission_number` returns 1.  The idempotency check must
        # detect that meta.json already carries 1 and skip write + commit.
        result = _run_bake(
            git_repo,
            mission_slug,
            mission_branch,
            merge_state=state,
        )

        # No new commit produced on the mission branch — this is the #983
        # regression assertion. If the idempotency check is disabled, this
        # would be commits_after_first_write + 1.
        assert _commit_count(git_repo, mission_branch) == commits_after_first_write, (
            "Idempotency check should have prevented a second commit (regression #983)"
        )

        # #4900: this seam never marks mission_number_baked itself
        # -- only the executor does, after target-side verification.
        assert state.mission_number_baked is False, (
            "mission_number_baked must NOT be set here (#4900) -- only "
            "the executor sets it, after verifying the number on the target"
        )

        loaded = load_state(git_repo, "01ABCDEFGHIJKLMNOPQRSTUVWX")
        assert loaded is not None
        assert loaded.mission_number_baked is False

        # #4900: the skipped (idempotent) branch write never discards the
        # decided number -- it is returned so the executor's
        # target-tree write + read-back verification still runs.
        assert result == 1


# ---------------------------------------------------------------------------
# T027 Test 2: fresh-merge happy path (FR-011)
# ---------------------------------------------------------------------------


class TestFreshMergeHappyPath:
    """First-time assignment: meta.json has mission_number=null; the step
    writes the number and commits it. Per #4900 it does NOT mark
    mission_number_baked itself -- only the executor does, after verifying
    the number on the target.
    """

    def test_fresh_merge_writes_without_marking_baked_itself(self, git_repo: Path) -> None:
        mission_slug = "fresh-mission-02BCDEFGHI"
        mission_branch = _make_mission_branch(git_repo, mission_slug)
        # Count commits on the mission branch before assignment.
        commits_before = _commit_count(git_repo, mission_branch)

        state = ConsolidationState(
            mission_id="02BCDEFGHIJKLMNOPQRSTUVWX",
            mission_slug=mission_slug,
            target_branch="main",
            wp_order=["WP01"],
            mission_number_baked=False,
        )
        save_state(state, git_repo)

        result = _run_bake(
            git_repo,
            mission_slug,
            mission_branch,
            merge_state=state,
        )

        # A new commit should have been made on the mission branch.
        assert _commit_count(git_repo, mission_branch) == commits_before + 1, (
            "Expected exactly one new commit from the fresh assignment"
        )

        # The returned integer is the assigned number (1, since target is empty).
        assert result == 1

        # #4900: the flag is NOT set by this seam.
        assert state.mission_number_baked is False

        loaded = load_state(git_repo, "02BCDEFGHIJKLMNOPQRSTUVWX")
        assert loaded is not None
        assert loaded.mission_number_baked is False


# ---------------------------------------------------------------------------
# T027 Test 3: resume short-circuit — flag=True bypasses all I/O (FR-012)
# ---------------------------------------------------------------------------


class TestResumeShortCircuitWhenFlagIsTrue:
    """When mission_number_baked=True on the loaded state, the assignment step
    must return immediately without reading meta.json or making any git calls.
    """

    def test_short_circuit_does_not_read_meta_or_commit(self, git_repo: Path) -> None:
        mission_slug = "shortcircuit-mission-03CD"
        mission_branch = _make_mission_branch(git_repo, mission_slug)
        # Count on mission branch so we detect any unwanted commit there too.
        commits_before = _commit_count(git_repo, mission_branch)

        # State already has the baked flag set — simulates a resume where the
        # prior run completed the assignment successfully.
        state = ConsolidationState(
            mission_id="03CDEFGHIJKLMNOPQRSTUVWX",
            mission_slug=mission_slug,
            target_branch="main",
            wp_order=["WP01"],
            mission_number_baked=True,
        )
        save_state(state, git_repo)

        result = _run_bake(
            git_repo,
            mission_slug,
            mission_branch,
            merge_state=state,
        )

        # No commit must have been made on the mission branch.
        assert _commit_count(git_repo, mission_branch) == commits_before, (
            "Short-circuit (mission_number_baked=True) must not produce any commit"
        )

        # Function returns None immediately.
        assert result is None

        # The flag remains True.
        loaded = load_state(git_repo, "03CDEFGHIJKLMNOPQRSTUVWX")
        assert loaded is not None
        assert loaded.mission_number_baked is True


# ---------------------------------------------------------------------------
# T027 Bonus: backward-compatibility — older state files load without error
# ---------------------------------------------------------------------------


class TestBackwardCompatibilityLoad:
    """Older state.json files that lack mission_number_baked must load safely
    with the default value of False.
    """

    def test_state_without_baked_flag_loads_as_false(self, tmp_path: Path) -> None:
        """Simulate a pre-WP04 state.json (no mission_number_baked key)."""
        import json as _json

        state_dir = (
            tmp_path / ".kittify" / "runtime" / "merge" / "legacy-mission-id"
        )
        state_dir.mkdir(parents=True, exist_ok=True)
        legacy_data = {
            "mission_id": "legacy-mission-id",
            "mission_slug": "legacy-mission",
            "target_branch": "main",
            "wp_order": ["WP01"],
            "completed_wps": [],
            "current_wp": None,
            "has_pending_conflicts": False,
            "strategy": "merge",
            "workspace_path": None,
            "started_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
            # NOTE: no "mission_number_baked" key — intentionally absent
        }
        (state_dir / "state.json").write_text(
            _json.dumps(legacy_data, indent=2), encoding="utf-8"
        )

        loaded = load_state(tmp_path, "legacy-mission-id")
        assert loaded is not None, "Legacy state file must load without error"
        assert loaded.mission_number_baked is False, (
            "mission_number_baked must default to False for pre-WP04 state files"
        )

    def test_round_trip_with_flag_true(self, tmp_path: Path) -> None:
        """State with mission_number_baked=True survives a save/load round-trip."""
        state = ConsolidationState(
            mission_id="round-trip-test-id",
            mission_slug="round-trip-test",
            target_branch="main",
            wp_order=["WP01"],
            mission_number_baked=True,
        )
        save_state(state, tmp_path)

        loaded = load_state(tmp_path, "round-trip-test-id")
        assert loaded is not None
        assert loaded.mission_number_baked is True
