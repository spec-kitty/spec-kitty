"""Shared projection helpers for plugin bundle projectors.

The Claude Code, Copilot, and VS Code projectors differ only in their package
layout (manifest location, agent filename suffix). The common work -- selecting
which canonical surfaces belong in a bundle, computing each surface's
bundle-relative path, and writing the staging files -- lives here so the
per-target projectors stay thin.

**Scope guard (FR-016, C-006):** :func:`write_bundle` performs filesystem writes
*only* under the caller-supplied ``output_dir`` staging directory. It contains no
install, registration, enablement, or marketplace-publish logic; the only side
effect is creating local files inside the staging tree.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from hashlib import sha256  # noqa: TID251 -- exact staging byte integrity.
from pathlib import Path
from uuid import uuid4

from specify_cli.core.no_follow import chmod_fd
from specify_cli.skills import command_installer

from ..enums import ActivationMode, ToolSurfaceKind
from ..model import SurfacePlan
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
from ..status import _surface_id
from .model import BundleEntry, BundleObservation, PreparedBundle, StagedFile

OWNER = "plugin_bundle"
_LEDGER = ".spec-kitty-bundle.json"


@dataclass(frozen=True)
class SelectedSkillBundle:
    """Original selected staging and command supplier, with shared parent inputs."""

    assessment: OwnerAssessment
    commands: OwnerAssessment
    parents: tuple[BundleObservation, ...]

    @classmethod
    def prepare(cls, assessment: OwnerAssessment, commands: OwnerAssessment) -> SelectedSkillBundle:
        prepared = assessment.prepared
        if (
            not assessment.complete
            or any(d.severity == "error" for d in assessment.diagnostics)
            or assessment.owner_key != OWNER
            or not isinstance(prepared, PreparedBundle)
            or assessment.root != commands.root
            or assessment.consent != commands.consent
            or not any(s is commands for s in prepared.suppliers)
            or not isinstance(commands.prepared, command_installer.PreparedCommands)
        ):
            raise ValueError("Selected staging requires the original command supplier and matching consent/root")
        parents = tuple(observe_bundle_path(item.path, members=True) for item in prepared.observations if item.state.kind == "directory")
        return cls(assessment, commands, parents)


@dataclass
class _SelectedBundleRun:
    inputs: SelectedSkillBundle
    parents: dict[Path, BundleObservation]
    written: dict[Path, BundleObservation] = field(default_factory=dict)
    completed: tuple[BundleObservation, ...] | None = None
    attempted: bool = False


_SELECTED_SKILL_BUNDLE: ContextVar[_SelectedBundleRun | None] = ContextVar("selected_skill_bundle", default=None)


@contextmanager
def selected_skill_bundle_guard(selected: SelectedSkillBundle | None) -> Iterator[tuple[Diagnostic, ...]]:
    """Require original staging/supplier observations before any provisioning."""
    if selected is None:
        yield ()
        return
    with staging_guard(selected.assessment) as errors:
        try:
            if SelectedSkillBundle.prepare(selected.assessment, selected.commands) != selected:
                raise ValueError("Selected bundle parent inputs changed")
            errors += command_installer.recheck_commands(selected.commands, phase="preflight")
        except (OSError, ValueError) as exc:
            errors += (Diagnostic("precondition_changed", OWNER, "error", str(exc)),)
        token = _SELECTED_SKILL_BUNDLE.set(None if errors else _SelectedBundleRun(selected, {p.path: p for p in selected.parents}))
        try:
            yield errors
        finally:
            _SELECTED_SKILL_BUNDLE.reset(token)


def _selected_provisioned_observation(assessment: OwnerAssessment, item: BundleObservation) -> BundleObservation:
    run = _SELECTED_SKILL_BUNDLE.get()
    if run is None or run.inputs.assessment is not assessment:
        return item
    payload = run.inputs.commands.prepared
    assert isinstance(payload, command_installer.PreparedCommands)
    target = command_installer._recheck_command_provisioning(payload, "apply")
    if target != item.path:
        return item
    assert payload.provisioning is not None
    current = observe_bundle_path(item.path)
    return replace(item, state=replace(item.state, sha256=payload.provisioning.write.desired_sha256, mtime_ns=current.state.mtime_ns))


def _record_selected_stage(assessment: OwnerAssessment, effect: PhysicalEffect, *, before: bool) -> None:
    """Capture identities at the real writer, never authorize a caller-supplied hash."""
    run = _SELECTED_SKILL_BUNDLE.get()
    if run is None or run.inputs.assessment is not assessment:
        return
    parent = run.parents.get(effect.destination.parent)
    if parent is not None:
        current = observe_bundle_path(parent.path, members=True)
        expected = parent
        if not before:
            names = set(parent.children or ())
            names.add(effect.destination.name)
            expected = replace(parent, children=tuple(sorted(names)), state=replace(parent.state, mtime_ns=current.state.mtime_ns))
        if current != expected:
            raise ValueError(f"Selected bundle parent changed: {parent.path}")
        run.parents[parent.path] = current
    if not before:
        run.written[effect.destination] = observe_bundle_path(effect.destination)
        if effect.after.kind == "directory":
            run.parents[effect.destination] = observe_bundle_path(effect.destination, members=True)


def _finish_selected_stage(assessment: OwnerAssessment) -> None:
    run = _SELECTED_SKILL_BUNDLE.get()
    if run is None or run.inputs.assessment is not assessment:
        return
    prepared = assessment.prepared
    assert isinstance(prepared, PreparedBundle)
    effects = {e.destination: e for e in assessment.effects}
    observations = {o.path: o for o in prepared.observations}
    observations.update(run.parents)
    completed = []
    for path, original in observations.items():
        effect = effects.get(path)
        if effect is not None and path in run.parents:
            original = replace(original, state=replace(original.state, mode=effect.after.mode))
        if effect is not None and path not in run.parents:
            written = run.written[path]
            original = replace(written, state=replace(effect.after, mtime_ns=written.state.mtime_ns))
        elif path not in run.parents:
            original = _selected_provisioned_observation(assessment, original)
        current = observe_bundle_path(path, members=original.children is not None)
        if not same_observation(current, original):
            raise ValueError(f"Selected staged output/input changed: {path}")
        if path in run.parents:
            run.parents[path] = current
        completed.append(current)
    run.completed = tuple(completed)


@contextmanager
def completed_selected_skill_bundle(selected: SelectedSkillBundle | None) -> Iterator[tuple[Diagnostic, ...]]:
    """Admit only this guarded staging's checked receipts before upstream writes."""
    if selected is None:
        yield ()
        return
    run = _SELECTED_SKILL_BUNDLE.get()
    try:
        if run is None or run.inputs is not selected or run.completed is None:
            raise ValueError("Selected bundle staging must complete before upstream repair")
        for item in run.completed:
            if observe_bundle_path(item.path, members=item.children is not None) != item:
                raise ValueError(f"Completed selected bundle changed: {item.path}")
    except (OSError, ValueError) as exc:
        yield (Diagnostic("precondition_changed", OWNER, "error", str(exc)),)
        return
    with command_installer._completed_bundle_parents(selected.commands, tuple(run.parents.values())):
        yield ()


# Surface kinds that belong in a plugin bundle. Session-presence kinds
# (CONTEXT_FILE, RULE) are deliberately excluded -- they are project-install
# surfaces, not bundle components (see WP09 task spec).
BUNDLE_SURFACE_KINDS: frozenset[ToolSurfaceKind] = frozenset(
    {
        ToolSurfaceKind.COMMAND_SKILL,
        ToolSurfaceKind.CHARTER_SKILL,
        ToolSurfaceKind.AGENT_PROFILE,
        ToolSurfaceKind.HOOK,
        ToolSurfaceKind.NATIVE_CONFIG,
    }
)

# Inert placeholder manifest version. The manifest is a declarative descriptor;
# its presence never triggers install/publish behaviour.
_MANIFEST_VERSION = "0.0.0"


def _bundle_relative_path(
    kind: ToolSurfaceKind,
    source_path: Path,
    layout: dict[ToolSurfaceKind, str],
    agent_filename: Callable[[str], str],
) -> str | None:
    """Compute the in-bundle relative path for a surface, or ``None`` to skip."""
    prefix = layout.get(kind)
    if prefix is None:
        return None
    if kind == ToolSurfaceKind.AGENT_PROFILE:
        leaf = agent_filename(source_path.stem)
        return f"{prefix}/{leaf}" if prefix else leaf
    if kind == ToolSurfaceKind.COMMAND_SKILL or kind == ToolSurfaceKind.CHARTER_SKILL:
        # Command/charter skills are ``.../<name>/SKILL.md``; preserve the
        # skill directory name inside the bundle's ``skills/`` tree.
        if "skills" in source_path.parts:
            index = len(source_path.parts) - 1 - source_path.parts[::-1].index("skills")
            return f"{prefix}/" + "/".join(source_path.parts[index + 1 :])
        return f"{prefix}/{source_path.parent.name}/{source_path.name}"
    leaf = source_path.name
    return f"{prefix}/{leaf}" if prefix else leaf


def bundle_entries_for_plans(
    plans: Sequence[SurfacePlan],
    project_root: Path,
    *,
    layout: dict[ToolSurfaceKind, str],
    agent_filename: Callable[[str], str],
    bundle_kinds: frozenset[ToolSurfaceKind],
) -> tuple[BundleEntry, ...]:
    """Project the bundleable surfaces of ``plans`` into ``BundleEntry`` tuples.

    Only surfaces whose source path lies inside ``project_root`` are bundled --
    a staging safety guard so a plugin bundle can never absorb a file from
    outside the project tree (e.g. a user-global surface). The result is
    de-duplicated on ``bundle_relative_path`` and ordered deterministically so
    repeated projections are byte-stable.
    """
    seen: dict[str, BundleEntry] = {}
    for plan in plans:
        for instance in plan.instances:
            kind = instance.definition.kind
            if kind not in bundle_kinds or instance.definition.activation_mode == ActivationMode.DISABLED:
                continue
            if not _within_project(instance.path, project_root):
                continue
            rel = _bundle_relative_path(kind, instance.path, layout, agent_filename)
            if rel is None:
                continue
            candidate = BundleEntry(
                surface_kind=kind,
                source_path=_project_source_path(instance.path, project_root),
                bundle_relative_path=rel,
                logical_owners=(instance.owner,),
                surface_ids=(_surface_id(instance),),
                sources=(_project_source_path(instance.path, project_root),),
                source_root=project_root.resolve(),
                claims=((_project_source_path(instance.path, project_root), instance.owner, _surface_id(instance)),),
            )
            prior = seen.get(rel)
            seen[rel] = (
                candidate
                if prior is None
                else replace(
                    prior,
                    logical_owners=tuple(sorted(set(prior.logical_owners + candidate.logical_owners))),
                    surface_ids=tuple(sorted(set(prior.surface_ids + candidate.surface_ids))),
                    sources=tuple(sorted(set(prior.sources + candidate.sources))),
                    claims=tuple(sorted(set(prior.claims + candidate.claims))),
                )
            )
    return tuple(seen[key] for key in sorted(seen))


def _within_project(path: Path, project_root: Path) -> bool:
    """Select lexical project members; a hostile child link must fail, not vanish."""
    try:
        relative = _project_source_path(path, project_root).relative_to(project_root.resolve())
    except ValueError:
        return False
    return relative != Path(".")


def _project_source_path(path: Path, project_root: Path) -> Path:
    """Canonicalize a root alias, but keep project-relative child links literal."""
    if path.is_relative_to(project_root):
        return project_root.resolve() / path.relative_to(project_root)
    resolved = project_root.resolve()
    for ancestor in path.parents:
        if ancestor.resolve() == resolved:
            return resolved / path.relative_to(ancestor)
    raise ValueError(f"Bundle member is outside its selected project: {path}")


def plugin_manifest_payload(distribution_target: str) -> dict[str, object]:
    """Build the declarative ``plugin.json`` payload for a target.

    The payload is informational only; it carries no install/marketplace
    directives.
    """
    return {
        "name": "spec-kitty",
        "version": _MANIFEST_VERSION,
        "description": "Spec Kitty tool surfaces (staging bundle).",
        "distribution_target": distribution_target,
    }


def write_bundle(
    output_dir: Path,
    entries: Sequence[BundleEntry],
    manifest_relative_path: str,
    manifest: dict[str, object],
) -> None:
    """Prepare once, then apply exactly the selected staging members."""
    root = staging_root(output_dir)
    output_dir = confined_output(output_dir, root)
    inputs = AssessmentInputs(root, consent=ApplyConsent(automatic=True))
    observations: list[BundleObservation] = []
    files = files_for_entries(entries, output_dir, root, observations)
    manifest_path = (output_dir / manifest_relative_path).relative_to(root.path).as_posix()
    files += (StagedFile(manifest_path, json_bytes(manifest), manifest=True),)
    assessment = prepare_staging(inputs, files, (output_dir,), tuple(observations))
    result = apply_staging(assessment, inputs.consent)
    if not assessment.complete or result.failed or result.skipped or any(d.state != "unchanged" for d in assessment.dispositions):
        raise ValueError(
            "; ".join(d.message for d in assessment.diagnostics + result.diagnostics) or "Staged bundle contains preserved or consent-required content"
        )


def json_bytes(payload: dict[str, object], *, legacy: bool = False) -> bytes:
    """Retain each existing manifest serializer's byte convention."""
    if legacy:
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_regular(path: Path) -> bytes:
    """Read one regular node without following its final link."""
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow == 0 and path.is_symlink():
        raise ValueError(f"Required bundle source is not a regular file: {path}")
    descriptor = os.open(path, os.O_RDONLY | no_follow)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Required bundle source is not a regular file: {path}")
        return stream.read()


def observe_bundle_path(path: Path, *, members: bool = False) -> BundleObservation:
    """Observe file content/type/mode/mtime and node identity without link traversal."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return BundleObservation(path, FileState("absent"), None, None)
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        state = FileState("symlink", target=os.readlink(path), mode=mode, mtime_ns=info.st_mtime_ns)
    elif stat.S_ISREG(info.st_mode):
        state = FileState("file", sha256=sha256(read_regular(path)).hexdigest(), mode=mode, mtime_ns=info.st_mtime_ns)
    elif stat.S_ISDIR(info.st_mode):
        state = FileState("directory", mode=mode, mtime_ns=info.st_mtime_ns)
    else:
        raise ValueError(f"Unsupported staging node: {path}")
    children = tuple(sorted(p.name for p in path.iterdir())) if members and state.kind == "directory" else None
    after = path.lstat()
    if (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mode, after.st_mtime_ns):
        raise ValueError(f"Bundle input changed while reading: {path}")
    return BundleObservation(path, state, info.st_dev, info.st_ino, children)


def read_observed_file(observation: BundleObservation) -> bytes:
    """Retain bytes only if they agree with the selected source observation."""
    content = read_regular(observation.path)
    if sha256(content).hexdigest() != observation.state.sha256 or observe_bundle_path(observation.path) != observation:
        raise ValueError(f"Bundle source changed during preparation: {observation.path}")
    return content


def observe_confined(root: Path, path: Path) -> tuple[BundleObservation, ...]:
    """Observe every parent, including absent parents, before accessing a member."""
    relative = path.relative_to(root)
    if ".." in relative.parts:
        raise ValueError(f"Unconfined bundle path: {path}")
    paths = (root, *(root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)))
    observations = []
    for index, candidate in enumerate(paths):
        item = observe_bundle_path(candidate)
        if index < len(paths) - 1 and item.state.kind not in {"directory", "absent"}:
            raise ValueError(f"Unsafe bundle parent: {candidate}")
        observations.append(item)
    return tuple(observations)


def observe_tree(root: Path) -> tuple[BundleObservation, ...]:
    """Enumerate supporting descendants without following any child links."""
    observations: list[BundleObservation] = []
    pending = [root]
    while pending:
        path = pending.pop()
        observed = observe_bundle_path(path, members=True)
        if observed.state.kind not in {"file", "directory"}:
            raise ValueError(f"Unsafe required bundle source: {path}")
        observations.append(observed)
        if observed.children is not None:
            pending.extend(path / name for name in reversed(observed.children))
    return tuple(observations)


def staging_root(output_dir: Path) -> OperationRoot:
    """Resolve the existing staging ancestor once; never resolve a child link."""
    candidate = output_dir.absolute().parent
    while not candidate.exists():
        candidate = candidate.parent
    if candidate.is_symlink():
        raise ValueError(f"Staging ancestor is a symlink: {candidate}")
    return OperationRoot("staging", "project", candidate.resolve())


def confined_output(output_dir: Path, root: OperationRoot) -> Path:
    """Normalize the trusted existing ancestor, without resolving descendants."""
    candidate = output_dir.absolute().parent
    while not candidate.exists():
        candidate = candidate.parent
    if candidate.resolve() != root.path:
        raise ValueError("Staging root changed during selection")
    normalized: Path = root.path / output_dir.absolute().relative_to(candidate)
    return normalized


def files_for_entries(
    entries: Sequence[BundleEntry],
    output_dir: Path,
    root: OperationRoot,
    observations: list[BundleObservation],
) -> tuple[StagedFile, ...]:
    """Materialize exact bytes in memory, requiring all shared claims to agree."""
    result = []
    for entry in entries:
        variants: list[tuple[bytes, int]] = []
        if entry.content is not None:
            variants.append((entry.content, entry.mode))
        else:
            for source in entry.sources or (entry.source_path,):
                retained = [(content, mode) for path, content, mode in entry.retained if path == source]
                if retained:
                    variants.extend(retained)
                    continue
                observed = observe_confined(entry.source_root or source.parent, source)
                observations.extend(observed)
                if observed[-1].state.kind != "file":
                    raise ValueError(f"Required bundle source unavailable: {source}")
                content = read_observed_file(observed[-1])
                assert observed[-1].state.mode is not None
                variants.append((content, observed[-1].state.mode))
        if not variants or len(set(variants)) != 1:
            raise ValueError(f"Conflicting bundle members: {entry.bundle_relative_path}")
        content, mode = variants[0]
        _validate_member_bytes(entry, content)
        path = (output_dir / entry.bundle_relative_path).relative_to(root.path).as_posix()
        result.append(StagedFile(path, content, mode, entry.logical_owners or (OWNER,), entry.surface_ids))
    return tuple(result)


def _validate_member_bytes(entry: BundleEntry, content: bytes) -> None:
    """Validate structured required members, leaving binary supporting assets exact."""
    if entry.source_path.suffix == ".json":
        if not isinstance(json.loads(content), dict):
            raise ValueError(f"Required JSON bundle member is not an object: {entry.source_path}")
    elif entry.source_path.name == "SKILL.md":
        text = content.decode("utf-8")
        if text.startswith("---"):
            import yaml

            pieces = text.split("---", 2)
            try:
                valid = len(pieces) == 3 and isinstance(yaml.safe_load(pieces[1]), dict)
            except yaml.YAMLError as exc:
                raise ValueError(f"Malformed required skill frontmatter: {entry.source_path}") from exc
            if not valid:
                raise ValueError(f"Malformed required skill frontmatter: {entry.source_path}")


def supplied_entries(
    entries: tuple[BundleEntry, ...],
    suppliers: tuple[OwnerAssessment, ...],
) -> tuple[BundleEntry, ...]:
    """Consume concrete owner payloads, never rerender or apply their effects."""
    supplied = tuple(member for owner in suppliers for member in supplier_members(owner))
    retired = {effect.destination for owner in suppliers for effect in owner.effects if effect.after.kind == "absent"}
    result: list[BundleEntry] = []
    for entry in entries:
        paths = tuple(path for path in (entry.sources or (entry.source_path,)) if path not in retired)
        if not paths:
            continue
        claims = tuple(claim for claim in entry.claims if claim[0] in paths)
        entry = replace(
            entry,
            source_path=paths[0],
            sources=paths,
            claims=claims,
            logical_owners=tuple(sorted({claim[1] for claim in claims})) if entry.claims else entry.logical_owners,
            surface_ids=tuple(sorted({claim[2] for claim in claims})) if entry.claims else entry.surface_ids,
        )
        candidates = [(path, content, mode) for path, content, mode in supplied if path in paths]
        blocked = any(
            item.path is not None
            and owner.root.path / item.path in paths
            and item.state in {"preserve", "consent_required"}
            and not any(path == owner.root.path / item.path for path, _content, _mode in candidates)
            for owner in suppliers
            for item in owner.dispositions
        )
        if blocked:
            raise ValueError(f"Upstream owner retained no canonical bytes for {entry.source_path}")
        if candidates:
            variants = {(content, mode) for _path, content, mode in candidates}
            if len(variants) != 1:
                raise ValueError(f"Conflicting prepared bundle member: {entry.bundle_relative_path}")
            result.append(replace(entry, retained=tuple(candidates)))
        else:
            result.append(entry)
    return tuple(result)


def supplier_members(assessment: OwnerAssessment) -> tuple[tuple[Path, bytes, int], ...]:
    """Read only the exported immutable payload types of WP04-WP07."""
    from specify_cli.skills.command_installer import PreparedCommands
    from specify_cli.skills.installer import PreparedProjectSkills
    from specify_cli.skills.vibe_config import PreparedVibeConfig
    from ..profiles.projection import PreparedProfileBatch
    from ..providers.session_presence import PreparedSessionBatch

    if not assessment.complete:
        raise ValueError(f"Incomplete bundle supplier: {assessment.owner_key}")
    payload, root = assessment.prepared, assessment.root.path
    if isinstance(payload, PreparedCommands):
        return tuple((root / item.path, item.content, 0o644) for item in payload.commands if item.content is not None)
    if isinstance(payload, PreparedProjectSkills):
        return tuple(
            (item.effect.destination, item.content, item.effect.after.mode or 0o444) for item in payload.writes if item.content is not None and item.order == 2
        )
    if isinstance(payload, PreparedProfileBatch):
        return tuple((item.native.output_path, item.content, 0o644) for item in payload.projections)
    if isinstance(payload, PreparedSessionBatch):
        return tuple((root / item.path, item.content, item.before.mode or 0o644) for _tool, item in payload.files if item.disposition != "preserve")
    if isinstance(payload, PreparedVibeConfig):
        return ((root / payload.file.path, payload.file.content, payload.file.before.mode or 0o644),)
    raise ValueError(f"Unsupported concrete bundle supplier: {assessment.owner_key}")


def _ledger_entries(raw: bytes) -> dict[str, tuple[str, int]]:
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("owner") != OWNER or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("Invalid required bundle ownership manifest")
    members = data.get("members")
    if not isinstance(members, dict):
        raise ValueError("Invalid required bundle ownership members")
    result = {}
    for path, entry in members.items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            raise ValueError("Invalid bundle ownership entry")
        state = FileState("file", sha256=entry.get("sha256"), mode=entry.get("mode"))
        if Path(path).is_absolute() or ".." in Path(path).parts or not path:
            raise ValueError("Unconfined bundle ownership entry")
        assert state.sha256 is not None and state.mode is not None
        result[path] = (state.sha256, state.mode)
    return result


def prepare_staging(
    inputs: AssessmentInputs,
    files: tuple[StagedFile, ...],
    bundle_dirs: tuple[Path, ...],
    observations: tuple[BundleObservation, ...] = (),
    *,
    suppliers: tuple[OwnerAssessment, ...] = (),
    version: str | None = None,
    supporting_dirs: tuple[tuple[str, int], ...] = (),
) -> OwnerAssessment:
    """Compare one complete staged batch and retain every byte before any write."""
    try:
        if inputs.root.scope != "project":
            raise ValueError("Plugin bundles require an explicit project/staging root")
        return _prepare_staging(inputs, files, bundle_dirs, observations, suppliers, version, supporting_dirs)
    except (OSError, ValueError) as exc:
        return OwnerAssessment(
            OWNER, inputs.root, complete=False, consent=inputs.consent, diagnostics=(Diagnostic("bundle_input_invalid", OWNER, "error", str(exc)),)
        )


def _prepare_staging(
    inputs: AssessmentInputs,
    files: tuple[StagedFile, ...],
    bundle_dirs: tuple[Path, ...],
    observations: tuple[BundleObservation, ...],
    suppliers: tuple[OwnerAssessment, ...],
    version: str | None,
    supporting_dirs: tuple[tuple[str, int], ...],
) -> OwnerAssessment:
    root = inputs.root
    observed = list(observations)
    known, ledgers = _ledger_state(root, bundle_dirs, observed)
    effects: list[PhysicalEffect] = []
    dispositions: list[Disposition] = []
    directory_modes = dict(supporting_dirs)
    for relative, mode in supporting_dirs:
        observed.extend(observe_confined(root.path, root.path / relative))
        before = observed[-1].state
        if before.kind == "absent":
            effects.append(
                PhysicalEffect(
                    OWNER,
                    "surface_repair",
                    root,
                    relative,
                    "create",
                    before,
                    FileState("directory", mode=mode),
                    "Create selected supporting directory",
                    (OwnershipProof("managed_path", f"selected supporting directory:{relative}"),),
                    (OWNER,),
                )
            )
        elif before.kind != "directory":
            raise ValueError(f"Unsafe supporting directory: {relative}")
    unique = _unique_members(files)
    preserved: set[str] = set()
    for member in unique.values():
        observed.extend(observe_confined(root.path, root.path / member.path))
        before = observed[-1].state
        digest = sha256(member.content).hexdigest()
        prior = known.get(member.path)
        if before.kind == "symlink":
            dispositions.append(Disposition(OWNER, root.root_id, member.path, "preserve", "Unknown staged link is not owned by a file manifest"))
            preserved.add(member.path)
            continue
        if before.kind != "absent" and before.sha256 != digest:
            state = "consent_required" if prior else "preserve"
            if prior is None or member.path not in inputs.consent.overwrite_paths:
                dispositions.append(Disposition(OWNER, root.root_id, member.path, state, "Staged content requires exact prior ownership and consent"))
                preserved.add(member.path)
                continue
        if before.kind not in {"file", "absent", "symlink"}:
            raise ValueError(f"Unsupported bundle destination: {member.path}")
        proof = (
            OwnershipProof("manifest", f"{_LEDGER}:{member.path}")
            if prior
            else OwnershipProof("canonical_content" if before.kind == "file" else "managed_path", f"bundle member:{member.path}")
        )
        _stage_effect(root, member, before, proof, effects, dispositions)
    # Never publish a fresh descriptor that promises a preserved requested member.
    blocked_manifests = {m.path for m in unique.values() if m.manifest} if preserved else set()
    effects = [e for e in effects if e.path not in blocked_manifests]
    _add_ledgers(root, ledgers, unique, preserved | blocked_manifests, observed, effects, dispositions)
    for effect in tuple(effects):
        for path in reversed(Path(effect.path).parents):
            if path == Path("."):
                continue
            observed.extend(observe_confined(root.path, root.path / path))
            before = observed[-1].state
            if before.kind == "absent":
                effects.append(
                    PhysicalEffect(
                        OWNER,
                        "surface_repair",
                        root,
                        path.as_posix(),
                        "create",
                        before,
                        FileState("directory", mode=directory_modes.get(path.as_posix(), 0o755)),
                        "Create staged parent",
                        effect.ownership,
                        effect.logical_owners,
                        effect.surface_ids,
                    )
                )
    retained: dict[Path, BundleObservation] = {}
    for item in observed:
        prior_observation = retained.setdefault(item.path, item)
        if prior_observation != item:
            raise ValueError(f"Staging input changed during preparation: {item.path}")
    prepared = PreparedBundle(
        root,
        inputs.consent,
        tuple(unique.values()),
        tuple(retained.values()),
        suppliers,
        version,
        tuple(sorted({effect.path for effect in effects if effect.after.kind == "file"})),
        supporting_dirs,
    )
    return OwnerAssessment(
        OWNER,
        root,
        coalesce_effects(tuple(effects)),
        tuple(dispositions),
        inputs_fingerprint=(
            InputObservation("bundle_inputs", prepared.observations),
            InputObservation("bundle_supplier_inputs", tuple(s.inputs_fingerprint for s in suppliers)),
        ),
        prepared=prepared,
        consent=inputs.consent,
    )


def _ledger_state(
    root: OperationRoot,
    bundle_dirs: tuple[Path, ...],
    observed: list[BundleObservation],
) -> tuple[dict[str, tuple[str, int]], list[tuple[str, dict[str, tuple[str, int]]]]]:
    known: dict[str, tuple[str, int]] = {}
    ledgers: list[tuple[str, dict[str, tuple[str, int]]]] = []
    for directory in bundle_dirs:
        path = directory / _LEDGER
        observed.extend(observe_confined(root.path, path))
        state = observed[-1].state
        if state.kind not in {"file", "absent"}:
            raise ValueError(f"Unsafe bundle ownership manifest: {path}")
        entries = _ledger_entries(read_observed_file(observed[-1])) if state.kind == "file" else {}
        prefix = directory.relative_to(root.path)
        known.update({(prefix / relative).as_posix(): value for relative, value in entries.items()})
        ledgers.append((path.relative_to(root.path).as_posix(), entries))
    return known, ledgers


def _unique_members(files: tuple[StagedFile, ...]) -> dict[str, StagedFile]:
    unique: dict[str, StagedFile] = {}
    for member in files:
        previous = unique.get(member.path)
        if previous and (previous.content, previous.mode) != (member.content, member.mode):
            raise ValueError(f"Conflicting staged output: {member.path}")
        unique[member.path] = (
            member
            if previous is None
            else replace(
                previous,
                logical_owners=tuple(sorted(set(previous.logical_owners + member.logical_owners))),
                surface_ids=tuple(sorted(set(previous.surface_ids + member.surface_ids))),
            )
        )
    return unique


def _add_ledgers(
    root: OperationRoot,
    ledgers: list[tuple[str, dict[str, tuple[str, int]]]],
    unique: dict[str, StagedFile],
    excluded: set[str],
    observed: list[BundleObservation],
    effects: list[PhysicalEffect],
    dispositions: list[Disposition],
) -> None:
    for ledger_path, old in ledgers:
        directory = Path(ledger_path).parent
        members = dict(old)
        for member in unique.values():
            if member.managed and Path(member.path).is_relative_to(directory) and member.path not in excluded:
                members[Path(member.path).relative_to(directory).as_posix()] = (sha256(member.content).hexdigest(), member.mode)
        content = json_bytes({"schema_version": 1, "owner": OWNER, "members": {p: {"sha256": h, "mode": mode} for p, (h, mode) in sorted(members.items())}})
        member = StagedFile(ledger_path, content, manifest=True)
        unique[ledger_path] = member
        before = next(o.state for o in reversed(observed) if o.path == root.path / ledger_path)
        _stage_effect(root, member, before, OwnershipProof("managed_path", f"bundle ownership manifest:{ledger_path}"), effects, dispositions)


def _stage_effect(
    root: OperationRoot,
    member: StagedFile,
    before: FileState,
    proof: OwnershipProof,
    effects: list[PhysicalEffect],
    dispositions: list[Disposition],
) -> None:
    after = FileState("file", sha256=sha256(member.content).hexdigest(), mode=member.mode)
    if before.kind == "absent":
        action = "create"
    elif before.kind != "file":
        action = "replace"
    elif before.sha256 != after.sha256:
        action = "update"
    elif before.mode != after.mode:
        action = "chmod"
    else:
        dispositions.append(Disposition(OWNER, root.root_id, member.path, "unchanged", "Staged bytes and mode are current"))
        return
    effects.append(
        PhysicalEffect(
            OWNER, "surface_repair", root, member.path, action, before, after, "Prepare staged bundle output", (proof,), member.logical_owners, member.surface_ids
        )
    )


def recheck_staging(assessment: OwnerAssessment) -> tuple[Diagnostic, ...]:
    """Refuse all writes if any retained input or destination has changed."""
    prepared = assessment.prepared
    if not assessment.complete or not isinstance(prepared, PreparedBundle):
        return (Diagnostic("incomplete_assessment", OWNER, "error", "Staged bundle preparation is incomplete"),)
    if prepared.root != assessment.root or prepared.consent != assessment.consent:
        return (Diagnostic("precondition_changed", OWNER, "error", "Retained bundle root or consent changed"),)
    try:
        if prepared.version is not None:
            from ._builder import get_cli_version

            if get_cli_version() != prepared.version:
                raise ValueError("Bundle package version changed")
        for item in prepared.observations:
            current = observe_bundle_path(item.path, members=item.children is not None)
            if not same_observation(current, _selected_provisioned_observation(assessment, item)):
                raise ValueError(f"Bundle precondition changed: {item.path}")
    except (OSError, ValueError) as exc:
        return (Diagnostic("precondition_changed", OWNER, "error", str(exc)),)
    return ()


@contextmanager
def staging_guard(assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
    """Hold existing supplier guards across the entire staged-owner application."""
    from ..providers.protocol import AssessingSurfaceProvider
    from ..service import build_providers

    prepared = assessment.prepared
    if not isinstance(prepared, PreparedBundle):
        yield recheck_staging(assessment)
        return
    providers = {p.provider_key: p for p in build_providers()}
    with ExitStack() as stack:
        diagnostics: list[Diagnostic] = []
        for supplier in prepared.suppliers:
            provider = providers.get(supplier.owner_key)
            if not isinstance(provider, AssessingSurfaceProvider):
                diagnostics.append(Diagnostic("bundle_supplier_unavailable", OWNER, "error", supplier.owner_key))
            else:
                diagnostics.extend(stack.enter_context(provider.recheck(supplier)))
        diagnostics.extend(recheck_staging(assessment))
        yield tuple(diagnostics)


def same_observation(current: BundleObservation, retained: BundleObservation) -> bool:
    """Retain directory mtimes, but do not confuse sibling activity with drift."""
    if current.state.kind == retained.state.kind == "directory" and retained.children is None:
        current = replace(current, state=replace(current.state, mtime_ns=retained.state.mtime_ns))
    return current == retained


def write_staged_file(path: Path, content: bytes, mode: int) -> None:
    """Atomically replace one staged regular file with retained bytes and mode."""
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            chmod_fd(stream.fileno(), temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_staging(assessment: OwnerAssessment, consent: ApplyConsent) -> OwnerApplyResult:
    """Apply only retained effects, publishing manifests last and reporting actual IDs."""
    ids = tuple(e.id for e in assessment.effects)
    if not consent.automatic or consent.overwrite_paths != assessment.consent.overwrite_paths:
        return OwnerApplyResult(OWNER, skipped=ids, outcome="skipped")
    run = _SELECTED_SKILL_BUNDLE.get()
    if run is not None and run.inputs.assessment is assessment:
        if run.attempted:
            return OwnerApplyResult(
                OWNER,
                skipped=ids,
                outcome="precondition_changed",
                diagnostics=(Diagnostic("precondition_changed", OWNER, "error", "Selected bundle application is single-consumption"),),
            )
        run.attempted = True
    with staging_guard(assessment) as errors:
        if errors:
            return OwnerApplyResult(OWNER, skipped=ids, diagnostics=errors, outcome="precondition_changed")
        result = _apply_staged_effects(assessment)
        if result.outcome == "applied":
            try:
                _finish_selected_stage(assessment)
            except (OSError, ValueError, KeyError) as exc:
                return replace(result, outcome="partial", diagnostics=(Diagnostic("precondition_changed", OWNER, "error", str(exc)),))
        return result


def _apply_staged_effects(assessment: OwnerAssessment) -> OwnerApplyResult:
    """Consume a retained, guarded batch without another assessment."""
    prepared = assessment.prepared
    assert isinstance(prepared, PreparedBundle)
    members = {m.path: m for m in prepared.files}
    effects = sorted(
        assessment.effects,
        key=lambda e: (
            0 if e.after.kind == "directory" else 3 if Path(e.path).name == _LEDGER else 2 if members[e.path].manifest else 1,
            len(Path(e.path).parts),
            e.path,
        ),
    )
    succeeded: list[str] = []
    failed: list[str] = []
    diagnostics: list[Diagnostic] = []
    pending: list[tuple[PhysicalEffect, BundleObservation]] = []
    for effect in effects:
        if effect.after.kind == "file" and members[effect.path].manifest and pending:
            _finalize_staged_directories(pending, succeeded, failed, diagnostics)
            if failed:
                break
        try:
            _record_selected_stage(assessment, effect, before=True)
            current = observe_confined(assessment.root.path, effect.destination)[-1].state
            if current != effect.before:
                raise ValueError(f"Staged destination changed during apply: {effect.path}")
            if effect.after.kind == "directory":
                assert effect.after.mode is not None
                # Restrictive final permissions must not prevent descendant writes.
                deferred = effect.after.mode & 0o700 != 0o700
                mode = 0o700 if deferred else effect.after.mode
                effect.destination.mkdir(mode=mode)
                effect.destination.chmod(mode)
                if deferred:
                    pending.append((effect, observe_confined(assessment.root.path, effect.destination)[-1]))
                    _record_selected_stage(assessment, effect, before=False)
                    continue
            else:
                member = members[effect.path]
                if member.wrapper:
                    from .claude_wrapper import write_wrappers

                    write_wrappers(effect.destination.parent.parent, prepared=(effect.destination, member.content, member.mode))
                elif member.manifest:
                    from ._builder import write_json

                    write_json(effect.destination, member.content, mode=member.mode)
                else:
                    write_staged_file(effect.destination, member.content, member.mode)
            _record_selected_stage(assessment, effect, before=False)
        except (OSError, ValueError) as exc:
            failed.append(effect.id)
            diagnostics.append(Diagnostic("bundle_write_failed", OWNER, "error", str(exc)))
            break
        succeeded.append(effect.id)
    _finalize_staged_directories(pending, succeeded, failed, diagnostics)
    completed = set(succeeded + failed)
    return OwnerApplyResult(
        OWNER,
        tuple(succeeded),
        tuple(failed),
        tuple(e.id for e in effects if e.id not in completed),
        tuple(diagnostics),
        ("partial" if succeeded else "failed") if failed else "applied",
    )


def _finalize_staged_directories(
    pending: list[tuple[PhysicalEffect, BundleObservation]],
    succeeded: list[str],
    failed: list[str],
    diagnostics: list[Diagnostic],
) -> None:
    """Finish only this apply's created directories, child-first, including on failure."""
    for effect, created in reversed(pending):
        try:
            current = observe_confined(effect.root.path, effect.destination)[-1]
            if not same_observation(current, created):
                raise ValueError(f"Staged directory changed before finalization: {effect.path}")
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(effect.destination, flags)
            try:
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)) != (created.device, created.inode, created.state.mode):
                    raise ValueError(f"Staged directory replaced during finalization: {effect.path}")
                assert effect.after.mode is not None
                chmod_fd(descriptor, effect.destination, effect.after.mode)
            finally:
                os.close(descriptor)
            final = observe_confined(effect.root.path, effect.destination)[-1]
            if not same_observation(final, replace(created, state=effect.after)):
                raise ValueError(f"Staged directory changed during finalization: {effect.path}")
        except (OSError, ValueError) as exc:
            failed.append(effect.id)
            diagnostics.append(Diagnostic("bundle_write_failed", OWNER, "error", f"Cannot finalize {effect.path}: {exc}"))
        else:
            succeeded.append(effect.id)
    pending.clear()
