"""FR-009 tension-arbiter fields on ``_ActionDoctrineBundle`` (WP02).

``resolve_context`` (``charter.offering.drg.query``) now annotates co-delivered
``in_tension_with`` pairs with their reconciler; ``_load_action_doctrine_bundle``
must forward that annotation onto the delivered bundle verbatim -- see
``tests/doctrine/drg/test_tension_arbiters.py`` for the ``resolve_context``-level
coverage this file assumes and does not re-derive.

Follows the ``charter.activation._drg_helpers.load_validated_graph`` patch pattern from
``tests/charter/test_activation_consumers.py`` so the graph is hermetic (no
dependency on the shipped corpus's current shape) while exercising the real
``_load_action_doctrine_bundle`` -> ``resolve_context`` wiring end to end.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.action_doctrine_bundle import _load_action_doctrine_bundle
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast]

_ACTION_URN = "action:software-dev/implement"
_DIRECTIVE_024 = "directive:DIRECTIVE_024"
_DIRECTIVE_025 = "directive:DIRECTIVE_025"
_RECONCILER = "directive:RECONCILE_CHANGE_SCOPE_TENSIONS"
_UNARBITRATED_A = "directive:DIRECTIVE_TENSION_A"
_UNARBITRATED_B = "directive:DIRECTIVE_TENSION_B"


def _tension_graph() -> DRGGraph:
    """Mirrors the real ``024``/``025``/``reconcile-change-scope-tensions``
    corpus shape (see
    ``packs/built-in/directives/reconcile-change-scope-tensions.directive.yaml``
    and ``src/charter/offering/drg/migration/hand_authored_overlay.py``), plus
    an unreconciled pair to exercise ``unarbitrated_tensions``.
    """
    nodes = [
        DRGNode(urn=_ACTION_URN, kind=NodeKind.ACTION),
        DRGNode(urn=_DIRECTIVE_024, kind=NodeKind.DIRECTIVE),
        DRGNode(urn=_DIRECTIVE_025, kind=NodeKind.DIRECTIVE),
        DRGNode(urn=_RECONCILER, kind=NodeKind.DIRECTIVE),
        DRGNode(urn=_UNARBITRATED_A, kind=NodeKind.DIRECTIVE),
        DRGNode(urn=_UNARBITRATED_B, kind=NodeKind.DIRECTIVE),
    ]
    edges = [
        DRGEdge(source=_ACTION_URN, target=_DIRECTIVE_024, relation=Relation.SCOPE),
        DRGEdge(source=_ACTION_URN, target=_DIRECTIVE_025, relation=Relation.SCOPE),
        DRGEdge(source=_ACTION_URN, target=_UNARBITRATED_A, relation=Relation.SCOPE),
        DRGEdge(source=_ACTION_URN, target=_UNARBITRATED_B, relation=Relation.SCOPE),
        DRGEdge(source=_DIRECTIVE_024, target=_DIRECTIVE_025, relation=Relation.IN_TENSION_WITH),
        DRGEdge(source=_UNARBITRATED_A, target=_UNARBITRATED_B, relation=Relation.IN_TENSION_WITH),
        DRGEdge(source=_RECONCILER, target=_DIRECTIVE_024, relation=Relation.RECONCILES_TENSION),
        DRGEdge(source=_RECONCILER, target=_DIRECTIVE_025, relation=Relation.RECONCILES_TENSION),
    ]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-08-29T00:00:00+00:00",
        generated_by="test_action_bundle_tension_arbiters",
        nodes=nodes,
        edges=edges,
    )


def test_bundle_carries_tension_arbiters_and_unarbitrated_tensions(tmp_path: Path) -> None:
    with patch(
        "charter.activation._drg_helpers.load_validated_graph",
        return_value=_tension_graph(),
    ):
        bundle = _load_action_doctrine_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type="software-dev",
            pack_context=None,
        )

    assert bundle.tension_arbiters == ((_RECONCILER, (_DIRECTIVE_024, _DIRECTIVE_025)),)
    assert bundle.unarbitrated_tensions == ((_UNARBITRATED_A, _UNARBITRATED_B),)


def test_bundle_tension_fields_are_hashable_tuples(tmp_path: Path) -> None:
    """Brownfield constraint (tasks.md WP02 T2): tuples, not dict/list, so the
    frozen ``_ActionDoctrineBundle`` construction site stays valid and any
    hashable-context use of the bundle's fields does not raise."""
    with patch(
        "charter.activation._drg_helpers.load_validated_graph",
        return_value=_tension_graph(),
    ):
        bundle = _load_action_doctrine_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type="software-dev",
            pack_context=None,
        )

    assert isinstance(bundle.tension_arbiters, tuple)
    assert isinstance(bundle.unarbitrated_tensions, tuple)
    for arbiter, arbitrated in bundle.tension_arbiters:
        assert isinstance(arbiter, str)
        assert isinstance(arbitrated, tuple)
    for pair in bundle.unarbitrated_tensions:
        assert isinstance(pair, tuple)
        assert len(pair) == 2


def test_typeless_mission_bundle_has_empty_tension_fields(tmp_path: Path) -> None:
    """A typeless mission skips DRG action resolution entirely (FR-003a) --
    the tension fields must default to ``()``, never raise or infer."""
    bundle = _load_action_doctrine_bundle(
        repo_root=tmp_path,
        action="implement",
        effective_depth=2,
        mission_type=None,
        feature_dir=None,
        pack_context=None,
    )

    assert bundle.mission == ""
    assert bundle.tension_arbiters == ()
    assert bundle.unarbitrated_tensions == ()
