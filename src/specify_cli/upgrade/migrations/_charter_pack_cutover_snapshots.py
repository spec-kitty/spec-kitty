"""Frozen snapshots of every released ``default.yaml`` / ``minimal.yaml`` activation list (FR-012, #3732).

The comparand for the cutover migration's "stale list" rows. It is frozen data,
never a live file: the shipped ``default.yaml`` is deleted after the cutover
(FR-005), and a list a project holds must be compared with what a *released*
CLI wrote, not with today's preset.

Source: ``kitty-specs/charter-pack-cutover-01M491G6/research/default-yaml-snapshots.yaml``
(every ``spec-kitty-cli`` wheel on PyPI, 174 releases from 0.2.20 to 4.0.0rc5,
sha256-verified against PyPI, read with ``yaml.safe_load`` only, 2026-10-06).
Both the ``original`` lists and the ``post_rewrite`` lists (what the rtk and
4.0.0rc5 retirement migrations turn a released list into) are included.

Comparison rule (spec FR-012): per key, order-insensitive set equality after
id normalisation (:func:`normalise_id`: a directive's ``DIRECTIVE_<NNN>`` id and
its stem compare equal). ``mission_type_activations`` has no snapshot here: the
migration never resets it.

Do not edit the literals by hand; regenerate them from the research YAML.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

from charter.drg import CORE_KIND_PLURALS

__all__ = ["DEFAULT_KIND_GATE", "DEFAULT_SNAPSHOTS", "MINIMAL_KIND_GATE", "MINIMAL_SNAPSHOTS", "normalise_id"]

#: Every distinct released ``default`` list per per-artifact key (original and post-rewrite forms).
DEFAULT_SNAPSHOTS: Mapping[str, tuple[frozenset[str], ...]] = MappingProxyType(
    {
        "activated_directives": (
            frozenset(
                {
                    "001-architectural-integrity-standard",
                    "003-decision-documentation-requirement",
                    "010-specification-fidelity-requirement",
                    "018-doctrine-versioning-requirement",
                    "024-locality-of-change",
                    "025-boy-scout-rule",
                    "028-search-tool-discipline",
                    "029-agent-commit-signing-policy",
                    "030-test-and-typecheck-quality-gate",
                    "031-context-aware-design",
                    "032-conceptual-alignment",
                    "033-targeted-staging-policy",
                    "034-test-first-development",
                    "035-bulk-edit-occurrence-classification",
                    "036-black-box-integration-testing",
                    "037-living-documentation-sync",
                    "038-structured-prompt-boundary",
                    "039-lynn-cole-engineering-culture",
                    "040-recurring-bug-structural-intervention",
                }
            ),
        ),
        "activated_tactics": (
            frozenset(
                {
                    "acceptance-test-first",
                    "adr-drafting-workflow",
                    "adversarial-qa-handoff",
                    "aggregate-boundary-design",
                    "ammerse-impact-analysis",
                    "analysis-extract-before-interpret",
                    "anti-corruption-layer",
                    "architecture-diagram-review-checklist",
                    "atdd-adversarial-acceptance",
                    "atomic-design-review-checklist",
                    "atomic-state-ownership",
                    "autonomous-operation-protocol",
                    "avoid-gold-plating",
                    "behavior-driven-development",
                    "black-box-integration-testing",
                    "boring-code-review",
                    "bounded-context-canvas-fill",
                    "bounded-context-identification",
                    "bug-fixing-checklist",
                    "c4-zoom-in-architecture-documentation",
                    "chain-of-responsibility-rule-pipeline",
                    "change-apply-smallest-viable-diff",
                    "code-documentation-analysis",
                    "code-review-incremental",
                    "compositional-stream-boundaries",
                    "connascence-analysis",
                    "context-boundary-inference",
                    "context-mapping-classification",
                    "cross-cutting-state-via-store",
                    "decision-marker-capture",
                    "deepening-opportunity-assessment",
                    "dependency-hygiene",
                    "development-bdd",
                    "documentation-curation-audit",
                    "domain-event-capture",
                    "easy-to-change",
                    "eisenhower-prioritisation",
                    "entity-value-object-classification",
                    "five-paradigm-parallel-debugging",
                    "focused-function-complexity-check",
                    "forensic-repository-audit",
                    "formalized-constraint-testing",
                    "function-over-form-testing",
                    "generated-code-stewardship",
                    "glossary-curation-interview",
                    "input-validation-fail-fast",
                    "interface-variation-design",
                    "language-driven-design",
                    "locality-of-change",
                    "mutation-testing-workflow",
                    "no-parallel-duplicate-test-runs",
                    "occurrence-classification-workflow",
                    "premortem-risk-identification",
                    "problem-decomposition",
                    "quality-gate-verification",
                    "reasons-canvas-fill",
                    "reasons-canvas-review",
                    "refactoring-change-function-declaration",
                    "refactoring-combine-functions-into-transform",
                    "refactoring-conditional-to-strategy",
                    "refactoring-consolidate-conditional-expression",
                    "refactoring-encapsulate-record",
                    "refactoring-encapsulate-variable",
                    "refactoring-extract-class-by-responsibility-split",
                    "refactoring-extract-first-order-concept",
                    "refactoring-guard-clauses-before-polymorphism",
                    "refactoring-inline-temp",
                    "refactoring-introduce-null-object",
                    "refactoring-move-field",
                    "refactoring-move-method",
                    "refactoring-replace-magic-number-with-symbolic-constant",
                    "refactoring-replace-temp-with-query",
                    "refactoring-retry-pattern",
                    "refactoring-state-pattern-for-behavior",
                    "refactoring-strangler-fig",
                    "reference-architectural-patterns",
                    "requirements-validation-workflow",
                    "reverse-speccing",
                    "review-intent-and-risk-first",
                    "safe-to-fail-experiment",
                    "secure-design-checklist",
                    "secure-regex-catastrophic-backtracking",
                    "stakeholder-alignment",
                    "stopping-conditions",
                    "strategic-domain-classification",
                    "tdd-red-green-refactor",
                    "terminology-extraction-mapping",
                    "test-boundaries-by-responsibility",
                    "test-minimisation",
                    "test-pyramid-progression",
                    "test-readability-clarity-check",
                    "test-to-system-reconstruction",
                    "testing-select-appropriate-level",
                    "traceable-decisions",
                    "usage-examples-sync",
                    "work-package-completion-validation",
                    "zombies-tdd",
                }
            ),
            frozenset(
                {
                    "acceptance-test-first",
                    "adr-drafting-workflow",
                    "adversarial-qa-handoff",
                    "aggregate-boundary-design",
                    "ammerse-impact-analysis",
                    "analysis-extract-before-interpret",
                    "anti-corruption-layer",
                    "architecture-diagram-review-checklist",
                    "atdd-adversarial-acceptance",
                    "atomic-design-review-checklist",
                    "atomic-state-ownership",
                    "autonomous-operation-protocol",
                    "avoid-gold-plating",
                    "bdd-scenario-formulation",
                    "black-box-integration-testing",
                    "bounded-context-canvas-fill",
                    "bounded-context-identification",
                    "c4-zoom-in-architecture-documentation",
                    "chain-of-responsibility-rule-pipeline",
                    "change-apply-smallest-viable-diff",
                    "code-documentation-analysis",
                    "code-review-incremental",
                    "compositional-stream-boundaries",
                    "connascence-analysis",
                    "context-boundary-inference",
                    "context-mapping-classification",
                    "cross-cutting-state-via-store",
                    "decision-marker-capture",
                    "deepening-opportunity-assessment",
                    "dependency-hygiene",
                    "development-bdd",
                    "documentation-curation-audit",
                    "domain-event-capture",
                    "easy-to-change",
                    "eisenhower-prioritisation",
                    "entity-value-object-classification",
                    "five-paradigm-parallel-debugging",
                    "focused-function-complexity-check",
                    "forensic-repository-audit",
                    "formalized-constraint-testing",
                    "function-over-form-testing",
                    "generated-code-stewardship",
                    "glossary-curation-interview",
                    "input-validation-fail-fast",
                    "interface-variation-design",
                    "language-driven-design",
                    "mutation-testing-workflow",
                    "no-parallel-duplicate-test-runs",
                    "occurrence-classification-workflow",
                    "premortem-risk-identification",
                    "problem-decomposition",
                    "quality-gate-verification",
                    "reasons-canvas-fill",
                    "reasons-canvas-review",
                    "refactoring-change-function-declaration",
                    "refactoring-combine-functions-into-transform",
                    "refactoring-conditional-to-strategy",
                    "refactoring-consolidate-conditional-expression",
                    "refactoring-encapsulate-record",
                    "refactoring-encapsulate-variable",
                    "refactoring-extract-class-by-responsibility-split",
                    "refactoring-extract-first-order-concept",
                    "refactoring-guard-clauses-before-polymorphism",
                    "refactoring-inline-temp",
                    "refactoring-introduce-null-object",
                    "refactoring-move-field",
                    "refactoring-move-method",
                    "refactoring-replace-magic-number-with-symbolic-constant",
                    "refactoring-replace-temp-with-query",
                    "refactoring-retry-pattern",
                    "refactoring-state-pattern-for-behavior",
                    "refactoring-strangler-fig",
                    "reference-architectural-patterns",
                    "requirements-validation-workflow",
                    "reverse-speccing",
                    "review-intent-and-risk-first",
                    "safe-to-fail-experiment",
                    "secure-design-checklist",
                    "secure-regex-catastrophic-backtracking",
                    "stakeholder-alignment",
                    "stopping-conditions",
                    "strategic-domain-classification",
                    "supply-chain-install-safety",
                    "tdd-red-green-refactor",
                    "terminology-extraction-mapping",
                    "test-boundaries-by-responsibility",
                    "test-minimisation",
                    "test-pyramid-progression",
                    "test-readability-clarity-check",
                    "test-to-system-reconstruction",
                    "testing-select-appropriate-level",
                    "traceable-decisions",
                    "usage-examples-sync",
                    "work-package-completion-validation",
                    "zombies-tdd",
                }
            ),
            frozenset(
                {
                    "acceptance-test-first",
                    "adr-drafting-workflow",
                    "adversarial-qa-handoff",
                    "aggregate-boundary-design",
                    "ammerse-impact-analysis",
                    "analysis-extract-before-interpret",
                    "anti-corruption-layer",
                    "architecture-diagram-review-checklist",
                    "atdd-adversarial-acceptance",
                    "atomic-design-review-checklist",
                    "atomic-state-ownership",
                    "autonomous-operation-protocol",
                    "avoid-gold-plating",
                    "bdd-scenario-formulation",
                    "black-box-integration-testing",
                    "bounded-context-canvas-fill",
                    "bounded-context-identification",
                    "c4-zoom-in-architecture-documentation",
                    "chain-of-responsibility-rule-pipeline",
                    "change-apply-smallest-viable-diff",
                    "code-documentation-analysis",
                    "code-review-incremental",
                    "compositional-stream-boundaries",
                    "connascence-analysis",
                    "context-boundary-inference",
                    "context-mapping-classification",
                    "cross-cutting-state-via-store",
                    "decision-marker-capture",
                    "deepening-opportunity-assessment",
                    "dependency-hygiene",
                    "development-bdd",
                    "documentation-curation-audit",
                    "domain-event-capture",
                    "easy-to-change",
                    "eisenhower-prioritisation",
                    "entity-value-object-classification",
                    "five-paradigm-parallel-debugging",
                    "focused-function-complexity-check",
                    "forensic-repository-audit",
                    "formalized-constraint-testing",
                    "function-over-form-testing",
                    "generated-code-stewardship",
                    "glossary-curation-interview",
                    "input-validation-fail-fast",
                    "interface-variation-design",
                    "language-driven-design",
                    "mutation-testing-workflow",
                    "no-parallel-duplicate-test-runs",
                    "occurrence-classification-workflow",
                    "premortem-risk-identification",
                    "problem-decomposition",
                    "quality-gate-verification",
                    "reasons-canvas-fill",
                    "reasons-canvas-review",
                    "refactoring-change-function-declaration",
                    "refactoring-combine-functions-into-transform",
                    "refactoring-conditional-to-strategy",
                    "refactoring-consolidate-conditional-expression",
                    "refactoring-encapsulate-record",
                    "refactoring-encapsulate-variable",
                    "refactoring-extract-class-by-responsibility-split",
                    "refactoring-extract-first-order-concept",
                    "refactoring-guard-clauses-before-polymorphism",
                    "refactoring-inline-temp",
                    "refactoring-introduce-null-object",
                    "refactoring-move-field",
                    "refactoring-move-method",
                    "refactoring-replace-magic-number-with-symbolic-constant",
                    "refactoring-replace-temp-with-query",
                    "refactoring-retry-pattern",
                    "refactoring-state-pattern-for-behavior",
                    "refactoring-strangler-fig",
                    "reference-architectural-patterns",
                    "requirements-validation-workflow",
                    "reverse-speccing",
                    "review-intent-and-risk-first",
                    "safe-to-fail-experiment",
                    "secure-design-checklist",
                    "secure-regex-catastrophic-backtracking",
                    "stakeholder-alignment",
                    "stopping-conditions",
                    "strategic-domain-classification",
                    "tdd-red-green-refactor",
                    "terminology-extraction-mapping",
                    "test-boundaries-by-responsibility",
                    "test-minimisation",
                    "test-pyramid-progression",
                    "test-readability-clarity-check",
                    "test-to-system-reconstruction",
                    "testing-select-appropriate-level",
                    "traceable-decisions",
                    "usage-examples-sync",
                    "work-package-completion-validation",
                    "zombies-tdd",
                }
            ),
        ),
        "activated_styleguides": (
            frozenset(
                {
                    "aggregate-design-rules",
                    "deployable-skill-authoring",
                    "java-conventions",
                    "kitty-glossary-writing",
                    "mutation-aware-test-design",
                    "python-conventions",
                    "reasons-canvas-writing",
                    "testing-principles",
                }
            ),
            frozenset(
                {
                    "aggregate-design-rules",
                    "boring-code-review",
                    "deployable-skill-authoring",
                    "java-conventions",
                    "kitty-glossary-writing",
                    "mutation-aware-test-design",
                    "python-conventions",
                    "reasons-canvas-writing",
                    "testing-principles",
                }
            ),
        ),
        "activated_toolguides": (
            frozenset(
                {
                    "contextive",
                    "efficient-local-tooling",
                    "git-agent-commit-signing",
                    "maven-review-checks",
                    "mermaid-diagramming",
                    "plantuml-diagramming",
                    "python-mutation-tools",
                    "python-review-checks",
                    "rtk-search-tooling",
                    "typescript-mutation-tools",
                }
            ),
            frozenset(
                {
                    "contextive",
                    "efficient-local-tooling",
                    "git-agent-commit-signing",
                    "maven-review-checks",
                    "mermaid-diagramming",
                    "plantuml-diagramming",
                    "python-mutation-tools",
                    "python-review-checks",
                    "typescript-mutation-tools",
                }
            ),
            frozenset(
                {
                    "contextive",
                    "efficient-local-tooling",
                    "git-agent-commit-signing",
                    "java-supply-chain",
                    "javascript-supply-chain",
                    "maven-review-checks",
                    "mermaid-diagramming",
                    "plantuml-diagramming",
                    "python-mutation-tools",
                    "python-review-checks",
                    "python-supply-chain",
                    "typescript-mutation-tools",
                }
            ),
        ),
        "activated_paradigms": (
            frozenset(
                {
                    "atomic-design",
                    "behaviour-driven-development",
                    "brownfield-onboarding",
                    "c4-incremental-detail-modeling",
                    "deep-module-design",
                    "domain-driven-design",
                    "specification-by-example",
                    "structured-prompt-driven-development",
                }
            ),
        ),
        "activated_procedures": (
            frozenset(
                {
                    "bdd-scenario-lifecycle",
                    "disciplined-defect-diagnosis",
                    "documentation-gap-prioritization",
                    "domain-aware-decision-interview",
                    "drill-down-documentation",
                    "event-storming-discovery",
                    "example-mapping-workshop",
                    "issue-triage-state-machine",
                    "legacy-codebase-triage",
                    "migrate-project-guidance-to-spec-kitty-charter",
                    "refactoring",
                    "situational-assessment",
                    "test-first-bug-fixing",
                }
            ),
        ),
        "activated_agent_profiles": (
            frozenset(
                {
                    "architect-alphonso",
                    "curator-carla",
                    "debugger-debbie",
                    "designer-dagmar",
                    "frontend-freddy",
                    "generic-agent",
                    "human-in-charge",
                    "implementer-ivan",
                    "java-jenny",
                    "node-norris",
                    "planner-priti",
                    "python-pedro",
                    "researcher-robbie",
                    "retrospective-facilitator",
                    "reviewer-renata",
                }
            ),
            frozenset(
                {
                    "architect-alphonso",
                    "curator-carla",
                    "debugger-debbie",
                    "designer-dagmar",
                    "frontend-freddy",
                    "generic-agent",
                    "human-in-charge",
                    "implementer-ivan",
                    "java-jenny",
                    "node-norris",
                    "paula-patterns",
                    "planner-priti",
                    "python-pedro",
                    "researcher-robbie",
                    "retrospective-facilitator",
                    "reviewer-renata",
                }
            ),
            frozenset(
                {
                    "architect-alphonso",
                    "curator-carla",
                    "debugger-debbie",
                    "designer-dagmar",
                    "doctrine-daphne",
                    "frontend-freddy",
                    "generic-agent",
                    "human-in-charge",
                    "implementer-ivan",
                    "java-jenny",
                    "node-norris",
                    "paula-patterns",
                    "planner-priti",
                    "python-pedro",
                    "randy-reducer",
                    "researcher-robbie",
                    "retrospective-facilitator",
                    "reviewer-renata",
                }
            ),
        ),
        "activated_mission_step_contracts": (
            frozenset(
                {
                    "documentation-accept",
                    "documentation-audit",
                    "documentation-design",
                    "documentation-discover",
                    "documentation-generate",
                    "documentation-publish",
                    "documentation-validate",
                    "implement",
                    "plan",
                    "research-gathering",
                    "research-methodology",
                    "research-output",
                    "research-scoping",
                    "research-synthesis",
                    "review",
                    "specify",
                    "tasks",
                }
            ),
        ),
    }
)

#: The ``activated_kinds`` of every released ``default.yaml``: the core kinds.
#: Derived from the ``ArtifactKind`` authority (no hand-copied kind literal,
#: ``test_charter_kind_vocabulary_single_authority``); the released value is
#: frozen by ``test_charter_pack_cutover_snapshots.py::test_kind_gates``, which
#: fails if the authority ever drifts from it.
DEFAULT_KIND_GATE: frozenset[str] = frozenset(CORE_KIND_PLURALS)

#: The ``activated_kinds`` of every released ``minimal.yaml`` (a defect; DM-01M497F0NAQARAK3JZFVWF1SD0).
MINIMAL_KIND_GATE: frozenset[str] = frozenset(
    {
        "directives",
        "tactics",
    }
)

#: Every distinct released ``minimal`` list per per-artifact key.
MINIMAL_SNAPSHOTS: Mapping[str, tuple[frozenset[str], ...]] = MappingProxyType(
    {
        "activated_directives": (
            frozenset(
                {
                    "001-architectural-integrity-standard",
                    "010-specification-fidelity-requirement",
                    "024-locality-of-change",
                    "028-search-tool-discipline",
                    "030-test-and-typecheck-quality-gate",
                }
            ),
        ),
        "activated_tactics": (
            frozenset(
                {
                    "acceptance-test-first",
                    "boring-code-review",
                }
            ),
            frozenset(
                {
                    "acceptance-test-first",
                }
            ),
        ),
    }
)

#: ``DIRECTIVE_<NNN>`` -> stem for every directive in a snapshot (each built-in's id is its stem's prefix).
DIRECTIVE_ID_TO_STEM: Mapping[str, str] = MappingProxyType(
    {
        "DIRECTIVE_001": "001-architectural-integrity-standard",
        "DIRECTIVE_003": "003-decision-documentation-requirement",
        "DIRECTIVE_010": "010-specification-fidelity-requirement",
        "DIRECTIVE_018": "018-doctrine-versioning-requirement",
        "DIRECTIVE_024": "024-locality-of-change",
        "DIRECTIVE_025": "025-boy-scout-rule",
        "DIRECTIVE_028": "028-search-tool-discipline",
        "DIRECTIVE_029": "029-agent-commit-signing-policy",
        "DIRECTIVE_030": "030-test-and-typecheck-quality-gate",
        "DIRECTIVE_031": "031-context-aware-design",
        "DIRECTIVE_032": "032-conceptual-alignment",
        "DIRECTIVE_033": "033-targeted-staging-policy",
        "DIRECTIVE_034": "034-test-first-development",
        "DIRECTIVE_035": "035-bulk-edit-occurrence-classification",
        "DIRECTIVE_036": "036-black-box-integration-testing",
        "DIRECTIVE_037": "037-living-documentation-sync",
        "DIRECTIVE_038": "038-structured-prompt-boundary",
        "DIRECTIVE_039": "039-lynn-cole-engineering-culture",
        "DIRECTIVE_040": "040-recurring-bug-structural-intervention",
    }
)

_DIRECTIVES_KEY = "activated_directives"
#: An unnumbered directive's UPPER_SNAKE id (``USE_C4_MODEL_TECHNIQUES``).
_UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")
#: A numbered directive id (``DIRECTIVE_041``); one outside the table is left as written.
_NUMBERED_DIRECTIVE = re.compile(r"^DIRECTIVE_\d+$")


def normalise_id(kind_key: str, raw: str) -> str:
    """Return the comparable form of *raw* in the ``activated_<kind>`` list *kind_key*.

    Directives: ``DIRECTIVE_<NNN>`` becomes its numbered stem, and an
    unnumbered UPPER_SNAKE id becomes its kebab stem (a numbered id with no
    snapshot stem is left as written: it matches no snapshot either way).
    Every other kind's ids are file stems already and are returned unchanged.
    """
    if kind_key != _DIRECTIVES_KEY:
        return raw
    stem = DIRECTIVE_ID_TO_STEM.get(raw)
    if stem is not None:
        return stem
    if _UPPER_SNAKE.match(raw) and not _NUMBERED_DIRECTIVE.match(raw):
        return raw.lower().replace("_", "-")
    return raw
