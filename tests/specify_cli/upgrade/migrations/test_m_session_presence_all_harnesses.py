"""T029 — Tests for SessionPresenceAllHarnessesMigration (Phase 2).

Covers detect/apply/dry_run/idempotency, runs_on_worktrees, registry
registration, and the forward-compatibility monkey-patch scenario (C2).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Force import of both migration modules so their @register decorators fire.
import specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code  # noqa: F401
import specify_cli.upgrade.migrations.m_3_3_0_session_presence_all_harnesses  # noqa: F401
from specify_cli.upgrade.migrations.m_3_3_0_session_presence_all_harnesses import (
    SessionPresenceAllHarnessesMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.session_presence.content import SECTION_OPEN

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Project factory helpers
# ---------------------------------------------------------------------------


def _make_project(
    tmp_path: Path,
    agents: list[str] | None = None,
    agent_dirs: list[str] | None = None,
) -> Path:
    """Create a minimal spec-kitty project.

    Parameters
    ----------
    agents:
        Agent keys to include in config.yaml ``available`` list.
    agent_dirs:
        Additional directories to create under ``tmp_path`` (e.g. ``".cursor"``).
    """
    (tmp_path / ".kittify").mkdir()
    avail = agents or []
    lines = (
        "agents:\n  available:\n" + "".join(f"    - {a}\n" for a in avail)
        if avail
        else "agents:\n  available: []\n"
    )
    (tmp_path / ".kittify" / "config.yaml").write_text(lines, encoding="utf-8")
    for d in agent_dirs or []:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cursor_project(tmp_path: Path) -> Path:
    """A project with cursor configured and .cursor/ present."""
    return _make_project(tmp_path, agents=["cursor"], agent_dirs=[".cursor"])


@pytest.fixture
def multi_harness_project(tmp_path: Path) -> Path:
    """A project with cursor + gemini configured, both harness dirs present."""
    return _make_project(
        tmp_path,
        agents=["cursor", "gemini"],
        agent_dirs=[".cursor", ".gemini"],
    )


# ---------------------------------------------------------------------------
# TestDetect
# ---------------------------------------------------------------------------


class TestDetect:
    def test_false_for_project_without_kittify(self, tmp_path: Path) -> None:
        migration = SessionPresenceAllHarnessesMigration()
        assert migration.detect(tmp_path) is False

    def test_true_for_always_writable_harnesses_without_harness_dir(
        self, tmp_path: Path
    ) -> None:
        """detect() is True for always-writable harnesses even when no harness dirs exist.

        AgentsMdWriter (codex, opencode, antigravity) and SkillsPreambleWriter
        (pi, vibe, letta) always return ``can_write=True``.  This test confirms
        detect() is True when these agents are configured but not yet written,
        and False once presence has been written for all of them.

        C-005: only agents listed in config.yaml are processed; the empty-config
        case (no agents configured) must return False from detect().
        """
        # Empty config — no agents configured → detect() must return False
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        empty_project = _make_project(empty_dir)
        migration = SessionPresenceAllHarnessesMigration()
        assert migration.detect(empty_project) is False

        # With always-writable agents configured → detect() must return True
        agents_dir = tmp_path / "with_agents"
        agents_dir.mkdir()
        project = _make_project(agents_dir, agents=["codex", "opencode"])
        assert migration.detect(project) is True

        # Write all pending harnesses
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
            migration.apply(project)

        # Now detect() must be False
        assert migration.detect(project) is False

    def test_true_when_harness_dir_present_but_no_presence(
        self, cursor_project: Path
    ) -> None:
        """detect() is True when cursor dir exists but presence is missing."""
        migration = SessionPresenceAllHarnessesMigration()
        assert migration.detect(cursor_project) is True

    def test_false_when_all_presence_written(self, cursor_project: Path) -> None:
        """detect() is False only when every writable harness has presence."""
        migration = SessionPresenceAllHarnessesMigration()
        # Write all pending harnesses
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
            migration.apply(cursor_project)

        assert migration.detect(cursor_project) is False

    def test_true_when_second_harness_still_missing(
        self, multi_harness_project: Path
    ) -> None:
        """detect() remains True when only one of two harnesses is written."""
        # Write cursor presence, leave gemini absent
        rules_file = multi_harness_project / ".cursor" / "rules" / "spec-kitty.mdc"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        rules_file.write_text(f"{SECTION_OPEN}\nblock\n", encoding="utf-8")
        migration = SessionPresenceAllHarnessesMigration()
        assert migration.detect(multi_harness_project) is True


# ---------------------------------------------------------------------------
# TestApply
# ---------------------------------------------------------------------------


class TestApply:
    def _apply(self, project_path: Path) -> None:
        """Run apply() with patched heavy dependencies."""
        migration = SessionPresenceAllHarnessesMigration()
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
            migration.apply(project_path)

    def test_apply_writes_orientation_for_cursor(
        self, cursor_project: Path
    ) -> None:
        self._apply(cursor_project)
        rules_file = cursor_project / ".cursor" / "rules" / "spec-kitty.mdc"
        assert rules_file.exists()
        assert SECTION_OPEN in rules_file.read_text(encoding="utf-8")

    def test_apply_returns_success_result(self, cursor_project: Path) -> None:
        migration = SessionPresenceAllHarnessesMigration()
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
            result = migration.apply(cursor_project)
        assert result.success
        assert len(result.changes_made) >= 1

    def test_apply_dry_run_no_filesystem_changes(
        self, cursor_project: Path
    ) -> None:
        """apply(dry_run=True) reports pending changes but writes nothing."""
        migration = SessionPresenceAllHarnessesMigration()
        result = migration.apply(cursor_project, dry_run=True)
        assert result.success
        # The rules file must not have been created
        rules_file = cursor_project / ".cursor" / "rules" / "spec-kitty.mdc"
        assert not rules_file.exists()
        # But at least one change should be described
        assert len(result.changes_made) >= 1

    def test_apply_dry_run_changes_describe_pending_harness(
        self, cursor_project: Path
    ) -> None:
        migration = SessionPresenceAllHarnessesMigration()
        result = migration.apply(cursor_project, dry_run=True)
        assert any("cursor" in change for change in result.changes_made)

    def test_apply_idempotent(self, cursor_project: Path) -> None:
        """apply() twice does not duplicate the section."""
        self._apply(cursor_project)
        self._apply(cursor_project)
        rules_file = cursor_project / ".cursor" / "rules" / "spec-kitty.mdc"
        text = rules_file.read_text(encoding="utf-8")
        assert text.count(SECTION_OPEN) == 1

    def test_apply_skips_claude_harness(self, tmp_path: Path) -> None:
        """apply() never writes to the Claude harness (handled by Phase 1)."""
        _make_project(tmp_path, agent_dirs=[".claude"])
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "agents:\n  available:\n    - claude\n", encoding="utf-8"
        )
        # Run apply — claude entries should not be processed
        migration = SessionPresenceAllHarnessesMigration()
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
            result = migration.apply(tmp_path)
        # No changes should have been made for claude
        assert all("claude" not in change for change in result.changes_made)

    def test_apply_noop_when_nothing_pending(self, tmp_path: Path) -> None:
        """apply() returns empty changes_made when all presence is already written."""
        project = _make_project(tmp_path)
        migration = SessionPresenceAllHarnessesMigration()
        # First call writes everything
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
            migration.apply(project)
            # Second call: nothing pending
            result = migration.apply(project)
        assert result.success
        assert result.changes_made == []

    def test_apply_writes_multiple_harnesses(
        self, multi_harness_project: Path
    ) -> None:
        """apply() writes orientation for all pending harnesses in one pass."""
        self._apply(multi_harness_project)
        cursor_file = (
            multi_harness_project / ".cursor" / "rules" / "spec-kitty.mdc"
        )
        gemini_file = multi_harness_project / "GEMINI.md"
        assert SECTION_OPEN in cursor_file.read_text(encoding="utf-8")
        assert SECTION_OPEN in gemini_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TestMigrationAttributes
# ---------------------------------------------------------------------------


class TestMigrationAttributes:
    def test_runs_on_worktrees_is_false(self) -> None:
        assert SessionPresenceAllHarnessesMigration.runs_on_worktrees is False

    def test_migration_registered_in_registry(self) -> None:
        migration_ids = {m.migration_id for m in MigrationRegistry.get_all()}
        assert "3_3_0_session_presence_all_harnesses" in migration_ids

    def test_migration_id_distinct_from_phase1(self) -> None:
        migration_ids = {m.migration_id for m in MigrationRegistry.get_all()}
        assert "3_3_0_session_presence_claude_code" in migration_ids
        assert "3_3_0_session_presence_all_harnesses" in migration_ids


# ---------------------------------------------------------------------------
# TestForwardCompatibility (analysis finding C2)
# ---------------------------------------------------------------------------


class TestForwardCompatibility:
    def test_detect_true_when_qwen_monkey_patched_with_markdown_rules_writer(
        self, tmp_path: Path
    ) -> None:
        """C2: monkey-patching WRITER_REGISTRY["qwen"] with a real MarkdownRulesWriter
        causes detect() to return True for a project where qwen's target dir exists
        but orientation is absent.

        This verifies that the migration correctly picks up new writers added to the
        registry without code changes — forward-compatibility guarantee.
        """
        from specify_cli.session_presence.writers.registry import WRITER_REGISTRY
        from specify_cli.session_presence.writers.markdown_rules import (
            MarkdownRulesWriter,
        )

        # Set up a project that looks like it has a qwen install (create .qwen/)
        _make_project(tmp_path, agents=["qwen"], agent_dirs=[".qwen"])

        # Replace the NullWriter with a real MarkdownRulesWriter
        real_qwen_writer = MarkdownRulesWriter(
            harness_key="qwen",
            rules_path=".qwen/rules/spec-kitty.md",
            append_mode=False,
            check_dir=".qwen",
        )
        original_writer = WRITER_REGISTRY["qwen"]
        WRITER_REGISTRY["qwen"] = real_qwen_writer
        try:
            migration = SessionPresenceAllHarnessesMigration()
            # .qwen/ exists + no spec-kitty.md → detect() must return True
            assert migration.detect(tmp_path) is True
        finally:
            WRITER_REGISTRY["qwen"] = original_writer
