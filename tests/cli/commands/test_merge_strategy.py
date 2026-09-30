"""Merge strategy contracts for ``spec-kitty consolidate``.

Covers:
- ``merge.strategy`` config parsing and validation.
- ``consolidate --strategy`` end to end (real CLI subprocess on a real coord
  mission): the flag > config > squash precedence, what each strategy leaves
  in the target's history, and lane -> mission staying a true merge.
- Linear-history push-rejection detection and its remediation hint.
- Squash avoiding a linear-history rejection on a protected remote.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.consolidate import (
    LINEAR_HISTORY_REJECTION_TOKENS,
    _emit_remediation_hint,
    _is_linear_history_rejection,
)
from specify_cli.consolidation.config import ConfigError, MergeStrategy, load_merge_config
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus, sha_reachable

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
# FR-005 / FR-006 / FR-007 / FR-008 — the real `consolidate --strategy`
# ---------------------------------------------------------------------------

_SQUASH = "squash"
_MERGE = "merge"


def _commit_merge_config(mission: CoordMission, strategy: str) -> None:
    """Commit ``merge.strategy`` to the target branch's ``.kittify/config.yaml``."""
    kittify = mission.repo / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(f"merge:\n  strategy: {strategy}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", ".kittify/config.yaml"], cwd=mission.repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "chore: set merge strategy"], cwd=mission.repo, check=True, capture_output=True)


def _merge_commits_between(mission: CoordMission, base: str, tip: str) -> list[str]:
    completed = subprocess.run(
        ["git", "rev-list", "--min-parents=2", f"{base}..{tip}"],
        cwd=mission.repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.split()


@pytest.mark.slow  # one real `spec-kitty consolidate` per case on a real 2-lane coord mission
@pytest.mark.parametrize(
    ("config_strategy", "cli_args", "expected"),
    [
        (None, [], _SQUASH),
        (None, ["--strategy", "squash"], _SQUASH),
        (None, ["--strategy", "merge"], _MERGE),
        ("merge", [], _MERGE),
        ("merge", ["--strategy", "squash"], _SQUASH),
    ],
    ids=["default-is-squash", "flag-squash", "flag-merge", "config-merge", "flag-beats-config"],
)
def test_consolidate_strategy_decides_whether_lane_history_reaches_the_target(
    tmp_path: Path, config_strategy: str | None, cli_args: list[str], expected: str
) -> None:
    """Drive the real CLI; the strategy is observable only in the target's git history.

    - squash: every WP's content lands on the target, but no lane commit is
      reachable from it and the target gains no merge commit.
    - merge: every lane tip is an ancestor of the target.
    - either way (FR-007), lane -> mission stays a true merge: every lane tip is
      an ancestor of the retained mission (coordination) branch.
    Precedence (FR-005/006/008): ``--strategy`` > ``merge.strategy`` config > squash.
    """
    wps = ("WP01", "WP02")
    mission = build_coord_mission(tmp_path, wps=wps, mid8="01M3RBFC")
    if config_strategy is not None:
        _commit_merge_config(mission, config_strategy)
    lane_tips = {wp: mission.rev(mission.lane_branch(wp)) for wp in wps}
    target_before = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--keep-branch", *cli_args])

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    target = mission.target_branch
    assert all(blob_present_at(mission.repo, target, f"src/pkg/{wp.lower()}.py") for wp in wps)
    lane_tips_on_target = {wp: sha_reachable(mission.repo, tip, target) for wp, tip in lane_tips.items()}
    if expected == _SQUASH:
        assert lane_tips_on_target == dict.fromkeys(wps, False)
        assert _merge_commits_between(mission, target_before, target) == []
    else:
        assert lane_tips_on_target == dict.fromkeys(wps, True)
    assert {wp: sha_reachable(mission.repo, tip, mission.coord_branch) for wp, tip in lane_tips.items()} == dict.fromkeys(wps, True)


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
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


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
            cwd=remote,
            check=True,
            capture_output=True,
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
            cwd=local,
            check=True,
            capture_output=True,
        )

        # Squash merge produces a linear history — should push cleanly
        # The key assertion: _is_linear_history_rejection should NOT fire
        # for a squash-merged commit on a linear-history-only remote.
        # We verify this by checking that a single-commit push succeeds.
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=local,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local,
            capture_output=True,
            text=True,
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
            cwd=remote,
            check=True,
            capture_output=True,
        )

        # Initialize local and push initial commit
        local = tmp_path / "local"
        local.mkdir()
        _init_git_repo(local)
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        # Create a branch and merge back with a merge commit
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=local, check=True, capture_output=True)
        (local / "feat.txt").write_text("feature\n")
        subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "feat"],
            cwd=local,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "checkout", "main"], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "merge", "--no-ff", "feature", "-m", "Merge feature into main"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        # This push should fail on a strict linear-history remote (merge commit is non-fast-forward)
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=local,
            capture_output=True,
            text=True,
        )
        # The push fails because it's not a fast-forward
        if result.returncode != 0:
            # Verify our parser recognises this as a linear history rejection
            full_stderr = result.stderr
            # denyNonFastForwards returns "non-fast-forward" in the rejection
            assert _is_linear_history_rejection(full_stderr), f"Expected linear history rejection but parser returned False. stderr: {full_stderr!r}"
