"""#6968 regression — ``charter context`` advertises only resolving sections.

A consumer charter that never authored ``Terminology Canon``, ``Code Review
Checklist`` or ``Regression Vigilance`` must not be told that loading them is
action-critical: the bootstrap context used to emit a ``--include
section:<slug>`` stanza for each of them, and every one of those selectors
resolved to the "has not yet authored" placeholder.

The absence assertions below are paired with a positive control on the same
fixture shape (a charter carrying the three headings), so a probe that cannot
see a rendered section at all would fail the control instead of passing the
absence check vacuously.

Both arms go through the production entry points
(:func:`charter.activation.context.build_charter_context` and
:func:`charter.activation.context.build_charter_context_include`), not the
private renderer helpers.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation.context import (
    build_charter_context,
    build_charter_context_include,
)

pytestmark = [pytest.mark.fast]

_HEADER = "Action-Critical Charter Sections (implement):"
_SECTION_SELECTORS = (
    "section:terminology-canon",
    "section:code-review-checklist",
    "section:regression-vigilance",
)

_CONSUMER_CHARTER = textwrap.dedent(
    """\
    # Consumer Charter

    ## Purpose

    Ship a small CLI.

    ## Testing Policy

    Tests are declared in YAML.
    """
)

_FULL_CHARTER = textwrap.dedent(
    """\
    # Project Charter

    ## Terminology Canon

    - The canonical term for a unit of governed work is **Mission**.

    ## Code Review Checklist

    - Terminology in code and docs aligns with the project glossary.

    ## Regression Vigilance

    Reviewers MUST grep the diff for the old term before approving.
    """
)


def _write_charter(repo_root: Path, content: str) -> Path:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    charter_path = charter_dir / "charter.md"
    charter_path.write_text(content, encoding="utf-8")
    return charter_path


def _bootstrap_text(repo_root: Path, action: str) -> str:
    return build_charter_context(repo_root, action=action, mark_loaded=False).text


@pytest.mark.parametrize("action", ["implement", "review"])
def test_consumer_charter_advertises_no_section_it_does_not_have(
    tmp_path: Path, action: str
) -> None:
    """A minimal consumer charter gets no action-critical advertising (#6968)."""

    _write_charter(tmp_path, _CONSUMER_CHARTER)

    text = _bootstrap_text(tmp_path, action)

    for selector in _SECTION_SELECTORS:
        assert f"--include {selector}" not in text, (
            f"{action} context advertised {selector} although the charter does "
            "not author that section; its fetch resolves to a placeholder."
        )
    assert f"Action-Critical Charter Sections ({action}):" not in text


@pytest.mark.parametrize("action", ["implement", "review"])
def test_charter_with_all_sections_still_advertises_them(
    tmp_path: Path, action: str
) -> None:
    """Positive control: the same probe sees every section when it IS authored."""

    _write_charter(tmp_path, _FULL_CHARTER)

    text = _bootstrap_text(tmp_path, action)

    assert f"Action-Critical Charter Sections ({action}):" in text
    for selector in _SECTION_SELECTORS:
        assert f"--include {selector}" in text
    assert "The canonical term for a unit of governed work is **Mission**" in text


def test_only_the_authored_section_is_advertised(tmp_path: Path) -> None:
    """A charter carrying one of three headings advertises exactly that one."""

    _write_charter(
        tmp_path,
        textwrap.dedent(
            """\
            # Project Charter

            ## Code Review Checklist

            - Terminology in code and docs aligns with the project glossary.
            """
        ),
    )

    text = _bootstrap_text(tmp_path, "implement")

    assert "--include section:code-review-checklist" in text
    assert "--include section:terminology-canon" not in text
    assert "--include section:regression-vigilance" not in text


def test_direct_selector_fetch_keeps_its_honest_degrade(tmp_path: Path) -> None:
    """The explicit fetch surface stays usable for a heading the charter lacks."""

    _write_charter(tmp_path, _CONSUMER_CHARTER)

    rendered = build_charter_context_include(
        tmp_path, "section:code-review-checklist", action="implement"
    )

    assert "Code Review Checklist" in rendered
    assert "has not yet authored" in rendered
