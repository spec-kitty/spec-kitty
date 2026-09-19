"""Invariance assertions for the WP04 extractor re-point (mission-step-authority).

``extract_mission_type_edges`` (``doctrine.drg.migration.extractor``) was
re-pointed from a raw ``data.get("action_sequence")`` YAML read to the WP02
projection seam (``doctrine.missions.step_projection.project_action_sequence``,
resolved builtin-only via ``MissionStepRepository``). This module pins the
three invariants that re-point must hold (T012, FR-004/FR-010):

1. **DRG 0-delta (NFR-002)** -- the regenerated graph still counts 280 nodes /
   757 edges / 10 orphans, and is byte-identical to the shipped graph
   (:func:`~doctrine.drg.loader.load_built_in_graph`).
2. **No edge for non-sequence steps** -- a step with ``in_action_sequence:
   false`` (``retrospect``, and software-dev's other 6 non-sequence steps)
   never mints a ``mission_type --requires--> action`` edge.
3. **Projection == pre-mission action_sequence** -- the projected edge set for
   every shipped mission type matches the edge set the raw YAML
   ``action_sequence`` would have produced (byte-for-byte, order preserved).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.migration.extractor import (
    extract_mission_type_edges,
    generate_graph,
)
from charter.offering.drg.migration.hand_authored_overlay import (
    HAND_AUTHORED_EDGES,
    generate_reference_graph_with_overlay,
)
from charter.offering.drg.models import Relation
from charter.offering.missions.mission_step_repository import MissionStepRepository
from tests.doctrine._builtin_inventory import (
    pure_builtin_node_count,
    shipped_builtin_node_count,
)

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
DOCTRINE_ROOT: Path = _REPO_ROOT / "src" / "charter" / "offering"

#: HISTORICAL LEDGER (#3234). The node/edge counts below are now DERIVED from the
#: ``packs/built-in`` filesystem inventory (see ``_EXPECTED_NODE_COUNT`` at the end
#: of this block and ``tests/doctrine/_builtin_inventory.py``), so this delta-by-
#: delta journal is no longer a live frozen contract that every doctrine addition
#: must append to. It is retained as the audit trail of how the corpus reached its
#: present size and as the authority other tests cite for orphan-membership,
#: relation-histogram, and reachability moves. The bare ``_EXPECTED_NODE_COUNT ->``
#: / ``_EXPECTED_EDGE_COUNT ->`` count arithmetic in entries below is frozen at the
#: values current when each entry landed; do not hand-reconcile it going forward --
#: the derived assertion and ``regenerate-graph --check`` are the live guards.
#:
#: Baseline DRG counts pinned by the mission-step-authority mission (NFR-002).
#: Any drift here is a defect, not an accepted change -- see WP04's Definition
#: of Done in kitty-specs/mission-step-authority-01KXNZMT/tasks/WP04-extractor-repoint.md.
#: WP06 (mission-step-creatability-01KXQA6R, S-C / #2724) grafts the
#: mission_type->step->template chain into the shipped graph: 8 mission-qualified
#: template nodes (software-dev 2 + documentation/research/plan x {spec,plan})
#: and 8 matching action->template ``instantiates`` edges (N=8, computed from
#: the authored ``iter_template_refs`` refs, not hand-picked). Every new
#: template node gets an ``instantiates`` in-edge (S-C adds 0 orphans).
#: Re-baselined after rebase onto upstream/main: the base advanced by +1 node
#: / +1 orphan -- ``procedure:red-main-release-discipline`` was present in the
#: upstream doctrine source but missing from upstream's shipped graph (a
#: pre-existing upstream freshness drift this regeneration incidentally fixes).
#: So the counts are (upstream-source-truth 281/757/11) + S-C's intentional
#: +8/+8/+0 = 289/765/11.
#:
#: Re-baselined for WP03 of doctrine-tension-edges-01KY1WPC: retiring the
#: contradiction-declaration field removes the 6 phantom paradigm/tactic-kind
#: nodes and 10 mis-minted ``replaces`` edges the field used to produce (2
#: directive<->directive + 8 paradigm->{paradigm,tactic}), and the new
#: ``reconcile-change-scope-tensions`` directive (a plain built-in directive
#: with no ordinary ``tactic_refs``/``references``) adds one orphan of its own
#: in a PURE regeneration -- its only edges are the hand-authored
#: ``reconciles_tension`` edges the extractor cannot mint (see
#: ``doctrine.drg.migration.hand_authored_overlay``). So a bare
#: ``generate_graph`` run yields 289 - 6 + 1 = 284 nodes,
#: 765 - 10 = 755 edges, 11 - 1 + 2 = 12 orphans.
#:
#: Mission glossary-pack-doctrine-kind-01KY30SW (WP03) then adds the built-in
#: ``spec-kitty-core`` glossary pack's own source node
#: (``glossary_pack:spec-kitty-core``, emitted by the
#: ``_emit_glossary_pack_nodes`` block in ``extract_artifact_edges``). Mission
#: A ships zero outbound references for the pack (enforcement fields are inert
#: until Mission B), so this is +1 node / +0 edges / +1 orphan (the new node
#: has no edges yet, same shape as any freshly-registered kind with no
#: cross-references). Both changes compose over the same base:
#: 284/755/12 + 1/0/1 = 285/755/13 (verified by regenerating the DRG against
#: the current base -- see the base-divergence reconciliation).
#:
#: Two independent changes compose over the same 285/755/13 base:
#: (1) upstream's ``git-worktree-pr-workflow`` toolguide (agent-knowledge-
#:     canonical-homes) adds +1 node / +2 edges / +0 orphans -- its two
#:     ``suggests`` refs (``clean-linear-commit-history``,
#:     ``pr-agent-worktree-isolation``) are ordinary outbound edges and both
#:     targets already had edges: 285/755/13 + 1/2/0 = 286/757/13.
#: (2) Mission doctrine-controlled-transition-gates (epic #2535 half A, WP09)
#:     teaches the extractor to mint one ``mission_step_contract:<mission>/<action>``
#:     node per built-in step contract (``missions/built_in_step_contracts/
#:     *.step-contract.yaml``) so the pre-review activation join resolves ACTIVE.
#:     17 shipped contracts (documentation x7 + research x5 + software-dev x5),
#:     each edge-less (the MSC fragment ships ``edges: []``): +17 nodes / +0 edges
#:     / +17 orphans.
#: Composed: 285/755/13 + 1/2/0 + 17/0/17 = 303/757/30.
#: (3) Mission ship-structural-lint-as-asset: the common-docs structural lint is
#:     relocated into ``assets/built-in`` as the first shipped doctrine ASSET,
#:     so the extractor mints one edge-less ``asset:common-docs-structural-lint``
#:     node (the asset fragment ships ``edges: []``): +1 node / +0 edges /
#:     +1 orphan. Composed: 303/757/30 + 1/0/1 = 304/757/31.
#: (4) ADR 2026-07-26-2 (doctrine artefact pack layout): the PowerShell toolguide
#:     and its 245-line guide are promoted from ``toolguides/`` into the pack
#:     layer ``toolguides/built-in/``. It had sat outside ``<type>/<pack>/`` since
#:     the framework's first commit, so node discovery never saw it and the
#:     toolguide was unreachable; promotion mints one edge-less
#:     ``toolguide:powershell-syntax`` node: +1 node / +0 edges / +1 orphan.
#:     The same change handles nine mispacked artefacts: **eight are DELETED**
#:     (three byte-identical duplicates, two stale divergent copies, three
#:     content-free seed stubs) and the ninth is the promotion above -- it was
#:     moved, not deleted. The eight deletions have **zero** count impact: none
#:     of them was ever a node, which is precisely why they were dead.
#:     Composed: 304/757/31 + 1/0/1 = 305/757/32.
#:     (An earlier revision of this ledger said "DELETES nine ... five duplicates,
#:     four seed stubs". Both sub-counts were wrong -- git shows 8 deletions and
#:     3 renames -- while the numeric assertions below stayed green. NFR-006 makes
#:     this prose a contract precisely so the counts stay auditable; it is corrected
#:     here rather than quietly, because a wrong ledger is what NFR-006 forbids.)
#: (5) Mission doctrine-silence-guards-01KYFV7Q, WP09 (FR-012): a
#:     **relation-only change at constant cardinality**, and the mission's single
#:     ledgered exception to its own NFR-004 "no graph content change".
#:     ``agent_profile:doctrine-daphne --applies--> procedure:onboard-external-
#:     agent-to-pack`` is retyped to ``requires`` in ``_CURATED_ARTIFACT_EDGES``.
#:     +0 nodes / +0 edges / +0 orphans -- the counts below are deliberately
#:     UNCHANGED, which is exactly why the change is ledgered here: a cardinality
#:     baseline cannot see it, so without this entry a live traversal result would
#:     have moved with every golden count still green. What DID move is the
#:     relation histogram: ``applies`` 1 -> 0, ``requires`` 259 -> 260 (shipped
#:     graph, i.e. including the hand-authored overlay).
#:     Why: ``applies`` was that procedure's only inbound edge and no traversal
#:     follows ``applies``, so activating the profile could not reach the operating
#:     procedure it declares. Post-change ``cascade_activation_targets`` from
#:     ``agent_profile:doctrine-daphne`` reaches it -- and the activation set grows
#:     by FOUR artifacts, not one: the procedure (procedures 5 -> 6) plus its own
#:     three output templates ``decomposition-table``, ``onboarded-artifact-set``
#:     and ``source-agent-dossier`` (templates 6 -> 9). Recording only the procedure
#:     would understate the traversal move this entry exists to make visible.
#:     Orphan count is unaffected
#:     because ``_orphan_urns`` counts incidence, not relation.
#:     Guarded by ``tests/architectural/test_no_authored_applies_edge.py``.
#: (6) Landing pass for PR #3007, operator ruling 2026-07-28 (#3009 remedy 4):
#:     ``toolguide:rtk-search-tooling`` is REMOVED outright -- artefact, its
#:     245-line guide, its entry in the default charter pack's toolguide
#:     activations, and this repository's own activation. RTK will not be pushed
#:     to the userbase: it is difficult to set up correctly and can significantly
#:     affect test execution, so shipping an activated toolguide for it is a
#:     liability rather than an oversight to be wired.
#:     -1 node / +0 edges / -1 orphan. Composed: 305/757/32 - 1/0/1 = 304/757/31.
#:     It was one of the nine ``_ACTIVATED_BUT_ORPHANED`` entries below; the
#:     other eight are oversights and are wired rather than deleted, so this is
#:     the only member that leaves by deletion. The node carried no edges in
#:     either direction (verified: its sole graph appearance was its own node
#:     line), so nothing else in the graph moves.
#: (7) Same ruling, the other half of #3009 remedy 4: the eight remaining
#:     ``_ACTIVATED_BUT_ORPHANED`` artefacts are WIRED via
#:     ``_CURATED_ARTIFACT_EDGES``. The charter activated them while the graph
#:     gave them no inbound edge, so cascade reached none of them -- the same
#:     failure WP09 fixed once (entry 5), with no edge at all rather than an
#:     unfollowed relation. +0 nodes / +7 edges / -8 orphans.
#:     Seven new edges de-orphan seven targets; the EIGHTH artefact,
#:     ``directive:DIRECTIVE_035``, leaves the orphan set without an edge of its
#:     own by becoming the SOURCE of one (``_orphan_urns`` counts incidence, so a
#:     first outbound edge de-orphans just as an inbound one does). That is why
#:     the orphan delta is -8 while the edge delta is +7.
#:     Composed: 304/757/31 + 0/+7/-8 = 304/764/23.
#:     Each edge follows an existing (source_kind -> target_kind, relation)
#:     pattern in the shipped graph; ``requires`` where the source mandates the
#:     target, ``suggests`` where it recommends.
#:     Review corrected WHICH artefacts, not how many: the invented
#:     onboarding->skill-styleguide edge was dropped and an
#:     ``atomic-design-review-checklist -> atomic-design`` edge added in its
#:     place, and ``DIRECTIVE_028 -> no-parallel-duplicate-test-runs`` was
#:     re-pointed to ``DIRECTIVE_030`` (028 scopes tool SELECTION; the tactic is
#:     a discipline on how a suite is RUN). Totals are unchanged; only
#:     ``_ACTIVATED_BUT_ORPHANED``'s membership moved. A bare cardinality
#:     could not have shown that swap -- which is the case for naming members.
#:     ``styleguide:deployable-skill-authoring`` is now the one deliberately NOT
#:     wired -- see ``_ACTIVATED_BUT_ORPHANED``.
#: (8) Mission doctrine-delivery-reachability-01KYMXD6, WP09 (T050, FR-015): one
#:     hand-authored SCOPE edge, ``action:documentation/generate --scope-->
#:     directive:DIRECTIVE_042``, added to ``HAND_AUTHORED_EDGES``. It is the
#:     REACHING edge for the common-docs cluster: DIRECTIVE_042 and the asset /
#:     styleguide / four common-docs tactics it heads were all measured
#:     action-UNREACHABLE (a strongly-connected island no action scoped), so the
#:     four pre-existing ``requires`` edges into ``asset:common-docs-structural-lint``
#:     de-orphaned it by incidence while it still reached nobody. This edge makes
#:     042 action-reachable, delivering the cluster transitively.
#:     +0 nodes / +1 edge (overlay) / +0 orphans. The PURE golden counts below are
#:     UNCHANGED -- the edge is overlay-authored, not extractor-derived -- so
#:     ``test_shipped_graph_is_fresh_and_byte_identical`` stays green because it
#:     asserts ``_EXPECTED_EDGE_COUNT + len(HAND_AUTHORED_EDGES)`` (764 + 18 = 782,
#:     was 764 + 17 = 781) against the regenerated shipped graph. The moved counts
#:     are: shipped edges 781 -> 782; ``len(HAND_AUTHORED_EDGES)`` 17 -> 18; the
#:     ``scope`` relation histogram 157 -> 158 (pinned by
#:     ``tests/architectural/test_no_authored_applies_edge.py`` and mirrored in
#:     ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md``,
#:     both updated). Orphan sets are unaffected: 042 and the asset were already
#:     edge-incident. The per-channel reachability move (six artefacts leave
#:     ``_ACTION_UNREACHABLE_D1``/``D2``) is ledgered in
#:     ``tests/doctrine/drg/test_reachability.py``. Canonical home / B2 handoff:
#:     the scope edge belongs in the documentation step-contract action index;
#:     mission B2 migrates it when it retires this overlay generator. See
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (9) #3063 family-A (DDD family), operator interview outcome: FOURTEEN
#:     hand-authored edges added to ``HAND_AUTHORED_EDGES`` (hub
#:     ``paradigm:domain-driven-design``). One reaching ``scope`` edge
#:     ``action:software-dev/specify --scope--> paradigm:domain-driven-design``;
#:     ten ``requires`` edges from the DDD paradigm to its genuine family members
#:     (bounded-context-identification / context-mapping-classification /
#:     context-boundary-inference / bounded-context-canvas-fill /
#:     strategic-domain-classification / aggregate-boundary-design /
#:     entity-value-object-classification / domain-event-capture /
#:     anti-corruption-layer / styleguide:aggregate-design-rules -- each attests
#:     DDD in its OWN text); and three composition-only ``suggests`` edges from
#:     agent profiles (architect-alphonso, paula-patterns, randy-reducer) to the
#:     paradigm. +0 nodes / +14 edges (overlay) / +0 orphans -- every endpoint
#:     was already edge-incident, so the orphan sets above are unchanged. The
#:     PURE golden counts below are UNCHANGED (overlay-authored, not extractor-
#:     derived), so ``test_shipped_graph_is_fresh_and_byte_identical`` stays green:
#:     it asserts ``_EXPECTED_EDGE_COUNT + len(HAND_AUTHORED_EDGES)`` (764 + 32 =
#:     796, was 764 + 18 = 782). Moved counts: shipped edges 782 -> 796;
#:     ``len(HAND_AUTHORED_EDGES)`` 18 -> 32; relation histogram ``requires``
#:     262 -> 272, ``suggests`` 337 -> 340, ``scope`` 158 -> 159 (all three pinned
#:     by ``tests/architectural/test_no_authored_applies_edge.py`` and mirrored in
#:     ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md``,
#:     all updated). The per-channel reachability move (twelve artefacts leave
#:     ``_ACTION_UNREACHABLE_D1``/``D2``; four leave ``_PROFILE_RESCUES``) is
#:     ledgered in ``tests/doctrine/drg/test_reachability.py``. NOTE the specify
#:     edge is ``scope`` not the ``suggests`` the #3063 wiring table named: a
#:     ``suggests`` edge sourced at an action node is measured inert (see the
#:     wiring-table doc); only ``scope`` delivers, per the WP09 precedent.
#:     EXCLUDED as non-attested: ``tactic:reference-architectural-patterns`` (its
#:     own text is general reference-architecture selection, not DDD) and the
#:     state/UI tactics compositional-stream-boundaries / cross-cutting-state-via-
#:     store / atomic-state-ownership. DEFERRED: the DDD<->documentation edge (B1).
#: (10) #3063 family-B (REFACTORING family), operator interview outcome: a NEW
#:     built-in directive ``directive:DISCIPLINED_REFACTORING``
#:     (``directives/built-in/disciplined-refactoring.directive.yaml``) plus
#:     FOURTEEN hand-authored ``suggests`` edges added to ``HAND_AUTHORED_EDGES``.
#:     The directive carries NO inline references (relationships are edges, per the
#:     frozen-legacy references surface), so a PURE ``generate_graph`` run mints its
#:     node but zero edges -- exactly the ``RECONCILE_CHANGE_SCOPE_TENSIONS`` shape.
#:     So the PURE golden counts move +1 NODE / +0 edges: ``_EXPECTED_NODE_COUNT``
#:     304 -> 305, ``_EXPECTED_EDGE_COUNT`` UNCHANGED at 764. In a pure run the
#:     directive is an ORPHAN (its only edges are overlay-authored), so it joins
#:     ``_AWAITING_REFERENCES`` (pure orphans 23 -> 24) and, because the overlay
#:     wires it (7 outbound directive->tactic + 7 inbound profile->directive),
#:     ``_ORPHANS_RESOLVED_BY_OVERLAY`` (2 -> 3); shipped orphans stay 21.
#:     The fourteen overlay edges are ALL ``suggests``: 7 from the directive to the
#:     refactoring tactics (encapsulate-record / encapsulate-variable /
#:     extract-first-order-concept / move-field / move-method /
#:     state-pattern-for-behavior / strangler-fig), each with a per-tactic ``when``
#:     derived from the tactic's OWN applicability text; and 7 from the
#:     implementer-role agent profiles (frontend-freddy, generic-agent,
#:     implementer-ivan, java-jenny, node-norris, python-pedro, randy-reducer) to
#:     the directive. Moved counts: shipped nodes 310 -> 311; shipped edges
#:     796 -> 810; ``len(HAND_AUTHORED_EDGES)`` 32 -> 46; relation histogram
#:     ``suggests`` 340 -> 354 (``requires``/``scope`` UNCHANGED) -- pinned by
#:     ``tests/architectural/test_no_authored_applies_edge.py`` and mirrored in
#:     ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md``,
#:     both updated. This family is INERT: the directive is not charter-activated
#:     (so it never enters the reachability pins' ``_activated()`` universe) and
#:     both edge legs are ``suggests`` on channels that do not follow ``suggests``
#:     into delivery, so ``_ACTION_UNREACHABLE_D1``/``D2``, ``_PROFILE_UNREACHABLE``
#:     and ``_PROFILE_RESCUES`` in ``tests/doctrine/drg/test_reachability.py`` are
#:     UNCHANGED (measured, not assumed). The seven refactoring tactics remain in
#:     the delivery-reachability DEFERRED set (topology authored, delivery pending a
#:     profile-channel walk update). URN CASING: the wiring named
#:     ``directive:disciplined-refactoring``; the Directive model's ``id`` pattern +
#:     ``id_normalizer`` upper-case it, so the canonical URN is
#:     ``directive:DISCIPLINED_REFACTORING`` (the ``RECONCILE_CHANGE_SCOPE_TENSIONS``
#:     precedent). See ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (11) #3063 family-C (ARCHITECTURE-DOCS / DIAGRAMMING family), operator interview
#:     outcome: a NEW built-in directive ``directive:USE_C4_MODEL_TECHNIQUES``
#:     (``directives/built-in/use-c4-model-techniques.directive.yaml``) plus NINE
#:     hand-authored ``suggests`` edges added to ``HAND_AUTHORED_EDGES``. The
#:     directive carries NO inline references (relationships are edges), so a PURE
#:     ``generate_graph`` run mints its node but zero edges -- the
#:     ``DISCIPLINED_REFACTORING`` / ``RECONCILE_CHANGE_SCOPE_TENSIONS`` shape. So the
#:     PURE golden counts move +1 NODE / +0 edges: ``_EXPECTED_NODE_COUNT`` 305 -> 306,
#:     ``_EXPECTED_EDGE_COUNT`` UNCHANGED at 764. In a pure run the directive is an
#:     ORPHAN (its only edges are overlay-authored), so it joins
#:     ``_AWAITING_REFERENCES`` (pure orphans 24 -> 25) and, because the overlay wires
#:     it (7 outbound directive->member + 1 outbound directive->DDD + 1 inbound
#:     architect-alphonso->directive), ``_ORPHANS_RESOLVED_BY_OVERLAY`` (3 -> 4);
#:     shipped orphans stay 21. The nine overlay edges are ALL ``suggests``: 7 from
#:     the directive to the attested architecture-documentation techniques
#:     (paradigm:c4-incremental-detail-modeling, tactic:c4-zoom-in-architecture-
#:     documentation, tactic:architecture-diagram-review-checklist,
#:     toolguide:mermaid-diagramming, toolguide:plantuml-diagramming,
#:     procedure:drill-down-documentation, tactic:code-documentation-analysis), each
#:     with a per-member ``when`` grounded in the member's OWN purpose/scope text; 1
#:     the reinforcement bridge to ``paradigm:domain-driven-design`` (the attested
#:     "supporting" leg — ``suggests`` is the closest attested relation, no new kind
#:     invented); and 1 from ``agent_profile:architect-alphonso`` to the directive.
#:     Moved counts: shipped nodes 311 -> 312; shipped edges 810 -> 819;
#:     ``len(HAND_AUTHORED_EDGES)`` 46 -> 55; relation histogram ``suggests``
#:     354 -> 363 (``requires``/``scope`` UNCHANGED) -- pinned by
#:     ``tests/architectural/test_no_authored_applies_edge.py`` and mirrored in
#:     ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md``,
#:     both updated. This family is INERT: the directive is not charter-activated (so
#:     it never enters the reachability pins' ``_activated()`` universe) and all nine
#:     edges are ``suggests`` on channels that do not follow ``suggests`` into
#:     delivery, so ``_ACTION_UNREACHABLE_D1``/``D2``, ``_PROFILE_UNREACHABLE`` and
#:     ``_PROFILE_RESCUES`` in ``tests/doctrine/drg/test_reachability.py`` are
#:     UNCHANGED (measured, not assumed). The DDD-bridge edge is INBOUND to the
#:     already-action-reachable DDD paradigm (family-A), so it delivers nothing new.
#:     The seven architecture-doc technique members remain in the delivery-
#:     reachability DEFERRED set (topology authored, delivery pending fast-follow).
#:     EXCLUDED as non-attested: ``procedure:documentation-gap-prioritization`` (its
#:     own text triages documentation gaps by user impact across all doc types -- a
#:     documentation-project-management technique, not a C4 / architecture-doc one).
#:     URN CASING: the wiring named ``directive:use-c4-model-techniques``; the
#:     Directive model's ``id`` pattern + ``id_normalizer`` upper-case it, so the
#:     canonical URN is ``directive:USE_C4_MODEL_TECHNIQUES``. See
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (12) #3063 family-D (TESTING / BDD / MUTATION family), operator interview
#:     outcome + ACCEPT-DELIVERY ruling (2026-07-29). FIVE new built-in artefacts
#:     plus FIFTY-FOUR hand-authored ``suggests`` edges. The artefacts:
#:     ``directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY``
#:     (``directives/built-in/use-mutation-testing-to-validate-test-quality.
#:     directive.yaml``), ``styleguide:quadruple-a-test-format``,
#:     ``styleguide:given-when-then-authoring``, ``toolguide:sonar`` (+ SONAR.md)
#:     and ``toolguide:gherkin`` (+ GHERKIN.md). Each carries NO inline references
#:     (relationships are edges), so a PURE ``generate_graph`` run mints five nodes
#:     but zero edges. PURE golden counts move +5 NODES / +0 edges:
#:     ``_EXPECTED_NODE_COUNT`` 306 -> 311, ``_EXPECTED_EDGE_COUNT`` UNCHANGED at
#:     764. In a pure run all five are ORPHANS (their only edges are overlay-
#:     authored), so they join ``_AWAITING_REFERENCES`` (pure orphans 25 -> 30) and,
#:     because the overlay wires every one of them, ``_ORPHANS_RESOLVED_BY_OVERLAY``
#:     (4 -> 9); shipped orphans stay 21.
#:     Unlike families B/C, family D is REACHABILITY-AFFECTING (operator ACCEPT-
#:     DELIVERY), because two hubs are EXISTING action-scoped directives:
#:     ``directive:DIRECTIVE_034`` and ``directive:DIRECTIVE_030`` are both
#:     ``scope``-linked from ``action:software-dev/implement`` and
#:     ``action:software-dev/review``, so ``resolve_context`` walks their outbound
#:     ``suggests`` and DELIVERS the targets at implement/review. The 54 edges: 7
#:     from DIRECTIVE_034 (BDD/ATDD family; DELIVERS 5 activated members + the 2 new
#:     BDD artefacts); 2 from ``paradigm:brownfield-onboarding`` (DELIVERS at d=2
#:     only, via a <=2-hop suggests chain); 4 from the new mutation directive
#:     (INERT — new hub not action-scoped); 5 from DIRECTIVE_030 + 3 from
#:     ``directive:DIRECTIVE_041`` (test-quality fan-out split per fit; 030 DELIVERS,
#:     041 INERT as it is not action-scoped); 32 profile->hub edges (INERT in the
#:     profile channel); and 1 inert ``architect-alphonso --suggests-->
#:     event-storming-discovery``. Moved counts: shipped nodes 312 -> 317; shipped
#:     edges 819 -> 873; ``len(HAND_AUTHORED_EDGES)`` 55 -> 109; relation histogram
#:     ``suggests`` 363 -> 417 (``requires`` 272 / ``scope`` 159 UNCHANGED) -- pinned
#:     by ``tests/architectural/test_no_authored_applies_edge.py`` and mirrored in
#:     ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md``,
#:     both updated. The per-channel reachability move is ledgered in
#:     ``tests/doctrine/drg/test_reachability.py``: ``_ACTION_UNREACHABLE_D1`` 67 ->
#:     60, ``_ACTION_UNREACHABLE_D2`` 60 -> 50, ``_ACTION_D1_D2_SPREAD`` 7 -> 10,
#:     ``_PROFILE_RESCUES`` 4 -> 2 (``_PROFILE_UNREACHABLE`` UNCHANGED at 153). URN
#:     CASING: the wiring named the mutation hub lower-kebab; the Directive model's
#:     ``id`` pattern + ``id_normalizer`` upper-case it, so the canonical URN is
#:     ``directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY``. See
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (13) #3063 family-E (ANALYSIS / TERMINOLOGY / REASONS-CANVAS family), operator
#:     interview outcome: NINE hand-authored ``suggests`` edges added to
#:     ``HAND_AUTHORED_EDGES`` and ZERO new artefacts -- every endpoint already
#:     exists, so the PURE golden counts below are UNCHANGED
#:     (``_EXPECTED_NODE_COUNT`` 311, ``_EXPECTED_EDGE_COUNT`` 764). The nine
#:     edges: 1 from ``agent_profile:architect-alphonso`` to
#:     ``styleguide:reasons-canvas-writing`` (E1, canvas-writing only); 2
#:     reinforcement edges from ``tactic:terminology-extraction-mapping`` to
#:     ``paradigm:domain-driven-design`` and ``paradigm:brownfield-onboarding``
#:     (E2 group 1 -- the only terminology/analysis tactic whose OWN text attests a
#:     paradigm); 3 glossary/language links (``toolguide:contextive`` ->
#:     ``tactic:glossary-curation-interview`` and ``tactic:language-driven-design``;
#:     ``tactic:terminology-extraction-mapping`` -> ``tactic:glossary-curation-
#:     interview`` -- the fourth implied edge, terminology-extraction-mapping ->
#:     language-driven-design, was OMITTED as it already exists extractor-minted
#:     from that tactic's own ``references:`` block); and 3 tool-support edges
#:     (``toolguide:terminology-guard`` -> ``tactic:canonical-source-unification``
#:     and ``tactic:occurrence-classification-workflow``; ``toolguide:contextive``
#:     -> ``tactic:terminology-extraction-mapping``). Moved counts: shipped edges
#:     873 -> 882; ``len(HAND_AUTHORED_EDGES)`` 109 -> 118; relation histogram
#:     ``suggests`` 417 -> 426 (``requires`` 272 / ``scope`` 159 UNCHANGED) --
#:     pinned by ``tests/architectural/test_no_authored_applies_edge.py`` and
#:     mirrored in ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-
#:     relationships.md``, both updated. ``test_shipped_graph_is_fresh_and_byte_
#:     identical`` stays green by construction (764 + 118 = 882). Orphan sets are
#:     UNCHANGED -- every one of the nine endpoints was already edge-incident, so
#:     no artefact enters or leaves ``_AWAITING_REFERENCES`` /
#:     ``_ORPHANS_RESOLVED_BY_OVERLAY``. Family E is INERT: every source is either
#:     the architect profile (inert in the profile channel) or an action-
#:     unreachable tactic/toolguide, and the reinforcement edges point INTO
#:     already-reachable paradigms, so ``_ACTION_UNREACHABLE_D1``/``D2``,
#:     ``_PROFILE_UNREACHABLE`` and ``_PROFILE_RESCUES`` in
#:     ``tests/doctrine/drg/test_reachability.py`` are UNCHANGED (measured, not
#:     assumed). The delivery-reachability DEFERRED set stays at 50 -- no artefact
#:     leaves (delivery is the fast-follow's job). See
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (14) doctrine-delivery-activation-01KYQVQK WP02 (T007/T008/T009): SEVEN new
#:     ``anti_pattern`` nodes and TEN hand-authored edges added to the overlay,
#:     with the PURE golden counts below UNCHANGED (``_EXPECTED_NODE_COUNT`` 311,
#:     ``_EXPECTED_EDGE_COUNT`` 764) because every edge endpoint already existed
#:     (the three ``template:c4-*-mermaid-template`` nodes, ``action:documentation/
#:     design``, and the seven ``tactic:refactoring-*`` sources) and the seven
#:     anti_pattern nodes are overlay content (``HAND_AUTHORED_NODES``), never
#:     extractor-minted. The ten edges: 3 ``action:documentation/design
#:     --instantiates--> template:c4-{context,container,component}-mermaid-
#:     template`` (T007, canonical Family-C topology completion, parallel to the
#:     pre-existing ``documentation-plan-template.md`` instantiates edge; NOT the
#:     delivery vector -- the templates already deliver to architect-alphonso via
#:     the profile channel's suggests-walk reaching ``tactic:c4-zoom-in-
#:     architecture-documentation``, WP01); and 7 ``tactic:refactoring-*
#:     --REJECTS--> anti_pattern:<smell>`` (T009, one per grounded refactoring
#:     tactic: encapsulate-record->unencapsulated-record, encapsulate-variable->
#:     global-data, extract-first-order-concept->implicit-concept, move-field->
#:     misplaced-field, move-method->feature-envy, state-pattern-for-behavior->
#:     repeated-switches-on-state, strangler-fig->big-bang-rewrite). Moved counts:
#:     shipped nodes 317 -> 324, shipped edges 882 -> 892; ``len(HAND_AUTHORED_
#:     NODES)`` 6 -> 13; ``len(HAND_AUTHORED_EDGES)`` 118 -> 128; relation
#:     histogram ``instantiates`` 8 -> 11 and ``rejects`` 8 -> 15 (``suggests``
#:     426 / ``requires`` 272 / ``scope`` 159 UNCHANGED). Only ``instantiates``
#:     carries a stated count in ``RELATION_DESCRIPTIONS`` (8 -> 11, mirrored in
#:     ``docs/architecture/doctrine-relationships.md``); ``rejects`` states no
#:     count, left unstated per the existing convention. ``test_shipped_graph_is_
#:     fresh_and_byte_identical`` stays green by construction (311 + 13 = 324;
#:     764 + 128 = 892). T006's Family-A ``when`` backfill on the three
#:     agent_profile->DDD ``suggests`` edges is content-only (no count or
#:     histogram move). Orphan sets UNCHANGED: the seven anti_pattern nodes each
#:     gain an inbound ``rejects`` edge, so none is orphaned, and every other
#:     endpoint was already edge-incident. Family is INERT/validation-tier: no
#:     channel walks ``instantiates`` or ``rejects`` into delivery, and
#:     anti_pattern is a non-activatable kind (D14/C-004), so
#:     ``_ACTION_UNREACHABLE_D1``/``D2``, ``_PROFILE_UNREACHABLE`` and
#:     ``_PROFILE_RESCUES`` in ``tests/doctrine/drg/test_reachability.py`` are
#:     UNCHANGED (measured, not assumed). See
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (15) Mission rehome-writing-comms-doctrine: the writing/communications doctrine
#:     set is rehomed into ``packs/built-in`` as 21 new EXTRACTOR-DERIVED artefacts
#:     (all pure, zero overlay -- ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES``
#:     stay 13/128): 7 agent profiles (analyst-annie, comms-cleo, diagram-daisy,
#:     lexical-larry, minutes-maker-mahad, scribe-sally, synthesizer-sam), 4
#:     numeric directives (DIRECTIVE_047 audience-oriented-writing / 048
#:     version-governance / 049 agent-declaration-and-self-introduction / 050
#:     credential-handling-discipline), 2 styleguides (meeting-minutes-format,
#:     professional-communications), 2 procedures (glossary-maintenance-workflow,
#:     meeting-minutes-pipeline), 1 tactic (writing-audience-catalog) and 5 assets
#:     (asset:writing-audience-{agentic-framework-core-team,automation-agent,
#:     line-manager,nontech-educator,software-engineer}). Each carries ordinary
#:     inline references / directive-references the extractor mints as edges, so
#:     none is an orphan. PURE golden counts move +21 NODES / +42 edges:
#:     ``_EXPECTED_NODE_COUNT`` 311 -> 332, ``_EXPECTED_EDGE_COUNT`` 764 -> 806.
#:     Shipped nodes 324 -> 345, shipped edges 892 -> 934 (= pure 332/806 + the
#:     unchanged overlay 13/128). Pure relation histogram moved on ``requires``
#:     (272 -> 289), ``suggests`` (339 -> 348) and ``specializes_from`` (0 -> 4);
#:     ``scope`` 157 / ``instantiates`` 8 UNCHANGED. The authored-edge relation
#:     histogram pinned by ``tests/architectural/test_no_authored_applies_edge.py``
#:     is UNCHANGED (overlay untouched). ORPHAN MEMBERSHIP MOVE: exactly one node
#:     LEAVES the orphan set. ``directive:USE_C4_MODEL_TECHNIQUES`` was a pure
#:     orphan wired only by the family-C overlay (ledger entry (11) --
#:     _AWAITING_REFERENCES + _ORPHANS_RESOLVED_BY_OVERLAY). The new
#:     ``agent_profile:diagram-daisy`` declares a ``directive-references`` entry
#:     ``code: USE_C4_MODEL_TECHNIQUES`` which ``normalize_directive_id`` resolves
#:     to ``directive:USE_C4_MODEL_TECHNIQUES``, so the extractor now mints a real
#:     ``agent_profile:diagram-daisy --requires--> directive:USE_C4_MODEL_TECHNIQUES``
#:     edge. USE_C4 is therefore no longer a pure orphan: pure orphans 30 -> 29
#:     (``_AWAITING_REFERENCES`` 11 -> 10, and it leaves _ORPHANS_RESOLVED_BY_OVERLAY
#:     9 -> 8). Shipped orphans UNCHANGED at 21 (USE_C4 already had shipped edges via
#:     the overlay, so it was never a shipped orphan). None of the 21 new artefacts
#:     is an orphan (all edge-incident), so no bucket gains a member.
#: Node count DERIVED from the ``packs/built-in`` inventory (#3234), not frozen: a
#: fresh ``generate_graph`` (pure, no overlay) must produce exactly one node per
#: shipped source file across the file-backed kinds, plus the structurally-derived
#: action/template nodes. Adding a shipped artifact bumps both the inventory and the
#: graph in lockstep (no false red); a loader/extractor that drops or mis-mints one
#: reds. See ``tests/doctrine/_builtin_inventory.py`` for the anti-tautology contract.
#: (16) supply-chain-security-checks-layer-01KZBFBS WP01 (T001/T002/T003): ONE
#:     new ``directive`` node (``directive:DIRECTIVE_051``, 051-supply-chain-
#:     install-safety -- renumbered from the mission's original 047 claim
#:     after ``rehome-writing-comms-doctrine`` independently minted the real
#:     ``DIRECTIVE_047`` (audience-oriented-writing) first; entry (15) landed
#:     first, so this mission's directive takes the next free numeric slot)
#:     and ONE new ``tactic`` node (``tactic:supply-chain-install-safety``),
#:     both extractor-minted from their own files -- no ``HAND_AUTHORED_NODES``
#:     change. Applied atop entry (15)'s 332/806, PURE golden counts move +2
#:     NODES / +8 edges: pure nodes 332 -> 334 (tracked live by
#:     ``_EXPECTED_NODE_COUNT``), pure edges 806 -> 814. The eight new edges
#:     are all inline ``references`` on the two new files plus the
#:     ``references`` addition to the existing ``tactic:dependency-hygiene``
#:     (extended for JS/TS applicability, not a new node): +1 ``requires`` and
#:     +7 ``suggests``, matching the moved ``RELATION_DESCRIPTIONS`` shipped
#:     counts (``requires`` 303 -> 304, ``suggests`` 437 -> 444, mirrored in
#:     ``docs/architecture/doctrine-relationships.md``; ``scope`` 159
#:     UNCHANGED at this step). ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES``
#:     are UNCHANGED at 13/128 (this WP touches no overlay content), so
#:     shipped counts move by exactly the PURE delta: shipped nodes 345 ->
#:     347, shipped edges 934 -> 942. Neither new node is orphaned:
#:     ``directive:DIRECTIVE_051`` gets inbound ``suggests`` from both
#:     ``tactic:dependency-hygiene`` and ``tactic:supply-chain-install-
#:     safety``, and ``tactic:supply-chain-install-safety`` gets inbound
#:     ``suggests`` from both ``tactic:dependency-hygiene`` and
#:     ``directive:DIRECTIVE_051``. Orphan sets are otherwise UNCHANGED.
#: (17) supply-chain-security-checks-layer-01KZBFBS WP02 (T004/T005): ZERO new
#:     nodes. Six new ``scope`` edges, all extractor-derived from the
#:     ``directives:``/``tactics:`` lists in
#:     ``packs/built-in/missions/software-dev/actions/{plan,implement,
#:     review}/index.yaml`` -- each of the three actions gains one
#:     ``action:software-dev/<action> --scope--> directive:DIRECTIVE_051`` edge
#:     and one ``action:software-dev/<action> --scope--> tactic:supply-chain-
#:     install-safety`` edge (no ``HAND_AUTHORED_EDGES`` change; these mirror
#:     the pre-existing pattern of every other directive/tactic already listed
#:     in those same three index.yaml files). Applied atop entry (16)'s
#:     334/814, PURE golden counts move +0 NODES / +6 edges: pure nodes
#:     UNCHANGED at 334, pure edges 814 -> 820. The moved
#:     ``RELATION_DESCRIPTIONS`` count is ``scope`` 159 -> 165 (mirrored in
#:     ``docs/architecture/doctrine-relationships.md``; ``requires``/
#:     ``suggests`` UNCHANGED at this step). ``HAND_AUTHORED_NODES``/
#:     ``HAND_AUTHORED_EDGES`` are UNCHANGED at 13/128 (this WP touches no
#:     overlay content), so shipped counts move by exactly the PURE delta:
#:     shipped nodes UNCHANGED at 347, shipped edges 942 -> 948. No node is
#:     added, so no new orphan is possible; every action node already had
#:     outbound edges, so orphan sets are UNCHANGED.
#: (18) supply-chain-security-checks-layer-01KZBFBS WP03 (T009-T012): binds the
#:     WP01 directive/tactic layer to the 7 targeted agent profiles
#:     (``reviewer-renata``, ``implementer-ivan``, ``node-norris``,
#:     ``frontend-freddy``, ``python-pedro``, ``java-jenny``,
#:     ``architect-alphonso``). Every new edge is an inline-``references``
#:     ``requires`` edge minted from each profile's own
#:     ``directive-references`` (all 7 add ``"051"``; formerly authored on the
#:     retired ``context-sources.directives`` surface, consolidated in entry
#:     (21)) and/or
#:     ``tactic-references`` (``reviewer-renata`` and 5 implementation/support
#:     profiles add ``supply-chain-install-safety`` and/or
#:     ``dependency-hygiene``, per-profile applicability) -- no new node, no
#:     overlay content. Applied atop entry (17)'s 334/820, PURE golden counts
#:     move +0 NODES / +16 edges: pure nodes UNCHANGED at 334, pure edges 820
#:     -> 836. ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES`` are UNCHANGED
#:     at 13/128 (this WP touches no overlay content), so shipped counts move
#:     by exactly the PURE delta: shipped nodes UNCHANGED at 347, shipped
#:     edges 948 -> 964. All 16 edges are ``requires`` (``RELATION_
#:     DESCRIPTIONS`` / ``docs/architecture/doctrine-relationships.md`` moved
#:     304 -> 320, both updated; ``suggests`` 444 / ``scope`` 165 UNCHANGED).
#:     No node is newly orphaned -- every target (``directive:DIRECTIVE_051``,
#:     ``tactic:dependency-hygiene``, ``tactic:supply-chain-install-safety``)
#:     already had inbound edges from WP01. The per-channel reachability move
#:     (``tactic:dependency-hygiene`` and ``tactic:secure-design-checklist``
#:     leave ``_PROFILE_UNREACHABLE``; ``_PROFILE_RESCUES`` UNCHANGED) is
#:     ledgered in ``tests/doctrine/drg/test_reachability.py``.
#: (19) drg-reachability-metric-wiring-01KZS5VR WP01 (T001/T002, #3009 point 3):
#:     SEVEN new curated edges added to ``_CURATED_ARTIFACT_EDGES`` (the six
#:     traced #3009-remedy relationships from research.md; edge "6" splits into
#:     two physical tuples, 6a/6b, one per profile) -- no new node, no overlay
#:     content. Measured LIVE against the pre-wiring graph at HEAD: pure nodes
#:     334, pure edges 838; shipped nodes 347, shipped edges 966 (two more edges
#:     than entry (18)'s stated 334/836 -- a pre-existing prose/measurement
#:     drift from an unrelated intervening change, out of this WP's scope to
#:     reconcile; the live count is authoritative, per the wiring-table's own
#:     "50 vs 60" reconciliation precedent). PURE golden counts move +0 NODES /
#:     +7 edges: pure nodes UNCHANGED at 334, pure edges 838 -> 845.
#:     ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES`` are UNCHANGED at 13/128
#:     (this WP touches no overlay content), so shipped counts move by exactly
#:     the PURE delta: shipped nodes UNCHANGED at 347, shipped edges 966 -> 973
#:     (verified: ``load_built_in_graph()`` measures 973 post-regeneration).
#:     Two of the seven edges are ``requires`` (edges 5, 6b); five are
#:     ``suggests`` (edges 1, 2, 3, 4, 6a) -- ``RELATION_DESCRIPTIONS`` /
#:     ``docs/architecture/doctrine-relationships.md`` were not updated (neither
#:     carries a stated count for ``requires``/``suggests``, per the existing
#:     convention of leaving uncounted relations unstated).
#:     THREE nodes leave the orphan set (a **shrink**, C-003):
#:     ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS`` leaves
#:     ``_ACTIVATED_BUT_ORPHANED`` (edges 2/3 give it real inbound edges);
#:     ``directive:DISCIPLINED_REFACTORING`` and ``directive:USE_MUTATION_
#:     TESTING_TO_VALIDATE_TEST_QUALITY`` leave ``_AWAITING_REFERENCES`` (edges
#:     1/4). Pure orphans 29 -> 26 (``_ACTIVATED_BUT_ORPHANED`` 6 -> 5,
#:     ``_AWAITING_REFERENCES`` 5 -> 3). All three were ALREADY resolved by the
#:     hand-authored overlay in the shipped graph (ledger entries 10/12: family-B
#:     ``suggests`` edges for DISCIPLINED_REFACTORING, family-D ``suggests``
#:     edges for USE_MUTATION_TESTING, and the ``reconciles_tension`` overlay for
#:     RECONCILE), so they also leave ``_ORPHANS_RESOLVED_BY_OVERLAY`` (8 -> 5)
#:     by the SAME three -- ``_SHIPPED_ORPHANS`` (= ``_INTENTIONAL_ORPHANS`` -
#:     ``_ORPHANS_RESOLVED_BY_OVERLAY``) is measured UNCHANGED at 21 (already
#:     tight against ``DOCUMENTED_ORPHAN_RESIDUAL`` before this wiring, and
#:     still tight after -- no ratchet needed, verified empirically rather than
#:     assumed). The per-channel reachability move (the whole-graph companion
#:     metric 88 -> 75, and the activated-only ``_ACTION_UNREACHABLE_D1``/``D2``,
#:     ``_PROFILE_UNREACHABLE``, ``_PROFILE_RESCUES`` moves) is ledgered in
#:     ``tests/doctrine/drg/test_reachability.py`` and
#:     ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.
#: (20) Mission #3604 (WP07, ``extract_governance_profile_scope_edges``): mints
#:     ZERO new nodes -- every ``selected_*`` target it walks was already minted
#:     by an earlier ``generate_graph`` pass (its own docstring's contract,
#:     enforced since #3629 by ``assert_governance_scope_edges_resolve``). It
#:     adds exactly 39 new ``mission_type --scope--> {directive,tactic,paradigm,
#:     styleguide,toolguide,procedure,agent_profile,mission_step_contract}``
#:     edges -- one per non-empty ``selected_*`` entry across the four built-in
#:     ``governance-profile.yaml`` files -- ALL of relation ``scope``, never
#:     ``requires``/``suggests`` (distinct from entries (16)-(18)'s
#:     inline-``references`` ``requires`` edges, which this pass does not
#:     touch). The moved ``RELATION_DESCRIPTIONS`` / ``docs/architecture/
#:     doctrine-relationships.md`` count is ``scope`` 165 -> 204 (action-sourced
#:     165 UNCHANGED, mission_type-sourced 0 -> 39; verified live against
#:     ``load_built_in_graph()``: 204 total scope edges, 165 action-sourced /
#:     39 mission_type-sourced by source-node kind).
#:     This entry deliberately does NOT restate a full composed pure/shipped
#:     node+edge total the way entries (16)-(19) do: ``requires``/``suggests``
#:     also moved between entry (19)'s ending state and the live graph (live:
#:     ``requires`` 332, ``suggests`` 451), but neither move is attributable to
#:     this pass -- ``extract_governance_profile_scope_edges`` emits ``scope``
#:     edges exclusively -- so composing a single before/after node+edge total
#:     here would silently fold in unrelated intervening changes, exactly the
#:     drift entry (19) itself flagged as out of its own scope to reconcile.
#:     The ``scope`` 165 -> 204 move is the complete, attributable claim this
#:     entry makes.
#: (21) Mission ``doctrine-drg-silent-drop-boundary-01M0PE7E`` (WP02, #3629 p1):
#:     the retired ``context-sources.*`` bare-string profile surface was removed
#:     from the model + schema, and ``extract_artifact_edges`` now projects
#:     ``agent_profile`` edges from the canonical top-level ``*-references``
#:     surface: ``directive-references -> requires`` (replacing the retired
#:     ``context-sources.directives`` loop), ``tactic-references -> requires``
#:     (unchanged), and the newly-added ``toolguide-references`` /
#:     ``styleguide-references -> suggests`` projections. The ATTRIBUTABLE golden
#:     delta, measured as the per-``agent_profile:*`` edge-set diff of a fresh
#:     regeneration against the pre-consolidation committed graph, is exactly
#:     THREE new edges, ZERO new nodes, and ZERO overlay change:
#:       * ``agent_profile:python-pedro --requires--> directive:DIRECTIVE_034``.
#:         pedro authors ``034`` in ``directive-references`` (the retired
#:         ``context-sources.directives`` list omitted it -- the sole shipped
#:         divergence), so the canonical projection now mints it. ``034`` was
#:         ALREADY an overlay ``suggests`` target for pedro, so it becomes a
#:         ``requires``+``suggests`` DIAMOND -- consistent with pedro's existing
#:         ``030``/``041`` diamonds -- and ``progressive_disclosure`` delivers it
#:         EAGER (requires precedence). This is the DELIBERATE, ledgered pedro/034
#:         decision (post-plan squad F4/F5): full uniform canonical projection
#:         with the overlay left intact -- NOT a pedro-specific extractor
#:         exclusion (a special-case hack) and NOT an overlay edit; the delivered
#:         artefact set is unchanged (``034`` was already action-scoped-delivered
#:         at implement/review), only the profile-channel edge relation on ``034``
#:         is now ``requires`` rather than a ``when``-conditioned ``suggests``.
#:       * ``agent_profile:diagram-daisy --suggests--> toolguide:mermaid-
#:         diagramming`` and ``--suggests--> toolguide:plantuml-diagramming``.
#:         diagram-daisy is the only shipped profile authoring
#:         ``toolguide-references``; the new ``toolguide-references -> suggests``
#:         projection mints them. Both toolguides were ALREADY profile-reachable
#:         via ``daisy --requires--> USE_C4_MODEL_TECHNIQUES --suggests-->`` (the
#:         family-C overlay, entry (11)), so ``_PROFILE_RESCUES`` /
#:         ``_PROFILE_UNREACHABLE`` in ``tests/doctrine/drg/test_reachability.py``
#:         are UNCHANGED (measured) -- the direct edges add a second path to
#:         already-reachable nodes. No shipped profile authors
#:         ``styleguide-references``, so that projection is exercised only by the
#:         divergent fixture in
#:         ``tests/doctrine/agent_profiles/test_context_sources_migration.py``.
#:     Relation histogram: ``requires`` +1, ``suggests`` +2, ``scope``
#:     UNCHANGED. ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES`` UNCHANGED (no
#:     overlay content touched). No new node -> no new orphan; ``mermaid``/
#:     ``plantuml`` gain a pure inbound edge but are not members of this module's
#:     frozen orphan sets (they are reachability-set members only). The C-006
#:     golden-diff -- "the per-``agent_profile:*`` edge-set diff is empty except
#:     this ledgered delta" -- is pinned by ``test_context_sources_migration.py``.
#: (22) Charter directive ``prefer-durable-fixes`` (mission
#:     ``charter-prefer-durable-fixes-directive``): ONE new ``directive`` node
#:     (``directive:DIRECTIVE_052``, ``directives/052-prefer-durable-fixes.
#:     directive.yaml``), extractor-minted from its own file. It carries NO
#:     inline ``references`` (relationships are edges, per the frozen-legacy
#:     references surface — the ``DISCIPLINED_REFACTORING`` /
#:     ``RECONCILE_CHANGE_SCOPE_TENSIONS`` precedent), so its relationships are
#:     authored as FIVE curated (pure) ``suggests`` edges in
#:     ``_CURATED_ARTIFACT_EDGES`` — NOT overlay content, so
#:     ``HAND_AUTHORED_NODES``/``HAND_AUTHORED_EDGES`` are UNCHANGED. The five:
#:     ``directive:DIRECTIVE_052 --suggests-->`` each of
#:     ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS`` (the arbiter that sizes the
#:     remediation), ``directive:DIRECTIVE_044`` (feeds canonical-source
#:     unification), ``directive:DIRECTIVE_043`` (close the class by
#:     construction), ``directive:DIRECTIVE_040`` (recurrence escalation), and
#:     ``styleguide:adversarial-squad-cadence`` (the investigation-squad
#:     mechanism). PURE golden counts move +1 NODE / +5 edges:
#:     ``_EXPECTED_NODE_COUNT`` auto-tracks via ``pure_builtin_node_count()``
#:     (the new file bumps the inventory glob and the graph in lockstep — no
#:     frozen literal to hand-reconcile), ``_EXPECTED_EDGE_COUNT`` is not frozen
#:     (edges >= nodes floor holds). Relation histogram ``suggests`` +5
#:     (``requires``/``scope``/``in_tension_with``/``reconciles_tension``
#:     UNCHANGED); ``suggests`` carries only a directional, test-unenforced prose
#:     count in ``RELATION_DESCRIPTIONS`` / ``docs/architecture/doctrine-
#:     relationships.md`` (left as-is per the ledger entry (19) precedent for a
#:     small curated ``suggests`` add). ORPHAN SETS UNCHANGED: the new directive
#:     is edge-incident via its five outbound curated edges (never a pure
#:     orphan, so it enters NO ``_INTENTIONAL_ORPHANS`` bucket); all five targets
#:     were already edge-incident, so none enters or leaves any orphan set.
#:     ``_SHIPPED_ORPHANS`` UNCHANGED at 21. REACHABILITY: the directive is a new
#:     action-unreachable node (nothing ``scope``s it), the same INERT shape as
#:     ``DISCIPLINED_REFACTORING`` / ``USE_C4_MODEL_TECHNIQUES`` — it joins the
#:     live action-unreachable ``dead`` partition in
#:     ``tests/doctrine/drg/test_reachability.py``, which since PR #3342 asserts
#:     only totality/disjointness (no frozen membership), so nothing there
#:     moves. It is charter-activated in this repository's ``.kittify`` but not
#:     in any pinned pack-default reachability universe.
#: Node count DERIVED from the ``packs/built-in`` inventory (#3234), not frozen: a
#: fresh ``generate_graph`` (pure, no overlay) must produce exactly one node per
#: shipped source file across the file-backed kinds, plus the structurally-derived
#: action/template nodes. Adding a shipped artifact bumps both the inventory and the
#: graph in lockstep (no false red); a loader/extractor that drops or mis-mints one
#: reds. See ``tests/doctrine/_builtin_inventory.py`` for the anti-tautology contract.
_EXPECTED_NODE_COUNT = pure_builtin_node_count()
#: No frozen ``_EXPECTED_EDGE_COUNT``: edge totals come from frontmatter refs and
#: cannot be independently derived from the filesystem. EXACT edge integrity is
#: guaranteed by ``spec-kitty doctrine regenerate-graph --check`` (committed
#: fragments == a fresh regeneration) and, in-process, by
#: ``test_shipped_graph_is_fresh_and_byte_identical`` (regenerated edge SET ==
#: shipped edge SET). Count assertions below use an ``edges >= nodes`` floor.

# ---------------------------------------------------------------------------
# Orphan MEMBERSHIP, not an orphan count
# ---------------------------------------------------------------------------
# This was ``_EXPECTED_ORPHAN_COUNT = 32`` -- a bare cardinality with the
# delta-only ledger above as its sole explanation. A count cannot distinguish
# "32 known-acceptable orphans" from "32 unexamined orphans", and they were the
# second kind: nine of them are artefacts the charter has ACTIVATED, which the
# count read as settled for as long as the number stayed at 32. Naming the
# members makes a new orphan announce itself by URN instead of nudging an
# integer, and makes the unacceptable ones impossible to file under the same
# heading as the acceptable ones.
#
# The four sets below partition the orphan set by *why* each node has no edge.
# Three are legitimate; the fourth is a tracked defect that must shrink to
# empty. Deliberately NOT redefining the metric: ``_orphan_urns`` still counts
# edge INCIDENCE, exactly as before (the stricter traversability measures in
# issue #3009 move a golden count repo-wide and are a separate mission).

#: Built-in mission step contracts. ``mission_step_contract.graph.yaml`` ships
#: ``edges: []`` by construction (ledger entry 2): a contract is resolved by the
#: ``(mission_type, action)`` join at pre-review activation, never by graph
#: traversal, so it has no edge to carry. 17 shipped = documentation 7 +
#: research 5 + software-dev 5.
_EDGELESS_BY_CONSTRUCTION: frozenset[str] = frozenset(
    {
        f"mission_step_contract:{contract}"
        for contract in (
            "documentation/accept",
            "documentation/audit",
            "documentation/design",
            "documentation/discover",
            "documentation/generate",
            "documentation/publish",
            "documentation/validate",
            "research/gathering",
            "research/methodology",
            "research/output",
            "research/scoping",
            "research/synthesis",
            "software-dev/implement",
            "software-dev/plan",
            "software-dev/review",
            "software-dev/specify",
            "software-dev/tasks",
        )
    }
)

#: Nodes a landed mission registered before anything cross-references them.
#: Each is explained by a numbered entry in the ledger above; an orphan here is
#: expected to leave the set when the follow-up mission wires it, not to sit
#: here indefinitely.
_AWAITING_REFERENCES: frozenset[str] = frozenset(
    {
        # Ledger (glossary-pack-doctrine-kind-01KY30SW): Mission A ships the
        # pack node with zero outbound refs; its enforcement fields stay inert
        # until Mission B.
        "glossary_pack:spec-kitty-core",
        # Ledger (3): the first shipped doctrine ASSET; ``asset.graph.yaml``
        # ships ``edges: []``. Wired by the hand-authored overlay -- see
        # _ORPHANS_RESOLVED_BY_OVERLAY.
        "asset:common-docs-structural-lint",
        # Ledger (4): promoted out of ``toolguides/`` into the ``built-in``
        # pack layer by ADR 2026-07-26-2, which made it a node for the first
        # time. Nothing references it yet.
        "toolguide:powershell-syntax",
        # Ledger (10) #3063 family-B introduced ``directive:DISCIPLINED_
        # REFACTORING`` here as a pure orphan wired only by the family-B
        # overlay. Ledger (19) (drg-reachability-metric-wiring-01KZS5VR, WP01,
        # #3009 point 3) RETIRES that status: ``procedure:refactoring
        # --suggests--> DISCIPLINED_REFACTORING`` (edge 1) is now a real,
        # extractor-minted (curated-table) edge, so it is no longer a pure
        # orphan -- removed from this set (and from
        # _ORPHANS_RESOLVED_BY_OVERLAY). See ledger entry (19).
        # Ledger (11) #3063 family-C introduced ``directive:USE_C4_MODEL_TECHNIQUES``
        # here as a pure orphan wired only by the family-C overlay. Ledger (15)
        # (rehome-writing-comms-doctrine) RETIRES that status: the new
        # ``agent_profile:diagram-daisy`` declares a ``directive-references`` entry
        # for it, so the extractor now mints a real ``requires`` edge into it and it
        # is no longer a pure orphan -- removed from this set (and from
        # _ORPHANS_RESOLVED_BY_OVERLAY). See ledger entry (15).
        # Ledger (12) #3063 family-D introduced the five new TESTING/BDD/MUTATION
        # artefacts. Each carried no inline references, so a pure
        # ``generate_graph`` minted its node but no edge; every one was wired
        # only by the hand-authored family-D ``suggests`` edges.
        #
        # Ledger (writing-comms/diagramming activation, commit 9a99801f1, #3009):
        # four of the five family-D artefacts -- quadruple-a-test-format,
        # given-when-then-authoring, sonar, gherkin -- became charter-ACTIVATED. An
        # activated pure orphan is a tracked #3009 defect, so they graduate to
        # _ACTIVATED_BUT_ORPHANED (the floor guard demands it, and the orphan
        # partition keeps each URN in exactly one bucket).
        #
        # ``USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`` -- which is NOT
        # activated -- was the sole family-D survivor here as a plain
        # awaiting-references orphan. Ledger (19) RETIRES that status too:
        # ``directive:DIRECTIVE_030 --suggests--> USE_MUTATION_TESTING_TO_
        # VALIDATE_TEST_QUALITY`` (edge 4) is now a real, extractor-minted edge
        # -- removed from this set (and from _ORPHANS_RESOLVED_BY_OVERLAY).
    }
)

#: The human operator is a participant, not a doctrine artefact anything
#: delegates to or resolves through. No traversal should ever reach it, so
#: zero incident edges is the correct shape rather than a gap.
_NOT_A_TRAVERSAL_TARGET: frozenset[str] = frozenset({"agent_profile:human-in-charge"})

#: **Tracked defect -- issue #3009. This set must only ever SHRINK.**
#: Renamed from ``_ACTIVATED_BUT_UNREACHABLE`` (WP08/T044): it is measured by
#: ``_orphan_urns``, which counts edge INCIDENCE, so it names activated nodes
#: with no edge in *either* direction -- an orphan, not the stricter
#: "unreachable from an action/profile traversal". Per-channel REACHABILITY (the
#: activated-but-unreachable membership sets that a nominal inbound edge from an
#: unreachable source does NOT satisfy) lives in
#: ``tests/doctrine/drg/test_reachability.py`` (WP08).
#: Every URN here is ACTIVATED in ``.kittify/config.yaml`` yet has no edge at
#: all, so ``charter activate --cascade`` pulls in nothing for it, deactivation
#: frees nothing, and no action's context resolution can surface it. The
#: charter says these are live doctrine; the DRG says they reach nobody.
#: ``procedure:red-main-release-discipline`` is the procedure behind charter
#: standing order #9; ``tactic:occurrence-classification-workflow`` is the
#: workflow behind DIRECTIVE_035 -- and DIRECTIVE_035 is itself on this list.
#:
#: This is the same failure WP09 fixed once for
#: ``procedure:onboard-external-agent-to-pack`` (there: an edge typed
#: ``applies``, which no traversal follows; here: no edge at all).
#:
#: Note the count: issue #3009 reports NINE. It is ten. The issue's matcher
#: compares a node's bare id against the ``activated_*`` lists, which works for
#: every kind except ``directive`` -- directive URNs are ``directive:
#: DIRECTIVE_035`` while the charter activates the file slug
#: ``035-bulk-edit-occurrence-classification``, so no directive could ever
#: match. Fixing an artefact here removes its line; nothing may be added
#: without an issue reference.
#:
#: RESOLVED 2026-07-28 (operator ruling, landing pass for PR #3007). Of the ten:
#: ``toolguide:rtk-search-tooling`` was DELETED (ledger entry 6) and eight were
#: WIRED via ``_CURATED_ARTIFACT_EDGES`` (ledger entry 7) -- seven targets plus
#: ``directive:DIRECTIVE_035``, which leaves this set by becoming an edge SOURCE
#: rather than by gaining an inbound edge.
#: ``styleguide:deployable-skill-authoring`` was the only survivor of ledger
#: entry 7; the writing-comms/diagramming activation (commit 9a99801f1, #3009)
#: later adds four more activated pure orphans -- see the set body.
#:
#: The first pass had ``paradigm:atomic-design`` here instead, claiming no
#: defensible source existed. Review refuted that from the corpus:
#: ``tactic:atomic-design-review-checklist`` ships, is activated in both the
#: default pack and this project, and ``tactic -> paradigm suggests`` is the
#: commonest inbound-to-paradigm shape in the graph (9 edges, 6 of them exactly
#: this, via the semantic-compression family). The two dispositions were
#: INVERTED: the artefact WITH a name-identical source was refused, while an
#: edge was invented for the one without. ``deployable-skill-authoring``
#: genuinely has no owner -- the onboarding procedure mentions "skill" zero
#: times, and the styleguide is a distribution-surface concern, not a
#: pack-authoring one. Corrected so the standard is applied once: record
#: relationships that exist, refuse to invent ones that do not.
# Ledger (kind-complete-cascade-orphan-wiring-01M0FQCD, WP02, #3009 RESIDUAL --
# the move that drives this tracked-defect set to EMPTY, C-003):
#   * The four family-D artefacts -- ``styleguide:given-when-then-authoring``,
#     ``toolguide:gherkin`` (both from DIRECTIVE_034), ``toolguide:sonar`` (from
#     DIRECTIVE_030) and ``styleguide:quadruple-a-test-format`` (from
#     DIRECTIVE_041) -- were PROMOTED from hand-authored overlay ``suggests``
#     edges to their owning directive's own ``references`` frontmatter. The
#     extractor now mints a real inbound edge for each in the PURE graph, so they
#     are no longer orphans at all: they leave BOTH this set and
#     ``_ORPHANS_RESOLVED_BY_OVERLAY`` (the overlay no longer resolves them --
#     the overlay edges were deleted, the frontmatter edges took their place,
#     byte-identically). See ``TestResidualOrphanWiring`` and the promoted
#     directive YAMLs.
#   * ``styleguide:deployable-skill-authoring`` -- the sole source-less member --
#     leaves for the new ``_DIRECT_ACTIVATION_ONLY`` disposition (FR-008). It is
#     still a pure orphan (no defensible source, no invented edge -- C-003), so
#     it stays in ``_INTENTIONAL_ORPHANS`` via that bucket; it simply stops being
#     counted as tracked #3009 debt.
# Net: ``_ACTIVATED_BUT_ORPHANED`` -5 (4 promoted + 1 direct-only) -> empty; the
# #3009 residual is closed. This set is now the empty floor the "must only ever
# SHRINK" invariant always aimed at -- a new member may be added only with an
# issue reference and a defensible-source audit.
_ACTIVATED_BUT_ORPHANED: frozenset[str] = frozenset()

#: **Direct-activation-only disposition (#3009 residual, mission
#: kind-complete-cascade-orphan-wiring-01M0FQCD, WP02, FR-008).**
#: ``styleguide:deployable-skill-authoring`` is charter-ACTIVATED yet has no
#: defensible source artefact to carry an inbound edge: the onboarding procedure
#: mentions "skill" zero times, and the styleguide is a distribution-surface
#: concern, not a pack-authoring one (see the ``_ACTIVATED_BUT_ORPHANED`` header's
#: closing paragraph, which already refused to invent an edge for it). It is
#: therefore recorded here as *direct-activation-only*: it is reached by charter
#: activation directly (``charter activate styleguide deployable-skill-authoring``),
#: never by a cascade or an action/profile traversal, and inventing a guessed edge
#: to green-wash it is explicitly refused (C-003). It stays a pure orphan (a member
#: of ``_INTENTIONAL_ORPHANS``) but leaves the tracked-defect
#: ``_ACTIVATED_BUT_ORPHANED`` set, which this mission drives to empty.
_DIRECT_ACTIVATION_ONLY: frozenset[str] = frozenset(
    {
        "styleguide:deployable-skill-authoring",
    }
)

#: Every node a PURE ``generate_graph`` run leaves incident to no edge.
#: CURRENT total is 22 (see the WP02 ledger paragraph at the end of this block);
#: the arithmetic that follows is the historical trail that reached the prior 26.
#: 17 + 3 + 1 + 5 = 26 (was 17 + 5 + 1 + 6 = 29 before ledger entry (19)
#: (drg-reachability-metric-wiring-01KZS5VR, WP01, #3009 point 3): three URNs
#: leave -- ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS`` leaves
#: ``_ACTIVATED_BUT_ORPHANED`` (6 -> 5) and ``directive:DISCIPLINED_
#: REFACTORING`` / ``directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY``
#: leave ``_AWAITING_REFERENCES`` (5 -> 3), each because a curated edge now
#: gives it a real extractor-minted inbound edge. This is a SHRINK, C-003).
#: Earlier: ``_AWAITING_REFERENCES`` shrank 10 -> 5 when the writing-comms/
#: diagramming activation (commit 9a99801f1, #3009) graduated four family-D
#: artefacts plus the reconcile-change-scope-tensions hub directive into
#: ``_ACTIVATED_BUT_ORPHANED`` 1 -> 6; the union was unchanged. It had earlier
#: shrunk to 10 with ledger entry (15)'s
#: rehome-writing-comms-doctrine, which gives ``directive:USE_C4_MODEL_TECHNIQUES`` a
#: real extractor edge via ``agent_profile:diagram-daisy`` -- it had grown to 11 with
#: ledger entry (12)'s five new family-D artefacts, atop entry (11)'s
#: ``directive:USE_C4_MODEL_TECHNIQUES`` and entry (10)'s
#: ``directive:DISCIPLINED_REFACTORING``). The retired
#: ``_EXPECTED_ORPHAN_COUNT`` pinned 32; the difference is ledger entries (6) and (7)
#: -- one deletion and eight wirings -- and is now a consequence of the membership
#: rather than the whole contract.
#: Ledger (kind-complete-cascade-orphan-wiring-01M0FQCD, WP02, #3009 residual):
#: the pure-orphan total moves 26 -> 22. The four promoted family-D artefacts
#: gain real frontmatter inbound edges and leave the orphan set entirely (-4);
#: ``deployable-skill-authoring`` merely changes bucket (``_ACTIVATED_BUT_ORPHANED``
#: -> ``_DIRECT_ACTIVATION_ONLY``) and stays an orphan. New composition:
#: 17 + 3 + 1 + 0 + 1 = 22 (``_EDGELESS_BY_CONSTRUCTION`` + ``_AWAITING_REFERENCES``
#: + ``_NOT_A_TRAVERSAL_TARGET`` + ``_ACTIVATED_BUT_ORPHANED`` (now empty) +
#: ``_DIRECT_ACTIVATION_ONLY``).
_INTENTIONAL_ORPHANS: frozenset[str] = (
    _EDGELESS_BY_CONSTRUCTION
    | _AWAITING_REFERENCES
    | _NOT_A_TRAVERSAL_TARGET
    | _ACTIVATED_BUT_ORPHANED
    | _DIRECT_ACTIVATION_ONLY
)

#: The pure-extractor figure (22) and the shipped-graph figure (21) differ by
#: exactly this ONE node, and by nothing else: the hand-authored overlay
#: (``charter.offering.drg.migration.hand_authored_overlay``) carries edges the
#: extractor has no frontmatter mechanism to mint, and the sole survivor lands on
#: ``asset:common-docs-structural-lint`` (``asset.graph.yaml`` ships ``edges: []``
#: so an asset can never be an edge source in the pure graph).
#: (Ledger entry (15) removed ``directive:USE_C4_MODEL_TECHNIQUES`` from this set --
#: it gained a real extractor edge, so the overlay no longer resolves it. Ledger
#: entry (19) removed ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS``,
#: ``directive:DISCIPLINED_REFACTORING`` and ``directive:USE_MUTATION_TESTING_TO_
#: VALIDATE_TEST_QUALITY`` for the same reason -- each gained a real curated-table
#: extractor edge. Ledger (kind-complete-cascade-orphan-wiring-01M0FQCD, WP02,
#: #3009 residual) removed the four family-D artefacts
#: (``styleguide:given-when-then-authoring``, ``toolguide:gherkin``,
#: ``toolguide:sonar``, ``styleguide:quadruple-a-test-format``): their overlay
#: ``suggests`` edges were DELETED and re-authored byte-identically in directive
#: frontmatter, so they gain a real pure-graph inbound edge and cease to be
#: orphans -- the overlay no longer determines (or even carries) their status. -4.
#: Naming them keeps the two figures related by a stated cause instead of by two
#: independent magic numbers that could drift apart unnoticed.
_ORPHANS_RESOLVED_BY_OVERLAY: frozenset[str] = frozenset(
    {
        "asset:common-docs-structural-lint",
    }
)

#: Orphans that survive into the graph an operator actually loads.
_SHIPPED_ORPHANS: frozenset[str] = _INTENTIONAL_ORPHANS - _ORPHANS_RESOLVED_BY_OVERLAY

#: software-dev steps that are not action-sequence members (retrospect lives
#: outside every type's step directory and is asserted separately).
_SOFTWARE_DEV_NON_SEQUENCE_STEPS = frozenset(
    {"accept", "analyze", "charter", "research", "tasks-finalize", "tasks-outline", "tasks-packages"}
)


#: The hand-pinned authored action_sequence per built-in type. Post-WP07 the
#: flat ``action_sequence`` is removed from the mission_types YAML (the step.yaml
#: projection is the sole authority), so this test compares the projected edge
#: set against this independent human-authored contract rather than a raw-YAML
#: read of a field that no longer exists.
_SHIPPED_ACTION_SEQUENCES: dict[str, list[str]] = {
    "software-dev": ["specify", "plan", "tasks", "implement", "review"],
    "documentation": ["discover", "audit", "design", "generate", "validate", "publish", "accept"],
    "research": ["scoping", "methodology", "gathering", "synthesis", "output"],
    "plan": ["specify", "research", "plan", "review"],
}


def _shipped_action_sequences() -> dict[str, list[str]]:
    """The pinned authored ``action_sequence`` per built-in type (the projected
    edge set must equal the edges these sequences imply)."""
    return dict(_SHIPPED_ACTION_SEQUENCES)


def _orphan_urns(nodes: Any, edges: Any) -> set[str]:
    """Return node URNs incident to no edge (neither source nor target)."""
    incident: set[str] = set()
    for edge in edges:
        incident.add(edge.source)
        incident.add(edge.target)
    return {node.urn for node in nodes if node.urn not in incident}


def _describe_orphan_drift(measured: set[str], expected: frozenset[str]) -> str:
    """Render an orphan-set mismatch as the two directions a reader must act on.

    The whole point of replacing the golden count: a failure must name the node,
    and say whether something newly lost its edges or newly gained one.
    """
    appeared = sorted(measured - expected)
    resolved = sorted(expected - measured)
    lines: list[str] = []
    if appeared:
        lines.append(
            "NEW orphans -- these nodes are incident to no edge and nothing "
            "declares that acceptable:\n"
            + "\n".join(f"    + {urn}" for urn in appeared)
            + "\n  Either give the node an edge a traversal follows, or add it to "
            "the bucket that explains why it has none."
        )
    if resolved:
        lines.append(
            "NO LONGER orphans -- these are still declared as edge-less:\n"
            + "\n".join(f"    - {urn}" for urn in resolved)
            + "\n  Drop them from the declaration; if one left "
            "_ACTIVATED_BUT_ORPHANED, note the fix on issue #3009."
        )
    return "orphan membership drifted.\n  " + "\n  ".join(lines)


@pytest.mark.doctrine
class TestDRGZeroDelta:
    """The projection re-point leaves the shipped DRG graph unchanged (NFR-002)."""

    def test_regenerated_graph_matches_baseline_counts(self, tmp_path: Path) -> None:
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")

        assert len(graph.nodes) == _EXPECTED_NODE_COUNT, (
            "pure regeneration node count drifted from the packs/built-in "
            "inventory -- a shipped artifact was dropped or mis-minted"
        )
        # Edge floor (see the _EXPECTED_NODE_COUNT note above): exact edge integrity
        # is guaranteed by regenerate-graph --check and by the byte-identity test.
        assert len(graph.edges) >= len(graph.nodes)

        orphans = _orphan_urns(graph.nodes, graph.edges)
        assert orphans == _INTENTIONAL_ORPHANS, _describe_orphan_drift(
            orphans, _INTENTIONAL_ORPHANS
        )

    def test_shipped_graph_orphans_are_the_pure_set_minus_the_overlay(self) -> None:
        """The two figures (pure 29, shipped 21) differ by a stated cause.

        Asserting each against its own constant would let them drift apart while
        both stayed green. Here the shipped set is *derived* from the pure set,
        so an overlay edge that stops landing reds with the node's name.
        """
        shipped = load_built_in_graph()
        orphans = _orphan_urns(shipped.nodes, shipped.edges)
        assert orphans == _SHIPPED_ORPHANS, _describe_orphan_drift(
            orphans, _SHIPPED_ORPHANS
        )

    def test_the_overlay_really_does_wire_the_nodes_it_is_credited_with(self) -> None:
        """Floor for the derivation above.

        If ``_ORPHANS_RESOLVED_BY_OVERLAY`` named a node the overlay does not
        actually wire, the subtraction would still produce a self-consistent
        pair of sets. This pins the cause, not just the arithmetic.
        """
        assert _INTENTIONAL_ORPHANS >= _ORPHANS_RESOLVED_BY_OVERLAY
        assert not (_ORPHANS_RESOLVED_BY_OVERLAY & _SHIPPED_ORPHANS)

        overlay_targets: set[str] = set()
        for edge in HAND_AUTHORED_EDGES:
            overlay_targets.add(edge.source)
            overlay_targets.add(edge.target)
        assert overlay_targets >= _ORPHANS_RESOLVED_BY_OVERLAY, (
            "these nodes are credited to the hand-authored overlay but no "
            "overlay edge touches them: "
            f"{sorted(_ORPHANS_RESOLVED_BY_OVERLAY - overlay_targets)}"
        )

    def test_the_orphan_partition_is_disjoint_and_total(self) -> None:
        """The four ``why`` sets must partition the orphan set exactly.

        Without this an entry could sit in two buckets (or in none while the
        union still matched), which would let the tracked-defect set be
        understated while every other assertion stayed green.
        """
        parts = (
            _EDGELESS_BY_CONSTRUCTION,
            _AWAITING_REFERENCES,
            _NOT_A_TRAVERSAL_TARGET,
            _ACTIVATED_BUT_ORPHANED,
            _DIRECT_ACTIVATION_ONLY,
        )
        assert sum(len(part) for part in parts) == len(_INTENTIONAL_ORPHANS), (
            "the orphan buckets overlap -- a URN is filed under two reasons"
        )

    def test_shipped_graph_is_fresh_and_byte_identical(self) -> None:
        """A fresh regeneration + the hand-authored overlay matches the shipped graph.

        Post-WP03 (doctrine-tension-edges-01KY1WPC): the shipped graph also
        carries hand-authored ``in_tension_with``/``reconciles_tension``/
        ``rejects`` edges and ``anti_pattern`` nodes the extractor has no
        frontmatter mechanism to mint (C-005). The reference is therefore
        "pure regeneration + the enumerable overlay", not a bare regeneration.
        """
        shipped = load_built_in_graph()
        regenerated = generate_reference_graph_with_overlay(DOCTRINE_ROOT)

        assert {n.urn for n in regenerated.nodes} == {n.urn for n in shipped.nodes}
        assert {
            (e.source, e.target, e.relation.value) for e in regenerated.edges
        } == {(e.source, e.target, e.relation.value) for e in shipped.edges}
        # Node count is the inventory-derived shipped figure (pure + overlay).
        assert (
            len(regenerated.nodes)
            == len(shipped.nodes)
            == shipped_builtin_node_count()
        )
        # No frozen edge integer: the SET equality asserted above already proves the
        # regenerated and shipped edge sets are byte-identical (the in-process
        # equivalent of regenerate-graph --check). Assert their sizes agree exactly
        # (non-frozen) plus the floor.
        assert len(regenerated.edges) == len(shipped.edges) >= len(shipped.nodes)


#: The four #3009-residual orphans that get a real frontmatter inbound edge this
#: mission (kind-complete-cascade-orphan-wiring-01M0FQCD, WP02, FR-007). Each was
#: a hand-authored overlay ``suggests`` edge sourced at its owning directive; the
#: promotion moves that authority into the directive's own ``references``
#: frontmatter so the edge exists in the PURE extractor graph, not only the
#: overlay. ``(source directive, target)`` pairs:
_RESIDUAL_FRONTMATTER_PROMOTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("directive:DIRECTIVE_034", "styleguide:given-when-then-authoring"),
        ("directive:DIRECTIVE_034", "toolguide:gherkin"),
        ("directive:DIRECTIVE_030", "toolguide:sonar"),
        ("directive:DIRECTIVE_041", "styleguide:quadruple-a-test-format"),
    }
)


@pytest.mark.doctrine
class TestResidualOrphanWiring:
    """#3009 residual: 4 overlay edges promoted to source frontmatter, 1 direct-only.

    ATDD red-first (WP02/T006): both assertions are RED on the planning base
    (the 4 targets have zero inbound edges in the pure graph; the fifth is still
    filed under the tracked-defect ``_ACTIVATED_BUT_ORPHANED`` set). They go
    green once the promotions land in directive frontmatter (T007/T008) and the
    ledger records ``deployable-skill-authoring`` direct-activation-only (T010).
    """

    def test_promoted_targets_have_a_pure_graph_inbound_edge(self, tmp_path: Path) -> None:
        """FR-007: each promoted target is de-orphaned in the PURE extractor
        graph (no overlay), sourced from its owning directive's frontmatter with
        the expected ``(source, target)`` pair -- not merely *some* inbound edge."""
        graph = generate_graph(DOCTRINE_ROOT, tmp_path / "graph.yaml")
        inbound_pairs = {(edge.source, edge.target) for edge in graph.edges}
        missing = sorted(
            pair for pair in _RESIDUAL_FRONTMATTER_PROMOTIONS if pair not in inbound_pairs
        )
        assert not missing, (
            "these #3009-residual orphans still lack a pure-graph frontmatter "
            "inbound edge from their owning directive (promotion did not take "
            f"effect): {missing}"
        )

    def test_deployable_skill_authoring_is_direct_activation_only(self) -> None:
        """FR-008: the source-less fifth orphan is recorded direct-activation-only
        and has LEFT the tracked-defect ``_ACTIVATED_BUT_ORPHANED`` set (never
        given a guessed edge -- C-003)."""
        urn = "styleguide:deployable-skill-authoring"
        assert urn in _DIRECT_ACTIVATION_ONLY
        assert urn not in _ACTIVATED_BUT_ORPHANED, (
            "deployable-skill-authoring must move OUT of the tracked-defect "
            "_ACTIVATED_BUT_ORPHANED set into the direct-activation-only "
            "disposition, not sit in both"
        )


@pytest.mark.doctrine
class TestNonSequenceStepsMintNoEdge:
    """``in_action_sequence: false`` steps never mint a mission_type->action edge."""

    def test_software_dev_non_sequence_steps_mint_no_edge(self) -> None:
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        sw_dev_targets = {
            e.target
            for e in edges
            if e.source == "mission_type:software-dev" and e.relation is Relation.REQUIRES
        }

        steps = MissionStepRepository.default().resolve_all_for_mission_type(
            "software-dev", pack_context=None
        )
        non_sequence_step_ids = {
            step_id for step_id, step in steps.items() if not step.in_action_sequence
        }

        assert non_sequence_step_ids == _SOFTWARE_DEV_NON_SEQUENCE_STEPS
        for step_id in non_sequence_step_ids:
            assert f"action:software-dev/{step_id}" not in sw_dev_targets, (
                f"{step_id} is in_action_sequence:false but minted a requires edge"
            )

    def test_retrospect_never_appears_as_a_requires_edge_target(self) -> None:
        """``retrospect`` is not a member of any shipped type's action sequence."""
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        retrospect_targets = {
            e.target
            for e in edges
            if e.relation is Relation.REQUIRES and e.target.endswith("/retrospect")
        }
        assert not retrospect_targets


@pytest.mark.doctrine
class TestProjectedEdgeSetMatchesActionSequence:
    """Projected edges == the pre-mission ``action_sequence``-derived edges, per type."""

    def test_every_type_projected_edges_match_shipped_action_sequence(self) -> None:
        edges = extract_mission_type_edges(DOCTRINE_ROOT)
        sequences = _shipped_action_sequences()

        assert sequences, "expected at least one shipped mission type"
        for mission_id, steps in sequences.items():
            source_urn = f"mission_type:{mission_id}"
            emitted = [
                e.target
                for e in edges
                if e.source == source_urn and e.relation is Relation.REQUIRES
            ]
            expected = [f"action:{mission_id}/{step}" for step in steps]
            assert emitted == expected, (
                f"{source_urn}: projected edges {emitted} != "
                f"raw action_sequence-derived edges {expected}"
            )
