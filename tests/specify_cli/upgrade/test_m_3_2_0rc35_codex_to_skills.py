"""Tests for the 3.2.0 Codex-to-Agent-Skills migration.

Covers:
- clean fixture: codex in config, no .codex/prompts/ — skills installed, no errors
- owned_unedited_only fixture: all 11 spec-kitty.*.md deleted, .codex/prompts/ removed
- mixed fixture: spec-kitty files removed, my-own-prompt.md preserved, dir kept
- vibe_only fixture: migration is a no-op (codex not configured)
- Idempotency: running migration twice on mixed produces same state

Fixtures live under tests/specify_cli/upgrade/fixtures/codex_legacy/.

All tests use real filesystem operations against tmp_path copies of the
fixtures.  No mocks for the core migration logic.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.upgrade.migrations.m_3_2_0rc35_codex_to_skills import (
    CodexToSkillsMigration,
    _classify,
)

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "codex_legacy"
_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # repo root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_fixture(fixture_name: str, tmp_path: Path) -> Path:
    """Copy a named fixture tree into a fresh tmp_path subdirectory.

    Templates come from the installed ``specify_cli`` package, not from the
    fixture, so we do not seed any ``src/specify_cli/`` tree into the fixture.
    A real user project never contains the spec-kitty source tree.
    """
    src = _FIXTURES_ROOT / fixture_name
    dest = tmp_path / fixture_name
    shutil.copytree(src, dest)
    return dest


def _skill_path(project: Path, command: str) -> Path:
    return project / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md"


def _manifest_path(project: Path) -> Path:
    return project / ".kittify" / "command-skills-manifest.json"


def _load_manifest_entries(project: Path) -> list[dict]:
    import json  # noqa: PLC0415

    data = json.loads(_manifest_path(project).read_text(encoding="utf-8"))
    return data.get("entries", [])


# ---------------------------------------------------------------------------
# detect() unit tests
# ---------------------------------------------------------------------------


class TestDetect:
    def test_true_when_legacy_files_present(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        assert CodexToSkillsMigration().detect(project) is True

    def test_false_when_no_prompts_dir(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        assert CodexToSkillsMigration().detect(project) is False

    def test_false_when_only_third_party_files(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        (project / ".codex" / "prompts").mkdir(parents=True)
        (project / ".codex" / "prompts" / "my-team.md").write_text("# custom")
        assert CodexToSkillsMigration().detect(project) is False


# ---------------------------------------------------------------------------
# can_apply() unit tests
# ---------------------------------------------------------------------------


class TestCanApply:
    def test_false_when_no_kittify(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        ok, reason = CodexToSkillsMigration().can_apply(empty)
        assert ok is False
        assert ".kittify/" in reason

    def test_true_for_initialized_project(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        ok, reason = CodexToSkillsMigration().can_apply(project)
        assert ok is True
        assert reason == ""


# ---------------------------------------------------------------------------
# _classify() unit tests
# ---------------------------------------------------------------------------


class TestClassify:
    def test_owned_files_classified_correctly(self, tmp_path: Path) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "spec-kitty.specify.md").write_text("# specify")
        (prompts / "spec-kitty.plan.md").write_text("# plan")
        (prompts / "my-team.md").write_text("# custom")

        results = _classify(prompts)
        by_name = {r.path.name: r for r in results}

        assert by_name["spec-kitty.specify.md"].status == "owned_unedited"
        assert by_name["spec-kitty.plan.md"].status == "owned_unedited"
        assert by_name["my-team.md"].status == "third_party"

    def test_non_md_files_ignored(self, tmp_path: Path) -> None:
        prompts = tmp_path / "prompts"
        prompts.mkdir()
        (prompts / "spec-kitty.specify.txt").write_text("not md")
        results = _classify(prompts)
        assert results == []


# ---------------------------------------------------------------------------
# apply() — clean fixture
# ---------------------------------------------------------------------------


class TestApplyClean:
    """codex configured, no .codex/prompts/ — just installs skills."""

    def test_11_skill_files_created(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        result = CodexToSkillsMigration().apply(project)

        assert result.success, f"errors: {result.errors}"
        for cmd in CANONICAL_COMMANDS:
            assert _skill_path(project, cmd).exists(), f"Missing SKILL.md for {cmd}"

    def test_manifest_has_11_entries(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        CodexToSkillsMigration().apply(project)

        entries = _load_manifest_entries(project)
        assert len(entries) == len(CANONICAL_COMMANDS)

    def test_manifest_entries_include_codex(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        CodexToSkillsMigration().apply(project)

        entries = _load_manifest_entries(project)
        for entry in entries:
            agents = entry.get("agents", [])
            assert "codex" in agents, f"codex missing from agents in {entry['path']}"

    def test_no_codex_prompts_dir_created(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)
        CodexToSkillsMigration().apply(project)

        prompts_dir = project / ".codex" / "prompts"
        assert not prompts_dir.exists()


    def test_6155_names_regenerated_skill_in_changes(self, tmp_path: Path) -> None:
        """#6155: a re-run over a drifted, manifest-owned projection regenerates it and names
        the path once in ``changes_made`` instead of regenerating silently."""
        from specify_cli.skills import command_installer
        from specify_cli.tool_surface.repair import REGENERATED_SURFACE_LINE

        project = _copy_fixture("clean", tmp_path)
        command_installer.install(project, "codex")
        drifted = _skill_path(project, "plan")
        drifted.write_bytes(drifted.read_bytes() + b"\n<!-- stale output from another checkout -->\n")
        rel = drifted.relative_to(project).as_posix()

        result = CodexToSkillsMigration().apply(project)

        assert result.success, f"errors: {result.errors}"
        assert result.changes_made.count(REGENERATED_SURFACE_LINE.format(path=rel)) == 1, result.changes_made


# ---------------------------------------------------------------------------
# apply() — owned_unedited_only fixture
# ---------------------------------------------------------------------------


class TestApplyOwnedUnedited:
    """All 11 spec-kitty.*.md present — should all be deleted."""

    def test_prompts_dir_removed_after_migration(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        result = CodexToSkillsMigration().apply(project)

        assert result.success, f"errors: {result.errors}"
        prompts_dir = project / ".codex" / "prompts"
        assert not prompts_dir.exists(), ".codex/prompts/ should be removed (was empty)"

    def test_codex_dir_itself_preserved(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        CodexToSkillsMigration().apply(project)

        codex_dir = project / ".codex"
        assert codex_dir.exists(), ".codex/ itself must never be removed"

    def test_skills_installed(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        CodexToSkillsMigration().apply(project)

        for cmd in CANONICAL_COMMANDS:
            assert _skill_path(project, cmd).exists(), f"Missing SKILL.md for {cmd}"

    def test_no_preservation_notice_on_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        CodexToSkillsMigration().apply(project)

        captured = capsys.readouterr()
        # Third-party preservation notice goes to stderr; with all owned files
        # removed there should be nothing in stderr about preserving files.
        assert "left untouched" not in captured.err


# ---------------------------------------------------------------------------
# apply() — mixed fixture
# ---------------------------------------------------------------------------


class TestApplyMixed:
    """5 spec-kitty files + my-own-prompt.md — spec-kitty files deleted, custom kept."""

    def test_spec_kitty_files_removed(self, tmp_path: Path) -> None:
        project = _copy_fixture("mixed", tmp_path)
        CodexToSkillsMigration().apply(project)

        for cmd in ("analyze", "charter", "checklist", "implement", "plan"):
            legacy = project / ".codex" / "prompts" / f"spec-kitty.{cmd}.md"
            assert not legacy.exists(), f"{legacy.name} should have been removed"

    def test_third_party_file_preserved(self, tmp_path: Path) -> None:
        project = _copy_fixture("mixed", tmp_path)
        CodexToSkillsMigration().apply(project)

        custom = project / ".codex" / "prompts" / "my-own-prompt.md"
        assert custom.exists(), "my-own-prompt.md must not be touched"

    def test_prompts_dir_retained(self, tmp_path: Path) -> None:
        project = _copy_fixture("mixed", tmp_path)
        CodexToSkillsMigration().apply(project)

        prompts_dir = project / ".codex" / "prompts"
        assert prompts_dir.exists(), ".codex/prompts/ should be kept (not empty)"

    def test_skills_installed(self, tmp_path: Path) -> None:
        project = _copy_fixture("mixed", tmp_path)
        CodexToSkillsMigration().apply(project)

        for cmd in CANONICAL_COMMANDS:
            assert _skill_path(project, cmd).exists()

    def test_preservation_notice_in_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        project = _copy_fixture("mixed", tmp_path)
        CodexToSkillsMigration().apply(project)

        captured = capsys.readouterr()
        assert "my-own-prompt.md" in captured.err or "left untouched" in captured.err


# ---------------------------------------------------------------------------
# apply() — vibe_only fixture
# ---------------------------------------------------------------------------


class TestApplyVibeOnly:
    """codex absent from agents.available — migration must be a no-op."""

    def test_no_op_when_codex_not_configured(self, tmp_path: Path) -> None:
        project = _copy_fixture("vibe_only", tmp_path)
        result = CodexToSkillsMigration().apply(project)

        assert result.success
        # No skills installed
        skills_root = project / ".agents" / "skills"
        assert not skills_root.exists(), ".agents/skills/ must not be created"

    def test_manifest_unchanged(self, tmp_path: Path) -> None:
        project = _copy_fixture("vibe_only", tmp_path)
        CodexToSkillsMigration().apply(project)

        assert not _manifest_path(project).exists(), "manifest must not be created"

    def test_no_changes_reported(self, tmp_path: Path) -> None:
        project = _copy_fixture("vibe_only", tmp_path)
        result = CodexToSkillsMigration().apply(project)

        assert result.changes_made == []


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Running the migration twice on mixed produces identical state."""

    def test_second_run_is_no_op(self, tmp_path: Path) -> None:
        project = _copy_fixture("mixed", tmp_path)

        # First run
        result1 = CodexToSkillsMigration().apply(project)
        assert result1.success

        # Snapshot state after first run
        skills_files_1 = sorted(
            str(p.relative_to(project))
            for p in (project / ".agents" / "skills").rglob("SKILL.md")
        )
        custom_present_1 = (
            project / ".codex" / "prompts" / "my-own-prompt.md"
        ).exists()
        manifest_bytes_1 = _manifest_path(project).read_bytes()

        # Second run
        result2 = CodexToSkillsMigration().apply(project)
        assert result2.success

        # State must be identical
        skills_files_2 = sorted(
            str(p.relative_to(project))
            for p in (project / ".agents" / "skills").rglob("SKILL.md")
        )
        custom_present_2 = (
            project / ".codex" / "prompts" / "my-own-prompt.md"
        ).exists()
        manifest_bytes_2 = _manifest_path(project).read_bytes()

        assert skills_files_1 == skills_files_2
        assert custom_present_1 == custom_present_2
        assert manifest_bytes_1 == manifest_bytes_2

    def test_idempotent_on_clean_fixture(self, tmp_path: Path) -> None:
        project = _copy_fixture("clean", tmp_path)

        result1 = CodexToSkillsMigration().apply(project)
        assert result1.success

        manifest_bytes_1 = _manifest_path(project).read_bytes()

        result2 = CodexToSkillsMigration().apply(project)
        assert result2.success

        manifest_bytes_2 = _manifest_path(project).read_bytes()
        assert manifest_bytes_1 == manifest_bytes_2


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        result = CodexToSkillsMigration().apply(project, dry_run=True)

        assert result.success
        # No SKILL.md files written
        skills_root = project / ".agents" / "skills"
        assert not skills_root.exists()
        # Legacy files still present
        prompts_dir = project / ".codex" / "prompts"
        assert prompts_dir.exists()
        assert any(prompts_dir.iterdir())

    def test_dry_run_reports_expected_changes(self, tmp_path: Path) -> None:
        project = _copy_fixture("owned_unedited_only", tmp_path)
        result = CodexToSkillsMigration().apply(project, dry_run=True)

        assert any("Would install" in c for c in result.changes_made)
        assert any("Would delete" in c for c in result.changes_made)
