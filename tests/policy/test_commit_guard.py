"""Tests for pre-commit ownership guard."""

from specify_cli.policy.commit_guard import (
    CommitGuardResult,
    OwnershipScope,
    is_implementation_branch,
    validate_staged_files,
)
from specify_cli.policy.config import CommitGuardConfig


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

class TestBranchDetection:
    def test_lane_branch(self):
        assert is_implementation_branch("kitty/mission-057-feat-lane-a") is True

    def test_non_lane_branch_rejected(self):
        assert is_implementation_branch("057-feat-dev") is False

    def test_main_branch(self):
        assert is_implementation_branch("main") is False

    def test_mission_branch(self):
        assert is_implementation_branch("kitty/mission-057-feat") is False


class TestKittySpecsProtection:
    def test_blocks_kitty_specs_on_lane_branch(self):
        result = validate_staged_files(
            staged_files=["kitty-specs/057/spec.md", "src/app.py"],
            owned_files=["src/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is False
        assert any("kitty-specs" in v for v in result.violations)

    def test_warns_kitty_specs_in_warn_mode(self):
        result = validate_staged_files(
            staged_files=["kitty-specs/057/spec.md"],
            owned_files=["src/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="warn"),
        )
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_allows_kitty_specs_when_disabled(self):
        result = validate_staged_files(
            staged_files=["kitty-specs/057/spec.md"],
            owned_files=["src/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(block_mission_specs=False),
        )
        assert result.allowed is True
        assert len(result.violations) == 0

    def test_allows_own_occurrence_map_on_lane_branch(self):
        """#2980: a bulk-edit mission's own occurrence map is the single permitted
        kitty-specs/ lane write — even in block mode, and not even a warning."""
        result = validate_staged_files(
            staged_files=["kitty-specs/057-feat/occurrence_map.yaml", "src/app.py"],
            owned_files=["src/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is True
        assert not any("kitty-specs" in v for v in result.violations)
        assert not any("kitty-specs" in w for w in result.warnings)

    def test_still_blocks_other_kitty_specs_alongside_occurrence_map(self):
        """The exception is scoped to occurrence_map.yaml; a sibling spec.md on
        the lane is still a protected-path violation."""
        result = validate_staged_files(
            staged_files=[
                "kitty-specs/057-feat/occurrence_map.yaml",
                "kitty-specs/057-feat/spec.md",
            ],
            owned_files=["src/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is False
        assert any("spec.md" in v for v in result.violations)
        assert not any("occurrence_map.yaml" in v for v in result.violations)


class TestOwnershipEnforcement:
    def test_in_scope_files_allowed(self):
        result = validate_staged_files(
            staged_files=["src/views/dashboard.py", "src/views/utils.py"],
            owned_files=["src/views/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is True

    def test_out_of_scope_blocked(self):
        result = validate_staged_files(
            staged_files=["src/views/dashboard.py", "src/merge/engine.py"],
            owned_files=["src/views/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is False
        assert any("src/merge/engine.py" in v for v in result.violations)

    def test_out_of_scope_warned_in_warn_mode(self):
        result = validate_staged_files(
            staged_files=["src/merge/engine.py"],
            owned_files=["src/views/**"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="warn"),
        )
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_no_owned_files_allows_all(self):
        result = validate_staged_files(
            staged_files=["anything.py"],
            owned_files=[],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is True

    def test_non_implementation_branch_skips_all(self):
        result = validate_staged_files(
            staged_files=["kitty-specs/spec.md", "src/anything.py"],
            owned_files=["src/views/**"],
            branch_name="main",
            policy=CommitGuardConfig(mode="block"),
        )
        assert result.allowed is True

    def test_active_wp_scope_violation_includes_active_context(self):
        result = validate_staged_files(
            staged_files=["src/previous.py"],
            owned_files=["src/active.py"],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
            ownership_scope=OwnershipScope(
                owned_files=["src/active.py"],
                active_wp_id="WP04",
                lane_id="lane-a",
                context_source="canonical_status",
            ),
        )

        assert result.allowed is False
        assert result.violations == [
            "ACTIVE_WP_SCOPE_VIOLATION: src/previous.py is outside active_wp=WP04 owned_files ['src/active.py']; lane_id=lane-a; context_source=canonical_status"
        ]

    def test_stale_or_ambiguous_context_diagnostic_is_not_scope_violation(self):
        result = validate_staged_files(
            staged_files=["src/previous.py"],
            owned_files=[],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
            ownership_scope=OwnershipScope(
                owned_files=[],
                active_wp_id=None,
                lane_id="lane-a",
                context_source="canonical_status",
                diagnostic_code="ACTIVE_WP_CONTEXT_AMBIGUOUS",
                diagnostic_message=(
                    "ACTIVE_WP_CONTEXT_AMBIGUOUS: Cannot prove active WP for branch "
                    "kitty/mission-057-feat-lane-a; lane_id=lane-a; active candidates: WP01, WP04"
                ),
            ),
        )

        assert result.allowed is False
        assert result.violations == [
            "ACTIVE_WP_CONTEXT_AMBIGUOUS: Cannot prove active WP for branch kitty/mission-057-feat-lane-a; lane_id=lane-a; active candidates: WP01, WP04"
        ]
        assert "Out of scope" not in result.violations[0]

    def test_active_wp_without_owned_files_fails_closed(self):
        result = validate_staged_files(
            staged_files=["src/anything.py"],
            owned_files=[],
            branch_name="kitty/mission-057-feat-lane-a",
            policy=CommitGuardConfig(mode="block"),
            ownership_scope=OwnershipScope(
                owned_files=[],
                active_wp_id="WP04",
                lane_id="lane-a",
                context_source="canonical_status",
            ),
        )

        assert result.allowed is False
        assert result.violations == [
            "ACTIVE_WP_OWNERSHIP_MISSING: active_wp=WP04 has no owned_files; lane_id=lane-a; context_source=canonical_status"
        ]


class TestHookInstaller:
    def test_install_creates_hook(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)

        from specify_cli.policy.hook_installer import install_commit_guard

        record = install_commit_guard(repo, repo)

        # #4895: install_commit_guard now returns the full HookInstallRecord
        # (so the backup_path it may carry is never dropped) rather than a
        # bare Path; hook_path is still the installed hook's location.
        assert record is not None
        assert record.hook_path.exists()
        assert "commit_guard_hook" in record.hook_path.read_text()
        assert record.backup_path is None

    def test_install_is_idempotent(self, tmp_path):
        import subprocess

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)

        from specify_cli.policy.hook_installer import install_commit_guard

        record1 = install_commit_guard(repo, repo)
        record2 = install_commit_guard(repo, repo)
        assert record1 == record2
