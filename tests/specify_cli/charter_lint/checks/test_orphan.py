"""Tests for OrphanChecker.

Uses duck-type SimpleNamespace stubs — the real doctrine DRG package is
not required.  All scenarios pass without WP5.1 being available.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specify_cli.charter_runtime.lint.checks.orphan import OrphanChecker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_node(urn: str, kind: str, label: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(urn=urn, kind=kind, label=label)


def _make_edge(source: str, target: str, relation: str) -> SimpleNamespace:
    return SimpleNamespace(source=source, target=target, relation=relation)


def _make_drg(nodes: list, edges: list) -> SimpleNamespace:
    node_map = {getattr(n, "urn", ""): n for n in nodes}

    def get_node(urn: str):
        return node_map.get(urn)

    return SimpleNamespace(nodes=nodes, edges=edges, get_node=get_node)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOrphanCheckerManufacturedDecay:
    """Verify that orphaned nodes generate findings."""

    def test_orphaned_directive_detected(self):
        directive_node = _make_node("directive:DIR-001", "directive", "DIR-001 Governance")
        drg = _make_drg(nodes=[directive_node], edges=[])
        findings = OrphanChecker().run(drg)
        assert len(findings) == 1
        f = findings[0]
        assert f.category == "orphan"
        assert f.type == "orphaned_directive"
        assert f.id == "directive:DIR-001"
        assert f.severity == "medium"

    def test_orphaned_glossary_scope_detected(self):
        gs_node = _make_node("glossary:workspace", "glossary_scope", "Workspace")
        drg = _make_drg(nodes=[gs_node], edges=[])
        findings = OrphanChecker().run(drg)
        assert any(f.type == "orphaned_glossary_scope" for f in findings)

    def test_feature_scope_propagated(self):
        directive_node = _make_node("directive:DIR-002", "directive")
        drg = _make_drg(nodes=[directive_node], edges=[])
        findings = OrphanChecker().run(drg, feature_scope="test-feature")
        assert findings[0].feature_id == "test-feature"

    def test_remediation_hint_present(self):
        directive_node = _make_node("directive:DIR-003", "directive")
        drg = _make_drg(nodes=[directive_node], edges=[])
        findings = OrphanChecker().run(drg)
        assert findings[0].remediation_hint is not None


class TestOrphanCheckerCleanDRG:
    """Verify that a well-connected DRG produces zero orphan findings."""

    def test_connected_directive_no_finding(self):
        """A directive referenced via a real ``Relation`` member is not orphaned.

        ``"governs"`` is not a member of the ``Relation`` enum (it was the
        pre-fix phantom relation, #2737) — use ``"requires"``, one of the
        relations the built-in doctrine layer actually emits toward
        directives.
        """
        directive_node = _make_node("directive:DIR-001", "directive", "DIR-001")
        referencing_node = _make_node("agent_profile:001", "agent_profile")
        edge = _make_edge("agent_profile:001", "directive:DIR-001", "requires")
        drg = _make_drg(nodes=[directive_node, referencing_node], edges=[edge])
        findings = OrphanChecker().run(drg)
        assert findings == []

    def test_reconciliation_directive_outgoing_edge_no_finding(self):
        """A directive with zero incoming edges is not orphaned if it carries an
        outgoing ``reconciles_tension`` edge.

        ``reconciles_tension`` always points FROM the active reconciliation
        artefact TO the tension pair it resolves, never the reverse, so an
        incoming-edge-only check would misfire on every reconciliation
        directive even though it is doing exactly its intended job.
        """
        reconciler_node = _make_node("directive:RECONCILE-001", "directive")
        tension_node = _make_node("directive:DIR-999", "directive")
        edge = _make_edge("directive:RECONCILE-001", "directive:DIR-999", "reconciles_tension")
        drg = _make_drg(nodes=[reconciler_node, tension_node], edges=[edge])
        findings = OrphanChecker().run(drg)
        # DIR-999 has no incoming edges of any kind and no outgoing
        # reconciles_tension edge -- it is still (correctly) flagged.
        assert [f.id for f in findings] == ["directive:DIR-999"]

    def test_adr_kind_no_longer_monitored(self):
        """The ``adr`` orphan rule is retired (#2737): a disconnected ``adr``
        node -- however disconnected -- never produces a finding, because no
        real ``Relation`` enum member ever backed ``"supersedes"`` or
        ``"references"`` and no ``adr`` node kind exists in the built-in
        layer today.
        """
        adr_node = _make_node("adr:ADR-001", "adr", "ADR-001 Use YAML")
        drg = _make_drg(nodes=[adr_node], edges=[])
        findings = OrphanChecker().run(drg)
        assert findings == []

    def test_connected_glossary_no_finding(self):
        gs_node = _make_node("glossary:workspace", "glossary_scope", "Workspace")
        action_node = _make_node("action:implement", "action")
        edge = _make_edge("action:implement", "glossary:workspace", "vocabulary")
        drg = _make_drg(nodes=[gs_node, action_node], edges=[edge])
        findings = OrphanChecker().run(drg)
        assert findings == []

    def test_non_monitored_kind_ignored(self):
        """Node kinds not in the orphan rules should produce no findings."""
        node = _make_node("action:some-action", "action", "Some Action")
        drg = _make_drg(nodes=[node], edges=[])
        findings = OrphanChecker().run(drg)
        assert findings == []


class TestOrphanCheckerMissingDRG:
    """Verify graceful handling of a missing/empty DRG."""

    def test_none_drg_returns_empty(self):
        findings = OrphanChecker().run(None)
        assert findings == []

    def test_empty_nodes_returns_empty(self):
        drg = _make_drg(nodes=[], edges=[])
        findings = OrphanChecker().run(drg)
        assert findings == []

    def test_drg_with_no_nodes_attr_returns_empty(self):
        drg = SimpleNamespace()  # no .nodes attribute
        findings = OrphanChecker().run(drg)
        assert findings == []


class TestOrphanCheckerBuiltInGraphExactSet:
    """T031 (FR-008/NFR-003, closes #2737): run the real check against the
    shipped built-in DRG and require *exact* set equality on the resulting
    ``orphaned_directive`` finding IDs.

    NFR-003 explicitly requires this to be an exact-equality assertion, not
    ``<=`` and not a ``len()`` bound: either of those weaker forms would also
    pass if T030 had accidentally over-deleted the ``directive`` rule and
    produced 0 findings, which is the exact failure mode FR-008 rules out
    ("Deleting the directive branch outright (yielding 0 findings) is NOT
    acceptable").
    """

    def test_orphaned_directive_findings_exact_set(self):
        """The shipped built-in DRG now has NO orphaned directives.

        #6017 (``97e42f00b2``) wired the last two — ``DIRECTIVE_035`` (via
        ``occurrence-classification-workflow``'s ``suggests`` edge) and
        ``DIRECTIVE_039`` (via ``deep-module-design``'s ``requires`` edge) —
        into the doctrine graph, an intended and accepted move (the cascade
        ratchet and changelog landed alongside it). Every built-in directive
        is now referenced, so the orphaned-directive set is empty.

        FR-008/NFR-003 still forbids a *vacuous* 0 (a deleted directive rule
        would also yield 0). The exact ``== set()`` here no longer carries that
        guarantee on its own, so the anti-vacuity half moved to the positive
        control below (and to
        ``TestOrphanCheckerManufacturedDecay.test_orphaned_directive_detected``).
        """
        from charter.offering.drg.loader import load_built_in_graph

        drg = load_built_in_graph()
        findings = OrphanChecker().run(drg)

        orphaned_directive_ids = {
            f.id.removeprefix("directive:") for f in findings if f.type == "orphaned_directive"
        }

        assert orphaned_directive_ids == set()

    def test_directive_orphan_rule_is_live_against_built_in_directives(self):
        """FR-008 anti-vacuity positive control for the (now-empty) exact set.

        Because the built-in orphaned-directive set is empty, ``== set()`` above
        can no longer tell "every directive is wired" apart from "the directive
        orphan rule was accidentally deleted" — the exact failure mode FR-008
        rules out. This proves the rule is still live against the *real*
        built-in directive population: stripping every edge makes the checker
        flag all of those directives, so an empty result above can only mean the
        directives are referenced, never that the rule stopped firing.
        """
        from charter.offering.drg.loader import load_built_in_graph

        drg = load_built_in_graph()
        directive_nodes = [
            node
            for node in drg.nodes
            if getattr(getattr(node, "kind", None), "value", str(getattr(node, "kind", ""))) == "directive"
        ]
        assert directive_nodes, "the built-in graph must contain directive nodes"

        edgeless = _make_drg(nodes=directive_nodes, edges=[])
        flagged = {f.id for f in OrphanChecker().run(edgeless) if f.type == "orphaned_directive"}

        assert flagged == {node.urn for node in directive_nodes}

    def test_no_orphaned_adr_findings_in_built_in_graph(self):
        """The retired ``adr`` rule must never surface a finding (#2737)."""
        from charter.offering.drg.loader import load_built_in_graph

        drg = load_built_in_graph()
        findings = OrphanChecker().run(drg)

        assert not any(f.type == "orphaned_adr" for f in findings)
