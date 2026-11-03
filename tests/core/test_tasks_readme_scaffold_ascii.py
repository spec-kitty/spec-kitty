"""Pin the character class of the core-owned mission scaffold text (#6877).

``render_tasks_readme_content()`` writes ``kitty-specs/<mission>/tasks/README.md``
at mission-create time. That file lives under ``kitty-specs/``, so
``spec-kitty validate-encoding`` scans it -- and before #6877 the scaffold it
wrote contained a U+2013 EN DASH, which meant a brand-new mission failed its own
encoding gate before anyone authored a word.

The fix is ASCII by construction in the source text, never a transliteration at
the write boundary: a sanitizer there cannot tell scaffold text from the
maintainer's prose and would silently rewrite the author's words (the #6579
precedent, ``test_artifact_keeps_authored_content_verbatim`` in
``tests/specify_cli/decisions/test_store.py``).

These tests are the gate for that invariant, not a snapshot of the text:

* :func:`test_rendered_tasks_readme_is_ascii` and
  :func:`test_gate_detector_finds_nothing` assert the shipped constant renders
  ASCII and that the encoding gate's own detector agrees.
* :func:`test_pin_fails_when_a_glyph_is_injected` is the non-vacuity proof
  required by ``architectural-gate-non-vacuity``: the same predicate must be
  able to fail, and it must be reading the shipped constant rather than a
  hard-coded copy of the output.
* :func:`test_renderer_formats_it_does_not_sanitise` pins the boundary: the
  renderer interpolates, it never repairs.
"""

from __future__ import annotations

import inspect
import string
from importlib import import_module
from pathlib import Path

import pytest

from specify_cli.core.mission_creation_scaffold import (
    TASKS_README_TEMPLATE,
    render_tasks_readme_content,
)
from specify_cli.text_sanitization import detect_problematic_characters

#: Branch names exercised by the pin. The renderer interpolates the planning
#: branch into the scaffold's frontmatter example, so a glyph introduced by an
#: interpolation would surface here too.
BRANCH_NAMES = ("main", "feature/x", "release-4.0.0")

_MODULE_PATH = Path(inspect.getfile(render_tasks_readme_content))


def _non_ascii_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.isascii()]


@pytest.mark.parametrize("planning_branch", BRANCH_NAMES)
def test_rendered_tasks_readme_is_ascii(planning_branch: str) -> None:
    """A mission's scaffold must not contain a byte outside ASCII (#6877)."""
    rendered = render_tasks_readme_content(planning_branch)

    worst = max(rendered.encode("utf-8"))
    assert worst <= 0x7F, f"tasks/README.md renders non-ASCII byte 0x{worst:02X} for branch {planning_branch!r}; offending lines: {_non_ascii_lines(rendered)}"


def test_gate_detector_finds_nothing() -> None:
    """The encoding gate's own detector must agree the scaffold is clean.

    ``detect_problematic_characters`` is the authority ``validate-encoding``
    uses, so this test asks the gate rather than restating its character list
    (single canonical authority, DIRECTIVE_044).
    """
    rendered = render_tasks_readme_content("main")

    assert detect_problematic_characters(rendered) == []


def test_pin_fails_when_a_glyph_is_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity: the ASCII predicate must be able to fail (#6877).

    A gate nobody has seen fail is a screenshot. Two glyphs are injected into the
    *shipped* constant and rendered through the *shipped* renderer -- the EN DASH
    the scaffold actually carried, and the EM DASH a pasted criterion would
    bring -- and the unmutated template is asserted clean in the same test, so
    one case witnesses both directions of the predicate.

    Mutating ``TASKS_README_TEMPLATE`` on its own module (rather than rendering a
    hand-built string) is what makes this a proof: the case goes red if someone
    later re-pins the gate against a literal copy of the rendered output instead
    of reading the constant.
    """
    module = import_module("specify_cli.core.mission_creation_scaffold")
    anchor = "# Tasks Directory"
    assert anchor in TASKS_README_TEMPLATE, "the mutation anchor moved; update this case rather than deleting it"

    for glyph in ("\u2013", "\u2014"):
        monkeypatch.setattr(module, "TASKS_README_TEMPLATE", TASKS_README_TEMPLATE.replace(anchor, f"{anchor} {glyph}", 1))

        rendered = module.render_tasks_readme_content("main")

        assert not rendered.isascii(), f"the ASCII predicate did not notice an injected {glyph!r}"
        assert f"{anchor} {glyph}" in _non_ascii_lines(rendered)
        assert max(rendered.encode("utf-8")) > 0x7F

    monkeypatch.undo()

    # Positive control, same fixture: the shipped template renders clean.
    assert render_tasks_readme_content("main").isascii()


def test_renderer_formats_it_does_not_sanitise() -> None:
    """The renderer interpolates; it never repairs what it was handed (#6877, FR-004).

    A non-ASCII branch name must pass through unchanged. This is the guard rail
    against "fixing" the pin by sanitising the renderer's output, which would
    also rewrite the author's own prose.
    """
    authored = "feature/caf\u00e9"

    rendered = render_tasks_readme_content(authored)

    assert authored in rendered
    assert not rendered.isascii()


def test_scaffold_module_never_sanitises() -> None:
    """No sanitizer sits on the scaffold path (#6877, NFR-001)."""
    source = _MODULE_PATH.read_text(encoding="utf-8")

    for forbidden in ("sanitize_markdown_text", "sanitize_directory", "detect_problematic_characters"):
        assert forbidden not in source, (
            f"{_MODULE_PATH.name} references {forbidden!r}; the scaffold must be ASCII by construction, not repaired on the way out (#6877, NFR-001)"
        )


def test_template_placeholders_are_known() -> None:
    """The scaffold's only field is ``planning_branch``.

    Pins the mutation helper above to a real contract: if a second field is
    added, ``_render`` must be updated with it rather than silently producing a
    ``KeyError``-free but wrong string.
    """
    fields = {name for _, name, _, _ in string.Formatter().parse(TASKS_README_TEMPLATE) if name is not None}

    assert fields == {"planning_branch"}
