"""Tests for occurrence classification guardrails (WP05).

Covers:
- apply_text_replacements with and without context_filter
- exclude_paths filter factory
- Template content validation for Bulk Edit Safety and Post-Edit Verification
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.skill_update import (
    apply_text_replacements,
    exclude_paths,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# The software-dev command templates were migrated from
# ``src/specify_cli/missions/<type>/command-templates/`` to the canonical doctrine
# mission-steps structure. The implement step's bulk-edit safety / occurrence
# classification content now lives in the doctrine prompt.
IMPLEMENT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packs"
    / "built-in"
    / "missions"
    / "mission-steps"
    / "software-dev"
    / "implement"
    / "prompt.md"
)


@pytest.fixture()
def sample_file(tmp_path: Path) -> Path:
    """Create a simple skill-root text file for replacement tests."""
    p = tmp_path / ".claude" / "skills" / "demo-skill" / "sample.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("hello world\nfoo bar baz\n", encoding="utf-8")
    return p


@pytest.fixture()
def kittify_file(tmp_path: Path) -> Path:
    """Create a skill-root file inside a .kittify directory."""
    d = tmp_path / ".claude" / "skills" / "demo-skill" / ".kittify"
    d.mkdir(parents=True)
    p = d / "config.yaml"
    p.write_text("old_term: value\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# T025 — apply_text_replacements with context_filter
# ---------------------------------------------------------------------------


class TestApplyTextReplacementsNoFilter:
    """Existing behaviour is preserved when context_filter is not provided."""

    def test_replaces_text(self, sample_file: Path) -> None:
        result = apply_text_replacements(
            sample_file, [("hello", "goodbye")]
        )
        assert result is True
        assert "goodbye world" in sample_file.read_text(encoding="utf-8")

    def test_returns_false_when_no_match(self, sample_file: Path) -> None:
        result = apply_text_replacements(
            sample_file, [("nonexistent", "replacement")]
        )
        assert result is False

    def test_multiple_replacements(self, sample_file: Path) -> None:
        result = apply_text_replacements(
            sample_file,
            [("hello", "goodbye"), ("foo", "qux")],
        )
        assert result is True
        content = sample_file.read_text(encoding="utf-8")
        assert "goodbye world" in content
        assert "qux bar baz" in content

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / ".claude" / "skills" / "demo-skill" / "does_not_exist.txt"
        result = apply_text_replacements(missing, [("a", "b")])
        assert result is False

    def test_rejects_non_skill_root_path(self, tmp_path: Path) -> None:
        other = tmp_path / "outside.txt"
        other.write_text("hello world\n", encoding="utf-8")

        result = apply_text_replacements(other, [("hello", "goodbye")])

        assert result is False
        assert other.read_text(encoding="utf-8") == "hello world\n"


class TestApplyTextReplacementsWithFilter:
    """context_filter gates file processing."""

    def test_filter_accepts(self, sample_file: Path) -> None:
        result = apply_text_replacements(
            sample_file,
            [("hello", "goodbye")],
            context_filter=lambda _: True,
        )
        assert result is True
        assert "goodbye" in sample_file.read_text(encoding="utf-8")

    def test_filter_rejects(self, sample_file: Path) -> None:
        original = sample_file.read_text(encoding="utf-8")
        result = apply_text_replacements(
            sample_file,
            [("hello", "goodbye")],
            context_filter=lambda _: False,
        )
        assert result is False
        assert sample_file.read_text(encoding="utf-8") == original

    def test_filter_receives_correct_path(self, sample_file: Path) -> None:
        captured: list[Path] = []

        def spy(path: Path) -> bool:
            captured.append(path)
            return True

        apply_text_replacements(
            sample_file, [("hello", "goodbye")], context_filter=spy
        )
        assert captured == [sample_file]

    def test_filter_skips_before_reading(self, tmp_path: Path) -> None:
        """If the filter rejects, the file is never opened (even if missing)."""
        missing = tmp_path / ".claude" / "skills" / "demo-skill" / "no_such_file.txt"
        result = apply_text_replacements(
            missing,
            [("a", "b")],
            context_filter=lambda _: False,
        )
        assert result is False


# ---------------------------------------------------------------------------
# T025 — exclude_paths factory
# ---------------------------------------------------------------------------


class TestExcludePaths:
    """exclude_paths() creates a context_filter for apply_text_replacements."""

    def test_single_pattern_excludes(self, kittify_file: Path) -> None:
        filt = exclude_paths("*.kittify*")
        # .kittify/config.yaml should be excluded
        assert filt(kittify_file) is False

    def test_single_pattern_allows(self, sample_file: Path) -> None:
        filt = exclude_paths("*.kittify*")
        assert filt(sample_file) is True

    def test_multiple_patterns(self, tmp_path: Path) -> None:
        lock = tmp_path / "poetry.lock"
        lock.write_text("content", encoding="utf-8")
        config = tmp_path / ".kittify" / "c.yaml"
        config.parent.mkdir(exist_ok=True)
        config.write_text("content", encoding="utf-8")
        normal = tmp_path / "src" / "main.py"
        normal.parent.mkdir(exist_ok=True)
        normal.write_text("content", encoding="utf-8")

        filt = exclude_paths("*.lock", "*.kittify*")
        assert filt(lock) is False
        assert filt(config) is False
        assert filt(normal) is True

    def test_no_patterns_allows_all(self, sample_file: Path) -> None:
        filt = exclude_paths()
        assert filt(sample_file) is True

    def test_integration_with_apply(
        self, sample_file: Path, kittify_file: Path
    ) -> None:
        """End-to-end: exclude_paths + apply_text_replacements."""
        filt = exclude_paths("*.kittify*")

        # sample_file is NOT excluded => replacement happens
        r1 = apply_text_replacements(
            sample_file, [("hello", "goodbye")], context_filter=filt
        )
        assert r1 is True

        # kittify_file IS excluded => no replacement
        original = kittify_file.read_text(encoding="utf-8")
        r2 = apply_text_replacements(
            kittify_file, [("old_term", "new_term")], context_filter=filt
        )
        assert r2 is False
        assert kittify_file.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# T023 / T024 — Template content validation
# ---------------------------------------------------------------------------


class TestImplementTemplateContent:
    """Verify the implement template includes required safety sections."""

    @pytest.fixture(autouse=True)
    def _load_template(self) -> None:
        assert IMPLEMENT_TEMPLATE_PATH.is_file(), (
            f"implement.md template not found at {IMPLEMENT_TEMPLATE_PATH}"
        )
        self.content = IMPLEMENT_TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_has_bulk_edit_safety_section(self) -> None:
        assert "## Bulk Edit Safety" in self.content

    def test_has_occurrence_classification_subsection(self) -> None:
        assert "Occurrence Classification" in self.content

    def test_has_category_table(self) -> None:
        """The 12 occurrence categories from the spec must be present."""
        categories = [
            "import_path",
            "class_name",
            "function_name",
            "variable",
            "dict_key",
            "file_path",
            "config_value",
            "log_message",
            "comment",
            "documentation",
            "test_fixture",
            "external_ref",
        ]
        for cat in categories:
            assert f"`{cat}`" in self.content, (
                f"Category '{cat}' missing from implement template"
            )

    def test_has_post_edit_verification_subsection(self) -> None:
        assert "Post-Edit" in self.content and "Verification" in self.content

    def test_verification_checks_template_dirs(self) -> None:
        # Command templates moved from src/specify_cli/missions/*/command-templates/
        # to packs/built-in/missions/mission-steps/ (doctrine-to-charter rework).
        assert "packs/built-in/missions/mission-steps/" in self.content
        assert "src/specify_cli/missions/*/command-templates/" not in self.content

    def test_verification_checks_agent_dirs(self) -> None:
        # At least one agent dir must be mentioned
        assert ".claude/commands/" in self.content

    def test_classification_report_mentioned(self) -> None:
        assert "classification report" in self.content

    def test_verification_report_mentioned(self) -> None:
        assert "verification report" in self.content
