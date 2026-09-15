"""T027 — Tests for AgentsMdWriter, registry completeness, and check_dir refinement.

Covers:
- AgentsMdWriter functional behaviour (can_write, has_presence, write, remove)
- Registry completeness: all 17 expected harness keys present (roo removed 2026-05-15; llxprt added)
- Pattern B harness registry spot-checks
- check_dir refinement to MarkdownRulesWriter.can_write()
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN, SessionPresenceContent
from specify_cli.session_presence.writers.agents_md import AgentsMdWriter
from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
from specify_cli.session_presence.writers.null_writer import NullWriter
from specify_cli.session_presence.writers.registry import WRITER_REGISTRY, get_writer
from specify_cli.session_presence.writers.skills_preamble import SkillsPreambleWriter

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_REGISTRY_KEYS = frozenset({
    # Pattern A
    "claude",
    # Pattern B — "roo" removed (Roo Code shut down 2026-05-15, C-007)
    "cursor", "windsurf", "copilot", "kiro", "gemini", "llxprt",
    # Pattern C
    "codex", "opencode", "antigravity",
    # Pattern D
    "pi", "vibe", "letta",
    # Pattern E
    "qwen", "kilocode", "auggie", "q",
})


def _make_content(
    version: str = "3.2.0",
    slug: str = "test-project",
    health: str = "healthy",
    available: str | None = None,
) -> SessionPresenceContent:
    return SessionPresenceContent(version, slug, health, available)


def _agents_md_writer(harness_key: str = "codex") -> AgentsMdWriter:
    return AgentsMdWriter(harness_key)


# ---------------------------------------------------------------------------
# AgentsMdWriter — can_write
# ---------------------------------------------------------------------------

class TestAgentsMdWriterCanWrite:
    def test_can_write_always_true_when_dir_missing(self, tmp_path: Path) -> None:
        """can_write() returns True even when AGENTS.md's parent doesn't exist."""
        # tmp_path is a fresh dir with nothing in it
        writer = _agents_md_writer()
        assert writer.can_write(tmp_path) is True

    def test_can_write_true_when_agents_md_present(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
        writer = _agents_md_writer()
        assert writer.can_write(tmp_path) is True

    def test_can_write_true_for_empty_dir(self, tmp_path: Path) -> None:
        # Even a completely empty project root should allow writing
        assert _agents_md_writer().can_write(tmp_path) is True


# ---------------------------------------------------------------------------
# AgentsMdWriter — has_presence
# ---------------------------------------------------------------------------

class TestAgentsMdWriterHasPresence:
    def test_false_when_agents_md_absent(self, tmp_path: Path) -> None:
        assert _agents_md_writer().has_presence(tmp_path) is False

    def test_false_when_agents_md_exists_no_section(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# No spec-kitty section\n", encoding="utf-8")
        assert _agents_md_writer().has_presence(tmp_path) is False

    def test_true_when_section_present(self, tmp_path: Path) -> None:
        writer = _agents_md_writer()
        writer.write(tmp_path, _make_content())
        assert writer.has_presence(tmp_path) is True


# ---------------------------------------------------------------------------
# AgentsMdWriter — write
# ---------------------------------------------------------------------------

class TestAgentsMdWriterWrite:
    def test_first_write_creates_agents_md(self, tmp_path: Path) -> None:
        writer = _agents_md_writer()
        writer.write(tmp_path, _make_content())
        target = tmp_path / "AGENTS.md"
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert SECTION_OPEN in text
        assert SECTION_CLOSE in text

    def test_second_write_replaces_section_no_duplicate(self, tmp_path: Path) -> None:
        writer = _agents_md_writer()
        writer.write(tmp_path, _make_content())
        writer.write(tmp_path, _make_content(version="3.3.0"))
        text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert text.count(SECTION_OPEN) == 1
        assert "3.3.0" in text

    def test_write_preserves_existing_agents_md_content(self, tmp_path: Path) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("# Existing AGENTS.md from other tools\n", encoding="utf-8")
        writer = _agents_md_writer()
        writer.write(tmp_path, _make_content())
        text = target.read_text(encoding="utf-8")
        assert "# Existing AGENTS.md from other tools" in text
        assert SECTION_OPEN in text


# ---------------------------------------------------------------------------
# AgentsMdWriter — remove
# ---------------------------------------------------------------------------

class TestAgentsMdWriterRemove:
    def test_remove_strips_section_leaves_other_content(self, tmp_path: Path) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("# Before\n\n# After\n", encoding="utf-8")
        writer = _agents_md_writer()
        writer.write(tmp_path, _make_content())
        writer.remove(tmp_path)
        text = target.read_text(encoding="utf-8")
        assert SECTION_OPEN not in text
        assert SECTION_CLOSE not in text
        assert "# Before" in text

    def test_remove_noop_when_section_absent(self, tmp_path: Path) -> None:
        target = tmp_path / "AGENTS.md"
        original = "# No section here\n"
        target.write_text(original, encoding="utf-8")
        _agents_md_writer().remove(tmp_path)  # Must not raise
        assert target.read_text(encoding="utf-8") == original

    def test_remove_noop_when_file_absent(self, tmp_path: Path) -> None:
        _agents_md_writer().remove(tmp_path)  # Must not raise


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    def test_all_expected_keys_present(self) -> None:
        """WRITER_REGISTRY must cover all 17 harness keys — no silent gaps."""
        missing = EXPECTED_REGISTRY_KEYS - set(WRITER_REGISTRY.keys())
        assert not missing, f"Registry is missing keys: {sorted(missing)}"

    def test_registry_has_no_extra_unexpected_keys(self) -> None:
        """No undocumented keys should creep into the registry."""
        extra = set(WRITER_REGISTRY.keys()) - EXPECTED_REGISTRY_KEYS
        assert not extra, f"Registry has unexpected keys: {sorted(extra)}"

    def test_get_writer_unknown_key_returns_null_writer(self) -> None:
        result = get_writer("definitely_not_a_harness")
        assert isinstance(result, NullWriter)


# ---------------------------------------------------------------------------
# Pattern B spot-checks via get_writer
# ---------------------------------------------------------------------------

class TestPatternBRegistry:
    def test_cursor_rules_path(self) -> None:
        writer = get_writer("cursor")
        assert isinstance(writer, MarkdownRulesWriter)
        assert writer.rules_path == ".cursor/rules/spec-kitty.mdc"
        assert writer.append_mode is False

    def test_copilot_append_mode_true(self) -> None:
        writer = get_writer("copilot")
        assert isinstance(writer, MarkdownRulesWriter)
        assert writer.rules_path == ".github/copilot-instructions.md"
        assert writer.append_mode is True

    def test_gemini_rules_path(self) -> None:
        writer = get_writer("gemini")
        assert isinstance(writer, MarkdownRulesWriter)
        assert writer.rules_path == "GEMINI.md"
        assert writer.append_mode is True

    def test_pattern_e_keys_return_null_writer(self) -> None:
        for key in ("qwen", "kilocode", "auggie", "q"):
            result = get_writer(key)
            assert isinstance(result, NullWriter), f"Expected NullWriter for {key!r}"

    def test_codex_returns_agents_md_writer(self) -> None:
        result = get_writer("codex")
        assert isinstance(result, AgentsMdWriter)
        assert not isinstance(result, SkillsPreambleWriter)


# ---------------------------------------------------------------------------
# check_dir refinement on MarkdownRulesWriter
# ---------------------------------------------------------------------------

class TestMarkdownRulesWriterCheckDir:
    def test_can_write_with_check_dir_true_when_dir_exists(self, tmp_path: Path) -> None:
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        writer = MarkdownRulesWriter(
            harness_key="cursor",
            rules_path=".cursor/rules/spec-kitty.mdc",
            append_mode=False,
            check_dir=".cursor",
        )
        assert writer.can_write(tmp_path) is True

    def test_can_write_with_check_dir_false_when_dir_absent(self, tmp_path: Path) -> None:
        writer = MarkdownRulesWriter(
            harness_key="cursor",
            rules_path=".cursor/rules/spec-kitty.mdc",
            append_mode=False,
            check_dir=".cursor",
        )
        assert writer.can_write(tmp_path) is False

    def test_can_write_without_check_dir_checks_rules_parent(self, tmp_path: Path) -> None:
        """Regression: without check_dir, parent of rules_path must exist."""
        writer = MarkdownRulesWriter(
            harness_key="cursor",
            rules_path=".cursor/rules/spec-kitty.mdc",
            append_mode=False,
        )
        # .cursor/rules/ does NOT exist — should return False
        assert writer.can_write(tmp_path) is False

    def test_can_write_with_check_dir_true_even_if_rules_subdir_absent(
        self, tmp_path: Path
    ) -> None:
        """check_dir=".cursor" succeeds when .cursor/ exists but .cursor/rules/ doesn't."""
        (tmp_path / ".cursor").mkdir()
        # .cursor/rules/ does NOT exist
        writer = MarkdownRulesWriter(
            harness_key="cursor",
            rules_path=".cursor/rules/spec-kitty.mdc",
            append_mode=False,
            check_dir=".cursor",
        )
        assert writer.can_write(tmp_path) is True

    def test_can_write_without_check_dir_top_level_path(self, tmp_path: Path) -> None:
        """Without check_dir, top-level paths (e.g. GEMINI.md) check Path('.') → always True."""
        writer = MarkdownRulesWriter(
            harness_key="gemini",
            rules_path="GEMINI.md",
            append_mode=True,
        )
        # Path(".").parent is Path(".") which exists — so should return True
        assert writer.can_write(tmp_path) is True


# ---------------------------------------------------------------------------
# Dual Pattern C/D write to same AGENTS.md — idempotency under multiple writers
# ---------------------------------------------------------------------------

class TestDualPatternCDWriteIdempotency:
    def test_two_pattern_c_writers_no_duplicate_section(self, tmp_path: Path) -> None:
        """When two Pattern C harnesses write to AGENTS.md, only one section exists."""
        codex_writer = AgentsMdWriter("codex")
        opencode_writer = AgentsMdWriter("opencode")
        content = _make_content()
        codex_writer.write(tmp_path, content)
        opencode_writer.write(tmp_path, content)
        text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert text.count(SECTION_OPEN) == 1

    def test_pattern_c_then_pattern_d_no_duplicate_section(self, tmp_path: Path) -> None:
        """Pattern C write followed by Pattern D write — still exactly one section."""
        from specify_cli.session_presence.writers.skills_preamble import SkillsPreambleWriter as SPW
        codex_writer = AgentsMdWriter("codex")
        pi_writer = SPW("pi")
        content = _make_content()
        codex_writer.write(tmp_path, content)
        pi_writer.write(tmp_path, content)
        text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert text.count(SECTION_OPEN) == 1
