"""WP03 (#3488, FR-008) — bind the DRG-emit seam to the profile-delivery seam.

**C-004 context (verify-first — no shipped delivery code changed here).**
Grounding confirmed the rc1 #3488 delivery gaps are already fixed on current
main: operating-procedures is data-driven into the DRG
(``_emit_operating_procedure_edges``,
``src/doctrine/drg/migration/extractor.py``) with a fail-closed doctor check
(``_run_operating_procedures_check``,
``src/specify_cli/cli/commands/_doctrine_collect.py``); step ``description``
renders (``format_inline_named_body``,
``src/charter/context_renderers/profile_sections.py``); styleguide/toolguide
pointer-only delivery is a *documented, deliberate* NFR-001 token-budget
choice (``_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON``, same module). The
residual this file closes is structural, not a code fix: no test previously
bound the DRG-emit side (a profile-selector field really is projected into
the graph) to the delivery side (that same channel reaches the agent, either
as an inline body or as an *attested* pointer-only fetch stanza). This file
binds ``_render_profile_sections``'s delivery renderer composition
(``_PROFILE_SECTION_RENDERERS``) to the projected-channel roster
(``_REAL_PROJECTED_CHANNELS``), so a renderer added without a matching
roster entry, or a rostered channel that stops delivering (neither body nor
attested pointer-only), reddens — plus a 3-edge emit spot-check
(``test_directive_tactic_operating_procedures_are_emitted_as_drg_edges``).
It additionally binds the emit-side governance scope-field table
(``_GOVERNANCE_PROFILE_SCOPE_FIELDS``) to the ``MissionTypeProfile`` schema
(the #3604 defect class: a ``selected_*`` field that validates and loads but
has no table entry to project it into the DRG). This is not a full,
automatic emit↔delivery cross-seam enumeration — a purely emit-only channel
that is projected into the DRG but never wired into any delivery renderer at
all stays outside what these binds catch.

**FR-008 anti-divergence test design.** The six profile-selector channels
``_render_profile_sections`` composes (its module-level
``_PROFILE_SECTION_RENDERERS`` tuple) are grouped into two buckets:

* **body-delivering** — ``directive`` (``directive-references`` →
  ``_render_profile_directives``), ``tactic`` (``tactic-references`` →
  ``_render_profile_tactics``), and ``operating-procedures`` (the
  ``collaboration.operating-procedures`` field → an
  ``agent_profile --requires--> procedure`` DRG edge → the profile channel →
  ``render_profile_procedures``). Each renders the artifact's verbatim body
  inline.
* **attested pointer-only** — ``styleguide`` / ``toolguide``
  (``styleguide-references`` / ``toolguide-references`` →
  ``render_profile_styleguides`` / ``render_profile_toolguides``, both
  ``body_fn=None`` by design), and ``suggested_doctrine`` (the profile
  *channel*'s ``suggests``-reached #3063 A–E families →
  ``render_profile_suggested_doctrine``, also ``body_fn=None`` — NFR-003:
  a suggested artefact is always named as a link, never inlined). Never an
  inline body; always the fetch stanza, and the *reason* for that choice is
  either a named, importable constant (styleguide/toolguide) or the
  renderer's own docstring (suggested_doctrine) rather than an unattested
  aside.

``test_directive_tactic_operating_procedures_are_emitted_as_drg_edges`` binds
the **emit** half: it runs the single-authority extractor
(``extract_artifact_edges``, mirroring the tmp_path pack-fixture pattern used
throughout ``tests/doctrine/drg/migration/test_extractor.py``) over a minimal
fixture pack and asserts the three body-delivering channels really do land as
``agent_profile --requires--> {directive,tactic,procedure}`` DRG edges — not
merely assumed from reading the source.

``test_real_projected_channels_are_delivered_or_attested_pointer_only`` binds
the **delivery** half: it renders one synthetic profile citing all six
channels through the real ``_render_profile_sections`` entry point and
classifies each channel's rendered output as ``"body"``, ``"pointer_only"``,
or ``"undelivered"`` (an inline body is present XOR the fetch-stanza selector
is present; anything else — neither, or ambiguously both — is a divergence).
The FR-008 invariant, ``_is_consistent``, accepts ``"body"`` outright and
accepts ``"pointer_only"`` only when the channel carries a non-empty attested
reason; ``"undelivered"`` is always a failure.

``test_real_projected_channels_roster_matches_product_renderer_composition``
closes the divergence this file was written to catch but originally left
open: it binds ``_REAL_PROJECTED_CHANNELS`` to
``_PROFILE_SECTION_RENDERERS`` — the exact tuple the product composes — by
renderer *function identity*, not by a hand-counted literal. A 7th channel
wired into that tuple without a matching roster entry now fails this
assertion instead of passing silently (the original defect: the roster had
only five hand-listed channels while the product already composed six,
and nothing tied the two together).

**Red-first proof.** The classifier and invariant are generic — they do not
special-case the six real channel names — so the two synthetic-channel tests
below (``test_synthetic_undelivered_channel_is_caught`` and
``test_synthetic_unattested_pointer_only_channel_is_caught``) exercise the
*same* ``_classify_delivery`` / ``_is_consistent`` pair against a fabricated
channel that mimics exactly what a future one-seam-only divergence would look
like: a channel projected into the DRG whose delivery renderer was either
never wired up (renders neither a body nor its own fetch stanza) or wired
``body_fn=None`` with no attestation (silent pointer-only, the pre-#3488-fix
defect class). Both synthetic cases fail the invariant; the six real
channels, exercised through the identical mechanism in the test just above,
currently pass — proving the check is live, not a tautology.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest

from charter.activation.context_renderers.profile_sections import (
    _PROFILE_SECTION_RENDERERS,
    _STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON,
    _render_profile_directives,
    _render_profile_sections,
    _render_profile_tactics,
    render_profile_procedures,
    render_profile_styleguides,
    render_profile_suggested_doctrine,
    render_profile_toolguides,
)
from charter.activation.mission_type_profiles import MissionTypeProfile
from charter.offering.agent_profiles import AgentProfile
from charter.offering.drg.migration.extractor import (
    _GOVERNANCE_PROFILE_SCOPE_FIELDS,
    extract_artifact_edges,
)
from charter.offering.drg.migration.id_normalizer import artifact_to_urn
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = pytest.mark.fast

_DeliveryMode = Literal["body", "pointer_only", "undelivered"]


# ---------------------------------------------------------------------------
# Delivery-side fixture: one synthetic profile exercising all six channels
# through the real ``_render_profile_sections`` entry point.
# ---------------------------------------------------------------------------

#: The suggested-doctrine fixture artefact + the ``suggests`` edge ``when``
#: ``render_profile_suggested_doctrine`` must surface for it.
_SUGGESTED_PARADIGM_ID = "fixture-paradigm"
_SUGGESTED_PARADIGM_WHEN = "you are shaping a new bounded context"


class _StubCatalogRepo:
    """Minimal ``_CatalogRepoLike`` stand-in: a fixed id -> artifact mapping."""

    def __init__(self, items: dict[str, object]) -> None:
        self._items = items

    def get(self, item_id: str) -> object | None:
        return self._items.get(item_id)


def _fixture_suggested_doctrine_graph() -> DRGGraph:
    """A minimal DRG: the fixture profile ``suggests`` one paradigm.

    Mirrors the shape ``render_profile_suggested_doctrine`` walks in
    production (WP01, #3063 Family A: ``agent_profile --suggests--> paradigm``)
    — see ``tests/doctrine/drg/test_profile_suggests_delivery.py`` for the
    real-graph equivalent this synthesizes a minimal stand-in for.
    """
    return DRGGraph(
        schema_version="1.0",
        generated_at="1970-01-01T00:00:00Z",
        generated_by="test_emit_delivery_bind:_fixture_suggested_doctrine_graph",
        nodes=[
            DRGNode(urn="agent_profile:fr008-bind-fixture", kind=NodeKind.AGENT_PROFILE),
            DRGNode(urn=f"paradigm:{_SUGGESTED_PARADIGM_ID}", kind=NodeKind.PARADIGM),
        ],
        edges=[
            DRGEdge(
                source="agent_profile:fr008-bind-fixture",
                target=f"paradigm:{_SUGGESTED_PARADIGM_ID}",
                relation=Relation.SUGGESTS,
                when=_SUGGESTED_PARADIGM_WHEN,
            ),
        ],
    )


class _StubAgentProfileChannel:
    """Stubs the slice of ``AgentProfileRepository`` the delivery-side
    channel renderers depend on: ``profile_channel_procedure_ids`` (WP08's
    ``requires``/``specializes_from`` walk, consumed by
    ``render_profile_procedures``) and ``profile_channel_reached`` + ``.drg``
    (the ``suggests``-delivery walk, consumed by
    ``render_profile_suggested_doctrine``) — without needing a real,
    materialized DRG for either.
    """

    def __init__(
        self,
        procedure_ids: list[str],
        reached: frozenset[str],
        drg: DRGGraph,
    ) -> None:
        self._procedure_ids = procedure_ids
        self._reached = reached
        self.drg = drg

    def profile_channel_procedure_ids(self, profile_id: str) -> list[str]:
        return self._procedure_ids

    def profile_channel_reached(self, profile_id: str) -> frozenset[str]:
        return self._reached


def _fixture_profile() -> AgentProfile:
    """A profile citing all four direct-citation channels (T010/T011)."""
    return AgentProfile.model_validate(
        {
            "profile-id": "fr008-bind-fixture",
            "name": "FR-008 Bind Fixture",
            "roles": ["implementer"],
            "purpose": "test fixture for the FR-008 emit<->delivery bind",
            "specialization": {"primary-focus": "testing"},
            "directive-references": [
                {
                    "code": "DIRECTIVE_999",
                    "name": "Fixture Directive",
                    "rationale": "bind test",
                }
            ],
            "tactic-references": [{"id": "fixture-tactic", "rationale": "bind test"}],
            "styleguide-references": [{"id": "fixture-styleguide", "rationale": "bind test"}],
            "toolguide-references": [{"id": "fixture-toolguide", "rationale": "bind test"}],
        }
    )


def _fixture_service() -> SimpleNamespace:
    """A ``ActiveCharterService``-shaped stub: every catalog resolves, deterministically."""
    return SimpleNamespace(
        directives=_StubCatalogRepo({"DIRECTIVE_999": SimpleNamespace(intent="Do the fixture thing.")}),
        tactics=_StubCatalogRepo({"fixture-tactic": SimpleNamespace(name="Fixture Tactic", purpose="A fixture tactic body.", steps=[])}),
        styleguides=_StubCatalogRepo({"fixture-styleguide": SimpleNamespace(title="Fixture Styleguide")}),
        toolguides=_StubCatalogRepo({"fixture-toolguide": SimpleNamespace(title="Fixture Toolguide")}),
        procedures=_StubCatalogRepo(
            {
                "fixture-procedure": SimpleNamespace(
                    name="Fixture Procedure",
                    purpose="A fixture procedure body.",
                    steps=[],
                )
            }
        ),
        paradigms=_StubCatalogRepo({_SUGGESTED_PARADIGM_ID: SimpleNamespace(title="Fixture Paradigm")}),
        agent_profiles=_StubAgentProfileChannel(
            procedure_ids=["fixture-procedure"],
            reached=frozenset({f"paradigm:{_SUGGESTED_PARADIGM_ID}"}),
            drg=_fixture_suggested_doctrine_graph(),
        ),
    )


# ---------------------------------------------------------------------------
# The FR-008 classifier + invariant — generic over any channel, real or
# synthetic (no per-name special-casing), which is what makes the
# undelivered/unattested tests below a genuine red-first proof rather than a
# hand-tuned assertion.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProjectedChannel:
    """One profile-selector channel projected into the DRG.

    ``body_marker`` is a string that only appears in the rendered block when
    the channel's artifact body was inlined. ``fetch_selector`` is the
    ``<kind>:<id>`` selector the canonical fetch stanza
    (``Run: spec-kitty charter context --include <selector>``) would carry if
    the channel rendered pointer-only. ``attested_reason`` is the documented,
    non-empty rationale for pointer-only delivery when that is the design
    (``None`` for channels that are never meant to be pointer-only).
    ``renderer`` is the actual product function
    (``_PROFILE_SECTION_RENDERERS`` member) this channel exercises — the
    anti-divergence guard test below binds the roster to the product's
    renderer *composition* through this field, by function identity, rather
    than by a hand-counted literal. ``None`` for the synthetic/hypothetical
    channels below, which exercise no real renderer.

    ``emitted_requires_edge_kind`` is the target-node *kind* string an
    ``agent_profile --requires--> <kind>:bind-fixture`` edge lands as when
    :func:`~doctrine.drg.migration.extractor.extract_artifact_edges` walks
    this channel's citation field for a profile that cites it (#3633 item 1,
    the emit-side enumeration binding below). ``None`` for channels whose
    delivery does NOT depend on a citation-to-requires DRG edge at all:
    ``styleguide``/``toolguide`` render straight from the profile's own
    schema field (no DRG involved — see ``render_profile_styleguides``/
    ``render_profile_toolguides``), and ``suggested_doctrine`` is delivered
    via transitive ``suggests``-reachability, not a direct citation edge.
    """

    name: str
    body_marker: str | None
    fetch_selector: str
    attested_reason: str | None
    renderer: Callable[..., list[str]] | None = None
    emitted_requires_edge_kind: str | None = None


def _fetch_stanza_line(selector: str) -> str:
    return f"Run: spec-kitty charter context --include {selector}"


def _classify_delivery(block: str, channel: _ProjectedChannel) -> _DeliveryMode:
    """Classify how *channel* actually reached the rendered *block*.

    ``"undelivered"`` is the FR-008 divergence: a channel that is projected
    into the DRG but whose rendered output carries neither an inline body nor
    its own fetch-stanza pointer — it silently reaches no agent.
    """
    has_body = channel.body_marker is not None and channel.body_marker in block
    has_fetch = _fetch_stanza_line(channel.fetch_selector) in block
    if has_body and not has_fetch:
        return "body"
    if has_fetch and not has_body:
        return "pointer_only"
    return "undelivered"


def _is_consistent(channel: _ProjectedChannel, mode: _DeliveryMode) -> bool:
    """FR-008 invariant: every projected channel is body-delivering OR attests
    a documented pointer-only reason. ``"undelivered"`` never satisfies it,
    and ``"pointer_only"`` without a reason does not either — distinguishing a
    *deliberate* NFR-001-style choice from a silent no-op.
    """
    if mode == "body":
        return True
    if mode == "pointer_only":
        return bool(channel.attested_reason)
    return False


#: The documented, non-empty rationale for ``suggested_doctrine``'s
#: pointer-only (``body_fn=None``) delivery — pulled from the renderer's own
#: docstring (NFR-003: a suggested artefact is named as a link, never
#: inlined) rather than hand-typed, so the attestation is bound to the
#: product's own words the same way ``_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON``
#: is a named product constant for the styleguide/toolguide channels.
_SUGGESTED_DOCTRINE_POINTER_ONLY_REASON: str = render_profile_suggested_doctrine.__doc__ or ""
assert "NFR-003" in _SUGGESTED_DOCTRINE_POINTER_ONLY_REASON, (
    "render_profile_suggested_doctrine's docstring must document the NFR-003 link-only rationale this test attests"
)


_REAL_PROJECTED_CHANNELS: tuple[_ProjectedChannel, ...] = (
    _ProjectedChannel(
        name="directive",
        body_marker="Intent: Do the fixture thing.",
        fetch_selector="directive:DIRECTIVE_999",
        attested_reason=None,
        renderer=_render_profile_directives,
        emitted_requires_edge_kind="directive",
    ),
    _ProjectedChannel(
        name="tactic",
        body_marker="Name: Fixture Tactic",
        fetch_selector="tactic:fixture-tactic",
        attested_reason=None,
        renderer=_render_profile_tactics,
        emitted_requires_edge_kind="tactic",
    ),
    _ProjectedChannel(
        name="operating-procedures",
        body_marker="Name: Fixture Procedure",
        fetch_selector="procedure:fixture-procedure",
        attested_reason=None,
        renderer=render_profile_procedures,
        emitted_requires_edge_kind="procedure",
    ),
    _ProjectedChannel(
        name="styleguide",
        body_marker=None,
        fetch_selector="styleguide:fixture-styleguide",
        attested_reason=_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON,
        renderer=render_profile_styleguides,
    ),
    _ProjectedChannel(
        name="toolguide",
        body_marker=None,
        fetch_selector="toolguide:fixture-toolguide",
        attested_reason=_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON,
        renderer=render_profile_toolguides,
    ),
    _ProjectedChannel(
        name="suggested_doctrine",
        body_marker=None,
        fetch_selector=f"paradigm:{_SUGGESTED_PARADIGM_ID}",
        attested_reason=_SUGGESTED_DOCTRINE_POINTER_ONLY_REASON,
        renderer=render_profile_suggested_doctrine,
    ),
)


# ---------------------------------------------------------------------------
# T010 — the FR-008 structural bind.
# ---------------------------------------------------------------------------


def test_real_projected_channels_are_delivered_or_attested_pointer_only() -> None:
    """Every real projected channel is currently body-delivering or attested
    pointer-only — the seam is consistent today (this is the "confirm the
    test currently PASSES for the real channels" half of the red-first proof).
    """
    block = _render_profile_sections(_fixture_profile(), _fixture_service())

    results = {channel.name: _classify_delivery(block, channel) for channel in _REAL_PROJECTED_CHANNELS}

    assert results == {
        "directive": "body",
        "tactic": "body",
        "operating-procedures": "body",
        "styleguide": "pointer_only",
        "toolguide": "pointer_only",
        "suggested_doctrine": "pointer_only",
    }
    for channel in _REAL_PROJECTED_CHANNELS:
        assert _is_consistent(channel, results[channel.name]), (
            f"channel {channel.name!r} classified as {results[channel.name]!r} violates the FR-008 body-or-attested-pointer-only invariant"
        )


def test_real_projected_channels_roster_matches_product_renderer_composition() -> None:
    """FR-008 anti-divergence GUARD: bind ``_REAL_PROJECTED_CHANNELS`` to the
    product's own renderer composition (``_PROFILE_SECTION_RENDERERS`` —
    the exact tuple ``_render_profile_sections`` iterates), not to a
    hand-counted literal.

    This is the durable check the original roster lacked: it hand-listed five
    channels while the product already composed six (``directive``, ``tactic``,
    ``styleguide``, ``toolguide``, ``operating-procedures``,
    ``suggested_doctrine``), and nothing tied the two together — so the sixth
    channel silently passed the FR-008 invariant test above by simply never
    being checked. Binding by renderer *function identity* means a future 7th
    channel added to ``_PROFILE_SECTION_RENDERERS`` without a matching roster
    entry fails this assertion (set sizes/members diverge) instead of the
    divergence going unnoticed, exactly the residual this file exists to close.
    """
    roster_renderers = {channel.renderer for channel in _REAL_PROJECTED_CHANNELS}
    product_renderers = set(_PROFILE_SECTION_RENDERERS)

    assert roster_renderers == product_renderers, (
        "_REAL_PROJECTED_CHANNELS's renderer set has diverged from "
        "_PROFILE_SECTION_RENDERERS (the product's composed profile-channel "
        "renderers) — a channel was added to or removed from one without "
        "updating the other"
    )
    # No duplicate/missing coverage: exactly one roster entry per renderer.
    assert len(_REAL_PROJECTED_CHANNELS) == len(_PROFILE_SECTION_RENDERERS)


def test_governance_profile_scope_field_table_is_bound_to_model_schema() -> None:
    """Emit-side bind: the extractor's _GOVERNANCE_PROFILE_SCOPE_FIELDS table
    must enumerate exactly MissionTypeProfile's selected_* fields. A new
    selected_* field added to the model without a table entry would validate,
    load, and then vanish at the DRG projection seam -- the #3604 defect this
    mission closed. This guard reddens on that drift (both directions)."""
    table_fields = {name for name, _kind in _GOVERNANCE_PROFILE_SCOPE_FIELDS}
    model_fields = {n for n in MissionTypeProfile.model_fields if n.startswith("selected_")}

    assert table_fields == model_fields, (
        "_GOVERNANCE_PROFILE_SCOPE_FIELDS has diverged from "
        "MissionTypeProfile's selected_* fields (symmetric difference: "
        f"{table_fields ^ model_fields}) -- a selected_* field was added to "
        "or removed from the model without a matching extractor table entry, "
        "or vice versa"
    )


def test_synthetic_undelivered_channel_is_caught() -> None:
    """Red-first proof (1/2): a channel projected into the DRG whose delivery
    renderer was never wired up — neither an inline body nor its own fetch
    stanza reaches the rendered block — fails the FR-008 invariant. This is
    exactly what a future channel added to DRG projection but forgotten in
    ``_render_profile_sections``'s renderer list would look like.
    """
    block = _render_profile_sections(_fixture_profile(), _fixture_service())
    ghost_channel = _ProjectedChannel(
        name="hypothetical-new-channel",
        body_marker="Name: Ghost Artifact",
        fetch_selector="ghost-kind:ghost-artifact",
        attested_reason=None,
    )

    mode = _classify_delivery(block, ghost_channel)

    assert mode == "undelivered"
    assert not _is_consistent(ghost_channel, mode)


def test_synthetic_unattested_pointer_only_channel_is_caught() -> None:
    """Red-first proof (2/2): a channel that renders pointer-only but carries
    no attested reason also fails — distinguishing the *documented*
    NFR-001-style design choice (styleguide/toolguide) from an undocumented,
    silent pointer-only drop (the pre-#3488-fix defect class).
    """
    block = _render_profile_sections(_fixture_profile(), _fixture_service())
    # Reuse a real fetch selector so ``has_fetch`` is genuinely True; the only
    # difference from the real ``styleguide`` channel is the missing attestation.
    unattested_channel = _ProjectedChannel(
        name="hypothetical-unattested-pointer-only",
        body_marker=None,
        fetch_selector="styleguide:fixture-styleguide",
        attested_reason=None,
    )

    mode = _classify_delivery(block, unattested_channel)

    assert mode == "pointer_only"
    assert not _is_consistent(unattested_channel, mode)


def test_directive_tactic_operating_procedures_are_emitted_as_drg_edges(
    tmp_path: Path,
) -> None:
    """Emit-side half of the bind: the three body-delivering channels above
    really are projected into the DRG by the single-authority extractor
    (``extract_artifact_edges`` — C-004, no re-implementation), not merely
    assumed from reading the source. Mirrors the tmp_path pack-fixture
    pattern used by ``test_procedure_reference_reason_roundtrips`` et al. in
    ``tests/doctrine/drg/migration/test_extractor.py``.
    """
    doctrine_root = tmp_path / "pack"
    (doctrine_root / "directives").mkdir(parents=True)
    (doctrine_root / "tactics").mkdir(parents=True)
    (doctrine_root / "procedures").mkdir(parents=True)
    (doctrine_root / "agent_profiles").mkdir(parents=True)

    (doctrine_root / "directives" / "bind-fixture.directive.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\ntitle: Bind Fixture Directive\n",
        encoding="utf-8",
    )
    (doctrine_root / "tactics" / "bind-fixture.tactic.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\nname: Bind Fixture Tactic\n",
        encoding="utf-8",
    )
    (doctrine_root / "procedures" / "bind-fixture.procedure.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\nname: Bind Fixture Procedure\npurpose: test\n",
        encoding="utf-8",
    )
    (doctrine_root / "agent_profiles" / "bind-fixture.agent.yaml").write_text(
        "\n".join(
            [
                "profile-id: bind-fixture",
                "name: Bind Fixture Profile",
                "directive-references:",
                "  - code: bind-fixture",
                "    name: Bind Fixture Directive",
                "    rationale: test",
                "tactic-references:",
                "  - id: bind-fixture",
                "collaboration:",
                "  operating-procedures: [bind-fixture]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _nodes, edges = extract_artifact_edges(doctrine_root)
    edge_triples = {(edge.source, edge.target, edge.relation) for edge in edges}
    profile_urn = artifact_to_urn("agent_profile", "bind-fixture")

    assert (
        profile_urn,
        artifact_to_urn("directive", "bind-fixture"),
        Relation.REQUIRES,
    ) in edge_triples
    assert (
        profile_urn,
        artifact_to_urn("tactic", "bind-fixture"),
        Relation.REQUIRES,
    ) in edge_triples
    assert (
        profile_urn,
        artifact_to_urn("procedure", "bind-fixture"),
        Relation.REQUIRES,
    ) in edge_triples


def test_direct_citation_channels_are_emitted_by_enumeration_over_the_delivery_roster(
    tmp_path: Path,
) -> None:
    """#3633 item 1: the emit half above was a hand-listed 3-channel spot
    check with no structural tie to the delivery roster
    (``_REAL_PROJECTED_CHANNELS``) -- a channel added to or dropped from the
    roster's direct-citation set could drift from what
    ``extract_artifact_edges`` actually emits, and nothing here would
    notice. This test drives the same fixture-and-assert shape generically
    off ``_ProjectedChannel.emitted_requires_edge_kind`` instead, so it is
    a genuine enumeration bind rather than three independent literals:

    * A channel present in the roster with a non-``None``
      ``emitted_requires_edge_kind`` whose edge stops being emitted (an
      **delivered-but-unemitted** regression) fails the per-channel assert
      below.
    * A channel added to the roster's direct-citation set without a
      matching real edge in the fixture also fails, the same way.

    The `emitted_requires_edge_kind is not None` filter is itself asserted
    against the three known direct-citation channels so silently dropping a
    channel from that set (or expanding it without updating this test's own
    understanding) reddens too, rather than only shrinking the loop body.

    ``styleguide``/``toolguide`` (profile-field-only delivery, no DRG edge)
    and ``suggested_doctrine`` (transitive ``suggests``-reachability, not a
    direct citation edge) are deliberately excluded -- see
    ``_ProjectedChannel.emitted_requires_edge_kind``'s docstring for why
    those three have no citation-to-requires edge shape to check here.
    """
    direct_citation_channels = [channel for channel in _REAL_PROJECTED_CHANNELS if channel.emitted_requires_edge_kind is not None]
    assert {channel.name for channel in direct_citation_channels} == {
        "directive",
        "tactic",
        "operating-procedures",
    }, (
        "the set of _REAL_PROJECTED_CHANNELS entries carrying a non-None "
        "emitted_requires_edge_kind has drifted from the three known "
        "direct-citation channels -- update this test alongside the roster"
    )

    doctrine_root = tmp_path / "pack"
    (doctrine_root / "directives").mkdir(parents=True)
    (doctrine_root / "tactics").mkdir(parents=True)
    (doctrine_root / "procedures").mkdir(parents=True)
    (doctrine_root / "agent_profiles").mkdir(parents=True)
    (doctrine_root / "directives" / "bind-fixture.directive.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\ntitle: Bind Fixture Directive\n",
        encoding="utf-8",
    )
    (doctrine_root / "tactics" / "bind-fixture.tactic.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\nname: Bind Fixture Tactic\n",
        encoding="utf-8",
    )
    (doctrine_root / "procedures" / "bind-fixture.procedure.yaml").write_text(
        "schema_version: '1.0'\nid: bind-fixture\nname: Bind Fixture Procedure\npurpose: test\n",
        encoding="utf-8",
    )
    (doctrine_root / "agent_profiles" / "bind-fixture.agent.yaml").write_text(
        "\n".join(
            [
                "profile-id: bind-fixture",
                "name: Bind Fixture Profile",
                "directive-references:",
                "  - code: bind-fixture",
                "    name: Bind Fixture Directive",
                "    rationale: test",
                "tactic-references:",
                "  - id: bind-fixture",
                "collaboration:",
                "  operating-procedures: [bind-fixture]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    _nodes, edges = extract_artifact_edges(doctrine_root)
    edge_triples = {(edge.source, edge.target, edge.relation) for edge in edges}
    profile_urn = artifact_to_urn("agent_profile", "bind-fixture")

    for channel in direct_citation_channels:
        expected_edge = (
            profile_urn,
            artifact_to_urn(channel.emitted_requires_edge_kind, "bind-fixture"),
            Relation.REQUIRES,
        )
        assert expected_edge in edge_triples, (
            f"channel {channel.name!r} is delivery-attested in "
            "_REAL_PROJECTED_CHANNELS but extract_artifact_edges does not "
            f"emit its expected DRG edge {expected_edge}"
        )


# ---------------------------------------------------------------------------
# T011 — attest the pointer-only reason (AC-006): a test-pinned constant, not
# only a code docstring.
# ---------------------------------------------------------------------------


def test_pointer_only_reason_is_attested_non_empty() -> None:
    """The styleguide/toolguide pointer-only choice is a named, non-empty,
    importable constant — test-attested rather than only a docstring aside.
    """
    assert isinstance(_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON, str)
    assert _STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON.strip()
    assert "NFR-001" in _STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON
