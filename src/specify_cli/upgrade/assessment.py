"""Concrete retained preparations for the upgrade finalizer.

Inventory and write authority remain with the registered owners. This module
coordinates their existing APIs; it does not render assets or simulate writes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from hashlib import sha256  # noqa: TID251 - exact YAML file integrity, not charter semantic hashing.
from pathlib import Path

from charter.activation.compiler import _PreparedMissionTypeActivations, prepare_mission_type_activations

from specify_cli.core.agent_config import load_agent_config
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.skills.command_installer import PreparedCommands, SUPPORTED_AGENTS
from specify_cli.skills.installer import SkillInstallationAssessment, assess_skill_installation
from specify_cli.skills.catalog import resolve_project_skill_catalog
from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.operations import (
    ApplyConsent,
    AssessmentInputs,
    Diagnostic,
    FileState,
    OperationRoot,
    OwnerAssessment,
    OwnerApplyResult,
    OwnershipProof,
    PhysicalEffect,
    coalesce_effects,
)
from specify_cli.tool_surface.plan import SurfacePlanBuilder
from specify_cli.tool_surface.providers.command_skills import CommandSkillsProvider
from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider, SkillCommandComposition
from specify_cli.tool_surface.providers.plugin_bundle import PLUGIN_BUNDLE_TOOL_KEY
from specify_cli.tool_surface.providers.protocol import AssessingSurfaceProvider
from specify_cli.tool_surface.repair import SurfaceRepairService
from specify_cli.tool_surface.service import build_providers, build_registry


@dataclass(frozen=True)
class PreparedUpgradeRepairs:
    """One resolved project's original compiler and whole-owner preparations."""

    root: OperationRoot
    provisioning: _PreparedMissionTypeActivations
    installation: SkillInstallationAssessment
    commands: tuple[OwnerAssessment, ...]
    composition: SkillCommandComposition | None
    remaining: tuple[OwnerAssessment, ...]
    diagnostics: tuple[Diagnostic, ...]
    consent: ApplyConsent

    @property
    def owners(self) -> tuple[OwnerAssessment, ...]:
        """Original owner assessments, including both paired physical roots."""
        return (self.installation.global_assets, self.installation.project_skills, *self.commands, *self.remaining)

    @property
    def complete(self) -> bool:
        """Never interpret an incomplete required owner as an empty plan."""
        return all(owner.complete for owner in self.owners) and not any(d.severity == "error" for d in self.diagnostics)

    @property
    def effects(self) -> tuple[PhysicalEffect, ...]:
        """Consume supplier one-writer composition, not upper-layer deduplication."""
        if self.composition is not None:
            effects = self.composition.effects
        else:
            effects = tuple(effect for owner in (self.installation.global_assets, self.installation.project_skills, *self.commands) for effect in owner.effects)
        return coalesce_effects(effects + self.provisioning_effects + tuple(effect for owner in self.remaining for effect in owner.effects))

    @property
    def provisioning_effects(self) -> tuple[PhysicalEffect, ...]:
        """Adapt charter-owned bytes without reconstructing its YAML policy."""
        write = self.provisioning.write
        if not write.changed:
            return ()
        proof = (OwnershipProof("managed_path", "charter.activation.compiler:mission_type_activations"),)
        effects = tuple(
            PhysicalEffect(
                "provisioning",
                "provisioning",
                self.root,
                parent.relative_to(self.root.path).as_posix(),
                "create",
                FileState("absent"),
                FileState("directory", mode=0o755),
                "Activation target parent",
                proof,
                ("project",),
            )
            for parent in write.absent_parents
        )
        before = FileState("absent") if write.before_bytes is None else FileState("file", sha256=sha256(write.before_bytes).hexdigest(), mode=write.mode)
        return effects + (
            PhysicalEffect(
                "provisioning",
                "provisioning",
                self.root,
                write.target.relative_to(self.root.path).as_posix(),
                "create" if write.before_bytes is None else "update",
                before,
                FileState("file", sha256=write.desired_sha256, mode=write.mode),
                self.provisioning.reason,
                proof,
                ("project",),
            ),
        )


def prepare_upgrade_repairs(project_path: Path, *, consent: ApplyConsent) -> PreparedUpgradeRepairs:
    """Read actual configured inventory and retain each owner's prepared bytes."""
    root = OperationRoot("project", "project", project_path.resolve())
    agents = tuple(load_agent_config(root.path).available)
    slash_command_agents = tuple(agent for agent in agents if agent in AGENT_COMMAND_CONFIG)
    command_skill_agents = tuple(agent for agent in agents if agent in SUPPORTED_AGENTS)
    provisioning = prepare_mission_type_activations(root.path)
    providers = build_providers()
    builder = SurfacePlanBuilder(build_registry((*agents, PLUGIN_BUNDLE_TOOL_KEY)), providers)
    installation = assess_skill_installation(
        AssessmentInputs(root, projected=provisioning, consent=consent),
        resolve_project_skill_catalog(root.path),
        agents,
        runtime=True,
        commands=True,
        command_agent_keys=slash_command_agents,
    )
    managed = builder.assess(agents, AssessmentInputs(root, projected=installation, consent=consent), kinds=(ToolSurfaceKind.DOCTRINE_SKILL,))
    commands = builder.assess(
        command_skill_agents,
        AssessmentInputs(root, projected=provisioning, consent=consent),
        kinds=(ToolSurfaceKind.COMMAND_SKILL,),
    ).assessments
    # Slash-command preparation is already in the paired coordinated global
    # batch. Do not assess a second cold global writer for those definitions.
    remaining_kinds = tuple(
        kind
        for kind in ToolSurfaceKind
        if kind
        not in {
            ToolSurfaceKind.DOCTRINE_SKILL,
            ToolSurfaceKind.COMMAND_SKILL,
            ToolSurfaceKind.COMMAND_FILE,
        }
    )
    remaining = builder.assess(
        (*agents, PLUGIN_BUNDLE_TOOL_KEY),
        AssessmentInputs(root, consent=consent),
        kinds=remaining_kinds,
        configured_tools=agents,
    ).assessments
    owners = (installation.global_assets, installation.project_skills, *managed.assessments, *commands, *remaining)
    diagnostics = tuple(d for owner in owners for d in owner.diagnostics)
    concrete = tuple(owner for owner in commands if isinstance(owner.prepared, PreparedCommands))
    composition = None
    if len(concrete) == 1 and not any(d.severity == "error" for d in diagnostics):
        composition = ManagedSkillsProvider().compose_installation(installation, concrete[0])
    elif len(concrete) > 1:
        diagnostics += (Diagnostic("command_owner_conflict", "command_skills", "error", "Expected one whole-root command preparation"),)
    prepared = PreparedUpgradeRepairs(root, provisioning, installation, commands, composition, remaining, diagnostics, consent)
    # Detect physical conflicts before any finalizer write, not during rendering.
    _ = prepared.effects
    return prepared


@contextmanager
def preflight_upgrade_repairs(prepared: PreparedUpgradeRepairs) -> Iterator[tuple[Diagnostic, ...]]:
    """Hold the concrete paired guard through provisioning and surface apply."""
    if not prepared.complete:
        yield prepared.diagnostics or (Diagnostic("incomplete_assessment", "upgrade", "error", "Required repair assessment is incomplete"),)
        return
    provider = ManagedSkillsProvider()
    with ExitStack() as stack:
        context = (
            provider.preflight_composition(prepared.composition, prepared.consent)
            if prepared.composition is not None
            else provider.preflight_installation(prepared.installation, prepared.consent)
        )
        errors = tuple(stack.enter_context(context))
        for command in prepared.commands:
            errors += CommandSkillsProvider().preflight(command)
        providers = {provider.provider_key: provider for provider in build_providers()}
        for owner in prepared.remaining:
            if not owner.effects:
                continue
            owner_provider = providers.get(owner.owner_key)
            if not isinstance(owner_provider, AssessingSurfaceProvider):
                errors += (Diagnostic("assessment_unsupported", owner.owner_key, "error", "Required owner unavailable at preflight"),)
                continue
            errors += tuple(stack.enter_context(owner_provider.recheck(owner)))
        yield errors


def apply_upgrade_repairs(prepared: PreparedUpgradeRepairs) -> tuple[OwnerApplyResult, ...]:
    """Dispatch retained surface bytes inside the caller's active preflight."""
    service = SurfaceRepairService(build_providers())
    bundles = tuple(owner for owner in prepared.remaining if owner.owner_key == "plugin_bundle")
    results = tuple(service.apply_assessments(bundles, prepared.consent))
    if any(result.outcome not in {"applied", "skipped"} for result in results):
        return results
    provider = ManagedSkillsProvider()
    if prepared.composition is not None:
        paired = provider.apply_composition(prepared.composition, prepared.consent)
    else:
        paired = provider.apply_installation(prepared.installation, prepared.consent)
    results += tuple(paired)
    if any(result.outcome not in {"applied", "skipped"} for result in paired):
        return results
    others = tuple(owner for owner in prepared.remaining if owner.owner_key != "plugin_bundle")
    return results + tuple(service.apply_assessments(others, prepared.consent))
