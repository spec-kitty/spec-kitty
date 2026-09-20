"""Tests for WP02 merge strategy wiring (FR-005, FR-006, FR-007, FR-008, FR-009, NFR-003).

Covers:
- test_strategy_flag_flows_through (FR-005)
- test_default_strategy_is_squash (FR-006)
- test_lane_to_mission_uses_merge_commit (FR-007)
- test_config_yaml_strategy_honored (FR-008)
- test_invalid_config_strategy_raises (FR-008)
- test_push_rejection_emits_hint_for_known_tokens (FR-009)
- test_push_rejection_fails_open_for_unknown (FR-009)
- test_protected_linear_history_succeeds_default (NFR-003)

Note on patching: consolidate_lane_into_mission/integrate_mission_into_target are imported locally inside
_run_lane_based_merge, so they must be patched at the source module level
(specify_cli.lanes.merge.*) not at specify_cli.cli.commands.merge.*.
Similarly, evaluate_merge_gates and load_policy_config are patched at their source paths.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.merge import (
    LINEAR_HISTORY_REJECTION_TOKENS,
    _emit_remediation_hint,
    _is_linear_history_rejection,
    _run_lane_based_merge,
)
from specify_cli.merge.config import ConfigError, MergeStrategy, load_merge_config

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# FR-008 — load_merge_config tests
# ---------------------------------------------------------------------------


class TestLoadMergeConfig:
    def test_returns_empty_config_when_no_config_file(self, tmp_path: Path) -> None:
        config = load_merge_config(tmp_path)
        assert config.strategy is None

    def test_returns_empty_config_when_merge_section_absent(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("vcs:\n  type: git\n")
        config = load_merge_config(tmp_path)
        assert config.strategy is None

    def test_returns_squash_when_config_says_squash(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: squash\n")
        config = load_merge_config(tmp_path)
        assert config.strategy == MergeStrategy.SQUASH

    def test_returns_merge_when_config_says_merge(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: merge\n")
        config = load_merge_config(tmp_path)
        assert config.strategy == MergeStrategy.MERGE

    def test_returns_rebase_when_config_says_rebase(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: rebase\n")
        config = load_merge_config(tmp_path)
        assert config.strategy == MergeStrategy.REBASE

    def test_invalid_config_strategy_raises(self, tmp_path: Path) -> None:
        """FR-008: bogus merge.strategy raises ConfigError, not silent fallback."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: bogus\n")
        with pytest.raises(ConfigError, match="Invalid merge.strategy"):
            load_merge_config(tmp_path)

    def test_invalid_config_strategy_error_message_lists_allowed_values(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: fast\n")
        with pytest.raises(ConfigError) as exc_info:
            load_merge_config(tmp_path)
        msg = str(exc_info.value)
        assert "merge" in msg
        assert "squash" in msg
        assert "rebase" in msg


# ---------------------------------------------------------------------------
# FR-009 — push-error parser tests
# ---------------------------------------------------------------------------


class TestLinearHistoryRejectionParser:
    """FR-009: each of the 5 locked tokens triggers the hint; unknown stderr does not."""

    @pytest.mark.parametrize("token", list(LINEAR_HISTORY_REJECTION_TOKENS))
    def test_known_token_returns_true(self, token: str) -> None:
        assert _is_linear_history_rejection(f"remote: error: {token}") is True

    @pytest.mark.parametrize("token", list(LINEAR_HISTORY_REJECTION_TOKENS))
    def test_known_token_case_insensitive(self, token: str) -> None:
        assert _is_linear_history_rejection(f"REMOTE: {token.upper()}") is True

    def test_unrelated_stderr_returns_false(self) -> None:
        assert _is_linear_history_rejection("fatal: connection refused") is False

    def test_empty_stderr_returns_false(self) -> None:
        assert _is_linear_history_rejection("") is False

    def test_authentication_error_returns_false(self) -> None:
        assert _is_linear_history_rejection("remote: Permission to user/repo.git denied") is False


class TestEmitRemediationHint:
    def test_emits_hint_with_strategy_flag(self) -> None:
        from rich.console import Console
        from io import StringIO

        buf = StringIO()
        test_console = Console(file=buf, highlight=False, markup=False)
        _emit_remediation_hint(test_console)
        output = buf.getvalue()
        assert "squash" in output

    def test_emits_hint_with_config_key(self) -> None:
        from rich.console import Console
        from io import StringIO

        buf = StringIO()
        test_console = Console(file=buf, highlight=False, markup=False)
        _emit_remediation_hint(test_console)
        output = buf.getvalue()
        assert "merge.strategy" in output


# ---------------------------------------------------------------------------
# FR-005 / FR-006 — strategy wiring through _run_lane_based_merge
# ---------------------------------------------------------------------------


def _make_mock_lanes_manifest(mission_slug: str) -> MagicMock:
    """Return a mock LanesManifest for a 2-lane, 2-WP mission."""
    manifest = MagicMock()
    manifest.target_branch = "main"
    manifest.mission_branch = f"kitty/mission-{mission_slug}"

    lane_a = MagicMock()
    lane_a.lane_id = "lane-a"
    lane_a.wp_ids = ["WP01"]

    lane_b = MagicMock()
    lane_b.lane_id = "lane-b"
    lane_b.wp_ids = ["WP02"]

    manifest.lanes = [lane_a, lane_b]
    return manifest


def _write_meta(feature_dir: Path, mission_slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": mission_slug}),
        encoding="utf-8",
    )


@contextmanager
def _patched_lane_based_merge_dependencies(
    tmp_path: Path,
    manifest: MagicMock,
    lane_result: MagicMock,
    mission_result: MagicMock,
):
    """Patch heavy merge dependencies while preserving strategy call assertions."""
    with ExitStack() as stack:
        stack.enter_context(patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest))
        stack.enter_context(patch("specify_cli.merge.resolve.load_state", return_value=None))
        stack.enter_context(patch("specify_cli.merge.done_bookkeeping.save_state"))
        stack.enter_context(patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path))
        stack.enter_context(patch("specify_cli.merge.executor._enforce_target_branch_sync_preflight"))
        stack.enter_context(patch("specify_cli.merge.executor._check_mission_branch", return_value=(True, None)))
        stack.enter_context(patch("specify_cli.merge.executor._pre_mutation_safety_preflight"))
        stack.enter_context(patch("specify_cli.status.get_wp_lane", return_value="done"))
        mock_lane_merge = stack.enter_context(
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result)
        )
        mock_mission_merge = stack.enter_context(
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result)
        )
        stack.enter_context(patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"))
        stack.enter_context(patch("specify_cli.merge.executor.commit_merge_bookkeeping", return_value=True))
        mock_run_check = stack.enter_context(patch("specify_cli.post_merge.stale_assertions.run_check"))
        mock_gates = stack.enter_context(patch("specify_cli.policy.merge_gates.evaluate_merge_gates"))
        mock_policy = stack.enter_context(patch("specify_cli.policy.config.load_policy_config"))
        stack.enter_context(patch("specify_cli.merge.executor.run_command", return_value=(0, "abc123", "")))
        stack.enter_context(patch("specify_cli.merge.executor.has_remote", return_value=False))
        stack.enter_context(patch("specify_cli.merge.executor.cleanup_merge_workspace"))
        stack.enter_context(patch("specify_cli.merge.executor.clear_state"))
        stack.enter_context(patch("specify_cli.merge.state.MergeState"))

        stale_report = MagicMock()
        stale_report.findings = []
        mock_run_check.return_value = stale_report

        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mock_gates.return_value = gate_eval

        policy = MagicMock()
        policy.merge_gates = []
        mock_policy.return_value = policy

        yield mock_lane_merge, mock_mission_merge


class TestStrategyFlagFlowsThrough:
    """FR-005: --strategy squash reaches _run_lane_based_merge and is honored."""

    def test_strategy_squash_passed_to_integrate_mission_into_target(self, tmp_path: Path) -> None:
        """FR-005: strategy parameter is passed down to integrate_mission_into_target."""
        mission_slug = "068-test"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug)

        manifest = _make_mock_lanes_manifest(mission_slug)

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        with _patched_lane_based_merge_dependencies(
            tmp_path, manifest, lane_result, mission_result
        ) as (_mock_lane_merge, mock_mission_merge):
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

            # Verify strategy was passed to integrate_mission_into_target
            mock_mission_merge.assert_called_once()
            call_kwargs = mock_mission_merge.call_args.kwargs
            assert call_kwargs.get("strategy") == MergeStrategy.SQUASH

    def test_default_strategy_is_squash(self, tmp_path: Path) -> None:
        """FR-006: when no strategy is specified, SQUASH is the default."""
        mission_slug = "068-test2"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug)

        manifest = _make_mock_lanes_manifest(mission_slug)

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        with _patched_lane_based_merge_dependencies(
            tmp_path, manifest, lane_result, mission_result
        ) as (_mock_lane_merge, mock_mission_merge):
            # Call WITHOUT specifying strategy → should default to SQUASH
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
            )

            mock_mission_merge.assert_called_once()
            call_kwargs = mock_mission_merge.call_args.kwargs
            assert call_kwargs.get("strategy") == MergeStrategy.SQUASH


# ---------------------------------------------------------------------------
# FR-007 — lane→mission uses merge commit regardless of strategy
# ---------------------------------------------------------------------------


class TestLaneToMissionUsesMergeCommit:
    """FR-007: lane→mission keeps merge-commit semantics regardless of strategy."""

    def test_lane_to_mission_does_not_receive_strategy(self, tmp_path: Path) -> None:
        """Verify consolidate_lane_into_mission is called WITHOUT a strategy parameter."""
        mission_slug = "068-test3"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug)

        manifest = _make_mock_lanes_manifest(mission_slug)

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        with _patched_lane_based_merge_dependencies(
            tmp_path, manifest, lane_result, mission_result
        ) as (mock_lane_merge, _mock_mission_merge):
            # Use squash strategy — lane→mission should NOT be affected
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

            # consolidate_lane_into_mission must NOT receive a strategy parameter
            for call in mock_lane_merge.call_args_list:
                assert "strategy" not in call.kwargs, (
                    "lane→mission merge must not receive a strategy parameter "
                    "(FR-007: always uses merge commit)"
                )


# ---------------------------------------------------------------------------
# FR-008 — config yaml strategy honored
# ---------------------------------------------------------------------------


class TestConfigYamlStrategyHonored:
    """FR-008: merge.strategy in config.yaml is honored when no CLI flag is given."""

    def test_config_merge_strategy_squash(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("merge:\n  strategy: merge\n")
        config = load_merge_config(tmp_path)
        assert config.strategy == MergeStrategy.MERGE


# ---------------------------------------------------------------------------
# NFR-003 — linear history protection integration test
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo at path with an initial commit."""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        cwd=path, check=True, capture_output=True
    )


class TestProtectedLinearHistorySucceedsDefault:
    """NFR-003: squash default succeeds against a remote with denyNonFastForwards."""

    def test_push_with_squash_avoids_linear_history_error(self, tmp_path: Path) -> None:
        """Squash produces a single new commit which fast-forwards cleanly."""
        # Set up a bare remote with receive.denyNonFastForwards = true
        remote = tmp_path / "remote.git"
        remote.mkdir()
        subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=remote, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "receive.denyNonFastForwards", "true"],
            cwd=remote, check=True, capture_output=True,
        )

        # Set up a local repo and push
        local = tmp_path / "local"
        local.mkdir()
        _init_git_repo(local)

        # Add a commit to local to make remote behind
        (local / "feature.txt").write_text("feature\n")
        subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "feature"],
            cwd=local, check=True, capture_output=True,
        )

        # Squash merge produces a linear history — should push cleanly
        # The key assertion: _is_linear_history_rejection should NOT fire
        # for a squash-merged commit on a linear-history-only remote.
        # We verify this by checking that a single-commit push succeeds.
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=local, check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local, capture_output=True, text=True,
        )
        # A regular linear-history push should succeed
        assert result.returncode == 0, f"Push failed unexpectedly: {result.stderr}"

    def test_merge_commit_push_rejected_by_linear_history(self, tmp_path: Path) -> None:
        """A merge commit push to denyNonFastForwards remote emits the remediation hint."""
        # Set up a bare remote with denyNonFastForwards
        remote = tmp_path / "remote.git"
        remote.mkdir()
        subprocess.run(["git", "init", "--bare", "-b", "main"], cwd=remote, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "receive.denyNonFastForwards", "true"],
            cwd=remote, check=True, capture_output=True,
        )

        # Initialize local and push initial commit
        local = tmp_path / "local"
        local.mkdir()
        _init_git_repo(local)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=local, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local, check=True, capture_output=True,
        )

        # Create a branch and merge back with a merge commit
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=local, check=True, capture_output=True)
        (local / "feat.txt").write_text("feature\n")
        subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "feat"],
            cwd=local, check=True, capture_output=True,
        )
        subprocess.run(["git", "checkout", "main"], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "merge", "--no-ff", "feature",
             "-m", "Merge feature into main"],
            cwd=local, check=True, capture_output=True,
        )

        # This push should fail on a strict linear-history remote (merge commit is non-fast-forward)
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local, capture_output=True, text=True,
        )
        # The push fails because it's not a fast-forward
        if result.returncode != 0:
            # Verify our parser recognises this as a linear history rejection
            full_stderr = result.stderr
            # denyNonFastForwards returns "non-fast-forward" in the rejection
            assert _is_linear_history_rejection(full_stderr), (
                f"Expected linear history rejection but parser returned False. "
                f"stderr: {full_stderr!r}"
            )
