"""The orientation block names the right ``specify`` invocation per harness (#6475, #6470).

WP09 review cycle 1 item 5: the block hard-coded ``/spec-kitty.specify`` for every
harness, which is wrong for command-skill agents (Codex ``$spec-kitty-specify``,
Antigravity ``/spec-kitty-specify``). ``AGENTS.md`` is shared, so it names every form.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.invocation import (
    LEGACY_SPECIFY_INVOCATION,
    invocation_for_writer,
    shared_invocation,
)
from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
from specify_cli.session_presence.writers.registry import get_writer

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SHARED = "`$spec-kitty-specify` (codex), `/skill:spec-kitty-specify` (pi), `/spec-kitty-specify` (antigravity, letta, vibe) or `/spec-kitty.specify` (opencode)"


def _content(version: str = "4.0.0") -> SessionPresenceContent:
    return SessionPresenceContent(version, "demo", "healthy", None)


def test_default_render_keeps_the_slash_form() -> None:
    assert "  → run `/spec-kitty.specify`\n" in _content().render()


def test_shared_invocation_groups_agents_by_token() -> None:
    assert shared_invocation(["opencode", "codex", "antigravity", "pi", "vibe", "letta"]) == _SHARED


def test_shared_invocation_single_and_empty() -> None:
    assert shared_invocation(["codex"]) == "`$spec-kitty-specify` (codex)"
    assert shared_invocation([]) == LEGACY_SPECIFY_INVOCATION


def test_invocation_for_writer_uses_the_harness_token_outside_agents_md() -> None:
    assert invocation_for_writer("gemini", "GEMINI.md") == "`/spec-kitty.specify`"
    assert invocation_for_writer("antigravity", "AGENTS.md") == _SHARED


@pytest.mark.parametrize("first, second", [("antigravity", "codex"), ("codex", "opencode"), ("pi", "letta")])
def test_agents_md_writers_render_identical_bytes(tmp_path: Path, first: str, second: str) -> None:
    get_writer(first).write(tmp_path, _content())
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert f"  → run {_SHARED}\n" in text
    assert "→ run `/spec-kitty.specify`\n" not in text

    assert not get_writer(second).prepare(tmp_path, _content()).changed


def test_a_pre_6475_agents_md_block_is_refreshed_at_the_same_version(tmp_path: Path) -> None:
    legacy = _content().render()
    (tmp_path / "AGENTS.md").write_text(f"# Notes\n\n{legacy}", encoding="utf-8")

    get_writer("antigravity").write(tmp_path, _content())

    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# Notes\n\n")
    assert f"  → run {_SHARED}\n" in text
    assert text.count("<!-- spec-kitty:orientation -->") == 1


def test_an_edited_block_is_still_preserved(tmp_path: Path) -> None:
    edited = _content().render().replace("Two usage patterns", "My patterns")
    (tmp_path / "AGENTS.md").write_text(edited, encoding="utf-8")

    prepared = get_writer("codex").prepare(tmp_path, _content())

    assert prepared.disposition == "preserve"


def test_slash_rules_file_keeps_the_slash_form(tmp_path: Path) -> None:
    MarkdownRulesWriter("gemini", "GEMINI.md", append_mode=True).write(tmp_path, _content())
    assert "  → run `/spec-kitty.specify`\n" in (tmp_path / "GEMINI.md").read_text(encoding="utf-8")
