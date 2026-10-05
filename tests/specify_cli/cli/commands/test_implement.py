"""WP06 (T026) -- unit tests for the implement planning-artifact migration.

These tests pin the behavior that planning-artifact commits route
through :class:`BookkeepingTransaction` when the mission has a
``coordination_branch`` in ``meta.json``, and fall back to the legacy
raw-git path when it does not.

The full end-to-end flow lives in
``tests/integration/test_implement_review_flow.py``; this file covers
the small pure-Python shape changes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from specify_cli.coordination.planning_commit import PlanningPlacement

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _unresolved_placement() -> PlanningPlacement:
    """An unresolved placement: these tests drive the commit directly, without a
    resolvable WP context, so the seam filters on the coordination branch
    ``meta.json`` declares (#5232, R-1b)."""
    return PlanningPlacement(resolved=False, ref=None)


def _make_meta(
    feature_dir: Path,
    *,
    with_coord: bool = True,
    mission_id: str = "01JZZZZZZZZZZZZZZZZZZZZZZZ",
    mission_slug: str = "wp06-impl-mission",
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-05-28T00:00:00+00:00",
        "friendly_name": "WP06 implement test mission",
    }
    if with_coord:
        payload["coordination_branch"] = f"kitty/mission-{mission_slug}-{mission_id[:8]}"
    (feature_dir / "meta.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


class TestPlanningArtifactIdempotentCommit:
    """Sequential claims must not fail on already-committed planning edits.

    The coordination model commits a claim's COORD-partition-artifact edits to
    the coordination branch but leaves them uncommitted in the main checkout. A
    later claim re-discovers those edits as "uncommitted"; committing the
    identical content again is an empty commit, which ``safe_commit`` rejects
    with "git commit failed" — blocking every claim after the first. The commit
    path must treat already-on-coord content as an idempotent no-op.

    Re-pinned (WP01 / #2533): the fixture file is ``issue-matrix.md``, a
    genuine COORD-partition kind (``mission_runtime.artifacts.MissionArtifactKind.ISSUE_MATRIX``)
    that legitimately still compares against and commits to the coordination
    ref post-fix. The original fixture used ``tasks/WP01.md`` (a PRIMARY kind,
    ``WORK_PACKAGE_TASK``) — under the corrected partition it now compares
    against ``HEAD`` (see ``resolve_precondition_ref``), so an "already on
    coord" scenario no longer applies to it; that PRIMARY-kind idempotency
    invariant is covered instead by
    ``TestResolvePlanningArtifactStaging.test_idempotent_when_already_matching_its_partition_ref``
    in ``test_implement_cores.py``. The write-side twin of committing a
    genuinely-dirty PRIMARY artifact to the *primary* ref (never coord) is
    FR-003 / WP02's scope, not this test's.
    """

    def test_committing_content_already_on_coord_is_noop(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

        mission_slug = "demo-feature"
        mission_id = "01J6XW9K00000000000000000P"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        git("config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        git("add", "seed.txt")
        git("commit", "-q", "-m", "initial")

        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            feature_dir,
            with_coord=True,
            mission_id=mission_id,
            mission_slug=mission_slug,
        )
        coord_artifact = feature_dir / "issue-matrix.md"
        feature_dir.mkdir(parents=True, exist_ok=True)

        # 1) Commit the COORD-kind artifact with content X; point coord at it
        #    (coord HEAD == X).
        coord_artifact.write_text("lane: in_progress\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "feature dir @ X")
        git("branch", coord_branch)
        coord_before = git("rev-parse", coord_branch)

        # 2) Advance main HEAD so the tracked file differs (content Y).
        coord_artifact.write_text("lane: in_progress\nY\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "main @ Y")

        # 3) Working tree: restore content X. Now `git status` reports the
        #    artifact as modified (differs from main HEAD=Y) but its content
        #    equals coord=X.
        coord_artifact.write_text("lane: in_progress\n", encoding="utf-8")
        assert git("status", "--porcelain", str(feature_dir))  # dirty

        # MUST NOT raise: the only dirty file already matches coord, so the
        # commit is an idempotent no-op (previously raised "git commit failed").
        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            planning_branch="main",
            auto_commit=True,
            placement=_unresolved_placement(),
        )

        # No empty commit was created on the coordination branch.
        assert git("rev-parse", coord_branch) == coord_before


class TestSoloPrBoundCoordMissionClaimPrecondition:
    """WP01 (#2533) red-first regression: the implement-claim precondition
    compared EVERY feature-dir file against a single collapsed ref (the
    coordination branch), so a solo PR-bound ``coord`` mission whose planning
    artifacts are committed on the feature/target branch -- and therefore
    legitimately absent on the still-empty coordination branch -- aborted the
    claim with "Planning artifacts not committed", even with nothing left to
    commit. FR-002/FR-004: fixed by resolving the comparison ref PER FILE via
    ``resolve_precondition_ref`` (PRIMARY kinds -> HEAD, COORD kinds -> coord).

    Modeled on ``test_committing_content_already_on_coord_is_noop`` above: a
    real ``tmp_path`` git repo, ``_make_meta(..., with_coord=True)``, and the
    pre-existing precondition entry point
    (``_ensure_planning_artifacts_committed_git``) driven with
    ``auto_commit=False`` (required for the abort path).
    """

    def test_committed_planning_artifacts_do_not_abort_the_claim(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

        mission_slug = "solo-coord-mission"
        mission_id = "01J7Y8Z900000000000000000Q"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        git("config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        git("add", "seed.txt")
        git("commit", "-q", "-m", "initial")

        # The coordination branch is created BEFORE any planning artifact
        # exists -- an "empty" coord branch, exactly the solo PR-bound
        # scenario (Acceptance Scenario 1).
        git("branch", coord_branch)

        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            feature_dir,
            with_coord=True,
            mission_id=mission_id,
            mission_slug=mission_slug,
        )
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (feature_dir / "lanes.json").write_text("{}\n", encoding="utf-8")
        wp = feature_dir / "tasks" / "WP01.md"
        wp.parent.mkdir(parents=True, exist_ok=True)
        wp.write_text(
            "---\nwork_package_id: WP01\nagent: null\n---\nbody\n",
            encoding="utf-8",
        )

        git("add", "-A")
        git("commit", "-q", "-m", "planning artifacts committed on the feature branch")

        # Simulate the prior claim's own uncommitted runtime self-write
        # (shell_pid/shell_pid_created_at -- the exact #2570.1 residue) so
        # this is a genuinely dirty PRIMARY file at claim time, not merely a
        # clean-but-coord-absent one.
        wp.write_text(
            "---\nwork_package_id: WP01\nagent: null\nshell_pid: '4242'\n"
            "shell_pid_created_at: '123.0'\n---\nbody\n",
            encoding="utf-8",
        )
        assert git("status", "--porcelain", str(feature_dir)), "expected WP01.md to be dirty"

        coord_before = git("rev-parse", coord_branch)

        # RED (pre-fix): every planning artifact is diffed against the coord
        # branch, where they are all legitimately absent -> read as "changed"
        # -> the WP01.md runtime-only self-write cannot be recognized as
        # lock-only (its committed baseline is looked up on coord, where it
        # does not exist either) -> the claim aborts with typer.Exit(1) and
        # "Planning artifacts not committed", even though nothing genuinely
        # needs committing.
        # GREEN (post-fix): PRIMARY kinds compare against HEAD; the runtime-only
        # WP01.md diff is recognized and dropped, and every other planning
        # artifact matches HEAD byte-for-byte -> the claim proceeds silently.
        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            planning_branch="main",
            auto_commit=False,
            placement=_unresolved_placement(),
        )

        # Topology is unchanged: the coordination branch was never touched.
        assert git("rev-parse", coord_branch) == coord_before


class TestStructuralPlanningArtifactsFailClosed:
    """Deletions/renames of planning artifacts must FAIL CLOSED, not proceed.

    The planning-artifact commit routes through ``BookkeepingTransaction.write_artifact``
    — a write-only API that cannot remove an old path from the coordination branch.
    Before this fix, a deleted/renamed artifact was silently dropped (the parser kept
    only the rename's new path; the idempotency filter ``continue``d on a non-existent
    source) and the claim PROCEEDED, leaving the coordination branch incoherent
    (stale deleted/renamed-from artifacts) — #1598 review P1. The claim must refuse.
    """

    def _seeded_repo(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        git("config", "commit.gpgsign", "false")
        feature_dir = repo / "kitty-specs" / "demo-feature"
        _make_meta(
            feature_dir,
            with_coord=True,
            mission_id="01J6XW9K00000000000000000P",
            mission_slug="demo-feature",
        )
        wp = feature_dir / "tasks" / "WP01.md"
        wp.parent.mkdir(parents=True, exist_ok=True)
        wp.write_text("lane: planned\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "seed feature dir")
        return repo, feature_dir, git, wp

    def test_deleted_planning_artifact_fails_closed(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo, feature_dir, git, wp = self._seeded_repo(tmp_path)
        head_before = git("rev-parse", "HEAD")

        wp.unlink()  # unstaged deletion → porcelain " D kitty-specs/.../WP01.md"

        with pytest.raises(typer.Exit):
            _ensure_planning_artifacts_committed_git(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug="demo-feature",
                wp_id="WP02",
                planning_branch="main",
                auto_commit=True,
                placement=_unresolved_placement(),
            )
        # The claim refused: nothing was committed (no silent advance).
        assert git("rev-parse", "HEAD") == head_before

    def test_renamed_planning_artifact_fails_closed(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo, feature_dir, git, wp = self._seeded_repo(tmp_path)
        head_before = git("rev-parse", "HEAD")

        # Staged rename → porcelain "R  <old> -> <new>".
        git(
            "mv",
            "kitty-specs/demo-feature/tasks/WP01.md",
            "kitty-specs/demo-feature/tasks/WP01-renamed.md",
        )

        with pytest.raises(typer.Exit):
            _ensure_planning_artifacts_committed_git(
                repo_root=repo,
                feature_dir=feature_dir,
                mission_slug="demo-feature",
                wp_id="WP02",
                planning_branch="main",
                auto_commit=True,
                placement=_unresolved_placement(),
            )
        assert git("rev-parse", "HEAD") == head_before


class TestPlanningArtifactPath:
    """Modern (post-WP03) mission routes planning artifacts through coord branch."""

    def test_modern_mission_resolves_coord_branch_from_meta(
        self, tmp_path: Path
    ) -> None:
        from specify_cli.mission_metadata import load_meta

        feature_dir = tmp_path / "kitty-specs" / "wp06-impl-mission"
        _make_meta(feature_dir, with_coord=True)
        meta = load_meta(feature_dir)
        assert isinstance(meta, dict)
        assert meta["coordination_branch"].startswith("kitty/mission-")
        assert meta["mission_id"] == "01JZZZZZZZZZZZZZZZZZZZZZZZ"

    def test_legacy_mission_has_no_coord_branch(self, tmp_path: Path) -> None:
        from specify_cli.mission_metadata import load_meta

        feature_dir = tmp_path / "kitty-specs" / "wp06-legacy-mission"
        _make_meta(feature_dir, with_coord=False)
        meta = load_meta(feature_dir)
        assert isinstance(meta, dict)
        assert "coordination_branch" not in meta


class TestImplementModuleImports:
    """The migrated implement module imports cleanly after WP01/WP06."""

    def test_implement_imports_safe_commit_with_new_signature(self) -> None:
        from specify_cli.git import safe_commit
        import inspect

        sig = inspect.signature(safe_commit)
        assert "destination_ref" in sig.parameters
        assert "worktree_root" in sig.parameters


class TestNonCoordStatusFilesCommitted:
    """#1775 review M3: the coord-owned status-file exclusion must be coord-only.

    On a non-coordination (flat/legacy) mission there is no coord branch that owns
    the canonical status log/snapshot, so the primary checkout's ``status.events.jsonl``
    / ``status.json`` ARE canonical and must be committed. The pre-fix code excluded
    them unconditionally, silently dropping a status edit on flat missions.
    """

    def _entries(self):
        from specify_cli.cli.commands.implement_cores import _PorcelainEntry

        return [
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.events.jsonl", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.json", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/tasks.md", is_structural=False),
        ]

    def test_non_coord_includes_status_files(self) -> None:
        from specify_cli.cli.commands.implement_cores import _status_paths_for_commit

        # No coordination branch → the primary checkout's status files are
        # canonical and must be committed (not dropped).
        paths = _status_paths_for_commit(self._entries(), coord_branch_for_filter=None)
        assert "kitty-specs/m/status.events.jsonl" in paths
        assert "kitty-specs/m/status.json" in paths
        assert "kitty-specs/m/tasks.md" in paths

    def test_coord_excludes_status_files(self) -> None:
        from specify_cli.cli.commands.implement_cores import _status_paths_for_commit

        # Coordination branch present → status log/snapshot are coord-owned and
        # excluded so the primary checkout's stale copies do not clobber the seed.
        paths = _status_paths_for_commit(
            self._entries(), coord_branch_for_filter="kitty/mission-m-01ABCDEF"
        )
        assert "kitty-specs/m/status.events.jsonl" not in paths
        assert "kitty-specs/m/status.json" not in paths
        assert "kitty-specs/m/tasks.md" in paths


class TestPlanningArtifactAutoCommit:
    """Planning artifacts stage from the transaction worktree, not the caller checkout."""

    def test_auto_commit_uses_coordination_worktree_paths(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        mission_slug = "demo-feature"
        mission_id = "01J6XW9K00000000000000000P"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

        # #2648 (WP01): a real mission's planning_branch is never main/master
        # (protected) -- see test_implement_writeside.py's module docstring.
        # "main" used to double as an unrealistic stand-in that (pre-fix)
        # happened to divert through the ``767`` protected-branch arm, which
        # collapsed the whole batch onto ``coord_branch`` regardless of the
        # requested destination. Post-fix, a protected ``planning_branch``
        # here fails closed (``PlacementResolutionRequired``); check the repo
        # out directly on a realistic, non-protected, mission-branch-shaped
        # ref instead (``_print_planning_artifact_commit_instructions``
        # requires the actual checked-out branch to equal ``planning_branch``).
        planning_branch = f"mission/{mission_slug}"

        git("init", "-q", "-b", planning_branch)
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        git("config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        git("add", "seed.txt")
        git("commit", "-q", "-m", "initial")
        git("branch", coord_branch)

        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            feature_dir,
            with_coord=True,
            mission_id=mission_id,
            mission_slug=mission_slug,
        )
        (feature_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            planning_branch=planning_branch,
            auto_commit=True,
            placement=_unresolved_placement(),
        )

        # write-path-integrity WP02 / T008 / FR-001 (SC-001) re-baseline: a
        # PRIMARY artifact (tasks.md) now lands on the mission's TARGET branch,
        # NEVER the coordination branch. Pre-fix this test pinned the #3371 bug
        # (PRIMARY tasks.md committed onto coord); the fix routes it to the
        # target branch and leaves coord free of PRIMARY files.
        assert git("rev-parse", planning_branch) != git("rev-parse", coord_branch)
        assert (
            git("show", f"{planning_branch}:kitty-specs/{mission_slug}/tasks.md").strip()
            == "# tasks"
        )
        coord_branch_tasks = subprocess.run(
            ["git", "show", f"{coord_branch}:kitty-specs/{mission_slug}/tasks.md"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert coord_branch_tasks.returncode != 0, (
            "PRIMARY tasks.md must NOT be committed onto the coordination branch "
            "(#3371); it belongs on the mission target branch."
        )

    def test_auto_commit_with_coord_feature_dir_uses_primary_artifact_source(
        self, tmp_path: Path
    ) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        mission_slug = "demo-feature"
        mission_id = "01J6XW9K00000000000000000P"
        mid8 = mission_id[:8]
        coord_branch = f"kitty/mission-{mission_slug}-{mid8}"

        # #2648 (WP01): "main" is protected -- see the sibling test above for
        # the full rationale. Check the repo out directly on a realistic,
        # non-protected, mission-branch-shaped ref.
        planning_branch = f"mission/{mission_slug}"

        git("init", "-q", "-b", planning_branch)
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "Test")
        git("config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        git("add", "seed.txt")
        git("commit", "-q", "-m", "initial")
        git("branch", coord_branch)

        primary_feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(
            primary_feature_dir,
            with_coord=True,
            mission_id=mission_id,
            mission_slug=mission_slug,
        )
        tasks = primary_feature_dir / "tasks.md"
        tasks.write_text("# tasks\n", encoding="utf-8")

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=primary_feature_dir,
            mission_slug=mission_slug,
            wp_id="WP01",
            planning_branch=planning_branch,
            auto_commit=True,
            placement=_unresolved_placement(),
        )
        # write-path-integrity WP02 / T008 / FR-001 re-baseline: PRIMARY planning
        # artifacts (tasks.md, meta.json) are committed to the mission TARGET
        # branch from the PRIMARY checkout -- they are NO LONGER staged into a
        # coordination worktree (the removed #3371 mis-route). So the first claim
        # lands tasks.md on ``planning_branch`` and materialises NO coord worktree
        # for primary artifacts.
        assert (
            git("show", f"{planning_branch}:kitty-specs/{mission_slug}/tasks.md").strip()
            == "# tasks"
        )
        coord_first = subprocess.run(
            ["git", "show", f"{coord_branch}:kitty-specs/{mission_slug}/tasks.md"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert coord_first.returncode != 0

        # A second claim reads the PRIMARY feature dir as the artifact source and
        # commits the updated tasks.md to the target branch (never coord).
        tasks.write_text("# tasks\n\nupdated\n", encoding="utf-8")

        _ensure_planning_artifacts_committed_git(
            repo_root=repo,
            feature_dir=primary_feature_dir,
            mission_slug=mission_slug,
            wp_id="WP02",
            planning_branch=planning_branch,
            auto_commit=True,
            placement=_unresolved_placement(),
        )

        assert (
            git("show", f"{planning_branch}:kitty-specs/{mission_slug}/tasks.md").strip()
            == "# tasks\n\nupdated"
        )
        coord_second = subprocess.run(
            ["git", "show", f"{coord_branch}:kitty-specs/{mission_slug}/tasks.md"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert coord_second.returncode != 0, (
            "PRIMARY tasks.md must never be committed onto the coordination "
            "branch (#3371)."
        )
