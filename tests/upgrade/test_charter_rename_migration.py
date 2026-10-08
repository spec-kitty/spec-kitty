"""Tests for the comprehensive charter-rename migration (m_3_1_1_charter_rename).

Covers:
- T042: Layout A, B, C migrations
- T043: Content rewriting + agent prompt command rewrite
- T044: Metadata normalization
- T045: Idempotency + partial state recovery
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_1_1_charter_rename import (
    CharterRenameMigration,
)

pytestmark = pytest.mark.fast


@pytest.fixture
def migration() -> CharterRenameMigration:
    """Create migration instance."""
    return CharterRenameMigration()


# ── T042: Layout A, B, C migrations ────────────────────────────────────────


class TestLayoutA:
    """Layout A: modern .kittify/constitution/ directory renamed to .kittify/charter/."""

    def test_layout_a_detect(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """detect() returns True when .kittify/constitution/ exists."""
        const_dir = tmp_path / ".kittify" / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Project Charter")
        assert migration.detect(tmp_path) is True

    def test_layout_a_migration(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Modern .kittify/constitution/ directory is renamed to .kittify/charter/."""
        kittify = tmp_path / ".kittify"
        const_dir = kittify / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Project Charter")
        (const_dir / "governance.yaml").write_text("testing: {}")
        (const_dir / "references.yaml").write_text(
            'source_path: ".kittify/constitution/interview/answers.yaml"'
        )

        result = migration.apply(tmp_path)

        assert result.success
        assert not const_dir.exists()
        charter_dir = kittify / "charter"
        assert (charter_dir / "charter.md").exists()
        assert (charter_dir / "governance.yaml").exists()
        assert (charter_dir / "references.yaml").exists()

    def test_layout_a_renames_constitution_md(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """constitution.md inside the renamed dir becomes charter.md."""
        const_dir = tmp_path / ".kittify" / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Project Charter")

        migration.apply(tmp_path)

        charter_dir = tmp_path / ".kittify" / "charter"
        assert (charter_dir / "charter.md").exists()
        assert not (charter_dir / "constitution.md").exists()


class TestLayoutB:
    """Layout B: legacy .kittify/memory/constitution.md moved to .kittify/charter/."""

    def test_layout_b_detect(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """detect() returns True when .kittify/memory/constitution.md exists."""
        memory_dir = tmp_path / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "constitution.md").write_text("# Charter")
        assert migration.detect(tmp_path) is True

    def test_layout_b_migration(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Legacy .kittify/memory/constitution.md is moved to .kittify/charter/charter.md."""
        memory_dir = tmp_path / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "constitution.md").write_text("# Charter")

        result = migration.apply(tmp_path)

        assert result.success
        assert not (memory_dir / "constitution.md").exists()
        assert (tmp_path / ".kittify" / "charter" / "charter.md").exists()


class TestLayoutC:
    """Layout C: pre-0.10.12 mission-specific constitutions are removed."""

    def test_layout_c_detect(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """detect() returns True when mission-specific constitution dir exists."""
        missions = tmp_path / ".kittify" / "missions"
        (missions / "software-dev" / "constitution").mkdir(parents=True)
        (missions / "software-dev" / "constitution" / "local.md").write_text("old")
        assert migration.detect(tmp_path) is True

    def test_layout_c_migration(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Pre-0.10.12 mission-specific constitutions are removed."""
        missions = tmp_path / ".kittify" / "missions"
        (missions / "software-dev" / "constitution").mkdir(parents=True)
        (missions / "software-dev" / "constitution" / "local.md").write_text("old")

        result = migration.apply(tmp_path)

        assert result.success
        assert not (missions / "software-dev" / "constitution").exists()

    def test_layout_c_multiple_missions(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Multiple mission-specific constitution dirs are all removed."""
        missions = tmp_path / ".kittify" / "missions"
        for m in ("software-dev", "research", "documentation"):
            (missions / m / "constitution").mkdir(parents=True)
            (missions / m / "constitution" / "local.md").write_text(f"old-{m}")

        result = migration.apply(tmp_path)

        assert result.success
        for m in ("software-dev", "research", "documentation"):
            assert not (missions / m / "constitution").exists()


# ── T043: Content rewriting + agent prompt tests ───────────────────────────


class TestContentRewriting:
    """Content rewriting replaces constitution references in generated files."""

    def test_content_rewriting_charter_md(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Generated charter.md has embedded constitution references rewritten."""
        charter_dir = tmp_path / ".kittify" / "constitution"
        charter_dir.mkdir(parents=True)
        (charter_dir / "constitution.md").write_text(
            "# Project Constitution\n<!-- Generated by spec-kitty constitution generate -->"
        )

        result = migration.apply(tmp_path)

        assert result.success
        content = (tmp_path / ".kittify" / "charter" / "charter.md").read_text()
        assert "constitution" not in content.lower()
        assert "Charter" in content

    def test_content_rewriting_references_yaml(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """references.yaml paths are rewritten from constitution to charter."""
        charter_dir = tmp_path / ".kittify" / "constitution"
        charter_dir.mkdir(parents=True)
        (charter_dir / "constitution.md").write_text("# Charter")
        (charter_dir / "references.yaml").write_text(
            'source_path: ".kittify/constitution/interview/answers.yaml"'
        )

        result = migration.apply(tmp_path)

        assert result.success
        refs = (tmp_path / ".kittify" / "charter" / "references.yaml").read_text()
        assert "constitution" not in refs.lower()
        assert "charter" in refs

    def test_content_rewriting_case_preserving(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Replacement is case-preserving: Constitution -> Charter, constitution -> charter."""
        charter_dir = tmp_path / ".kittify" / "constitution"
        charter_dir.mkdir(parents=True)
        (charter_dir / "constitution.md").write_text(
            "The Constitution defines rules.\nEach constitution section is important."
        )

        migration.apply(tmp_path)

        content = (tmp_path / ".kittify" / "charter" / "charter.md").read_text()
        assert "The Charter defines rules." in content
        assert "Each charter section is important." in content

    def test_agent_prompt_command_rewrite(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Agent prompts have constitution command references updated."""
        # Setup: create agent prompt with old command
        claude_dir = tmp_path / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        (claude_dir / "spec-kitty.specify.md").write_text(
            "Run: spec-kitty constitution context --action specify --json"
        )
        # Also create constitution dir so migration detects work
        (tmp_path / ".kittify" / "constitution").mkdir(parents=True)
        (tmp_path / ".kittify" / "constitution" / "constitution.md").write_text("test")
        # Need agent config for the migration to find claude
        config_dir = tmp_path / ".kittify"
        (config_dir / "config.yaml").write_text(
            "agents:\n  available:\n    - claude\n"
        )

        result = migration.apply(tmp_path)

        assert result.success
        prompt = (claude_dir / "spec-kitty.specify.md").read_text()
        assert "constitution" not in prompt.lower()
        assert "charter" in prompt

    def test_agent_command_file_renamed(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """spec-kitty.constitution.md is renamed to spec-kitty.charter.md."""
        claude_dir = tmp_path / ".claude" / "commands"
        claude_dir.mkdir(parents=True)
        (claude_dir / "spec-kitty.constitution.md").write_text(
            "Run the constitution workflow"
        )
        (tmp_path / ".kittify" / "config.yaml").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "agents:\n  available:\n    - claude\n"
        )

        result = migration.apply(tmp_path)

        assert result.success
        assert not (claude_dir / "spec-kitty.constitution.md").exists()
        assert (claude_dir / "spec-kitty.charter.md").exists()
        content = (claude_dir / "spec-kitty.charter.md").read_text()
        assert "constitution" not in content.lower()

    def test_skill_directory_left_alone(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """A spec-kitty-constitution-doctrine skill dir is left untouched.

        Its charter-era name spec-kitty-charter-doctrine is retired by the
        charter-pack cutover, so the rename must never recreate it.
        """
        skills_dir = tmp_path / ".claude" / "skills"
        old_skill = skills_dir / "spec-kitty-constitution-doctrine"
        old_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("Constitution doctrine skill")
        (tmp_path / ".kittify" / "config.yaml").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "agents:\n  available:\n    - claude\n"
        )

        assert migration.detect(tmp_path) is False, "a skill dir alone is not constitution-era state to migrate"
        result = migration.apply(tmp_path)

        assert result.success
        assert (old_skill / "SKILL.md").read_text() == "Constitution doctrine skill"
        assert not (skills_dir / "spec-kitty-charter-doctrine").exists()
        assert not any("skills" in change for change in result.changes_made), result.changes_made


# ── T044: Metadata normalization tests ─────────────────────────────────────


class TestMetadataNormalization:
    """Test that old migration IDs in metadata are rewritten to charter-era IDs."""

    def _write_metadata(self, kittify: Path, migration_ids: list[str]) -> None:
        """Helper: write a metadata.yaml with the given migration IDs."""
        kittify.mkdir(parents=True, exist_ok=True)
        migrations_yaml = "\n".join(
            f'    - id: "{mid}"\n      applied_at: "2026-01-01T00:00:00"\n      result: "success"'
            for mid in migration_ids
        )
        (kittify / "metadata.yaml").write_text(
            f"""spec_kitty:
  version: 3.1.0a0
  initialized_at: "2026-01-01T00:00:00"
migrations:
  applied:
{migrations_yaml}
"""
        )

    def test_metadata_normalization_rewrites_old_ids(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Old constitution-era migration IDs are rewritten to charter-era IDs."""
        kittify = tmp_path / ".kittify"
        # Create constitution dir so migration detects + applies
        const_dir = kittify / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Charter")

        self._write_metadata(kittify, [
            "0.10.12_constitution_cleanup",
            "2.0.0_constitution_directory",
        ])

        result = migration.apply(tmp_path)
        assert result.success

        # Verify normalized in changes
        assert any("metadata" in c.lower() for c in result.changes_made)

    def test_metadata_normalization_noop_when_already_charter(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """No metadata changes when IDs are already charter-era."""
        kittify = tmp_path / ".kittify"
        # Create constitution dir so migration detects
        const_dir = kittify / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Charter")

        self._write_metadata(kittify, [
            "0.10.12_charter_cleanup",
            "2.0.0_charter_directory",
        ])

        result = migration.apply(tmp_path)
        assert result.success

        # No metadata normalization change should be reported
        metadata_changes = [c for c in result.changes_made if "metadata" in c.lower() and "migration" in c.lower()]
        assert len(metadata_changes) == 0

    def test_metadata_normalization_no_metadata_file(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Migration handles missing metadata.yaml gracefully."""
        const_dir = tmp_path / ".kittify" / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Charter")

        result = migration.apply(tmp_path)
        assert result.success


# ── T045: Idempotency + partial state recovery ────────────────────────────


class TestIdempotency:
    """Test that running the migration twice produces the same result."""

    def test_idempotency(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Running migration twice: second detect() returns False."""
        const_dir = tmp_path / ".kittify" / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Project Charter")

        result1 = migration.apply(tmp_path)
        assert result1.success

        # Second run: detect should return False
        assert migration.detect(tmp_path) is False

    def test_idempotency_layout_b(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Layout B: second detect() returns False after migration."""
        memory_dir = tmp_path / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "constitution.md").write_text("# Charter")

        result = migration.apply(tmp_path)
        assert result.success

        assert migration.detect(tmp_path) is False


class TestPartialState:
    """Test edge cases with partial/mixed state."""

    def test_partial_state_both_exist(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Both constitution/ and charter/ exist: merge and cleanup."""
        kittify = tmp_path / ".kittify"
        (kittify / "constitution").mkdir(parents=True)
        (kittify / "constitution" / "constitution.md").write_text("old")
        (kittify / "constitution" / "extra.yaml").write_text("extra")
        (kittify / "charter").mkdir(parents=True)
        (kittify / "charter" / "charter.md").write_text("new")

        result = migration.apply(tmp_path)

        assert result.success
        assert not (kittify / "constitution").exists()
        # charter.md preserved (not overwritten)
        assert (kittify / "charter" / "charter.md").read_text() == "new"
        # extra.yaml merged
        assert (kittify / "charter" / "extra.yaml").exists()

    def test_no_constitution_state(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Fresh project with no constitution state: detect returns False."""
        (tmp_path / ".kittify").mkdir()
        assert migration.detect(tmp_path) is False

    def test_stale_memory_file_removed(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """Memory/constitution.md removed when charter/charter.md already exists."""
        kittify = tmp_path / ".kittify"
        (kittify / "memory").mkdir(parents=True)
        (kittify / "memory" / "constitution.md").write_text("stale")
        (kittify / "charter").mkdir(parents=True)
        (kittify / "charter" / "charter.md").write_text("current")

        result = migration.apply(tmp_path)

        assert result.success
        assert not (kittify / "memory" / "constitution.md").exists()
        assert (kittify / "charter" / "charter.md").read_text() == "current"

    def test_no_kittify_dir(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """No .kittify directory at all: detect returns False."""
        assert migration.detect(tmp_path) is False

    def test_all_three_layouts_combined(
        self, tmp_path: Path, migration: CharterRenameMigration
    ) -> None:
        """All three layouts present: migration handles all of them."""
        kittify = tmp_path / ".kittify"

        # Layout A
        const_dir = kittify / "constitution"
        const_dir.mkdir(parents=True)
        (const_dir / "constitution.md").write_text("# Layout A charter")
        (const_dir / "governance.yaml").write_text("test: true")

        # Layout B
        memory_dir = kittify / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "constitution.md").write_text("# Layout B charter")

        # Layout C
        missions = kittify / "missions"
        (missions / "software-dev" / "constitution").mkdir(parents=True)
        (missions / "software-dev" / "constitution" / "local.md").write_text("old")

        result = migration.apply(tmp_path)

        assert result.success
        # Layout C cleaned
        assert not (missions / "software-dev" / "constitution").exists()
        # Layout B stale file removed (Layout A creates charter/ first)
        assert not (memory_dir / "constitution.md").exists()
        # Layout A renamed
        assert not const_dir.exists()
        # charter dir has merged content
        charter_dir = kittify / "charter"
        assert charter_dir.exists()
        assert (charter_dir / "charter.md").exists()

    def test_migration_metadata_attributes(self, migration: CharterRenameMigration) -> None:
        """Migration has correct ID and version attributes."""
        assert migration.migration_id == "3.1.1_charter_rename"
        assert migration.target_version == "3.1.1"
        assert "charter" in migration.description.lower()
