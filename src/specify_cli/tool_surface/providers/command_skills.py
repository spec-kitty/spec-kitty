"""Command-skill surface provider.

Wraps :mod:`specify_cli.skills.command_installer` as a reporting-layer
:class:`~specify_cli.tool_surface.providers.protocol.ReportingSurfaceProvider`.
The provider never reimplements the installer's hash, ref-count, or shared-root
safety logic -- it delegates every mutation to the installer and only translates
its results into surface contract types.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
from pathlib import Path

from specify_cli.skills import command_installer, manifest_store

from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    CONFIGURED_TOOL_SURFACE_UNINSTALLED,
    GENERATED_SURFACE_MISSING,
    MANAGED_FILE_DRIFT,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STALE_GENERATED_SURFACE,
    UNMANAGED_SPEC_KITTY_SURFACE,
    UNSAFE_MANAGED_PATH,
    make_finding,
)
from ..model import SurfaceDefinition, SurfaceInstance, SurfaceSelection
from ..operations import (
    ApplyConsent,
    AssessmentInputs,
    Diagnostic,
    Disposition,
    InputObservation,
    OperationRoot,
    OwnerAssessment,
    OwnerApplyResult,
)
from ..repair import RepairResult
from ..status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_ORPHANED,
    STATE_PRESENT,
    STATE_STALE,
    STATE_UNSAFE,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "command_skills"
_PATH_PATTERN = ".agents/skills/spec-kitty.{command}/SKILL.md"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind command-skill --fix"
# Drift guidance: an edited command skill is replaced only by the explicit repair.
_DRIFT_REPAIR_HINT = "spec-kitty doctor tool-surfaces --fix"
_SKILLS_PREFIX = ".agents/skills/spec-kitty."
_SKILL_SUFFIX = "/SKILL.md"


def command_skill_definition() -> SurfaceDefinition:
    """Return the built-in command-skill :class:`SurfaceDefinition`."""
    return SurfaceDefinition(
        kind=ToolSurfaceKind.COMMAND_SKILL,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=_PATH_PATTERN,
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.SKILLS_INVOKABLE,
        provider_key=PROVIDER_KEY,
        repair_hint=_REPAIR_HINT,
    )


def _rel_path(command: str) -> str:
    return _PATH_PATTERN.format(command=command)


def _surface_id_for_rel(tool_key: str, rel_path: str) -> str:
    safe = rel_path.removeprefix(".agents/skills/")
    safe = safe.replace("/", ".").replace("\\", ".")
    return f"{tool_key}.{ToolSurfaceKind.COMMAND_SKILL}.{safe}"


class CommandSkillsProvider:
    """Provider for command-skill (``SKILL.md``) surfaces."""

    provider_key = PROVIDER_KEY

    def __init__(self, installer: object | None = None) -> None:
        # ``installer`` is accepted for dependency injection in tests; by default
        # the module-level installer functions are used directly so installer
        # invariants (hash/ref-count/shared-root safety) are never bypassed.
        self._installer = installer if installer is not None else command_installer

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == ToolSurfaceKind.COMMAND_SKILL)

    def assess(self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...]) -> OwnerAssessment:
        """Prepare the full selected batch, including zero-expansion pruning."""
        agents = tuple(
            sorted(
                {
                    selection.tool_key
                    for selection in selections
                    if self.can_handle(selection.definition) and selection.definition.activation_mode != ActivationMode.DISABLED
                }
            )
        )
        if not agents:
            return OwnerAssessment(
                PROVIDER_KEY,
                inputs.root,
                dispositions=(Disposition(PROVIDER_KEY, inputs.root.root_id, None, "not_applicable", "No enabled command-skill selection"),),
                inputs_fingerprint=(InputObservation("selections", selections),),
                consent=inputs.consent,
            )
        assessment = command_installer.prepare_commands(inputs, agents, prune=True)
        effects = tuple(
            replace(
                effect,
                surface_ids=tuple(
                    _surface_id(status.instance)
                    for status in statuses
                    if status.instance.path == effect.destination
                    and status.instance.owner in agents
                    and status.instance.definition.activation_mode != ActivationMode.DISABLED
                ),
            )
            for effect in assessment.effects
        )
        return replace(
            assessment,
            effects=effects,
            inputs_fingerprint=assessment.inputs_fingerprint
            + (
                # Findings are mutable reporting data retained by AssessedSurfaces.
                InputObservation("instances", tuple(status.instance for status in statuses)),
                InputObservation("states", tuple(status.state for status in statuses)),
                InputObservation("selections", selections),
            ),
        )

    def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
        """No command-owner lock exists; retain the complete pre-write check."""
        return nullcontext(command_installer.recheck_commands(assessment))

    def preflight(self, assessment: OwnerAssessment) -> tuple[Diagnostic, ...]:
        """Require original inputs before the composer's provisioning phase."""
        if (
            assessment.complete
            and assessment.prepared is None
            and not assessment.effects
            and not assessment.diagnostics
            and assessment.dispositions
            and all(item.state == "not_applicable" for item in assessment.dispositions)
        ):
            return ()
        return command_installer.recheck_commands(assessment, phase="preflight")

    def apply(self, assessment: OwnerAssessment, consent: ApplyConsent) -> OwnerApplyResult:
        """Consume the command owner's exact preparation and truthful results."""
        return command_installer.apply_commands(assessment, consent)

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into one instance per canonical command for ``tool_key``."""
        if tool_key not in command_installer.SUPPORTED_AGENTS:
            return []
        manifest = manifest_store.load(project_root)
        instances: list[SurfaceInstance] = []
        expected_rels: set[str] = set()
        for command in command_installer.CANONICAL_COMMANDS:
            rel = _rel_path(command)
            expected_rels.add(rel)
            abs_path = project_root / rel
            entry = manifest.find(rel)
            instances.append(
                SurfaceInstance(
                    definition=definition,
                    path=abs_path,
                    exists=abs_path.exists(),
                    file_hash=entry.content_hash if entry is not None else None,
                    owner=tool_key,
                    surface_id=f"{tool_key}.{ToolSurfaceKind.COMMAND_SKILL}.{rel.removeprefix('.agents/skills/').removesuffix('/SKILL.md')}",
                )
            )
        try:
            report = command_installer.verify(project_root)
        except command_installer.InstallerError:
            return instances
        extra_rels = set(report.orphans) | set(report.stale) | set(report.unsafe)
        for rel in sorted(extra_rels - expected_rels):
            abs_path = project_root / rel
            instances.append(
                SurfaceInstance(
                    definition=definition,
                    path=abs_path,
                    exists=abs_path.exists(),
                    file_hash=None,
                    owner=tool_key,
                    surface_id=_surface_id_for_rel(tool_key, rel),
                )
            )
        return instances

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Re-check existence and hash and return a :class:`SurfaceStatus`."""
        path = instance.path
        project_root, rel = _project_root_and_rel(path)
        verify_report = None
        if project_root is not None and rel is not None:
            try:
                verify_report = command_installer.verify(project_root)
            except command_installer.InstallerError:
                verify_report = None
        if verify_report is not None:
            if rel in verify_report.unsafe:
                return self._unsafe_status(instance, path)
            if rel in verify_report.stale:
                return self._stale_status(instance, path)
            if rel in verify_report.orphans:
                return self._orphan_status(instance, path)
            if rel in verify_report.gaps:
                return self._missing_status(instance, path)
        if project_root is not None and rel is not None:
            manifest = manifest_store.load(project_root)
            entry = manifest.find(rel)
            if entry is not None and instance.owner not in entry.agents:
                return self._uninstalled_status(instance, path)
        if not path.exists():
            return self._missing_status(instance, path)
        if instance.file_hash is not None:
            on_disk = manifest_store.fingerprint_file(path)
            if on_disk != instance.file_hash and not _is_canonical_bytes(project_root, rel, on_disk):
                return self._drift_status(instance, path)
        return SurfaceStatus(instance=instance, state=STATE_PRESENT)

    @staticmethod
    def _drift_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_DRIFTED,
            findings=(
                make_finding(
                    MANAGED_FILE_DRIFT,
                    SEVERITY_WARNING,
                    f"Command skill drifted from manifest hash: {path}; run '{_DRIFT_REPAIR_HINT}' to restore it",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                    repair_command=_DRIFT_REPAIR_HINT,
                ),
            ),
        )

    @staticmethod
    def _missing_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_MISSING,
            findings=(
                make_finding(
                    GENERATED_SURFACE_MISSING,
                    SEVERITY_ERROR,
                    f"Command skill for {instance.owner} is missing: {path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    @staticmethod
    def _orphan_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_ORPHANED,
            findings=(
                make_finding(
                    UNMANAGED_SPEC_KITTY_SURFACE,
                    SEVERITY_WARNING,
                    f"Spec Kitty-looking command skill is not owned by the manifest: {path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                ),
            ),
        )

    @staticmethod
    def _stale_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_STALE,
            findings=(
                make_finding(
                    STALE_GENERATED_SURFACE,
                    SEVERITY_WARNING,
                    f"Command skill is no longer canonical: {path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                ),
            ),
        )

    @staticmethod
    def _unsafe_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_UNSAFE,
            findings=(
                make_finding(
                    UNSAFE_MANAGED_PATH,
                    SEVERITY_ERROR,
                    f"Command skill path is unsafe or escapes the project root: {path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                ),
            ),
        )

    @staticmethod
    def _uninstalled_status(instance: SurfaceInstance, path: Path) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_MISSING,
            findings=(
                make_finding(
                    CONFIGURED_TOOL_SURFACE_UNINSTALLED,
                    SEVERITY_ERROR,
                    f"Configured tool is not recorded as an owner of command skill: {path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        """Delegate removal of an agent's command skills to the installer.

        The instance path is ``<project_root>/.agents/skills/...``; the project
        root is recovered by stripping the canonical relative suffix so the
        installer's shared-root safety logic is preserved.
        """
        rel = _PATH_PATTERN.split("{command}", 1)[0]
        marker = rel.split("/", 1)[0]
        parts = instance.path.parts
        if marker not in parts:
            return False
        project_root = Path(*parts[: parts.index(marker)])
        report = command_installer.remove(project_root, instance.owner)
        return bool(report.deref)

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        """Reinstall command skills for the affected agents via the installer."""
        affected = tuple(sorted({s.instance.owner for s in statuses if s.state in (STATE_MISSING, STATE_DRIFTED, STATE_STALE, STATE_ORPHANED, STATE_UNSAFE)}))
        if not affected:
            return RepairResult(dry_run=dry_run)
        selections = tuple(SurfaceSelection(agent, next(s.instance.definition for s in statuses if s.instance.owner == agent)) for agent in affected)
        # An explicit repair is the operator's consent to replace a drifted (edited) skill; only
        # DRIFTED statuses populate it, so missing/stale paths never widen the overwrite set.
        consent = ApplyConsent(
            automatic=True,
            overwrite_paths=tuple(sorted(s.instance.path.relative_to(project_root).as_posix() for s in statuses if s.state == STATE_DRIFTED)),
        )
        inputs = AssessmentInputs(OperationRoot("project", "project", project_root.absolute()), consent=consent)
        assessment = self.assess(inputs, statuses, selections=selections)
        if not assessment.complete:
            return RepairResult(failed=tuple(d.message for d in assessment.diagnostics), dry_run=dry_run)
        unresolved = {d.path for d in assessment.dispositions if d.state in {"preserve", "consent_required"}}
        eligible = tuple(
            _surface_id(s.instance) for s in statuses if s.instance.owner in affected and s.instance.path.relative_to(project_root).as_posix() not in unresolved
        )
        failed = tuple(sorted(path for path in unresolved if path is not None))
        if dry_run:
            return RepairResult(repaired=eligible, failed=failed, dry_run=True)
        result = self.apply(assessment, consent)
        if result.outcome != "applied":
            successful_paths = {e.destination for e in assessment.effects if e.id in result.succeeded}
            repaired = tuple(_surface_id(s.instance) for s in statuses if s.instance.path in successful_paths)
            return RepairResult(repaired=repaired, failed=failed + tuple(d.message for d in result.diagnostics))
        return RepairResult(repaired=eligible, failed=failed)


def _command_from_rel(rel: str) -> str | None:
    """Return the canonical command name of a command-skill relative path, else ``None``."""
    if not (rel.startswith(_SKILLS_PREFIX) and rel.endswith(_SKILL_SUFFIX)):
        return None
    return rel[len(_SKILLS_PREFIX) : -len(_SKILL_SUFFIX)] or None


def _is_canonical_bytes(project_root: Path | None, rel: str | None, on_disk: str) -> bool:
    """Whether *on_disk* is today's canonical rendering (a fresh file with an old recorded hash).

    ``None`` from the installer (no single canonical rendering) fails toward
    reporting drift: only a proven match suppresses the finding.
    """
    if project_root is None or rel is None:
        return False
    command = _command_from_rel(rel)
    return command is not None and command_installer.canonical_digest(project_root, command) == on_disk


def _project_root_and_rel(path: Path) -> tuple[Path | None, str | None]:
    parts = path.parts
    try:
        agents_index = parts.index(".agents")
    except ValueError:
        return None, None
    project_root = Path(*parts[:agents_index])
    rel = Path(*parts[agents_index:])
    return project_root, rel.as_posix()


# ---------------------------------------------------------------------------
# Self-registration (fires at import time via providers._discovery)
# ---------------------------------------------------------------------------
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=CommandSkillsProvider,
        definitions=(command_skill_definition(),),
        kind_tokens={"command-skill": ToolSurfaceKind.COMMAND_SKILL},
        order=0,
    )
)
