"""Native-config surface provider.

Handles tool-specific config *glue* -- the entries that wire a harness up to
discover Spec Kitty's shared skills, distinct from the orientation/context files
owned by :mod:`session_presence`. These are :data:`ToolSurfaceKind.NATIVE_CONFIG`
surfaces.

Currently the only verified native-config glue is Mistral Vibe's ``skill_paths``
entry in ``.vibe/config.toml`` (see
:mod:`specify_cli.skills.vibe_config`). The provider expands one instance per
tool that needs glue, probes whether the glue is present and current, and
delegates repair back to the owning helper -- it never reimplements the TOML
merge logic.

Harnesses with no known native-config glue yield a single
``research-gap-surface`` finding rather than being treated as healthy.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import replace
from collections.abc import Iterator
from hashlib import sha256  # noqa: TID251 -- exact physical bytes, not doctrine hashing.
from pathlib import Path
import tomllib

from specify_cli.skills.vibe_config import (
    VIBE_SKILL_PATH,
    PreparedVibeConfig,
    ensure_project_skill_path,
    prepare_project_skill_path,
)
from specify_cli.session_presence.writers.markdown_rules import observe_presence_path, presence_state
from specify_cli.core.agent_config import load_agent_config, AgentConfigError
from ..operations import (
    AssessmentInputs,
    ApplyConsent,
    Diagnostic,
    Disposition,
    FileState,
    OperationRoot,
    OwnerAssessment,
    OwnerApplyResult,
    OwnershipProof,
    PhysicalEffect,
    state_equivalent,
)

from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    NATIVE_CONFIG_MISSING,
    RESEARCH_GAP_SURFACE,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    make_finding,
)
from ..model import SurfaceDefinition, SurfaceInstance, SurfaceSelection
from ..repair import RepairResult
from ..status import (
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "native_config"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind native_config --fix"
_RESEARCH_GAP_SENTINEL = "<unsupported>"
_VIBE_CONFIG_REL = ".vibe/config.toml"

# Tools whose skills are discovered only after a native-config glue entry is
# written. ``vibe`` needs the ``skill_paths`` entry in ``.vibe/config.toml``.
_VIBE_TOOL_KEY = "vibe"


def native_config_definition() -> SurfaceDefinition:
    """Return the built-in ``native_config`` :class:`SurfaceDefinition`."""
    return SurfaceDefinition(
        kind=ToolSurfaceKind.NATIVE_CONFIG,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=_VIBE_CONFIG_REL,
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.ALWAYS,
        provider_key=PROVIDER_KEY,
        repair_hint=_REPAIR_HINT,
    )


class NativeConfigProvider:
    """Provider for tool-specific native config glue (e.g. vibe skill paths)."""

    provider_key = PROVIDER_KEY

    def assess(
        self,
        inputs: AssessmentInputs,
        statuses: Sequence[SurfaceStatus],
        *,
        selections: tuple[SurfaceSelection, ...],
    ) -> OwnerAssessment:
        """Prepare the selected native owner, including empty expansion."""
        selected = any(
            s.tool_key == _VIBE_TOOL_KEY
            and s.definition.activation_mode != ActivationMode.DISABLED
            and s.definition.required_policy == RequiredPolicy.REPAIRABLE_REQUIRED
            for s in selections
        )
        if not selected:
            return OwnerAssessment(
                PROVIDER_KEY,
                inputs.root,
                dispositions=(Disposition(PROVIDER_KEY, inputs.root.root_id, None, "not_applicable", "No selected verified native glue"),),
                consent=inputs.consent,
            )
        try:
            config = observe_presence_path(inputs.root.path, ".kittify/config.yaml")
            if presence_state(config[-1]).kind not in ("file", "absent"):
                raise ValueError("Agent config is not a regular file")
            if presence_state(config[-1]).kind == "file" and "vibe" not in load_agent_config(inputs.root.path).available:
                return OwnerAssessment(
                    PROVIDER_KEY,
                    inputs.root,
                    dispositions=(Disposition(PROVIDER_KEY, inputs.root.root_id, None, "not_applicable", "Vibe is disabled"),),
                    consent=inputs.consent,
                )
            prepared = prepare_project_skill_path(inputs.root.path)
            effects = self._effects(inputs.root, prepared, tuple(_surface_id(s.instance) for s in statuses))
            prepared = replace(prepared, observations=prepared.observations + config)
        except (OSError, ValueError, TypeError, AttributeError, AgentConfigError) as exc:
            return OwnerAssessment(
                PROVIDER_KEY,
                inputs.root,
                complete=False,
                diagnostics=(Diagnostic("native_config_unreadable", PROVIDER_KEY, "error", str(exc)),),
                consent=inputs.consent,
            )
        dispositions = () if effects else (Disposition(PROVIDER_KEY, inputs.root.root_id, _VIBE_CONFIG_REL, "unchanged", "Native discovery is current"),)
        return OwnerAssessment(
            PROVIDER_KEY,
            inputs.root,
            effects=effects,
            dispositions=dispositions,
            inputs_fingerprint=prepared.observations,
            prepared=prepared,
            consent=inputs.consent,
        )

    @staticmethod
    def _effects(root: OperationRoot, prepared: PreparedVibeConfig, ids: tuple[str, ...]) -> tuple[PhysicalEffect, ...]:
        if not prepared.file.changed:
            return ()
        effects = []
        for observation in prepared.observations[1:-1]:
            before = presence_state(observation)
            if before.kind == "absent":
                effects.append(
                    PhysicalEffect(
                        PROVIDER_KEY,
                        "surface_repair",
                        root,
                        observation.name,
                        "create",
                        before,
                        FileState("directory", mode=0o755),
                        "Native config parent",
                        (OwnershipProof("managed_path", _VIBE_CONFIG_REL + "#skill_paths"),),
                        ("vibe",),
                        ids,
                    )
                )
        before = prepared.file.before
        effects.append(
            PhysicalEffect(
                PROVIDER_KEY,
                "surface_repair",
                root,
                prepared.file.path,
                "create" if before.kind == "absent" else "update",
                before,
                FileState("file", sha256=sha256(prepared.file.content).hexdigest(), mode=before.mode if before.mode is not None else 0o644),
                "Add shared skill discovery",
                (OwnershipProof("managed_path", _VIBE_CONFIG_REL + "#skill_paths"),),
                ("vibe",),
                ids,
            )
        )
        return tuple(effects)

    @contextmanager
    def recheck(self, assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
        """Refuse every write if any native input or parent changed."""
        prepared = assessment.prepared
        try:
            valid = isinstance(prepared, PreparedVibeConfig) and (
                all(observe_presence_path(assessment.root.path, old.name)[-1] == old for old in prepared.observations)
            )
        except (OSError, ValueError):
            valid = False
        yield () if valid else (Diagnostic("precondition_changed", PROVIDER_KEY, "error", "Native config inputs changed"),)

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        """Apply exact TOML-owner bytes; recheck even for direct protocol callers."""
        ids = tuple(effect.id for effect in assessment.effects)
        if not assessment.complete or not explicit_consent.automatic or explicit_consent != assessment.consent:
            return OwnerApplyResult(PROVIDER_KEY, skipped=ids, outcome="skipped")
        if not ids:
            return OwnerApplyResult(PROVIDER_KEY)
        with self.recheck(assessment) as diagnostics:
            if diagnostics:
                return OwnerApplyResult(PROVIDER_KEY, skipped=ids, diagnostics=diagnostics, outcome="precondition_changed")
            prepared = assessment.prepared
            if not isinstance(prepared, PreparedVibeConfig):
                raise TypeError("Expected native preparation")
            try:
                ensure_project_skill_path(assessment.root.path, prepared=prepared)
            except (OSError, ValueError) as exc:
                succeeded = tuple(e.id for e in assessment.effects if _directory_postcondition_holds(e))
                return OwnerApplyResult(
                    PROVIDER_KEY,
                    succeeded=succeeded,
                    failed=tuple(i for i in ids if i not in succeeded),
                    diagnostics=(Diagnostic("native_apply_failed", PROVIDER_KEY, "error", str(exc)),),
                    outcome="partial" if succeeded else "failed",
                )
        return OwnerApplyResult(PROVIDER_KEY, succeeded=ids)

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == ToolSurfaceKind.NATIVE_CONFIG)

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into the glue instance(s) for ``tool_key``.

        Only Vibe currently has verified native-config glue. Any other tool
        yields a research-gap instance so the gap is reported, not hidden.
        """
        if tool_key != _VIBE_TOOL_KEY:
            return [self._research_gap_instance(definition, tool_key)]
        path = project_root / _VIBE_CONFIG_REL
        return [
            SurfaceInstance(
                definition=definition,
                path=path,
                exists=_vibe_skill_path_present(path),
                file_hash=None,
                owner=tool_key,
            )
        ]

    @staticmethod
    def _research_gap_instance(definition: SurfaceDefinition, tool_key: str) -> SurfaceInstance:
        return SurfaceInstance(
            definition=definition,
            path=Path(_RESEARCH_GAP_SENTINEL),
            exists=False,
            file_hash=None,
            owner=tool_key,
        )

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Re-check whether the native-config glue entry is present."""
        if str(instance.path) == _RESEARCH_GAP_SENTINEL:
            return self._research_gap_status(instance)
        if _vibe_skill_path_present(instance.path):
            return SurfaceStatus(instance=instance, state=STATE_PRESENT)
        return self._missing_status(instance)

    @staticmethod
    def _research_gap_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_NOT_APPLICABLE,
            findings=(
                make_finding(
                    RESEARCH_GAP_SURFACE,
                    SEVERITY_INFO,
                    f"No known native-config glue for {instance.owner}.",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                ),
            ),
        )

    @staticmethod
    def _missing_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_MISSING,
            findings=(
                make_finding(
                    NATIVE_CONFIG_MISSING,
                    SEVERITY_ERROR,
                    f"Native-config glue missing for {instance.owner}: {instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        """Native-config glue is shared with user config; never auto-removed."""
        _ = instance
        return False

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        """Write the missing native-config glue via the owning helper."""
        actionable = [s for s in statuses if s.state == STATE_MISSING]
        skipped = tuple(_surface_id(s.instance) for s in statuses if s.state == STATE_NOT_APPLICABLE)
        if not actionable:
            return RepairResult(skipped=skipped, dry_run=dry_run)
        consent = ApplyConsent(automatic=True)
        assessment = self.assess(
            AssessmentInputs(OperationRoot("project", "project", project_root), consent=consent),
            actionable,
            selections=(SurfaceSelection("vibe", native_config_definition()),),
        )
        if not assessment.complete:
            return RepairResult(skipped=skipped, failed=tuple(d.message for d in assessment.diagnostics), dry_run=dry_run)
        if any(d.state == "not_applicable" for d in assessment.dispositions):
            return RepairResult(skipped=skipped + tuple(_surface_id(s.instance) for s in actionable), dry_run=dry_run)
        result = None if dry_run else self.apply(assessment, consent)
        failed = tuple(d.message for d in result.diagnostics) if result is not None else ()
        return RepairResult(
            repaired=() if failed else tuple(_surface_id(s.instance) for s in actionable),
            skipped=skipped,
            failed=failed,
            dry_run=dry_run,
        )


def _directory_postcondition_holds(effect: PhysicalEffect) -> bool:
    """A mkdir alone does not complete a create with a promised final mode."""
    if effect.after.kind != "directory":
        return False
    try:
        observed = observe_presence_path(effect.root.path, effect.path)[-1]
    except (OSError, ValueError):
        return False
    return bool(state_equivalent(presence_state(observed), effect.after))


def _vibe_skill_path_present(config_path: Path) -> bool:
    """Return whether ``.vibe/config.toml`` lists the shared skills path."""
    if not config_path.exists():
        return False
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not raw.strip():
        return False
    try:
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError:
        return False
    skill_paths = data.get("skill_paths")
    if isinstance(skill_paths, str):
        return bool(skill_paths == VIBE_SKILL_PATH)
    if isinstance(skill_paths, list):
        return VIBE_SKILL_PATH in [str(value) for value in skill_paths]
    return False


# ---------------------------------------------------------------------------
# Self-registration (fires at import time via providers._discovery)
# ---------------------------------------------------------------------------
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=NativeConfigProvider,
        definitions=(native_config_definition(),),
        kind_tokens={
            "native-config": ToolSurfaceKind.NATIVE_CONFIG,
            "native_config": ToolSurfaceKind.NATIVE_CONFIG,
        },
        order=30,
    )
)
