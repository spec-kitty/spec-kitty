"""Command-Skill Installer for shared-root command-skill agents.

This module owns all mutations under ``.agents/skills/`` for agents that consume
Spec Kitty slash commands as Agent Skills.  It wraps
:mod:`specify_cli.skills.manifest_store` (WP01) and
:mod:`specify_cli.skills.command_renderer` (WP02) to provide three public
operations:

* :func:`install` — additive, idempotent, reference-counted.
* :func:`remove` — reference-counted; physical delete only when ``agents``
  list empties.
* :func:`verify` — read-only drift / orphan / gap scanner.

NFR-002 (shared-root coexistence)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Third-party directories and files under ``.agents/skills/`` are **never**
touched.  The installer only creates or deletes paths that appear in the
manifest, and the manifest only ever references files in
``spec-kitty.<command>/SKILL.md`` subdirectories.

No call to :func:`shutil.rmtree` or any recursive deletion exists in this
module.  The only directory removal is a targeted
``parent.rmdir()`` — which succeeds only on an empty directory.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
import errno
import os
import stat
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from specify_cli.core.agent_config import AgentConfigError
from specify_cli.core.no_follow import chmod_fd

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
)

from specify_cli.skills import manifest_store
from specify_cli.skills.manifest_store import ManifestEntry
from specify_cli.skills.manifest_errors import ManifestError
from specify_cli.skills import command_renderer
from specify_cli.skills.paths import SkillPathObservation, observe_skill_path
from specify_cli.skills._agent_roster import SUPPORTED_AGENTS as SUPPORTED_AGENTS
from specify_cli.agent_upgrade_prompt import prepend_agent_upgrade_check
from kernel.clock import now_utc_iso
from specify_cli.shims.registry import CONSUMER_SKILLS
from kernel import paths as kernel_paths
from kernel.paths import to_posix

if TYPE_CHECKING:
    from specify_cli.tool_surface.bundles.model import BundleObservation
    from charter.activation.compiler import _PreparedMissionTypeActivations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Re-exported from the leaf authority :data:`specify_cli.skills._agent_roster`
#: so historical ``command_installer.SUPPORTED_AGENTS`` references keep working
#: while the roster has exactly one definition (#1941).

#: Commands installed as full prompt-backed Agent Skills.  These match the
#: step directories under ``packs/built-in/missions/mission-steps/software-dev/``.
#: ``checklist`` was retired in 3.2.0a5 (FR-003 / FR-004 / #815).
PROMPT_BACKED_COMMANDS: tuple[str, ...] = (
    "accept",
    "analyze",
    "charter",
    "implement",
    "plan",
    "research",
    "review",
    "specify",
    "tasks",
    "tasks-finalize",
    "tasks-outline",
    "tasks-packages",
)

#: Commands installed as thin Agent Skills that delegate to the canonical CLI.
CLI_WRAPPER_COMMANDS: tuple[str, ...] = (
    "dashboard",
    "merge",
    "status",
)

#: The full consumer-facing command-skill set.
CANONICAL_COMMANDS: tuple[str, ...] = tuple(sorted((*PROMPT_BACKED_COMMANDS, *CLI_WRAPPER_COMMANDS)))

assert set(CANONICAL_COMMANDS) == set(CONSUMER_SKILLS), "Command-skill installer must cover every consumer command"

_CLI_WRAPPER_DESCRIPTIONS: dict[str, str] = {
    "dashboard": "Open the mission dashboard",
    "merge": "Merge an accepted mission",
    "status": "Show mission and work package status",
}

_CLI_WRAPPER_COMMANDS: dict[str, str] = {
    "dashboard": "spec-kitty dashboard",
    "merge": "spec-kitty merge",
    "status": "spec-kitty agent tasks status",
}


def _package_templates_dir(mission_type: str = "software-dev") -> Path:
    """Return the directory containing canonical command step directories inside
    the installed ``doctrine`` package.

    Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
    (FR-005) relocated ``mission-steps/`` from
    ``src/charter/offering/missions/mission-steps`` to
    ``packs/built-in/missions/mission-steps`` — the retired
    ``Path(charter.offering.__file__).parent``-relative construction addressed
    exactly the old, now-nonexistent location. Resolved through the one
    promoted missions-root authority
    (:meth:`~charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`,
    FR-004) instead, which works identically in editable and wheel installs.

    Parameters
    ----------
    mission_type:
        The mission type sub-directory to resolve (defaults to
        ``"software-dev"``).
    """
    from charter.missions import MissionTemplateRepository  # noqa: PLC0415 — deferred to avoid import-time side effects

    # Typed pin: ``charter.*`` is ``follow_imports = "skip"`` in pyproject, so the
    # facade re-export is ``Any`` to mypy; the runtime type is ``Path``.
    missions_root: Path = MissionTemplateRepository.default_missions_root()
    return missions_root / "mission-steps" / mission_type


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class InstallerError(Exception):
    """Raised when an install, remove, or verify operation cannot complete safely.

    Attributes
    ----------
    code:
        Machine-readable error code.  One of:

        * ``"manifest_parse_failed"`` — manifest is corrupt; operator must
          resolve before retrying.
        * ``"unexpected_collision"`` — on-disk hash does not match the manifest
          entry hash during install.  Drift detected.
        * ``"manifest_entry_not_found"`` — ``remove()`` called for an agent
          with no matching manifest entries.
        * ``"file_mutation_detected"`` — on-disk hash does not match the
          manifest entry hash during remove.  Abort to preserve integrity.
        * ``"unsupported_agent"`` — ``agent_key`` not in
          :data:`SUPPORTED_AGENTS`.
        * ``"unsafe_path"`` — a managed path resolves outside ``repo_root``.
    context:
        Additional diagnostic keyword arguments (path, agent_key, etc.).
    """

    def __init__(self, code: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {context}")


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass
class InstallReport:
    """Summary of an :func:`install` operation.

    Attributes
    ----------
    added:
        Paths of files that were written to disk for the first time (or
        rewritten due to a template update).
    already_installed:
        Paths already in the manifest for this agent with matching hashes —
        no disk write occurred.
    reused_shared:
        Paths already on disk (installed by another agent) whose manifest
        entry gained *agent_key* in its ``agents`` tuple.
    errors:
        Human-readable error strings for non-fatal issues (empty unless a
        caller uses the error-collection path, which is reserved for future
        use).
    """

    added: list[str] = field(default_factory=list)
    already_installed: list[str] = field(default_factory=list)
    reused_shared: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RemoveReport:
    """Summary of a :func:`remove` operation.

    Attributes
    ----------
    deref:
        Paths for which *agent_key* was removed from ``agents`` (covers both
        ``kept`` and ``deleted`` cases).
    deleted:
        Subset of ``deref`` whose ``agents`` list became empty — the file was
        physically deleted.
    kept:
        Subset of ``deref`` whose ``agents`` list is still non-empty — the
        file remains on disk, owned by the remaining agents.
    """

    deref: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    """Summary of a :func:`verify` operation.

    Attributes
    ----------
    drift:
        Paths whose on-disk SHA-256 no longer matches the stored hash.
    orphans:
        Files under ``.agents/skills/spec-kitty.*/`` that are not in the
        manifest.
    gaps:
        Manifest entries whose files are missing from disk.
    stale:
        Manifest entries for command skills that are no longer canonical.
    unsafe:
        Manifest entries or orphan candidates that resolve outside
        ``repo_root`` through symlinks.
    """

    drift: list[str] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unsafe: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_template(repo_root: Path, command: str) -> Path:
    """Return the absolute path to the command prompt template for *command*.

    Templates live inside the installed ``doctrine`` package (not under the
    user's project root). ``repo_root`` is retained in the signature for
    call-site symmetry but is intentionally unused — the template location is
    package state, not project state.

    New doctrine layout:
    ``doctrine/missions/mission-steps/<mission_type>/<step_id>/prompt.md``
    """
    del repo_root  # not used; kept for call-site consistency
    return _package_templates_dir() / command / "prompt.md"


def _render_command_skill(repo_root: Path, command: str, agent_key: str, version: str) -> bytes:
    """Return serialized SKILL.md bytes for a command skill."""
    if command in PROMPT_BACKED_COMMANDS:
        template = _resolve_template(repo_root, command)
        rendered = command_renderer.render(template, agent_key, version, repo_root=repo_root)
        return rendered.to_skill_md().encode("utf-8")

    if command not in CLI_WRAPPER_COMMANDS:
        raise InstallerError("unknown_command", command=command)

    description = _CLI_WRAPPER_DESCRIPTIONS[command]
    cli_command = _CLI_WRAPPER_COMMANDS[command]
    body = (
        f"# /spec-kitty.{command} - {description}\n\n"
        "## Purpose\n\n"
        "Run the canonical Spec Kitty CLI command for this workflow and treat "
        "its output as authoritative.\n\n"
        "Do not rediscover mission context from branches, files, prompt "
        "contents, or separate charter loads. If mission selection is required, "
        "pass `--mission <handle>` where `<handle>` is a mission_id, mid8, or "
        "mission_slug.\n\n"
        "## User Input\n\n"
        "The content of the user's message that invoked this skill is the User "
        "Input. Consider it before proceeding. If it contains CLI arguments, "
        "append them to the command below.\n\n"
        "## Steps\n\n"
        "Run this command from the repository root:\n\n"
        "```bash\n"
        f"{cli_command} <user-provided-args-if-any>\n"
        "```\n\n"
        "Report the command output and follow any next-step instructions it "
        "prints.\n"
    )
    body = prepend_agent_upgrade_check(body)
    skill_md = f"---\nname: spec-kitty.{command}\ndescription: {description}\nuser-invocable: true\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"
    return skill_md.encode("utf-8")


def _atomic_write(path: Path, content: bytes, *, mode: int = 0o644) -> None:
    """Write *content* to *path* atomically (temp-file + rename).

    Guarantees that a crashed write leaves at most a stale ``.tmp`` file
    behind, never a partially-written target.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    created = False
    try:
        with tmp.open("xb") as fh:
            created = True
            fh.write(content)
            fh.flush()
            chmod_fd(fh.fileno(), tmp, mode)
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if created:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
        raise


def _ensure_project_confined(repo_root: Path, rel_path: str, abs_path: Path) -> None:
    """Reject managed paths that escape the project root through symlinks."""
    repo_resolved = repo_root.resolve()
    try:
        resolved_target = abs_path.resolve(strict=False)
    except OSError as exc:
        raise InstallerError("unsafe_path", path=rel_path, detail=str(exc)) from exc

    if not resolved_target.is_relative_to(repo_resolved):
        raise InstallerError(
            "unsafe_path",
            path=rel_path,
            resolved=str(resolved_target),
            repo_root=str(repo_resolved),
        )


def _command_from_rel_path(rel_path: str) -> str | None:
    prefix = ".agents/skills/spec-kitty."
    suffix = "/SKILL.md"
    if not rel_path.startswith(prefix) or not rel_path.endswith(suffix):
        return None
    return rel_path[len(prefix) : -len(suffix)]


def _is_canonical_rel_path(rel_path: str) -> bool:
    command = _command_from_rel_path(rel_path)
    return command in CANONICAL_COMMANDS


def _get_version() -> str:
    """Return the current Spec Kitty CLI version, or a dev fallback."""
    try:
        import specify_cli as _sk  # noqa: PLC0415

        return getattr(_sk, "__version__", "0.0.0-dev")
    except Exception:  # pragma: no cover
        return "0.0.0-dev"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_OWNER = "command_skills"
_MANIFEST = ".kittify/command-skills-manifest.json"


@dataclass(frozen=True)
class CommandInput:
    """A command batch input observed without following destination links."""

    path: Path
    state: FileState
    children: tuple[str, ...] | None = None


_BUNDLE_PARENTS: ContextVar[tuple[OwnerAssessment, tuple[CommandInput, ...]] | None] = ContextVar(
    "command_completed_bundle_parents",
    default=None,
)


@contextlib.contextmanager
def _completed_bundle_parents(assessment: OwnerAssessment, parents: tuple[BundleObservation, ...]) -> Iterator[None]:
    """Scope actual selected-staging receipts to the original command assessment."""
    inputs = tuple(CommandInput(p.path, p.state, p.children) for p in parents)
    token = _BUNDLE_PARENTS.set((assessment, inputs))
    try:
        yield
    finally:
        _BUNDLE_PARENTS.reset(token)


def _bundle_parent_input(assessment: OwnerAssessment, path: Path) -> CommandInput | None:
    active = _BUNDLE_PARENTS.get()
    if active is None or active[0] != assessment:
        return None
    return next((p for p in active[1] if p.path == path), None)


@dataclass(frozen=True)
class PreparedCommand:
    """Retained command bytes and the corresponding exact manifest decision."""

    path: str
    content: bytes | None
    entry: ManifestEntry | None
    report_kind: str
    proof: OwnershipProof | None = None


@dataclass(frozen=True)
class CommandExecutionArtifact:
    """Bounded apply-only atomic replacement path; never a persistent effect."""

    directory: str
    name_pattern: str
    purpose: str = "atomic_write"


@dataclass(frozen=True)
class PreparedCommands:
    """Immutable command-owner payload, not a replayable filesystem plan."""

    commands: tuple[PreparedCommand, ...]
    original_entries: tuple[ManifestEntry, ...]
    manifest_bytes: bytes
    observations: tuple[CommandInput, ...]
    catalog: tuple[str, ...]
    version: str
    execution_artifacts: tuple[CommandExecutionArtifact, ...]
    template_paths: tuple[tuple[str, Path], ...]
    provisioning: _PreparedMissionTypeActivations | None = None


_PARENT_CREATIONS: ContextVar[dict[Path, SkillPathObservation] | None] = ContextVar(
    "command_parent_creations",
    default=None,
)


@contextlib.contextmanager
def _record_command_parent_creations() -> Iterator[dict[Path, SkillPathObservation]]:
    """Record identities at actual mkdir, for the bounded paired skill owner."""
    created: dict[Path, SkillPathObservation] = {}
    token = _PARENT_CREATIONS.set(created)
    try:
        yield created
    finally:
        _PARENT_CREATIONS.reset(token)


def _state(path: Path) -> FileState:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return FileState("absent")
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        return FileState("symlink", target=os.readlink(path), mode=mode, mtime_ns=info.st_mtime_ns)
    if stat.S_ISDIR(info.st_mode):
        return FileState("directory", mode=mode, mtime_ns=info.st_mtime_ns)
    if stat.S_ISREG(info.st_mode):
        return FileState("file", sha256=manifest_store.fingerprint_file(path), mode=mode, mtime_ns=info.st_mtime_ns)
    raise InstallerError("unsafe_path", path=str(path), detail="Unsupported node kind")


def windows_dir_mode_only_divergence(observed: FileState, planned: FileState) -> bool:
    """Return True when a directory diverges from the plan *only* by POSIX mode on Windows.

    A freshly-created shared skills directory (e.g. ``.agents/skills``) carries a
    POSIX ``mode`` of ``0o755`` in the plan, but Windows ``os.chmod`` cannot
    represent those bits, so the observed directory mode can never match the plan.
    Two gates compare that planned mode against the freshly-observed directory --
    the completion re-check in the managed-skills provider AND the doctrine apply's
    command-parent receipt check (``installer._command_parent_receipts``). Left
    unhandled either makes ``upgrade`` unable to converge in one pass on Windows:
    the re-check raises (#4776) or a ``chmod`` is re-planned forever (#4777), and
    the doctrine skills never apply.

    Treating that single, host-inherent divergence as satisfied lets ``upgrade``
    converge in one pass with both command AND doctrine skills applied
    (FR-005/006) and report zero dry-run repairs once converged (FR-007). The
    relaxation is deliberately narrow: only directory-kind effects, only when the
    *sole* remaining difference after equalizing ``mode`` is the mode itself, and
    only on Windows -- the host check goes through the canonical patchable
    ``kernel.paths.is_windows`` seam (module attribute at call time, so tests
    monkeypatch ``kernel.paths.is_windows`` without faking ``os.name``), so POSIX
    file- and directory-mode correctness is never weakened (NFR-003).
    """
    if not kernel_paths.is_windows():
        return False
    if observed.kind != "directory" or planned.kind != "directory":
        return False
    return bool(replace(observed, mode=planned.mode) == planned)


def _manifest_change_bytes(manifest: manifest_store.SkillsManifest) -> bytes:
    """Serialize a manifest with ``installed_at`` neutralized, for change detection only.

    #4134: ``installed_at`` is a per-invocation wall-clock stamp (sampled once as
    ``_CommandBatch.time`` and threaded into ``ManifestEntry.installed_at``).
    Excluding it from the change-detection comparison -- mirroring the
    doctrine-skill provider's ``_expected_entries``, which compares with
    ``installed_at=""`` -- keeps a cross-invocation timestamp difference from
    planning a phantom manifest rewrite (and from tripping the completion
    re-check). Callers persist the manifest's *real* bytes; only the
    "did the manifest meaningfully change?" decision runs through this seam, so
    the preserved-timestamp contract stays intact.
    """
    neutralized = manifest_store.SkillsManifest(
        schema_version=manifest.schema_version,
        entries=[replace(entry, installed_at="") for entry in manifest.entries],
    )
    encoded: bytes = manifest_store.serialize(neutralized)
    return encoded


class _CommandBatch:
    """Collect command decisions and their physical supporting effects once."""

    def __init__(self, inputs: AssessmentInputs, agents: tuple[str, ...]) -> None:
        self.inputs = inputs
        self.root = inputs.root.path
        self.provisioning = _prepare_command_provisioning(self.root, inputs.projected)
        self.agents = agents
        self.observations: dict[Path, CommandInput] = {}
        self.effects: dict[str, PhysicalEffect] = {}
        self.commands: list[PreparedCommand] = []
        self.dispositions: list[Disposition] = []
        self.artifacts: list[CommandExecutionArtifact] = []
        self.template_paths: list[tuple[str, Path]] = []
        if self.observe_destination(_MANIFEST).kind not in {"file", "absent"}:
            raise InstallerError("manifest_parse_failed", detail="Manifest must be a regular file")
        try:
            self.manifest = manifest_store.load(self.root)
        except ManifestError as exc:
            raise InstallerError("manifest_parse_failed", detail=str(exc)) from exc
        self.original_entries = tuple(self.manifest.entries)
        self.version = _get_version()
        self.time = now_utc_iso()

    def observe(self, path: Path, *, children: bool = False) -> FileState:
        state = _state(path)
        names = tuple(sorted(p.name for p in path.iterdir())) if children and state.kind == "directory" else None
        observation = CommandInput(path, state, names)
        previous = self.observations.get(path)
        if previous is not None and previous.state != state:
            raise InstallerError("precondition_changed", path=str(path))
        if previous is not None and previous.children is not None and names is None:
            observation = previous
        self.observations[path] = observation
        return state

    def observe_destination(self, rel: str) -> FileState:
        path = self.root / rel
        if not path.is_relative_to(self.root) or ".." in Path(rel).parts:
            raise InstallerError("unsafe_path", path=rel)
        for parent in reversed(path.parents):
            if (parent == self.root or parent.is_relative_to(self.root)) and self.observe(parent).kind not in {"directory", "absent"}:
                raise InstallerError("unsafe_path", path=rel, detail="Non-directory parent")
        return self.observe(path)

    def disposition(self, rel: str, state: str, reason: str) -> None:
        self.dispositions.append(Disposition(_OWNER, self.inputs.root.root_id, rel, state, reason))

    def effect(self, rel: str, after: FileState, owners: tuple[str, ...], proof: OwnershipProof) -> None:
        before = self.observe_destination(rel)
        if before.kind == "absent":
            action = "create"
        elif after.kind == "absent":
            action = "delete"
        elif before.kind != after.kind:
            action = "replace"
        elif before.sha256 != after.sha256:
            action = "update"
        elif before.mode != after.mode:
            action = "chmod"
        else:
            return
        effect = PhysicalEffect(
            _OWNER,
            "surface_repair",
            self.inputs.root,
            rel,
            action,
            before,
            after,
            "Reconcile command delivery and manifest ownership",
            (proof,),
            owners,
        )
        previous = self.effects.get(rel)
        if previous is not None:
            effect = replace(effect, logical_owners=previous.logical_owners + effect.logical_owners, ownership=previous.ownership + effect.ownership)
        self.effects[rel] = effect

    def parents(self, rel: str, owners: tuple[str, ...]) -> None:
        for parent in reversed(Path(rel).parents):
            if parent == Path("."):
                continue
            name = parent.as_posix()
            if self.observe_destination(name).kind == "absent":
                if self.provisioning is not None and self.root / name in self.provisioning.write.absent_parents:
                    continue  # The canonical YAML writer owns these directories.
                self.effect(name, FileState("directory", mode=0o755), owners, OwnershipProof("managed_path", f"parent:{rel}"))

    def atomic_artifact(self, rel: str) -> None:
        path = Path(rel)
        temporary = path.with_suffix(".tmp") if rel == _MANIFEST else path.with_suffix(path.suffix + ".tmp")
        if self.observe_destination(temporary.as_posix()).kind != "absent":
            raise InstallerError("unexpected_collision", path=temporary.as_posix())
        self.artifacts.append(CommandExecutionArtifact(temporary.parent.as_posix(), temporary.name))

    def install_command(self, command: str, content: bytes, *, adopt_only: bool = False) -> None:
        rel = f".agents/skills/spec-kitty.{command}/SKILL.md"
        existing = self.manifest.find(rel)
        parent = Path(rel).parent.as_posix()
        try:
            parent_state = self.observe_destination(parent)
        except InstallerError as exc:
            if exc.code != "unsafe_path":
                raise
            self.disposition(rel, "preserve", "Unsafe command parent retained")
            return
        package_link = parent_state.kind == "symlink"
        if package_link and existing is None:
            self.disposition(rel, "preserve", "Unknown package link is not command ownership")
            return
        before = FileState("absent") if package_link else self.observe_destination(rel)
        digest = manifest_store.fingerprint(content)
        if self.preserve(rel, before, existing, digest):
            return
        if adopt_only and (existing is not None or before.kind != "file" or before.sha256 != digest):
            return
        owners = tuple(sorted(set(existing.agents if existing else ()) | set(self.agents)))
        entry = ManifestEntry(rel, digest, owners, existing.installed_at if existing else self.time, self.version)
        same = before.kind == "file" and before.sha256 == digest
        if same and existing is not None:
            entry = existing
            for agent in self.agents:
                entry = entry.with_agent_added(agent)
        kind = "already_installed" if same and existing == entry else "reused_shared" if same else "added"
        proof = (
            OwnershipProof("manifest", f"{_MANIFEST}#{rel}")
            if existing
            else OwnershipProof("canonical_content" if same else "managed_path", f"CANONICAL_COMMANDS:{command}:{digest}")
        )
        self.commands.append(PreparedCommand(rel, content, entry, kind, proof))
        self.manifest.upsert(entry)
        if package_link:
            self.effect(parent, FileState("directory", mode=0o755), owners, proof)
            self.effects[rel] = PhysicalEffect(
                _OWNER,
                "surface_repair",
                self.inputs.root,
                rel,
                "create",
                before,
                FileState("file", sha256=digest, mode=0o644),
                "Copy into the replaced owned package link",
                (proof,),
                owners,
            )
            self.artifacts.append(CommandExecutionArtifact(parent, "SKILL.md.tmp"))
        elif not same:
            self.parents(rel, owners)
            self.effect(rel, FileState("file", sha256=digest, mode=before.mode if before.kind == "file" else 0o644), owners, proof)
            self.atomic_artifact(rel)
        else:
            self.disposition(rel, "unchanged", "Canonical bytes retained; manifest owners assessed separately")

    def preserve(self, rel: str, before: FileState, existing: ManifestEntry | None, digest: str) -> bool:
        if before.kind == "directory" or (before.kind == "symlink" and existing is None):
            self.disposition(rel, "preserve", "Unknown node is not command ownership")
            return True
        if before.kind != "file":
            return False
        if existing is not None and before.sha256 != existing.content_hash:
            self.disposition(rel, "consent_required", "Managed command content has drifted")
            return True
        if existing is None and before.sha256 != digest:
            self.disposition(rel, "preserve", "Unknown content does not equal canonical rendered bytes")
            return True
        return False

    def remove_entry(self, entry: ManifestEntry, remaining: tuple[str, ...]) -> None:
        before = self.observe_destination(entry.path)
        if before.kind == "directory" or (before.kind == "file" and before.sha256 != entry.content_hash):
            self.disposition(entry.path, "consent_required", "Edited owned prune/remove candidate retained")
            return
        if remaining:
            updated = ManifestEntry(entry.path, entry.content_hash, remaining, entry.installed_at, entry.spec_kitty_version)
            self.manifest.upsert(updated)
            self.commands.append(PreparedCommand(entry.path, None, updated, "kept"))
            return
        proof = OwnershipProof("manifest", f"{_MANIFEST}#{entry.path}")
        if before.kind != "absent":
            self.effect(entry.path, FileState("absent"), entry.agents, proof)
        parent = (self.root / entry.path).parent
        state = self.observe(parent, children=True)
        if state.kind == "directory" and self.observations[parent].children in {(), ("SKILL.md",)}:
            self.effect(parent.relative_to(self.root).as_posix(), FileState("absent"), entry.agents, proof)
        self.manifest.remove_path(entry.path)
        self.commands.append(PreparedCommand(entry.path, None, None, "deleted"))

    def finish(self) -> OwnerAssessment:
        encoded = manifest_store.serialize(self.manifest)
        owners = tuple(sorted(set(self.agents) | {a for e in self.original_entries for a in e.agents}))
        # Ordering is not an effect; retain original bytes when entries agree.
        # #4134: change detection compares installed_at-neutralized content so a
        # cross-invocation wall-clock ``installed_at`` never plans a phantom
        # manifest rewrite (mirrors the doctrine provider's ``_expected_entries``
        # installed_at=""). The STORED bytes below keep their real timestamp.
        if self.manifest.entries != list(self.original_entries) and _manifest_change_bytes(self.manifest) != _manifest_change_bytes(
            manifest_store.SkillsManifest(entries=list(self.original_entries))
        ):
            self.parents(_MANIFEST, owners)
            before = self.observe_destination(_MANIFEST)
            self.effect(
                _MANIFEST,
                FileState("file", sha256=manifest_store.fingerprint(encoded), mode=before.mode if before.kind == "file" else 0o644),
                owners,
                OwnershipProof("managed_path", _MANIFEST),
            )
            self.effects[_MANIFEST] = replace(
                self.effects[_MANIFEST], ownership=(self.effects[_MANIFEST].ownership + tuple(c.proof for c in self.commands if c.proof is not None))
            )
            self.atomic_artifact(_MANIFEST)
        payload = PreparedCommands(
            tuple(self.commands),
            self.original_entries,
            encoded,
            tuple(self.observations.values()),
            CANONICAL_COMMANDS,
            self.version,
            tuple(self.artifacts),
            tuple(self.template_paths),
            self.provisioning,
        )
        return OwnerAssessment(
            _OWNER,
            self.inputs.root,
            tuple(self.effects.values()),
            tuple(self.dispositions),
            inputs_fingerprint=(InputObservation("command_inputs", payload.observations), InputObservation("projected", self.inputs.projected)),
            prepared=payload,
            consent=self.inputs.consent,
        )


def _resolve_observed_input(path: Path) -> Path:
    try:
        return path.resolve()
    except RuntimeError as exc:
        # Python 3.11 pathlib translates ELOOP into RuntimeError. Translate only
        # that observation failure; programmer exceptions still escape.
        cause = exc.__cause__ or exc.__context__
        if isinstance(cause, OSError) and cause.errno == errno.ELOOP:
            raise cause from exc
        raise


def _prepare_command_provisioning(repo_root: Path, projected: object) -> _PreparedMissionTypeActivations | None:
    """Admit only the actual compiler's immutable, still-current preparation."""
    from charter.activation.compiler import _PreparedMissionTypeActivations, prepare_mission_type_activations

    if projected is None:
        return None
    if type(projected) is not _PreparedMissionTypeActivations:
        raise ValueError("Unsupported command provisioning input")
    prepared = cast("_PreparedMissionTypeActivations", projected)
    prepared.write.recheck()
    if prepared != prepare_mission_type_activations(repo_root):
        raise ValueError("Command provisioning differs from the canonical compiler preparation")
    write = prepared.write
    original = next(item for item in write.observations if item.path == write.target)
    if write.changed and original.identity is not None and original.identity[-1] != 1:
        raise ValueError("Changed command provisioning requires a single-link rendering authority")
    command_renderer.validate_mission_provisioning(repo_root, write.before_bytes, write.desired_bytes, write.target)
    return prepared


def _recheck_command_provisioning(payload: PreparedCommands, phase: Literal["preflight", "transition", "apply"]) -> Path | None:
    """Permit only the known direct writer's exact transition, never rerender."""
    from charter.activation.charter_yaml_io import observe_yaml_input

    provisioning = payload.provisioning
    if provisioning is None:
        return None
    write = provisioning.write
    if manifest_store.fingerprint(write.desired_bytes) != write.desired_sha256:
        raise ValueError("precondition_changed: prepared provisioning bytes")
    current = observe_yaml_input(write.target)
    if phase == "preflight" or not write.changed or current.content == write.before_bytes:
        write.recheck()
        if phase == "apply" and write.changed:
            raise ValueError("precondition_changed: mission provisioning has not been applied")
        return None
    if write.before_bytes is None:
        write.recheck_applied()
        return cast("Path", write.target)
    original = next(item for item in write.observations if item.path == write.target)
    old, new = original.identity, current.identity
    # The existing YAML writer truncates in place. Only target size/mtime/ctime
    # can change; a replacement inode, link, mode or unrelated input cannot.
    if (
        old is None
        or new is None
        or old[:3] != new[:3]
        or old[6] != 1
        or new[6] != 1
        or new[3] < old[3]
        or new[4] < old[4]
        or new[5] != len(write.desired_bytes)
        or current.content != write.desired_bytes
    ):
        raise ValueError(f"precondition_changed: provisioning target {write.target}")
    for item in write.observations:
        if item.path != write.target and observe_yaml_input(item.path) != item:
            raise ValueError(f"precondition_changed: provisioning input {item.path}")
    return cast("Path", write.target)


def prepare_commands(
    inputs: AssessmentInputs,
    agents: tuple[str, ...],
    *,
    prune: bool = False,
    remove_agents: tuple[str, ...] = (),
    adopt_only: bool = False,
) -> OwnerAssessment:
    """Prepare the complete selected command batch without writes or normalization.

    Exact canonical bytes alone permit unowned regular-file adoption. Unknown
    bytes and links are preserved; existing manifest owners survive shared reuse.
    """
    try:
        if any(a not in SUPPORTED_AGENTS for a in agents + remove_agents):
            raise InstallerError("unsupported_agent", agents=agents + remove_agents)
        batch = _CommandBatch(inputs, agents)
        for path in command_renderer.rendering_inputs(inputs.root.path):
            batch.observe(path)
            resolved = _resolve_observed_input(path)
            if resolved != path:
                batch.observe(resolved)
        for command in CANONICAL_COMMANDS if agents else ():
            if command in PROMPT_BACKED_COMMANDS:
                template = _resolve_template(inputs.root.path, command)
                batch.template_paths.append((command, template))
                batch.observe(template)
                batch.observe(_resolve_observed_input(template))
            variants = tuple(_render_command_skill(inputs.root.path, command, agent, batch.version) for agent in agents)
            if len(set(variants)) != 1:
                raise InstallerError("shared_content_conflict", command=command)
            batch.install_command(command, variants[0], adopt_only=adopt_only)
        for entry in batch.original_entries:
            if remove_agents or (prune and not _is_canonical_rel_path(entry.path)):
                selected = set(remove_agents or agents or entry.agents)
                if selected.intersection(entry.agents):
                    batch.remove_entry(entry, tuple(a for a in entry.agents if a not in selected))
        assessment = batch.finish()
        diagnostics = recheck_commands(assessment, phase="preflight")
        return replace(assessment, complete=False, diagnostics=diagnostics) if diagnostics else assessment
    except (OSError, ValueError, AgentConfigError, InstallerError, ManifestError, command_renderer.SkillRenderError) as exc:
        return OwnerAssessment(
            _OWNER,
            inputs.root,
            complete=False,
            diagnostics=(Diagnostic(getattr(exc, "code", "command_input_unreadable"), _OWNER, "error", str(exc)),),
            consent=inputs.consent,
        )


def recheck_commands(assessment: OwnerAssessment, *, phase: Literal["preflight", "transition", "apply"] = "transition") -> tuple[Diagnostic, ...]:
    """Check retained inputs, with explicit original-state and apply phases.

    Preflight requires original compiler observations before any provisioning.
    Transition accepts original or exact provisioned state for service rechecks.
    Apply requires provisioning complete when a changed write was prepared.
    """
    payload = assessment.prepared
    if not assessment.complete or not isinstance(payload, PreparedCommands):
        return (Diagnostic("incomplete_assessment", _OWNER, "error", "Command preparation is incomplete"),)
    try:
        if InputObservation("projected", payload.provisioning) not in assessment.inputs_fingerprint:
            raise ValueError("precondition_changed: retained provisioning input")
        provisioned_target = _recheck_command_provisioning(payload, phase)
        if payload.catalog != CANONICAL_COMMANDS or payload.version != _get_version():
            raise InstallerError("precondition_changed", detail="Command catalog/version changed")
        if any(_resolve_template(assessment.root.path, command) != path for command, path in payload.template_paths):
            raise InstallerError("precondition_changed", detail="Command source selection changed")
        for item in payload.observations:
            if phase != "preflight":
                item = _bundle_parent_input(assessment, item.path) or item
            current = _state(item.path)
            if provisioned_target is not None and _resolve_observed_input(item.path) == provisioned_target and item.state.kind in {"file", "absent"}:
                assert payload.provisioning is not None
                expected = FileState(
                    "file",
                    sha256=payload.provisioning.write.desired_sha256,
                    mode=current.mode if item.state.kind == "absent" else item.state.mode,
                    mtime_ns=current.mtime_ns,
                )
            else:
                expected = item.state
            children = item.children
            if provisioned_target is not None and payload.provisioning is not None and payload.provisioning.write.before_bytes is None:
                created = (*payload.provisioning.write.absent_parents, provisioned_target)
                additions = tuple(path.name for path in created if path.parent == item.path)
                if additions and item.state.kind in {"absent", "directory"}:
                    # The YAML receipt already verifies these parent identities.
                    # Creating its direct children may change directory mtime.
                    expected = FileState("directory", mode=current.mode if item.state.kind == "absent" else item.state.mode, mtime_ns=current.mtime_ns)
                    if children is not None:
                        children = tuple(sorted((*children, *additions)))
            if current != expected:
                raise InstallerError("precondition_changed", path=str(item.path))
            if children is not None and tuple(sorted(p.name for p in item.path.iterdir())) != children:
                raise InstallerError("precondition_changed", path=str(item.path))
    except (OSError, ValueError, InstallerError) as exc:
        return (Diagnostic("precondition_changed", _OWNER, "error", str(exc)),)
    return ()


def _apply_command_effect(effect: PhysicalEffect, payload: PreparedCommands) -> None:
    path = effect.destination
    if effect.after.kind == "directory":
        if effect.before.kind == "symlink":
            path.unlink()
        path.mkdir(mode=0o755)
        path.chmod(0o755)
        created = _PARENT_CREATIONS.get()
        if created is not None and effect.before.kind == "absent":
            created[path] = observe_skill_path(path)
    elif effect.after.kind == "absent":
        if effect.before.kind == "directory":
            path.rmdir()
        else:
            path.unlink()
    elif effect.path == _MANIFEST:
        manifest_store.save_prepared(effect.root.path, payload.manifest_bytes, mode=effect.after.mode if effect.after.mode is not None else 0o644)
    else:
        command = next(c for c in payload.commands if c.path == effect.path)
        assert command.content is not None
        _atomic_write(path, command.content, mode=effect.after.mode if effect.after.mode is not None else 0o644)


def _partial_manifest(assessment: OwnerAssessment, payload: PreparedCommands, succeeded: set[str]) -> None:
    """Save only entries supported by completed writes, retaining prior owners."""
    manifest = manifest_store.SkillsManifest(entries=list(payload.original_entries))
    by_path = {effect.path: effect for effect in assessment.effects}
    for command in payload.commands:
        effect = by_path.get(command.path)
        if effect is not None and effect.id not in succeeded:
            continue
        if command.entry is None:
            manifest.remove_path(command.path)
        else:
            manifest.upsert(command.entry)
    encoded = manifest_store.serialize(manifest)
    # #4134: installed_at-neutralized change detection (see ``finish``); the
    # persisted bytes below still carry the real timestamps.
    if _manifest_change_bytes(manifest) != _manifest_change_bytes(manifest_store.SkillsManifest(entries=list(payload.original_entries))):
        manifest_effect = by_path.get(_MANIFEST)
        mode = manifest_effect.after.mode if manifest_effect is not None else None
        manifest_store.save_prepared(assessment.root.path, encoded, mode=mode if mode is not None else 0o644)


def apply_commands(assessment: OwnerAssessment, consent: ApplyConsent) -> OwnerApplyResult:
    """Apply exact prepared bytes after a full recheck; report actual partial I/O."""
    ids = tuple(e.id for e in assessment.effects)
    if not consent.automatic or consent != assessment.consent:
        return OwnerApplyResult(_OWNER, skipped=ids, outcome="skipped")
    diagnostics = recheck_commands(assessment, phase="apply")
    if diagnostics:
        return OwnerApplyResult(_OWNER, skipped=ids, diagnostics=diagnostics, outcome="precondition_changed")
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    effects = sorted(
        assessment.effects,
        key=lambda e: (
            3 if e.path == _MANIFEST else 2 if e.after.kind == "absent" and e.before.kind == "directory" else 0 if e.after.kind == "directory" else 1,
            len(Path(e.path).parts),
            e.path,
        ),
    )
    succeeded: list[str] = []
    for effect in effects:
        try:
            _apply_command_effect(effect, payload)
        except OSError as exc:
            messages = [Diagnostic("command_apply_failed", _OWNER, "error", str(exc))]
            try:
                if effect.path != _MANIFEST:
                    _partial_manifest(assessment, payload, set(succeeded))
            except OSError as manifest_exc:
                messages.append(Diagnostic("partial_manifest_failed", _OWNER, "error", str(manifest_exc)))
            return OwnerApplyResult(
                _OWNER,
                tuple(succeeded),
                (effect.id,),
                tuple(i for i in ids if i not in succeeded and i != effect.id),
                tuple(messages),
                "partial" if succeeded else "failed",
            )
        succeeded.append(effect.id)
    return OwnerApplyResult(_OWNER, tuple(succeeded))


def _direct_assessment(repo_root: Path, agents: tuple[str, ...], *, prune: bool = False, remove_agents: tuple[str, ...] = ()) -> OwnerAssessment:
    inputs = AssessmentInputs(OperationRoot("project", "project", repo_root.absolute()), consent=ApplyConsent(automatic=True))
    assessment = prepare_commands(inputs, agents, prune=prune, remove_agents=remove_agents)
    if not assessment.complete:
        raise InstallerError(assessment.diagnostics[0].code, detail=assessment.diagnostics[0].message)
    for disposition in assessment.dispositions:
        if disposition.state in {"preserve", "consent_required"}:
            if disposition.path is not None:
                _ensure_project_confined(repo_root, disposition.path, repo_root / disposition.path)
            raise InstallerError("file_mutation_detected" if remove_agents or prune else "unexpected_collision", path=disposition.path)
    result = apply_commands(assessment, inputs.consent)
    if result.outcome != "applied":
        raise InstallerError(result.outcome, diagnostics=result.diagnostics)
    return assessment


def install(repo_root: Path, agent_key: str) -> InstallReport:
    """Install the complete canonical batch; preserve the public logical report."""
    assessment = _direct_assessment(repo_root, (agent_key,))
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    report = InstallReport()
    for command in payload.commands:
        getattr(report, command.report_kind).append(command.path)
    return report


def remove(repo_root: Path, agent_key: str) -> RemoveReport:
    """Release one owner's references; delete only the final proven owner."""
    assessment = _direct_assessment(repo_root, (), remove_agents=(agent_key,))
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    report = RemoveReport()
    for command in payload.commands:
        report.deref.append(command.path)
        getattr(report, command.report_kind).append(command.path)
    return report


def prune_stale(repo_root: Path) -> list[str]:
    """Prune exact manifest-owned retired commands, preserving edited candidates."""
    assessment = _direct_assessment(repo_root, (), prune=True, remove_agents=())
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    return [command.path for command in payload.commands if command.report_kind == "deleted"]


def verify(repo_root: Path) -> VerifyReport:
    """Scan for drift, orphans, and gaps without mutating anything.

    This function is read-only.  It never writes to the manifest or to the
    filesystem.

    Parameters
    ----------
    repo_root:
        Absolute path to the project root.

    Returns
    -------
    VerifyReport
        * ``drift``: entries whose on-disk SHA-256 no longer matches the
          stored hash.
        * ``orphans``: files under ``.agents/skills/spec-kitty.*/`` that are
          not recorded in the manifest.
        * ``gaps``: manifest entries whose files are absent from disk.

    Raises
    ------
    InstallerError("manifest_parse_failed")
        The manifest file is corrupt.
    """
    try:
        manifest = manifest_store.load(repo_root)
    except Exception as exc:
        raise InstallerError("manifest_parse_failed", detail=str(exc)) from exc

    report = VerifyReport()
    manifest_paths = {e.path for e in manifest.entries}

    # --- Drift and gaps -------------------------------------------------------
    for entry in manifest.entries:
        abs_path = repo_root / entry.path
        try:
            _ensure_project_confined(repo_root, entry.path, abs_path)
        except InstallerError:
            report.unsafe.append(entry.path)
            continue
        if not _is_canonical_rel_path(entry.path):
            report.stale.append(entry.path)
        if not abs_path.exists():
            report.gaps.append(entry.path)
            continue
        on_disk = manifest_store.fingerprint_file(abs_path)
        if on_disk != entry.content_hash:
            report.drift.append(entry.path)

    # --- Orphan scan ----------------------------------------------------------
    # Only examine spec-kitty.* subdirectories under .agents/skills/.
    skills_root = repo_root / ".agents" / "skills"
    if skills_root.exists():
        for subdir in skills_root.iterdir():
            if not subdir.is_dir() or not subdir.name.startswith("spec-kitty."):
                continue
            for file in subdir.rglob("*"):
                if not file.is_file():
                    continue
                rel = to_posix(file.relative_to(repo_root))
                try:
                    _ensure_project_confined(repo_root, rel, file)
                except InstallerError:
                    report.unsafe.append(rel)
                    continue
                if rel not in manifest_paths:
                    report.orphans.append(rel)

    return report
