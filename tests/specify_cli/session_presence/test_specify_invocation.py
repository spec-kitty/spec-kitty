"""The orientation block names every harness's ``specify`` invocation (#6475, #6470).

WP09 review cycle 1 item 5: the block hard-coded ``/spec-kitty.specify`` for every
harness, which is wrong for command-skill agents (Codex ``$spec-kitty-specify``,
Antigravity ``/spec-kitty-specify``). The block names every form, so it stays one
text for every harness (``AGENTS.md`` is shared; the frozen rc39 refresh compares
with one ``render()``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.invocation import LEGACY_SPECIFY_INVOCATION, orientation_invocation
from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
from specify_cli.session_presence.writers.registry import get_writer

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ALL_FORMS = (
    "`/spec-kitty.specify` (slash-command agents), `$spec-kitty-specify` (codex), "
    "`/skill:spec-kitty-specify` (pi) or `/spec-kitty-specify` (antigravity, letta, vibe)"
)


def _content(version: str = "4.0.0") -> SessionPresenceContent:
    return SessionPresenceContent(version, "demo", "healthy", None)


def test_orientation_invocation_names_every_form() -> None:
    assert orientation_invocation() == _ALL_FORMS


def test_render_names_every_form() -> None:
    assert f"  → run {_ALL_FORMS}\n" in _content().render()


@pytest.mark.parametrize("first, second", [("antigravity", "codex"), ("codex", "opencode"), ("pi", "letta")])
def test_agents_md_writers_render_identical_bytes(tmp_path: Path, first: str, second: str) -> None:
    get_writer(first).write(tmp_path, _content())
    assert f"  → run {_ALL_FORMS}\n" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    assert not get_writer(second).prepare(tmp_path, _content()).changed


@pytest.mark.parametrize("version", ["4.0.0", "3.2.0"])
def test_a_pre_6475_block_is_refreshed(tmp_path: Path, version: str) -> None:
    """Same version or older: a block with the old slash-only line is Spec Kitty's and is rewritten."""
    legacy = SessionPresenceContent(version, "demo", "healthy", None, LEGACY_SPECIFY_INVOCATION).render()
    (tmp_path / "AGENTS.md").write_text(f"# Notes\n\n{legacy}", encoding="utf-8")

    get_writer("antigravity").write(tmp_path, _content())

    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# Notes\n\n")
    assert f"  → run {_ALL_FORMS}\n" in text
    assert text.count("<!-- spec-kitty:orientation -->") == 1


def test_an_edited_block_is_still_preserved(tmp_path: Path) -> None:
    edited = _content().render().replace("Two usage patterns", "My patterns")
    (tmp_path / "AGENTS.md").write_text(edited, encoding="utf-8")

    assert get_writer("codex").prepare(tmp_path, _content()).disposition == "preserve"


def test_slash_rules_file_gets_the_same_block(tmp_path: Path) -> None:
    MarkdownRulesWriter("gemini", "GEMINI.md", append_mode=True).write(tmp_path, _content())
    assert (tmp_path / "GEMINI.md").read_text(encoding="utf-8") == _content().render()
