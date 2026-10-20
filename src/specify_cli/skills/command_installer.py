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
``spec-kitty-<command>/SKILL.md`` subdirectories (names composed by
:mod:`specify_cli.skills.command_skill_names`). A manifest written before #6475
may still record the legacy dotted ``spec-kitty.<command>/SKILL.md`` form; every
preparation retires such an entry with one rule (FR-020): an unmodified file is
deleted, an edited one is kept and no longer managed.

No call to :func:`shutil.rmtree` or any recursive deletion exists in this
module.  The only directory removal is a targeted
``parent.rmdir()`` — which succeeds only on an empty directory.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
import os
import re
import stat
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from specify_cli.core.agent_config import AgentConfigError

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
from specify_cli.skills.command_skill_names import (
    COMMAND_SKILL_PREFIX,
    command_skill_name,
    command_skill_rel_path,
    legacy_command_skill_name,
    legacy_command_skill_names,
    legacy_command_skill_rel_path,
    parse_command_skill_rel_path,
    parse_legacy_command_skill_rel_path,
)
from specify_cli.agent_upgrade_prompt import prepend_agent_upgrade_check
from kernel.clock import now_utc_iso
from kernel.no_follow import chmod_fd
from kernel.resolution import resolve_rejecting_loops
from specify_cli.shims.registry import CONSUMER_SKILLS
from specify_cli.state import contract as state_contract
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
    "consolidate",
    "status",
)

#: The full consumer-facing command-skill set.
CANONICAL_COMMANDS: tuple[str, ...] = tuple(sorted((*PROMPT_BACKED_COMMANDS, *CLI_WRAPPER_COMMANDS)))

assert set(CANONICAL_COMMANDS) == set(CONSUMER_SKILLS), "Command-skill installer must cover every consumer command"

#: The pre-#6475 dotted folder names of the canonical commands (read/retire only).
LEGACY_COMMAND_SKILL_NAMES: frozenset[str] = legacy_command_skill_names(CANONICAL_COMMANDS)

#: Disposition state of an edited legacy dotted skill kept on disk but no longer managed.
LEGACY_KEPT = "legacy_kept"
#: Disposition state of a canonical path occupied by content Spec Kitty does not own.
COLLISION = "collision"
#: Dispositions that skip one path with a warning instead of failing the batch (FR-019/FR-020).
WARNING_DISPOSITIONS = frozenset({LEGACY_KEPT, COLLISION})

_CLI_WRAPPER_DESCRIPTIONS: dict[str, str] = {
    "consolidate": "Consolidate an accepted mission",
    "status": "Show mission and work package status",
}

_CLI_WRAPPER_COMMANDS: dict[str, str] = {
    "consolidate": "spec-kitty consolidate",
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
    regenerated:
        Paths of drifted manifest-owned command-skill projections that were
        regenerated to the canonical render on the DERIVED/IGNORED surface
        (#6155) — reported per-path rather than silently folded into ``added``.
    errors:
        Human-readable error strings for non-fatal issues (empty unless a
        caller uses the error-collection path, which is reserved for future
        use).
    collisions:
        Canonical paths skipped because content Spec Kitty does not own
        occupies them (FR-019); not counted as installed.
    legacy_removed:
        Unmodified legacy dotted command skills (pre-#6475) deleted, or whose
        absent file's manifest entry was dropped.
    legacy_kept:
        Edited legacy dotted command skills kept on disk and no longer managed.
    """

    added: list[str] = field(default_factory=list)
    already_installed: list[str] = field(default_factory=list)
    reused_shared: list[str] = field(default_factory=list)
    regenerated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    legacy_removed: list[str] = field(default_factory=list)
    legacy_kept: list[str] = field(default_factory=list)

    @property
    def installed_count(self) -> int:
        """Command skills this run wrote or newly claimed: added, reused and regenerated (#6155)."""
        return len(self.added) + len(self.reused_shared) + len(self.regenerated)


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
    legacy_removed / legacy_kept:
        Legacy dotted entries retired by the same pass (see :class:`InstallReport`);
        never part of ``deref``.
    """

    deref: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    legacy_removed: list[str] = field(default_factory=list)
    legacy_kept: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    """Summary of a :func:`verify` operation.

    Attributes
    ----------
    drift:
        Paths whose on-disk SHA-256 no longer matches the stored hash.
    orphans:
        Files under a canonical ``.agents/skills/spec-kitty-<command>/``
        folder (explicit command set only, FR-004) that are not in the
        manifest and are not a collision.
    gaps:
        Manifest entries whose files are missing from disk.
    stale:
        Manifest entries for command skills that are no longer canonical
        (legacy dotted entries excluded; see ``legacy``).
    unsafe:
        Manifest entries or orphan candidates that resolve outside
        ``repo_root`` through symlinks.
    legacy:
        Legacy dotted ``spec-kitty.<command>/SKILL.md`` paths: manifest
        entries still recorded and folders still on disk (pre-#6475).
    collisions:
        Canonical ``SKILL.md`` paths occupied by content the manifest does not
        own and that is not today's canonical rendering (FR-019).
    """

    drift: list[str] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unsafe: list[str] = field(default_factory=list)
    legacy: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def collision_warning(path: str) -> str:
    """The one wording for a canonical path skipped because the user's own content occupies it (FR-019)."""
    return f"Your own folder blocks command skill {path} — rename or remove it, then run `spec-kitty doctor skills --fix`"


def legacy_kept_warning(path: str) -> str:
    """The one wording for an edited legacy dotted command skill that was kept (FR-020)."""
    return f"Legacy dotted command skill {path} has your edits, so it was kept; it is no longer managed — remove it when you no longer need your edits"


def install_warnings(report: InstallReport | RemoveReport) -> list[str]:
    """Return the per-path warnings an install or remove report carries, collisions first."""
    collisions = report.collisions if isinstance(report, InstallReport) else []
    return [collision_warning(path) for path in collisions] + [legacy_kept_warning(path) for path in report.legacy_kept]


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
        skill_md: str = rendered.to_skill_md()
        return skill_md.encode("utf-8")

    if command not in CLI_WRAPPER_COMMANDS:
        raise InstallerError("unknown_command", command=command)

    description = _CLI_WRAPPER_DESCRIPTIONS[command]
    cli_command = _CLI_WRAPPER_COMMANDS[command]
    body = (
        f"# /{command_skill_name(command)} - {description}\n\n"
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
    frontmatter = f"---\nname: {command_skill_name(command)}\ndescription: {description}\nuser-invocable: true\n---\n"
    skill_md = frontmatter + (body if body.startswith("\n") else "\n" + body)
    return skill_md.encode("utf-8")


#: The User Input block's token example as WP02 rewrote it, and as releases before #6475 wrote it.
_USER_INPUT_TOKENS = ("spec-kitty-<command>`", "spec-kitty.<command>`")


def legacy_rendering(content: bytes, command: str) -> bytes:
    """Reconstruct *content* (today's render of *command*) as a release before #6475 wrote it.

    Before the rename the frontmatter ``name`` and every invocation token used the dotted
    ``spec-kitty.<command>`` form (A-M1). Restoring the name, reversing the invocation rewrite
    and the User Input block example yields the bytes that release would write from today's
    templates, so an unedited legacy file whose recorded hash went stale is still proven ours.
    """
    text = content.decode("utf-8")
    text = text.replace(f"name: {command_skill_name(command)}\n", f"name: {legacy_command_skill_name(command)}\n", 1)
    text = _HYPHEN_TOKEN.sub(lambda m: f"{m['sigil']}{legacy_command_skill_name(m['name'].removeprefix(COMMAND_SKILL_PREFIX))}", text)
    return text.replace(*_USER_INPUT_TOKENS).encode("utf-8")


def _hyphen_token_pattern() -> re.Pattern[str]:
    """Match ``/``, ``$`` or ``/skill:`` + a canonical skill name, on the rewrite's token boundary."""
    names = "|".join(re.escape(command_skill_name(c)) for c in sorted(CANONICAL_COMMANDS, key=lambda c: (-len(c), c)))
    return re.compile(rf"(?<![A-Za-z0-9_.:/$-])(?P<sigil>/skill:|/|\$)(?P<name>{names})(?![A-Za-z0-9_-]|\.[A-Za-z0-9])")


_HYPHEN_TOKEN = _hyphen_token_pattern()


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
    """Reject managed paths that escape the project root through symlinks.

    Refuses a symlink loop anywhere in ``abs_path``'s components on every
    interpreter, not only 3.11/3.12 (``kernel.resolution.resolve_rejecting_loops``).
    """
    repo_resolved = repo_root.resolve()
    try:
        resolved_target = resolve_rejecting_loops(abs_path)
    except OSError as exc:
        raise InstallerError("unsafe_path", path=rel_path, detail=str(exc)) from exc

    if not resolved_target.is_relative_to(repo_resolved):
        raise InstallerError(
            "unsafe_path",
            path=rel_path,
            resolved=str(resolved_target),
            repo_root=str(repo_resolved),
        )


def is_canonical_rel_path(rel_path: str) -> bool:
    """Whether *rel_path* is ``.agents/skills/spec-kitty-<command>/SKILL.md`` for a canonical command."""
    return parse_command_skill_rel_path(rel_path, CANONICAL_COMMANDS) is not None


def is_legacy_rel_path(rel_path: str) -> bool:
    """Whether *rel_path* is the pre-#6475 dotted ``SKILL.md`` path of a canonical command."""
    return parse_legacy_command_skill_rel_path(rel_path, CANONICAL_COMMANDS) is not None


def _get_version() -> str:
    """Return the current Spec Kitty CLI version, or a dev fallback."""
    try:
        import specify_cli as _sk  # noqa: PLC0415

        return getattr(_sk, "__version__", "0.0.0-dev")
    except Exception:  # pragma: no cover
        return "0.0.0-dev"


def _shared_skills_projection_regenerable() -> bool:
    """Whether the command-skill projection may be regenerated on drift, read at runtime (#6155).

    The single authority for this surface's class is the ``shared_skills_projection`` entry of
    ``specify_cli.state.contract.STATE_SURFACES``: the regenerate/prune of a drifted
    manifest-owned ``.agents/skills/spec-kitty-<cmd>/SKILL.md`` is sound ONLY while that surface
    is DERIVED (never authoritative) and git-IGNORED (never a committed edit). Reading the
    contract here, rather than hard-coding the premise, makes the regenerate self-checking: if
    the surface were ever reclassified the installer stops clobbering and falls through to the
    operator-consent branch instead (item 2 / FR-002 / C-002).
    """
    surface = next((s for s in state_contract.STATE_SURFACES if s.name == "shared_skills_projection"), None)
    return surface is not None and surface.authority is state_contract.AuthorityClass.DERIVED and surface.git_class is state_contract.GitClass.IGNORED


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_OWNER = "command_skills"
_LEGACY_REPORT_KINDS = frozenset({"legacy_removed", LEGACY_KEPT})
_MANIFEST = ".kittify/command-skills-manifest.json"
_COLLISION_REASON = "Content Spec Kitty does not own occupies this command skill path; skipped"
_LEGACY_KEPT_REASON = "Edited legacy dotted command skill kept on disk; it is no longer managed"


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


_MODE_RELAXABLE_KINDS = frozenset({"directory", "file", "symlink"})


def windows_dir_mode_only_divergence(observed: FileState, planned: FileState) -> bool:
    """Return True when a node diverges from the plan *only* by POSIX mode on Windows.

    A freshly-created shared skills directory (e.g. ``.agents/skills``) carries a
    POSIX ``mode`` of ``0o755`` in the plan, but Windows ``os.chmod`` cannot
    represent those bits, so the observed directory mode can never match the plan.
    Two gates compare that planned mode against the freshly-observed directory --
    the completion re-check in the managed-skills provider AND the doctrine apply's
    command-parent receipt check (``installer._command_parent_receipts``). Left
    unhandled either makes ``upgrade`` unable to converge in one pass on Windows:
    the re-check raises (#4776) or a ``chmod`` is re-planned forever (#4777), and
    the charter skills never apply.

    Treating that single, host-inherent divergence as satisfied lets ``upgrade``
    converge in one pass with both command AND charter skills applied
    (FR-005/006) and report zero dry-run repairs once converged (FR-007).

    **File/symlink extension (#4927, T005).** Every managed *file*'s
    Windows-representable mode differs from its planned POSIX mode too --
    exactly the same host-inherent shape as the directory case above -- so
    the relaxation is generalized to ``file``/``symlink`` kinds under this
    SAME authority (C-002: no second divergence authority). The relaxation
    stays deliberately narrow: same-kind effects only (``observed.kind ==
    planned.kind``, restricted to ``directory``/``file``/``symlink``), only
    when the *sole* remaining difference after equalizing ``mode`` is the
    mode itself, and only on Windows -- the host check goes through the
    canonical patchable ``kernel.paths.is_windows`` seam (module attribute
    at call time, so tests monkeypatch ``kernel.paths.is_windows`` without
    faking ``os.name``), so POSIX file- and directory-mode correctness is
    never weakened (NFR-003/FR-007). Callers whose "planned" state does not
    carry a comparable ``mtime_ns`` (e.g. the project-skill projection's
    ``_expected_project_entries``, which never sets one) must normalize
    ``mtime_ns`` on the observed side before calling, exactly as the
    managed-skills completion re-check already does -- this helper does not
    special-case ``mtime_ns`` itself.
    """
    if not kernel_paths.is_windows():
        return False
    if observed.kind != planned.kind or observed.kind not in _MODE_RELAXABLE_KINDS:
        return False
    return bool(replace(observed, mode=planned.mode) == planned)


def _manifest_change_bytes(manifest: manifest_store.SkillsManifest) -> bytes:
    """Serialize a manifest with ``installed_at`` neutralized, for change detection only.

    #4134: ``installed_at`` is a per-invocation wall-clock stamp (sampled once as
    ``_CommandBatch.time`` and threaded into ``ManifestEntry.installed_at``).
    Excluding it from the change-detection comparison -- mirroring the
    charter-skill provider's ``_expected_entries``, which compares with
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


def _adoptable(existing: ManifestEntry | None, before: FileState, digest: str) -> bool:
    """Return True when an adopt-only pass may stage this command's entry.

    Only exact canonical bytes in a regular file qualify. An unowned file is
    adopted; an owned one is adopted only to refresh a stale recorded hash
    (an older release's rendering), which never touches the file bytes.
    """
    if before.kind != "file" or before.sha256 != digest:
        return False
    return existing is None or existing.content_hash != digest


def _refreshed_entry(existing: ManifestEntry, digest: str, agents: tuple[str, ...]) -> ManifestEntry:
    """Return *existing* recording the canonical *digest* with *agents* added."""
    entry = replace(existing, content_hash=digest)
    for agent in agents:
        entry = entry.with_agent_added(agent)
    return entry


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
        # #6155: the DERIVED/IGNORED regenerate/prune gate, read once from the state contract
        # per batch (see _shared_skills_projection_regenerable). `_regenerated` names the paths
        # regenerated on drift for the per-path report (item 1).
        self._regenerate_derived = _shared_skills_projection_regenerable()
        self._regenerated: set[str] = set()
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
        rel = command_skill_rel_path(command)
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
        if existing is None and before.kind == "absent" and self.foreign_folder(parent, parent_state):
            return
        digest = manifest_store.fingerprint(content)
        if self.preserve(rel, before, existing, digest, adopt_only=adopt_only):
            return
        if adopt_only and not _adoptable(existing, before, digest):
            return
        owners = tuple(sorted(set(existing.agents if existing else ()) | set(self.agents)))
        entry = ManifestEntry(rel, digest, owners, existing.installed_at if existing else self.time, self.version)
        same = before.kind == "file" and before.sha256 == digest
        if same and existing is not None:
            entry = _refreshed_entry(existing, digest, self.agents)
        kind = "already_installed" if same and existing == entry else "reused_shared" if same else "added"
        if rel in self._regenerated:
            # #6155 item 1: a drifted DERIVED projection regenerated by preserve() is reported
            # per-path (InstallReport.regenerated) rather than folded silently into `added`.
            kind = "regenerated"
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

    def preserve(self, rel: str, before: FileState, existing: ManifestEntry | None, digest: str, *, adopt_only: bool = False) -> bool:
        if before.kind == "directory" or (before.kind == "symlink" and existing is None):
            self.disposition(rel, "preserve", "Unknown node is not command ownership")
            return True
        if before.kind != "file":
            return False
        if existing is not None and before.sha256 not in (existing.content_hash, digest):
            if not adopt_only and self._regenerate_derived:
                # RUNTIME GATE (#6155, item 2). The shared command-skill projection
                # (.agents/skills/spec-kitty-<cmd>/SKILL.md) is regenerated on drift ONLY while
                # `_regenerate_derived` holds -- i.e. while `shared_skills_projection`
                # (state/contract.py) is read at runtime as DERIVED authority and git-IGNORED.
                # On that surface a manifest-owned projection whose on-disk bytes match neither
                # the recorded hash nor the current render is stale or cross-checkout generated
                # output (the tracked manifest and the ignored bytes legitimately disagree
                # between checkouts), never a committed user edit. Regenerate it to the canonical
                # render so install/upgrade/sync/init stay idempotent against the manifest (#702),
                # and name it for the per-path report (item 1) via the regenerated report_kind
                # recorded on the PreparedCommand in install_command(). When the gate does NOT
                # hold the branch falls through to the consent path below (overwrite_paths ->
                # consent_required), which is also where the adopt-only pass lands.
                self._regenerated.add(rel)
                return False
            if rel in self.inputs.consent.overwrite_paths:
                return False  # Explicit exact-path consent: the canonical bytes replace the edit.
            # The gate is off (surface not DERIVED/IGNORED) or this is an adopt-only pass, which
            # never writes bytes: an edited manifest-owned file is not adoptable, so surface it
            # for explicit consent rather than silently skipping it (#5574 / #6155 fall-through).
            self.disposition(rel, "consent_required", "Managed command content has drifted")
            return True
        if existing is None and before.sha256 != digest:
            # FR-019 (operator ruling 2026-10-20): a file the manifest does not own and whose bytes are
            # not the canonical rendering is the user's own; skip this one path with a warning and let
            # the rest of the batch install.
            self.disposition(rel, COLLISION, _COLLISION_REASON)
            return True
        return False

    def foreign_folder(self, parent: str, parent_state: FileState) -> bool:
        """Skip a canonical folder that holds someone else's files but no ``SKILL.md`` (FR-019)."""
        if parent_state.kind != "directory":
            return False
        self.observe(self.root / parent, children=True)
        if not self.observations[self.root / parent].children:
            return False  # An empty leftover folder is safe to fill.
        self.disposition(f"{parent}/SKILL.md", COLLISION, _COLLISION_REASON)
        return True

    def owned_legacy_bytes(self, entry: ManifestEntry, before: FileState) -> bool:
        """Whether a legacy file holds the recorded bytes, or today's render under the legacy name (A-M1)."""
        if before.sha256 == entry.content_hash:
            return True
        command = parse_legacy_command_skill_rel_path(entry.path, CANONICAL_COMMANDS)
        agents = tuple(a for a in (self.agents or entry.agents) if a in SUPPORTED_AGENTS)
        if command is None or not agents:
            return False
        if command in PROMPT_BACKED_COMMANDS:
            template = _resolve_template(self.root, command)
            self.observe(template)
            self.observe(_resolve_observed_input(template))
        try:
            rendered = _render_command_skill(self.root, command, agents[0], self.version)
        except (OSError, ValueError, InstallerError, command_renderer.SkillRenderError):
            return False  # No proof of ownership: keep the file (the safe direction).
        return bool(manifest_store.fingerprint(legacy_rendering(rendered, command)) == before.sha256)

    def release_legacy_entry(self, entry: ManifestEntry, remove_agents: tuple[str, ...]) -> None:
        """Release *remove_agents* from a legacy entry in a remove-only preparation (FR-020).

        Nothing is installed in such a pass, so the remaining owners keep their dotted skill
        (their next install or upgrade migrates it). Only when a removed agent was the last
        owner does the legacy rule run: delete if unmodified, otherwise keep with a warning.
        """
        if not set(remove_agents) & set(entry.agents):
            return
        remaining = tuple(agent for agent in entry.agents if agent not in remove_agents)
        if not remaining:
            self.migrate_legacy_entry(entry)
            return
        updated = replace(entry, agents=remaining)
        self.manifest.upsert(updated)
        self.commands.append(PreparedCommand(entry.path, None, updated, "kept"))

    def migrate_legacy_entry(self, entry: ManifestEntry) -> None:
        """Retire one legacy dotted manifest entry with the single legacy rule (FR-020).

        Owned and unmodified (on-disk hash equals the recorded hash, or today's rendering under
        the legacy name, :func:`legacy_rendering`): delete the file, and the
        folder only when it is then empty. Absent: drop the entry. Anything else (edited bytes,
        a directory, a link, an unsafe parent): keep it on disk, drop the entry, and record a
        ``legacy_kept`` disposition so callers warn that the path is no longer managed. Never the
        DERIVED drift-delete branch of :meth:`remove_entry`.
        """
        try:
            before = self.observe_destination(entry.path)
        except InstallerError as exc:
            if exc.code != "unsafe_path":
                raise
            before = None
        self.manifest.remove_path(entry.path)
        if before is not None and before.kind == "absent":
            self.commands.append(PreparedCommand(entry.path, None, None, "legacy_removed"))
            return
        if before is None or before.kind != "file" or not self.owned_legacy_bytes(entry, before):
            self.commands.append(PreparedCommand(entry.path, None, None, LEGACY_KEPT))
            self.disposition(entry.path, LEGACY_KEPT, _LEGACY_KEPT_REASON)
            return
        proof = OwnershipProof("manifest", f"{_MANIFEST}#{entry.path}")
        self.effect(entry.path, FileState("absent"), entry.agents, proof)
        parent = (self.root / entry.path).parent
        if self.observe(parent, children=True).kind == "directory" and self.observations[parent].children == ("SKILL.md",):
            self.effect(parent.relative_to(self.root).as_posix(), FileState("absent"), entry.agents, proof)
        self.commands.append(PreparedCommand(entry.path, None, None, "legacy_removed", proof))

    def remove_entry(self, entry: ManifestEntry, remaining: tuple[str, ...], *, retired: bool = False) -> None:
        before = self.observe_destination(entry.path)
        # #6155 item 3: a DIRECTORY at the projection path is always refused. A drifted
        # manifest-owned FILE is pruned ONLY on a RETIRED-command prune (``retired`` -- a path
        # no longer in CANONICAL_COMMANDS, pruned via prune_stale) on the DERIVED/IGNORED
        # surface, where the projection is git-ignored generated output, never a committed edit.
        # Every other caller -- agent deregistration via remove() (retired=False) -- keeps
        # refusing a drifted file with ``consent_required`` -> file_mutation_detected, unchanged.
        if before.kind == "directory" or (before.kind == "file" and before.sha256 != entry.content_hash and not (retired and self._regenerate_derived)):
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
    """Resolve ``path``, raising ``OSError(errno.ELOOP)`` on a symlink loop.

    Interpreter-invariant on 3.11-3.14 via
    ``kernel.resolution.resolve_rejecting_loops``: a genuine programmer
    ``RuntimeError`` (not loop-shaped) still escapes unmasked.
    """
    return resolve_rejecting_loops(path)


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


def canonical_digest(project_root: Path, command: str) -> str | None:
    """Return the SHA-256 of today's canonical rendering of *command*, read-only.

    The roster is the configured command-skill agents, exactly as
    :func:`prepare_commands` receives them from its callers. ``None`` means
    there is no single canonical rendering to compare against: the command is
    not canonical, no command-skill agent is configured, rendering failed, or
    the agents render different bytes. Nothing is written.
    """
    from specify_cli.core.agent_config import get_configured_agents

    if command not in CANONICAL_COMMANDS:
        return None
    try:
        agents = tuple(agent for agent in get_configured_agents(project_root) if agent in SUPPORTED_AGENTS)
        version = _get_version()
        variants = {_render_command_skill(project_root, command, agent, version) for agent in agents}
    except (OSError, ValueError, AgentConfigError, InstallerError, command_renderer.SkillRenderError):
        return None
    if len(variants) != 1:
        return None
    digest: str = manifest_store.fingerprint(next(iter(variants)))
    return digest


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
    bytes at a canonical path are skipped as a ``collision`` (FR-019); unknown
    links and directories are preserved; existing manifest owners survive
    shared reuse. Unless *adopt_only*, every legacy dotted manifest entry is
    retired first by :meth:`_CommandBatch.migrate_legacy_entry` (FR-020), so
    install, prune, remove and provider repair share one legacy rule.
    """
    try:
        if any(a not in SUPPORTED_AGENTS for a in agents + remove_agents):
            raise InstallerError("unsupported_agent", agents=agents + remove_agents)
        batch = _CommandBatch(inputs, agents)
        legacy = tuple(entry for entry in batch.original_entries if is_legacy_rel_path(entry.path))
        for entry in () if adopt_only else legacy:
            if remove_agents and not agents:
                batch.release_legacy_entry(entry, remove_agents)
            else:
                batch.migrate_legacy_entry(entry)
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
            if entry in legacy:
                continue  # Retired above by the legacy rule (FR-020), or left alone when adopting only.
            retired = bool(prune and not is_canonical_rel_path(entry.path))
            if remove_agents or retired:
                selected = set(remove_agents or agents or entry.agents)
                if selected.intersection(entry.agents):
                    batch.remove_entry(entry, tuple(a for a in entry.agents if a not in selected), retired=retired)
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
    report.collisions.extend(d.path for d in assessment.dispositions if d.state == COLLISION and d.path is not None)
    return report


def remove(repo_root: Path, agent_key: str) -> RemoveReport:
    """Release one owner's references; delete only the final proven owner."""
    assessment = _direct_assessment(repo_root, (), remove_agents=(agent_key,))
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    report = RemoveReport()
    for command in payload.commands:
        if command.report_kind not in _LEGACY_REPORT_KINDS:
            report.deref.append(command.path)
        getattr(report, command.report_kind).append(command.path)
    return report


def prune_stale(repo_root: Path) -> list[str]:
    """Prune manifest entries of retired commands and legacy dotted entries; return deleted paths.

    * A retired command's entry (a path not in :data:`CANONICAL_COMMANDS`, not legacy) is pruned
      through :meth:`_CommandBatch.remove_entry`. While the projection surface is DERIVED and
      git-IGNORED (#6155), that includes a *drifted* file: it is deleted, not preserved. A
      directory at the path is refused (``file_mutation_detected``).
    * A legacy dotted entry follows the legacy rule (FR-020): an unmodified file is deleted, an
      edited one is kept on disk and only its entry is dropped (never deleted here).

    Returns the deleted paths: retired ones, then legacy ones (an absent legacy file's dropped
    entry included).
    """
    assessment = _direct_assessment(repo_root, (), prune=True, remove_agents=())
    payload = assessment.prepared
    assert isinstance(payload, PreparedCommands)
    return [command.path for command in payload.commands if command.report_kind in {"deleted", "legacy_removed"}]


def verify(repo_root: Path) -> VerifyReport:
    """Scan for drift, orphans, gaps, legacy leftovers and collisions without mutating anything.

    This function is read-only.  It never writes to the manifest or to the
    filesystem.

    Parameters
    ----------
    repo_root:
        Absolute path to the project root.

    Returns
    -------
    VerifyReport
        * ``drift`` / ``gaps``: canonical or retired entries whose on-disk
          SHA-256 no longer matches the stored hash / whose files are absent.
        * ``legacy``: legacy dotted entries and on-disk dotted folders of the
          canonical commands (reported, never repaired by name; R-m5).
        * ``collisions`` / ``orphans``: content under a canonical
          ``spec-kitty-<command>/`` folder that the manifest does not record.
          Only the explicit command set is scanned (FR-004): a user's own
          ``spec-kitty-mine/`` is never reported.

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
    _verify_entries(repo_root, manifest, report)
    _verify_legacy_folders(repo_root, report)
    _verify_canonical_folders(repo_root, {e.path for e in manifest.entries}, report)
    return report


def _verify_entries(repo_root: Path, manifest: manifest_store.SkillsManifest, report: VerifyReport) -> None:
    """Classify each manifest entry as unsafe, legacy, stale, gap or drift."""
    for entry in manifest.entries:
        if is_legacy_rel_path(entry.path):
            # Retired by the legacy rule on the next preparation, which never follows a link
            # out of the project; reported read-only here, never as drift/unsafe (R-m5).
            report.legacy.append(entry.path)
            continue
        abs_path = repo_root / entry.path
        try:
            _ensure_project_confined(repo_root, entry.path, abs_path)
        except InstallerError:
            report.unsafe.append(entry.path)
            continue
        if not is_canonical_rel_path(entry.path):
            report.stale.append(entry.path)
        if not abs_path.exists():
            report.gaps.append(entry.path)
            continue
        on_disk = manifest_store.fingerprint_file(abs_path)
        if on_disk != entry.content_hash:
            report.drift.append(entry.path)


def _verify_legacy_folders(repo_root: Path, report: VerifyReport) -> None:
    """Report on-disk legacy dotted leftovers of the canonical commands (explicit set only).

    The ``SKILL.md`` path when it still exists; otherwise the folder itself
    (``.agents/skills/spec-kitty.<command>/``) when only other files remain in it.
    """
    for command in CANONICAL_COMMANDS:
        rel = legacy_command_skill_rel_path(command)
        if rel in report.legacy:
            continue
        if os.path.lexists(repo_root / rel):
            report.legacy.append(rel)
        elif os.path.lexists((repo_root / rel).parent):
            report.legacy.append(f"{Path(rel).parent.as_posix()}/")


def _verify_canonical_folders(repo_root: Path, manifest_paths: set[str], report: VerifyReport) -> None:
    """Report unowned content in canonical command folders as collisions or orphans."""
    for command in CANONICAL_COMMANDS:
        rel = command_skill_rel_path(command)
        folder = (repo_root / rel).parent
        if not folder.is_dir():
            continue
        if rel not in manifest_paths and _is_collision(repo_root, command, repo_root / rel, folder):
            report.collisions.append(rel)
            continue
        for file in sorted(folder.rglob("*")):
            if not file.is_file():
                continue
            file_rel = to_posix(file.relative_to(repo_root))
            try:
                _ensure_project_confined(repo_root, file_rel, file)
            except InstallerError:
                report.unsafe.append(file_rel)
                continue
            if file_rel not in manifest_paths:
                report.orphans.append(file_rel)


def _is_collision(repo_root: Path, command: str, skill_md: Path, folder: Path) -> bool:
    """Mirror the installer's FR-019 skip: unowned non-canonical ``SKILL.md``, or a foreign folder."""
    if folder.is_symlink():
        return False  # A package link is the installer's ``preserve`` case, reported as before.
    if not os.path.lexists(skill_md):
        return any(folder.iterdir())
    if skill_md.is_symlink() or not skill_md.is_file():
        return False
    on_disk: str = manifest_store.fingerprint_file(skill_md)
    return on_disk != canonical_digest(repo_root, command)
