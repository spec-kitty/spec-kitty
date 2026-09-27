"""T030 — Integration smoke test: spec-kitty upgrade with all harnesses configured.

Verifies that ``MigrationRunner.upgrade()`` completes without errors on a minimal
project that has all harnesses configured and their harness directories present.

This guards against:
- Import errors in either Phase 1 or Phase 2 migration modules.
- Unhandled exceptions in writer code paths invoked during upgrade.
- Registry double-registration or key collisions between Phase 1 and Phase 2.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Force both migration modules to register before MigrationRunner is imported.
import specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code  # noqa: F401
import specify_cli.upgrade.migrations.m_3_3_0_session_presence_all_harnesses  # noqa: F401

from specify_cli.upgrade import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# Harnesses whose config directories to create for the smoke project.
# (NullWriter harnesses like qwen / kilocode / auggie / q are omitted because
# their ``can_write()`` always returns False — no directories needed.)
# ---------------------------------------------------------------------------
_HARNESS_DIRS = [
    ".claude",       # Phase 1
    ".cursor",       # cursor  (MarkdownRulesWriter)
    ".windsurf",     # windsurf (MarkdownRulesWriter)
    ".github",       # copilot  (MarkdownRulesWriter, check_dir=".github")
    # ".roo" omitted — Roo Code shut down on 2026-05-15 (C-007)
    ".kiro",         # kiro     (MarkdownRulesWriter)
    ".gemini",       # gemini   (MarkdownRulesWriter, append_mode=True)
    # codex / opencode / antigravity → AgentsMdWriter (always can_write=True)
    # pi / vibe / letta            → SkillsPreambleWriter (always can_write=True)
]

_ALL_AGENT_KEYS = [
    "claude",
    "cursor", "windsurf", "copilot", "kiro", "gemini",
    "codex", "opencode", "antigravity",
    "pi", "vibe", "letta",
    "qwen", "kilocode", "auggie", "q",
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
]

_FROM_VERSION = "3.2.0rc38"
_TARGET_VERSION = "3.2.0rc39"


def _make_full_project(tmp_path: Path) -> Path:
    """Create a minimal spec-kitty project with all harness dirs present."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()

    # Write config.yaml with all agents listed
    agents_yaml = "agents:\n  available:\n" + "".join(
        f"    - {key}\n" for key in _ALL_AGENT_KEYS
    )
    (kittify / "config.yaml").write_text(agents_yaml, encoding="utf-8")

    # Write real upgrade metadata so full-suite registry state cannot make this
    # smoke test start from "unknown" and replay legacy migrations.
    (kittify / "metadata.yaml").write_text(
        f"""spec_kitty:
  version: {_FROM_VERSION}
  initialized_at: '2026-01-01T00:00:00'
  last_upgraded_at:
environment:
  python_version: '3.11'
  platform: test
  platform_version: ''
migrations:
  applied: []
""",
        encoding="utf-8",
    )

    # Create harness directories
    for d in _HARNESS_DIRS:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def full_project(tmp_path: Path) -> Path:
    return _make_full_project(tmp_path)


class TestUpgradeSmoke:
    def test_upgrade_runs_without_errors(self, full_project: Path) -> None:
        """MigrationRunner.upgrade() completes without errors on a full project."""
        runner = MigrationRunner(full_project)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = runner.upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=False)

        assert result.success, f"Upgrade failed with errors: {result.errors}"
        assert result.errors == []

    def test_upgrade_dry_run_runs_without_errors(self, full_project: Path) -> None:
        """MigrationRunner.upgrade(dry_run=True) runs without errors."""
        runner = MigrationRunner(full_project)
        result = runner.upgrade(_TARGET_VERSION, dry_run=True, include_worktrees=False)
        assert result.success, f"Dry-run upgrade failed: {result.errors}"
        assert result.errors == []

    def test_upgrade_is_idempotent(self, full_project: Path) -> None:
        """Running upgrade twice leaves the project in the same healthy state."""
        runner = MigrationRunner(full_project)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result1 = runner.upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=False)
            result2 = runner.upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=False)

        assert result1.success, f"First upgrade failed: {result1.errors}"
        assert result2.success, f"Second upgrade failed: {result2.errors}"

    def test_both_phase_migrations_registered(self) -> None:
        """Both Phase 1 and Phase 2 migration IDs are present in the registry."""
        from specify_cli.upgrade.registry import MigrationRegistry

        ids = {m.migration_id for m in MigrationRegistry.get_all()}
        assert "3_3_0_session_presence_claude_code" in ids
        assert "3_3_0_session_presence_all_harnesses" in ids

    def test_claude_md_written_after_upgrade(self, full_project: Path) -> None:
        """After upgrade, CLAUDE.md contains the orientation section."""
        from specify_cli.session_presence.content import SECTION_OPEN

        runner = MigrationRunner(full_project)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            runner.upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=False)

        claude_md = full_project / ".claude" / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md should have been created by Phase 1"
        assert SECTION_OPEN in claude_md.read_text(encoding="utf-8")

    def test_cursor_rules_written_after_upgrade(self, full_project: Path) -> None:
        """After upgrade, cursor rules file contains the orientation section."""
        from specify_cli.session_presence.content import SECTION_OPEN

        runner = MigrationRunner(full_project)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            runner.upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=False)

        rules_file = full_project / ".cursor" / "rules" / "spec-kitty.mdc"
        assert rules_file.exists(), "cursor rules file should have been created"
        assert SECTION_OPEN in rules_file.read_text(encoding="utf-8")
