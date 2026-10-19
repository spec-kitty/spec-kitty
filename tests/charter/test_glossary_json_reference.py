"""M4 (R3) — delivered glossary packs surface in the JSON ``references[]``.

A pre-merge review found a canonical-source drift: M4's delivery table marks
``GLOSSARY_PACK`` as delivered (slot ``glossary_packs``, activation-gated) and
the bootstrap-TEXT render emits it, but the JSON payload dropped it entirely —
glossary was not folded into ``build_disclosure_payload``'s ``extra_delivered``,
so a delivered glossary pack was silently absent from the action-scoped JSON.

The minimal, consistent fix (mirroring the deliberate ``asset`` asymmetry,
#3037) folds delivered glossary packs into the flat ``references[]`` link set via
``extra_delivered={"glossary_pack": bundle.glossary_pack_ids}`` — WITHOUT a typed
``glossary``/``glossary_packs`` array and WITHOUT a ``context_schema_version``
bump (``references`` is already a declared top-level key).

This module pins that contract two ways:

* directly over ``progressive_disclosure.build_disclosure_payload`` with a
  synthetic DRG carrying a ``glossary_pack:<id>`` node — the glossary id must
  appear in ``references[]`` (deterministic, no live charter required);
* over the live ``build_charter_context_json`` payload — a delivered glossary
  pack must NOT introduce a typed ``glossary``/``glossary_packs``/``assets``
  array, and ``context_schema_version`` must stay pinned to the tracked
  contract version (``1.4.0`` after the procedures, directives-source and diagnostics
  additions).

Red-first: on the base (glossary absent from ``extra_delivered``) the first
assertion — the glossary id in ``references[]`` — fails.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation import progressive_disclosure as pd
from charter.activation.context import build_charter_context_json
from charter.activation.context_contract import (
    CONTEXT_CONTRACT_TOP_LEVEL_KEYS,
    CONTEXT_SCHEMA_VERSION,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast]

_GLOSSARY_ID = "M4-GLOSSARY-PACK"
_ROOT_ID = "DIRECTIVE_ROOT"
_ROOT_URN = f"directive:{_ROOT_ID}"
_GLOSSARY_URN = f"glossary_pack:{_GLOSSARY_ID}"


def _node(urn: str) -> DRGNode:
    return DRGNode(urn=urn, kind=NodeKind(urn.split(":", 1)[0]))


def _synthetic_graph() -> DRGGraph:
    """A root directive that ``requires`` a delivered glossary pack.

    ``link_references`` names a delivered artefact only when a source in
    ``roots ∪ delivered ∪ bridge_urns`` has an inbound edge to it — so the
    glossary node needs an inbound edge from the root to appear in the link set.
    """
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-08-19T00:00:00Z",
        generated_by="test",
        nodes=[_node(_ROOT_URN), _node(_GLOSSARY_URN)],
        edges=[
            DRGEdge(
                source=_ROOT_URN,
                target=_GLOSSARY_URN,
                relation=Relation.REQUIRES,
                when=None,
                reason=None,
            )
        ],
    )


def test_delivered_glossary_pack_appears_in_references() -> None:
    """A ``glossary_pack`` id in ``extra_delivered`` is folded into ``references[]``."""
    payload = pd.build_disclosure_payload(
        repos_by_kind={},
        extra_delivered={"asset": [], "glossary_pack": [_GLOSSARY_ID]},
        merged=_synthetic_graph(),
        roots=[_ROOT_URN],
        include_all=False,
        body_of=None,
    )
    reference_ids = {ref["id"] for ref in payload["references"]}  # type: ignore[union-attr]
    assert _GLOSSARY_ID in reference_ids, "delivered glossary pack must be named in the JSON references[] link set"


def test_glossary_pack_is_reference_only_no_typed_array() -> None:
    """Folding glossary into references[] adds no typed ``glossary`` array."""
    payload = pd.build_disclosure_payload(
        repos_by_kind={},
        extra_delivered={"asset": [], "glossary_pack": [_GLOSSARY_ID]},
        merged=_synthetic_graph(),
        roots=[_ROOT_URN],
        include_all=False,
        body_of=None,
    )
    assert "glossary" not in payload
    assert "glossary_packs" not in payload
    assert "assets" not in payload
    # The only top-level key this slice introduces is the declared ``references``.
    assert set(payload) == {"references"}


def _write_charter_fixture(tmp_path: Path) -> None:
    """A minimal activation-provisioned charter repo (mirrors test_procedures_json_array)."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (charter_dir / "charter.md").write_text(
        textwrap.dedent(
            """\
            # Project Charter

            ## Policy Summary

            - Intent: deterministic glossary-reference fixture

            ## Terminology Canon

            - Canonical product term is "Mission".
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "governance.yaml").write_text(
        textwrap.dedent(
            """\
            charter:
              template_set: software-dev-default
              selected_paradigms: []
              selected_directives: []
              available_tools: []
            """
        ),
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text('schema_version: "1.0.0"\nreferences: []\n', encoding="utf-8")


def test_live_payload_has_no_typed_glossary_array_and_pinned_version(
    tmp_path: Path,
) -> None:
    """The live bootstrap payload keeps glossary reference-only; version unchanged."""
    _write_charter_fixture(tmp_path)
    payload = build_charter_context_json(tmp_path, action="implement", mission_type="software-dev")

    # No typed glossary/asset array is ever promoted (reference-only contract).
    assert "glossary" not in payload
    assert "glossary_packs" not in payload
    assert "assets" not in payload
    assert "glossary" not in CONTEXT_CONTRACT_TOP_LEVEL_KEYS
    assert "glossary_packs" not in CONTEXT_CONTRACT_TOP_LEVEL_KEYS

    # ``references`` is already a declared top-level key; the version tracks the
    # combined procedures + directives-source contract.
    assert "references" in payload
    assert "references" in CONTEXT_CONTRACT_TOP_LEVEL_KEYS
    assert CONTEXT_SCHEMA_VERSION == "1.4.0"
    assert payload["context_schema_version"] == "1.4.0"

    # No undeclared top-level key escaped the ledger after the glossary fold.
    assert set(payload) <= CONTEXT_CONTRACT_TOP_LEVEL_KEYS
