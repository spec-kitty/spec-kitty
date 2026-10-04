"""Plugin bundle surface provider.

Wires the plugin bundle projectors (Claude Code, Copilot CLI, VS Code) into a
reporting-layer provider for :data:`ToolSurfaceKind.PLUGIN_MANIFEST`. The provider
*delegates* all projection to the projectors and only translates their results
into surface-contract types -- it never reimplements bundle layout logic.

**Scope guard (FR-016, C-006):** this provider projects bundles into a staging
``output_dir`` and validates them. It performs no auto-install, no plugin
registration, and no marketplace publication. The ``repair`` path re-projects
staging files only; it does not enable or ship anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, runtime_checkable
from specify_cli.core.agent_config import AgentConfigError

from ..bundles.claude import ClaudeCodeBundleProjector
from ..bundles.copilot import CopilotBundleProjector
from ..bundles.model import BundleEntry, BundleSources, BundleValidationResult, PluginBundle, StagedFile
from ..bundles.projection import (
    BUNDLE_SURFACE_KINDS, apply_staging, files_for_entries, json_bytes,
    observe_confined, plugin_manifest_payload, prepare_staging, staging_guard,
    supplied_entries,
)
from ..bundles.vscode import VsCodeBundleProjector
from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    BUNDLE_COMPONENT_MISSING,
    PLUGIN_MANIFEST_STALE_PATH,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SurfaceFinding,
    make_finding,
)
from ..model import SurfaceDefinition, SurfaceInstance, SurfacePlan, SurfaceSelection
from ..operations import (
    ApplyConsent, AssessmentInputs, Diagnostic, Disposition, OperationRoot,
    OwnerApplyResult, OwnerAssessment,
)
from ..repair import RepairResult
from ..status import (
    STATE_MISSING,
    STATE_PRESENT,
    STATE_STALE,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "plugin_bundle"
# Synthetic registry key under which the (tool-agnostic) plugin-manifest surface
# is registered. Plugin bundles aggregate surfaces across all tools, so the
# manifest is not a per-tool surface; ``expand`` only fires for this key.
PLUGIN_BUNDLE_TOOL_KEY = "plugin_bundle"
# Staging output root for projected bundles. Per the WP09 task spec this must be
# a release/staging artifact and never live under ``.kittify/`` or any
# project-managed directory.
_OUTPUT_SUBDIR = "dist/spec-kitty-plugins"
# Definition-level path pattern (root manifest) used only for the registry's
# ``SurfaceDefinition``; the *probed* per-target manifest path is computed from
# each projector's ``manifest_relative_path`` so the Claude Code
# ``.claude-plugin/`` layout is honoured.
_PATH_PATTERN = "dist/spec-kitty-plugins/{target}/plugin.json"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind plugin-manifest --fix"


@runtime_checkable
class BundleProjector(Protocol):
    """Structural type for the bundle projectors this provider drives."""

    distribution_target: str
    manifest_relative_path: str

    def entries(self, plan: Sequence[SurfacePlan], project_root: Path) -> tuple[BundleEntry, ...]: ...

    def project(
        self,
        plan: Sequence[SurfacePlan],
        project_root: Path,
        output_dir: Path,
    ) -> PluginBundle: ...

    def validate(
        self,
        bundle: PluginBundle,
        required_surface_kinds: set[ToolSurfaceKind] | None = None,
    ) -> BundleValidationResult: ...


def plugin_manifest_definition() -> SurfaceDefinition:
    """Return the built-in plugin-manifest :class:`SurfaceDefinition`."""
    return SurfaceDefinition(
        kind=ToolSurfaceKind.PLUGIN_MANIFEST,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PLUGIN_BUNDLE,
        path_pattern=_PATH_PATTERN,
        required_policy=RequiredPolicy.OPTIONAL,
        activation_mode=ActivationMode.DISABLED,
        provider_key=PROVIDER_KEY,
        repair_hint=_REPAIR_HINT,
    )


def default_projectors() -> list[BundleProjector]:
    """Return the standard set of staging-only bundle projectors."""
    return [
        ClaudeCodeBundleProjector(),
        CopilotBundleProjector(),
        VsCodeBundleProjector(),
    ]


class PluginBundleProvider:
    """Provider for plugin-manifest (plugin bundle) surfaces."""

    provider_key = PROVIDER_KEY

    def __init__(
        self,
        projectors: Sequence[BundleProjector] | None = None,
        output_subdir: str = _OUTPUT_SUBDIR,
    ) -> None:
        self._projectors = list(projectors) if projectors is not None else (
            default_projectors()
        )
        self._output_subdir = output_subdir

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == ToolSurfaceKind.PLUGIN_MANIFEST)

    def _output_dir(self, project_root: Path, target: str) -> Path:
        return project_root / self._output_subdir / target

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into one manifest instance per distribution target.

        Bundles aggregate across all tools, so this only fires for the synthetic
        :data:`PLUGIN_BUNDLE_TOOL_KEY`; any other ``tool_key`` yields nothing,
        preventing a duplicate manifest per configured tool.
        """
        if tool_key != PLUGIN_BUNDLE_TOOL_KEY:
            return []
        instances: list[SurfaceInstance] = []
        for projector in self._projectors:
            manifest_path = (
                self._output_dir(project_root, projector.distribution_target)
                / projector.manifest_relative_path
            )
            instances.append(
                SurfaceInstance(
                    definition=definition,
                    path=manifest_path,
                    exists=manifest_path.exists(),
                    file_hash=None,
                    owner=projector.distribution_target,
                )
            )
        return instances

    def _projector_for(self, target: str) -> BundleProjector | None:
        for projector in self._projectors:
            if projector.distribution_target == target:
                return projector
        return None

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Probe the staged bundle manifest and its required components."""
        target = instance.owner
        projector = self._projector_for(target)
        if projector is None:
            return self._stale_status(instance)
        if not instance.path.exists():
            return SurfaceStatus(instance=instance, state=STATE_MISSING)
        output = self._staged_output_dir(instance.path)
        root = output.parent
        for _part in Path(self._output_subdir).parts:
            root = root.parent
        assessment = self.assess(
            AssessmentInputs(OperationRoot("project", "project", root),
                             projected=BundleSources(selected_targets=(target,))),
            (), selections=(),
        )
        if assessment.complete and not assessment.effects and all(d.state == "unchanged" for d in assessment.dispositions):
            return SurfaceStatus(instance=instance, state=STATE_PRESENT)
        finding = make_finding(BUNDLE_COMPONENT_MISSING, SEVERITY_ERROR,
                               "Selected staged bundle has missing, drifted, or unavailable members.",
                               path=instance.path)
        return self._incomplete_status(instance, (finding,))

    def assess(
        self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *,
        selections: tuple[SurfaceSelection, ...],
    ) -> OwnerAssessment:
        """Prepare explicitly selected staging, never enable an advisory bundle."""
        _ = statuses
        sources = inputs.projected if isinstance(inputs.projected, BundleSources) else BundleSources()
        selected = sources.selected_targets
        if not selected and any(self.can_handle(s.definition) and s.definition.activation_mode != ActivationMode.DISABLED for s in selections):
            selected = tuple(p.distribution_target for p in self._projectors)
        if not selected:
            return OwnerAssessment(PROVIDER_KEY, inputs.root, consent=inputs.consent,
                                   dispositions=(Disposition(PROVIDER_KEY, inputs.root.root_id, self._output_subdir,
                                                             "not_applicable", "Optional disabled staging was not selected"),))
        try:
            observations = list(observe_confined(inputs.root.path, inputs.root.path / ".kittify/config.yaml"))
            if observations[-1].state.kind not in {"file", "absent"}:
                raise ValueError("Bundle source configuration is not a regular file")
            plans = self._plans_for_projection(inputs.root.path)
            if any(d.severity == "error" for plan in plans for d in plan.diagnostics):
                raise ValueError("; ".join(d.message for plan in plans for d in plan.diagnostics if d.severity == "error"))
            suppliers = sources.assessments or self._source_assessments(inputs, plans)
            files: list[StagedFile] = []
            directories: list[Path] = []
            for target in sorted(set(selected)):
                projector = self._projector_for(target)
                if projector is None:
                    raise ValueError(f"Unknown bundle target: {target}")
                directory = self._output_dir(inputs.root.path, target)
                entries = supplied_entries(projector.entries(plans, inputs.root.path), suppliers)
                files.extend(files_for_entries(entries, directory, inputs.root, observations))
                manifest = (directory / projector.manifest_relative_path).relative_to(inputs.root.path).as_posix()
                files.append(StagedFile(manifest, json_bytes(plugin_manifest_payload(target)), manifest=True))
                directories.append(directory)
            return prepare_staging(inputs, tuple(files), tuple(directories), tuple(observations), suppliers=suppliers)
        except (OSError, ValueError, TypeError, AgentConfigError) as exc:
            return OwnerAssessment(PROVIDER_KEY, inputs.root, complete=False, consent=inputs.consent,
                                   diagnostics=(Diagnostic("bundle_input_invalid", PROVIDER_KEY, "error", str(exc)),))

    def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
        return staging_guard(assessment)

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        return apply_staging(assessment, explicit_consent)

    @staticmethod
    def _source_assessments(inputs: AssessmentInputs, plans: Sequence[SurfacePlan]) -> tuple[OwnerAssessment, ...]:
        """Ask the selected registered owners for their concrete desired outputs."""
        from specify_cli.skills.installer import assess_skill_installation
        from specify_cli.skills.catalog import resolve_project_skill_catalog
        from ..providers.protocol import AssessingSurfaceProvider
        from ..service import build_providers

        selected = tuple(dict.fromkeys(
            SurfaceSelection(plan.tool_key, instance.definition) for plan in plans for instance in plan.instances
            if instance.path.is_absolute() and instance.path != inputs.root.path and instance.path.is_relative_to(inputs.root.path)
            and instance.definition.kind in BUNDLE_SURFACE_KINDS and instance.definition.activation_mode != ActivationMode.DISABLED
        ))
        result = []
        for provider in build_providers():
            selections = tuple(s for s in selected if s.definition.provider_key == provider.provider_key and provider.can_handle(s.definition))
            if not selections or not isinstance(provider, AssessingSurfaceProvider):
                continue
            owner_inputs = AssessmentInputs(inputs.root, consent=inputs.consent)
            if provider.provider_key == "managed_skills":
                installation = assess_skill_installation(owner_inputs, resolve_project_skill_catalog(inputs.root.path, stage=False),
                                                        tuple(sorted({s.tool_key for s in selections})))
                owner_inputs = AssessmentInputs(inputs.root, projected=installation, consent=inputs.consent)
            assessment = provider.assess(owner_inputs, (), selections=selections)
            if not assessment.complete:
                raise ValueError(f"{provider.provider_key}: " + "; ".join(d.message for d in assessment.diagnostics))
            if assessment.prepared is not None:
                result.append(assessment)
        return tuple(result)

    @staticmethod
    def _staged_output_dir(manifest_path: Path) -> Path:
        # Claude Code: ``<output>/.claude-plugin/plugin.json``.
        if manifest_path.parent.name == ".claude-plugin":
            return manifest_path.parent.parent
        return manifest_path.parent

    @staticmethod
    def _incomplete_status(
        instance: SurfaceInstance,
        missing: Sequence[SurfaceFinding],
    ) -> SurfaceStatus:
        findings = tuple(
            make_finding(
                BUNDLE_COMPONENT_MISSING,
                SEVERITY_ERROR,
                finding.message,
                tool_key=instance.owner,
                surface_id=_surface_id(instance),
                path=instance.path,
                repair_command=_REPAIR_HINT,
            )
            for finding in missing
        )
        return SurfaceStatus(
            instance=instance, state=STATE_MISSING, findings=findings
        )

    @staticmethod
    def _stale_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_STALE,
            findings=(
                make_finding(
                    PLUGIN_MANIFEST_STALE_PATH,
                    SEVERITY_WARNING,
                    (
                        "Plugin manifest references an unknown distribution "
                        f"target: {instance.owner}"
                    ),
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                ),
            ),
        )

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        """Re-project staging bundles for missing/stale statuses."""
        actionable = [
            s for s in statuses if s.state in (STATE_MISSING, STATE_STALE)
        ]
        if not actionable:
            return RepairResult(dry_run=dry_run)
        consent = ApplyConsent(automatic=True)
        assessment = self.assess(
            AssessmentInputs(OperationRoot("project", "project", project_root.resolve()),
                             projected=BundleSources(selected_targets=tuple(s.instance.owner for s in actionable)),
                             consent=consent), actionable, selections=(),
        )
        if not assessment.complete:
            return RepairResult(failed=tuple(_surface_id(s.instance) for s in actionable), dry_run=dry_run,
                                findings_after=tuple(make_finding(BUNDLE_COMPONENT_MISSING, SEVERITY_ERROR, d.message)
                                                     for d in assessment.diagnostics))
        if dry_run:
            return RepairResult(repaired=tuple(e.id for e in assessment.effects), dry_run=True)
        result = self.apply(assessment, consent)
        messages = tuple(d.message for d in result.diagnostics) + tuple(
            d.reason for d in assessment.dispositions if d.state in {"preserve", "consent_required"})
        return RepairResult(repaired=result.succeeded, failed=result.failed, skipped=result.skipped,
                            findings_after=tuple(make_finding(BUNDLE_COMPONENT_MISSING, SEVERITY_ERROR, message)
                                                 for message in messages))

    @staticmethod
    def _plans_for_projection(project_root: Path) -> list[SurfacePlan]:
        """Build the surface plans the projectors consume during repair.

        Imported lazily to avoid a provider <-> service import cycle.
        """
        from specify_cli.core.agent_config import load_agent_config
        from ..service import build_plans_for_bundles

        agents = load_agent_config(project_root).available
        plans: list[SurfacePlan] = build_plans_for_bundles(project_root, tool_keys=agents)
        return plans


# ---------------------------------------------------------------------------
# Self-registration (fires at import time via providers._discovery)
# ---------------------------------------------------------------------------
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=PluginBundleProvider,
        definitions=(plugin_manifest_definition(),),
        kind_tokens={
            "plugin-manifest": ToolSurfaceKind.PLUGIN_MANIFEST,
            "plugin_manifest": ToolSurfaceKind.PLUGIN_MANIFEST,
        },
        synthetic_key=PLUGIN_BUNDLE_TOOL_KEY,
        order=60,
    )
)
