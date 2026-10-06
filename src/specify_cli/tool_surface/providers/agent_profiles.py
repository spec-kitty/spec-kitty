"""Native agent profile surface provider.

Wires :class:`~specify_cli.tool_surface.profiles.projection.ProfileProjector`
and :class:`~specify_cli.tool_surface.profiles.manifest.ProfileManifest` into a
reporting-layer provider for :data:`ToolSurfaceKind.AGENT_PROFILE`.

Behavioural contract (FR-012/013/014):

* Tools with a native named-agent primitive (Claude Code, Copilot/VS Code,
  Codex, Augment, Amazon Q) expand to one instance per projected profile and
  are repairable.  Amazon Q profiles are user-global (not manifest-tracked);
  their presence is checked via filesystem inspection.
* Tools assessed as having no native primitive (e.g. Windsurf, Cursor) expand
  to a single ``not_applicable`` instance whose finding is
  ``profile-projection-unsupported`` at severity ``info`` -- the top-level
  ``ok`` stays ``true`` because no ``error`` finding is produced.
* Tools that have not yet been formally assessed yield a ``research_gap``
  instance with finding ``research-gap-surface`` at severity ``info``.
* A projected file that is configured but missing is an ``error``
  (``native-agent-profile-missing``); a file whose content no longer matches the
  manifest hash is a ``warning`` (``native-agent-profile-drift``).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from charter.activation.pack_context import CharterPackConfigError
from ruamel.yaml.error import YAMLError

from specify_cli.core.agent_config import AgentConfigError, load_agent_config
from specify_cli.skills.manifest_store import fingerprint

from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    NATIVE_AGENT_PROFILE_DRIFT,
    NATIVE_AGENT_PROFILE_MISSING,
    PROFILE_PROJECTION_UNSUPPORTED,
    RESEARCH_GAP_SURFACE,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    make_finding,
)
from ..model import NativeAgentProfile, SurfaceDefinition, SurfaceInstance, SurfaceSelection
from ..operations import (
    ApplyConsent,
    AssessmentInputs,
    Diagnostic,
    Disposition,
    FileState,
    InputObservation,
    OperationRoot,
    OwnerApplyResult,
    OwnerAssessment,
    OwnershipProof,
    PhysicalEffect,
    coalesce_effects,
)
from ..profiles._paths import confined_path, observe_node, observe_tree
from ..profiles.amazon_q_renderer import FORMAT_AMAZON_Q_AGENT
from ..profiles.capability_matrix import HARNESS_CAPABILITY_MATRIX, is_research_gap
from ..profiles.manifest import ProfileManifest, hash_content, hash_file, manifest_path_for
from ..profiles.projection import PreparedProfileBatch, PreparedProjection, ProfileProjector
from ..profiles.renderers import get_renderer, native_name_violation
from ..repair import RepairResult, _is_init_upgrade_auto_repairable
from ..status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    STATE_UNSUPPORTED,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "agent_profiles"
_PATH_PATTERN = ".claude/agents/{profile_id}.md"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind agent-profile --fix"
# Sentinel paths used to route probe() without holding real filesystem paths.
_RESEARCH_GAP_SENTINEL = "<unsupported>"
_NOT_APPLICABLE_SENTINEL = "<not-applicable>"
# Synthetic instance path that routes ``probe`` to the projection diagnostics
# (the #1940 finding codes from :meth:`ProfileProjector.diagnose`). Carries no
# file on disk; it exists only to flow ``diagnose`` findings through the standard
# ``collect`` path into ``doctor tool-surfaces --json`` output.
_DIAGNOSTICS_SENTINEL = "<profile-diagnostics>"


def agent_profile_definition() -> SurfaceDefinition:
    """Return the built-in agent-profile :class:`SurfaceDefinition`."""
    return SurfaceDefinition(
        kind=ToolSurfaceKind.AGENT_PROFILE,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=_PATH_PATTERN,
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.USER_INVOKED,
        provider_key=PROVIDER_KEY,
        repair_hint=_REPAIR_HINT,
    )


def _build_projector(project_root: Path) -> ProfileProjector:
    try:
        return ProfileProjector.from_project(project_root)
    except (CharterPackConfigError, YAMLError, TypeError, KeyError) as exc:
        raise ValueError(f"Invalid required profile inputs: {exc}") from exc


class AgentProfilesProvider:
    """Provider for projected native agent profile surfaces."""

    provider_key = PROVIDER_KEY

    def __init__(
        self,
        projector: ProfileProjector | None = None,
        manifest: ProfileManifest | None = None,
    ) -> None:
        # ``projector``/``manifest`` are injectable for tests; in production they
        # are built per ``project_root`` inside ``expand``/``repair`` so the
        # provider stays usable as a stateless singleton in the service wiring.
        self._projector = projector
        self._manifest = manifest

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == ToolSurfaceKind.AGENT_PROFILE)

    def _projector_for(self, project_root: Path) -> ProfileProjector:
        return self._projector or _build_projector(project_root)

    def _manifest_for(self, project_root: Path) -> ProfileManifest:
        return self._manifest or ProfileManifest.load(project_root)

    def assess(
        self,
        inputs: AssessmentInputs,
        statuses: Sequence[SurfaceStatus],
        *,
        selections: tuple[SurfaceSelection, ...],
    ) -> OwnerAssessment:
        """Prepare the selected whole profile batch, including status-less pruning."""
        _ = statuses  # Inventory cannot supply status-less orphan ownership.
        return self._assess(inputs, selections)

    def _assess(
        self,
        inputs: AssessmentInputs,
        selections: tuple[SurfaceSelection, ...],
        only_paths: frozenset[Path] | None = None,
    ) -> OwnerAssessment:
        try:
            confined_path(manifest_path_for(inputs.root.path), inputs.root.path)
            manifest_before = observe_node(manifest_path_for(inputs.root.path))
            load_agent_config(inputs.root.path)
            batch = _ProfileBatch(inputs, selections, self._manifest_for(inputs.root.path))
            if observe_node(manifest_path_for(inputs.root.path)) != manifest_before:
                raise ValueError("Profile manifest changed while loading")
            eligible = batch.selected_tools()
            if not eligible:
                return batch.finish((), ())
            roots = _profile_input_roots(inputs.root.path)
            before = _input_states(roots)
            if any(state.kind == "symlink" and "agent_profiles" in path.parts for path, state in before):
                raise ValueError("Required profile source trees contain a symlink")
            projector = self._projector_for(inputs.root.path)
            for tool in eligible:
                batch.diagnostics.extend(Diagnostic(f.code, PROVIDER_KEY, f.severity, f.message) for f in projector.diagnose(tool, inputs.root.path))
            if any(d.severity == "error" for d in batch.diagnostics):
                return batch.finish((), ())
            projected = tuple(p for tool in eligible for p in projector.prepare(tool, inputs.root.path))
            sources = projector.source_paths()
            source_roots = tuple(sorted({p.parent for p in sources}))
            for source in sources:
                boundaries = [r for r in (inputs.root.path, *roots) if source != r and source.is_relative_to(r)]
                if not boundaries:
                    raise ValueError(f"Required profile source is outside observed input roots: {source}")
                confined_path(source, min(boundaries, key=lambda r: len(r.parts)))
                if observe_node(source).kind != "file":
                    raise ValueError(f"Required profile source unavailable: {source}")
            batch.prepare(projected, only_paths)
            assessment = batch.finish(projected, tuple(sorted(set(roots + source_roots + sources))))
            if before != _input_states(roots) or observe_node(manifest_path_for(inputs.root.path)) != manifest_before:
                raise ValueError("Profile inputs changed during preparation")
            return assessment
        except (OSError, ValueError, TypeError, KeyError, AgentConfigError, CharterPackConfigError, YAMLError) as exc:
            return OwnerAssessment(
                PROVIDER_KEY,
                inputs.root,
                complete=False,
                diagnostics=(Diagnostic("profile_input_invalid", PROVIDER_KEY, "error", str(exc)),),
                consent=inputs.consent,
            )

    @contextmanager
    def recheck(self, assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
        """Recheck every retained input before apply; this owner has no existing lock."""
        prepared = _prepared(assessment)
        try:
            current = _input_states(prepared.input_roots)
            planned_dirs = _planned_directory_creates(assessment.effects)
            for path, state in prepared.destinations:
                confined_path(path, assessment.root.path)
                observed = observe_node(path)
                if _sibling_created_planned_dir(state, observed, planned_dirs.get(path)):
                    observed = state
                # Sibling owners may create files in a retained parent during
                # the same guarded composition. Directory mtime is not an
                # ownership or confinement identity; kind/mode still are.
                if state.kind == "directory" and observed.kind == "directory":
                    observed = replace(observed, mtime_ns=state.mtime_ns)
                if observed != state:
                    raise ValueError(f"Profile destination changed: {path}")
            if current != prepared.input_states:
                raise ValueError("Profile source/config input root changed")
            diagnostics: tuple[Diagnostic, ...] = ()
        except (OSError, ValueError) as exc:
            diagnostics = (Diagnostic("precondition_changed", PROVIDER_KEY, "error", str(exc)),)
        yield diagnostics

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        """Apply retained bytes after a fresh whole-batch check; report actual effects."""
        ids = tuple(e.id for e in assessment.effects)
        if not assessment.complete or not explicit_consent.automatic or explicit_consent.overwrite_paths != assessment.consent.overwrite_paths:
            return OwnerApplyResult(PROVIDER_KEY, skipped=ids, outcome="skipped")
        if not ids:
            return OwnerApplyResult(PROVIDER_KEY, outcome="skipped")
        with self.recheck(assessment) as diagnostics:
            if diagnostics:
                return OwnerApplyResult(PROVIDER_KEY, skipped=ids, diagnostics=diagnostics, outcome="precondition_changed")
            return _apply_profile_batch(assessment)

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into one instance per projected profile for ``tool_key``.

        Uses :data:`~.profiles.capability_matrix.HARNESS_CAPABILITY_MATRIX` to
        distinguish ``not_applicable`` (assessed, no native primitive) from
        ``research_gap`` (not yet assessed) before attempting projection.

        For projectable tools a synthetic diagnostics instance is appended so
        that :meth:`ProfileProjector.diagnose`'s #1940 finding codes flow through
        the standard ``collect`` path and reach ``doctor tool-surfaces --json``.
        ``not_applicable`` harnesses (no native primitive) return early; tools
        with no projection emit only the research-gap instance.
        """
        record = HARNESS_CAPABILITY_MATRIX.get(tool_key)
        if record is not None and not record.has_native_agent_primitive:
            return [self._not_applicable_instance(definition, tool_key)]
        projector = self._projector_for(project_root)
        projected = projector.project(tool_key, project_root)
        if not projected:
            # Tool is assessed as capable but the projector returned nothing —
            # this occurs when no renderer is registered yet, which is a
            # research gap (the capability matrix may be ahead of the renderer
            # registry).
            if is_research_gap(tool_key):
                return [self._research_gap_instance(definition, tool_key)]
            return [self._research_gap_instance(definition, tool_key)]
        manifest = self._manifest_for(project_root)
        instances = [self._instance_from_projection(definition, native, manifest) for native in projected]
        instances.append(self._diagnostics_instance(definition, tool_key, project_root))
        return instances

    @staticmethod
    def _diagnostics_instance(
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> SurfaceInstance:
        # ``path`` carries ``project_root`` so ``probe`` can rebuild a projector
        # for the project overlay layer; ``surface_id`` marks it as the
        # diagnostics sentinel and ``owner`` carries the tool key.
        return SurfaceInstance(
            definition=definition,
            path=project_root,
            exists=False,
            file_hash=None,
            owner=tool_key,
            surface_id=f"{tool_key}.{definition.kind}.{_DIAGNOSTICS_SENTINEL}",
        )

    @staticmethod
    def _not_applicable_instance(definition: SurfaceDefinition, tool_key: str) -> SurfaceInstance:
        """Return a sentinel instance representing a ``not_applicable`` harness."""
        return SurfaceInstance(
            definition=definition,
            path=Path(_NOT_APPLICABLE_SENTINEL),
            exists=False,
            file_hash=None,
            owner=tool_key,
        )

    @staticmethod
    def _research_gap_instance(definition: SurfaceDefinition, tool_key: str) -> SurfaceInstance:
        return SurfaceInstance(
            definition=definition,
            path=Path(_RESEARCH_GAP_SENTINEL),
            exists=False,
            file_hash=None,
            owner=tool_key,
        )

    @staticmethod
    def _instance_from_projection(
        definition: SurfaceDefinition,
        native: NativeAgentProfile,
        manifest: ProfileManifest,
    ) -> SurfaceInstance:
        path = native.output_path
        return SurfaceInstance(
            definition=definition,
            path=path,
            exists=path.exists(),
            file_hash=manifest.get_hash(path),
            owner=native.tool_key,
        )

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Probe one projected profile (or a sentinel instance).

        The diagnostics sentinel delegates to :meth:`ProfileProjector.diagnose`
        so the #1940 finding codes are surfaced; the not-applicable and
        research-gap sentinels and normal projected files keep their existing
        semantics.
        """
        if self._is_diagnostics_instance(instance):
            return self._diagnostics_status(instance)
        path_str = str(instance.path)
        if path_str == _NOT_APPLICABLE_SENTINEL:
            return self._not_applicable_status(instance)
        if path_str == _RESEARCH_GAP_SENTINEL:
            return self._research_gap_status(instance)
        if not instance.path.exists():
            return self._missing_status(instance)
        if instance.file_hash is not None and hash_file(instance.path) != instance.file_hash:
            return self._drift_status(instance)
        return SurfaceStatus(instance=instance, state=STATE_PRESENT)

    @staticmethod
    def _not_applicable_status(instance: SurfaceInstance) -> SurfaceStatus:
        """Build a ``not_applicable`` status for an assessed non-capable harness."""
        record = HARNESS_CAPABILITY_MATRIX.get(instance.owner)
        reason = record.reason if record is not None else "No native agent primitive."
        return SurfaceStatus(
            instance=instance,
            state=STATE_NOT_APPLICABLE,
            findings=(
                make_finding(
                    PROFILE_PROJECTION_UNSUPPORTED,
                    SEVERITY_INFO,
                    (f"{instance.owner} does not support native agent profile projection; profiles are exposed through other surfaces instead. Reason: {reason}"),
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    details={"status": "not_applicable", "reason": reason},
                ),
            ),
        )

    @staticmethod
    def _is_diagnostics_instance(instance: SurfaceInstance) -> bool:
        surface_id = instance.surface_id
        if surface_id is None:
            return False
        return bool(surface_id.endswith(_DIAGNOSTICS_SENTINEL))

    def _diagnostics_status(self, instance: SurfaceInstance) -> SurfaceStatus:
        # ``path`` is the ``project_root`` recorded at expand time (see
        # ``_diagnostics_instance``); rebuild the projector for it so the project
        # overlay layer participates in diagnosis.
        project_root = instance.path
        projector = self._projector_for(project_root)
        findings = tuple(projector.diagnose(instance.owner, project_root))
        return SurfaceStatus(
            instance=instance,
            state=STATE_NOT_APPLICABLE,
            findings=findings,
        )

    @staticmethod
    def _research_gap_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_NOT_APPLICABLE,
            findings=(
                make_finding(
                    RESEARCH_GAP_SURFACE,
                    SEVERITY_INFO,
                    (f"No verified native agent-profile primitive for {instance.owner}; profiles are not projected."),
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    details={"status": "research_gap"},
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
                    NATIVE_AGENT_PROFILE_MISSING,
                    SEVERITY_ERROR,
                    f"Native agent profile is missing: {instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
        )

    @staticmethod
    def _drift_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_DRIFTED,
            findings=(
                make_finding(
                    NATIVE_AGENT_PROFILE_DRIFT,
                    SEVERITY_WARNING,
                    f"Native agent profile drifted from manifest hash: {instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
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
        """Re-project missing/drifted profiles and prune de-activated orphans.

        Beyond writing missing/drifted files, the ``--fix`` path reconciles the
        managed surface with the current **activation-admitted** projection set:
        any manifest-tracked, project-local file whose profile is no longer
        admitted (de-activated or removed) is deleted and its manifest entry
        dropped (R8). Pruning runs even when nothing is missing/drifted, since a
        de-activated profile produces no status at all.
        """
        actionable = [s for s in statuses if s.state in (STATE_MISSING, STATE_DRIFTED)]
        skipped = tuple(_surface_id(s.instance) for s in statuses if s.state in (STATE_NOT_APPLICABLE, STATE_UNSUPPORTED))
        if dry_run:
            return RepairResult(
                repaired=tuple(_surface_id(s.instance) for s in actionable),
                skipped=skipped,
                dry_run=True,
            )
        # Explicit doctor Q repair retains its existing user-global writer.
        q_statuses = [s for s in actionable if s.instance.owner in {"q", "amazon-q", FORMAT_AMAZON_Q_AGENT}]
        repaired: list[str] = []
        failed: list[str] = []
        if q_statuses:
            projector = self._projector_for(project_root)
            index = self._project_index(projector, project_root, q_statuses)
            manifest = self._manifest_for(project_root)
            for status in q_statuses:
                self._repair_one(status, projector, index, manifest, repaired, failed)
        selections = tuple(dict.fromkeys(SurfaceSelection(s.instance.owner, s.instance.definition) for s in statuses))
        consent = ApplyConsent(
            automatic=True,
            overwrite_paths=tuple(
                sorted(s.instance.path.relative_to(project_root).as_posix() for s in actionable if s.state == STATE_DRIFTED and s not in q_statuses)
            ),
        )
        assessment = self._assess(
            AssessmentInputs(OperationRoot("project", "project", project_root), consent=consent),
            selections,
            frozenset(s.instance.path for s in actionable if s not in q_statuses),
        )
        result = self.apply(assessment, consent)
        succeeded = {e.destination for e in assessment.effects if e.id in result.succeeded}
        repaired.extend(_surface_id(s.instance) for s in actionable if s.instance.path in succeeded)
        failed.extend(d.message for d in assessment.diagnostics + result.diagnostics if d.severity == "error")
        failed.extend(f"profile drift: {d.path}" for d in assessment.dispositions if d.state == "consent_required")
        return RepairResult(repaired=tuple(repaired), failed=tuple(failed), skipped=skipped)

    @staticmethod
    def _project_index(
        projector: ProfileProjector,
        project_root: Path,
        actionable: Sequence[SurfaceStatus],
    ) -> dict[str, NativeAgentProfile]:
        """Map output-path -> NativeAgentProfile for every affected tool key."""
        index: dict[str, NativeAgentProfile] = {}
        for tool_key in sorted({s.instance.owner for s in actionable}):
            for native in projector.project(tool_key, project_root):
                index[str(native.output_path)] = native
        return index

    @staticmethod
    def _repair_one(
        status: SurfaceStatus,
        projector: ProfileProjector,
        index: dict[str, NativeAgentProfile],
        manifest: ProfileManifest,
        repaired: list[str],
        failed: list[str],
    ) -> None:
        from dataclasses import replace

        instance = status.instance
        surface_id = _surface_id(instance)
        native = index.get(str(instance.path))
        if native is None:
            failed.append(f"{surface_id}: no projection for {instance.path}")
            return
        body = projector.render(native.tool_key, native.profile_urn)
        if body is None:
            failed.append(f"{surface_id}: unable to render {native.profile_urn}")
            return
        try:
            instance.path.parent.mkdir(parents=True, exist_ok=True)
            instance.path.write_text(body, encoding="utf-8")
        except OSError as exc:  # surfaced as a failure, never swallowed
            failed.append(f"{surface_id}: {exc}")
            return
        # User-global renderers (e.g. Amazon Q) write outside the project tree
        # and must NOT be recorded in the project manifest.
        if native.format != FORMAT_AMAZON_Q_AGENT:
            manifest.record(replace(native, file_hash=hash_content(body)))
        repaired.append(surface_id)


@dataclass(frozen=True)
class _ProfileName:
    profile_id: str


def _prepared(assessment: OwnerAssessment) -> PreparedProfileBatch:
    prepared = assessment.prepared
    if not isinstance(prepared, PreparedProfileBatch):
        raise ValueError("Assessment does not contain prepared profiles")
    return prepared


def _input_states(roots: tuple[Path, ...]) -> tuple[tuple[Path, FileState], ...]:
    return tuple(item for root in roots for item in observe_tree(root))


def _profile_input_roots(root: Path) -> tuple[Path, ...]:
    from charter.activation.pack_context import PackContext, resolve_charter_yaml_pointer
    from charter.drg import ArtifactKind, resolve_org_roots
    from charter.pack_paths import built_in_dir
    from ruamel.yaml import YAML

    PackContext.from_config(root)
    package = built_in_dir(ArtifactKind.AGENT_PROFILE)
    if not package.is_dir():
        raise ValueError(f"Required built-in profile sources unavailable: {package}")
    org_roots = tuple(resolve_org_roots(root))
    for org in org_roots:
        if observe_node(org).kind != "directory":
            raise ValueError(f"Required org profile root unavailable: {org}")
    paths = [package, Path(__file__).parent.parent / "profiles", *org_roots]
    paths.extend(root / p for p in (".kittify/config.yaml", ".kittify/charter", ".kittify/agent_profiles", ".kittify/doctrine", "doctrine", "pyproject.toml"))
    paths.append(manifest_path_for(root))
    config = root / ".kittify/config.yaml"
    if observe_node(config).kind == "file":
        data = YAML(typ="safe").load(config.read_text(encoding="utf-8")) or {}
        pointer = resolve_charter_yaml_pointer(root, data)
        if pointer is not None:
            paths.append(pointer)
    return tuple(sorted(set(paths)))


class _ProfileBatch:
    """Owner-local mutable preparation; only frozen values leave this builder."""

    def __init__(self, inputs: AssessmentInputs, selections: tuple[SurfaceSelection, ...], manifest: ProfileManifest):
        self.inputs = inputs
        self.selections = selections
        self.manifest = ProfileManifest(manifest.manifest_path)
        self.original = tuple(manifest.all_entries())
        for entry in self.original:
            self.manifest.record(entry)
        self.effects: list[PhysicalEffect] = []
        self.dispositions: list[Disposition] = []
        self.diagnostics: list[Diagnostic] = []
        self.contents: dict[Path, bytes] = {}
        self.destinations: dict[Path, FileState] = {}
        self.tools: tuple[str, ...] = ()

    def selected_tools(self) -> tuple[str, ...]:
        selected = []
        for selection in self.selections:
            status = SurfaceStatus(SurfaceInstance(selection.definition, self.inputs.root.path, False, None, selection.tool_key), STATE_MISSING)
            renderer = get_renderer(selection.tool_key)
            if not _is_init_upgrade_auto_repairable(status) or renderer is None:
                self.dispositions.append(
                    Disposition(PROVIDER_KEY, self.inputs.root.root_id, None, "not_applicable", f"Profile policy excludes {selection.tool_key}")
                )
            else:
                selected.append(selection.tool_key)
        self.tools = tuple(sorted(set(selected)))
        return self.tools

    def preserve(self, path: Path, reason: str, *, drift: bool = False) -> None:
        relative: str | None
        try:
            relative = path.relative_to(self.inputs.root.path).as_posix()
            if ".." in Path(relative).parts:
                relative = None
        except ValueError:
            relative = None
        self.dispositions.append(Disposition(PROVIDER_KEY, self.inputs.root.root_id, relative, "consent_required" if drift else "preserve", reason))

    def observe(self, path: Path) -> FileState:
        confined_path(path, self.inputs.root.path)
        parent = path.parent
        while parent != self.inputs.root.path:
            if parent not in self.destinations:
                self.destinations[parent] = observe_node(parent)
            parent = parent.parent
        if path not in self.destinations:
            self.destinations[path] = observe_node(path)
        return self.destinations[path]

    def effect(self, path: Path, after: FileState, owners: tuple[str, ...], proof: OwnershipProof, reason: str) -> None:
        before = self.observe(path)
        if before.kind == "absent":
            action = "create"
        elif after.kind == "absent":
            action = "delete"
        elif before.sha256 != after.sha256:
            action = "update"
        else:
            return
        self.effects.append(
            PhysicalEffect(
                PROVIDER_KEY,
                "surface_repair",
                self.inputs.root,
                path.relative_to(self.inputs.root.path).as_posix(),
                action,
                before,
                after,
                reason,
                (proof,),
                owners,
                tuple(_surface_id(SurfaceInstance(agent_profile_definition(), path, False, None, owner)) for owner in owners),
            )
        )

    def prepare(self, projected: tuple[PreparedProjection, ...], only_paths: frozenset[Path] | None) -> None:
        grouped: dict[Path, list[PreparedProjection]] = {}
        for projection in projected:
            grouped.setdefault(projection.native.output_path, []).append(projection)
        for path, group in grouped.items():
            if len({p.content for p in group}) != 1:
                raise ValueError(f"Conflicting profile projections: {path}")
            self.prepare_output(group, only_paths)
        for entry in self.original:
            if entry.output_path not in grouped and entry.tool_key in self.tools:
                self.prepare_orphan(entry)
        self.prepare_manifest()
        self.prepare_parents()

    def prepare_output(self, group: list[PreparedProjection], only_paths: frozenset[Path] | None) -> None:
        item = group[0]
        path = item.native.output_path
        try:
            state = self.observe(path)
        except ValueError as exc:
            self.preserve(path, str(exc))
            return
        if only_paths is not None and path not in only_paths:
            return
        original = next((e for e in self.original if e.output_path == path), None)
        proof = OwnershipProof("managed_path", f"profile renderer:{item.native.tool_key}:{item.native.profile_urn}")
        if state.kind not in {"file", "absent"}:
            self.preserve(path, "Profile destination is a custom link or unsupported node")
            return
        if original is not None and not _valid_entry(original, self.inputs.root.path):
            self.preserve(path, "Profile manifest identity does not authorize this path")
            return
        if state.kind == "file":
            if original is None and state.sha256 != item.native.file_hash:
                self.preserve(path, "Unknown profile content; no adoption authority")
                return
            if original is not None and state.sha256 != original.file_hash:
                relative = path.relative_to(self.inputs.root.path).as_posix()
                if relative not in self.inputs.consent.overwrite_paths:
                    self.preserve(path, "Managed profile drift requires exact-path consent", drift=True)
                    return
            proof = OwnershipProof("manifest" if original else "canonical_content", f"{self.manifest.manifest_path.name}:{path.relative_to(self.inputs.root.path)}")
        owners = tuple(p.native.tool_key for p in group)
        mode = state.mode if state.kind == "file" else 0o644
        after = FileState("file", sha256=item.native.file_hash, mode=mode)
        if state.kind == "absent" or state.sha256 != after.sha256:
            self.contents[path] = item.content
            self.effect(path, after, owners, proof, "Install prepared native profile")
        else:
            self.dispositions.append(
                Disposition(PROVIDER_KEY, self.inputs.root.root_id, path.relative_to(self.inputs.root.path).as_posix(), "unchanged", "Native profile bytes match")
            )
        # A shared alias must not replace a retained logical manifest owner.
        native = replace(item.native, tool_key=original.tool_key) if original and original.tool_key not in owners else item.native
        self.manifest.record(native)

    def prepare_orphan(self, entry: NativeAgentProfile) -> None:
        path = entry.output_path
        if not _valid_entry(entry, self.inputs.root.path):
            self.preserve(path, "Unconfined or unsupported orphan manifest identity")
            return
        try:
            state = self.observe(path)
        except ValueError as exc:
            self.preserve(path, str(exc))
            return
        if state.kind == "absent":
            self.manifest.remove(path)
        elif state.kind == "file" and state.sha256 == entry.file_hash:
            self.effect(
                path,
                FileState("absent"),
                self.entry_owners(entry),
                OwnershipProof("manifest", f"{self.manifest.manifest_path.name}:{entry.profile_urn}"),
                "Prune unchanged deactivated profile",
            )
            self.manifest.remove(path)
        else:
            self.preserve(path, "Orphan drift or custom link; retain ownership record", drift=True)

    def entry_owners(self, entry: NativeAgentProfile) -> tuple[str, ...]:
        """Recover selected aliases through the existing renderer/path authority."""
        return tuple(tool for tool in self.tools if _valid_entry(replace(entry, tool_key=tool), self.inputs.root.path))

    def prepare_manifest(self) -> None:
        if tuple(self.manifest.all_entries()) == self.original:
            return
        path = self.manifest.manifest_path
        state = self.observe(path)
        content = self.manifest.render_bytes()
        self.contents[path] = content
        entries = self.original + tuple(self.manifest.all_entries())
        owners = {e.tool_key for e in entries if e.format != FORMAT_AMAZON_Q_AGENT}
        owners.update(tool for entry in entries for tool in self.entry_owners(entry))
        self.effect(
            path,
            FileState("file", sha256=str(fingerprint(content)), mode=state.mode if state.kind == "file" else 0o644),
            tuple(sorted(owners)) or self.tools,
            OwnershipProof("managed_path", ".kittify/agent_profiles_manifest.json schema 1"),
            "Persist exact prepared profile ownership",
        )

    def prepare_parents(self) -> None:
        children = tuple(self.effects)
        for child in children:
            if child.action == "delete":
                continue
            parent = child.destination.parent
            while parent != self.inputs.root.path:
                if self.observe(parent).kind == "absent":
                    self.effect(parent, FileState("directory", mode=0o755), child.logical_owners, child.ownership[0], "Create profile supporting directory")
                parent = parent.parent

    def finish(self, projections: tuple[PreparedProjection, ...], roots: tuple[Path, ...]) -> OwnerAssessment:
        complete = not any(d.severity == "error" for d in self.diagnostics)
        self.observe(self.manifest.manifest_path)
        states = _input_states(roots)
        prepared = PreparedProfileBatch(
            projections, tuple(sorted(self.contents.items())), self.original, roots, states, tuple(sorted(self.destinations.items())), self.selections
        )
        return OwnerAssessment(
            PROVIDER_KEY,
            self.inputs.root,
            coalesce_effects(tuple(self.effects)) if complete else (),
            tuple(self.dispositions),
            tuple(self.diagnostics),
            complete,
            (InputObservation("profile_inputs", states),),
            prepared,
            self.inputs.consent,
        )


def _valid_entry(entry: NativeAgentProfile, root: Path) -> bool:
    if entry.format == FORMAT_AMAZON_Q_AGENT or entry.tool_key in {"q", "amazon-q", FORMAT_AMAZON_Q_AGENT}:
        return False
    if not entry.profile_urn.startswith("agent_profile:"):
        return False
    name = entry.profile_urn.split(":", 1)[1]
    renderer = get_renderer(entry.tool_key)
    if native_name_violation(name) or renderer is None or renderer.format_key != entry.format:
        return False
    return bool(renderer.output_path(entry.tool_key, _ProfileName(name), root) == entry.output_path)


def _planned_directory_creates(effects: tuple[PhysicalEffect, ...]) -> dict[Path, FileState]:
    """Planned ``create`` directory effects, keyed by destination."""
    return {e.destination: e.after for e in effects if e.action == "create" and e.after.kind == "directory"}


def _sibling_created_planned_dir(before: FileState, observed: FileState, planned: FileState | None) -> bool:
    """True when a sibling owner made the identical planned directory first (#4275).

    Only the exact shape is accepted: planned absent -> directory, now an existing
    directory with the planned mode.
    """
    return planned is not None and planned.kind == "directory" and before.kind == "absent" and observed.kind == "directory" and observed.mode == planned.mode


def _write_profile_effect(effect: PhysicalEffect, content: bytes | None) -> None:
    from specify_cli.core.no_follow import chmod_fd

    path = effect.destination
    confined_path(path, effect.root.path)
    observed = observe_node(path)
    if effect.action == "create" and _sibling_created_planned_dir(effect.before, observed, effect.after):
        return  # a sibling owner already created the identical shared directory (#4275)
    if observed != effect.before:
        raise FileExistsError(f"Prepared profile destination changed before write: {path}")
    if effect.after.kind == "directory":
        path.mkdir(mode=effect.after.mode or 0o755)
        path.chmod(effect.after.mode or 0o755)
    elif effect.action == "delete":
        path.unlink()
    else:
        assert content is not None
        if path == manifest_path_for(effect.root.path):
            ProfileManifest(path).save(content, exclusive=effect.action == "create")
            if effect.action == "create":
                path.chmod(effect.after.mode or 0o644)
        else:
            with path.open("xb" if effect.action == "create" else "wb") as stream:
                stream.write(content)
                if effect.action == "create":
                    chmod_fd(stream.fileno(), path, effect.after.mode or 0o644)


def _apply_profile_batch(assessment: OwnerAssessment) -> OwnerApplyResult:
    prepared = _prepared(assessment)
    contents = dict(prepared.contents)
    succeeded: list[str] = []
    failed: list[str] = []
    diagnostics: list[Diagnostic] = []
    manifest_path = manifest_path_for(assessment.root.path)
    ordered = sorted(assessment.effects, key=lambda e: (e.destination == manifest_path, e.after.kind != "directory", len(e.destination.parts), e.path))
    for effect in ordered:
        if effect.destination == manifest_path and failed:
            failed.append(effect.id)
            diagnostics.append(Diagnostic("profile_manifest_not_applied", PROVIDER_KEY, "error", "Partial file failure; original ownership records retained"))
            continue
        try:
            _write_profile_effect(effect, contents.get(effect.destination))
        except (OSError, ValueError) as exc:
            # Confinement/node refusals can occur after earlier effects succeeded.
            failed.append(effect.id)
            diagnostics.append(Diagnostic("profile_apply_failed", PROVIDER_KEY, "error", f"{effect.path}: {exc}"))
        else:
            succeeded.append(effect.id)
    outcome = "partial" if failed and succeeded else "failed" if failed else "applied"
    return OwnerApplyResult(PROVIDER_KEY, tuple(succeeded), tuple(failed), diagnostics=tuple(diagnostics), outcome=outcome)


# Self-registration (fires at import time via providers._discovery).
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=AgentProfilesProvider,
        definitions=(agent_profile_definition(),),
        kind_tokens={"agent-profile": ToolSurfaceKind.AGENT_PROFILE},
        order=50,
    )
)
