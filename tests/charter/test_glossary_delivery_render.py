"""WP01 (deliver-loaded-doctrine) — glossary render is names-only + pointer.

An activated, graph-reachable glossary pack must reach the agent through the
action-doctrine bundle as its term *surfaces* (names) plus a
``--include glossary-pack:<id>`` fetch pointer — and NEVER as inlined term
definitions (NFR-001 token budget). An org-authored pack reaches the agent
through the same path as a built-in pack (FR-011), so the two render identically.
"""

from __future__ import annotations

import pytest

from charter.activation.context import _ActionGovernanceBundle
from charter.activation.context_renderers.bootstrap_text import _render_action_doctrine_lines
from charter.offering.glossary_packs.models import GlossaryPack, GlossaryTerm

pytestmark = [pytest.mark.fast]

_PACK_ID = "spec-kitty-core"
_SURFACES = ("Mission", "Work Package", "Lane")
_DEFINITIONS = ("DEF-MISSION", "DEF-WP", "DEF-LANE")


def _pack(provenance: str) -> GlossaryPack:
    return GlossaryPack(
        id=_PACK_ID,
        provenance=provenance,
        terms=[
            GlossaryTerm(
                surface=surface,
                definition=definition,
                confidence=1.0,
                status="canonical",
            )
            for surface, definition in zip(_SURFACES, _DEFINITIONS, strict=True)
        ],
    )


class _GlossaryRepo:
    """Minimal ``glossary_packs`` repository stub: ``get`` by id."""

    def __init__(self, pack: GlossaryPack) -> None:
        self._pack = pack

    def get(self, item_id: str) -> GlossaryPack | None:
        return self._pack if item_id == self._pack.id else None


class _Service:
    """A doctrine service exposing only the ``glossary_packs`` repository.

    The action-render rows for the other kinds resolve ``getattr(service,
    <attr>, None)`` → ``None`` and emit nothing (the bundle carries no ids for
    them), so this test isolates the glossary block.
    """

    def __init__(self, pack: GlossaryPack) -> None:
        self.glossary_packs = _GlossaryRepo(pack)


def _bundle(pack: GlossaryPack) -> _ActionGovernanceBundle:
    return _ActionGovernanceBundle(
        mission="software-dev",
        directive_ids=[],
        tactic_ids=[],
        styleguide_ids=[],
        toolguide_ids=[],
        procedure_ids=[],
        asset_ids=[],
        glossary_pack_ids=[_PACK_ID],
        service=_Service(pack),
    )


def _render(pack: GlossaryPack) -> str:
    lines: list[str] = []
    _render_action_doctrine_lines(lines, _bundle(pack), repo_root=None)
    return "\n".join(lines)


def test_glossary_pack_renders_surfaces_and_fetch_pointer() -> None:
    text = _render(_pack("builtin"))

    for surface in _SURFACES:
        assert surface in text, f"term surface {surface!r} must render"
    assert "--include glossary-pack:spec-kitty-core" in text, "fetch pointer required"


def test_glossary_render_never_inlines_definitions() -> None:
    """NFR-001: definitions are pulled on demand, never inlined."""
    text = _render(_pack("builtin"))

    for definition in _DEFINITIONS:
        assert definition not in text, f"definition {definition!r} was inlined — NFR-001 forbids it (surfaces + pointer only)"


def test_org_sourced_pack_renders_identically_to_builtin() -> None:
    """FR-011: an org-authored pack reaches the agent through the same path."""
    builtin = _render(_pack("builtin"))
    org = _render(_pack("org:acme"))

    assert builtin == org
    assert builtin, "the glossary block must actually render something"


def test_no_glossary_ids_renders_no_glossary_block() -> None:
    """Byte-stability: a bundle with no glossary ids emits nothing new."""
    bundle = _ActionGovernanceBundle(
        mission="software-dev",
        directive_ids=[],
        tactic_ids=[],
        styleguide_ids=[],
        toolguide_ids=[],
        procedure_ids=[],
        asset_ids=[],
        glossary_pack_ids=[],
        service=_Service(_pack("builtin")),
    )
    lines: list[str] = []
    _render_action_doctrine_lines(lines, bundle, repo_root=None)

    assert not any("Glossar" in line for line in lines)
