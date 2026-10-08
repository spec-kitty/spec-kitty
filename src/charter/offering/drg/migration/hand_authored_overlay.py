"""Enumerable registry of DRG content hand-authored directly in the shipped
``packs/built-in/*.graph.yaml`` fragments (mission doctrine-tension-edges-01KY1WPC
WP02) that the extractor cannot derive from built-in artifact frontmatter.

Why this exists
----------------

The extractor (:mod:`charter.offering.drg.migration.extractor`) walks built-in
artifact YAML and mints DRG nodes/edges from their inline reference fields
(``tactic_refs``, ``references``, etc.). WP02 of this mission hand-authored
three new DRG relations (``in_tension_with``, ``reconciles_tension``,
``rejects``) plus six ``anti_pattern`` nodes directly into the graph
fragments. Per ADR 2026-07-18-1 / constraint C-005 ("edge-authored, not
field-derived"), the extractor has **no frontmatter mechanism** that could
ever mint these -- they are authored content, not migrated content, and a
pure regeneration will never reproduce them. That is by design, not drift.

Two consumers depend on this registry so a pure extractor regeneration never
silently regresses (or perpetually misreports staleness on) the hand-authored
content:

1. ``spec-kitty charter pack regenerate-graph`` (:mod:`specify_cli.cli.commands.charter.pack_tooling`)
   -- both its ``--check`` freshness comparison and its write path must merge
   this overlay in, or running the command for real would overwrite
   ``packs/built-in/*.graph.yaml`` with a version that has silently dropped
   every hand-authored tension/reconciliation/rejection edge and anti-pattern
   node, and ``--check`` alone would report "stale" forever even when nothing
   is actually stale.
2. The doctrine test suite's shipped-graph freshness/equality canaries
   (``tests/doctrine/drg/migration/test_extractor.py``,
   ``test_extractor_projection.py``, ``test_path_ref_resolver.py``,
   ``tests/doctrine/drg/test_graph_sharding_equality.py``,
   ``test_sharding_silent_degrade.py``) -- each compares a pure extractor
   regeneration against the committed shipped graph and must merge this
   overlay into its "expected" side.

Any discrepancy beyond exactly this enumerated overlay is still a genuine
freshness failure. Growing this list is a deliberate, reviewed edit -- it
should only change in lockstep with a new hand-authored edge/node landing in
one of the ``*.graph.yaml`` fragments, never as a reflex "make the check
pass" change.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.validator import assert_valid

# ---------------------------------------------------------------------------
# Repeated literals hoisted to named constants (Sonar python:S1192). Grouped
# by role: DRG URNs referenced as node/edge endpoints, `when=` applicability
# clauses shared verbatim across several profile->hub edges, and the shared
# opening sentence fragment of a `reason=` value whose remainder differs per
# edge (joined back with `+` where the literal is only the first chunk of an
# implicitly-concatenated multi-line string).
# ---------------------------------------------------------------------------

_URN_ANTI_PATTERN_BIG_BALL_OF_MUD = "anti_pattern:big-ball-of-mud"
_URN_ANTI_PATTERN_BIG_UPFRONT_DESIGN = "anti_pattern:big-upfront-design"
_URN_ASSET_COMMON_DOCS_STRUCTURAL_LINT = "asset:common-docs-structural-lint"
_URN_ACTION_DOCUMENTATION_DESIGN = "action:documentation/design"
_URN_DIRECTIVE_025 = "directive:DIRECTIVE_025"
_URN_DIRECTIVE_030 = "directive:DIRECTIVE_030"
_URN_DIRECTIVE_034 = "directive:DIRECTIVE_034"
_URN_DIRECTIVE_041 = "directive:DIRECTIVE_041"
_URN_DIRECTIVE_RECONCILE_CHANGE_SCOPE_TENSIONS = "directive:RECONCILE_CHANGE_SCOPE_TENSIONS"
_URN_DIRECTIVE_DISCIPLINED_REFACTORING = "directive:DISCIPLINED_REFACTORING"
_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES = "directive:USE_C4_MODEL_TECHNIQUES"
_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY = "directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY"
_URN_PARADIGM_BROWNFIELD_ONBOARDING = "paradigm:brownfield-onboarding"
_URN_PARADIGM_C4_INCREMENTAL_DETAIL_MODELING = "paradigm:c4-incremental-detail-modeling"
_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN = "paradigm:domain-driven-design"
_URN_TACTIC_TERMINOLOGY_EXTRACTION_MAPPING = "tactic:terminology-extraction-mapping"
_URN_TOOLGUIDE_CONTEXTIVE = "toolguide:contextive"
_URN_PROFILE_ARCHITECT_ALPHONSO = "agent_profile:architect-alphonso"
_URN_PROFILE_FRONTEND_FREDDY = "agent_profile:frontend-freddy"
_URN_PROFILE_GENERIC_AGENT = "agent_profile:generic-agent"
_URN_PROFILE_IMPLEMENTER_IVAN = "agent_profile:implementer-ivan"
_URN_PROFILE_JAVA_JENNY = "agent_profile:java-jenny"
_URN_PROFILE_NODE_NORRIS = "agent_profile:node-norris"
_URN_PROFILE_PYTHON_PEDRO = "agent_profile:python-pedro"
_URN_PROFILE_RANDY_REDUCER = "agent_profile:randy-reducer"
_URN_PROFILE_REVIEWER_RENATA = "agent_profile:reviewer-renata"

_WHEN_DISCIPLINED_REFACTORING_TIDYING = "when tidying code, encountering long classes/methods, or discovering convoluted logic"
_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS = "when writing or reviewing the tests that accompany an implementation"
_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR = "when assessing whether the tests around a change actually constrain its behaviour"
_WHEN_TESTS_MEET_QUALITY_GATE = "when assessing whether tests meet the quality gate they must pass"
_WHEN_KEEPING_TESTS_AS_SCAFFOLD = "when keeping the tests they write a clear scaffold rather than friction"

_REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING = "An implementer-role profile should reach the disciplined-refactoring "
_REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB = "An implementer-role profile should reach the test-first hub when "
_REASON_IMPLEMENTER_REACHES_MUTATION_HUB = "An implementer-role profile should reach the mutation hub when "
_REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB = "An implementer-role profile should reach the test-quality-gate hub "
_REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB = "An implementer-role profile should reach the tests-as-scaffold hub "

# ---------------------------------------------------------------------------
# The thirteen anti-pattern/smell nodes authored in
# packs/built-in/anti_pattern.graph.yaml. None of these are ever an edge *source*
# (rejects edges terminate at them), so they carry no outgoing edges of their
# own.
#
# The first six (WP02 of mission doctrine-tension-edges-01KY1WPC) are the
# paradigm-rejected architectural anti-patterns. The final seven (T008 of mission
# doctrine-delivery-activation-01KYQVQK, FR-008/C-004) name the code smells the
# SEVEN grounded refactoring-* tactics solve, each derived from that tactic's own
# ATTESTED Family-B `when` text (hand_authored_overlay.py:621-728); every one is a
# REJECTS-target of its rejecting tactic (see HAND_AUTHORED_EDGES below).
#
# DEFERRED per C-004 (no invented smells): the other ELEVEN refactoring-* tactics
# carry NO attested problem/when text anywhere in the shipped tree (verified:
# refactoring-{change-function-declaration, combine-functions-into-transform,
# conditional-to-strategy, consolidate-conditional-expression,
# extract-class-by-responsibility-split, guard-clauses-before-polymorphism,
# inline-temp, introduce-null-object, replace-magic-number-with-symbolic-constant,
# replace-temp-with-query, retry-pattern} have neither a Family-B suggests edge
# with a `when` nor a top-level problem/when/trigger/smell field on the tactic
# artifact). No anti_pattern node is authored for them — fabricating a smell
# description would violate C-004's grounding bar.
# ---------------------------------------------------------------------------

HAND_AUTHORED_NODES: tuple[DRGNode, ...] = (
    DRGNode(
        urn="anti_pattern:anemic-domain-model",
        kind=NodeKind.ANTI_PATTERN,
        label="Anemic Domain Model",
        tags=["anti-pattern"],
    ),
    DRGNode(
        urn=_URN_ANTI_PATTERN_BIG_BALL_OF_MUD,
        kind=NodeKind.ANTI_PATTERN,
        label="Big Ball of Mud",
        tags=["anti-pattern"],
    ),
    DRGNode(
        urn=_URN_ANTI_PATTERN_BIG_UPFRONT_DESIGN,
        kind=NodeKind.ANTI_PATTERN,
        label="Big Upfront Design",
        tags=["anti-pattern"],
    ),
    DRGNode(
        urn="anti_pattern:code-is-the-documentation",
        kind=NodeKind.ANTI_PATTERN,
        label="Code Is the Documentation",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:database-driven-design",
        kind=NodeKind.ANTI_PATTERN,
        label="Database-Driven Design",
        tags=["anti-pattern"],
    ),
    DRGNode(
        urn="anti_pattern:single-diagram-architecture",
        kind=NodeKind.ANTI_PATTERN,
        label="Single-Diagram Architecture",
        tags=["smell"],
    ),
    # T008 (doctrine-delivery-activation-01KYQVQK): the seven refactoring code
    # smells, each grounded in its rejecting tactic's attested Family-B `when`.
    DRGNode(
        urn="anti_pattern:unencapsulated-record",
        kind=NodeKind.ANTI_PATTERN,
        label="Unencapsulated Record",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:global-data",
        kind=NodeKind.ANTI_PATTERN,
        label="Global Data",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:implicit-concept",
        kind=NodeKind.ANTI_PATTERN,
        label="Implicit Concept",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:misplaced-field",
        kind=NodeKind.ANTI_PATTERN,
        label="Misplaced Field",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:feature-envy",
        kind=NodeKind.ANTI_PATTERN,
        label="Feature Envy",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:repeated-switches-on-state",
        kind=NodeKind.ANTI_PATTERN,
        label="Repeated Switches on State",
        tags=["smell"],
    ),
    DRGNode(
        urn="anti_pattern:big-bang-rewrite",
        kind=NodeKind.ANTI_PATTERN,
        label="Big-Bang Rewrite",
        tags=["anti-pattern"],
    ),
)

# ---------------------------------------------------------------------------
# The 2 in_tension_with + 3 reconciles_tension + 8 rejects edges authored in
# packs/built-in/{directive,paradigm}.graph.yaml (WP02 T007/T008/T010/T011),
# migrated from the retired contradiction-declaration field (WP03).
# Reason text copied verbatim from the committed fragments.
# ---------------------------------------------------------------------------

HAND_AUTHORED_EDGES: tuple[DRGEdge, ...] = (
    DRGEdge(
        source="directive:DIRECTIVE_024",
        target=_URN_DIRECTIVE_025,
        relation=Relation.IN_TENSION_WITH,
        reason=(
            "Locality of Change bounds new work to the minimum scope the goal "
            "requires; Boy Scout Rule endorses opportunistic improvement of "
            "touched areas, which can justify expanding a change beyond that "
            "boundary. Both remain valid, co-activatable rules -- the tension "
            "is resolved per-change by keeping adjacent campsite cleaning "
            "inside the touched area while deferring genuinely broad refactors "
            "with an explicit rationale, not by retiring either rule. See "
            "directive:RECONCILE_CHANGE_SCOPE_TENSIONS."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_025,
        target="tactic:change-apply-smallest-viable-diff",
        relation=Relation.IN_TENSION_WITH,
        reason=(
            "The Boy Scout Rule encourages leaving touched code better than "
            "found, which can justify changes beyond the smallest viable diff "
            "the tactic prescribes. Both remain valid, co-activatable rules -- "
            "apply smallest-viable-diff discipline for goal delivery, and fold "
            "in only the touched-area fixes Boy Scout Rule requires, deferring "
            "broader opportunistic improvement to an explicit task. See "
            "directive:RECONCILE_CHANGE_SCOPE_TENSIONS."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_RECONCILE_CHANGE_SCOPE_TENSIONS,
        target="directive:DIRECTIVE_024",
        relation=Relation.RECONCILES_TENSION,
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_RECONCILE_CHANGE_SCOPE_TENSIONS,
        target=_URN_DIRECTIVE_025,
        relation=Relation.RECONCILES_TENSION,
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_RECONCILE_CHANGE_SCOPE_TENSIONS,
        target="tactic:change-apply-smallest-viable-diff",
        relation=Relation.RECONCILES_TENSION,
    ),
    DRGEdge(
        source=_URN_PARADIGM_BROWNFIELD_ONBOARDING,
        target=_URN_ANTI_PATTERN_BIG_BALL_OF_MUD,
        relation=Relation.REJECTS,
        reason=(
            "A Big Ball of Mud is the failure mode brownfield onboarding is "
            "built to interrupt. Where Big Ball of Mud lets coupling and "
            "concepts leak without investigation, brownfield onboarding "
            "insists that the leaks be mapped and named before they are "
            "either preserved or removed."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_BROWNFIELD_ONBOARDING,
        target=_URN_ANTI_PATTERN_BIG_UPFRONT_DESIGN,
        relation=Relation.REJECTS,
        reason=(
            "Big Upfront Design assumes the right structure can be derived "
            "from first principles before contact with the existing system. "
            "Brownfield onboarding inverts the priority: the existing system "
            "is the primary evidence, and design proposals must be grounded "
            "in what the codebase, its history, and its SMEs already encode."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_C4_INCREMENTAL_DETAIL_MODELING,
        target=_URN_ANTI_PATTERN_BIG_UPFRONT_DESIGN,
        relation=Relation.REJECTS,
        reason=(
            "Big Upfront Design attempts to specify every architectural "
            "detail before implementation begins. C4 incremental detail "
            "modeling favours progressive discovery -- start with a context "
            "diagram and add lower levels only when they earn their keep."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_C4_INCREMENTAL_DETAIL_MODELING,
        target="anti_pattern:code-is-the-documentation",
        relation=Relation.REJECTS,
        reason=(
            "Relying solely on source code as documentation forces every "
            "stakeholder -- including non-technical sponsors -- to read code "
            "to understand system boundaries. C4 provides visual abstractions "
            "that make architecture accessible without requiring code "
            "literacy."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_C4_INCREMENTAL_DETAIL_MODELING,
        target="anti_pattern:single-diagram-architecture",
        relation=Relation.REJECTS,
        reason=(
            "A single all-in-one architecture diagram conflates audiences and "
            "abstraction levels, producing a poster that nobody can review in "
            "a reasonable time. C4 explicitly separates concerns into "
            "distinct levels."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="anti_pattern:anemic-domain-model",
        relation=Relation.REJECTS,
        reason=(
            "Anemic Domain Models strip behaviour from domain objects, "
            "reducing them to data bags with external procedural services. "
            "This defeats the purpose of a rich, expressive domain model and "
            "scatters invariant enforcement across service layers."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target=_URN_ANTI_PATTERN_BIG_BALL_OF_MUD,
        relation=Relation.REJECTS,
        reason=(
            "A Big Ball of Mud architecture has no explicit context "
            "boundaries or ubiquitous language. Concepts leak across "
            "modules, coupling grows unchecked, and model integrity becomes "
            "impossible to maintain."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="anti_pattern:database-driven-design",
        relation=Relation.REJECTS,
        reason=(
            "Starting from a database schema and generating code around it "
            "inverts the DDD priority: the domain model should drive "
            "persistence, not the other way around. Schema-first thinking "
            "produces models shaped by storage constraints rather than "
            "business rules."
        ),
    ),
    # -----------------------------------------------------------------------
    # The 4 requires edges wiring the common-docs artifacts to the shipped
    # structural-lint asset (mission ship-structural-lint-as-asset). The lint
    # is now the first built-in ASSET (asset:common-docs-structural-lint); the
    # directive, styleguide, and the write/scaffold tactics NAME it in prose as
    # the gate that enforces them. (The write edge replaced the retired
    # curation tactic's edge when mission squad-doctrine-single-owner-01M3KBP7
    # folded curation's run-the-live-gates step into common-docs-write.) The extractor has no frontmatter
    # mechanism to mint an edge to an asset, so these are authored directly in
    # the graph fragments. REQUIRES (not suggests): activating any of these
    # artifacts pulls the shipped lint asset in as a mandatory prerequisite.
    # Note: ASSET is not a charter-activatable kind, so this is not a
    # charter-activate-cascade deployment hook -- `--cascade all` on these
    # artifacts only emits a benign "could not cascade-activate
    # asset/common-docs-structural-lint" warning. The edge's real job is DRG
    # de-orphaning (an un-linked asset that everything references is the
    # un-navigable state the asset kind exists to fix) plus transitive-ref
    # resolution: it is what lets resolve_transitive_refs() return the asset
    # with is_complete=True for consumers walking these artifacts' reference
    # closure, i.e. deployment-manifest completeness rather than an
    # activation trigger.
    # -----------------------------------------------------------------------
    DRGEdge(
        source="directive:DIRECTIVE_042",
        target=_URN_ASSET_COMMON_DOCS_STRUCTURAL_LINT,
        relation=Relation.REQUIRES,
        reason=(
            "DIRECTIVE_042 names the common-docs structural lint as the live "
            "mechanical gate that enforces it; activating the directive "
            "requires the shipped lint asset to be present."
        ),
    ),
    DRGEdge(
        source="styleguide:common-docs",
        target=_URN_ASSET_COMMON_DOCS_STRUCTURAL_LINT,
        relation=Relation.REQUIRES,
        reason=(
            "The common-docs styleguide's tooling rows and quality_test name "
            "the structural lint as their enforcing gate, and its "
            "structural_lint_config: block is the policy the asset loads; "
            "activating the styleguide requires the shipped lint asset."
        ),
    ),
    DRGEdge(
        source="tactic:common-docs-write",
        target=_URN_ASSET_COMMON_DOCS_STRUCTURAL_LINT,
        relation=Relation.REQUIRES,
        reason=(
            "The common-docs write tactic's run-the-live-gates step directs the "
            "agent to run the structural lint before handoff; activating the "
            "tactic requires the shipped lint asset."
        ),
    ),
    DRGEdge(
        source="tactic:common-docs-scaffold",
        target=_URN_ASSET_COMMON_DOCS_STRUCTURAL_LINT,
        relation=Relation.REQUIRES,
        reason=(
            "The common-docs scaffold tactic relies on the structural lint's "
            "index_completeness check to enforce section-index scaffolding; "
            "activating the tactic requires the shipped lint asset."
        ),
    ),
    # -----------------------------------------------------------------------
    # WP09 (mission doctrine-delivery-reachability-01KYMXD6, T050, FR-015): the
    # reaching edge for the common-docs cluster. The four `requires` edges above
    # de-orphan asset:common-docs-structural-lint by INCIDENCE, but every one of
    # their sources (DIRECTIVE_042, styleguide:common-docs, and the common-docs
    # tactics) was measured action-UNREACHABLE -- the whole documentation-
    # authoring family is a strongly-connected island no action node scopes, so
    # the asset (and the styleguide, and the four common-docs tactics) reached
    # nobody. Incidence is not reachability (contract R-6); this is exactly the
    # PR #3007 failure the mission exists to correct.
    #
    # This SCOPE edge makes DIRECTIVE_042 itself action-reachable: resolve_context
    # walks `scope` at depth 1 from the action, then 042's pre-existing
    # `requires`/`suggests` edges deliver the asset, the styleguide and the four
    # common-docs tactics transitively. Measured with the WP08 helper: d=1 and d=2
    # action-reachable each grow by exactly the seven artefacts 042 heads.
    #
    # C-007 is satisfied without inventing a relationship: (a) DIRECTIVE_042's own
    # `scope:` text -- "Applies whenever a documentation file under the Common Docs
    # root is created, moved, renamed ..." -- attests it governs documentation-file
    # creation, and `documentation/generate`'s `write_docs` step writes docs/**/*.md
    # (creates documentation files); (b) the source is an `action` node, C-007(b)'s
    # second clause. It is NOT a profile/lineage edge, so assert_valid's
    # profile-endpoint rule does not apply.
    #
    # Canonical home / B2 handoff: the canonical surface for an action->artefact
    # `scope` edge is the documentation step-contract action index
    # (missions/built_in_step_contracts/documentation-generate.step-contract.yaml,
    # `delegates_to` candidates), which is outside WP09's owned files. Mission B2
    # (drg-edge-migration-extractor-retirement-01KYFV8C) retires this overlay
    # generator; when it does it MUST migrate this edge into that action index
    # rather than silently dropping it. See
    # docs/plans/doctrine/delivery-reachability-wiring-table.md.
    DRGEdge(
        source="action:documentation/generate",
        target="directive:DIRECTIVE_042",
        relation=Relation.SCOPE,
        reason=(
            "The documentation/generate action creates documentation files "
            "(its write_docs step writes docs/**/*.md), which is DIRECTIVE_042's "
            "stated trigger ('whenever a documentation file under the Common Docs "
            "root is created'); the action is therefore governed by the common-docs "
            "documentation standard. This scope edge is the reaching entry point "
            "that delivers the common-docs styleguide, tactics and structural-lint "
            "asset, which were otherwise a strongly-connected island no action "
            "scoped (WP09 / FR-015)."
        ),
    ),
    # -----------------------------------------------------------------------
    # #3063 family-A (DDD family), operator interview outcome. The operator has
    # ATTESTED these relationships (C-007(a) satisfied by operator ruling); the
    # hub is paradigm:domain-driven-design. Three kinds of edge land here:
    #
    #   1. ONE reaching `scope` edge, action:software-dev/specify -> the DDD
    #      paradigm. This is the edge that changes action reachability: it makes
    #      the DDD paradigm action-reachable at the specify grain, and the
    #      paradigm's `requires` edges below then deliver the whole family
    #      transitively (resolve_context walks scope at depth 1 from the action,
    #      then requires transitively). Measured with the WP08 helper: d=1 and
    #      d=2 action-reachable each grow by exactly the twelve artefacts the
    #      paradigm heads (the paradigm, its two pre-existing directive_refs
    #      DIRECTIVE_031/032, and the ten members below minus
    #      strategic-domain-classification, which was already reachable).
    #
    #      NOTE the relation is `scope`, NOT `suggests`. The #3063 wiring table
    #      row named `suggests`, but that is measured INERT: resolve_context
    #      walks `suggests` only FROM scope-resolved artifacts, never from the
    #      action node itself (query.resolve_context steps 2/3 seed from
    #      `scoped_artifacts`), so a `suggests` edge sourced at an action changes
    #      no reachability. Only a `scope` edge from an action delivers — exactly
    #      the WP09 precedent (action:documentation/generate --scope--> 042). The
    #      #3063 §3 mandate ("this edge DOES change action reachability; update
    #      the pinned unreachable sets") is satisfiable only by `scope`, so the
    #      table's `suggests` is corrected to `scope` here and the discrepancy is
    #      recorded in docs/plans/doctrine/delivery-reachability-wiring-table.md.
    #
    #      C-007 without inventing a relationship: (a) the DDD paradigm's own
    #      summary attests strategic design ("aligning code with a deep model of
    #      the business domain"), which is what the software-dev specify step
    #      does ("align the mission design with architectural intent"); (b) the
    #      source is an `action` node, C-007(b)'s second clause. Canonical home /
    #      B2 handoff: an action->artefact `scope` edge belongs in the
    #      software-dev specify step-contract action index; mission B2 migrates
    #      it when it retires this overlay generator.
    #
    #   2. TEN `requires` edges, DDD paradigm -> each genuine DDD family member.
    #      Each target's OWN text attests DDD membership (C-007a): bounded-context
    #      identification / canvas-fill / boundary-inference and context-mapping
    #      (Evans strategic design), strategic-domain-classification (Core/
    #      Supporting/Generic subdomain), aggregate-boundary-design /
    #      entity-value-object-classification / domain-event-capture /
    #      anti-corruption-layer (Evans tactical patterns) and the
    #      aggregate-design-rules styleguide. EXCLUDED as non-attested:
    #      reference-architectural-patterns (its own text is general reference-
    #      architecture selection by quality attributes, not DDD) and the state/
    #      UI tactics compositional-stream-boundaries / cross-cutting-state-via-
    #      store / atomic-state-ownership.
    #
    #   3. THREE `suggests` edges, agent profiles -> the DDD paradigm. These are
    #      COMPOSITION-ONLY / INERT under today's traversal: the profile channel
    #      walks {requires, specializes_from} only, and the action channel does
    #      not seed from profiles, so a profile--suggests-->paradigm edge changes
    #      NO reachability (measured: profile channel 39->39, unchanged). They
    #      record the attested "an architect/pattern-scout/reducer should reach
    #      DDD when designing or inspecting code" relationship for when a future
    #      channel follows it.
    #
    # DEFERRED (NOT authored here): the DDD<->documentation mutual-reinforcement
    # edge — gated on the upcoming value-based edge properties (B1). Noted in the
    # wiring-table doc as pending.
    # -----------------------------------------------------------------------
    DRGEdge(
        source="action:software-dev/specify",
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SCOPE,
        reason=(
            "The software-dev specify step aligns the mission design with "
            "architectural intent; Domain-Driven Design is the paradigm that "
            "governs aligning that design with a deep model of the business "
            "domain (DDD's own summary). This scope edge is the reaching entry "
            "point that makes the DDD paradigm action-reachable at the specify "
            "grain and delivers its strategic-design family transitively "
            "(#3063 family-A). It is `scope` not `suggests` because a suggests "
            "edge sourced at an action node is inert under resolve_context."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:bounded-context-identification",
        relation=Relation.REQUIRES,
        reason=(
            "Bounded Context Identification is DDD strategic design (Evans): "
            "drawing boundaries around regions where a single consistent model "
            "and ubiquitous language apply. Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:context-mapping-classification",
        relation=Relation.REQUIRES,
        reason=(
            "Context Mapping Classification is DDD strategic design: it "
            "classifies every relationship between bounded contexts using the "
            "canonical DDD context-mapping patterns. Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:context-boundary-inference",
        relation=Relation.REQUIRES,
        reason=(
            "Context Boundary Inference is DDD strategic design: it detects "
            "bounded-context boundaries from team ownership and terminology "
            "conflicts, documenting ubiquitous language per context. Activating "
            "DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:bounded-context-canvas-fill",
        relation=Relation.REQUIRES,
        reason=(
            "Bounded Context Canvas Fill is DDD strategic design: it guides "
            "completing a Bounded Context Canvas (DDD Crew v5) capturing a "
            "context's strategic classification and ubiquitous language. "
            "Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:strategic-domain-classification",
        relation=Relation.REQUIRES,
        reason=(
            "Strategic Domain Classification is DDD strategic design (Evans): "
            "classifying each bounded context as Core, Supporting or Generic "
            "subdomain to guide investment. Activating DDD pulls it in. (Already "
            "action-reachable via paula-patterns' review tactic; this edge "
            "records the paradigm membership without moving its reachability.)"
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:aggregate-boundary-design",
        relation=Relation.REQUIRES,
        reason=(
            "Aggregate Boundary Design is DDD tactical design (Evans / Vernon): "
            "defining transactional consistency boundaries and aggregate roots "
            "within a bounded context. Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:entity-value-object-classification",
        relation=Relation.REQUIRES,
        reason=(
            "Entity vs Value Object Classification is DDD tactical design "
            "(Evans): classifying each domain object as an Entity or a Value "
            "Object. Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:domain-event-capture",
        relation=Relation.REQUIRES,
        reason=(
            "Domain Event Capture is DDD tactical design (Evans / Fowler): "
            "funnelling significant state changes through immutable Domain "
            "Event objects. Activating DDD pulls it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="tactic:anti-corruption-layer",
        relation=Relation.REQUIRES,
        reason=(
            "The Anti-Corruption Layer is a DDD context-mapping pattern (Evans): "
            "a translation layer that keeps a foreign system's model from "
            "corrupting the domain's ubiquitous language. Activating DDD pulls "
            "it in."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        target="styleguide:aggregate-design-rules",
        relation=Relation.REQUIRES,
        reason=(
            "The Aggregate Design Rules styleguide encodes DDD tactical "
            "aggregate discipline (reference by identity, keep aggregates small, "
            "eventual consistency between aggregates via domain events). "
            "Activating DDD pulls it in."
        ),
    ),
    # T006 (mission doctrine-delivery-activation-01KYQVQK, D3/R-M6): each of the
    # three Family-A profile->DDD `suggests` edges previously carried a `reason=`
    # but no `when=`, so every delivery fell back to STATED_DEFAULT_WHEN. The
    # `when` below is derived from each edge's own `reason` trigger clause (the
    # applicability condition, distinct from the `reason` which stays as-is and
    # states *why* the edge exists) — matching the Family B/C `when=`/`reason=`
    # convention in this same file. Content-only edit: no node/edge cardinality
    # or relation-histogram move.
    DRGEdge(
        source=_URN_PROFILE_ARCHITECT_ALPHONSO,
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SUGGESTS,
        when="designing or reviewing significant code changes",
        reason=(
            "When designing and reviewing significant code changes, the "
            "architect should reach Domain-Driven Design. Composition-only under "
            "today's traversal (the profile channel walks requires/"
            "specializes_from only), authored per the #3063 operator attestation."
        ),
    ),
    DRGEdge(
        source="agent_profile:paula-patterns",
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SUGGESTS,
        when="investigating or inspecting code",
        reason=(
            "When investigating or inspecting code, the pattern scout should "
            "reach Domain-Driven Design. Composition-only under today's "
            "traversal, authored per the #3063 operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SUGGESTS,
        when="investigating or inspecting code",
        reason=(
            "When investigating or inspecting code, the reducer should reach "
            "Domain-Driven Design. Composition-only under today's traversal, "
            "authored per the #3063 operator attestation."
        ),
    ),
    # -----------------------------------------------------------------------
    # #3063 family-B (REFACTORING family), operator interview outcome. The
    # operator has ATTESTED these relationships; the hub is a NEW built-in
    # directive, `directive:DISCIPLINED_REFACTORING` (authored as
    # packs/built-in/directives/disciplined-refactoring.directive.yaml).
    #
    # URN CASING NOTE: the wiring instruction named the hub
    # `directive:disciplined-refactoring` (lower-kebab). A directive node's URN is
    # derived from its artifact `id`, and the Directive model requires `id` to
    # match `^[A-Z][A-Z0-9_-]*$` while `id_normalizer.normalize_directive_id`
    # upper-cases any non-numeric slug — so the only URN a real directive artifact
    # can yield here is `directive:DISCIPLINED_REFACTORING` (exactly the
    # `directive:RECONCILE_CHANGE_SCOPE_TENSIONS` precedent). The lower-kebab form
    # is unreachable through the schema; the canonical URN is corrected to
    # UPPER_SNAKE here and recorded in
    # docs/plans/doctrine/delivery-reachability-wiring-table.md.
    #
    # This family is INERT under today's traversal (composition-only) — measured,
    # not assumed:
    #
    #   * SEVEN `suggests` edges, DISCIPLINED_REFACTORING -> each refactoring
    #     tactic, each carrying a per-tactic `when` = the applicability/"problem"
    #     the tactic solves (refactoring.guru-style "when to consider this
    #     refactor"), derived from the tactic's OWN purpose/first-step text (not
    #     invented). These deliver nothing under the action channel: the directive
    #     is scoped by no action, so `resolve_context` never reaches it, and
    #     `suggests` is only walked FROM scope-resolved artifacts — so its outbound
    #     `suggests` edges are never traversed. The seven tactics stay
    #     action-unreachable (they already were).
    #
    #   * SEVEN `suggests` edges, each implementer-role agent profile ->
    #     DISCIPLINED_REFACTORING, all sharing the attested `when` "when tidying
    #     code, encountering long classes/methods, or discovering convoluted
    #     logic". These are inert in the profile channel too: that channel walks
    #     {requires, specializes_from} only, never `suggests`. The implementer
    #     profiles are every built-in profile whose role is `implementer`
    #     (python-pedro is primary): frontend-freddy, generic-agent,
    #     implementer-ivan, java-jenny, node-norris, python-pedro, randy-reducer.
    #
    # Net reachability move: NONE. `directive:DISCIPLINED_REFACTORING` is a new
    # built-in directive that this project's charter does NOT activate, so it
    # never enters the `_activated()` universe the reachability pins subtract
    # from; the fourteen edges are `suggests` on both channels, which neither
    # channel follows into delivery. Measured with the WP08 helper: the
    # `_ACTION_UNREACHABLE_D1`/`D2`, `_PROFILE_UNREACHABLE` and `_PROFILE_RESCUES`
    # sets are UNCHANGED. Only composition counts move (one new directive node via
    # extraction + fourteen overlay edges); ledgered in the wiring-table doc and
    # test_extractor_projection's composition ledger.
    #
    # DEFERRED (recorded, NOT authored here): (1) the refactoring tactics remain
    # in the delivery-reachability DEFERRED set — their delivery needs the
    # profile-channel walk to follow `suggests` (topology authored, delivery
    # pending fast-follow); (2) an `anti_pattern`-authoring companion (each code
    # smell -> the refactor that resolves it) is a doctrine-CONTENT decision left
    # to the fast-follow, not authored in this pass.
    # -----------------------------------------------------------------------
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-encapsulate-record",
        relation=Relation.SUGGESTS,
        when=(
            "a raw data record (a dict, plain object, or mutably-used named "
            "tuple) is accessed by field name from many call sites, and that "
            "direct access blocks adding validation, renaming fields, or changing "
            "the internal representation"
        ),
        reason=(
            "Disciplined refactoring suggests Encapsulate Record when the smell is "
            "an unencapsulated data record; the `when` is the tactic's own stated "
            "applicability. Composition-only under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-encapsulate-variable",
        relation=Relation.SUGGESTS,
        when=(
            "a widely-accessed module-level or global variable (or public class "
            "attribute) is read and written from many locations and needs a single "
            "chokepoint for monitoring, validation, or a later change of type"
        ),
        reason=(
            "Disciplined refactoring suggests Encapsulate Variable when the smell "
            "is a globally-accessed variable with no chokepoint; the `when` is the "
            "tactic's own stated applicability. Composition-only under today's "
            "traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-extract-first-order-concept",
        relation=Relation.SUGGESTS,
        when=("an important concept is implicit, duplicated, or scattered across the code with no explicit name or single home"),
        reason=(
            "Disciplined refactoring suggests Extract First-Order Concept when the "
            "smell is a hidden/duplicated concept that should be named; the `when` "
            "is the tactic's own stated applicability. Composition-only under "
            "today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-move-field",
        relation=Relation.SUGGESTS,
        when=("a field is read and modified more by another class than the one that declares it, so data ownership has drifted"),
        reason=(
            "Disciplined refactoring suggests Move Field when the smell is a field "
            "living on the wrong owner; the `when` is the tactic's own stated "
            "applicability. Composition-only under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-move-method",
        relation=Relation.SUGGESTS,
        when=("a method uses more of another class's data and behaviour than its own host's (feature envy)"),
        reason=(
            "Disciplined refactoring suggests Move Method when the smell is feature "
            "envy; the `when` is the tactic's own stated applicability (its first "
            "step confirms feature envy and target ownership). Composition-only "
            "under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-state-pattern-for-behavior",
        relation=Relation.SUGGESTS,
        when=(
            "a class's methods are full of conditionals branching on the same "
            "internal state variable (enum, status flag, boolean), and behaviour is "
            "driven by lifecycle state transitions"
        ),
        reason=(
            "Disciplined refactoring suggests State Pattern for Behavior when the "
            "smell is sprawling conditionals switching on an object's lifecycle "
            "state; the `when` is the tactic's own stated applicability. "
            "Composition-only under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        target="tactic:refactoring-strangler-fig",
        relation=Relation.SUGGESTS,
        when=(
            "a legacy component or code path must be replaced incrementally — "
            "running the new implementation alongside the old and rerouting callers "
            "one at a time — because a single-step cutover is too risky"
        ),
        reason=(
            "Disciplined refactoring suggests Strangler Fig when the smell is a "
            "legacy path that cannot be replaced in one safe step; the `when` is "
            "the tactic's own stated applicability. Composition-only under today's "
            "traversal."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_FRONTEND_FREDDY,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal (the profile channel walks requires/specializes_from only), "
            "authored per the #3063 family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_GENERIC_AGENT,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal, authored per the #3063 family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_IMPLEMENTER_IVAN,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal, authored per the #3063 family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_JAVA_JENNY,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal, authored per the #3063 family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_NODE_NORRIS,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal, authored per the #3063 family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_PYTHON_PEDRO,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            "The primary implementer-role profile should reach the "
            "disciplined-refactoring directive when restructuring code. "
            "Composition-only under today's traversal, authored per the #3063 "
            "family-B operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_DIRECTIVE_DISCIPLINED_REFACTORING,
        relation=Relation.SUGGESTS,
        when=_WHEN_DISCIPLINED_REFACTORING_TIDYING,
        reason=(
            _REASON_IMPLEMENTER_REACHES_DISCIPLINED_REFACTORING + "directive when restructuring code. Composition-only under today's "
            "traversal, authored per the #3063 family-B operator attestation."
        ),
    ),
    # -----------------------------------------------------------------------
    # #3063 family-C (ARCHITECTURE-DOCS / DIAGRAMMING family), operator
    # interview outcome. The operator has ATTESTED these relationships; the hub
    # is a NEW built-in directive, `directive:USE_C4_MODEL_TECHNIQUES` (authored
    # as packs/built-in/directives/use-c4-model-techniques.directive.yaml).
    #
    # URN CASING NOTE (same rule as family-B's DISCIPLINED_REFACTORING): the
    # wiring named the hub `directive:use-c4-model-techniques` (lower-kebab). A
    # directive node's URN is derived from its artifact `id`, and the Directive
    # model requires `id` to match `^[A-Z][A-Z0-9_-]*$` while
    # `id_normalizer.normalize_directive_id` upper-cases any non-numeric slug — so
    # the only URN a real directive artifact can yield is
    # `directive:USE_C4_MODEL_TECHNIQUES` (the RECONCILE_CHANGE_SCOPE_TENSIONS /
    # DISCIPLINED_REFACTORING precedent). Recorded in
    # docs/plans/doctrine/delivery-reachability-wiring-table.md.
    #
    # This family is INERT under today's traversal (composition-only) — measured,
    # not assumed:
    #
    #   * SEVEN `suggests` edges, USE_C4_MODEL_TECHNIQUES -> each attested
    #     architecture-documentation technique, each carrying a per-member `when`
    #     grounded in the member's OWN purpose/scope text (not invented). These
    #     deliver nothing under the action channel: the directive is scoped by no
    #     action, so `resolve_context` never reaches it, and `suggests` is only
    #     walked FROM scope-resolved artifacts. The members stay action-unreachable
    #     (they already were — all seven are in the delivery-reachability DEFERRED
    #     set).
    #
    #   * ONE `suggests` edge, USE_C4_MODEL_TECHNIQUES -> paradigm:domain-driven-
    #     design: the reinforcement ("supporting") bridge the operator attested.
    #     `suggests` is the closest ATTESTED relation for "supporting/reinforces"
    #     (a soft, non-mandatory pointer) — no new relation kind was invented. It
    #     is INBOUND to the DDD paradigm, which Family A already made action-
    #     reachable; it therefore delivers nothing new (a directive->paradigm edge
    #     does not make the SOURCE reachable) and moves no pin. The documentation-
    #     family leg of the "supporting the documentation and DDD paradigms"
    #     instruction needs no separate edge: `paradigm:c4-incremental-detail-
    #     modeling` IS the documentation/architecture-modelling paradigm and is
    #     already a member above, so the documentation leg is covered by the member
    #     edge and only the DDD leg is added here.
    #
    #   * ONE `suggests` edge, agent_profile:architect-alphonso ->
    #     USE_C4_MODEL_TECHNIQUES, `when` = "documenting or reviewing system
    #     architecture" (alphonso's attested scope: roles=architect, capabilities
    #     system-design / architecture-review / component-design). Inert in the
    #     profile channel too: that channel walks {requires, specializes_from}
    #     only, never `suggests`.
    #
    # EXCLUDED as non-attested (reported to the operator): the #3063 candidate
    # `procedure:documentation-gap-prioritization`. Its own text triages
    # documentation gaps by user impact across ALL doc types (tutorials, how-tos,
    # reference, explanation) — a documentation-project-management technique, not a
    # C4 / architecture-documentation / diagramming one. No member edge is
    # authored for it; it stays in the DEFERRED set.
    #
    # Net reachability move: NONE. `directive:USE_C4_MODEL_TECHNIQUES` is a new
    # built-in directive this project's charter does NOT activate, so it never
    # enters the `_activated()` universe the reachability pins subtract from; all
    # nine edges are `suggests` on channels that do not follow `suggests` into
    # delivery. Measured with the WP08 helper: `_ACTION_UNREACHABLE_D1`/`D2`,
    # `_PROFILE_UNREACHABLE` and `_PROFILE_RESCUES` are UNCHANGED. Only composition
    # counts move (one new directive node via extraction + nine overlay edges);
    # ledgered in the wiring-table doc and test_extractor_projection's ledger.
    #
    # DEFERRED (recorded, NOT authored here): the seven architecture-doc technique
    # members remain in the delivery-reachability DEFERRED set — topology authored,
    # delivery pending fast-follow (their delivery needs the directive to be
    # action-scoped, or the profile channel to follow `suggests`).
    # -----------------------------------------------------------------------
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target=_URN_PARADIGM_C4_INCREMENTAL_DETAIL_MODELING,
        relation=Relation.SUGGESTS,
        when=(
            "communicating a system's architecture to more than one audience at "
            "more than one level of detail, so it must be broken into progressive "
            "zoom levels (System Context, Container, Component, Code) rather than a "
            "single all-in-one diagram"
        ),
        reason=(
            "The C4 hub suggests the C4 incremental-detail paradigm as its core "
            "mental model; the `when` is the paradigm's own stated purpose "
            "(progressive zoom, right detail per audience). Composition-only under "
            "today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="tactic:c4-zoom-in-architecture-documentation",
        relation=Relation.SUGGESTS,
        when=(
            "actually drawing the architecture diagrams — starting from the System "
            "Context and zooming in to Container and Component levels only where "
            "additional detail adds value"
        ),
        reason=(
            "The C4 hub suggests the zoom-in documentation workflow as the concrete "
            "step-by-step technique; the `when` is the tactic's own stated purpose. "
            "Composition-only under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="tactic:architecture-diagram-review-checklist",
        relation=Relation.SUGGESTS,
        when=(
            "an architecture diagram is about to be shared, committed, or included "
            "in documentation and must communicate to its audience without a verbal "
            "walkthrough (title, legend, typed described elements, labelled "
            "unidirectional relationships)"
        ),
        reason=(
            "The C4 hub suggests the diagram review checklist as its quality gate; "
            "the `when` is the tactic's own stated purpose. Composition-only under "
            "today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="toolguide:mermaid-diagramming",
        relation=Relation.SUGGESTS,
        when=("rendering the architecture diagrams as text-based, version-controlled diagram-as-code in Mermaid so they diff and review beside the code"),
        reason=(
            "The C4 hub suggests the Mermaid toolguide as one text-based rendering "
            "option satisfying its 'keep diagrams as diagram-as-code' rule; the "
            "`when` is the toolguide's own stated scope. Composition-only under "
            "today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="toolguide:plantuml-diagramming",
        relation=Relation.SUGGESTS,
        when=("rendering the architecture diagrams as text-based, version-controlled diagram-as-code in PlantUML so they diff and review beside the code"),
        reason=(
            "The C4 hub suggests the PlantUML toolguide as the other text-based "
            "rendering option satisfying its 'keep diagrams as diagram-as-code' "
            "rule; the `when` is the toolguide's own stated scope. Composition-only "
            "under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="procedure:drill-down-documentation",
        relation=Relation.SUGGESTS,
        when=(
            "capturing decisions, documentation, and architecture descriptions at a "
            "consistent abstraction level (organisational, architecture, design, "
            "code) with upward and downward traceability, rather than mixing levels "
            "in one artifact"
        ),
        reason=(
            "The C4 hub suggests the drill-down documentation procedure as the "
            "abstraction-level discipline that keeps each artifact at one C4 zoom "
            "level; the `when` is the procedure's own stated purpose/entry "
            "condition. Composition-only under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target="tactic:code-documentation-analysis",
        relation=Relation.SUGGESTS,
        when=(
            "reverse-engineering or reviewing an existing system's architecture — "
            "extracting terminology from its code and documentation to surface "
            "implicit context boundaries before they calcify into accidental "
            "coupling"
        ),
        reason=(
            "The C4 hub suggests code/documentation analysis as the technique for "
            "discovering an existing system's architecture (implicit boundaries) "
            "prior to documenting it; the `when` is the tactic's own stated purpose "
            "(architectural review / boundary discovery). Composition-only under "
            "today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SUGGESTS,
        when=(
            "the architecture being documented is organised around a domain model, "
            "so its container/component boundaries should reflect bounded contexts "
            "and the ubiquitous language"
        ),
        reason=(
            "The reinforcement ('supporting') bridge the #3063 operator attested: "
            "the C4 architecture-documentation hub suggests the Domain-Driven Design "
            "paradigm so architecture diagrams and domain boundaries reinforce each "
            "other. `suggests` is the closest attested relation for a soft "
            "supporting/reinforces pointer (no new relation kind invented). INBOUND "
            "to the already-action-reachable DDD paradigm (Family A), so it delivers "
            "nothing new and moves no pin — composition-only under today's "
            "traversal. The documentation-family leg of 'supporting the "
            "documentation and DDD paradigms' is already covered by the member edge "
            "to paradigm:c4-incremental-detail-modeling, which IS the documentation/"
            "architecture-modelling paradigm."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_ARCHITECT_ALPHONSO,
        target=_URN_DIRECTIVE_USE_C4_MODEL_TECHNIQUES,
        relation=Relation.SUGGESTS,
        when="documenting or reviewing system architecture",
        reason=(
            "The architect profile should reach the C4 architecture-documentation "
            "hub when documenting or reviewing system architecture (alphonso's "
            "attested scope: system-design / architecture-review / component-"
            "design). Composition-only under today's traversal (the profile channel "
            "walks requires/specializes_from only), authored per the #3063 family-C "
            "operator attestation."
        ),
    ),
    # -----------------------------------------------------------------------
    # #3063 family-D (TESTING / BDD / MUTATION family), operator interview
    # outcome. The operator has ATTESTED these relationships AND ruled
    # ACCEPT DELIVERY (2026-07-29): unlike families B and C, family D is
    # REACHABILITY-AFFECTING, not composition-only. The reason is measured, not
    # assumed: two of the four hubs are EXISTING directives already `scope`-linked
    # from actions —
    #   * directive:DIRECTIVE_034 (test-first-development) is scoped by
    #     action:software-dev/implement AND action:software-dev/review;
    #   * directive:DIRECTIVE_030 (test-and-typecheck-quality-gate) is scoped by
    #     the same two actions.
    # `resolve_context` step 3 walks `suggests` FROM the scope-resolved artifacts,
    # so a `suggests` edge sourced at 034/030 IS followed and DELIVERS its target
    # at implement/review. That is the opposite of the family-B/C pattern, where
    # the hub was a NEW, non-scoped directive whose outbound `suggests` were never
    # walked (inert). The operator wants this delivery: the BDD + test-quality
    # families become action-reachable at implement/review now, and the pins in
    # tests/doctrine/drg/test_reachability.py are updated to the measured result
    # (exactly as family-A did for DDD-at-specify), NOT left unchanged.
    #
    # Measured with the WP08 helper (resolve_context / action_channel_reachable),
    # before -> after the full family-D edge set + 5 new artefacts + the inert
    # event-storming edge:
    #   * _ACTION_UNREACHABLE_D1 67 -> 60. The SEVEN delivered at d=1 (compact):
    #     from DIRECTIVE_034 — development-bdd, atdd-adversarial-acceptance,
    #     specification-by-example, formalized-constraint-testing,
    #     example-mapping-workshop; from DIRECTIVE_030 — adversarial-qa-handoff,
    #     work-package-completion-validation.
    #   * _ACTION_UNREACHABLE_D2 60 -> 50. The above seven PLUS three more reached
    #     only at the bootstrap depth d=2: reverse-speccing and
    #     test-to-system-reconstruction (via paradigm:brownfield-onboarding, which
    #     is not itself scoped but is reachable through a <=2-hop suggests chain, so
    #     a further suggests hop lands within the d=2 bound), and
    #     mutation-aware-test-design (a 2-hop suggests chain out of DIRECTIVE_030).
    #   * _ACTION_D1_D2_SPREAD 7 -> 10: reverse-speccing, test-to-system-
    #     reconstruction and mutation-aware-test-design were in BOTH old sets; they
    #     leave d=2 only, so they now sit in (D1 - D2).
    #   * _PROFILE_UNREACHABLE UNCHANGED (153): every family-D profile edge is
    #     `suggests`, which the profile channel (requires/specializes_from) does not
    #     follow.
    #   * _PROFILE_RESCUES 4 -> 2 (= _ACTION_UNREACHABLE_D2 - _PROFILE_UNREACHABLE):
    #     development-bdd and reverse-speccing entered the action channel, so they
    #     are no longer profile-only rescues; DIRECTIVE_044 and
    #     test-readability-clarity-check remain.
    #
    # The mutation hub is a NEW directive (directive:USE_MUTATION_TESTING_TO_
    # VALIDATE_TEST_QUALITY, authored as directives/built-in/use-mutation-testing-
    # to-validate-test-quality.directive.yaml). It is NOT charter-activated and NOT
    # action-scoped, so its four outbound `suggests` edges are INERT (its members
    # stay in the deferred set). The test-quality fan-out is SPLIT across two hubs
    # per each target's own text: DIRECTIVE_030 (the quality-BAR the gate enforces)
    # heads adversarial-qa-handoff, work-package-completion-validation,
    # testing-principles, test-desiderata-and-boundaries and toolguide:sonar;
    # DIRECTIVE_041 (tests-as-scaffold, clarity/authoring) heads
    # test-readability-clarity-check, zombies-tdd and the new quadruple-a-test-
    # format styleguide. DIRECTIVE_041 is NOT scope-linked from any action, so its
    # three `suggests` edges are inert (those members stay deferred); only the
    # 030-headed members are delivered.
    #
    # URN CASING (mutation hub): the wiring named the hub lower-kebab; the Directive
    # model's `id` pattern + id_normalizer upper-case it, so the canonical URN is
    # directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY (the
    # RECONCILE_CHANGE_SCOPE_TENSIONS / DISCIPLINED_REFACTORING precedent). Recorded
    # in docs/plans/doctrine/delivery-reachability-wiring-table.md.
    #
    # PROFILE -> hub edges (all `suggests`, all INERT in the profile channel; the
    # attested delivery vector for a future channel that follows suggests): the
    # seven implementer-role profiles reach the test-first, mutation and BOTH
    # test-quality hubs; reviewer-renata reaches the test-quality + mutation hubs;
    # debugger-debbie reaches the mutation hub.
    #
    # EVENT-STORMING (DDD-cluster membership, family-A): attached via
    # agent_profile:architect-alphonso --suggests--> procedure:event-storming-
    # discovery, which is INERT (measured: not reachable at d=1 or d=2). It is
    # DELIBERATELY NOT attached via paradigm:domain-driven-design: family-A made the
    # DDD paradigm a scope-resolved artifact (action:software-dev/specify --scope-->
    # DDD), so a DDD --suggests--> event-storming edge WOULD deliver event-storming
    # at specify (measured: reachable at d=1 and d=2) — which the operator's earlier
    # explicit guard forbids (context-overload concern). event-storming remains a
    # DDD-cluster member; it can be switched to paradigm-delivered later if the
    # operator wants it eager at specify.
    # -----------------------------------------------------------------------
    # D1. BDD/ATDD hub = directive:DIRECTIVE_034 (test-first-development).
    # DELIVERS at implement/review (034 is scope-resolved).
    DRGEdge(
        source=_URN_DIRECTIVE_034,
        target="tactic:development-bdd",
        relation=Relation.SUGGESTS,
        when=(
            "designing observable behavioural contracts at a system's public interfaces before implementation, so stakeholders can validate what the system must do"
        ),
        reason=(
            "Test-first development suggests BDD-as-behavioural-contract-design as "
            "the way to state required behaviour before code; the `when` is the "
            "tactic's own stated purpose. Delivered at implement/review (034 is "
            "scope-resolved) per the #3063 family-D ACCEPT-DELIVERY ruling."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_034,
        target="tactic:atdd-adversarial-acceptance",
        relation=Relation.SUGGESTS,
        when=(
            "hardening acceptance criteria by deliberately exploring how a feature could fail and turning selected failure modes into adversarial acceptance tests"
        ),
        reason=(
            "Test-first development suggests adversarial acceptance-test definition "
            "as the technique for strengthening acceptance criteria; the `when` is "
            "the tactic's own stated purpose. Delivered at implement/review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_034,
        target="paradigm:specification-by-example",
        relation=Relation.SUGGESTS,
        when=(
            "building shared understanding of required behaviour from concrete, "
            "business-readable examples that become executable acceptance tests and "
            "living documentation"
        ),
        reason=(
            "Test-first development suggests Specification by Example as the "
            "paradigm for driving development from concrete examples; the `when` is "
            "the paradigm's own stated summary. Delivered at implement/review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_034,
        target="tactic:formalized-constraint-testing",
        relation=Relation.SUGGESTS,
        when=(
            "verifying mathematical invariants and structural contracts (round-trip "
            "symmetry, equality/hash-code alignment, sparse serialization) with "
            "property-based rather than example-based checks"
        ),
        reason=(
            "Test-first development suggests formalized constraint testing when the "
            "behaviour to pin is an invariant/contract better checked by property "
            "patterns than by examples; the `when` is the tactic's own stated "
            "purpose. Delivered at implement/review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_034,
        target="procedure:example-mapping-workshop",
        relation=Relation.SUGGESTS,
        when=("turning a behaviour request into concrete rules, examples, and open questions as a shared specification set before implementation"),
        reason=(
            "Test-first development suggests the Example Mapping workshop as the "
            "collaborative step that produces the examples tests are written from; "
            "the `when` is the procedure's own stated purpose. Delivered at "
            "implement/review."
        ),
    ),
    # NOTE (#3009, mission kind-complete-cascade-orphan-wiring-01M0FQCD, WP02):
    # the DIRECTIVE_034 --suggests--> {styleguide:given-when-then-authoring,
    # toolguide:gherkin} overlay edges were PROMOTED to DIRECTIVE_034's own
    # ``references`` frontmatter (single canonical authority). The extractor now
    # mints these edges directly from the directive YAML, byte-identical (same
    # source/target/relation/when/reason), so they were removed here to keep a
    # single source of truth. See packs/built-in/directives/034-test-first-
    # development.directive.yaml.
    # D2. Brownfield onboarding hub = paradigm:brownfield-onboarding.
    # Not scope-resolved itself, but reachable via a <=2-hop suggests chain, so
    # these DELIVER at the bootstrap depth d=2 only. `suggests` matches how
    # brownfield already links its non-mandatory members (it mixes requires for
    # hard prerequisites with suggests, e.g. tactic:reverse-speccing below).
    DRGEdge(
        source=_URN_PARADIGM_BROWNFIELD_ONBOARDING,
        target="tactic:reverse-speccing",
        relation=Relation.SUGGESTS,
        when=(
            "reconstructing system understanding purely from test code and "
            "comparing it against the implementation and design docs to reveal "
            "under-documented behaviour"
        ),
        reason=(
            "Brownfield onboarding suggests reverse-speccing as the technique for "
            "recovering intent from an existing system's tests; the `when` is the "
            "tactic's own stated purpose. Delivered at d=2 per the family-D "
            "ACCEPT-DELIVERY ruling."
        ),
    ),
    DRGEdge(
        source=_URN_PARADIGM_BROWNFIELD_ONBOARDING,
        target="tactic:test-to-system-reconstruction",
        relation=Relation.SUGGESTS,
        when=(
            "scoring how effectively a legacy system's tests serve as executable "
            "specifications, identifying where they fail to communicate "
            "behavioural, architectural, or operational intent"
        ),
        reason=(
            "Brownfield onboarding suggests test-to-system reconstruction as the "
            "scored dual-agent validation of a legacy suite's specification "
            "quality; the `when` is the tactic's own stated purpose. Delivered at "
            "d=2."
        ),
    ),
    # D3. Mutation hub = NEW directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY.
    # INERT: the directive is not action-scoped and not charter-activated, so its
    # outbound `suggests` are never walked; these members stay in the deferred set.
    DRGEdge(
        source=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        target="tactic:mutation-testing-workflow",
        relation=Relation.SUGGESTS,
        when=("running mutation testing to verify tests detect real bugs rather than merely execute code, and triaging the surviving mutants"),
        reason=(
            "The mutation hub suggests the run/triage workflow as its concrete "
            "step-by-step technique; the `when` is the tactic's own stated purpose. "
            "Inert under today's traversal (the new hub directive is not action-"
            "scoped)."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        target="styleguide:mutation-aware-test-design",
        relation=Relation.SUGGESTS,
        when=("designing tests so common mutants (boundary, logic, membership, aggregate) are killed rather than tolerated"),
        reason=(
            "The mutation hub suggests the mutation-aware test-design conventions "
            "as the design discipline that makes mutants killable; the `when` is "
            "the styleguide's own scope. Inert under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        target="toolguide:python-mutation-tools",
        relation=Relation.SUGGESTS,
        when=("running mutation testing on Python code with mutmut (run/browse/apply, equivalent-mutant annotation)"),
        reason=(
            "The mutation hub suggests the Python mutation toolguide (mutmut) as the "
            "generator for Python; the `when` is the toolguide's own scope. Inert "
            "under today's traversal."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        target="toolguide:typescript-mutation-tools",
        relation=Relation.SUGGESTS,
        when=("running mutation testing on TypeScript/JavaScript code with Stryker"),
        reason=(
            "The mutation hub suggests the TypeScript/JavaScript mutation toolguide "
            "(Stryker) as the generator for that stack; the `when` is the "
            "toolguide's own scope. Inert under today's traversal."
        ),
    ),
    # D4a. Test-quality hub = directive:DIRECTIVE_030 (test-and-typecheck-quality-
    # gate) — the quality BAR the gate enforces. DELIVERS at implement/review (030
    # is scope-resolved).
    DRGEdge(
        source=_URN_DIRECTIVE_030,
        target="tactic:adversarial-qa-handoff",
        relation=Relation.SUGGESTS,
        when=(
            "preparing changed code for review/QA by identifying likely failure "
            "modes up front and leaving evidence that behaviour, typing, and edge "
            "cases were verified"
        ),
        reason=(
            "The test-and-typecheck quality gate suggests the adversarial QA "
            "handoff as the pre-handoff discipline that anticipates what review/QA "
            "will probe; the `when` is the tactic's own stated purpose. Delivered "
            "at implement/review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_030,
        target="tactic:work-package-completion-validation",
        relation=Relation.SUGGESTS,
        when=("validating that a work package meets its required quality gates before its status advances to for_review or done"),
        reason=(
            "The quality gate suggests work-package completion validation as the "
            "check that its gates are actually met before a status transition; the "
            "`when` is the tactic's own stated purpose. Delivered at implement/"
            "review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_030,
        target="styleguide:testing-principles",
        relation=Relation.SUGGESTS,
        when=(
            "judging whether a test suite is fast, isolated, repeatable, self-validating, thorough and truthful — the properties the quality gate exists to protect"
        ),
        reason=(
            "The quality gate suggests the testing-principles styleguide as the "
            "properties a suite must have to pass it; the `when` is the styleguide's "
            "own subject. Delivered at implement/review."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_030,
        target="styleguide:test-desiderata-and-boundaries",
        relation=Relation.SUGGESTS,
        when=(
            "assessing tests against the test desiderata (Kent Beck) and drawing each "
            "test's boundary by functional responsibility, with infrastructure stubbed "
            "outside it"
        ),
        reason=(
            "The quality gate suggests the test-desiderata-and-boundaries styleguide "
            "as the finer-grained bar for a good test; the `when` is the "
            "styleguide's own subject. Delivered at implement/review."
        ),
    ),
    # NOTE (#3009, mission kind-complete-cascade-orphan-wiring-01M0FQCD, WP02):
    # the DIRECTIVE_030 --suggests--> toolguide:sonar overlay edge was PROMOTED to
    # DIRECTIVE_030's own ``references`` frontmatter (single canonical authority);
    # the extractor now mints it byte-identical from the directive YAML, so it was
    # removed here. See packs/built-in/directives/030-test-and-typecheck-quality-
    # gate.directive.yaml.
    # D4b. Test-quality hub = directive:DIRECTIVE_041 (tests-as-scaffold-not-
    # friction) — the clarity / authoring side. INERT: 041 is NOT scope-linked from
    # any action, so its `suggests` are never walked; these members stay deferred.
    DRGEdge(
        source=_URN_DIRECTIVE_041,
        target="tactic:test-readability-clarity-check",
        relation=Relation.SUGGESTS,
        when=("checking whether a test suite documents behaviour well enough to reconstruct the system from tests alone (tests as executable specification)"),
        reason=(
            "Tests-as-scaffold suggests the readability/clarity check as the way to "
            "confirm tests remain a legible specification, not friction; the `when` "
            "is the tactic's own stated purpose. Inert (041 is not action-scoped)."
        ),
    ),
    DRGEdge(
        source=_URN_DIRECTIVE_041,
        target="tactic:zombies-tdd",
        relation=Relation.SUGGESTS,
        when=("driving implementation through tiny behaviour increments (ZOMBIES) with failing tests to control complexity"),
        reason=(
            "Tests-as-scaffold suggests ZOMBIES TDD as the increment-sized way to "
            "let tests scaffold the implementation; the `when` is the tactic's own "
            "stated purpose. Inert (041 is not action-scoped)."
        ),
    ),
    # NOTE (#3009, mission kind-complete-cascade-orphan-wiring-01M0FQCD, WP02):
    # the DIRECTIVE_041 --suggests--> styleguide:quadruple-a-test-format overlay
    # edge was PROMOTED to DIRECTIVE_041's own ``references`` frontmatter (single
    # canonical authority); the extractor now mints it byte-identical from the
    # directive YAML, so it was removed here. 041 stays non-action-scoped, so this
    # edge remains inert in the shipped reachability channels. See packs/built-in/
    # directives/041-tests-as-scaffold-not-friction.directive.yaml.
    # D5. Profile -> hub (all `suggests`, all INERT in the profile channel; the
    # attested delivery vector for a future channel that follows suggests).
    # Seven implementer-role profiles -> {test-first 034, mutation, test-quality
    # 030, test-quality 041}.
    DRGEdge(
        source=_URN_PROFILE_FRONTEND_FREDDY,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel (walks "
            "requires/specializes_from only), authored per the #3063 family-D "
            "operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_FRONTEND_FREDDY,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_FRONTEND_FREDDY,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_FRONTEND_FREDDY,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_GENERIC_AGENT,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel, authored per "
            "the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_GENERIC_AGENT,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_GENERIC_AGENT,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_GENERIC_AGENT,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_IMPLEMENTER_IVAN,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel, authored per "
            "the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_IMPLEMENTER_IVAN,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_IMPLEMENTER_IVAN,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_IMPLEMENTER_IVAN,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_JAVA_JENNY,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel, authored per "
            "the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_JAVA_JENNY,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_JAVA_JENNY,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_JAVA_JENNY,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_NODE_NORRIS,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel, authored per "
            "the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_NODE_NORRIS,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_NODE_NORRIS,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_NODE_NORRIS,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_PYTHON_PEDRO,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            "The primary implementer-role profile should reach the test-first hub "
            "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_PYTHON_PEDRO,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            "The primary implementer-role profile should reach the mutation hub "
            "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_PYTHON_PEDRO,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            "The primary implementer-role profile should reach the test-quality-"
            "gate hub when assessing test quality. Composition-only in the profile "
            "channel, authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_PYTHON_PEDRO,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            "The primary implementer-role profile should reach the tests-as-"
            "scaffold hub when writing tests. Composition-only in the profile "
            "channel, authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_DIRECTIVE_034,
        relation=Relation.SUGGESTS,
        when=_WHEN_WRITING_OR_REVIEWING_ACCOMPANYING_TESTS,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_FIRST_HUB + "writing tests. Composition-only in the profile channel, authored per "
            "the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when=_WHEN_ASSESSING_TESTS_CONSTRAIN_BEHAVIOUR,
        reason=(
            _REASON_IMPLEMENTER_REACHES_MUTATION_HUB + "assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when=_WHEN_TESTS_MEET_QUALITY_GATE,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TEST_QUALITY_GATE_HUB + "when assessing test quality. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_RANDY_REDUCER,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when=_WHEN_KEEPING_TESTS_AS_SCAFFOLD,
        reason=(
            _REASON_IMPLEMENTER_REACHES_TESTS_AS_SCAFFOLD_HUB + "when writing tests. Composition-only in the profile channel, authored "
            "per the #3063 family-D operator attestation."
        ),
    ),
    # reviewer-renata -> {test-quality 030, test-quality 041, mutation}
    DRGEdge(
        source=_URN_PROFILE_REVIEWER_RENATA,
        target=_URN_DIRECTIVE_030,
        relation=Relation.SUGGESTS,
        when="when assessing the quality of the tests under review",
        reason=(
            "The reviewer profile should reach the test-quality-gate hub when "
            "assessing the tests under review. Composition-only in the profile "
            "channel, authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_REVIEWER_RENATA,
        target=_URN_DIRECTIVE_041,
        relation=Relation.SUGGESTS,
        when="when assessing whether the tests under review are a clear scaffold rather than friction",
        reason=(
            "The reviewer profile should reach the tests-as-scaffold hub when "
            "assessing the tests under review. Composition-only in the profile "
            "channel, authored per the #3063 family-D operator attestation."
        ),
    ),
    DRGEdge(
        source=_URN_PROFILE_REVIEWER_RENATA,
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when="when assessing whether the tests under review actually constrain behaviour",
        reason=(
            "The reviewer profile should reach the mutation hub when assessing test "
            "quality under review. Composition-only in the profile channel, "
            "authored per the #3063 family-D operator attestation."
        ),
    ),
    # debugger-debbie -> {mutation}
    DRGEdge(
        source="agent_profile:debugger-debbie",
        target=_URN_DIRECTIVE_USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY,
        relation=Relation.SUGGESTS,
        when="when assessing whether the tests around a defect actually constrain the behaviour that broke",
        reason=(
            "The investigator/reviewer profile should reach the mutation hub when "
            "checking that the tests around a defect genuinely pin the behaviour. "
            "Composition-only in the profile channel, authored per the #3063 "
            "family-D operator attestation."
        ),
    ),
    # D6. Event-storming (DDD-cluster membership, family-A) attached INERT via the
    # architect profile, NOT via the DDD paradigm (which would deliver it at
    # specify). Measured inert: not reachable at d=1 or d=2.
    DRGEdge(
        source=_URN_PROFILE_ARCHITECT_ALPHONSO,
        target="procedure:event-storming-discovery",
        relation=Relation.SUGGESTS,
        when=("discovering domain events, commands, aggregates, policies, read models, and bounded-context boundaries from real business flows"),
        reason=(
            "Event Storming is a DDD-cluster discovery procedure (family-A). The "
            "operator's earlier guard keeps it OUT of the eager specify delivery "
            "(context-overload concern), so it is attached via the architect "
            "profile — INERT in the profile channel (requires/specializes_from "
            "only) — rather than via paradigm:domain-driven-design, which is "
            "scope-resolved (family-A) and would deliver it at specify. It can be "
            "switched to paradigm-delivered later if the operator wants it eager."
        ),
    ),
    # -----------------------------------------------------------------------
    # #3063 family-E (ANALYSIS / TERMINOLOGY / REASONS-CANVAS family), operator
    # interview outcome. The operator ATTESTED these relationships (C-007(a)
    # satisfied by operator ruling); each `when` is additionally grounded in the
    # SOURCE artefact's OWN text so a reviewer can verify it is not a topic-
    # adjacency invention. Family E authors NO new artefact files -- every
    # endpoint already exists -- so node count / `_EXPECTED_NODE_COUNT` stay
    # unchanged; all nine edges were overlay-authored `suggests` (seven remain
    # here since the two terminology-guard edges moved to `packs/internal`).
    #
    # Family E is INERT under today's traversal (composition-only) -- measured
    # with the WP08 helper, not assumed. Every source is either
    # `agent_profile:architect-alphonso` (a profile: the profile channel walks
    # {requires, specializes_from} only, so profile--suggests-->X is inert) or an
    # action-UNREACHABLE tactic/toolguide (`terminology-extraction-mapping` and
    # `contextive` are both in the pinned
    # `_ACTION_UNREACHABLE_D1`/`D2` sets, and `resolve_context` walks `suggests`
    # only FROM scope-resolved artifacts, never from an unreachable source). The
    # reinforcement edges (E-group-1) point INTO already-reachable paradigms,
    # which does not make the source reachable. Measured before/after with the
    # WP08 helper: `_ACTION_UNREACHABLE_D1`/`D2`, `_PROFILE_UNREACHABLE` and
    # `_PROFILE_RESCUES` are UNCHANGED. No pin moves; only composition counts
    # (nine overlay `suggests` edges). The deferred set stays at 50 -- no artefact
    # leaves it (delivery is the fast-follow's job per the operator).
    #
    # E1 (reasons-canvas / SPDD). The operator ruled: link only the canvas
    # *writing* as `suggests` to alphonso, for now. ONE edge.
    DRGEdge(
        source=_URN_PROFILE_ARCHITECT_ALPHONSO,
        target="styleguide:reasons-canvas-writing",
        relation=Relation.SUGGESTS,
        when=(
            "capturing the change-intent, decision boundaries and safeguards of a "
            "mission or a significant architectural change as a REASONS Canvas -- "
            "recording architectural decisions with rationale rather than mirroring "
            "code"
        ),
        reason=(
            "The architect should reach the REASONS Canvas writing styleguide when "
            "documenting the intent behind a significant architectural change: "
            "alphonso's attested scope is architectural decisions documented with "
            "rationale (DIRECTIVE_003, ADR/design outputs), and the styleguide's own "
            "purpose is to capture intent -- Safeguard (must) / Norm (should) / "
            "Approach (may) -- for a mission or change, not to mirror code. "
            "Composition-only under today's traversal (the profile channel walks "
            "requires/specializes_from only), authored per the #3063 family-E "
            "operator ruling (canvas WRITING only; the reasons-canvas fill/review "
            "tactics and the SPDD paradigm stay in the deferred set, untouched)."
        ),
    ),
    # -----------------------------------------------------------------------
    # E2 group 1 -- reinforcement into paradigms (member -> paradigm, `suggests`,
    # following the family-C "C8 DDD-bridge" precedent: source = the member,
    # target = the paradigm, so it is inert). The operator noted the terminology/
    # analysis tactics "link to both DDD and Brownfield approaches"; authored ONLY
    # where the tactic's OWN text attests (C-007a). Only
    # `terminology-extraction-mapping` attests either paradigm; see the EXCLUDED
    # audit below for the other three.
    DRGEdge(
        source=_URN_TACTIC_TERMINOLOGY_EXTRACTION_MAPPING,
        target=_URN_PARADIGM_DOMAIN_DRIVEN_DESIGN,
        relation=Relation.SUGGESTS,
        when=(
            "the extracted terms must be owned by a bounded context and cross-"
            "context uses translated at the boundary -- the strategic-DDD ubiquitous-"
            "language and anti-corruption-layer concerns the mapping surfaces"
        ),
        reason=(
            "The terminology-extraction-mapping tactic's OWN text attests DDD "
            "strategic design verbatim: it assigns term ownership 'by bounded "
            "context', translates cross-context uses 'at the context boundary', and "
            "names 'missing ACL or translation layers' as a failure mode -- so it "
            "reinforces Domain-Driven Design. INBOUND to the already-action-"
            "reachable DDD paradigm (family-A); a member->paradigm edge does not "
            "make the source reachable, so it is composition-only under today's "
            "traversal."
        ),
    ),
    DRGEdge(
        source=_URN_TACTIC_TERMINOLOGY_EXTRACTION_MAPPING,
        target=_URN_PARADIGM_BROWNFIELD_ONBOARDING,
        relation=Relation.SUGGESTS,
        when=(
            "recovering a shared vocabulary from an existing system's source code "
            "and documentation (as a follow-up to code-documentation-analysis) so "
            "the terminology latent in the codebase is named before it is changed"
        ),
        reason=(
            "The tactic's OWN text extracts domain terms from 'source code (class/"
            "method names), documentation ... as a follow-up to code-documentation-"
            "analysis' -- recovering terminology from an existing system, which is "
            "exactly the 'terminology aliases ... inferred from the code' durable "
            "artefact brownfield-onboarding's own summary names. INBOUND to the "
            "brownfield paradigm from an action-unreachable source, so composition-"
            "only under today's traversal."
        ),
    ),
    # E2 group 2 -- glossary / language links (`suggests`). The operator: contextive
    # links to "write a glossary" (tactic:glossary-curation-interview) and
    # "language-oriented development" (tactic:language-driven-design), "as do the
    # terminology extraction mapping". NOTE: the fourth implied edge,
    # `tactic:terminology-extraction-mapping --suggests--> tactic:language-driven-
    # design`, ALREADY EXISTS as an extractor-minted edge (from that tactic's own
    # `references:` block) -- authoring it here would be a duplicate, so it is
    # OMITTED (three edges, not four). See the EXCLUDED audit.
    DRGEdge(
        source=_URN_TOOLGUIDE_CONTEXTIVE,
        target="tactic:glossary-curation-interview",
        relation=Relation.SUGGESTS,
        when=(
            "capturing the terms produced by a glossary-curation round in an "
            "enforceable, IDE-surfaced ubiquitous-language glossary (hover, auto-"
            "complete, per-context definitions)"
        ),
        reason=(
            "Contextive's own summary is a tool to 'manage ubiquitous language ... "
            "glossary file setup ... alignment with Spec Kitty glossary curation "
            "workflows', and its guide ties the glossary-curation-interview tactic's "
            "output to Contextive format. It therefore supports the write-a-glossary "
            "workflow. INERT: contextive is action-unreachable, so its outbound "
            "`suggests` are never walked."
        ),
    ),
    DRGEdge(
        source=_URN_TOOLGUIDE_CONTEXTIVE,
        target="tactic:language-driven-design",
        relation=Relation.SUGGESTS,
        when=(
            "treating terminology drift as an architectural signal -- an IDE-"
            "surfaced glossary makes same-term/different-meaning and different-term/"
            "same-concept conflicts visible in the developer workflow"
        ),
        reason=(
            "Contextive surfaces ubiquitous-language definitions with compound-word "
            "recognition and multi-context term disambiguation (its own guide), which "
            "is the tooling that makes the linguistic conflicts language-driven-design "
            "hunts for observable. It therefore supports the language-oriented "
            "development approach. INERT: contextive is action-unreachable."
        ),
    ),
    DRGEdge(
        source=_URN_TACTIC_TERMINOLOGY_EXTRACTION_MAPPING,
        target="tactic:glossary-curation-interview",
        relation=Relation.SUGGESTS,
        when=("feeding the extracted, relationship-mapped, validated terms into the HiC-led curation rounds that promote them into the living glossary"),
        reason=(
            "The extraction-mapping tactic's OWN purpose is to build 'a "
            "comprehensive, maintainable glossary' and its final step publishes the "
            "validated terms as 'the authoritative source for the project ubiquitous "
            "language' -- the input the glossary-curation-interview curation rounds "
            "consume. INERT: terminology-extraction-mapping is action-unreachable. "
            "(Its sibling edge to `tactic:language-driven-design` is OMITTED here -- "
            "it already exists as an extractor-minted edge.)"
        ),
    ),
    # E2 group 3 -- tools-support-tactics (`suggests`, toolguide -> tactic). The
    # operator: "Terminology-guard and contextive are suggested tools linking to
    # the tactics/techniques they support." Authored where the tool genuinely
    # supports the tactic's workflow (verified per-tactic); see the EXCLUDED audit
    # for the candidates left out. The two terminology-guard edges moved to the
    # maintainer-only `packs/internal/drg/fragment.yaml` together with the
    # toolguide itself: the guard names a test that exists only in this
    # repository, so it no longer ships in the built-in tier.
    DRGEdge(
        source=_URN_TOOLGUIDE_CONTEXTIVE,
        target=_URN_TACTIC_TERMINOLOGY_EXTRACTION_MAPPING,
        relation=Relation.SUGGESTS,
        when=(
            "capturing the extracted, bounded-context-owned terms in an enforceable "
            "Contextive glossary so the recovered ubiquitous language is surfaced in "
            "the IDE rather than left in a static document"
        ),
        reason=(
            "Contextive is the ubiquitous-language glossary tool; the terms "
            "terminology-extraction-mapping extracts and validates are exactly the "
            "content Contextive stores and enforces (its guide ties glossary-curation "
            "output to Contextive format). It supports the extraction-mapping "
            "workflow's output. INERT: contextive is action-unreachable."
        ),
    ),
    # -----------------------------------------------------------------------
    # T007 (mission doctrine-delivery-activation-01KYQVQK, FR-007/C-005): the
    # three `action:documentation/design --instantiates--> template:c4-*-mermaid-
    # template` edges that complete the canonical topology the wiring table's
    # Family-C asset assessment records — parallel to the pre-existing
    # `action:documentation/design --instantiates--> template:documentation/
    # documentation-plan-template.md` edge in packs/built-in/action.graph.yaml.
    #
    # HOME CHOICE (documented per D13 so a future regeneration does not silently
    # drop these): the precedent documentation-plan-template edge is NOT hand-
    # authored — it is extractor-derived via
    # charter.offering.missions.step_projection.iter_template_refs (step_projection.py:124,
    # consumed by extractor.py's "Emit template:<mission>/<file> nodes + action
    # --instantiates--> template edges"), which mints MISSION-QUALIFIED template
    # nodes/edges from a MissionStep.template-shaped field. The three C4 templates
    # are shared/general-purpose nodes (`template:c4-*-mermaid-template`, NOT
    # mission-qualified) backed by src/charter/offering/templates/architecture/ — they are
    # not one mission's step-output template, so that extractor mechanism does not
    # derive them, and action.graph.yaml is itself extractor-regenerated (a manual
    # edit there would be dropped on `spec-kitty charter pack regenerate-graph`). Per
    # this module's own docstring scope ("content the extractor has no frontmatter
    # mechanism to mint"), HAND_AUTHORED_EDGES is the correct home. Following the
    # existing one-edge-per-template convention: 3 edges.
    #
    # NOT the delivery vector (D13, topology completion only): the C4 templates
    # already deliver to the architect via the profile channel's suggests-walk
    # (WP01) reaching tactic:c4-zoom-in-architecture-documentation, whose own
    # step-level `references:` already mint edges to all three templates. No
    # query.py/reachability.py change belongs in this WP — `instantiates` is not
    # walked by any channel and is not made walkable here.
    # -----------------------------------------------------------------------
    DRGEdge(
        source=_URN_ACTION_DOCUMENTATION_DESIGN,
        target="template:c4-context-mermaid-template",
        relation=Relation.INSTANTIATES,
        reason=(
            "The documentation/design action instantiates the C4 System Context "
            "mermaid template as one of its concrete architecture-diagram outputs, "
            "completing the canonical Family-C topology (topology only; delivery "
            "rides the c4-zoom-in tactic's own references, not this edge)."
        ),
    ),
    DRGEdge(
        source=_URN_ACTION_DOCUMENTATION_DESIGN,
        target="template:c4-container-mermaid-template",
        relation=Relation.INSTANTIATES,
        reason=(
            "The documentation/design action instantiates the C4 Container mermaid "
            "template as one of its concrete architecture-diagram outputs, "
            "completing the canonical Family-C topology (topology only; delivery "
            "rides the c4-zoom-in tactic's own references, not this edge)."
        ),
    ),
    DRGEdge(
        source=_URN_ACTION_DOCUMENTATION_DESIGN,
        target="template:c4-component-mermaid-template",
        relation=Relation.INSTANTIATES,
        reason=(
            "The documentation/design action instantiates the C4 Component mermaid "
            "template as one of its concrete architecture-diagram outputs, "
            "completing the canonical Family-C topology (topology only; delivery "
            "rides the c4-zoom-in tactic's own references, not this edge)."
        ),
    ),
    # -----------------------------------------------------------------------
    # T009 (mission doctrine-delivery-activation-01KYQVQK, FR-008/C-004): the
    # seven `tactic:refactoring-* --REJECTS--> anti_pattern:<smell>` edges wiring
    # each grounded refactoring tactic to the code smell it rejects. Same
    # canonical relation and direction (good artefact -> anti_pattern) as the
    # eight shipped REJECTS edges above; this WP extends the SOURCE-kind variety
    # (tactic, not just paradigm). The validator only constrains the TARGET kind
    # (must be anti_pattern) and requires each anti_pattern have >=1 inbound
    # rejects edge — both satisfied here. `reason=` is grounded verbatim-in-intent
    # in each tactic's own attested Family-B `when` text
    # (hand_authored_overlay.py:621-728). anti_patterns are NEVER delivered/
    # activated (validation-tier only, D14): no channel walks REJECTS, so these
    # edges move no reachability pin.
    # -----------------------------------------------------------------------
    DRGEdge(
        source="tactic:refactoring-encapsulate-record",
        target="anti_pattern:unencapsulated-record",
        relation=Relation.REJECTS,
        reason=(
            "Encapsulate Record rejects the Unencapsulated Record smell: a raw "
            "data record accessed by field name from many call sites, where the "
            "direct access blocks adding validation, renaming fields, or changing "
            "the internal representation (the tactic's own attested `when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-encapsulate-variable",
        target="anti_pattern:global-data",
        relation=Relation.REJECTS,
        reason=(
            "Encapsulate Variable rejects the Global Data smell: a widely-accessed "
            "module-level or global variable read and written from many locations "
            "with no single chokepoint for monitoring, validation, or a later "
            "change of type (the tactic's own attested `when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-extract-first-order-concept",
        target="anti_pattern:implicit-concept",
        relation=Relation.REJECTS,
        reason=(
            "Extract First-Order Concept rejects the Implicit Concept smell: an "
            "important concept left implicit, duplicated, or scattered across the "
            "code with no explicit name or single home (the tactic's own attested "
            "`when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-move-field",
        target="anti_pattern:misplaced-field",
        relation=Relation.REJECTS,
        reason=(
            "Move Field rejects the Misplaced Field smell: a field read and "
            "modified more by another class than the one that declares it, so data "
            "ownership has drifted to the wrong owner (the tactic's own attested "
            "`when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-move-method",
        target="anti_pattern:feature-envy",
        relation=Relation.REJECTS,
        reason=(
            "Move Method rejects the Feature Envy smell: a method that uses more "
            "of another class's data and behaviour than its own host's (the "
            "tactic's own attested `when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-state-pattern-for-behavior",
        target="anti_pattern:repeated-switches-on-state",
        relation=Relation.REJECTS,
        reason=(
            "State Pattern for Behavior rejects the Repeated Switches on State "
            "smell: a class whose methods are full of conditionals branching on "
            "the same internal state variable, with behaviour driven by lifecycle "
            "state transitions (the tactic's own attested `when`)."
        ),
    ),
    DRGEdge(
        source="tactic:refactoring-strangler-fig",
        target="anti_pattern:big-bang-rewrite",
        relation=Relation.REJECTS,
        reason=(
            "Strangler Fig rejects the Big-Bang Rewrite anti-pattern: replacing a "
            "legacy component or code path in a single-step cutover when it is too "
            "risky, instead of running the new implementation alongside the old "
            "and rerouting callers one at a time (the tactic's own attested "
            "`when`)."
        ),
    ),
)


def merge_hand_authored_overlay(graph: DRGGraph) -> DRGGraph:
    """Return a new graph = *graph* plus the enumerated hand-authored overlay.

    Re-sorts nodes/edges identically to ``generate_graph``'s own canonical
    ordering (nodes by URN; edges by ``(source, target, relation)``) and
    re-validates the result, so the returned graph is exactly what a
    "pure extraction + the known hand-authored additions" reference should
    look like.
    """
    nodes_by_urn: dict[str, DRGNode] = {n.urn: n for n in graph.nodes}
    for node in HAND_AUTHORED_NODES:
        nodes_by_urn[node.urn] = node

    edges_by_triple: dict[tuple[str, str, str], DRGEdge] = {(e.source, e.target, e.relation.value): e for e in graph.edges}
    for edge in HAND_AUTHORED_EDGES:
        edges_by_triple[(edge.source, edge.target, edge.relation.value)] = edge

    merged = DRGGraph(
        schema_version=graph.schema_version,
        generated_at=graph.generated_at,
        generated_by=graph.generated_by,
        nodes=sorted(nodes_by_urn.values(), key=lambda n: n.urn),
        edges=sorted(
            edges_by_triple.values(),
            key=lambda e: (e.source, e.target, e.relation.value),
        ),
    )
    assert_valid(merged)
    return merged


def generate_reference_graph_with_overlay(doctrine_root: Path) -> DRGGraph:
    """The in-memory freshness/equality reference: pure extraction + overlay.

    Regenerates *doctrine_root* into a throw-away scratch directory (never
    read back), then merges in :data:`HAND_AUTHORED_NODES` /
    :data:`HAND_AUTHORED_EDGES`. This is the non-vacuous reference every
    shipped-graph comparison should use now that the extractor is no longer
    the sole source of shipped content (WP02/WP03).
    """
    from charter.offering.drg.migration.extractor import generate_graph

    with tempfile.TemporaryDirectory() as scratch:
        pure = generate_graph(doctrine_root, Path(scratch) / "graph.yaml")
    return merge_hand_authored_overlay(pure)


def write_reference_graph_with_overlay(doctrine_root: Path, output_path: Path) -> DRGGraph:
    """Like :func:`generate_reference_graph_with_overlay`, but also writes the
    merged reference as per-kind fragments beside *output_path* (via the
    extractor's own canonical writer), so it is byte-comparable against the
    committed shipped graph.
    """
    from charter.offering.drg.migration.extractor import _write_graph_yaml

    merged = generate_reference_graph_with_overlay(doctrine_root)
    _write_graph_yaml(merged, output_path)
    return merged
