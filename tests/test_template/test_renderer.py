from __future__ import annotations

from pathlib import Path

from specify_cli.template.renderer import (
    parse_frontmatter,
    render_template,
    render_template_text,
    rewrite_paths,
)


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_parse_frontmatter_returns_metadata_body_and_raw() -> None:
    content = """---
description: Demo
scripts:
  sh: echo hi
---
Hello world
"""
    metadata, body, raw = parse_frontmatter(content)

    assert metadata["description"] == "Demo"
    assert metadata["scripts"]["sh"] == "echo hi"
    assert body.strip() == "Hello world"
    assert "scripts:" in raw


def test_render_template_applies_callable_variables_and_rewrites_paths(tmp_path: Path) -> None:
    template_path = tmp_path / "cmd.md"
    template_path.write_text(
        """---
description: Replace tokens
scripts:
  sh: ./scripts/run.sh
---
Use {SCRIPT} for __AGENT__ via templates/commands/demo.md.
""",
        encoding="utf-8",
    )

    metadata, rendered, raw = render_template(
        template_path,
        lambda meta: {"{SCRIPT}": meta["scripts"]["sh"], "__AGENT__": "codex"},
    )

    assert metadata["description"] == "Replace tokens"
    assert "Use ./.kittify/scripts/run.sh for codex" in rendered
    assert ".kittify/templates/commands/demo.md" in rendered
    assert "scripts:" in raw


def test_render_template_text_uses_supplied_text_instead_of_rereading_path(tmp_path: Path) -> None:
    template_path = tmp_path / "cmd.md"
    template_path.write_text(
        """---
description: Original
scripts:
  sh: echo original
---
Original body
""",
        encoding="utf-8",
    )

    metadata, rendered, _raw = render_template_text(
        """---
description: Processed
scripts:
  sh: echo processed
---
Run {SCRIPT}
""",
        lambda meta: {"{SCRIPT}": meta["scripts"]["sh"]},
        template_path=template_path,
    )

    assert metadata["description"] == "Processed"
    assert "Run echo processed" in rendered
    assert "Original body" not in rendered


def test_rewrite_paths_accepts_custom_patterns() -> None:
    result = rewrite_paths("Use foo/path", {"foo/path": "bar/path"})
    assert result == "Use bar/path"


def test_rewrite_paths_keeps_source_template_paths() -> None:
    source_path = "packs/built-in/missions/software-dev/templates/spec-template.md"
    assert rewrite_paths(source_path) == source_path


_SEED = """terms:
  - surface: {surface}
    definition: A term used by the renderer memo test
    confidence: 1.0
    status: active
"""


def test_glossary_seeds_are_parsed_once_per_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendering many templates parses the glossary seeds once until they change (#5526)."""
    import glossary.scope as scope_module
    from glossary.models import TermSense
    from specify_cli.template import renderer

    monkeypatch.setattr(renderer, "_TERM_SURFACES_MEMO", {}, raising=False)
    loads: list[object] = []
    original = scope_module.load_seed_file

    def _counted(scope: scope_module.GlossaryScope, repo_root: Path) -> list[TermSense]:
        loads.append(scope)
        return original(scope, repo_root)

    monkeypatch.setattr(scope_module, "load_seed_file", _counted)
    seed = tmp_path / ".kittify" / "glossaries" / "spec_kitty_core.yaml"
    seed.parent.mkdir(parents=True)
    seed.write_text(_SEED.format(surface="widget"), encoding="utf-8")
    template = tmp_path / "templates" / "demo.md"
    template.parent.mkdir()
    template.write_text("A widget and a gadget.\n", encoding="utf-8")

    _, first, _ = render_template(template)
    _, second, _ = render_template(template)
    per_build = len(scope_module.GlossaryScope)

    assert len(loads) == per_build
    assert first == second == "A widget<!-- glossary:glossary:widget --> and a gadget.\n"

    seed.write_text(_SEED.format(surface="gadget"), encoding="utf-8")
    _, third, _ = render_template(template)

    assert len(loads) == 2 * per_build
    assert third == "A widget and a gadget<!-- glossary:glossary:gadget -->.\n"


def test_glossary_seed_edit_with_identical_size_and_mtime_is_reparsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A same-size, same-mtime seed edit must still invalidate the memo (#5526 squad MINOR).

    The glossary seed files are consumer-writable, unlike the shipped
    read-only files the other renderer memos cover. A fingerprint keyed on
    ``(size, mtime)`` would serve a stale term-surface map for an edit that
    happens to preserve both, which coarse-granularity filesystems, ``touch
    -r``, or a times-preserving backup/restore can all produce.
    """
    import os

    from specify_cli.template import renderer

    monkeypatch.setattr(renderer, "_TERM_SURFACES_MEMO", {}, raising=False)
    seed = tmp_path / ".kittify" / "glossaries" / "spec_kitty_core.yaml"
    seed.parent.mkdir(parents=True)
    seed.write_text(_SEED.format(surface="widget"), encoding="utf-8")
    template = tmp_path / "templates" / "demo.md"
    template.parent.mkdir()
    template.write_text("A widget and a gadget.\n", encoding="utf-8")

    _, first, _ = render_template(template)
    assert first == "A widget<!-- glossary:glossary:widget --> and a gadget.\n"

    pre_stat = seed.stat()
    seed.write_text(_SEED.format(surface="gadget"), encoding="utf-8")
    assert seed.stat().st_size == pre_stat.st_size
    os.utime(seed, ns=(pre_stat.st_atime_ns, pre_stat.st_mtime_ns))
    assert seed.stat().st_mtime_ns == pre_stat.st_mtime_ns

    _, second, _ = render_template(template)
    assert second == "A widget and a gadget<!-- glossary:glossary:gadget -->.\n"
