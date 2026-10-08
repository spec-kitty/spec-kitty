"""Pointer-only module-README lint (WP09, FR-005 / C-005).

The **covered set** is objective: the ``src/doctrine`` modules whose code models
are bound in the drift-guard binding table (agent_profiles, drg, missions) — i.e.
the modules a reader lands in and needs a one-hop bridge to the canonical docs.

For every covered README the lint asserts the required canonical-doc pointer links
are present AND resolve in-mission. For the READMEs this mission authored as
*pointer-only* bridges (drg, missions) it additionally forbids schema duplication
(no pipe-table / no fenced block echoing model field names) under a fixed cap — the
C-005 no-new-drift-surface property, checked directly rather than via a length proxy.
Pre-existing rich READMEs (agent_profiles) are extended, not clobbered: only their
pointer links are checked.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.docs.diagram_drift.binding_table import BINDINGS

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIAGRAM_DOCS = {
    "doctrine-kinds.md",
    "doctrine-relationships.md",
    "mission-type-resolution.md",
}
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_POINTER_CAP_LINES = 30

# Objective covered set: modules with a drift-guard-bound code model.
# (readme relative path, strict_pointer_only)
#
# `src/charter/offering/missions/` is a bound-model module but is EXCLUDED: it is on the
# pack-relocation content manifest (tests/charter_offering/test_pack_relocation_guard.py),
# which forbids a README under that path. Its schema docs live in
# mission-type-resolution.md (linked from the code models directly).
_RELOCATION_EXCLUDED = frozenset({"missions"})
_COVERED: tuple[tuple[str, bool], ...] = (
    ("src/charter/offering/drg/README.md", True),  # authored here (pointer-only)
    ("src/charter/offering/agent_profiles/README.md", False),  # pre-existing rich README, extended
)


def _bound_modules_match_covered() -> None:
    """Every drift-guard-bound subpackage is either covered or relocation-excluded."""
    # doctrine.<pkg>...; artifact_kinds is a top-level module (no subpackage README).
    bound_pkgs = {parts[1] for b in BINDINGS if len(parts := b.model.__module__.split(".")) > 2}
    covered_pkgs = {rel.split("/")[2] for rel, _ in _COVERED}
    # No bound subpackage is silently dropped: each is covered or explicitly excluded.
    unaccounted = bound_pkgs - covered_pkgs - _RELOCATION_EXCLUDED
    assert not unaccounted, f"bound subpackages without a README or exclusion: {unaccounted}"
    assert covered_pkgs <= bound_pkgs, covered_pkgs


def _links(readme_text: str) -> list[str]:
    return _MD_LINK_RE.findall(readme_text)


def test_covered_modules_have_readmes() -> None:
    for rel, _ in _COVERED:
        assert (_REPO_ROOT / rel).is_file(), f"covered module missing README: {rel}"


def test_required_canonical_links_present_and_resolve() -> None:
    for rel, _ in _COVERED:
        readme = _REPO_ROOT / rel
        text = readme.read_text(encoding="utf-8")
        links = _links(text)
        # at least one canonical diagram-doc pointer
        assert any(any(doc in link for doc in _DIAGRAM_DOCS) for link in links), f"{rel}: no canonical diagram-doc pointer link"
        # every relative link resolves in-mission (strip anchor + query)
        for link in links:
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = (readme.parent / link.split("#", 1)[0]).resolve()
            assert target.exists(), f"{rel}: link does not resolve in-mission: {link}"


def test_pointer_readmes_are_pointer_only() -> None:
    for rel, strict in _COVERED:
        if not strict:
            continue
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) <= _POINTER_CAP_LINES, f"{rel}: pointer README too long ({len(lines)} lines)"
        # No schema field-table (a pipe-table duplicating a model would be a drift surface).
        assert not any(line.lstrip().startswith("|") for line in lines), f"{rel}: pointer README must not contain a field/pipe-table (C-005)"
        # No fenced code block (a pointer bridges, it never restates the schema).
        assert "```" not in text, f"{rel}: pointer README must not contain fenced code (C-005)"


def test_covered_set_tracks_bound_modules() -> None:
    _bound_modules_match_covered()
