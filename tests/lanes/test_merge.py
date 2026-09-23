"""Tests for lane-based merge operations."""

import os
import subprocess

import pytest

from specify_cli.lanes.merge import (
    LaneMergeResult,
    MissionMergeResult,
    _ensure_info_attributes,
    _git_common_dir,
    _merge_branch_into,
    _remove_info_attributes,
    consolidate_lane_into_mission,
    integrate_mission_into_target,
    preview_mission_target_integration,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.merge.config import MergeStrategy


def _info_attributes_driver_lines(repo):
    """Return the ``merge=spec-kitty-*`` driver lines in ``$GIT_COMMON_DIR/info/attributes``."""
    common_dir = _git_common_dir(repo)
    assert common_dir is not None
    attributes_path = common_dir / "info" / "attributes"
    if not attributes_path.exists():
        return []
    return [
        line
        for line in attributes_path.read_text(encoding="utf-8").splitlines()
        if "merge=spec-kitty-" in line
    ]

pytestmark = pytest.mark.git_repo


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=True)


def _git_stdout(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(repo, filename, content, message):
    (repo / filename).parent.mkdir(parents=True, exist_ok=True)
    (repo / filename).write_text(content)
    _run(["git", "add", filename], repo)
    _run(["git", "commit", "-m", message], repo)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@test.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _commit(repo, "README.md", "init\n", "init")
    _run(["git", "branch", "-M", "main"], repo)
    return repo


def _make_manifest(mission_slug="010-feat", *, target_branch="main", lanes=None):
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch=target_branch,
        lanes=lanes
        or [
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-04-03T12:00:00+00:00",
        computed_from="test",
    )


class TestMergeLaneToMission:
    def test_successful_lane_merge(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        # Create mission and lane branches
        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "branch", "kitty/mission-010-feat-lane-a"], repo)

        # Add a commit on the lane branch
        _run(["git", "checkout", "kitty/mission-010-feat-lane-a"], repo)
        _commit(repo, "src/new.py", "lane work\n", "lane commit")
        _run(["git", "checkout", "main"], repo)

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-a", manifest)

        assert result.success is True
        assert result.lane_id == "lane-a"
        assert result.merged_into == "kitty/mission-010-feat"

    def test_stale_lane_blocked(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "branch", "kitty/mission-010-feat-lane-a"], repo)

        # Both mission and lane change the same file
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/views.py", "mission\n", "mission change")

        _run(["git", "checkout", "kitty/mission-010-feat-lane-a"], repo)
        _commit(repo, "src/views.py", "lane\n", "lane change")
        _run(["git", "checkout", "main"], repo)

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-a", manifest)

        assert result.success is False
        assert result.stale_check is not None
        assert result.stale_check.is_stale is True

    def test_nonexistent_lane_branch(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()
        _run(["git", "branch", "kitty/mission-010-feat"], repo)

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-a", manifest)

        assert result.success is False
        assert "does not exist" in result.errors[0]

    def test_unknown_lane_id(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-z", manifest)

        assert result.success is False
        assert "not found" in result.errors[0]

    def test_planning_lane_uses_target_branch_not_main(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "checkout", "-b", "release/3.1.1"], repo)
        _commit(repo, "docs/release-note.md", "planning update\n", "planning base")
        _run(["git", "checkout", "main"], repo)
        _run(["git", "branch", "kitty/mission-010-feat", "release/3.1.1"], repo)

        manifest = _make_manifest(
            target_branch="release/3.1.1",
            lanes=[
                ExecutionLane(
                    lane_id="lane-planning",
                    wp_ids=("WP00",),
                    write_scope=("kitty-specs/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
        )

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-planning", manifest)

        assert result.success is True
        assert result.lane_id == "lane-planning"
        assert result.merged_into == "kitty/mission-010-feat"

    def test_stale_planning_lane_blocked_with_repo_root_remediation(self, tmp_path):
        """The `lane-planning` lane has no `.worktrees/` entry by design -- a
        stale-block error must not send the operator to a directory that
        cannot exist there (mirrors test_stale_lane_blocked for lane-a)."""
        repo = _make_repo(tmp_path)
        _run(["git", "checkout", "-b", "release/3.1.1"], repo)
        _commit(repo, "kitty-specs/WP00.md", "planning base\n", "planning base")
        _run(["git", "checkout", "main"], repo)
        _run(["git", "branch", "kitty/mission-010-feat", "release/3.1.1"], repo)

        # Mission and the planning lane's own branch (release/3.1.1) both
        # change the same file after their common base.
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "kitty-specs/WP00.md", "mission change\n", "mission change")

        _run(["git", "checkout", "release/3.1.1"], repo)
        _commit(repo, "kitty-specs/WP00.md", "planning-branch change\n", "planning change")
        _run(["git", "checkout", "main"], repo)

        manifest = _make_manifest(
            target_branch="release/3.1.1",
            lanes=[
                ExecutionLane(
                    lane_id="lane-planning",
                    wp_ids=("WP00",),
                    write_scope=("kitty-specs/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
        )

        result = consolidate_lane_into_mission(repo, "010-feat", "lane-planning", manifest)

        assert result.success is False
        assert result.stale_check is not None
        assert result.stale_check.is_stale is True
        assert ".worktrees/" not in result.errors[0]
        assert "repository-root checkout" in result.errors[0]
        assert "git checkout release/3.1.1 && git merge kitty/mission-010-feat" in result.errors[0]
        assert "spec-kitty agent status materialize" in result.errors[0]


class TestMergeMissionToTarget:
    def test_successful_mission_merge(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        # Create mission branch with a commit
        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        result = integrate_mission_into_target(repo, "010-feat", manifest)

        assert result.success is True
        assert result.commit is not None
        assert result.target_branch == "main"

    def test_squash_conflict_preserves_newer_target_source(self, tmp_path):
        """#4892: ordinary source divergence must fail before ref advancement."""
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 1\nBETA = 2\n",
            "shared source base",
        )

        _run(["git", "branch", manifest.mission_branch], repo)
        _run(["git", "checkout", manifest.mission_branch], repo)
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 100\nBETA = 2\n",
            "mission changes alpha",
        )
        source_before = _git_stdout(repo, "rev-parse", manifest.mission_branch)

        _run(["git", "checkout", "main"], repo)
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 777\nBETA = 2\n",
            "target hotfix changes alpha",
        )
        target_before = _git_stdout(repo, "rev-parse", "main")
        bytes_before = (repo / "src/shared.py").read_bytes()

        result = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )

        assert result.success is False
        assert "src/shared.py" in result.errors[0]
        assert _git_stdout(repo, "rev-parse", manifest.mission_branch) == source_before
        assert _git_stdout(repo, "rev-parse", "main") == target_before
        assert _git_stdout(repo, "branch", "--show-current") == "main"
        assert (repo / "src/shared.py").read_bytes() == bytes_before

    def test_squash_conflict_carries_structured_paths_and_code(self, tmp_path):
        """#4892: the conflict is structured data, not just ``errors`` prose.

        The executor's ``--resume`` tolerance is a substring match on ``errors``
        for "already"/"up to date". A conflicting path that literally contains
        "already" would read as "already merged" and slip a real conflict through
        resume — so the result must expose ``conflicting_paths`` and the shared
        ``TARGET_BRANCH_CONTENT_CONFLICT`` code for callers to gate on.
        """
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()
        conflicting = "src/test_already_applied.py"
        _commit(repo, conflicting, "VALUE = 1\n", "shared source base")

        _run(["git", "branch", manifest.mission_branch], repo)
        _run(["git", "checkout", manifest.mission_branch], repo)
        _commit(repo, conflicting, "VALUE = 100\n", "mission value")

        _run(["git", "checkout", "main"], repo)
        _commit(repo, conflicting, "VALUE = 777\n", "target hotfix")

        result = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )

        assert result.success is False
        assert result.conflicting_paths == (conflicting,)
        assert result.diagnostic_code == "TARGET_BRANCH_CONTENT_CONFLICT"
        # The path contains "already" — the very substring the resume tolerance
        # keys on — proving callers must gate on ``conflicting_paths``, never the
        # message text.
        assert "already" in result.errors[0].lower()

    def test_squash_combines_disjoint_same_file_changes(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 1\nBETA = 2\nGAMMA = 3\n",
            "shared source base",
        )

        _run(["git", "branch", manifest.mission_branch], repo)
        _run(["git", "checkout", manifest.mission_branch], repo)
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 100\nBETA = 2\nGAMMA = 3\n",
            "mission changes alpha",
        )

        _run(["git", "checkout", "main"], repo)
        _commit(
            repo,
            "src/shared.py",
            "ALPHA = 1\nBETA = 2\nGAMMA = 300\n",
            "target changes gamma",
        )

        result = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )

        assert result.success is True
        assert (repo / "src/shared.py").read_text(encoding="utf-8") == (
            "ALPHA = 100\nBETA = 2\nGAMMA = 300\n"
        )

    def test_squash_preview_reports_same_conflict_without_mutation(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()
        _commit(repo, "src/shared.py", "VALUE = 1\n", "shared source base")

        _run(["git", "branch", manifest.mission_branch], repo)
        _run(["git", "checkout", manifest.mission_branch], repo)
        _commit(repo, "src/shared.py", "VALUE = 100\n", "mission value")
        source_before = _git_stdout(repo, "rev-parse", manifest.mission_branch)

        _run(["git", "checkout", "main"], repo)
        _commit(repo, "src/shared.py", "VALUE = 777\n", "target hotfix")
        target_before = _git_stdout(repo, "rev-parse", "main")
        bytes_before = (repo / "src/shared.py").read_bytes()

        preview = preview_mission_target_integration(
            repo,
            manifest.mission_branch,
            "main",
            strategy=MergeStrategy.SQUASH,
        )

        assert preview.conflicting_paths == ("src/shared.py",)
        assert _git_stdout(repo, "rev-parse", manifest.mission_branch) == source_before
        assert _git_stdout(repo, "rev-parse", "main") == target_before
        assert _git_stdout(repo, "branch", "--show-current") == "main"
        assert (repo / "src/shared.py").read_bytes() == bytes_before
        assert _info_attributes_driver_lines(repo) == []
        assert (
            subprocess.run(
                [
                    "git",
                    "config",
                    "--local",
                    "--get",
                    "merge.spec-kitty-event-log.driver",
                ],
                cwd=str(repo),
                capture_output=True,
            ).returncode
            != 0
        )

    def test_squash_noop_fails_without_resume_permission(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        first = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )
        commits_after_first = subprocess.run(
            ["git", "rev-list", "--count", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        retry = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )
        commits_after_retry = subprocess.run(
            ["git", "rev-list", "--count", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert first.success is True
        assert retry.success is False
        assert "produced no changes" in retry.errors[0]
        assert commits_after_retry == commits_after_first

    def test_squash_retry_is_idempotent_when_resume_allows_already_applied(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        first = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
        )
        commits_after_first = subprocess.run(
            ["git", "rev-list", "--count", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        retry = integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
            allow_already_applied=True,
        )
        commits_after_retry = subprocess.run(
            ["git", "rev-list", "--count", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert first.success is True
        assert retry.success is True
        assert retry.already_applied is True
        assert retry.commit is None
        assert retry.errors == []
        assert commits_after_retry == commits_after_first

    def test_merge_self_heals_event_log_merge_driver_config(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        assert (
            subprocess.run(
                ["git", "config", "--local", "--get", "merge.spec-kitty-event-log.driver"],
                cwd=str(repo),
                capture_output=True,
                text=True,
            ).returncode
            != 0
        )

        result = integrate_mission_into_target(repo, "010-feat", manifest)

        assert result.success is True
        driver = subprocess.run(
            ["git", "config", "--local", "--get", "merge.spec-kitty-event-log.driver"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert driver == "spec-kitty merge-driver-event-log %O %A %B"

    def test_nonexistent_mission_branch(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        result = integrate_mission_into_target(repo, "010-feat", manifest)

        assert result.success is False
        assert "does not exist" in result.errors[0]

    def test_rebase_strategy_does_not_mutate_main_checkout_before_worktree(self, tmp_path):
        repo = _make_repo(tmp_path)
        source_branch = "kitty/mission-010-feat"

        _run(["git", "branch", source_branch], repo)
        _run(["git", "checkout", source_branch], repo)
        _commit(repo, "src/rebased.py", "mission work\n", "mission work")
        _run(["git", "checkout", "main"], repo)

        source_before = _git_stdout(repo, "rev-parse", source_branch)

        changed = _merge_branch_into(
            repo,
            source_branch,
            "main",
            strategy=MergeStrategy.REBASE,
        )

        assert changed is True
        assert _git_stdout(repo, "branch", "--show-current") == "main"
        assert _git_stdout(repo, "rev-parse", source_branch) == source_before
        assert _git_stdout(repo, "show", "main:src/rebased.py") == "mission work"

    def test_rebase_strategy_conflict_leaves_main_checkout_and_refs_unchanged(self, tmp_path):
        repo = _make_repo(tmp_path)
        source_branch = "kitty/mission-010-feat"

        _commit(repo, "src/conflict.py", "base\n", "base conflict file")
        _run(["git", "branch", source_branch], repo)
        _run(["git", "checkout", source_branch], repo)
        _commit(repo, "src/conflict.py", "source\n", "source conflict")
        _run(["git", "checkout", "main"], repo)
        _commit(repo, "src/conflict.py", "target\n", "target conflict")

        source_before = _git_stdout(repo, "rev-parse", source_branch)
        target_before = _git_stdout(repo, "rev-parse", "main")

        with pytest.raises(RuntimeError, match="Rebase of .* failed"):
            _merge_branch_into(
                repo,
                source_branch,
                "main",
                strategy=MergeStrategy.REBASE,
            )

        assert _git_stdout(repo, "branch", "--show-current") == "main"
        assert _git_stdout(repo, "rev-parse", source_branch) == source_before
        assert _git_stdout(repo, "rev-parse", "main") == target_before
        assert not (repo / ".git" / "rebase-merge").exists()


class TestSquashDoesNotLeakInfoAttributes:
    """#2709/#2711: the squash merge activates the custom drivers via
    ``$GIT_COMMON_DIR/info/attributes`` for the duration of the ephemeral merge
    only, and MUST tear that seeding down afterwards. If it persisted, a later
    ``auto_rebase`` in the same repo would find the git driver pre-activated and
    resolve ``status.events.jsonl`` via ``spec-kitty merge-driver-event-log`` on
    PATH before its in-process ``R-STATUS-EVENTS-JSONL-UNION`` classifier runs,
    re-coupling the two paths the split was meant to keep apart."""

    def test_squash_merge_tears_down_info_attributes_but_keeps_config(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        assert _info_attributes_driver_lines(repo) == []

        result = integrate_mission_into_target(
            repo, "010-feat", manifest, strategy=MergeStrategy.SQUASH
        )
        assert result.success is True

        # info/attributes activation is gone post-merge: a later auto_rebase must
        # fall back to its in-process union classifier, not the git driver.
        assert _info_attributes_driver_lines(repo) == []

        # ...but the git-config driver *definitions* persist (intended, inert
        # without an active attribute mapping — the self-heal surface).
        driver = subprocess.run(
            ["git", "config", "--local", "--get", "merge.spec-kitty-event-log.driver"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert driver == "spec-kitty merge-driver-event-log %O %A %B"

    def test_repeated_squash_merges_do_not_accumulate_info_attributes(self, tmp_path):
        repo = _make_repo(tmp_path)
        manifest = _make_manifest()

        _run(["git", "branch", "kitty/mission-010-feat"], repo)
        _run(["git", "checkout", "kitty/mission-010-feat"], repo)
        _commit(repo, "src/feature.py", "feature\n", "feature work")
        _run(["git", "checkout", "main"], repo)

        integrate_mission_into_target(
            repo, "010-feat", manifest, strategy=MergeStrategy.SQUASH
        )
        integrate_mission_into_target(
            repo,
            "010-feat",
            manifest,
            strategy=MergeStrategy.SQUASH,
            allow_already_applied=True,
        )
        assert _info_attributes_driver_lines(repo) == []


class TestInfoAttributesSeedTeardownSeam:
    """Unit coverage for the pure seed/teardown seam (test-scaffolding-as-design-smell:
    the behavior is testable without driving a full merge)."""

    def test_seed_returns_added_lines_and_teardown_removes_exactly_them(self, tmp_path):
        repo = _make_repo(tmp_path)
        info_dir = repo / ".git" / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        attributes_path = info_dir / "attributes"
        operator_line = "*.bin binary"
        attributes_path.write_text(operator_line + "\n", encoding="utf-8")

        added = _ensure_info_attributes(repo)

        assert added  # non-empty: driver lines were appended
        assert all("merge=spec-kitty-" in line for line in added)
        contents = attributes_path.read_text(encoding="utf-8").splitlines()
        assert operator_line in contents
        assert all(line in contents for line in added)

        _remove_info_attributes(repo, added)

        # Operator line survives; every seeded driver line is gone.
        remaining = attributes_path.read_text(encoding="utf-8").splitlines()
        assert remaining == [operator_line]

    def test_seed_is_idempotent_and_empty_teardown_is_noop(self, tmp_path):
        repo = _make_repo(tmp_path)

        first = _ensure_info_attributes(repo)
        assert first  # created + populated

        second = _ensure_info_attributes(repo)
        assert second == []  # already present → nothing added

        # A no-op teardown (nothing was added the second time) must not disturb
        # the lines the first seeding created.
        attributes_path = _git_common_dir(repo) / "info" / "attributes"
        before = attributes_path.read_text(encoding="utf-8")
        _remove_info_attributes(repo, second)
        assert attributes_path.read_text(encoding="utf-8") == before

    def test_teardown_unlinks_file_it_created(self, tmp_path):
        repo = _make_repo(tmp_path)
        attributes_path = _git_common_dir(repo) / "info" / "attributes"
        # Fresh repo: git init does not create info/attributes.
        assert not attributes_path.exists()

        added = _ensure_info_attributes(repo)
        assert added
        assert attributes_path.exists()

        _remove_info_attributes(repo, added)

        # Restored to prior state: the file we created is gone entirely.
        assert not attributes_path.exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX fake-git shim; the git_repo suite runs on POSIX CI shards.",
)
def test_ensure_merge_driver_config_raises_on_git_failure(tmp_path, monkeypatch):
    """The exception types init tolerates (#4159) are the ones the real helper raises.

    ``init`` wraps :func:`_ensure_merge_driver_git_config` in
    ``except (OSError, subprocess.CalledProcessError)`` and proves it with two
    *mocked* failures (``tests/agent/test_init_command.py``). Those tests never
    drive the real helper, so a future refactor that wrapped its failure in a
    different exception type would slip past both and silently re-break the
    init-abort this PR fixes. This pins the other half end-to-end: when the
    underlying ``git config`` invocation genuinely fails, the real helper raises
    ``subprocess.CalledProcessError`` (``_set_local_git_config``'s ``check=True``)
    -- the caught type -- and nothing else.
    """
    from specify_cli.lanes import merge as merge_module

    repo = _make_repo(tmp_path)  # real git repo; the helper's .git guard passes

    # A ``git`` that always exits non-zero, resolved via the merge pipeline's
    # single env authority (``_make_merge_env``), so only the helper's own
    # git-config calls fail -- not the real repo built above.
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nexit 1\n")
    fake_git.chmod(0o755)
    monkeypatch.setattr(
        merge_module,
        "_make_merge_env",
        lambda: {"PATH": str(fake_bin)},
    )

    with pytest.raises(subprocess.CalledProcessError):
        merge_module._ensure_merge_driver_git_config(repo)
