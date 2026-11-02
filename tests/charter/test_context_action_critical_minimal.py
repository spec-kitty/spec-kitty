"""#6968 regression — ``charter context`` advertises only resolving sections.

A consumer charter that never authored ``Terminology Canon``, ``Code Review
Checklist`` or ``Regression Vigilance`` must not be told that loading them is
action-critical: the bootstrap context used to emit a ``--include
section:<slug>`` stanza for each of them, and every one of those selectors
resolved to the "has not yet authored" placeholder.

Positive coverage (a charter that authors the headings still advertises them)
lives in ``test_context_section_bodies.py``; the explicit-fetch placeholder is
pinned in ``test_section_selector_graceful_degrade.py``. This module keeps the
single bootstrap-level entry-point test.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation.context import build_charter_context

pytestmark = [pytest.mark.fast]

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


def _write_charter(repo_root: Path, content: str) -> Path:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    charter_path = charter_dir / "charter.md"
    charter_path.write_text(content, encoding="utf-8")
    return charter_path


def _bootstrap_text(repo_root: Path, action: str) -> str:
    return build_charter_context(repo_root, action=action, mark_loaded=False).text


@pytest.mark.parametrize("action", ["implement", "review"])
def test_consumer_charter_advertises_no_section_it_does_not_have(tmp_path: Path, action: str) -> None:
    """A minimal consumer charter gets no action-critical advertising (#6968)."""

    _write_charter(tmp_path, _CONSUMER_CHARTER)

    text = _bootstrap_text(tmp_path, action)

    for selector in _SECTION_SELECTORS:
        assert f"--include {selector}" not in text, (
            f"{action} context advertised {selector} although the charter does not author that section; its fetch resolves to a placeholder."
        )
    assert f"Action-Critical Charter Sections ({action}):" not in text
