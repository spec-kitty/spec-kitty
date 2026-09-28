"""Session-presence surface provider.

Wraps :mod:`specify_cli.session_presence.writers.registry` as a reporting-layer
:class:`~specify_cli.tool_surface.providers.protocol.ReportingSurfaceProvider`.

``session_presence`` is a *provider name*, not a :class:`ToolSurfaceKind`. The
provider expands a tool's session-presence writer into one
:class:`SurfaceInstance` per managed artefact, tagging each with the distinct
:class:`ToolSurfaceKind` it represents:

* :data:`ToolSurfaceKind.CONTEXT_FILE` -- always-on orientation files
  (``.claude/CLAUDE.md``, ``AGENTS.md``, ``GEMINI.md``, copilot instructions).
* :data:`ToolSurfaceKind.RULE` -- path/glob-activated rules and steering files
  (``.cursor/rules/spec-kitty.mdc``, ``.kiro/steering/spec-kitty.md``).
* :data:`ToolSurfaceKind.HOOK` -- tool lifecycle event handlers
  (``.claude/settings.json`` ``SessionStart`` / ``Stop`` entries).

The provider never reimplements writer logic: ``expand`` asks the writer which
paths it manages, ``probe`` checks them, and ``repair`` delegates back to the
writer via :class:`SessionPresenceManager`. Harnesses with a ``NullWriter`` (no
known orientation mechanism) yield a single ``research-gap-surface`` finding --
never a hard failure and never a silent OK.
"""

from __future__ import annotations

from collections.abc import Sequence, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256  # noqa: TID251 -- exact physical file bytes, not doctrine hashing.
from pathlib import Path
import os

from specify_cli.core.agent_config import load_agent_config, AgentConfigError
from specify_cli.core.no_follow import fd_relative_dir_ops_supported

from specify_cli.session_presence.content import (
    SECTION_CLOSE,
    SECTION_OPEN,
    SessionPresenceContent,
)
from specify_cli.session_presence.hooks.claude_code_hook import (
    SESSION_START_EVENT,
    STOP_EVENT,
    ClaudeCodeHookRegistrar,
    SettingsNotDecodableError,
)
from specify_cli.session_presence.writers.claude_code import (
    SESSION_START_CMD,
    SESSION_STOP_CMD,
    ClaudeCodeWriter,
)
from specify_cli.session_presence.writers.markdown_rules import (
    MarkdownRulesWriter,
    PreparedPresenceFile,
    observe_presence_path,
    presence_state,
    _presence_parent,
    _walk_confined_parent,
)
from specify_cli.session_presence.writers.null_writer import NullWriter
from specify_cli.session_presence.writers.registry import get_writer

from ..enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from ..findings import (
    CONTEXT_FILE_MISSING,
    RESEARCH_GAP_SURFACE,
    SESSION_PRESENCE_INCOMPLETE,
    SESSION_PRESENCE_UNDECODABLE,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STALE_GENERATED_SURFACE,
    make_finding,
)
from ..model import SurfaceDefinition, SurfaceInstance, SurfaceSelection
from ..operations import (
    AssessmentInputs,
    ApplyConsent,
    Diagnostic,
    Disposition,
    FileState,
    InputObservation,
    OperationRoot,
    OwnerAssessment,
    OwnerApplyResult,
    OwnershipProof,
    PhysicalEffect,
    coalesce_effects,
)
from ..repair import RepairResult
from ..status import (
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    STATE_STALE,
    STATE_UNSAFE,
    SurfaceStatus,
    _surface_id,
)
from ._registry import SurfaceProviderRegistry, SurfaceRegistration

PROVIDER_KEY = "session_presence"
_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind context_file --fix"
_HOOK_REPAIR_HINT = "spec-kitty doctor tool-surfaces --kind hook --fix"
_RESEARCH_GAP_SENTINEL = "<unsupported>"

# The provider expands into these distinct kinds. ``session_presence`` itself is
# a provider name and is deliberately absent from this set.
_SESSION_PRESENCE_KINDS = frozenset(
    {
        ToolSurfaceKind.CONTEXT_FILE,
        ToolSurfaceKind.HOOK,
        ToolSurfaceKind.RULE,
    }
)

# Path fragments that mark a writer's target as a path/glob-activated *rule*
# rather than an always-on context file. Anything else a MarkdownRulesWriter
# manages is treated as a CONTEXT_FILE.
_RULE_PATH_MARKERS = ("/rules/", "/steering/", ".mdc")


@dataclass(frozen=True)
class PreparedSessionBatch:
    """Retained complete writer members and every source/destination observation."""

    files: tuple[tuple[str, PreparedPresenceFile], ...]
    observations: tuple[InputObservation, ...]
    content: SessionPresenceContent | None

    @property
    def execution_artifacts(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(dict.fromkeys(artifact for _tool, member in self.files for artifact in member.execution_artifacts))


def _definition_for(kind: ToolSurfaceKind) -> SurfaceDefinition:
    """Return the session-presence :class:`SurfaceDefinition` for ``kind``."""
    activation = ActivationMode.EVENT if kind == ToolSurfaceKind.HOOK else ActivationMode.GLOB if kind == ToolSurfaceKind.RULE else ActivationMode.ALWAYS
    repair_hint = _HOOK_REPAIR_HINT if kind == ToolSurfaceKind.HOOK else _REPAIR_HINT
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern="<session-presence>",
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=activation,
        provider_key=PROVIDER_KEY,
        repair_hint=repair_hint,
    )


def context_file_definition() -> SurfaceDefinition:
    """Return the built-in ``context_file`` :class:`SurfaceDefinition`."""
    return _definition_for(ToolSurfaceKind.CONTEXT_FILE)


def hook_definition() -> SurfaceDefinition:
    """Return the built-in ``hook`` :class:`SurfaceDefinition`."""
    return _definition_for(ToolSurfaceKind.HOOK)


def rule_definition() -> SurfaceDefinition:
    """Return the built-in ``rule`` :class:`SurfaceDefinition`."""
    return _definition_for(ToolSurfaceKind.RULE)


def _markdown_kind(rules_path: str) -> ToolSurfaceKind:
    """Classify a MarkdownRulesWriter target as ``RULE`` or ``CONTEXT_FILE``."""
    lowered = rules_path.lower()
    if any(marker in lowered for marker in _RULE_PATH_MARKERS):
        return ToolSurfaceKind.RULE
    return ToolSurfaceKind.CONTEXT_FILE


class SessionPresenceProvider:
    """Provider for session-presence surfaces (context files, hooks, rules)."""

    provider_key = PROVIDER_KEY

    def assess(
        self,
        inputs: AssessmentInputs,
        statuses: Sequence[SurfaceStatus],
        *,
        selections: tuple[SurfaceSelection, ...],
    ) -> OwnerAssessment:
        """Assess complete selected writer batches without network or persistence."""
        try:
            return self._prepare(inputs, statuses, selections)
        except (OSError, ValueError, AgentConfigError, TypeError, AttributeError) as exc:
            return OwnerAssessment(
                PROVIDER_KEY,
                inputs.root,
                complete=False,
                diagnostics=(Diagnostic("session_input_invalid", PROVIDER_KEY, "error", str(exc)),),
                consent=inputs.consent,
            )

    def _prepare(
        self,
        inputs: AssessmentInputs,
        statuses: Sequence[SurfaceStatus],
        selections: tuple[SurfaceSelection, ...],
    ) -> OwnerAssessment:
        root = inputs.root.path
        observations = list(observe_presence_path(root, ".kittify/config.yaml"))
        if presence_state(observations[-1]).kind not in ("file", "absent"):
            raise ValueError("Agent config is not a regular file")
        configured = None
        if presence_state(observations[-1]).kind == "file":
            configured = set(load_agent_config(root).available)
        content = inputs.projected if isinstance(inputs.projected, SessionPresenceContent) else None
        if inputs.projected is not None and not isinstance(inputs.projected, SessionPresenceContent):
            raise ValueError("Session assessment requires supplied SessionPresenceContent")
        files: list[tuple[str, PreparedPresenceFile]] = []
        effects: list[PhysicalEffect] = []
        dispositions: list[Disposition] = []
        eligible_selections = tuple(
            s for s in selections if s.definition.activation_mode != ActivationMode.DISABLED and s.definition.required_policy == RequiredPolicy.REPAIRABLE_REQUIRED
        )
        selected = sorted({s.tool_key for s in eligible_selections})
        if not selected:
            dispositions.append(Disposition(PROVIDER_KEY, inputs.root.root_id, None, "not_applicable", "No automatically repairable presence selection"))
        for tool in selected:
            writer = get_writer(tool)
            kinds = {s.definition.kind for s in eligible_selections if s.tool_key == tool}
            managed = _managed_surfaces(writer, root)
            applicable = isinstance(writer, MarkdownRulesWriter) and (configured is None or tool in configured) and any(kind in kinds for _, kind in managed)
            if applicable and isinstance(writer, MarkdownRulesWriter):
                check = writer.check_dir or str(Path(writer.rules_path).parent)
                observations.extend(observe_presence_path(root, check))
                applicable = writer.can_write(root)
            if not applicable or not isinstance(writer, MarkdownRulesWriter):
                dispositions.append(Disposition(PROVIDER_KEY, inputs.root.root_id, None, "not_applicable", f"No enabled selected writable presence for {tool}"))
                continue
            if content is None:
                content = _orientation_content(root)
            # Observe every sibling before invoking either format-aware renderer.
            for path, _kind in managed:
                observations.extend(observe_presence_path(root, path.relative_to(root).as_posix()))
            members = writer.prepare_batch(root, content) if isinstance(writer, ClaudeCodeWriter) else (writer.prepare(root, content),)
            ids = tuple(_surface_id(s.instance) for s in statuses if s.instance.owner == tool)
            for member in members:
                files.append((tool, member))
                if member.changed:
                    effects.extend(_session_effects(inputs.root, tool, member, tuple(observations), ids))
                else:
                    dispositions.append(Disposition(PROVIDER_KEY, inputs.root.root_id, member.path, member.disposition, member.reason))
        unique: dict[str, InputObservation] = {}
        for observation in observations:
            previous = unique.setdefault(observation.name, observation)
            if previous != observation:
                raise ValueError(f"Session input changed during preparation: {observation.name}")
        retained = tuple(unique.values())
        return OwnerAssessment(
            PROVIDER_KEY,
            inputs.root,
            effects=coalesce_effects(tuple(effects)),
            dispositions=tuple(dispositions),
            inputs_fingerprint=retained,
            prepared=PreparedSessionBatch(tuple(files), retained, content),
            consent=inputs.consent,
        )

    @contextmanager
    def recheck(self, assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
        """Validate the whole batch before its first write, including config."""
        try:
            for old in assessment.inputs_fingerprint:
                current = observe_presence_path(assessment.root.path, old.name)[-1]
                if old != current:
                    raise ValueError(f"Session input changed: {old.name}")
            diagnostics: tuple[Diagnostic, ...] = ()
        except (OSError, ValueError) as exc:
            diagnostics = (Diagnostic("precondition_changed", PROVIDER_KEY, "error", str(exc)),)
        yield diagnostics

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        """Apply retained members via their original writers after whole-batch recheck."""
        ids = tuple(e.id for e in assessment.effects)
        if not assessment.complete or not explicit_consent.automatic or explicit_consent != assessment.consent:
            return OwnerApplyResult(PROVIDER_KEY, skipped=ids, outcome="skipped")
        if not ids:
            return OwnerApplyResult(PROVIDER_KEY)
        with self.recheck(assessment) as diagnostics:
            if diagnostics:
                return OwnerApplyResult(PROVIDER_KEY, skipped=ids, diagnostics=diagnostics, outcome="precondition_changed")
            return self._apply_prepared(assessment)

    @staticmethod
    def _apply_prepared(assessment: OwnerAssessment) -> OwnerApplyResult:
        prepared = assessment.prepared
        if not isinstance(prepared, PreparedSessionBatch):
            raise TypeError("Expected session preparation")
        members = {item.path: (tool, item) for tool, item in prepared.files}
        effects = sorted(assessment.effects, key=lambda e: (e.after.kind != "directory", len(Path(e.path).parts), e.path))
        succeeded: list[str] = []
        for index, effect in enumerate(effects):
            try:
                if effect.after.kind == "directory":
                    relative = Path(effect.path)
                    root = assessment.root.path
                    if fd_relative_dir_ops_supported():
                        with _presence_parent(root, relative.parent, create=False) as fd:
                            os.mkdir(relative.name, 0o755, dir_fd=fd)
                        with _presence_parent(root, relative, create=False) as fd:
                            os.fchmod(fd, 0o755)
                    else:
                        # Windows: no dir_fd support, so fall back to the
                        # path-based confined walk (mirrors
                        # markdown_rules._windows_atomic_write). Every
                        # component up to and including the parent must
                        # already exist and be a real (non-symlink)
                        # directory -- this call never creates it.
                        parent = _walk_confined_parent(root, relative.parent, create=False)
                        target_dir = parent / relative.name
                        if target_dir.is_symlink():
                            raise ValueError(f"Refusing unowned symlink: {target_dir}")
                        target_dir.mkdir(mode=0o755)
                        if target_dir.is_symlink():
                            raise ValueError(f"Refusing unowned symlink: {target_dir}")
                        target_dir.chmod(0o755)
                else:
                    tool, member = members[effect.path]
                    writer = get_writer(tool)
                    if not isinstance(writer, MarkdownRulesWriter):
                        raise ValueError("Selected writer is no longer available")
                    writer.apply_prepared(assessment.root.path, member)
                succeeded.append(effect.id)
            except (OSError, ValueError) as exc:
                return OwnerApplyResult(
                    PROVIDER_KEY,
                    succeeded=tuple(succeeded),
                    failed=(effect.id,),
                    skipped=tuple(e.id for e in effects[index + 1 :]),
                    diagnostics=(Diagnostic("session_apply_failed", PROVIDER_KEY, "error", str(exc)),),
                    outcome="partial" if succeeded else "failed",
                )
        return OwnerApplyResult(PROVIDER_KEY, succeeded=tuple(succeeded))

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        # ``session_presence`` is a PROVIDER NAME, not a ToolSurfaceKind. This
        # provider handles the context_file, hook, and rule kinds it expands to.
        return definition.kind in _SESSION_PRESENCE_KINDS

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        """Expand into one instance per artefact the tool's writer manages.

        ``definition`` only carries the requested kind; the concrete kind of each
        emitted instance comes from the writer's metadata, never from a hardcoded
        path. Instances whose kind does not match ``definition.kind`` are filtered
        so ``--kind`` selection stays exact.
        """
        writer = get_writer(tool_key)
        if isinstance(writer, NullWriter):
            return [self._research_gap_instance(tool_key)]
        managed = _managed_surfaces(writer, project_root)
        instances: list[SurfaceInstance] = []
        for path, kind in managed:
            if kind != definition.kind:
                continue
            instances.append(
                SurfaceInstance(
                    definition=_definition_for(kind),
                    path=path,
                    exists=_artefact_present(writer, path, kind, project_root),
                    file_hash=None,
                    owner=tool_key,
                )
            )
        return instances

    @staticmethod
    def _research_gap_instance(tool_key: str) -> SurfaceInstance:
        return SurfaceInstance(
            definition=context_file_definition(),
            path=Path(_RESEARCH_GAP_SENTINEL),
            exists=False,
            file_hash=None,
            owner=tool_key,
        )

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        """Re-check presence of a session-presence artefact against disk.

        Presence is recomputed live (not read from the instance snapshot) so a
        post-repair re-probe reflects the just-written artefact.
        """
        if str(instance.path) == _RESEARCH_GAP_SENTINEL:
            return self._research_gap_status(instance)
        try:
            present = _instance_present(instance)
        except SettingsNotDecodableError:
            return self._undecodable_status(instance)
        if present:
            if _orientation_version_is_stale(instance):
                return self._stale_status(instance)
            return SurfaceStatus(instance=instance, state=STATE_PRESENT)
        return self._missing_status(instance)

    @staticmethod
    def _undecodable_status(instance: SurfaceInstance) -> SurfaceStatus:
        """Report an unreadable ``.claude/settings.json`` as a finding, not a crash.

        The file exists but its bytes cannot be proven to be a supported
        encoding (#4940, D6): re-saving it as UTF-8 is the only safe path, so
        this is reported truthfully rather than the presence check raising
        out of the read-only doctor probe.
        """
        return SurfaceStatus(
            instance=instance,
            state=STATE_UNSAFE,
            findings=(
                make_finding(
                    SESSION_PRESENCE_UNDECODABLE,
                    SEVERITY_ERROR,
                    f"undecodable: re-save {instance.path} as UTF-8",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                ),
            ),
        )

    @staticmethod
    def _stale_status(instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(
            instance=instance,
            state=STATE_STALE,
            findings=(
                make_finding(
                    STALE_GENERATED_SURFACE,
                    SEVERITY_WARNING,
                    f"Orientation version stale for {instance.owner}: {instance.path}",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=_REPAIR_HINT,
                ),
            ),
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
                    f"No known session-presence mechanism for {instance.owner}.",
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                ),
            ),
        )

    @staticmethod
    def _missing_status(instance: SurfaceInstance) -> SurfaceStatus:
        kind = instance.definition.kind
        if kind == ToolSurfaceKind.CONTEXT_FILE:
            code = CONTEXT_FILE_MISSING
            message = f"Always-on context file missing for {instance.owner}: {instance.path}"
            hint = _REPAIR_HINT
        else:
            code = SESSION_PRESENCE_INCOMPLETE
            label = "hook entry" if kind == ToolSurfaceKind.HOOK else "rule file"
            message = f"Session-presence {label} missing for {instance.owner}: {instance.path}"
            hint = _HOOK_REPAIR_HINT if kind == ToolSurfaceKind.HOOK else _REPAIR_HINT
        return SurfaceStatus(
            instance=instance,
            state=STATE_MISSING,
            findings=(
                make_finding(
                    code,
                    SEVERITY_ERROR,
                    message,
                    tool_key=instance.owner,
                    surface_id=_surface_id(instance),
                    path=instance.path,
                    repair_command=hint,
                ),
            ),
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        """Delegate removal to the owning writer.

        Returns ``False`` for research-gap sentinels (nothing to remove).
        """
        if str(instance.path) == _RESEARCH_GAP_SENTINEL:
            return False
        project_root, writer = _resolve_writer_for_instance(instance)
        if writer is None or project_root is None:
            return False
        writer.remove(project_root)
        return True

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        """Rewrite session presence for affected tools via their writers."""
        actionable = [s for s in statuses if s.state in (STATE_MISSING, STATE_STALE)]
        skipped = tuple(_surface_id(s.instance) for s in statuses if s.state == STATE_NOT_APPLICABLE)
        if not actionable:
            return RepairResult(skipped=skipped, dry_run=dry_run)
        consent = ApplyConsent(automatic=True)
        selections = tuple(SurfaceSelection(s.instance.owner, s.instance.definition) for s in actionable)
        assessment = self.assess(
            AssessmentInputs(OperationRoot("project", "project", project_root), consent=consent),
            actionable,
            selections=selections,
        )
        if not assessment.complete:
            return RepairResult(skipped=skipped, failed=tuple(d.message for d in assessment.diagnostics), dry_run=dry_run)
        result = None if dry_run else self.apply(assessment, consent)
        failed = tuple(d.message for d in result.diagnostics) if result is not None else ()
        preserved = {d.path for d in assessment.dispositions if d.state == "preserve"}
        prepared = assessment.prepared
        eligible = {tool for tool, _member in prepared.files} if isinstance(prepared, PreparedSessionBatch) else set()
        return RepairResult(
            repaired=tuple(
                _surface_id(s.instance)
                for s in actionable
                if s.instance.owner in eligible and not failed and s.instance.path.relative_to(project_root).as_posix() not in preserved
            ),
            skipped=skipped + tuple(_surface_id(s.instance) for s in actionable if s.instance.owner not in eligible),
            failed=failed + tuple(f"Preserved drift: {p}" for p in sorted(preserved) if p),
            dry_run=dry_run,
        )


def _session_effects(
    root: OperationRoot,
    tool: str,
    member: PreparedPresenceFile,
    observations: tuple[InputObservation, ...],
    ids: tuple[str, ...],
) -> tuple[PhysicalEffect, ...]:
    proof = (OwnershipProof("managed_path", f"session-presence:{member.path}:managed-region"),)
    effects = []
    for observation in observations:
        before = presence_state(observation)
        if observation.name == "." or before.kind != "absent" or not member.path.startswith(observation.name + "/"):
            continue
        effects.append(
            PhysicalEffect(
                PROVIDER_KEY,
                "surface_repair",
                root,
                observation.name,
                "create",
                before,
                FileState("directory", mode=0o755),
                "Session writer supporting directory",
                proof,
                (tool,),
                ids,
            )
        )
    before = member.before
    effects.append(
        PhysicalEffect(
            PROVIDER_KEY,
            "surface_repair",
            root,
            member.path,
            "create" if before.kind == "absent" else "update",
            before,
            FileState("file", sha256=sha256(member.content).hexdigest(), mode=before.mode if before.mode is not None else 0o644),
            member.reason,
            proof,
            (tool,),
            ids,
        )
    )
    return tuple(effects)


def _managed_surfaces(writer: object, project_root: Path) -> list[tuple[Path, ToolSurfaceKind]]:
    """Return the ``(absolute_path, kind)`` artefacts ``writer`` manages.

    Knowledge of which writer manages which artefacts lives here rather than in
    the writers themselves (the writers predate the surface contract). Claude's
    writer manages a context file plus two ``settings.json`` hook entries; the
    Markdown-family writers manage a single context-or-rule file classified by
    its target path.
    """
    surfaces: list[tuple[Path, ToolSurfaceKind]] = []
    if isinstance(writer, ClaudeCodeWriter):
        surfaces.append((project_root / writer.rules_path, ToolSurfaceKind.CONTEXT_FILE))
        settings = project_root / ClaudeCodeHookRegistrar().settings_relative_path
        surfaces.append((settings, ToolSurfaceKind.HOOK))
        surfaces.append((settings, ToolSurfaceKind.HOOK))
        return surfaces
    if isinstance(writer, MarkdownRulesWriter):
        surfaces.append((project_root / writer.rules_path, _markdown_kind(writer.rules_path)))
    return surfaces


def _instance_present(instance: SurfaceInstance) -> bool:
    """Recompute live presence for an instance from disk.

    The project root is recovered from the instance path by stripping the
    artefact's relative suffix; the writer is looked up by owner so the correct
    per-kind presence check runs.
    """
    writer = get_writer(instance.owner)
    kind = instance.definition.kind
    if kind == ToolSurfaceKind.HOOK and isinstance(writer, ClaudeCodeWriter):
        root = _project_root_from(instance.path, Path(".claude/settings.json"))
        return root is not None and _claude_hooks_present(root)
    if isinstance(writer, MarkdownRulesWriter):
        return _orientation_section_present(instance.path)
    return bool(instance.path.exists())


def _project_root_from(path: Path, rel: Path) -> Path | None:
    """Strip ``rel`` from the tail of ``path`` to recover the project root."""
    parts = path.parts
    rel_parts = rel.parts
    if len(parts) < len(rel_parts) or parts[-len(rel_parts) :] != rel_parts:
        return None
    return Path(*parts[: len(parts) - len(rel_parts)])


def _artefact_present(
    writer: object,
    path: Path,
    kind: ToolSurfaceKind,
    project_root: Path,
) -> bool:
    """Return whether the specific artefact at ``path`` is currently installed.

    Each artefact is checked in isolation -- the context file by its orientation
    marker, the hooks by their registrar. ``ClaudeCodeWriter.has_presence`` is a
    *composite* (file AND both hooks), so it is deliberately not used here: a
    ``--kind context_file`` probe must report the file's own state regardless of
    whether the sibling hooks happen to be present.

    An undecodable ``settings.json`` (#4940) is reported as not-present here
    (never a traceback out of ``expand``); ``probe()`` re-checks live and
    turns the same condition into a truthful ``session-presence-undecodable``
    finding instead.
    """
    if kind == ToolSurfaceKind.HOOK and isinstance(writer, ClaudeCodeWriter):
        try:
            return _claude_hooks_present(project_root)
        except SettingsNotDecodableError:
            return False
    if isinstance(writer, MarkdownRulesWriter):
        return _orientation_section_present(project_root / writer.rules_path)
    return path.exists()


def _orientation_section_present(target: Path) -> bool:
    """Return whether ``target`` exists and contains the orientation marker."""
    if not target.exists():
        return False
    try:
        return SECTION_OPEN in target.read_text(encoding="utf-8")
    except OSError:
        return False


#: The prefix ``SessionPresenceContent.render`` stamps immediately before the
#: version (``**Spec Kitty v{version}** — ...``). The version runs up to the
#: closing ``**``.
_VERSION_PREFIX = "**Spec Kitty v"
_VERSION_SUFFIX = "**"


def _on_disk_orientation_version(target: Path) -> str | None:
    """Return the version stamped in ``target``'s orientation block, or ``None``.

    The parse is scoped to the marker-delimited managed block (the same
    delimiters the writer uses to locate it), so a stray ``**Spec Kitty v...**``
    elsewhere in the file — a pasted example or a second stamp — cannot be
    mistaken for the managed version.

    ``None`` means the file is absent, unreadable, has no managed block, or the
    block carries no parseable ``**Spec Kitty v...**`` stamp — in which case the
    block is left alone rather than churned (a hand-edited block is drift,
    handled by a different rule).
    """
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return None
    open_at = text.find(SECTION_OPEN)
    if open_at == -1:
        return None
    close_at = text.find(SECTION_CLOSE, open_at)
    section = text[open_at : close_at if close_at != -1 else len(text)]
    start = section.find(_VERSION_PREFIX)
    if start == -1:
        return None
    start += len(_VERSION_PREFIX)
    end = section.find(_VERSION_SUFFIX, start)
    if end == -1:
        return None
    stamped = section[start:end].strip()
    return stamped or None


# Orientation-bearing surfaces carry the version stamp: always-on context files
# and path/glob-activated rule/steering files (both written by the Markdown
# family). Hooks do not, so they are excluded from the staleness check.
_ORIENTATION_STAMPED_KINDS = frozenset({ToolSurfaceKind.CONTEXT_FILE, ToolSurfaceKind.RULE})


def _orientation_version_is_stale(instance: SurfaceInstance) -> bool:
    """Return whether a present orientation surface's version stamp is outdated (#2265).

    Covers every Markdown-family orientation surface (context files AND
    rule/steering files) uniformly. Staleness is a pure version-string mismatch
    against the installed CLI, so a legitimate health-line change (e.g.
    ``upgrade-available`` -> ``healthy``) at the same version does not churn the
    block on every upgrade.
    """
    if instance.definition.kind not in _ORIENTATION_STAMPED_KINDS:
        return False
    project_root, writer = _resolve_writer_for_instance(instance)
    if project_root is None or writer is None:
        return False
    on_disk = _on_disk_orientation_version(project_root / writer.rules_path)
    if on_disk is None:
        return False
    return bool(on_disk != _orientation_content(project_root).version)


def _claude_hooks_present(project_root: Path) -> bool:
    """Return whether both Claude session hooks are registered."""
    start = ClaudeCodeHookRegistrar(SESSION_START_EVENT).is_registered(project_root, SESSION_START_CMD)
    stop = ClaudeCodeHookRegistrar(STOP_EVENT).is_registered(project_root, SESSION_STOP_CMD)
    return bool(start) and bool(stop)


def _resolve_writer_for_instance(
    instance: SurfaceInstance,
) -> tuple[Path | None, MarkdownRulesWriter | None]:
    """Recover ``(project_root, writer)`` for an instance, if resolvable.

    The project root is the parent of the artefact's harness directory; for the
    Markdown family the relative ``rules_path`` is stripped from the instance
    path. Returns ``(None, None)`` when the writer is not a known mutating type.
    """
    writer = get_writer(instance.owner)
    if not isinstance(writer, MarkdownRulesWriter):
        return None, None
    project_root = _project_root_from(instance.path, Path(writer.rules_path))
    if project_root is None:
        return None, None
    return project_root, writer


def _orientation_content(project_root: Path) -> SessionPresenceContent:
    """Use the session owner's explicit local-only content path."""
    from specify_cli.session_presence.manager import local_presence_content

    return local_presence_content(project_root.name)


# ---------------------------------------------------------------------------
# Self-registration (fires at import time via providers._discovery)
# ---------------------------------------------------------------------------
SurfaceProviderRegistry.register(
    SurfaceRegistration(
        provider_class=SessionPresenceProvider,
        definitions=(
            context_file_definition(),
            hook_definition(),
            rule_definition(),
        ),
        kind_tokens={
            "context-file": ToolSurfaceKind.CONTEXT_FILE,
            "context_file": ToolSurfaceKind.CONTEXT_FILE,
            "hook": ToolSurfaceKind.HOOK,
            "rule": ToolSurfaceKind.RULE,
        },
        order=20,
    )
)
