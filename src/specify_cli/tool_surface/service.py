"""High-level assembly for the ``doctor tool-surfaces`` command path.

This module wires the registry, providers, plan builder, status service, and
repair service together so the CLI layer stays thin (C-001: no business logic in
``doctor.py``). The CLI calls :func:`run_tool_surfaces` with parsed flags and
renders the returned :class:`SurfaceReport` / :class:`RepairResult`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .docs import DocsLinter, DocsLintFinding
from .enums import ToolSurfaceKind
from .findings import (
    GLOBAL_SKILL_KEPT_STALE,
    RETIRED_SKILL_KEPT_EDITED,
    SEVERITY_WARNING,
    SurfaceFinding,
    make_finding,
)
from .model import SurfacePlan
from .operations import AssessmentInputs, OwnerAssessment
from .plan import SurfacePlanBuilder
from .providers._discovery import _PROVIDERS  # noqa: F401 — imported for side-effects (registration)
from .providers._registry import SurfaceProviderRegistry
from .providers.plugin_bundle import PLUGIN_BUNDLE_TOOL_KEY
from .providers.protocol import ReportingSurfaceProvider
from .registry import ToolSurfaceRegistry
from .repair import RepairResult, SurfaceRepairService, explain_skipped
from .status import SurfaceReport, SurfaceStatusService

# Operator-facing ``--kind`` tokens are kebab-case; map them to ToolSurfaceKind.
# Session-presence kinds also accept the underscore wire value so operators can
# pass ``--kind context_file`` (matching the JSON ``surface_kind``) directly.
# Built from registered provider kind_tokens dicts; populated after _discovery
# fires all module-level SurfaceProviderRegistry.register() calls (WP04+).
_KIND_TOKENS: dict[str, ToolSurfaceKind] = SurfaceProviderRegistry.build_kind_tokens()

# Representative tool keys whose surfaces feed bundle projection: skills-invocable
# agents supply command + doctrine skills, ``claude`` supplies native agent
# profiles, and ``vibe`` supplies native config / hooks. Used only to build the
# projection plans during ``--fix`` repair of plugin bundles.
_BUNDLE_SOURCE_TOOL_KEYS: tuple[str, ...] = (
    "codex",
    "claude",
    "copilot",
    "vibe",
)


# Synthetic tool key used to register every built-in path pattern into a single
# registry for docs-contract linting (FR-017). The docs linter validates path
# *shapes* against the contract, independent of which tools are configured.
_DOCS_INDEX_TOOL_KEY = "__docs_contract__"


class UnknownSurfaceKind(ValueError):
    """Raised when an operator passes an unrecognized ``--kind`` token."""


def surface_kind_from_token(token: str) -> ToolSurfaceKind:
    """Map a kebab-case ``--kind`` token to a :class:`ToolSurfaceKind`."""
    try:
        return _KIND_TOKENS[token]
    except KeyError as exc:
        known = ", ".join(sorted(_KIND_TOKENS))
        raise UnknownSurfaceKind(f"Unknown surface kind '{token}'. Known kinds: {known}.") from exc


@dataclass(frozen=True)
class ToolSurfaceOutcome:
    """Bundle of the probe report and (optional) repair result."""

    report: SurfaceReport
    repair: RepairResult | None = None
    assessments: tuple[OwnerAssessment, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = self.report.to_json()
        if self.repair is not None:
            payload["repair"] = self.repair.to_json()
        return payload


def build_providers() -> list[ReportingSurfaceProvider]:
    """Return all providers available at this work package."""
    providers: list[ReportingSurfaceProvider] = SurfaceProviderRegistry.build_providers()
    return providers


def build_registry(tool_keys: Sequence[str]) -> ToolSurfaceRegistry:
    """Register the built-in definitions for each configured tool key."""
    return SurfaceProviderRegistry.build_registry(tool_keys)


def build_plans_for_bundles(project_root: Path, *, tool_keys: Sequence[str] | None = None) -> list[SurfacePlan]:
    """Build the canonical surface plans consumed by plugin bundle projection.

    Uses the existing registry and builder without additional kind filtering.

    Omitted or None tool keys use the representative bundle sources. Explicit
    keys, including an empty sequence, retain the builder's order and duplicates.
    """
    tools = _BUNDLE_SOURCE_TOOL_KEYS if tool_keys is None else tuple(tool_keys)
    providers = build_providers()
    registry = build_registry(tools)
    builder = SurfacePlanBuilder(registry, providers)
    return builder.build(tools, project_root)


def build_docs_linter() -> DocsLinter:
    """Build a :class:`DocsLinter` backed by every built-in path pattern.

    The linter validates documented path *shapes* against the contract and is
    independent of which tools are configured, so all definitions are registered
    under a single synthetic key (:data:`_DOCS_INDEX_TOOL_KEY`).
    """
    return DocsLinter(build_registry((_DOCS_INDEX_TOOL_KEY,)))


def lint_docs_directory(docs_dir: Path, patterns: list[str] | None = None) -> list[DocsLintFinding]:
    """Lint a docs directory against the tool surface contract (FR-017)."""
    findings: list[DocsLintFinding] = build_docs_linter().lint_directory(docs_dir, patterns)
    return findings


def run_tool_surfaces(
    project_root: Path,
    configured_tools: Sequence[str],
    *,
    tool_filter: str | None = None,
    kinds: Sequence[ToolSurfaceKind] | None = None,
    fix: bool = False,
    assessment_inputs: AssessmentInputs | None = None,
) -> ToolSurfaceOutcome:
    """Build/collect once, optionally repair or prepare immutable owner assessments.

    ``assessment_inputs`` opts into preparation without changing legacy report
    JSON or requiring old reporting/repair consumers to support the new protocol.
    It cannot be combined with ``fix``: apply uses the separate checked boundary.
    """
    if assessment_inputs is not None and (fix or assessment_inputs.root.path != project_root):
        raise ValueError("Assessment requires the selected root and cannot be combined with fix")
    tools = _selected_tools(configured_tools, tool_filter)
    providers = build_providers()
    registry = build_registry(tools)
    builder = SurfacePlanBuilder(registry, providers)
    kind_set = set(kinds) if kinds else None
    # The plugin-manifest surface is registered under a synthetic key (it is not
    # owned by any single configured tool). Add that key to the *plan* tool list
    # so the bundle manifests are probed, but never to ``configured_tools`` so
    # the operator-facing tool roster stays accurate. Skip it when a ``--tool``
    # filter is active (the operator asked for one specific tool) or when no
    # tools are configured (a bundle has nothing to aggregate).
    plan_tools = [*tools, PLUGIN_BUNDLE_TOOL_KEY] if tools and tool_filter is None else list(tools)
    if assessment_inputs is not None:
        assessed = builder.assess(plan_tools, assessment_inputs, kinds=kinds, configured_tools=tools)
        return ToolSurfaceOutcome(report=assessed.report, assessments=assessed.assessments)
    plans = builder.build(plan_tools, project_root)
    if kind_set is not None:
        plans = _filter_plans_by_kinds(plans, kind_set)
    report = SurfaceStatusService(providers).collect(project_root, plans, configured_tools=tools)
    if not fix:
        return ToolSurfaceOutcome(report=_with_global_skill_findings(report, kind_set, tool_filter))
    repair = SurfaceRepairService(providers).repair(project_root, report.surfaces, kinds=kind_set)
    plans = builder.build(plan_tools, project_root)
    if kind_set is not None:
        plans = _filter_plans_by_kinds(plans, kind_set)
    refreshed = SurfaceStatusService(providers).collect(project_root, plans, configured_tools=tools)
    return ToolSurfaceOutcome(
        report=_with_global_skill_findings(refreshed, kind_set, tool_filter),
        repair=explain_skipped(repair, refreshed.surfaces),
    )


def _with_global_skill_findings(report: SurfaceReport, kind_set: set[ToolSurfaceKind] | None, tool_filter: str | None) -> SurfaceReport:
    """Append the kept user-global skill files as warnings; they never flip ``ok`` (#5983)."""
    if kind_set is not None and ToolSurfaceKind.CHARTER_SKILL not in kind_set:
        return report
    findings = _global_skill_findings(tool_filter)
    if not findings:
        return report
    summary = replace(report.summary, warnings=report.summary.warnings + len(findings))
    return replace(report, summary=summary, findings=report.findings + findings)


_GLOBAL_KEPT_REMEDY = {
    GLOBAL_SKILL_KEPT_STALE: "Review it; to take today's version, delete it and run any spec-kitty command.",
    RETIRED_SKILL_KEPT_EDITED: "Review it and delete it when you no longer need it.",
}


def _global_skill_findings(tool_filter: str | None) -> tuple[SurfaceFinding, ...]:
    """One finding per global skill file the sync keeps, read from the assessment only (no writes).

    Uses :func:`kept_global_skill_files`, the rule the startup sync, ``upgrade`` and
    ``doctor --fix`` share. ``tool_key`` names the agent whose global root holds the
    file, or is ``None`` when several agents share that root.
    """
    from specify_cli.runtime.agent_skills import assess_global_agent_skills, kept_global_skill_files
    from specify_cli.skills.paths import get_primary_global_skill_root, iter_installable_agents

    roots = {agent: root for agent in iter_installable_agents() if (root := get_primary_global_skill_root(agent)) is not None}
    findings = []
    for item in kept_global_skill_files(assess_global_agent_skills()):
        owners = [agent for agent, root in roots.items() if root in item.path.parents]
        if tool_filter is not None and tool_filter not in owners:
            continue
        findings.append(_kept_finding(item.path, item.kind, item.reason, owners, roots))
    return tuple(findings)


def _kept_finding(path: Path, kind: str, reason: str, owners: Sequence[str], roots: dict[str, Path]) -> SurfaceFinding:
    skill = path.relative_to(roots[owners[0]]).parts[0] if owners else path.parent.name
    if kind == "stale_canonical":
        code = GLOBAL_SKILL_KEPT_STALE
        what = f"a file of the shipped skill '{skill}' whose bytes Spec Kitty cannot prove it wrote"
    else:
        code = RETIRED_SKILL_KEPT_EDITED
        what = f"an edited copy of the retired skill '{skill}'"
    remedy = _GLOBAL_KEPT_REMEDY[code]
    return make_finding(
        code,
        SEVERITY_WARNING,
        f"Kept {path}: {what} ({reason}). {remedy}",
        tool_key=owners[0] if len(owners) == 1 else None,
        path=path,
        repair_command=remedy,
        details={"skill": skill, "kept": kind, "reason": reason},
    )


def _selected_tools(configured_tools: Sequence[str], tool_filter: str | None) -> list[str]:
    if tool_filter is None:
        return list(configured_tools)
    return [t for t in configured_tools if t == tool_filter]


def _filter_plans_by_kinds(plans: Sequence[SurfacePlan], kind_set: set[ToolSurfaceKind]) -> list[SurfacePlan]:
    filtered: list[SurfacePlan] = []
    for plan in plans:
        instances = tuple(inst for inst in plan.instances if inst.definition.kind in kind_set)
        filtered.append(
            SurfacePlan(
                tool_key=plan.tool_key,
                instances=instances,
                computed_at=plan.computed_at,
                definitions=tuple(d for d in plan.definitions if d.kind in kind_set),
                diagnostics=plan.diagnostics,
            )
        )
    return filtered
