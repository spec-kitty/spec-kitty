"""Calibration walker: enumerate (profile, action) pairs for a mission.

For each step in the mission, the walker:
  1. Resolves ResolvedScope via the DRG resolver (with any project overlays applied).
  2. Looks up RequiredScope from the curated REQUIRED_SCOPE_MAP.
  3. Runs assert_inequality_holds with ``known_irrelevant`` = resolved - required
     (transitive extras surfaced by requires/suggests edges are tolerated).
  4. Emits a CalibrationFinding for every step.

Required-scope map (inline):
    Keys are ``(mission_key, action_urn)`` pairs.
    Values are frozenset[str] of the *directly scoped* artifact URNs (i.e. the
    direct ``scope`` edges from the action node in the built-in graph).  The
    resolver produces a strictly larger set via transitive ``requires`` /
    ``suggests`` traversal; those extras are tolerated as ``known_irrelevant``.

Overlay loading:
    The walker loads ``.kittify/charter-packs/overlays/calibration-<mission>.yaml``
    (if present) alongside the built-in ``packs/built-in/*.graph.yaml``
    fragments.  Overlay
    ``add_edge`` and ``remove_edge`` mutations are applied before resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from charter.drg import (
    DRGEdge,
    DRGGraph,
    DRGNode,
    NodeKind,
    Relation,
    load_built_in_graph,
    merge_layers,
    resolve_context,
)
from kernel.charter_pack_paths import resolve_project_pack_read_root
from specify_cli.calibration.inequality import InequalityResult, assert_inequality_holds


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

ACTION_RESEARCH_GATHERING = "action:research/gathering"
DIRECTIVE_003 = "directive:DIRECTIVE_003"
DIRECTIVE_010 = "directive:DIRECTIVE_010"
DIRECTIVE_037 = "directive:DIRECTIVE_037"
TACTIC_ADR_DRAFTING_WORKFLOW = "tactic:adr-drafting-workflow"
TACTIC_PREMORTEM_RISK_IDENTIFICATION = "tactic:premortem-risk-identification"
TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW = "tactic:requirements-validation-workflow"
AGENT_PROFILE_PLANNER_PRITI = "agent_profile:planner-priti"
AGENT_PROFILE_IMPLEMENTER_IVAN = "agent_profile:implementer-ivan"
AGENT_PROFILE_RETROSPECTIVE_FACILITATOR = "agent_profile:retrospective-facilitator"


@dataclass(frozen=True)
class EdgeChange:
    """A recommended DRG edge change."""

    kind: str  # "add_edge" | "remove_edge" | "rewire_edge"
    source: str
    target: str
    relation: str
    new_target: str | None = None  # for rewire_edge only


@dataclass
class CalibrationFinding:
    """Calibration result for a single (step, action, profile) triple.

    Attributes:
        step_id: Step identifier within the mission.
        action_id: Action URN (e.g. ``"action:software-dev/implement"``).
        profile_id: Agent-profile URN (e.g. ``"agent_profile:implementer-ivan"``).
        resolved_scope: URNs surfaced by the DRG resolver.
        required_scope: URNs the step needs (from curated map).
        known_irrelevant: URNs explicitly tolerated as irrelevant (benign extras).
        inequality: Result of assert_inequality_holds.
        recommended_edge_changes: Structured edge mutations to fix any violations.
    """

    step_id: str
    action_id: str
    profile_id: str
    resolved_scope: frozenset[str]
    required_scope: frozenset[str]
    known_irrelevant: frozenset[str]
    inequality: InequalityResult
    recommended_edge_changes: list[EdgeChange] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Curated required-scope map
#
# Keys: (mission_key, action_urn)
# Values: frozenset of URNs that the step *directly requires*
#         (matches the direct ``scope`` edges in the built-in graph, plus any
#          URNs the step semantically needs that may be missing from those edges).
#
# Rationale: determined by inspection of each action's semantic intent per R-005.
# The resolver produces a superset (via transitive traversal); extras are
# classified as known_irrelevant so the inequality holds without edge removal.
# ---------------------------------------------------------------------------

_REQUIRED_SCOPE: dict[tuple[str, str], frozenset[str]] = {
    # ------------------------------------------------------------------
    # software-dev
    # ------------------------------------------------------------------
    ("software-dev", "action:software-dev/specify"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("software-dev", "action:software-dev/plan"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_ADR_DRAFTING_WORKFLOW,
        TACTIC_PREMORTEM_RISK_IDENTIFICATION,
        "tactic:problem-decomposition",
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("software-dev", "action:software-dev/tasks"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        "directive:DIRECTIVE_024",
        TACTIC_ADR_DRAFTING_WORKFLOW,
        "tactic:problem-decomposition",
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("software-dev", "action:software-dev/implement"): frozenset({
        "directive:DIRECTIVE_024",
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_028",
        "directive:DIRECTIVE_029",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "tactic:acceptance-test-first",
        "tactic:autonomous-operation-protocol",
        "tactic:change-apply-smallest-viable-diff",
        "tactic:quality-gate-verification",
        "tactic:stopping-conditions",
        "tactic:tdd-red-green-refactor",
        "toolguide:efficient-local-tooling",
    }),
    ("software-dev", "action:software-dev/review"): frozenset({
        "directive:DIRECTIVE_003",
        "directive:DIRECTIVE_010",
        "directive:DIRECTIVE_024",
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_028",
        "directive:DIRECTIVE_029",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "directive:DIRECTIVE_037",
        "tactic:acceptance-test-first",
        "tactic:usage-examples-sync",
        "tactic:quality-gate-verification",
        "tactic:review-intent-and-risk-first",
        "tactic:stopping-conditions",
    }),
    ("software-dev", "action:software-dev/retrospect"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
    }),

    # ------------------------------------------------------------------
    # research
    # ------------------------------------------------------------------
    ("research", "action:research/scoping"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
        TACTIC_PREMORTEM_RISK_IDENTIFICATION,
    }),
    ("research", "action:research/methodology"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_ADR_DRAFTING_WORKFLOW,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("research", ACTION_RESEARCH_GATHERING): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("research", "action:research/synthesis"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_PREMORTEM_RISK_IDENTIFICATION,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("research", "action:research/output"): frozenset({
        DIRECTIVE_010,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("research", "action:research/retrospect"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
    }),

    # ------------------------------------------------------------------
    # documentation
    # ------------------------------------------------------------------
    ("documentation", "action:documentation/audit"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/design"): frozenset({
        "directive:DIRECTIVE_001",
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_ADR_DRAFTING_WORKFLOW,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/discover"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_PREMORTEM_RISK_IDENTIFICATION,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/generate"): frozenset({
        DIRECTIVE_010,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/publish"): frozenset({
        DIRECTIVE_010,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/validate"): frozenset({
        DIRECTIVE_010,
        DIRECTIVE_037,
        TACTIC_PREMORTEM_RISK_IDENTIFICATION,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("documentation", "action:documentation/retrospect"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
    }),

    # ------------------------------------------------------------------
    # erp-custom (maps ERP step roles to generic action URNs)
    # query-erp / lookup-provider / write-report → research/gathering
    # create-js / refactor-function              → software-dev/implement
    # ask-user                                   → software-dev/specify
    # retrospective                              → software-dev/retrospect
    # ------------------------------------------------------------------
    ("erp-custom", ACTION_RESEARCH_GATHERING): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_037,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("erp-custom", "action:software-dev/implement"): frozenset({
        "directive:DIRECTIVE_024",
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_028",
        "directive:DIRECTIVE_029",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "tactic:acceptance-test-first",
        "tactic:autonomous-operation-protocol",
        "tactic:change-apply-smallest-viable-diff",
        "tactic:quality-gate-verification",
        "tactic:stopping-conditions",
        "tactic:tdd-red-green-refactor",
        "toolguide:efficient-local-tooling",
    }),
    ("erp-custom", "action:software-dev/specify"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
        TACTIC_REQUIREMENTS_VALIDATION_WORKFLOW,
    }),
    ("erp-custom", "action:software-dev/retrospect"): frozenset({
        DIRECTIVE_003,
        DIRECTIVE_010,
    }),
}

# ---------------------------------------------------------------------------
# Mission step definitions
# ---------------------------------------------------------------------------

# Maps mission_key → list of (step_id, action_urn, profile_urn)
_MISSION_STEPS: dict[str, list[tuple[str, str, str]]] = {
    "software-dev": [
        ("specify",    "action:software-dev/specify",    AGENT_PROFILE_PLANNER_PRITI),
        ("plan",       "action:software-dev/plan",       AGENT_PROFILE_PLANNER_PRITI),
        ("tasks",      "action:software-dev/tasks",      AGENT_PROFILE_PLANNER_PRITI),
        ("implement",  "action:software-dev/implement",  AGENT_PROFILE_IMPLEMENTER_IVAN),
        ("review",     "action:software-dev/review",     "agent_profile:reviewer-renata"),
        ("retrospect", "action:software-dev/retrospect", AGENT_PROFILE_RETROSPECTIVE_FACILITATOR),
    ],
    "research": [
        ("scoping",     "action:research/scoping",     "agent_profile:researcher-robbie"),
        ("methodology", "action:research/methodology", "agent_profile:researcher-robbie"),
        ("gathering",   ACTION_RESEARCH_GATHERING,     "agent_profile:researcher-robbie"),
        ("synthesis",   "action:research/synthesis",   "agent_profile:researcher-robbie"),
        ("output",      "action:research/output",      "agent_profile:researcher-robbie"),
        ("retrospect",  "action:research/retrospect",  AGENT_PROFILE_RETROSPECTIVE_FACILITATOR),
    ],
    "documentation": [
        ("audit",       "action:documentation/audit",    "agent_profile:curator-carla"),
        ("design",      "action:documentation/design",   "agent_profile:curator-carla"),
        ("discover",    "action:documentation/discover", "agent_profile:curator-carla"),
        ("generate",    "action:documentation/generate", "agent_profile:curator-carla"),
        ("publish",     "action:documentation/publish",  "agent_profile:curator-carla"),
        ("validate",    "action:documentation/validate", "agent_profile:curator-carla"),
        ("retrospect",  "action:documentation/retrospect", AGENT_PROFILE_RETROSPECTIVE_FACILITATOR),
    ],
    "erp-custom": [
        ("query-erp",         ACTION_RESEARCH_GATHERING,         "agent_profile:researcher-robbie"),
        ("lookup-provider",   ACTION_RESEARCH_GATHERING,         "agent_profile:researcher-robbie"),
        ("ask-user",          "action:software-dev/specify",     AGENT_PROFILE_IMPLEMENTER_IVAN),
        ("create-js",         "action:software-dev/implement",   AGENT_PROFILE_IMPLEMENTER_IVAN),
        ("refactor-function", "action:software-dev/implement",   AGENT_PROFILE_IMPLEMENTER_IVAN),
        ("write-report",      ACTION_RESEARCH_GATHERING,         "agent_profile:researcher-robbie"),
        ("retrospective",     "action:software-dev/retrospect",  AGENT_PROFILE_RETROSPECTIVE_FACILITATOR),
    ],
}


# ---------------------------------------------------------------------------
# Overlay loading
# ---------------------------------------------------------------------------


def _calibration_overlay_path(repo_root: Path, mission_key: str) -> Path:
    """Return the project calibration overlay path for *mission_key* (project pack root)."""
    return resolve_project_pack_read_root(repo_root, quiet=True) / "overlays" / f"calibration-{mission_key}.yaml"


def _load_overlay_graph(
    repo_root: Path,
    mission_key: str,
) -> DRGGraph | None:
    """Load the project-local calibration overlay for *mission_key*, if present.

    The overlay YAML may contain:
      - ``nodes``: list of extra node definitions (added to the graph)
      - ``add_edge``: list of edges to add

    Returns None when the overlay file does not exist or is empty.
    """
    overlay_path = _calibration_overlay_path(repo_root, mission_key)
    if not overlay_path.exists():
        return None

    yaml = YAML(typ="safe")
    raw = yaml.load(overlay_path.read_text(encoding="utf-8"))
    if not raw:
        return None

    nodes: list[DRGNode] = []
    edges: list[DRGEdge] = []

    for node_data in raw.get("nodes", []):
        nodes.append(
            DRGNode(
                urn=node_data["urn"],
                kind=NodeKind(node_data["kind"]),
                label=node_data.get("label"),
            )
        )

    for edge_data in raw.get("add_edge", []):
        edges.append(
            DRGEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                relation=Relation(edge_data["relation"]),
                reason=edge_data.get("reason"),
            )
        )

    if not nodes and not edges:
        return None

    return DRGGraph(
        schema_version="1.0",
        generated_at="OVERLAY",
        generated_by="calibration-overlay",
        nodes=nodes,
        edges=edges,
    )


def _apply_remove_edges(graph: DRGGraph, repo_root: Path, mission_key: str) -> DRGGraph:
    """Remove edges listed in the overlay's ``remove_edge`` section."""
    overlay_path = _calibration_overlay_path(repo_root, mission_key)
    if not overlay_path.exists():
        return graph

    yaml = YAML(typ="safe")
    raw = yaml.load(overlay_path.read_text(encoding="utf-8"))
    if not raw:
        return graph

    removes: list[tuple[str, str, str]] = [
        (e["source"], e["target"], e["relation"])
        for e in raw.get("remove_edge", [])
    ]
    if not removes:
        return graph

    remove_set = set(removes)
    kept_edges = [
        e for e in graph.edges
        if (e.source, e.target, e.relation.value) not in remove_set
    ]
    return DRGGraph(
        schema_version=graph.schema_version,
        generated_at=graph.generated_at,
        generated_by=graph.generated_by,
        nodes=graph.nodes,
        edges=kept_edges,
    )


# ---------------------------------------------------------------------------
# Walker public API
# ---------------------------------------------------------------------------


def _build_graph(repo_root: Path, mission_key: str) -> DRGGraph:
    """Load built-in graph, apply overlay (add + remove), return merged graph.

    The built-in graph is read through the canonical :func:`load_built_in_graph`
    seam (WP03, mission #2680) rather than a bespoke ``repo_root``-relative path,
    so it follows the monolith->fragment migration (WP05) transparently. Overlays
    remain ``repo_root``-relative (project-local calibration input).
    """
    built_in = load_built_in_graph()
    overlay = _load_overlay_graph(repo_root, mission_key)
    merged = merge_layers(built_in, overlay)
    merged = _apply_remove_edges(merged, repo_root, mission_key)
    return merged


def _recommend_changes(
    action_urn: str,
    missing_urns: frozenset[str],
) -> list[EdgeChange]:
    """Derive minimal add_edge changes for any missing URNs.

    Over-broad URNs are not recommended for removal here because they are
    typically benign transitive extras (from requires/suggests traversal).
    Removal recommendations go in the overlay YAML directly if needed.
    """
    changes: list[EdgeChange] = []
    for urn in sorted(missing_urns):
        changes.append(
            EdgeChange(
                kind="add_edge",
                source=action_urn,
                target=urn,
                relation="scope",
            )
        )
    return changes


def walk_mission(
    *,
    mission_key: str,
    repo_root: Path,
) -> list[CalibrationFinding]:
    """Walk every (profile, action) pair in *mission_key* and calibrate.

    ``known_irrelevant`` is computed as the difference between ``resolved_scope``
    and ``required_scope``.  This means transitive URNs surfaced by
    ``requires``/``suggests`` traversal are tolerated rather than flagged as
    over-broad, which is the correct semantics for a resolver that produces a
    superset of directly-scoped artifacts.

    Args:
        mission_key: One of ``"software-dev"``, ``"research"``,
            ``"documentation"``, or ``"erp-custom"``.
        repo_root: Repository root containing the ``packs/built-in/*.graph.yaml``
            fragments and (optionally) ``.kittify/charter-packs/overlays/``.

    Returns:
        One :class:`CalibrationFinding` per step in the mission.

    Raises:
        KeyError: If *mission_key* is not in the built-in step registry.
        ``charter.offering.drg.DRGLoadError``: If the built-in graph cannot be loaded.
    """
    steps = _MISSION_STEPS[mission_key]
    graph = _build_graph(repo_root, mission_key)

    findings: list[CalibrationFinding] = []
    for step_id, action_urn, profile_urn in steps:
        ctx = resolve_context(graph, action_urn)
        resolved_scope = ctx.artifact_urns

        required_scope = _REQUIRED_SCOPE.get(
            (mission_key, action_urn),
            frozenset(),
        )

        # Transitive extras from requires/suggests are benign; classify as
        # known_irrelevant so the over-broad half of the inequality passes.
        known_irrelevant = resolved_scope - required_scope

        result = assert_inequality_holds(
            resolved_scope=resolved_scope,
            required_scope=required_scope,
            known_irrelevant=known_irrelevant,
        )

        changes = _recommend_changes(action_urn, result.missing_urns)

        findings.append(
            CalibrationFinding(
                step_id=step_id,
                action_id=action_urn,
                profile_id=profile_urn,
                resolved_scope=resolved_scope,
                required_scope=required_scope,
                known_irrelevant=known_irrelevant,
                inequality=result,
                recommended_edge_changes=changes,
            )
        )

    return findings
