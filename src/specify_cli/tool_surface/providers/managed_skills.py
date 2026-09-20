"""Managed doctrine-skill surface provider.

Wraps the existing managed doctrine-skill infrastructure
(:mod:`specify_cli.skills.registry` and :mod:`specify_cli.skills.verifier`) as a
reporting-layer
:class:`~specify_cli.tool_surface.providers.protocol.ReportingSurfaceProvider`.

Default repair consumes the installer's coordinated global/project preparation.
The verifier's legacy count-based repair collaborator remains injectable, but
ambiguous partial counts never become invented successful surface identities.

Doctrine skills are distinct from command skills:

* Command skills are slash-command invocations rendered to
  ``.agents/skills/spec-kitty.<command>/SKILL.md`` and tracked in
  ``.kittify/command-skills-manifest.json``.
* Doctrine skills are managed knowledge/mission-step surfaces installed by the
  skill installer and tracked in ``.kittify/skills-manifest.json``.

The provider never reimplements the installer's hash/symlink/path-traversal
safety logic or the verifier's drift detection -- it delegates every probe and
mutation to those modules and only translates their results into surface
contract types. The verifier already produces its own ``doctor skills`` report;
this provider adds the surface-contract view on top of it and must not duplicate
or conflict with that output.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, cast

from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_WRAPPER
from specify_cli.skills import installer as skill_installer
from specify_cli.skills import command_installer
from specify_cli.skills import verifier as skill_verifier
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    compute_content_hash,
    load_manifest,
)
from specify_cli.skills.paths import SkillPathObservation, get_primary_project_skill_root, observe_skill_path, recheck_skill_paths
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.command_installer import _windows_dir_mode_only_divergence

from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    GENERATED_SURFACE_MISSING,
    MANAGED_FILE_DRIFT,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    make_finding,
)
from ..model import SurfaceDefinition, SurfaceInstance, SurfaceSelection
from ..operations import ApplyConsent, AssessmentInputs, Diagnostic, FileState, OperationRoot, OwnerAssessment, OwnerApplyResult, PhysicalEffect, coalesce_effects
from ..repair import RepairResult
from ..bundles.projection import SelectedSkillBundle, completed_selected_skill_bundle, selected_skill_bundle_guard
from ..bundles.model import PreparedBundle
from ..status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_PRESENT,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "managed_skills"
_PATH_PATTERN = ".kittify/skills-manifest.json:{installed_path}"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind doctrine-skill --fix"
_PAIRED_GLOBAL: ContextVar[OwnerAssessment | None] = ContextVar("paired_skill_global", default=None)
_PROVISIONING_PAIR: ContextVar[skill_installer.SkillInstallationAssessment | None] = ContextVar(
    "provisioning_skill_pair", default=None,
)
_COMPOSITION: ContextVar[SkillCommandComposition | None] = ContextVar("skill_command_composition", default=None)


@dataclass(frozen=True)
class SkillCommandComposition:
    """Exact paired installation plus commands; shared parents have one writer."""

    installation: skill_installer.SkillInstallationAssessment
    commands: OwnerAssessment
    parents: tuple[SkillPathObservation, ...]
    staged_bundle: SelectedSkillBundle | None = None

    def __post_init__(self) -> None:
        installation, commands = self.installation, self.commands
        project, payload = installation.project_skills, commands.prepared
        if (
            commands.owner_key != "command_skills"
            or commands.root != project.root
            or commands.consent != project.consent
            or not isinstance(payload, command_installer.PreparedCommands)
            or not isinstance(project.prepared, skill_installer.PreparedProjectSkills)
            or payload.provisioning is not project.prepared.provisioning
            or not all(a.complete and not any(d.severity == "error" for d in a.diagnostics) for a in (commands, project, installation.global_assets))
        ):
            raise ValueError("Complete commands and the exact paired provisioning input required")
        _ = self.effects  # Static conflicts abort before provisioning, including replace().
        if self.staged_bundle is not None:
            bundle = self.staged_bundle
            if bundle.commands is not commands or not any(s is project for s in cast("PreparedBundle", bundle.assessment.prepared).suppliers):
                raise ValueError("Selected bundle must retain this exact command/project pair")
            coalesce_effects(self.effects + bundle.assessment.effects)

    @property
    def effects(self) -> tuple[PhysicalEffect, ...]:
        """Unique physical effects, retaining both owners' logical claims."""
        project = self.installation.project_skills
        commands = {e.destination: e for e in self.commands.effects}
        effects = list(self.installation.global_assets.effects)
        for effect in project.effects:
            command = commands.get(effect.destination)
            if command is None:
                effects.append(effect)
                continue
            if (command.action, command.before, command.after, command.phase) != (
                "create",
                FileState("absent"),
                FileState("directory", mode=0o755),
                effect.phase,
            ) or (effect.action, effect.before, effect.after) != (command.action, command.before, command.after):
                raise ValueError(f"Unsupported shared skill effect: {effect.destination}")
            commands[effect.destination] = replace(
                command,
                ownership=command.ownership + effect.ownership,
                logical_owners=command.logical_owners + effect.logical_owners,
                surface_ids=command.surface_ids + effect.surface_ids,
            )
        combined: tuple[PhysicalEffect, ...] = coalesce_effects(tuple(effects) + tuple(commands.values()))
        return combined


def _composition_parents(installation: skill_installer.SkillInstallationAssessment, commands: OwnerAssessment) -> tuple[Path, ...]:
    root = commands.root.path

    def ancestors(owner: OwnerAssessment) -> set[Path]:
        return {p for e in owner.effects for p in e.destination.parents if p == root or p.is_relative_to(root)}

    return tuple(sorted(ancestors(installation.project_skills) & ancestors(commands)))


def _composition_refused(composition: SkillCommandComposition, errors: tuple[Diagnostic, ...]) -> tuple[OwnerApplyResult, ...]:
    return tuple(
        OwnerApplyResult(
            owner,
            skipped=tuple(e.id for e in composition.effects if e.owner == owner),
            outcome="precondition_changed",
            diagnostics=errors,
        )
        for owner in (composition.commands.owner_key, composition.installation.global_assets.owner_key, PROVIDER_KEY)
    )


def _recheck_command_completion(
    composition: SkillCommandComposition,
    created: dict[Path, SkillPathObservation],
) -> tuple[SkillPathObservation, ...]:
    """Check concrete command output and exact common-parent membership/identity."""
    command_effects = composition.commands.effects
    payload = composition.commands.prepared
    assert isinstance(payload, command_installer.PreparedCommands)
    provisioning = payload.provisioning
    created_yaml: tuple[Path, ...] = ()
    if provisioning is not None and provisioning.write.before_bytes is None:
        created_yaml = provisioning.write.recheck_applied()
    for effect in command_effects:
        state = observe_skill_path(effect.destination).state
        normalized = replace(state, mtime_ns=effect.after.mtime_ns)
        if normalized != effect.after and not _windows_dir_mode_only_divergence(normalized, effect.after):
            raise ValueError(f"Completed command output changed: {effect.destination}")
    for before in composition.parents:
        current = observe_skill_path(before.path, members=True)
        expected = created.get(before.path, before)
        if before.path in created_yaml:
            expected = current  # Identity/mode already checked by the YAML writer receipt.
        bundle_parent = command_installer._bundle_parent_input(composition.commands, before.path)
        names = set(bundle_parent.children if bundle_parent is not None and bundle_parent.children is not None else before.children or ())
        names.update(path.name for path in created_yaml if path.parent == before.path)
        for effect in command_effects:
            if effect.destination.parent == before.path:
                if effect.after.kind == "absent":
                    names.discard(effect.destination.name)
                else:
                    names.add(effect.destination.name)
        if (current.state, current.identity, current.children) != (expected.state, expected.identity, tuple(sorted(names))):
            raise ValueError(f"Shared skill parent changed: {before.path}")
    shared = {e.destination for e in composition.installation.project_skills.effects} & {e.destination for e in command_effects}
    receipts = tuple(created[path] for path in sorted(shared))
    recheck_skill_paths(receipts)
    return receipts


class _VerifyResultProto(Protocol):
    """Subset of ``skills.verifier.VerifyResult`` this provider relies on."""

    ok: bool


class _VerifierProto(Protocol):
    """Subset of the ``skills.verifier`` module this provider delegates to."""

    def verify_installed_skills(self, project_path: Path) -> _VerifyResultProto:
        ...


class _RepairProto(Protocol):
    """Subset of the ``skills.verifier`` module this provider delegates to.

    ``repair_skills`` is owned by :mod:`specify_cli.skills.verifier` (not the
    ``installer`` module), so the default collaborator is the verifier module.
    """

    def repair_skills(
        self,
        project_path: Path,
        verify_result: _VerifyResultProto,
        registry: SkillRegistry,
    ) -> tuple[int, int]:
        ...


def managed_skill_definition() -> SurfaceDefinition:
    """Return the built-in doctrine-skill :class:`SurfaceDefinition`."""
    return SurfaceDefinition(
        kind=ToolSurfaceKind.DOCTRINE_SKILL,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=_PATH_PATTERN,
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.SKILLS_INVOKABLE,
        provider_key=PROVIDER_KEY,
        repair_hint=_REPAIR_HINT,
    )


class ManagedSkillsProvider:
    """Provider for managed doctrine-skill surfaces."""

    provider_key = PROVIDER_KEY

    def __init__(
        self,
        verifier: _VerifierProto | None = None,
        installer: _RepairProto | None = None,
        registry_factory: Callable[[], SkillRegistry] | None = None,
    ) -> None:
        # All collaborators are accepted for dependency injection in tests. By
        # default the module-level functions from ``skills.verifier`` are used
        # directly so the verifier invariants (hash/symlink/path-traversal
        # safety) are never bypassed or reimplemented. ``repair_skills`` lives in
        # the verifier module, so the default repair collaborator binds there --
        # the ``installer`` module does not expose it.
        self._verifier: _VerifierProto = (
            verifier if verifier is not None else skill_verifier
        )
        self._installer: _RepairProto = (
            installer if installer is not None else cast(_RepairProto, skill_verifier)
        )
        self._registry_factory: Callable[[], SkillRegistry] = (
            registry_factory
            if registry_factory is not None
            else SkillRegistry.from_package
        )
        self._legacy_collaborators = verifier is not None or installer is not None

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return definition.kind is ToolSurfaceKind.DOCTRINE_SKILL

    def compose_installation(
        self,
        installation: skill_installer.SkillInstallationAssessment,
        commands: OwnerAssessment,
        *,
        staged_bundle: OwnerAssessment | None = None,
    ) -> SkillCommandComposition:
        """Admit the original command/managed pair, without reassessment or writes."""
        return SkillCommandComposition(
            installation,
            commands,
            tuple(observe_skill_path(path, members=True) for path in _composition_parents(installation, commands)),
            SelectedSkillBundle.prepare(staged_bundle, commands) if staged_bundle is not None else None,
        )

    @contextmanager
    def preflight_composition(
        self,
        composition: SkillCommandComposition,
        consent: ApplyConsent,
    ) -> Iterator[tuple[Diagnostic, ...]]:
        """Hold existing three global locks and project lock across provisioning."""
        with selected_skill_bundle_guard(composition.staged_bundle) as bundle_errors, self.preflight_installation(composition.installation, consent) as errors:
            errors += bundle_errors
            errors += command_installer.recheck_commands(composition.commands, phase="preflight")
            try:
                _ = composition.effects
                if tuple(p.path for p in composition.parents) != _composition_parents(composition.installation, composition.commands):
                    raise ValueError("Shared parent inventory differs")
                recheck_skill_paths(composition.parents)
            except (OSError, ValueError) as exc:
                errors += (Diagnostic("shared_parent_changed", PROVIDER_KEY, "error", str(exc)),)
            token = _COMPOSITION.set(None if errors else composition)
            try:
                yield errors
            finally:
                _COMPOSITION.reset(token)

    def apply_composition(
        self,
        composition: SkillCommandComposition,
        consent: ApplyConsent,
    ) -> tuple[OwnerApplyResult, ...]:
        """Commands first, then paired global/managed apply, with one shared mkdir."""
        from specify_cli.runtime.asset_preparation import recheck_assets
        from .command_skills import CommandSkillsProvider
        from ..repair import SurfaceRepairService

        installation, commands = composition.installation, composition.commands
        if _COMPOSITION.get() is not composition or consent != commands.consent or not consent.automatic:
            return _composition_refused(
                composition, (Diagnostic("skill_composition_preflight_required", PROVIDER_KEY, "error", "Exact active composition and consent required"),)
            )
        with (
            completed_selected_skill_bundle(composition.staged_bundle) as bundle_errors,
            recheck_assets(installation.global_assets) as global_errors,
            self.recheck(installation.project_skills) as project_errors,
        ):
            errors = bundle_errors + global_errors + project_errors + command_installer.recheck_commands(commands, phase="apply")
            if errors:
                return _composition_refused(composition, errors)
            _COMPOSITION.set(None)  # Single consumption, including partial failure.
            with command_installer._record_command_parent_creations() as created:
                command_results: tuple[OwnerApplyResult, ...] = SurfaceRepairService([CommandSkillsProvider()]).apply_assessments((commands,), consent)
            if any(r.outcome not in {"applied", "skipped"} for r in command_results):
                return command_results + _composition_refused(composition, command_results[0].diagnostics)[1:]
            try:
                receipts = _recheck_command_completion(composition, created)
            except (OSError, ValueError, KeyError) as exc:
                errors = (Diagnostic("shared_parent_changed", PROVIDER_KEY, "error", str(exc)),)
                return command_results + _composition_refused(composition, errors)[1:]
            with skill_installer._completed_command_parents(installation.project_skills, receipts):
                results = self.apply_installation(installation, consent)
            delegated = {e.id for e in installation.project_skills.effects if e.destination in {p.path for p in receipts}}
            return command_results + tuple(replace(r, skipped=tuple(i for i in r.skipped if i not in delegated)) for r in results)

    def assess(
        self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...]
    ) -> OwnerAssessment:
        """Consume the project part of an explicitly coordinated installation."""
        _ = statuses  # Selection policy, including zero expansion, is authoritative.
        agents = tuple(sorted({selection.tool_key for selection in selections if self.can_handle(selection.definition)}))
        installation = inputs.projected
        if isinstance(installation, skill_installer.SkillInstallationAssessment):
            project = installation.project_skills
            if installation.agent_keys == agents and project.root == inputs.root and project.consent == inputs.consent:
                if installation.global_assets.complete:
                    return project
                return replace(project, complete=False, diagnostics=project.diagnostics + installation.global_assets.diagnostics)
            return OwnerAssessment(PROVIDER_KEY, inputs.root, complete=False, diagnostics=(
                Diagnostic("skill_context_mismatch", PROVIDER_KEY, "error", "Coordinated skill context differs from selected project inputs"),
            ))
        assessment = skill_installer.assess_project_skills(inputs, self._registry_factory(), agents)
        return replace(assessment, complete=False, diagnostics=assessment.diagnostics + (
            Diagnostic("managed_skills_global_context_required", PROVIDER_KEY, "error",
                       "Prepare and dispatch the separate coordinated global owner using assess_skill_installation"),
        ))

    def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
        pair = _PROVISIONING_PAIR.get()
        return skill_installer.recheck_project_skills(
            assessment, provisioning_applied=pair is not None and assessment == pair.project_skills,
        )

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        return skill_installer.apply_project_skills(assessment, explicit_consent)

    @contextmanager
    def preflight_installation(
        self, installation: skill_installer.SkillInstallationAssessment, consent: ApplyConsent,
    ) -> Iterator[tuple[Diagnostic, ...]]:
        """Check BOTH original owners before provisioning; hold locks through apply.

        Only after an empty diagnostic tuple may the caller apply its retained
        compiler descriptor, then call apply_installation inside this context.
        """
        from specify_cli.runtime.asset_preparation import recheck_assets

        global_assets, project = installation.global_assets, installation.project_skills
        with recheck_assets(global_assets) as global_errors, skill_installer.recheck_project_skills(project) as project_errors:
            errors = global_errors + project_errors
            if not consent.automatic or not global_assets.complete or not project.complete or consent != global_assets.consent or consent != project.consent:
                errors += (Diagnostic("skill_context_mismatch", PROVIDER_KEY, "error", "Complete paired assessments and exact consent required"),)
            pair = replace(installation, project_skills=replace(project, effects=coalesce_effects(project.effects)))
            token = _PROVISIONING_PAIR.set(None if errors else pair)
            try:
                yield errors
            finally:
                _PROVISIONING_PAIR.reset(token)

    def apply_installation(
        self, installation: skill_installer.SkillInstallationAssessment, consent: ApplyConsent,
    ) -> tuple[OwnerApplyResult, ...]:
        """Hold paired preflight/locks around the existing per-owner dispatcher.

        This is the provider composition boundary, not another global assessment.
        Raw independent dispatch cannot establish this operation-wide guarantee.
        """
        from specify_cli.runtime.asset_preparation import recheck_assets
        from ..repair import SurfaceRepairService

        global_assets, project = installation.global_assets, installation.project_skills
        prepared = project.prepared
        if isinstance(prepared, skill_installer.PreparedProjectSkills) and prepared.provisioning is not None:
            pair = replace(installation, project_skills=replace(project, effects=coalesce_effects(project.effects)))
            if _PROVISIONING_PAIR.get() != pair:
                errors = (Diagnostic("paired_skill_preflight_required", PROVIDER_KEY, "error",
                                     "Canonical provisioning requires original paired preflight before any writes"),)
                return tuple(OwnerApplyResult(
                    owner.owner_key, skipped=tuple(effect.id for effect in owner.effects),
                    outcome="precondition_changed", diagnostics=errors,
                ) for owner in (global_assets, project))
        with recheck_assets(global_assets) as global_errors, self.recheck(project) as project_errors:
            errors = global_errors + project_errors
            if not global_assets.complete or not project.complete or consent != global_assets.consent or consent != project.consent:
                errors += (Diagnostic("skill_context_mismatch", PROVIDER_KEY, "error", "Complete paired assessments and exact consent required"),)
            if errors:
                return tuple(OwnerApplyResult(
                    owner.owner_key, skipped=tuple(effect.id for effect in owner.effects),
                    outcome="precondition_changed", diagnostics=errors,
                ) for owner in (global_assets, project))
            token = _PAIRED_GLOBAL.set(replace(global_assets, effects=coalesce_effects(global_assets.effects)))
            try:
                results: tuple[OwnerApplyResult, ...] = SurfaceRepairService([GlobalSkillAssetsProvider(), self]).apply_assessments(
                    (global_assets, project), consent,
                )
                return results
            finally:
                _PAIRED_GLOBAL.reset(token)

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into one instance per managed doctrine skill for ``tool_key``.

        The registry is policy and the manifest is state. Manifest entries for
        ``tool_key`` carry installed hashes when present; otherwise the canonical
        registry still supplies the expected project paths so fresh clones report
        repairable missing doctrine skills instead of silently returning no
        surfaces.
        """
        manifest = load_manifest(project_root)
        manifest_entries = (
            [entry for entry in manifest.entries if entry.agent_key == tool_key]
            if manifest is not None
            else []
        )
        entries_by_path = {
            entry.installed_path: entry
            for entry in self._expected_entries(tool_key)
        }
        for entry in manifest_entries:
            expected = entries_by_path.get(entry.installed_path)
            entries_by_path[entry.installed_path] = (
                replace(entry, content_hash=expected.content_hash) if expected is not None else entry
            )
        instances: list[SurfaceInstance] = []
        for entry in entries_by_path.values():
            abs_path = project_root / entry.installed_path
            instances.append(
                SurfaceInstance(
                    definition=definition,
                    path=abs_path,
                    exists=abs_path.exists(),
                    file_hash=entry.content_hash or None,
                    owner=tool_key,
                    surface_id=_managed_surface_id(tool_key, entry),
                )
            )
        return instances

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Re-check existence and manifest hash via the managed-skill layer."""
        path = instance.path
        if path.is_symlink():
            return self._drifted_status(instance)
        if not path.exists():
            return self._missing_status(instance)
        if not path.is_file():
            return self._drifted_status(instance)
        if instance.file_hash is not None:
            on_disk = self._content_hash(path)
            if on_disk != instance.file_hash:
                return self._drifted_status(instance)
        return SurfaceStatus(instance=instance, state=STATE_PRESENT)

    @staticmethod
    def _content_hash(path: Path) -> str | None:
        try:
            digest: str = compute_content_hash(path)
        except OSError:
            return None
        return digest

    @staticmethod
    def _missing_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_MISSING,
            findings=(
                make_finding(
                    GENERATED_SURFACE_MISSING,
                    SEVERITY_ERROR,
                    f"Managed doctrine skill for {instance.owner} is missing: "
                    f"{instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    @staticmethod
    def _drifted_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_DRIFTED,
            findings=(
                make_finding(
                    MANAGED_FILE_DRIFT,
                    SEVERITY_WARNING,
                    f"Managed doctrine skill drifted from manifest hash: "
                    f"{instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        """Doctrine-skill removal is not in scope for the surface contract.

        Managed doctrine skills are removed per-agent by the dedicated skill
        installer flow (``agent config remove``/skill uninstall), which owns the
        symlink and shared-root ref-count safety logic. This provider therefore
        never deletes them as part of surface repair and returns ``False`` to
        signal that no removal was performed.
        """
        _ = instance
        return False

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        """Prepare once, then report only actually permitted/completed repairs."""
        actionable = [
            s for s in statuses if s.state in (STATE_MISSING, STATE_DRIFTED)
        ]
        if not actionable:
            return RepairResult(dry_run=dry_run)
        ids = tuple(_surface_id(s.instance) for s in actionable)
        tool_keys = tuple(sorted({s.instance.owner for s in actionable}))
        if not self._legacy_collaborators or dry_run:
            return self._repair_prepared(project_root, actionable, tool_keys, dry_run=dry_run)
        unmanifested = any(
            not _manifest_owns(project_root, s.instance) for s in actionable
        )
        return self._delegate_repair(project_root, ids, unmanifested)

    def _repair_prepared(
        self, project_root: Path, statuses: Sequence[SurfaceStatus], tool_keys: tuple[str, ...], *, dry_run: bool,
    ) -> RepairResult:
        ids = tuple(_surface_id(status.instance) for status in statuses)
        consent = ApplyConsent(automatic=True)
        try:
            registry = self._resolve_registry()
            if registry is None:
                return RepairResult(failed=("managed_skills: no canonical skill registry",) + ids, dry_run=dry_run)
            inputs = AssessmentInputs(OperationRoot("project", "project", project_root.absolute()), consent=consent)
            installation = skill_installer.assess_skill_installation(inputs, registry, tool_keys)
        except (OSError, ValueError) as exc:
            return RepairResult(failed=(f"managed_skills: {exc}",) + ids, dry_run=dry_run)
        if not installation.global_assets.complete or not installation.project_skills.complete:
            return RepairResult(failed=ids, dry_run=dry_run)
        project = installation.project_skills
        succeeded = {effect.id for effect in project.effects}
        errors: tuple[str, ...] = ()
        if not dry_run:
            results = skill_installer.apply_skill_installation(
                installation,
                consent,
                rebuild_global_assets=lambda: skill_installer.assess_skill_installation(inputs, registry, tool_keys).global_assets,
            )
            succeeded = set(results[1].succeeded)
            errors = tuple(f"managed_skills: {item.message}" for result in results for item in result.diagnostics)
        repaired: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []
        for status in statuses:
            sid = _surface_id(status.instance)
            effects = [effect for effect in project.effects if effect.destination == status.instance.path.absolute()]
            if effects:
                (repaired if all(effect.id in succeeded for effect in effects) else failed).append(sid)
            else:
                skipped.append(sid)
        return RepairResult(repaired=tuple(repaired), skipped=tuple(skipped), failed=tuple(failed) + errors, dry_run=dry_run)

    def _delegate_repair(
        self,
        project_root: Path,
        ids: tuple[str, ...],
        unmanifested: bool,
    ) -> RepairResult:
        registry = self._resolve_registry()
        if registry is None:
            return RepairResult(
                failed=("managed_skills: no canonical skill registry",) + ids,
                dry_run=False,
            )
        if unmanifested:
            return RepairResult(failed=("managed_skills: legacy collaborator cannot assess unmanifested content",) + ids)
        verify_result = self._verifier.verify_installed_skills(project_root)
        if verify_result.ok:
            return RepairResult(dry_run=False)
        try:
            repaired, failed = self._installer.repair_skills(
                project_root, verify_result, registry
            )
        except OSError as exc:  # surfaced as a failure, never swallowed
            return RepairResult(
                failed=(f"managed_skills: {exc}",) + ids,
                dry_run=False,
            )
        return self._repair_outcome(ids, repaired, failed)

    @staticmethod
    def _repair_outcome(
        ids: tuple[str, ...], repaired: int, failed: int
    ) -> RepairResult:
        if failed > 0:
            return RepairResult(
                failed=(f"managed_skills: {failed} file(s) failed to repair; legacy result has no path identities",) + ids,
                dry_run=False,
            )
        if repaired != len(ids):
            return RepairResult(failed=("managed_skills: ambiguous legacy repair count",) + ids)
        return RepairResult(repaired=ids, dry_run=False)

    def _resolve_registry(self) -> SkillRegistry | None:
        registry = self._registry_factory()
        if registry.discover_skills():
            return registry
        return None

    def _expected_entries(self, tool_key: str) -> list[ManagedFileEntry]:
        config = AGENT_SKILL_CONFIG.get(tool_key)
        if config is None or config["class"] == SKILL_CLASS_WRAPPER:
            return []
        root = get_primary_project_skill_root(tool_key)
        if root is None:
            return []
        registry = self._resolve_registry()
        if registry is None:
            return []
        installation_class = str(config["class"])
        entries: list[ManagedFileEntry] = []
        for skill in registry.discover_skills():
            for source_file in skill.all_files:
                rel_within_skill = source_file.relative_to(skill.skill_dir)
                installed_path = (
                    Path(root) / skill.name / rel_within_skill
                ).as_posix()
                source = skill_verifier._find_source_file(skill.skill_dir, rel_within_skill.as_posix())
                if source is None:
                    raise ValueError(f"Unsafe or missing canonical skill source: {source_file}")
                entries.append(
                    ManagedFileEntry(
                        skill_name=skill.name,
                        source_file=rel_within_skill.as_posix(),
                        installed_path=installed_path,
                        installation_class=installation_class,
                        agent_key=tool_key,
                        content_hash=skill_verifier._expected_content_hash(source, skill.name, rel_within_skill.as_posix()),
                        installed_at="",
                        delivery_mode="copy",
                    )
                )
        return entries


class GlobalSkillAssetsProvider(ManagedSkillsProvider):
    """Dispatcher adapter for the separately retained coordinated global owner.

    It is intentionally not registered as another inventory provider. Composers
    dispatch the existing global assessment through apply_installation, never
    assess a second cold batch or dispatch outside its paired guarded context.
    """

    provider_key = "global_assets"

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        _ = definition
        return False

    def assess(
        self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...]
    ) -> OwnerAssessment:
        _ = inputs, statuses, selections
        raise ValueError("Dispatch the existing coordinated global assessment; do not prepare another global batch")

    @contextmanager
    def recheck(self, assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
        from specify_cli.runtime.asset_preparation import recheck_assets

        # WP02 coalesces into an equal immutable value, not the same object.
        if _PAIRED_GLOBAL.get() != assessment:
            yield (Diagnostic("paired_skill_preflight_required", self.provider_key, "error",
                              "Use ManagedSkillsProvider.apply_installation for paired preflight and dispatch"),)
            return
        with recheck_assets(assessment) as diagnostics:
            yield diagnostics

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        from specify_cli.runtime.asset_preparation import apply_assets

        if _PAIRED_GLOBAL.get() != assessment:
            return OwnerApplyResult(self.provider_key, skipped=tuple(effect.id for effect in assessment.effects),
                                    outcome="precondition_changed", diagnostics=(
                                        Diagnostic("paired_skill_preflight_required", self.provider_key, "error",
                                                   "Global skill apply requires the paired guarded context"),
                                    ))
        return apply_assets(assessment, explicit_consent)


def doctrine_skill_entries(
    project_root: Path, tool_key: str
) -> list[ManagedFileEntry]:
    """Return the manifest entries owned by ``tool_key`` (helper for tests)."""
    manifest = load_manifest(project_root)
    if manifest is None:
        return []
    return [e for e in manifest.entries if e.agent_key == tool_key]


def _managed_surface_id(tool_key: str, entry: ManagedFileEntry) -> str:
    safe_path = entry.source_file.replace("/", ".").replace("\\", ".")
    return f"{tool_key}.{ToolSurfaceKind.DOCTRINE_SKILL}.{entry.skill_name}.{safe_path}"


def _manifest_owns(project_root: Path, instance: SurfaceInstance) -> bool:
    manifest = load_manifest(project_root)
    if manifest is None:
        return False
    try:
        rel = instance.path.relative_to(project_root).as_posix()
    except ValueError:
        try:
            rel = instance.path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return False
    return any(
        entry.agent_key == instance.owner and entry.installed_path == rel
        for entry in manifest.entries
    )


# ---------------------------------------------------------------------------
# Self-registration (fires at import time via providers._discovery)
# ---------------------------------------------------------------------------
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=ManagedSkillsProvider,
        definitions=(managed_skill_definition(),),
        kind_tokens={"doctrine-skill": ToolSurfaceKind.DOCTRINE_SKILL},
        order=40,
    )
)
