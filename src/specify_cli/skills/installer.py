"""Retained canonical skill projections with separately coordinated global assets."""

from __future__ import annotations

import stat
import hashlib
import json
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from threading import RLock
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import cast
from charter.activation.compiler import _PreparedMissionTypeActivations, prepare_mission_type_activations
from charter.activation.charter_yaml_io import observe_yaml_input, yaml_documents_equal
from ruamel.yaml import YAML

from specify_cli.core.config import (
    AGENT_SKILL_CONFIG,
    SKILL_CLASS_SHARED,
    SKILL_CLASS_WRAPPER,
)
from specify_cli.core.atomic import atomic_write
from specify_cli.core.agent_config import AgentConfigError, load_agent_config
from specify_cli.core.no_follow import chmod_fd
from specify_cli.core.safe_delete import safe_rmdir as _safe_rmdir
from specify_cli.core.safe_delete import safe_unlink as _safe_unlink
from specify_cli.skills.command_renderer import ensure_skill_frontmatter
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    load_manifest,
    prepare_manifest,
    _parse_manifest,
)
from specify_cli.skills.paths import (
    get_primary_global_skill_root,
    get_primary_project_skill_root,
    SkillPathObservation,
    observe_skill_path,
    recheck_skill_paths,
    skill_path_observations,
)
from specify_cli.skills.command_installer import windows_dir_mode_only_divergence
from specify_cli.tool_surface.operations import (
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
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry

logger = logging.getLogger(__name__)

DELIVERY_COPY = "copy"
DELIVERY_SYMLINK = "symlink"


@dataclass(frozen=True)
class SkillBackupReplacement:
    """Stable replacement identity, excluding wall time and project location."""

    path: str
    before: FileState
    after: FileState


@dataclass(frozen=True)
class PreparedSkillBackup:
    root: Path
    observations: tuple[SkillPathObservation, ...]
    replacements: tuple[SkillBackupReplacement, ...]


def prepare_skill_backup(
    project_path: Path,
    replacements: tuple[SkillBackupReplacement, ...],
    *,
    explicit_root: Path | None = None,
) -> PreparedSkillBackup:
    """Allocate without writes; every occupied candidate remains user-owned."""
    if not replacements:
        raise ValueError("A skill backup requires replacements")
    ordered = tuple(sorted(replacements, key=lambda replacement: replacement.path))
    if len({replacement.path for replacement in ordered}) != len(ordered):
        raise ValueError("Duplicate skill backup path")
    records = []
    for replacement in ordered:
        relative = Path(replacement.path)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts or relative.as_posix() != replacement.path:
            raise ValueError(f"Unsafe skill backup path: {relative}")
        records.append(
            [
                relative.as_posix(),
                [replacement.before.kind, replacement.before.sha256, replacement.before.target, replacement.before.mode],
                [replacement.after.kind, replacement.after.sha256, replacement.after.target, replacement.after.mode],
            ]
        )
    serialized = json.dumps(["agent-skills-backup-v1", records], separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()  # noqa: TID251 -- deterministic backup identity, not charter hashing
    parent = _backup_parent(project_path)
    candidate = explicit_root or parent / f"state-v1-{digest}"
    if candidate.parent != parent:
        raise ValueError("Explicit skill backup must be a direct child of the managed backup parent")
    observations: list[SkillPathObservation] = []
    index = 0
    while True:
        current = skill_path_observations(project_path, candidate)
        observations.extend(current)
        if current[-1].state.kind == "absent":
            return PreparedSkillBackup(candidate, tuple(observations), ordered)
        if explicit_root is not None:
            raise FileExistsError(f"Skill backup already exists: {candidate}")
        index += 1
        candidate = parent / f"state-v1-{digest}-{index}"


def create_skill_backup(prepared: PreparedSkillBackup) -> Path:
    """Consume the chosen absence, refusing races rather than reallocating."""
    recheck_skill_paths(prepared.observations)
    for observed in prepared.observations:
        if observed.path == prepared.root:
            continue
        if observed.state.kind == "absent":
            observed.path.mkdir(mode=0o700)
    prepared.root.mkdir(mode=0o700)
    return prepared.root


def _backup_parent(project_path: Path) -> Path:
    """Return the established owner-local retained-backup directory."""
    return project_path / ".kittify" / ".migration-backup" / "agent-skills"


def _archive_existing_path(dest: Path, project_path: Path, backup_root: Path | None, *, after: FileState | None = None) -> Path:
    """Retain a file or literal link without following links or clobbering backups."""
    inputs = skill_path_observations(project_path, dest)
    before = inputs[-1].state
    if before.kind not in {"file", "symlink"}:
        raise ValueError(f"Cannot archive skill node: {dest}")
    if backup_root is None:
        allocation = prepare_skill_backup(project_path, (SkillBackupReplacement(dest.relative_to(project_path).as_posix(), before, after or FileState("absent")),))
        recheck_skill_paths(inputs)
        backup_root = create_skill_backup(allocation)
    elif backup_root.parent != _backup_parent(project_path):
        raise ValueError("Skill backup is outside the managed backup parent")
    backup_path = backup_root / dest.relative_to(project_path)
    backup_inputs = skill_path_observations(project_path, backup_path)
    if backup_inputs[-1].state.kind != "absent":
        raise FileExistsError(f"Skill backup member already exists: {backup_path}")
    recheck_skill_paths(inputs + backup_inputs)
    for observed in backup_inputs[:-1]:
        if observed.state.kind == "absent":
            observed.path.mkdir(mode=0o700)
    if before.kind == "symlink":
        assert before.target is not None
        backup_path.symlink_to(before.target)
        if before.mode is not None and stat.S_IMODE(backup_path.lstat().st_mode) != before.mode:
            backup_path.chmod(before.mode, follow_symlinks=False)
        if before.mtime_ns is not None:
            os.utime(backup_path, ns=(before.mtime_ns, before.mtime_ns), follow_symlinks=False)
    else:
        # Delegate the verbatim regular-file copy to the single asset-preservation
        # backup core (contract C1.5 / DIRECTIVE_044 single authority); it preserves
        # mode + mtime and refuses to clobber. The trailing _safe_unlink stays here,
        # in the wrapper, not in the copy-only core.
        from specify_cli.asset_preservation.backup import write_file_verbatim

        write_file_verbatim(dest, backup_path)
    recheck_skill_paths(inputs)
    _safe_unlink(dest)
    return backup_root


def _replacement_is_owned(manifest: ManagedSkillManifest | None, project_path: Path, dest: Path, before: FileState) -> bool:
    if manifest is None or before.kind != "file":
        return False
    owners = [entry for entry in manifest.entries if entry.installed_path == dest.relative_to(project_path).as_posix()]
    if not owners:
        return False
    for entry in owners:
        root = get_primary_project_skill_root(entry.agent_key)
        skill_name, source = Path(entry.skill_name), Path(entry.source_file)
        if root is None or len(skill_name.parts) != 1 or skill_name.is_absolute() or ".." in skill_name.parts:
            return False
        if source.is_absolute() or not source.parts or ".." in source.parts:
            return False
        if project_path / root / skill_name / source != dest:
            return False
        if entry.content_hash != f"sha256:{before.sha256}" or entry.delivery_mode != DELIVERY_COPY:
            return False
    return True


def _project_skill_file(
    source_file: Path,
    dest: Path,
    project_path: Path,
    *,
    backup_root: Path | None = None,
    archived_paths: list[Path] | None = None,
) -> tuple[str, Path | None]:
    """Project a global canonical skill file into the project.

    New files are portable copies (#2412). Unmodified manifest-owned files
    may be replaced with a retained backup. Unknown or modified content and
    unverified links return ``preserved`` without acquiring ownership.
    """
    inputs = skill_path_observations(project_path, dest)
    before = inputs[-1].state
    source = observe_skill_path(source_file)
    if source.state.kind != "file":
        raise ValueError(f"Canonical skill source is not a regular file: {source_file}")
    content = source_file.read_bytes()
    recheck_skill_paths(inputs + (source,))
    if before.kind == "file" and before.sha256 == source.state.sha256:
        return DELIVERY_COPY, backup_root
    if before.kind != "absent":
        manifest = load_manifest(project_path, strict=True)
        if not _replacement_is_owned(manifest, project_path, dest, before):
            return "preserved", backup_root
        recheck_skill_paths(inputs + (source,))
        backup_root = _archive_existing_path(dest, project_path, backup_root, after=source.state)
        if archived_paths is not None:
            archived_paths.append(backup_root / dest.relative_to(project_path))

    atomic_write(dest, content, mkdir=True)
    assert source.state.mode is not None
    dest.chmod(source.state.mode)
    return DELIVERY_COPY, backup_root


def _project_skill_files(
    skill: CanonicalSkill,
    target_skill_dir: Path,
    global_skill_dir: Path,
    project_path: Path,
    installation_class: str,
    agent_key: str,
    archived_paths: list[Path] | None = None,
) -> list[ManagedFileEntry]:
    """Project all files for one skill into the project and return manifest entries."""
    entries: list[ManagedFileEntry] = []
    now = now_utc_iso()
    backup_root: Path | None = None
    previous = load_manifest(project_path, strict=True)
    replacements = []
    observations: list[SkillPathObservation] = []
    for source_file in skill.all_files:
        relative = source_file.relative_to(skill.skill_dir)
        dest = target_skill_dir / relative
        destination_inputs = skill_path_observations(project_path, dest)
        source_inputs = skill_path_observations(global_skill_dir, global_skill_dir / relative)
        observations.extend(destination_inputs + source_inputs)
        before, after = destination_inputs[-1].state, source_inputs[-1].state
        if after.kind != "file":
            raise ValueError(f"Canonical skill source is not a regular file: {source_file}")
        if _replacement_is_owned(previous, project_path, dest, before) and before.sha256 != after.sha256:
            replacements.append(SkillBackupReplacement(dest.relative_to(project_path).as_posix(), before, after))
    if replacements:
        allocation = prepare_skill_backup(project_path, tuple(replacements))
        recheck_skill_paths(tuple(observations))
        backup_root = create_skill_backup(allocation)

    for source_file in skill.all_files:
        rel_within_skill = source_file.relative_to(skill.skill_dir)
        global_file = global_skill_dir / rel_within_skill
        dest = target_skill_dir / rel_within_skill
        delivery_mode, backup_root = _project_skill_file(
            global_file,
            dest,
            project_path,
            backup_root=backup_root,
            archived_paths=archived_paths,
        )
        if delivery_mode == "preserved":
            if previous is not None:
                entries.extend(
                    entry for entry in previous.entries if entry.installed_path == dest.relative_to(project_path).as_posix() and entry.agent_key == agent_key
                )
            continue
        entries.append(
            ManagedFileEntry(
                skill_name=skill.name,
                source_file=str(rel_within_skill),
                installed_path=str(dest.relative_to(project_path)),
                installation_class=installation_class,
                agent_key=agent_key,
                content_hash=compute_content_hash(dest),
                installed_at=now,
                delivery_mode=delivery_mode,
            )
        )

    return entries


def _make_entries_for_existing(
    skill: CanonicalSkill,
    target_skill_dir: Path,
    project_path: Path,
    installation_class: str,
    agent_key: str,
) -> list[ManagedFileEntry]:
    """Create manifest entries pointing to already-projected files."""
    entries: list[ManagedFileEntry] = []
    now = now_utc_iso()
    previous = load_manifest(project_path, strict=True)

    for source_file in skill.all_files:
        rel_within_skill = source_file.relative_to(skill.skill_dir)
        dest = target_skill_dir / rel_within_skill
        observations = skill_path_observations(project_path, dest)
        expected = source_file.read_bytes()
        if rel_within_skill == Path("SKILL.md"):
            expected = ensure_skill_frontmatter(expected.decode("utf-8"), skill.name).encode("utf-8")
        current = observations[-1].state
        if current.kind != "file" or dest.read_bytes() != expected:
            if previous is not None:
                entries.extend(
                    entry for entry in previous.entries if entry.installed_path == dest.relative_to(project_path).as_posix() and entry.agent_key == agent_key
                )
            continue
        recheck_skill_paths(observations)
        entries.append(
            ManagedFileEntry(
                skill_name=skill.name,
                source_file=str(rel_within_skill),
                installed_path=str(dest.relative_to(project_path)),
                installation_class=installation_class,
                agent_key=agent_key,
                content_hash=compute_content_hash(dest),
                installed_at=now,
                delivery_mode=DELIVERY_COPY,
            )
        )

    return entries


def install_skills_for_agent(
    project_path: Path,
    agent_key: str,
    skills: list[CanonicalSkill],
    *,
    shared_root_installed: set[str] | None = None,
    archived_paths: list[Path] | None = None,
) -> list[ManagedFileEntry]:
    """Install the actual caller selection through retained global/project owners."""
    if agent_key not in AGENT_SKILL_CONFIG:
        raise ValueError(f"Unknown agent key: {agent_key!r}")
    if AGENT_SKILL_CONFIG[agent_key]["class"] == SKILL_CLASS_WRAPPER:
        return []
    manifest = _install_caller_skills(project_path, (agent_key,), _CapturedSkillRegistry(tuple(skills)), archived_paths, retire=False)
    names = {skill.name for skill in skills}
    if shared_root_installed is not None and AGENT_SKILL_CONFIG[agent_key]["class"] == SKILL_CLASS_SHARED:
        shared_root_installed.update(names)
    return [entry for entry in manifest.entries if entry.agent_key == agent_key and entry.skill_name in names]


def install_all_skills(
    project_path: Path,
    agent_keys: list[str],
    registry: SkillRegistry,
    *,
    archived_paths: list[Path] | None = None,
) -> ManagedSkillManifest:
    """Prepare all selected agents once; caller retains manifest-save ownership."""
    return _install_caller_skills(project_path, tuple(agent_keys), registry, archived_paths, retire=True)


@dataclass(frozen=True)
class PreparedProjectSkillWrite:
    effect: PhysicalEffect
    content: bytes | None
    order: int


@dataclass(frozen=True)
class PreparedProjectSkills:
    root: OperationRoot
    consent: ApplyConsent
    observations: tuple[SkillPathObservation, ...]
    agent_config: str
    writes: tuple[PreparedProjectSkillWrite, ...]
    manifest_content: bytes
    provisioning: _PreparedMissionTypeActivations | None = None


def _prepare_skill_provisioning(root: Path, projected: object) -> _PreparedMissionTypeActivations | None:
    """Admit only the actual compiler descriptor, without changing skill selection."""
    if projected is None:
        return None
    if type(projected) is not _PreparedMissionTypeActivations:
        raise ValueError("Managed skills require the canonical mission provisioning descriptor")
    descriptor = cast(_PreparedMissionTypeActivations, projected)
    descriptor.write.recheck()
    if descriptor != prepare_mission_type_activations(root):
        raise ValueError("Managed skill provisioning differs from the canonical compiler")
    write = descriptor.write
    original = next(item for item in write.observations if item.path == write.target)
    if write.changed and original.identity is not None and original.identity[-1] != 1:
        raise ValueError("Managed skill provisioning cannot rewrite a hardlinked authority")
    # Skills render solely from the retained catalog and selected agents. The
    # compiler's mission-type field cannot alter agent/config selection policy.
    documents = tuple(YAML(typ="rt").load(content or b"") for content in (write.before_bytes, write.desired_bytes))
    if any(document is not None and not isinstance(document, dict) for document in documents):
        raise ValueError("Managed skill provisioning requires mapping inputs")
    before, after = (document if document is not None else {} for document in documents)
    before.pop("mission_type_activations", None)
    after.pop("mission_type_activations", None)
    if not yaml_documents_equal(before, after):
        raise ValueError("Provisioning changes skill-relevant configuration")
    return descriptor


def _recheck_skill_provisioning(
    prepared: PreparedProjectSkills,
    *,
    provisioning_applied: bool,
) -> Path | None:
    """Allow only the retained compiler's direct-file transition, never a hash waiver."""
    provisioning = prepared.provisioning
    if provisioning is None:
        return None
    write = provisioning.write
    if not provisioning_applied or not write.changed:
        write.recheck()
        return None
    if _skill_bytes_state(write.desired_bytes, write.mode).sha256 != write.desired_sha256:
        raise ValueError("Managed skill provisioning bytes changed")
    if write.before_bytes is None:
        write.recheck_applied()
        return cast(Path, write.target)
    original = next(item for item in write.observations if item.path == write.target)
    current = observe_yaml_input(write.target)
    prior, actual = original.identity, current.identity
    if (
        current.content != write.desired_bytes
        or prior is None
        or actual is None
        or len(prior) != 7
        or len(actual) != 7
        or actual[:3] != prior[:3]
        or prior[-1] != 1
        or actual[-1] != 1
        or actual[5] != len(write.desired_bytes)
        or actual[3] < prior[3]
        or actual[4] < prior[4]
    ):
        raise ValueError("Managed skill provisioning has not completed its exact retained transition")
    for observation in write.observations:
        if observation.path != write.target and observe_yaml_input(observation.path) != observation:
            raise ValueError(f"Managed skill provisioning input changed: {observation.path}")
    target: Path = write.target
    return target


_PROJECT_SKILL_LOCK = RLock()
_RECHECKED_PROJECT: ContextVar[OwnerAssessment | None] = ContextVar("rechecked_project_skills", default=None)
_COMMAND_PARENTS: ContextVar[tuple[OwnerAssessment, tuple[SkillPathObservation, ...]] | None] = ContextVar(
    "managed_skill_command_parents",
    default=None,
)


@contextmanager
def _completed_command_parents(
    assessment: OwnerAssessment,
    created: tuple[SkillPathObservation, ...],
) -> Iterator[None]:
    """Scope actual command-writer parent receipts to one retained project batch."""
    token = _COMMAND_PARENTS.set((assessment, created))
    try:
        yield
    finally:
        _COMMAND_PARENTS.reset(token)


def _command_parent_receipts(assessment: OwnerAssessment) -> dict[Path, SkillPathObservation]:
    admitted = _COMMAND_PARENTS.get()
    if admitted is None or admitted[0] != assessment:
        return {}
    receipts = {item.path: item for item in admitted[1]}
    for path, item in receipts.items():
        matches = [e for e in assessment.effects if e.destination == path]
        if len(matches) != 1:
            raise ValueError(f"Invalid command-created skill parent: {path}")
        effect = matches[0]
        # #4776: on Windows a freshly-created shared parent cannot carry the
        # planned POSIX 0o755, so accept a directory whose sole divergence from
        # the plan is that host-unrepresentable mode (dir-scoped, host-gated via
        # kernel.paths.is_windows). POSIX drift still refuses (NFR-003).
        after_matches = effect.after == item.state or windows_dir_mode_only_divergence(item.state, effect.after)
        if effect.before.kind != "absent" or not after_matches or item.identity is None or item.state.kind != "directory":
            raise ValueError(f"Invalid command-created skill parent: {path}")
    recheck_skill_paths(tuple(receipts.values()))
    return receipts


def _agent_config_identity() -> str:
    return json.dumps({"agents": AGENT_SKILL_CONFIG, "global_home": str(Path.home())}, sort_keys=True, separators=(",", ":"))


def _skill_bytes_state(content: bytes, mode: int) -> FileState:
    return FileState("file", sha256=hashlib.sha256(content).hexdigest(), mode=mode)  # noqa: TID251 -- concrete managed-skill bytes


def _valid_skill_entry(entry: ManagedFileEntry) -> bool:
    root = get_primary_project_skill_root(entry.agent_key)
    name, source = Path(entry.skill_name), Path(entry.source_file)
    if root is None or name.is_absolute() or len(name.parts) != 1 or ".." in name.parts:
        return False
    if source.is_absolute() or not source.parts or ".." in source.parts:
        return False
    return (Path(root) / name / source).as_posix() == entry.installed_path


def _managed_link(entry: ManagedFileEntry, destination: Path, before: FileState) -> bool:
    root = get_primary_global_skill_root(entry.agent_key)
    if before.kind != "symlink" or entry.delivery_mode != DELIVERY_SYMLINK or root is None:
        return False
    assert before.target is not None
    literal = Path(os.path.normpath(destination.parent / before.target))
    return literal == root / entry.skill_name / entry.source_file


class _ProjectSkillPreparation:
    """Mutable assessment-local accumulator; only frozen bytes escape preparation."""

    def __init__(self, inputs: AssessmentInputs, persist_manifest: bool = True) -> None:
        self.inputs = inputs
        self.persist_manifest = persist_manifest
        self.observations: list[SkillPathObservation] = []
        self.writes: list[PreparedProjectSkillWrite] = []
        self.dispositions: list[Disposition] = []
        self.provisioning: _PreparedMissionTypeActivations | None = None

    def observe(self, path: str) -> FileState:
        observations = skill_path_observations(self.inputs.root.path, self.inputs.root.path / path)
        self.observations.extend(observations)
        return observations[-1].state

    def validate_config(self) -> None:
        state = self.observe(".kittify/config.yaml")
        if state.kind == "file":
            load_agent_config(self.inputs.root.path)
        elif state.kind != "absent":
            raise ValueError("Project agent config is not a regular file")

    def disposition(self, path: str, state: str, reason: str) -> None:
        self.dispositions.append(Disposition("managed_skills", self.inputs.root.root_id, path, state, reason))

    def write(
        self,
        path: str,
        before: FileState,
        after: FileState,
        content: bytes | None,
        owners: tuple[ManagedFileEntry, ...],
        order: int,
        reason: str,
        proof_kind: str = "manifest",
        *,
        consumers: tuple[ManagedFileEntry, ...] | None = None,
    ) -> None:
        if before.kind == after.kind == "absent":
            return
        if before.kind == "absent":
            action = "create"
        elif after.kind == "absent":
            action = "delete"
        elif before.kind != after.kind:
            action = "replace"
        elif before.sha256 != after.sha256:
            action = "update"
        elif before.target != after.target:
            action = "retarget"
        elif before.mode != after.mode:
            action = "chmod"
        else:
            return
        proofs = tuple(
            OwnershipProof(
                proof_kind,
                (
                    f".kittify/skills-manifest.json:{entry.agent_key}:{entry.installed_path}"
                    if proof_kind == "manifest"
                    else f"canonical-skill:{entry.skill_name}/{entry.source_file}:{entry.content_hash}"
                ),
            )
            for entry in owners
        )
        if not proofs:
            proofs = (OwnershipProof("managed_path", f"managed-skills:{path}"),)
        affected = owners if consumers is None else consumers
        effect = PhysicalEffect(
            "managed_skills",
            "surface_repair",
            self.inputs.root,
            path,
            action,
            before,
            after,
            reason,
            proofs,
            tuple(entry.agent_key for entry in affected) or ("managed_skills",),
            tuple(f"{entry.agent_key}.doctrine_skill.{entry.skill_name}.{entry.source_file.replace('/', '.')}" for entry in affected),
        )
        self.writes.append(PreparedProjectSkillWrite(effect, content, order))

    def parents(self) -> None:
        existing_writes = tuple(self.writes)
        directories: dict[str, PhysicalEffect] = {}
        for write in existing_writes:
            if write.effect.after.kind == "absent":
                continue
            for parent in reversed(Path(write.effect.path).parents):
                if parent == Path("."):
                    continue
                path = parent.as_posix()
                before = self.observe(path)
                if before.kind != "absent":
                    continue
                if self.provisioning is not None and self.inputs.root.path / path in self.provisioning.write.absent_parents:
                    continue  # The canonical YAML writer owns these directory creates.
                mode = 0o700 if path.startswith(".kittify/.migration-backup") else 0o755
                effect = replace(
                    write.effect, path=path, action="create", before=before, after=FileState("directory", mode=mode), reason="Create managed-skill parent"
                )
                previous = directories.get(path)
                if previous is not None:
                    effect = coalesce_effects((previous, effect))[0]
                directories[path] = effect
        self.writes.extend(PreparedProjectSkillWrite(effect, None, 0) for effect in directories.values())

    def prune(self, retired: tuple[ManagedFileEntry, ...]) -> None:
        deleted = {write.effect.path for write in self.writes if write.effect.after.kind == "absent"}
        candidates: set[Path] = set()
        for entry in retired:
            root = get_primary_project_skill_root(entry.agent_key)
            assert root is not None
            stop = Path(root) / entry.skill_name
            current = Path(entry.installed_path).parent
            while current.is_relative_to(stop):
                candidates.add(current)
                if current == stop:
                    break
                current = current.parent
        for relative in sorted(candidates, key=lambda path: (-len(path.parts), path.as_posix())):
            before = self.observe(relative.as_posix())
            if before.kind != "directory":
                continue
            observation = observe_skill_path(self.inputs.root.path / relative, members=True)
            self.observations.append(observation)
            assert observation.children is not None
            if all((relative / name).as_posix() in deleted for name in observation.children):
                owners = tuple(entry for entry in retired if Path(entry.installed_path).is_relative_to(relative))
                self.write(relative.as_posix(), before, FileState("absent"), None, owners, 3, "Prune empty retired skill directory")
                deleted.add(relative.as_posix())


def assess_project_skills(
    inputs: AssessmentInputs,
    registry: SkillRegistry,
    agent_keys: tuple[str, ...],
    *,
    selected_paths: tuple[str, ...] | None = None,
    retire: bool = True,
    persist_manifest: bool = True,
) -> OwnerAssessment:
    """Prepare the complete PROJECT contribution, never a global bootstrap substitute.

    The provider must compose the separately prepared global owner before it can
    claim full completeness. Direct verifier repair is historically project-only.
    """
    plan = _ProjectSkillPreparation(inputs, persist_manifest)
    try:
        if inputs.root.scope == "global":
            raise ValueError("Project skill assessment requires concrete project inputs")
        plan.provisioning = _prepare_skill_provisioning(inputs.root.path, inputs.projected)
        return _prepare_project_skills(plan, registry, tuple(sorted(set(agent_keys))), selected_paths, retire)
    except (OSError, ValueError, TypeError, AgentConfigError) as exc:
        return OwnerAssessment(
            "managed_skills",
            inputs.root,
            complete=False,
            consent=inputs.consent,
            diagnostics=(Diagnostic("skill_assessment_failed", "managed_skills", "error", str(exc)),),
        )


def _expected_project_entries(
    skills: tuple[CanonicalSkill, ...],
    agents: tuple[str, ...],
    now: str,
) -> dict[str, tuple[bytes, FileState, list[ManagedFileEntry]]]:
    expected: dict[str, tuple[bytes, FileState, list[ManagedFileEntry]]] = {}
    for agent in agents:
        if agent not in AGENT_SKILL_CONFIG:
            raise ValueError(f"Unknown agent key: {agent!r}")
        root = get_primary_project_skill_root(agent)
        if root is None:
            continue
        for skill in skills:
            for source in skill.all_files:
                relative = source.relative_to(skill.skill_dir).as_posix()
                path = (Path(root) / skill.name / relative).as_posix()
                source_content = source.read_bytes()
                if relative == "SKILL.md":
                    source_content = ensure_skill_frontmatter(source_content.decode("utf-8"), skill.name).encode("utf-8")
                state = _skill_bytes_state(source_content, stat.S_IMODE(source.stat().st_mode) & ~0o222)
                entry = ManagedFileEntry(skill.name, relative, path, str(AGENT_SKILL_CONFIG[agent]["class"]), agent, f"sha256:{state.sha256}", now)
                if not _valid_skill_entry(entry):
                    raise ValueError(f"Unsafe canonical skill path: {path}")
                if path in expected:
                    prior_content, prior_state, shared_owners = expected[path]
                    if (prior_content, prior_state) != (source_content, state):
                        raise ValueError(f"Conflicting shared skill sources: {path}")
                    shared_owners.append(entry)
                else:
                    expected[path] = source_content, state, [entry]
    return expected


def _reject_provisioning_source_overlap(
    provisioning: _PreparedMissionTypeActivations | None,
    skills: tuple[CanonicalSkill, ...],
) -> None:
    if provisioning is not None and any(source.resolve() == provisioning.write.target for skill in skills for source in skill.all_files):
        raise ValueError("Mission provisioning overlaps canonical skill input")


def _prepare_project_skills(
    plan: _ProjectSkillPreparation,
    registry: SkillRegistry,
    agents: tuple[str, ...],
    selected_paths: tuple[str, ...] | None,
    retire: bool,
) -> OwnerAssessment:
    project = plan.inputs.root.path
    config = _agent_config_identity()
    plan.validate_config()
    plan.observe(".kittify/skills-manifest.json")
    previous = load_manifest(project, strict=True)
    manifest = replace(previous, entries=[replace(entry) for entry in previous.entries]) if previous else ManagedSkillManifest()
    if any(not _valid_skill_entry(entry) for entry in manifest.entries):
        raise ValueError("Skills manifest contains an invalid ownership path")
    skills, catalog_inputs = registry.snapshot_catalog()
    _reject_provisioning_source_overlap(plan.provisioning, skills)
    plan.observations.extend(catalog_inputs)
    now = now_utc_iso()
    expected = _expected_project_entries(skills, agents, now)
    backups: list[tuple[SkillBackupReplacement, bytes | None, tuple[ManagedFileEntry, ...], tuple[ManagedFileEntry, ...]]] = []
    retired_entries: list[ManagedFileEntry] = []
    paths = set(expected)
    if selected_paths is not None:
        paths.intersection_update(selected_paths)
    if retire and skills:
        paths.update(entry.installed_path for entry in manifest.entries if entry.agent_key in agents and entry.installed_path not in expected)
    for path in sorted(paths):
        before = plan.observe(path)
        owners = tuple(entry for entry in manifest.entries if entry.installed_path == path)
        wanted = expected.get(path)
        selected_owners = tuple(entry for entry in owners if entry.agent_key in agents)
        if wanted is None and any(entry.agent_key not in agents for entry in owners):
            manifest.entries = [entry for entry in manifest.entries if entry not in selected_owners]
            plan.disposition(path, "preserve", "Unselected logical owners retain this shared file")
            continue
        content, after, new_owners = wanted if wanted is not None else (None, FileState("absent"), [])
        managed = bool(owners)
        unchanged_owned = managed and (
            before.kind == "file"
            and all(entry.delivery_mode == DELIVERY_COPY and entry.content_hash == f"sha256:{before.sha256}" for entry in owners)
            or before.kind == "symlink"
            and all(_managed_link(entry, project / path, before) for entry in owners)
        )
        canonical = wanted is not None and before.kind == "file" and before.sha256 == after.sha256
        if _preserve_project_path(plan, path, before, managed, canonical, unchanged_owned):
            continue
        effect_owners = owners or tuple(new_owners)
        # New consumers share the effect, but cannot fabricate prior manifest proof.
        consumers = owners + tuple(new_owners)
        if before.kind in {"file", "symlink"} and not canonical and (after.kind != "absent" or not unchanged_owned):
            old_bytes = (project / path).read_bytes() if before.kind == "file" else None
            backups.append((SkillBackupReplacement(path, before, after), old_bytes, effect_owners, consumers))
        plan.write(
            path, before, after, content, effect_owners, 2, "Reconcile selected managed skill", "manifest" if owners else "canonical_content", consumers=consumers
        )
        if wanted is None:
            manifest.entries = [entry for entry in manifest.entries if entry.installed_path != path]
            retired_entries.extend(selected_owners)
        else:
            for entry in new_owners:
                manifest.add_entry(entry)
            # Other agents sharing the physical file retain their logical ownership.
            for entry in owners:
                if entry.agent_key not in agents:
                    manifest.add_entry(replace(entry, content_hash=f"sha256:{after.sha256}", delivery_mode=DELIVERY_COPY))
        if not any(write.effect.path == path for write in plan.writes):
            plan.disposition(path, "unchanged", "Managed content is already current")
    if backups:
        allocation = prepare_skill_backup(project, tuple(item[0] for item in backups))
        plan.observations.extend(allocation.observations)
        for replacement, content, owners, consumers in backups:
            path = (allocation.root / replacement.path).relative_to(project).as_posix()
            plan.write(path, FileState("absent"), replacement.before, content, owners, 1, "Retain managed skill before replacement", consumers=consumers)
    plan.prune(tuple(retired_entries))
    return _finish_project_preparation(plan, manifest, previous, now, config)


def _finish_project_preparation(
    plan: _ProjectSkillPreparation,
    manifest: ManagedSkillManifest,
    previous: ManagedSkillManifest | None,
    now: str,
    config: str,
) -> OwnerAssessment:
    prepared_manifest = prepare_manifest(manifest, plan.inputs.root.path, operation_time=now)
    plan.observations.extend(prepared_manifest.observations)
    if prepared_manifest.changed and plan.persist_manifest and (manifest.entries or previous is not None):
        plan.write(
            ".kittify/skills-manifest.json",
            prepared_manifest.observations[-1].state,
            _skill_bytes_state(prepared_manifest.content, prepared_manifest.mode),
            prepared_manifest.content,
            tuple(manifest.entries) or tuple(previous.entries if previous else ()),
            4,
            "Persist prepared skills manifest",
        )
    plan.parents()
    recheck_skill_paths(tuple(plan.observations))
    if config != _agent_config_identity():
        raise ValueError("Agent skill configuration changed during assessment")
    effects = coalesce_effects(tuple(write.effect for write in plan.writes))
    by_path = {effect.path: effect for effect in effects}
    writes = tuple(sorted((replace(write, effect=by_path[write.effect.path]) for write in plan.writes), key=_project_write_sort_key))
    prepared = PreparedProjectSkills(plan.inputs.root, plan.inputs.consent, tuple(plan.observations), config, writes, prepared_manifest.content, plan.provisioning)
    if plan.provisioning is not None and any(
        item.path != plan.inputs.root.path / ".kittify/config.yaml" and item.state.kind == "file" and item.path.resolve() == plan.provisioning.write.target
        for item in plan.observations
    ):
        raise ValueError("Mission provisioning overlaps managed skill state")
    _recheck_skill_provisioning(prepared, provisioning_applied=False)
    return OwnerAssessment(
        "managed_skills",
        plan.inputs.root,
        effects,
        tuple(plan.dispositions),
        inputs_fingerprint=(
            InputObservation("project_skill_inputs", prepared.observations),
            InputObservation("agent_skill_config", config),
            InputObservation("skill_provisioning", prepared.provisioning),
        ),
        prepared=prepared,
        consent=plan.inputs.consent,
    )


def _preserve_project_path(
    plan: _ProjectSkillPreparation,
    path: str,
    before: FileState,
    managed: bool,
    canonical: bool,
    unchanged_owned: bool,
) -> bool:
    if before.kind == "directory" or (before.kind != "absent" and not managed and not canonical):
        plan.disposition(path, "preserve", "Unknown content is not owned by the skill manager")
    elif before.kind == "symlink" and not unchanged_owned:
        plan.disposition(path, "preserve", "Unverified link target is not managed")
    elif before.kind != "absent" and not unchanged_owned and not canonical and path not in plan.inputs.consent.overwrite_paths:
        plan.disposition(path, "consent_required", "Modified managed content requires exact-path overwrite consent")
    else:
        return False
    return True


def _project_write_sort_key(write: PreparedProjectSkillWrite) -> tuple[int, int, str]:
    depth = len(Path(write.effect.path).parts)
    return write.order, -depth if write.order == 3 else depth, write.effect.path


@contextmanager
def recheck_project_skills(
    assessment: OwnerAssessment,
    *,
    provisioning_applied: bool = False,
) -> Iterator[tuple[Diagnostic, ...]]:
    """Hold the process-local owner boundary; no pre-existing skill lock file exists."""
    with _PROJECT_SKILL_LOCK:
        prepared = assessment.prepared
        try:
            if assessment.owner_key != "managed_skills" or not isinstance(prepared, PreparedProjectSkills) or not assessment.complete:
                raise ValueError("Project skill assessment is incomplete or invalid")
            if (assessment.root, assessment.consent, assessment.effects) != (
                prepared.root,
                prepared.consent,
                coalesce_effects(tuple(write.effect for write in prepared.writes)),
            ) or any(item.severity == "error" for item in assessment.diagnostics):
                raise ValueError("Project skill assessment does not match its retained preparation")
            if assessment.inputs_fingerprint != (
                InputObservation("project_skill_inputs", prepared.observations),
                InputObservation("agent_skill_config", prepared.agent_config),
                InputObservation("skill_provisioning", prepared.provisioning),
            ):
                raise ValueError("Project skill inputs differ from retained preparation")
            transitioned = _recheck_skill_provisioning(prepared, provisioning_applied=provisioning_applied)
            command_parents = _command_parent_receipts(assessment)
            changed_config: Path | None = prepared.root.path / ".kittify/config.yaml"
            if transitioned != prepared.root.path.resolve() / ".kittify/config.yaml":
                changed_config = None
            provisioning_parents = prepared.provisioning.write.absent_parents if transitioned is not None and prepared.provisioning is not None else ()
            observations = []
            for item in prepared.observations:
                if item.path == changed_config or item.path in provisioning_parents:
                    continue
                item = command_parents.get(item.path, item)
                if transitioned is not None and prepared.provisioning is not None and prepared.provisioning.write.before_bytes is None:
                    additions = tuple(path.name for path in (*provisioning_parents, transitioned) if path.parent == item.path)
                    if additions and item.children is not None:
                        item = replace(item, children=tuple(sorted((*item.children, *additions))))
                observations.append(item)
            recheck_skill_paths(tuple(observations))
            if prepared.agent_config != _agent_config_identity():
                raise ValueError("Agent skill configuration changed")
        except (OSError, ValueError) as exc:
            yield (Diagnostic("precondition_changed", "managed_skills", "error", str(exc)),)
            return
        token = _RECHECKED_PROJECT.set(assessment if prepared.provisioning is None or provisioning_applied else None)
        try:
            yield ()
        finally:
            _RECHECKED_PROJECT.reset(token)


def _apply_project_skill_write(write: PreparedProjectSkillWrite) -> None:
    effect, content = write.effect, write.content
    path, after = effect.destination, effect.after
    current = skill_path_observations(effect.root.path, path)[-1].state
    if current != effect.before:
        raise ValueError(f"Managed-skill destination changed during apply: {path}")
    if after.kind == "absent":
        _safe_rmdir(path) if current.kind == "directory" else _safe_unlink(path)
    elif after.kind == "directory":
        path.mkdir(mode=after.mode or 0o755)
        path.chmod(after.mode if after.mode is not None else 0o755)
    elif effect.action == "chmod":
        assert after.mode is not None
        path.chmod(after.mode, follow_symlinks=False)
    elif after.kind == "symlink":
        assert after.target is not None
        path.symlink_to(after.target)
        if stat.S_IMODE(path.lstat().st_mode) != after.mode:
            assert after.mode is not None
            path.chmod(after.mode, follow_symlinks=False)
    else:
        assert content is not None and after.mode is not None
        if current.kind == "absent":
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, after.mode)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                chmod_fd(stream.fileno(), path, after.mode)
        else:
            atomic_write(path, content)
            path.chmod(after.mode)
    if after.kind in {"file", "symlink"} and after.mtime_ns is not None:
        os.utime(path, ns=(after.mtime_ns, after.mtime_ns), follow_symlinks=False)


def apply_project_skills(assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
    """Consume a guarded batch once; never rerender or reassess after writing."""
    prepared = assessment.prepared
    ids = tuple(effect.id for effect in assessment.effects)
    guarded = _RECHECKED_PROJECT.get()
    if guarded is None or guarded is not assessment or not isinstance(prepared, PreparedProjectSkills) or not assessment.complete:
        return OwnerApplyResult(
            "managed_skills",
            skipped=ids,
            outcome="precondition_changed",
            diagnostics=(Diagnostic("precondition_changed", "managed_skills", "error", "Project skill batch was not successfully rechecked"),),
        )
    _RECHECKED_PROJECT.set(None)
    if not explicit_consent.automatic or explicit_consent != assessment.consent:
        return OwnerApplyResult(
            "managed_skills",
            skipped=ids,
            outcome="skipped",
            diagnostics=(Diagnostic("consent_required", "managed_skills", "error", "Apply requires the exact prepared consent"),),
        )
    succeeded: list[str] = []
    try:
        delegated = _command_parent_receipts(assessment)
    except (OSError, ValueError) as exc:
        return OwnerApplyResult(
            "managed_skills", skipped=ids, outcome="precondition_changed", diagnostics=(Diagnostic("precondition_changed", "managed_skills", "error", str(exc)),)
        )
    skipped: list[str] = []
    for index, write in enumerate(prepared.writes):
        if write.effect.destination in delegated:
            skipped.append(write.effect.id)
            continue
        try:
            _apply_project_skill_write(write)
        except (OSError, ValueError) as exc:
            return OwnerApplyResult(
                "managed_skills",
                tuple(succeeded),
                (write.effect.id,),
                tuple(skipped) + tuple(item.effect.id for item in prepared.writes[index + 1 :]),
                (Diagnostic("skill_write_failed", "managed_skills", "error", str(exc)),),
                "partial" if succeeded else "failed",
            )
        succeeded.append(write.effect.id)
    return OwnerApplyResult("managed_skills", tuple(succeeded), skipped=tuple(skipped))


class _CapturedSkillRegistry(SkillRegistry):
    """Assessment-local caller inventory; never rediscovered after global writes."""

    def __init__(self, skills: tuple[CanonicalSkill, ...], observations: tuple[SkillPathObservation, ...] = ()) -> None:
        self._skills = tuple(replace(skill, references=list(skill.references), scripts=list(skill.scripts), assets=list(skill.assets)) for skill in skills)
        self._observations = observations

    def discover_skills(self) -> list[CanonicalSkill]:
        return list(self._skills)

    def snapshot_catalog(self) -> tuple[tuple[CanonicalSkill, ...], tuple[SkillPathObservation, ...]]:
        observations = list(self._observations)
        for skill in self._skills:
            for path in (skill.skill_dir, *(skill.skill_dir / name for name in ("references", "scripts", "assets"))):
                inputs = skill_path_observations(skill.skill_dir, path)
                observations.extend(inputs)
                if inputs[-1].state.kind not in {"directory", "absent"}:
                    raise ValueError(f"Canonical skill directory is unsafe: {path}")
                observations.append(observe_skill_path(path, members=True))
            for source in skill.all_files:
                inputs = skill_path_observations(skill.skill_dir, source)
                if inputs[-1].state.kind != "file":
                    raise ValueError(f"Canonical source is not a regular file: {source}")
                observations.extend(inputs)
        retained = tuple(observations)
        recheck_skill_paths(retained)
        return self._skills, retained


@dataclass(frozen=True)
class SkillInstallationAssessment:
    """Two separately executable owners, including ONE coordinated global batch."""

    global_assets: OwnerAssessment
    project_skills: OwnerAssessment
    agent_keys: tuple[str, ...]


def assess_skill_installation(
    inputs: AssessmentInputs,
    registry: SkillRegistry,
    agent_keys: tuple[str, ...],
    *,
    runtime: bool = False,
    commands: bool = False,
    command_agent_keys: list[str] | None = None,
    retire: bool = True,
    persist_manifest: bool = True,
) -> SkillInstallationAssessment:
    """Gather caller selection before one coordinated global assessment.

    Upgrade composition can include runtime/commands in this SAME call. Dispatch
    the returned global_assets once, never alongside another cold global batch.
    Project preparation uses canonical retained sources, not staged global files.
    """
    from specify_cli.runtime.agent_skills import GlobalSkillSelection
    from specify_cli.runtime.asset_preparation import assess_global_assets

    agents = tuple(sorted(set(agent_keys)))
    skills, observations = registry.snapshot_catalog()
    captured = _CapturedSkillRegistry(skills, observations)
    selection = GlobalSkillSelection(skills=skills, agent_keys=agents)
    project = assess_project_skills(inputs, captured, agents, retire=retire, persist_manifest=persist_manifest)
    global_assets = assess_global_assets(runtime=runtime, commands=commands, agent_keys=command_agent_keys, skill_selection=selection, consent=inputs.consent)
    return SkillInstallationAssessment(global_assets, project, agents)


def apply_skill_installation(
    installation: SkillInstallationAssessment,
    consent: ApplyConsent,
    *,
    rebuild_global_assets: Callable[[], OwnerAssessment] | None = None,
) -> tuple[OwnerApplyResult, OwnerApplyResult]:
    """Direct-call boundary: recheck BOTH roots before the first global write.

    #4174 landing-pass: this is a direct-call boundary OUTSIDE the
    ``bootstrap.ensure_runtime()`` / ``agent_commands.py`` / ``agent_skills.py``
    ``ensure_*`` graph -- it never re-assessed under the lock, so two
    independent concurrent installer invocations racing the same cold home
    reproduced the residual symptom the #4017 mission notes recorded: the
    winner materializes the global bundle for real, and the loser's own
    STALE assessment still carries ``create`` actions for paths the winner
    already created, non-idempotently replayed by ``apply_assets`` as a
    ``global_asset_write_failed: File exists``.

    When *rebuild_global_assets* is given, mirror
    ``asset_preparation.apply_with_reassess`` for the GLOBAL half only:
    re-assess under the ALREADY-HELD anchor lock (the nested
    ``apply_with_reassess`` call below reuses the SAME lock this function's
    own ``recheck_assets(global_assets)`` already acquired, via the
    ``_HELD_LOCKS`` short-circuit) and converge to a no-op when a peer
    already did the work. The PROJECT half's own ``recheck_project_skills``
    boundary is never rebuilt: ``apply_project_skills`` requires
    object-IDENTITY with whatever ``recheck_project_skills`` guarded, so
    the project assessment stays exactly what the caller passed in. Both
    locks are acquired in the SAME order as the *rebuild_global_assets is
    None* path (global first, then project) by keeping this structure --
    never split into two separate ``with`` statements.
    """
    from specify_cli.runtime.asset_preparation import apply_assets, apply_with_reassess, recheck_assets

    global_assets, project = installation.global_assets, installation.project_skills
    if isinstance(project.prepared, PreparedProjectSkills) and project.prepared.provisioning is not None:
        errors = (
            Diagnostic("paired_skill_preflight_required", "managed_skills", "error", "Provisioning requires the provider's paired preflight_installation boundary"),
        )
        return _refuse_skill_owner(global_assets, errors), _refuse_skill_owner(project, errors)
    if not global_assets.complete or not project.complete:
        return _refuse_skill_owner(global_assets, global_assets.diagnostics), _refuse_skill_owner(project, project.diagnostics)
    with recheck_assets(global_assets) as global_errors, recheck_project_skills(project) as project_errors:
        if global_errors or project_errors:
            errors = global_errors + project_errors
            return _refuse_skill_owner(global_assets, errors), _refuse_skill_owner(project, errors)
        if rebuild_global_assets is not None and global_assets.effects:
            # Only reassess when there is actually something to converge --
            # mirroring the ensure_*() owners' own "not assessment.effects:
            # return" guard before ever calling apply_with_reassess. Without
            # this, an ordinary warm/no-op apply would pay for a needless
            # extra assess on every call.
            global_result = apply_with_reassess(
                global_assets,
                rebuild_global_assets,
                consent,
                converged_log_message="global skill/command assets already materialized by a concurrent peer; nothing applied.",
                logger=logger,
            )
        else:
            global_result = apply_assets(global_assets, consent)
        if global_result.outcome not in {"applied", "skipped"} or (global_result.skipped and global_assets.effects):
            return global_result, _refuse_skill_owner(project, global_result.diagnostics)
        return global_result, apply_project_skills(project, consent)


def _refuse_skill_owner(owner: OwnerAssessment, diagnostics: tuple[Diagnostic, ...]) -> OwnerApplyResult:
    return OwnerApplyResult(owner.owner_key, skipped=tuple(effect.id for effect in owner.effects), outcome="precondition_changed", diagnostics=diagnostics)


def _install_caller_skills(
    project_path: Path,
    agents: tuple[str, ...],
    registry: SkillRegistry,
    archived_paths: list[Path] | None,
    *,
    retire: bool,
) -> ManagedSkillManifest:
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project_path.absolute()), consent=consent)
    installation = assess_skill_installation(inputs, registry, agents, retire=retire, persist_manifest=False)
    results = apply_skill_installation(
        installation,
        consent,
        rebuild_global_assets=lambda: assess_skill_installation(inputs, registry, agents, retire=retire, persist_manifest=False).global_assets,
    )
    if any(result.outcome not in {"applied", "skipped"} for result in results):
        errors = "; ".join(item.message for result in results for item in result.diagnostics)
        raise OSError(f"Managed skill installation did not complete: {errors}")
    project = installation.project_skills
    if archived_paths is not None:
        succeeded = set(results[1].succeeded)
        archived_paths.extend(
            effect.destination
            for effect in project.effects
            if effect.id in succeeded and effect.path.startswith(".kittify/.migration-backup/") and effect.after.kind in {"file", "symlink"}
        )
    prepared = project.prepared
    if not isinstance(prepared, PreparedProjectSkills):
        raise TypeError("Missing prepared project skill manifest")
    return _parse_manifest(prepared.manifest_content.decode("utf-8"))
