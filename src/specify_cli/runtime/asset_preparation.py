"""Retained global runtime asset batches, including owner inventory and locks.

This is private to the three global asset owners. It is not a project installer,
filesystem overlay, rollback service or serialized apply interface. Catalog and
format decisions stay in bootstrap, agent_commands and agent_skills.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import logging
import os
from pathlib import Path
import stat
import sys
from typing import TYPE_CHECKING, Literal, TypeVar

if TYPE_CHECKING:
    from specify_cli.runtime.agent_skills import GlobalSkillSelection

from kernel.errors import GuardedReadError
from kernel.locks import machine_file_lock
from kernel.paths import get_runtime_state_root
from specify_cli.core.safe_delete import safe_rmdir, safe_unlink
from specify_cli.runtime.generated_writer import generated_temporary_path, write_generated_file
from specify_cli.tool_surface.operations import (
    ApplyConsent,
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


def digest(data: bytes) -> str:
    """Hash exact asset bytes, without text or timestamp normalization."""
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 -- raw asset integrity, not charter hashing


def node_state(path: Path, *, read_content: bool = True) -> FileState:
    """Read one node without following its final link.

    ``read_content=False`` records a regular file's ``lstat`` shape but skips the
    byte read, standing in the empty-content digest. Used ONLY for owner lock
    files (#4703): on Windows ``msvcrt.locking()`` is mandatory, so reading a
    lock this process holds raises ``PermissionError`` — and a lock is a
    self-managed, definitionally-empty artifact whose content is never verified
    or used (only its kind: absent vs regular file), so the byte read is both
    fatal and pointless there.
    """
    try:
        info = path.lstat()
    except FileNotFoundError:
        return FileState("absent")
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        return FileState("symlink", target=os.readlink(path), mode=mode, mtime_ns=info.st_mtime_ns)
    if stat.S_ISDIR(info.st_mode):
        return FileState("directory", mode=mode, mtime_ns=info.st_mtime_ns)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Unsupported asset node: {path}")
    sha256 = digest(path.read_bytes()) if read_content else digest(b"")
    return FileState("file", sha256=sha256, mode=mode, mtime_ns=info.st_mtime_ns)


def _action(before: FileState, after: FileState) -> str | None:
    if before.kind == "absent":
        return "create" if after.kind != "absent" else None
    if after.kind == "absent":
        return "delete"
    if before.kind != after.kind:
        return "replace"
    if before.sha256 != after.sha256:
        return "update"
    if before.target != after.target:
        return "retarget"
    return "chmod" if before.mode != after.mode else None


@dataclass(frozen=True)
class AssetWrite:
    """Exact prepared content and its owner-produced effect."""

    effect: PhysicalEffect
    content: bytes | None


#: Role of an observed node, tagged by CALL SITE, never by path geography --
#: sources can share the HOME prefix under test layouts (SPEC_KITTY_TEMPLATE_ROOT,
#: editable installs), so a path-based classifier would misclassify them.
#: ``source_read``: a package/template source read (``source()``, or a
#: ``tree()``/child observation walking the SOURCE side of a copy).
#: ``destination_probe``: an inventory probe of this owner's managed
#: destination under home (``asset()``, the destination side of ``tree()``,
#: ``parents()``, ``retire()``, ``backup()``, and ``finish()``'s inventory/
#: version-stamp/lock bookkeeping). A concurrent peer materializing HOME
#: destination nodes must not be mistaken for asset-input drift (FR-002/C-002).
ObservationRole = Literal["source_read", "destination_probe"]


@dataclass(frozen=True)
class AssetObservation:
    """Exact node plus directory membership, including ignored children."""

    path: Path
    state: FileState
    children: tuple[str, ...] | None = None
    identity: tuple[int, int] | None = None
    role: ObservationRole = "source_read"


@dataclass(frozen=True)
class PreparedAssets:
    """Immutable output of one global owner; never a replay token."""

    writes: tuple[AssetWrite, ...]
    observations: tuple[AssetObservation, ...]
    environment: tuple[tuple[str, str | None], ...]
    lock_path: Path
    anchor: Path
    temporary_paths: tuple[Path, ...] = ()
    additional_lock_paths: tuple[Path, ...] = ()

    @property
    def lock_paths(self) -> tuple[Path, ...]:
        return tuple(sorted({self.lock_path, *self.additional_lock_paths}))


_SOURCE_ENV = (
    "HOME",
    "USERPROFILE",
    "SPEC_KITTY_HOME",
    "SPEC_KITTY_TEMPLATE_ROOT",
    "SPEC_KITTY_PACKS_ROOT",
    "XDG_CONFIG_HOME",
    "OPENCODE_CONFIG_DIR",
    "LOCALAPPDATA",
)
_HELD_LOCKS: ContextVar[frozenset[Path]] = ContextVar("global_asset_locks", default=frozenset())


class TornReadError(ValueError):
    """Within one preparation pass, the same path was observed twice with
    different states -- benign evidence of a concurrent peer mid-write on a
    destination-role path, never tolerated on a source-role path (FR-003,
    data-model.md). Carries this owner's serialization identity
    (``lock_paths``/``anchor``, the same values ``finish()`` would put into
    ``PreparedAssets``) so the identity survives past ``incomplete()``, which
    drops the ``AssetPreparation`` instance that raised it.

    Subclasses ``ValueError`` (never a flat replacement) so every existing
    ``except (OSError, ValueError)`` handler keeps matching, and ``str()``
    stays exactly ``f"Asset changed during preparation: {path}"`` -- the
    pre-existing message text and the ``TORN_READ_SIGNAL`` assertions in
    ``tests/runtime/test_generic_asset_scope.py`` are unchanged (research
    D-3).
    """

    def __init__(self, *, path: Path, role: ObservationRole, lock_paths: tuple[Path, ...], anchor: Path) -> None:
        super().__init__(f"Asset changed during preparation: {path}")
        self.path = path
        self.role = role
        self.lock_paths = lock_paths
        self.anchor = anchor


def global_asset_root(owner: str, paths: tuple[Path, ...]) -> OperationRoot:
    """Choose a stable reporting anchor covering resolved global destinations."""
    anchor = Path(os.path.commonpath((Path.home(), *paths))).parent
    return OperationRoot(owner, "global", anchor)


def _observation(path: Path, state: FileState, children: tuple[str, ...] | None = None, role: ObservationRole = "destination_probe") -> AssetObservation:
    if state.kind == "directory":
        info = path.lstat()
        return AssetObservation(path, replace(state, mtime_ns=None), children, (info.st_dev, info.st_ino), role)
    return AssetObservation(path, state, children, role=role)


class AssetPreparation:
    """Collect one runtime owner's canonical assets before any write.

    The private inventory records only canonically equal or successfully
    generated nodes. Unknown bytes never become ownership by hashing them.
    Entries are committed last, so partial installation cannot certify work.
    """

    def __init__(self, owner: str, root: OperationRoot, cache: Path, lock_name: str, consent: ApplyConsent) -> None:
        self.owner, self.root, self.consent = owner, root, consent
        self.lock_path = cache / lock_name
        self.inventory = cache / f"{owner}-assets.json"
        self.observed: dict[Path, AssetObservation] = {}
        self.writes: dict[Path, AssetWrite] = {}
        self.dispositions: list[Disposition] = []
        self.entries: dict[str, dict[str, object]] = {}
        self.previous: dict[str, dict[str, object]] = {}
        self._prune_candidates: dict[Path, tuple[Path, ...]] | None = None
        self.selected: set[Path] = set()
        self.temporary_paths: set[Path] = set()
        self.environment = tuple((name, os.environ.get(name)) for name in _SOURCE_ENV)
        state = self.observe(self.inventory, role="destination_probe")
        if state.kind == "file":
            payload = json.loads(self.inventory.read_bytes())
            if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), dict):
                raise ValueError(f"Invalid global asset inventory: {self.inventory}")
            for relative, record in payload["entries"].items():
                if not isinstance(relative, str) or not isinstance(record, dict):
                    raise ValueError("Invalid global asset inventory entry")
                # PhysicalEffect validates this same confined relative spelling.
                if Path(relative).is_absolute() or "\\" in relative or ":" in relative or any(p in {"", "..", "."} for p in relative.split("/")):
                    raise ValueError("Unconfined global asset inventory entry")
                try:
                    FileState(**record)
                except TypeError as exc:
                    raise ValueError("Invalid global asset inventory state") from exc
            self.previous = payload["entries"]
            self.entries = dict(self.previous)
        elif state.kind != "absent":
            raise ValueError(f"Global inventory is not a regular file: {self.inventory}")

    def observe(self, path: Path, *, members: bool = False, role: ObservationRole = "source_read", read_content: bool = True) -> FileState:
        """Observe ancestry before opening a node; reject escaping parents.

        ``role`` is tagged by the CALLER's call site (source read vs a probe of
        this owner's managed destination under home), never derived from the
        path itself. A path already recorded as ``source_read`` stays
        ``source_read`` even if later probed as a destination (source and
        destination trees can share the HOME prefix under test layouts) so
        genuine source drift is never over-narrowed away (FR-003/C-002).

        ``read_content=False`` observes the node without reading its bytes — used
        only for owner lock files, whose read under a held mandatory lock is
        fatal on Windows and whose content is never verified (#4703).
        """
        for parent in reversed(path.parents):
            if parent != Path(parent.anchor):
                state = node_state(parent)
                system_alias = (
                    sys.platform == "darwin" and parent in {Path("/var"), Path("/tmp")} and state.kind == "symlink" and state.target == f"private/{parent.name}"  # noqa: S108 -- validate macOS system aliases, not a temporary file
                )
                if state.kind not in {"absent", "directory"} and not system_alias:
                    raise ValueError(f"Asset parent is not a directory: {parent}")
                existing_parent = self.observed.get(parent)
                if existing_parent is None:
                    self.observed[parent] = _observation(parent, state, role=role)
                elif role == "source_read" and existing_parent.role != "source_read":
                    self.observed[parent] = replace(existing_parent, role="source_read")
        state = node_state(path, read_content=read_content)
        children = tuple(sorted(p.name for p in path.iterdir())) if members and state.kind == "directory" else None
        previous = self.observed.get(path)
        current = _observation(path, state, children if children is not None else previous.children if previous else None, role=role)
        if previous is not None and (previous.state, previous.identity) != (current.state, current.identity):
            # Effective role mirrors the stickiness rule just below: a path
            # already recorded (or now incoming) as a source read is source
            # drift, never tolerable, regardless of which side is which.
            effective_role: ObservationRole = "source_read" if role == "source_read" or previous.role == "source_read" else "destination_probe"
            raise TornReadError(path=path, role=effective_role, lock_paths=(self.lock_path,), anchor=self.root.path)
        if previous is not None and previous.role == "source_read":
            current = replace(current, role="source_read")
        self.observed[path] = current
        return state

    def source(self, path: Path) -> bytes:
        """Read a required regular source, retaining its exact observations."""
        if self.observe(path).kind != "file":
            raise ValueError(f"Required asset source is not a regular file: {path}")
        return path.read_bytes()

    def preserve(self, path: Path, reason: str, *, drift: bool = False) -> None:
        self.dispositions.append(
            Disposition(
                self.owner,
                self.root.root_id,
                path.relative_to(self.root.path).as_posix(),
                "consent_required" if drift else "preserve",
                reason,
            )
        )

    def _effect(self, path: Path, after: FileState, content: bytes | None, proof: OwnershipProof) -> None:
        before = self.observe(path, role="destination_probe")
        action = _action(before, after)
        relative = path.relative_to(self.root.path).as_posix()
        if action is None:
            self.dispositions.append(Disposition(self.owner, self.root.root_id, relative, "unchanged", "Asset already matches"))
            return
        if after.kind == "file" and action != "chmod" and path != self.lock_path:
            temporary = generated_temporary_path(path)
            if self.observe(temporary, role="destination_probe").kind != "absent":
                raise ValueError(f"Unproven atomic writer artifact must be preserved: {temporary}")
            self.temporary_paths.add(temporary)
        effect = PhysicalEffect(
            self.owner, "global_bootstrap", self.root, relative, action, before, after, "Refresh canonical global asset", (proof,), (self.owner,)
        )
        previous = self.writes.get(path)
        if previous is not None and previous.effect.after != after:
            raise ValueError(f"Conflicting global asset outputs: {path}")
        self.writes[path] = AssetWrite(effect, content)

    def overwrite_internal(self, path: Path, after: FileState, content: bytes | None, proof: OwnershipProof) -> None:
        """Unconditionally overwrite an internal, cache-only bookkeeping file.

        Public counterpart to ``_effect()``, exposing exactly its "always
        overwrite, no drift-preservation" semantics to callers OUTSIDE this
        module (PR-BOUNDARY-001). Deliberately NOT ``asset()``: ``asset()``'s
        drift-preservation logic is correct for user-facing managed files
        (never clobber an edit it cannot prove is unowned) but wrong for an
        internal, cache-only bookkeeping file that only this owner ever
        writes or reads -- a hand-corrupted or torn-write copy is never
        "owned" by a prior inventory entry, so ``asset()`` would PRESERVE it
        forever (every subsequent read stays malformed) instead of
        self-healing on the very next successful write.

        Reserved for internal bookkeeping artifacts this owner alone
        produces and consumes (e.g. the agent-commands freshness stamp) --
        never for files a project author might hand-edit; those must go
        through ``asset()``.

        pr-FRESH-002: a misuse-fails-loudly runtime guard, not just a
        docstring warning. Reuses the SAME classification the ``.lock``
        late-apply convention already encodes elsewhere in this module
        (``_write_order``'s stage-1/stage-6 buckets, and the sibling
        ``_VERSION_FILENAME``/``_FRESHNESS_STAMP_FILENAME`` constants in
        ``agent_commands.py``/``agent_skills.py``): every internal,
        cache-only bookkeeping file this class itself writes -- the
        version stamp, the freshness stamp, the persistent owner lock --
        lives directly in this owner's ``cache`` root (``self.inventory``'s
        parent; ``self.inventory`` and ``self.lock_path`` are both minted
        from the SAME ``cache`` argument at construction) and ends in
        ``.lock``. A user-facing managed asset never satisfies both: it
        lives under the destination tree ``asset()``/``tree()`` write to,
        not the cache root. A target that fails either check is refused
        before ``_effect()`` ever runs.
        """
        cache_root = self.inventory.parent
        if path.parent != cache_root or not path.name.endswith(".lock"):
            reason = f"must be a '.lock' file directly under the owner cache root {cache_root}"
            raise ValueError(f"overwrite_internal() refuses a non-internal target: {path} ({reason})")
        self._effect(path, after, content, proof)

    def parents(self, path: Path) -> None:
        for parent in reversed(path.parents):
            if parent == self.root.path or self.root.path not in parent.parents:
                continue
            state = self.observe(parent, role="destination_probe")
            if state.kind == "absent":
                self._effect(parent, FileState("directory", mode=0o755), None, OwnershipProof("managed_path", f"{self.owner}:required-parent"))

    def asset(self, path: Path, content: bytes | None, mode: int, *, managed_tree: bool = False, canonical_predecessor: bool = False) -> None:
        """Compare canonical output; preserve drift and unknown links/content."""
        before = self.observe(path, role="destination_probe")
        self.selected.add(path)
        relative = path.relative_to(self.root.path).as_posix()
        desired = FileState("directory", mode=mode) if content is None else FileState("file", sha256=digest(content), mode=mode)
        old = self.previous.get(relative)
        owned = old is not None and before.kind == old.get("kind") and before.sha256 == old.get("sha256") and before.target == old.get("target")
        equal = before.kind == desired.kind and before.sha256 == desired.sha256
        allowed_drift = old is not None and relative in self.consent.overwrite_paths
        if before.kind != "absent" and not (owned or equal or allowed_drift or canonical_predecessor or (managed_tree and before.kind != "symlink")):
            self.preserve(path, "Changed managed asset" if old else "Unproven existing asset", drift=old is not None)
            return
        if allowed_drift and not owned and not equal:
            self.backup(path, before, desired)
        if before.kind == "directory" and desired.kind != "directory":
            self.preserve(path, "Directory replacement requires enumerated ownership", drift=True)
            return
        self.parents(path)
        proof = OwnershipProof("manifest", f"{self.inventory.name}:{relative}") if owned else OwnershipProof("managed_path", f"{self.owner}:{relative}")
        if canonical_predecessor:
            # #4609: covers both a version-only marker refresh and a full
            # cross-release content upgrade of an older release's marked file.
            proof = OwnershipProof("canonical_content", f"{self.owner}:{relative}:canonical-predecessor")
        self._effect(path, desired, content, proof)
        self.entries[relative] = asdict(desired)

    def backup(self, path: Path, before: FileState, after: FileState) -> None:
        """Allocate a retained state-derived backup; collisions are never reused."""
        relative = path.relative_to(self.root.path).as_posix()
        identity = json.dumps((relative, asdict(replace(before, mtime_ns=None)), asdict(after)), sort_keys=True).encode()
        base = self.inventory.parent / "backups" / ("state-" + digest(identity))
        candidate = base
        suffix = 0
        while self.observe(candidate, role="destination_probe").kind != "absent":
            suffix += 1
            candidate = base.with_name(f"{base.name}-{suffix}")
        target = candidate / relative
        self.parents(target)
        data = self.source(path) if before.kind == "file" else None
        self._effect(target, replace(before, mtime_ns=None), data, OwnershipProof("manifest", f"{self.inventory.name}:{relative}"))

    def retire(self, path: Path) -> bool:
        """Remove only exact inventory-owned unchanged nodes; retain drift."""
        before = self.observe(path, members=True, role="destination_probe")
        if before.kind == "absent":
            return True
        relative = path.relative_to(self.root.path).as_posix()
        old = self.previous.get(relative)
        if old is None or (before.kind, before.sha256, before.target) != (old.get("kind"), old.get("sha256"), old.get("target")):
            self.preserve(path, "Unproven or edited retired asset", drift=old is not None)
            return False
        if before.kind == "directory":
            removable = [self.retire(child) for child in sorted(path.iterdir())]
            if not all(removable):
                self.preserve(path, "Retired directory contains preserved content")
                return False
        self._effect(path, FileState("absent"), None, OwnershipProof("manifest", f"{self.inventory.name}:{relative}"))
        self.entries.pop(relative, None)
        return True

    def prune_missing(self, destination: Path) -> None:
        """Inspect recorded descendants absent from this complete source tree."""
        if self._prune_candidates is None:
            descendants: dict[Path, list[Path]] = {}
            for relative in self.previous:
                path = self.root.path / relative
                for parent in path.parents:
                    descendants.setdefault(parent, []).append(path)
            self._prune_candidates = {parent: tuple(sorted(paths, key=lambda path: len(path.parts))) for parent, paths in descendants.items()}
        candidates = self._prune_candidates.get(destination, ())
        retired: list[Path] = []
        for path in candidates:
            if path in self.selected or any(parent in retired for parent in path.parents):
                continue
            self.retire(path)
            retired.append(path)

    def tree(self, source: Path, destination: Path, *, readonly: bool = False, managed_tree: bool = False) -> None:
        """Prepare all source descendants, retaining empty dirs and executable bits."""
        source_state = self.observe(source, members=True)
        if source_state.kind != "directory":
            raise ValueError(f"Required asset tree unavailable: {source}")
        dest_state = self.observe(destination, role="destination_probe")
        if dest_state.kind not in {"directory", "absent"}:
            self.preserve(destination, "Unproven asset tree replacement")
            return
        # Package directory modes are not portable (notably through pipx on Windows).
        # Managed destinations must stay traversable and writable while children land.
        directory_mode = 0o755 if managed_tree else source_state.mode or 0o755
        self.asset(destination, None, directory_mode, managed_tree=managed_tree)
        for child in sorted(source.iterdir()):
            state = self.observe(child)
            target = destination / child.name
            if state.kind == "directory":
                self.tree(child, target, readonly=readonly, managed_tree=managed_tree)
            elif state.kind == "file":
                mode = state.mode or 0o644
                self.asset(target, self.source(child), mode & ~0o222 if readonly else mode, managed_tree=managed_tree)
            else:
                raise ValueError(f"Unsupported source asset kind: {child}")

    def finish(self, version_path: Path | None, version: str) -> OwnerAssessment:
        """Retain supporting inventory/stamp bytes; never refresh equal content."""
        if self.entries != self.previous:
            data = (json.dumps({"schema_version": 1, "entries": self.entries}, sort_keys=True, indent=2) + "\n").encode()
            self.parents(self.inventory)
            self._effect(self.inventory, FileState("file", sha256=digest(data), mode=0o644), data, OwnershipProof("managed_path", f"{self.owner}:inventory"))
        if version_path is not None:
            self.parents(version_path)
            data = version.encode()
            self._effect(version_path, FileState("file", sha256=digest(data), mode=0o644), data, OwnershipProof("managed_path", f"{self.owner}:version-stamp"))
        if self.writes:
            self.parents(self.lock_path)
            # #4703: observe the owner lock by lstat only. finish() runs inside
            # apply_with_reassess's under-lock rebuild, so this process may hold
            # this exact lock; reading its bytes would raise on Windows. Only its
            # kind (absent vs regular file) is used, never its content.
            lock = self.observe(self.lock_path, role="destination_probe", read_content=False)
            if lock.kind == "absent":
                self._effect(
                    self.lock_path, FileState("file", sha256=digest(b""), mode=0o644), b"", OwnershipProof("managed_path", f"{self.owner}:persistent-lock")
                )
            elif lock.kind != "file":
                raise ValueError("Global owner lock is not a regular file")
        writes = tuple(self.writes.values())
        prepared = PreparedAssets(writes, tuple(self.observed.values()), self.environment, self.lock_path, self.root.path, tuple(sorted(self.temporary_paths)))
        return OwnerAssessment(
            self.owner,
            self.root,
            tuple(w.effect for w in writes),
            tuple(self.dispositions),
            inputs_fingerprint=(InputObservation("assets", prepared.observations),),
            prepared=prepared,
            consent=self.consent,
        )


def _diagnostic_code(error: Exception) -> str:
    """Route on type, never message text (research D-3): a destination-role
    ``TornReadError`` is ``asset_torn_read`` (whether it recurred under the
    serialization point or re-entrantly), a source-role one is
    ``asset_source_drift``, and everything else keeps the existing
    ``global_assets_unavailable`` code.
    """
    if isinstance(error, TornReadError):
        return "asset_source_drift" if error.role == "source_read" else "asset_torn_read"
    return "global_assets_unavailable"


def incomplete(owner: str, root: OperationRoot, error: Exception) -> OwnerAssessment:
    """A source/config failure never becomes a complete empty assessment.

    Message text is unchanged (``str(error)``); only the diagnostic ``code``
    is distinguished for a ``TornReadError`` (FR-003).
    """
    return OwnerAssessment(owner, root, complete=False, diagnostics=(Diagnostic(_diagnostic_code(error), owner, "error", str(error)),))


class StartupAssetError(GuardedReadError, RuntimeError):
    """Terminal startup-asset-preparation failure (FR-005/C-010).

    Raised by ``bootstrap.ensure_runtime``, ``agent_commands.
    _apply_command_assessment`` and ``agent_skills.ensure_global_agent_skills``
    in place of a bare ``RuntimeError`` when an assessment is incomplete or an
    apply outcome is neither ``applied`` nor ``skipped``. Multiple-inherits
    ``RuntimeError`` so existing ``except RuntimeError`` callers keep matching
    (research D-7), and ``GuardedReadError`` so ``_run_app_with_error_hook``
    renders it uniformly: exit 1, one stderr line, or one JSON object under
    ``--json`` -- no traceback (C-010, reusing the existing seam, no new
    renderer).

    ``code`` is a Python attribute only, never part of the JSON envelope --
    ``_guarded_read_error_json_payload`` emits only ``error``/``kind``/``path``
    and stays unchanged.
    """

    def __init__(self, reason: str, *, path: str | None, code: str) -> None:
        super().__init__(reason, path=path, reason=reason)
        self.code = code


def _startup_asset_error_hint(code: str) -> str:
    """The actionable next step depends on WHY startup preparation could not
    complete (FR-005/US3.1-3.3), and must NEVER suggest a destructive "fix"
    that could wipe unrelated state living in the SAME Spec Kitty home: on
    Windows ``get_kittify_home()`` resolves to the unified runtime root
    (``specify_cli.paths.get_runtime_root()``), which ALSO holds auth
    credentials (``auth/secure_storage/file_fallback.py`` stores them at
    ``get_runtime_root().base / "auth"``) -- deleting "the partially-written
    home" can delete a user's saved auth alongside it.

    - ``asset_torn_read``: a torn read that recurs under the serialization
      point means a DIFFERENT writer is racing this same home -- unlocked,
      or a different CLI version's peer, never a crashed one (a crashed
      peer's partial write is already absorbed by the locked reassess
      itself, so this case is never "go delete something").
    - ``asset_source_drift``: the installed package changed mid-run;
      reinstalling is a safe, non-destructive fix.
    - anything else (US3.3, content "same as today"): re-running resolves a
      genuinely transient failure, but a PERMANENT one (a lock path that is
      a directory or a dangling symlink, the home itself being a plain
      file, ...) needs a real diagnostic, not a blind retry loop or
      operator-authored deletion advice.
    """
    if code == "asset_torn_read":
        return "another spec-kitty process (possibly a different version) is writing the same Spec Kitty home -- let it finish or stop it, then re-run the command"
    if code == "asset_source_drift":
        return "the installed package's assets changed while this command was running -- re-run the command, and if it persists reinstall spec-kitty"
    return "re-run the command; if it persists, run `spec-kitty doctor --help` to find the right diagnostic"


def startup_asset_error(owner_key: str, diagnostics: tuple[Diagnostic, ...]) -> StartupAssetError:
    """Build the terminal ``StartupAssetError`` for one owner's diagnostics.

    ``reason`` names the owner, joins every diagnostic message, and appends a
    next-step hint that depends on the FIRST diagnostic's code (FR-005/
    US3.1-3.3) -- see :func:`_startup_asset_error_hint`. ``path`` is always
    ``None`` here: this call site only ever sees ``assessment.diagnostics``
    (plain message strings, never a carried typed exception), and
    ``Diagnostic`` itself has no path field -- guessing one out of message
    text would be exactly the message-parsing research D-3 rules out, so it
    stays unset rather than fabricated. ``code`` is the first diagnostic's
    code.
    """
    code = diagnostics[0].code if diagnostics else "global_assets_unavailable"
    reason = f"{owner_key}: " + "; ".join(d.message for d in diagnostics) + "; " + _startup_asset_error_hint(code)
    return StartupAssetError(reason, path=None, code=code)


_BuiltAssessment = TypeVar("_BuiltAssessment")


def _is_terminal_torn_read(exc: TornReadError) -> bool:
    """A torn read never escalates (stays terminal) when it is source-role
    (C-001: source drift is never tolerated), or when this process already
    holds ANY serialization point at all (C-005, stronger than a subset
    check).

    Serialization points never nest, and "terminal when held" is the
    conservative rule that covers both of the following, without this call
    site needing to know which one applies:

    - Owners whose anchors COINCIDE (the default layout, where every
      configured agent's directory sits under the same HOME) share the
      IDENTICAL non-reentrant cold-install sentinel -- a nested escalation
      there would self-deadlock on it.
    - Owners whose anchors DIFFER (e.g. ``XDG_CONFIG_HOME`` pointed outside
      HOME gives the commands owner's ``commonpath(...)`` a different
      result, hence a different :func:`_cold_install_sentinel` key from the
      runtime owner's) still risk lock-order inversion if nesting were
      allowed, since batch paths take owner locks in sorted order.
    """
    return exc.role == "source_read" or bool(_HELD_LOCKS.get())


def _waiting_message(exc: TornReadError) -> str:
    """One INFO line (FR-008): never contains "Error" (the #3998 reproducer
    greps for it), so a converged wait is visible but never mistaken for a
    failure.
    """
    return f"{exc.path}: waiting for a concurrent spec-kitty install to finish, then re-checking assets"


def build_serialized(build: Callable[[], _BuiltAssessment], *, logger: logging.Logger | None = None) -> _BuiltAssessment:
    """One unlocked attempt, then escalate ONCE to the serialization point on
    a destination-role torn read (FR-001/FR-002/FR-004/FR-008, NFR-003,
    research D-1/D-4/D-5). Replaces the retired unlocked back-to-back
    ``retry_torn_read`` loop.

    ``build`` MUST construct a fresh ``AssetPreparation`` (and do everything
    through ``finish()``) on every call, so the serialized attempt starts
    from a clean, re-read ``self.observed`` rather than the stale snapshot
    that raised -- and it MUST stop short of any shared, non-retriable side
    effect (such as ``_GlobalAssetPreparation.include()``), which callers
    perform exactly once on the stabilized result. This is generic across
    every global owner (bootstrap/commands/skills); none is special-cased.

    Only a destination-role ``TornReadError`` not already covered by a held
    serialization point is escalated, and only once: see
    :func:`_is_terminal_torn_read` for what stays terminal. Any other
    exception propagates immediately and unchanged, so a genuine failure is
    never masked.

    Scope caveat (plan.md R-4): callers reached OUTSIDE startup (the skills
    installer, ``tool_surface/providers/slash_commands.py``) adopt this same
    helper, so they too may now block briefly on a concurrent installer
    after a destination-role torn read. This is intended and has no flag.
    """
    log = logger if logger is not None else logging.getLogger(__name__)
    try:
        return build()
    except TornReadError as exc:
        if _is_terminal_torn_read(exc):
            raise
        log.info("%s", _waiting_message(exc))
        with _serialize_owner(exc.lock_paths, exc.anchor):
            return build()


class _GlobalAssetPreparation:
    """One physical preparation built by the three runtime format owners.

    Receives live owner-local builders, never opaque OwnerAssessment payloads.
    Shared infrastructure is compared here before freezing one executable batch.
    """

    def __init__(self, consent: ApplyConsent) -> None:
        self.consent = consent
        self.environment = tuple((name, os.environ.get(name)) for name in _SOURCE_ENV)
        self.writes: dict[Path, AssetWrite] = {}
        self.observations: dict[Path, AssetObservation] = {}
        self.locks: set[Path] = set()
        self.anchors: set[Path] = set()
        self.temporary_paths: set[Path] = set()

    def include(self, builder: AssetPreparation, effects: tuple[PhysicalEffect, ...]) -> None:
        if builder.environment != self.environment or builder.consent != self.consent:
            raise ValueError("Global preparation inputs changed between families")
        # #4017 rescope: reuse the builder's own ``finish()``-time observation
        # of its lock path when one is already on record, instead of calling
        # ``observe()`` again here. ``include()`` runs OUTSIDE the retried
        # ``build()`` (this batch is shared across owners and must never
        # replay a partial merge), so a second, needless observation of the
        # SAME path here is exactly the shape of torn read this rescope
        # fixes -- eliminating the duplicate observation removes the race
        # rather than adding another retry layer for it. Only fall back to a
        # fresh probe when ``build()`` never had reason to observe the lock
        # (an empty batch, e.g. nothing to write).
        existing_lock_state = builder.observed.get(builder.lock_path)
        # #4703: the fallback probe (an empty batch never observed the lock in
        # build()) must NOT read the lock's bytes either. include() runs inside
        # apply_with_reassess's under-lock rebuild for the commands/skills batch
        # owners, so this process may hold this lock; read_content=False takes an
        # lstat only, and include() consumes only lock_state.kind below.
        lock_state = (
            existing_lock_state.state if existing_lock_state is not None else builder.observe(builder.lock_path, role="destination_probe", read_content=False)
        )
        if lock_state.kind not in {"absent", "file"}:
            raise ValueError(f"Global family lock is not a regular file: {builder.lock_path}")
        self.locks.add(builder.lock_path)
        self.anchors.add(builder.root.path)
        self.temporary_paths.update(builder.temporary_paths)
        for observation in builder.observed.values():
            previous = self.observations.get(observation.path)
            if previous is not None:
                if (previous.state, previous.identity) != (observation.state, observation.identity):
                    raise ValueError(f"Global family observations disagree: {observation.path}")
                if previous.children is not None:
                    if observation.children is not None and previous.children != observation.children:
                        raise ValueError(f"Global family membership changed: {observation.path}")
                    observation = replace(observation, children=previous.children)
                if previous.role == "source_read":
                    # #4174 landing-pass: mirror observe()'s own intra-builder
                    # stickiness (a path once recorded source_read stays
                    # source_read) across FAMILIES too. Without this, a later
                    # family's destination_probe include() for a path an
                    # earlier family already tagged source_read silently wins
                    # last-writer-take-all, reopening the exact role-tagged
                    # toleration hole WP02 closed (FR-003/C-002).
                    observation = replace(observation, role="source_read")
            self.observations[observation.path] = observation
        for effect in effects:
            write = builder.writes[effect.destination]
            effect = replace(effect, owner="global_assets")
            previous_write = self.writes.get(effect.destination)
            if previous_write is not None:
                if previous_write.content != write.content:
                    raise ValueError(f"Global family bytes conflict: {effect.destination}")
                effect = coalesce_effects((previous_write.effect, effect))[0]
            self.writes[effect.destination] = AssetWrite(effect, write.content)

    def finish(self, families: tuple[OwnerAssessment, ...]) -> OwnerAssessment:
        anchor = Path(os.path.commonpath(tuple(self.anchors))) if self.anchors else Path.home().parent
        root = OperationRoot("global_assets", "global", anchor)
        diagnostics = tuple(d for family in families for d in family.diagnostics)
        dispositions = tuple(d for family in families for d in family.dispositions)
        if not families or not all(family.complete for family in families):
            return OwnerAssessment(
                "global_assets",
                root,
                complete=False,
                diagnostics=diagnostics or (Diagnostic("empty_global_selection", "global_assets", "error", "Select at least one global family"),),
                dispositions=dispositions,
            )
        locks = tuple(sorted(self.locks))
        writes = tuple(sorted(self.writes.values(), key=_write_order))
        observations = tuple(sorted(self.observations.values(), key=lambda item: str(item.path)))
        prepared = PreparedAssets(writes, observations, self.environment, locks[0], anchor, tuple(sorted(self.temporary_paths)), locks[1:])
        return OwnerAssessment(
            "global_assets",
            root,
            tuple(w.effect for w in writes),
            dispositions,
            diagnostics=diagnostics,
            inputs_fingerprint=(InputObservation("assets", observations),),
            prepared=prepared,
            consent=self.consent,
        )


def assess_global_assets(
    *,
    runtime: bool = True,
    commands: bool = True,
    skills: bool = True,
    agent_keys: list[str] | None = None,
    skill_selection: GlobalSkillSelection | None = None,
    consent: ApplyConsent = ApplyConsent(),
) -> OwnerAssessment:
    """Prepare selected global families once, with one executable owner.

    Dispatch only this assessment (owner_key ``global_assets``), using
    recheck_assets/apply_assets. Do not also dispatch separate family batches.
    ``agent_keys`` narrows commands only. ``skill_selection`` supplies immutable
    caller-resolved skills/agents; None retains package/all-agent skill policy.
    No existing preparation is accepted, combined opaquely or reassessed on apply.
    """
    from specify_cli.runtime import bootstrap, agent_commands, agent_skills

    if skill_selection is not None and not skills:
        raise ValueError("skill_selection requires skills=True")
    batch = _GlobalAssetPreparation(consent)
    families = []
    if runtime:
        families.append(bootstrap.assess_runtime(consent=consent, _batch=batch))
    if commands:
        families.append(agent_commands.assess_global_agent_commands(agent_keys=agent_keys, consent=consent, _batch=batch))
    if skills:
        families.append(agent_skills.assess_global_agent_skills(consent=consent, selection=skill_selection, _batch=batch))
    return batch.finish(tuple(families))


#: ``OwnershipProof.reference`` suffixes ``finish()`` mints for its own
#: certification bookkeeping (inventory manifest, version stamp, the
#: persistent owner lock) -- never a real asset's relative path. Used only
#: to gate bookkeeping toleration below; a real asset coincidentally
#: relative-pathed exactly like one of these is not a live concern (none
#: of the managed catalogs use these names).
_BOOKKEEPING_PROOF_SUFFIXES = frozenset({"inventory", "version-stamp", "persistent-lock"})


def _content_equal(current: FileState, desired: FileState) -> bool:
    """Same canonical payload, ignoring mode/mtime (never part of "bytes")."""
    return bool(current.kind == desired.kind and current.sha256 == desired.sha256)


def _is_bookkeeping_write(write: AssetWrite) -> bool:
    """Is this owner's own completion marker, not a genuine asset payload?

    A version stamp, lock file, or inventory manifest CERTIFIES that a
    batch finished -- it must never certify on its own. A concurrent peer
    that planted only a matching stamp, without the real payload files
    that stamp is supposed to certify, is exactly the unproven partial
    state this module must still refuse (the batch's own ``finish()``
    writes these last, deliberately, as a completion marker).
    """
    return any(proof.kind == "managed_path" and proof.reference.rsplit(":", 1)[-1] in _BOOKKEEPING_PROOF_SUFFIXES for proof in write.effect.ownership)


def _membership_drift_tolerated(
    observation: AssetObservation,
    actual_children: tuple[str, ...],
    writes_by_path: dict[Path, AssetWrite],
    content_paths: tuple[Path, ...],
) -> bool:
    """Tolerate ONLY a concurrent peer materializing this batch's OWN planned
    additions to a ``destination_probe`` directory's membership -- mirroring
    the content check's own peer-tolerance above. A ``source_read`` node, an
    expected child now missing, or an extra name this batch is not itself
    about to write (or writes different bytes for), still refuses; every
    genuine content file in the batch must ALSO already match canonical
    bytes, exactly as the content check requires before trusting a
    bookkeeping stamp (FR-002/C-002).
    """
    if observation.role != "destination_probe" or observation.children is None:
        return False
    recorded = set(observation.children)
    extra = set(actual_children) - recorded
    missing = recorded - set(actual_children)
    if missing or not extra:
        return False
    for name in extra:
        child = observation.path / name
        write = writes_by_path.get(child)
        if write is None:
            return False
        try:
            # FR-011 defensive guard: a recorded self-held lock never reaches
            # this branch (lock paths are excluded from check_assets's read
            # loop before membership is ever inspected), but an "extra"
            # child's bytes are still read here on the strength of that
            # assumption alone. Treat a read failure (a vanished/oversized/
            # permission-denied node -- e.g. a would-be #4703 self-held-lock
            # read that reaches here despite the assumption) as untolerated
            # rather than letting it propagate uncaught.
            state = node_state(child)
        except OSError:
            return False
        if not _content_equal(state, write.effect.after):
            return False
    try:
        return all(_content_equal(node_state(p), writes_by_path[p].effect.after) for p in content_paths)
    except OSError:
        return False


def _cold_install_sentinel_ancestor_paths(prepared: PreparedAssets) -> frozenset[Path]:
    """Ancestor paths whose absent-to-directory transition is legitimately
    THIS SAME recheck's own cold-install sentinel acquisition (#4756 WP02),
    never unrelated drift -- mirrors the ``lock_paths`` skip in
    :func:`check_assets` (#4703) for the identical reason: a side effect
    this exact call is responsible for is not "someone else changed my
    assets". The sentinel now resolves as a sibling of the per-user runtime
    state root (see :func:`_cold_install_sentinel`'s docstring), which can
    require creating that root's own parent directory (e.g. the user's
    home) when it does not yet exist -- a genuinely cold machine, not a
    concurrent peer or an attacker. Naturally bounded: an ancestor that
    already existed (the common case on a warm machine, and every
    filesystem-root-level ancestor) never shows an absent-to-directory
    transition in the first place, so including it here is harmless.
    """
    sentinel = _cold_install_sentinel(prepared.anchor)
    return frozenset({sentinel, *sentinel.parents})


def _is_cold_install_sentinel_materialization(
    observation: AssetObservation,
    current: AssetObservation,
    sentinel_ancestors: frozenset[Path],
) -> bool:
    """True when *observation*'s only "drift" is this recheck's own
    cold-install sentinel springing its ancestor chain from absent to an
    ordinary, otherwise-untouched directory."""
    return observation.path in sentinel_ancestors and observation.state.kind == "absent" and current.state.kind == "directory"


def check_assets(assessment: OwnerAssessment) -> tuple[Diagnostic, ...]:
    """Compare the entire batch before opening any write-capable handle.

    A ``destination_probe`` node (this owner's own managed output under
    home) whose observed state drifted is tolerated ONLY when the node's
    CURRENT on-disk content is byte-identical to the canonical content this
    same batch is about to (re)write there -- a benign concurrent peer
    materialized the exact same owned bytes, never asset-input drift
    (FR-002/C-002). A bookkeeping stamp (inventory/version-stamp/persistent-
    lock) additionally requires every genuine content-file write in the
    SAME batch to already be present with matching canonical bytes: a lone
    matching stamp with the rest of the tree still unproven is exactly the
    partial-completion case this must keep catching (the stamp is what
    CERTIFIES the batch, so it can never certify itself in isolation). Any
    other drift on a ``destination_probe`` node -- different bytes, a node
    this batch is not itself about to write, or a ``source_read`` node
    (package/template source) -- still refuses. Role-tagging is by call
    site, never path geography (FR-003).

    A ``destination_probe`` directory's MEMBERSHIP gets the same peer
    toleration (#4174 landing-pass rescope): a concurrent peer that added
    (or retired) exactly this batch's own planned names, with canonical
    bytes, is a benign commands/skills upgrade race, not asset-input drift
    -- see ``_membership_drift_tolerated``.
    """
    prepared = assessment.prepared
    if not isinstance(prepared, PreparedAssets):
        return (Diagnostic("invalid_preparation", assessment.owner_key, "error", "Expected retained global asset data"),)
    try:
        for name, value in prepared.environment:
            if os.environ.get(name) != value:
                raise ValueError(f"Global asset environment changed: {name}")
        writes_by_path = {write.effect.destination: write for write in prepared.writes}
        content_paths = tuple(path for path, write in writes_by_path.items() if write.effect.after.kind == "file" and not _is_bookkeeping_write(write))
        content_confirmed: bool | None = None  # computed lazily; a batch with no writes never needs it
        lock_paths = set(prepared.lock_paths)
        sentinel_ancestors = _cold_install_sentinel_ancestor_paths(prepared)
        # Ancestors precede child file reads, including parents outside the root.
        for observation in sorted(prepared.observations, key=lambda item: len(item.path.parts)):
            if observation.path in lock_paths:
                # #4703: never read an owner lock file's own bytes during recheck.
                # recheck_assets may hold this exact file under an exclusive lock,
                # and on Windows msvcrt.locking() is MANDATORY -- the process's own
                # read of its own held lock raises PermissionError errno 13 (POSIX
                # flock is advisory, which is why CI never caught it). The lock is a
                # self-managed empty artifact excluded from the content-proof set
                # (persistent-lock is a bookkeeping suffix), and its existence is
                # separately guaranteed by recheck_assets's open()+lock (which
                # fails first if the lock vanished) plus the lock's kind check at
                # finish()-observe time, so verifying its bytes protects nothing.
                continue
            try:
                current = _observation(observation.path, node_state(observation.path))
            except OSError as exc:
                # #4703: name the unreadable asset. A bare str(exc) on a Windows
                # PermissionError drops exc.filename (it is None), leaving only
                # "[Errno 13] Permission denied" -- undiagnosable as shipped.
                raise ValueError(f"Could not read global asset {observation.path}: {exc}") from exc
            drifted = (current.state, current.identity) != (observation.state, observation.identity)
            if drifted and not _is_cold_install_sentinel_materialization(observation, current, sentinel_ancestors):
                write = writes_by_path.get(observation.path) if observation.role == "destination_probe" else None
                tolerated = write is not None and _content_equal(current.state, write.effect.after)
                if tolerated and write is not None and (write.effect.after.kind != "file" or _is_bookkeeping_write(write)):
                    # A matching directory or a matching bookkeeping stamp proves
                    # nothing on its own -- only a matching genuine content FILE
                    # proves a peer actually materialized this batch's payload.
                    if content_confirmed is None:
                        content_confirmed = all(_content_equal(node_state(p), writes_by_path[p].effect.after) for p in content_paths)
                    tolerated = content_confirmed
                if not tolerated:
                    raise ValueError(f"Global asset input changed: {observation.path}")
            if observation.children is not None:
                actual_children = tuple(sorted(p.name for p in observation.path.iterdir()))
                if actual_children != observation.children and not _membership_drift_tolerated(observation, actual_children, writes_by_path, content_paths):
                    raise ValueError(f"Global asset inventory changed: {observation.path}")
    except (OSError, ValueError) as exc:
        return (Diagnostic("precondition_changed", assessment.owner_key, "error", str(exc)),)
    return ()


def _cold_install_sentinel(anchor: Path) -> Path:
    """A per-user lock file that serializes concurrent COLD installers of the
    same *anchor*.

    Directories cannot be locked through the canonical primitive (it opens,
    OS-locks and truncates a dedicated REGULAR-file path -- kernel.locks
    G1), so a cold install of any anchor -- POSIX or Windows alike --
    serializes on this dedicated sentinel file instead of flocking the
    anchor directory itself (the pre-WP04 POSIX shape). This sentinel is
    deliberately kept OUT of the managed asset tree (a sibling of the
    per-user runtime state root, keyed by the anchor path) so it never
    enters asset verification, while still contending across processes
    installing the same anchor. (#4703 cross-OS family)

    #4756 WP02: the sentinel used to live under the WORLD-SHARED
    ``tempfile.gettempdir()`` -- a machine-global location any other local
    user can read/traverse, keyed by a filename fully predictable from the
    (machine-global) *anchor*. It now resolves as a SIBLING of
    :func:`kernel.paths.get_runtime_state_root` (``~/.spec-kitty-cold-
    install``, next to ``~/.spec-kitty``) instead of a child of it, which
    another local user cannot write into either way -- closing that
    pre-plant window -- but, critically, keeps this sentinel's own ancestor
    chain structurally DISJOINT from ``kernel.paths.get_kittify_home()``'s.
    ``AssetPreparation.observe`` records EVERY ancestor of every observed
    destination (including the bare runtime-state-home directory itself,
    not just its managed subdirectories) so a later drift recheck can catch
    a parent swapped out from under it; a sentinel nested INSIDE that same
    home root would make its own out-of-band ``mkdir(parents=True)``
    (``kernel.locks``' ``_ensure_dir``) silently materialize the
    previously-absent home directory between the plan snapshot and the
    locked recheck, which a genuinely cold install (home not yet created)
    then reports as unexplained drift ("Global asset input changed") --
    self-inflicted, not a real concurrent-peer race. A sibling path shares
    ``get_runtime_state_root()``'s parent (already guaranteed to exist --
    the real ``$HOME``, or the caller-supplied ``SPEC_KITTY_HOME``'s own
    parent) without ever nesting under the home root itself, so it cannot
    trip that check. This function is PURE (no I/O): directory creation and
    mode hardening are the sole responsibility of the caller's
    ``kernel.locks.machine_file_lock`` acquisition below, whose
    ``_ensure_dir`` hardens a freshly-created parent to ``0o700`` -- a bare
    ``mkdir(exist_ok=True)`` here would pre-create that parent and make
    ``_ensure_dir`` see it as already existing, permanently skipping the
    chmod (the exact bug this WP fixes).

    FR-011: the anchor is normalized (case-folded, canonicalized) BEFORE
    keying so two equivalent spellings of the same anchor path (differing
    only by case on a case-insensitive filesystem, or by resolution of
    ``.``/``..``/a trailing separator) key the SAME sentinel rather than
    silently splitting into two unrelated locks.
    """
    normalized = os.path.normcase(str(Path(anchor).resolve()))
    key = hashlib.sha256(normalized.encode()).hexdigest()[:16]  # noqa: TID251 -- path keying, not charter hashing
    runtime_root = get_runtime_state_root()
    sentinel_dir = runtime_root.parent / f"{runtime_root.name}-cold-install"
    return sentinel_dir / f"{key}.lock"


@contextmanager
def _serialize_owner(lock_paths: tuple[Path, ...], anchor: Path) -> Iterator[None]:
    """Acquire one owner's serialization point: the single authority shared by
    ``recheck_assets`` and ``build_serialized`` (FR-002/C-008).

    Takes the cold-install sentinel when any of *lock_paths* is absent, plus
    every existing lock path, then records the set in ``_HELD_LOCKS`` for the
    duration of the ``with`` block. Any other lock choice would be a second,
    parallel authority that could drift from what the locked recheck takes --
    see ``research.md`` D-2.

    WP04: both the cold-install serialization and the per-owner-lock
    acquisition below route through ``kernel.locks.machine_file_lock`` (the
    canonical primitive, G1-G7) rather than a raw ``msvcrt``/``fcntl`` call.
    Neither this process's OS-lock acquisition NOR the cold-install
    serialization branches on platform any more (the primitive absorbs that
    internally) -- see ``_cold_install_sentinel``'s docstring for why the
    former POSIX-directory-flock shape is retired in favour of one uniform
    dedicated sentinel file for every platform.
    """
    with ExitStack() as stack:
        cold = any(not path.exists() for path in lock_paths)
        if cold:
            # A cold install has no owner lock file to acquire yet (apply's
            # own exclusive create is the final arbiter); serialize cold
            # installers of the SAME anchor on a dedicated machine-temp
            # sentinel instead -- never the anchor directory itself, which
            # the canonical primitive cannot lock (G1: a dedicated regular
            # lock-only path).
            stack.enter_context(machine_file_lock(_cold_install_sentinel(anchor), blocking=True))
        for path in lock_paths:
            if path.exists():
                stack.enter_context(machine_file_lock(path, blocking=True))
        token = _HELD_LOCKS.set(_HELD_LOCKS.get() | set(lock_paths))
        try:
            yield
        finally:
            _HELD_LOCKS.reset(token)


@contextmanager
def recheck_assets(assessment: OwnerAssessment) -> Iterator[tuple[Diagnostic, ...]]:
    """Hold an existing owner lock without truncation throughout recheck/apply.

    Cold lock creation is itself an assessed effect in apply. Recheck always
    runs before that creation; exclusive creation detects a racing cold owner.

    #4174 landing-pass rescope: the FIRST ``check_assets`` call above is
    UNLOCKED and can sample a concurrent peer mid-write -- ``_write_order``
    guarantees every directory this batch will create is written before ANY
    content file, so a loser can observe a peer's directories without any of
    its content yet. A directory-kind observation is tolerant of drift only
    when EVERY genuine content file in the batch already matches canonical
    bytes on disk (``check_assets``'s ``content_confirmed`` computation),
    which is false mid-write -- so this unlocked sample can raise even
    though nothing is actually wrong, only unfinished. When the assessment
    has effects and a retained ``PreparedAssets`` payload, this unlocked
    diagnostic is therefore NEVER authoritative on its own: proceed to
    acquire the lock regardless of what it found, and let the UNDER-LOCK
    recheck below (or, when re-entrant, the ``_HELD_LOCKS`` short-circuit,
    whose own diagnostics were computed while this process already held the
    lock and so cannot be observing a live concurrent write) decide. By the
    time the lock is actually granted, a genuine concurrent peer holding it
    while writing will have finished and the home will be fully materialized
    -- a true SOURCE-read drift (never tolerated, FR-003/C-002) still refuses
    once the under-lock recheck runs.

    The actual lock set is acquired through ``_serialize_owner`` -- the single
    serialization authority also used by ``build_serialized``'s escalation
    (FR-002/C-008), so an owner's locked recheck and its torn-read escalation
    can never choose a different lock set for the same assessment.
    """
    diagnostics = check_assets(assessment)
    prepared = assessment.prepared
    if not assessment.effects or not isinstance(prepared, PreparedAssets):
        yield diagnostics
        return
    if set(prepared.lock_paths) <= _HELD_LOCKS.get():
        yield diagnostics
        return
    with _serialize_owner(prepared.lock_paths, prepared.anchor):
        yield check_assets(assessment)


def apply_with_reassess(
    assessment: OwnerAssessment,
    rebuild: Callable[[], OwnerAssessment],
    consent: ApplyConsent,
    *,
    converged_log_message: str,
    logger: logging.Logger | None = None,
) -> OwnerApplyResult:
    """Hold *assessment*'s lock, re-assess under it, and converge or apply.

    Generalizes ``bootstrap.ensure_runtime()``'s original #4017 WP03
    re-assess-under-lock mechanism (see its docstring for the full
    mechanism) into ONE shared implementation every owner adopts, rather
    than triplicating the block. Once ``recheck_assets`` grants the lock, a
    genuine concurrent peer that was racing this same batch has finished --
    but the *assessment* passed in may still carry a STALE plan computed
    before that peer ran, whose actions (``mkdir``, ``open("x")``) are
    non-idempotent against the peer's now-materialized tree. Re-assessing
    via *rebuild* under the held lock, rather than applying the stale plan
    directly, converges to a no-op when the peer already did the work.

    Callers must already have confirmed ``assessment.complete`` and
    ``assessment.effects`` before calling this (matching the existing
    early-return shape every adopter already has); this helper only owns
    the ``recheck_assets`` boundary onward.

    ``rebuild`` MUST recompute a fresh, complete assessment against current
    state (an owner's own ``assess_*`` entry point) -- never replay or
    mutate the *assessment* argument.

    *logger* is the OPERATOR_SIGNAL_CONTRACT sink for the converged-no-op
    message: pass the calling module's own logger (each existing ``ensure_*``
    adopter already has one, and existing tests scope their ``caplog``
    capture to it by name) so the message is emitted at that logger's own
    configured level -- this module's logger defaults only when the caller
    genuinely has none of its own.
    """
    log = logger if logger is not None else logging.getLogger(__name__)
    with recheck_assets(assessment) as diagnostics:
        if diagnostics:
            return OwnerApplyResult(
                assessment.owner_key,
                skipped=tuple(effect.id for effect in assessment.effects),
                outcome="precondition_changed",
                diagnostics=diagnostics,
            )
        reassessment = rebuild()
        if not reassessment.complete:
            return OwnerApplyResult(
                reassessment.owner_key,
                skipped=tuple(effect.id for effect in reassessment.effects),
                outcome="failed",
                diagnostics=reassessment.diagnostics,
            )
        if not reassessment.effects:
            # OPERATOR_SIGNAL_CONTRACT: the machine half (a skipped/no-raise
            # outcome) is silent by construction -- this log sink carries the
            # human half so a converged-no-op race is never invisible.
            log.info(converged_log_message)
            return OwnerApplyResult(reassessment.owner_key, outcome="skipped")
        return apply_assets(reassessment, consent)


def _write_asset(write: AssetWrite) -> None:
    effect, content = write.effect, write.content
    path = effect.destination
    if effect.action == "delete":
        if effect.before.kind == "directory":
            safe_rmdir(path)
        else:
            safe_unlink(path)
    elif effect.action == "chmod":
        path.chmod(effect.after.mode or 0o444)
    elif effect.after.kind == "directory":
        try:
            path.mkdir(mode=effect.after.mode or 0o755)
        except FileExistsError:
            # #4756 WP02: a cold install's own sentinel lock (a sibling of
            # the per-user runtime state root) can materialize an ancestor
            # directory -- e.g. the home root itself -- as a side effect of
            # its own kernel.locks acquisition, moments before this SAME
            # plan's "create" action for that identical path runs (a
            # caller that applies directly, without the #4017 re-assess-
            # under-lock seam, never gets a second look at that fact).
            # check_assets's own precondition gate already ran immediately
            # before this write; tolerate ONLY an already-materialized
            # ordinary directory here (never a symlink standing in for
            # one) rather than raising on this specific, benign race.
            if path.is_symlink() or not path.is_dir():
                raise
        path.chmod(effect.after.mode or 0o755)
    elif effect.after.kind == "symlink":
        if effect.after.target is None:
            raise ValueError("Missing retained link target")
        path.symlink_to(effect.after.target)
    else:
        if content is None:
            raise ValueError("Missing prepared file bytes")
        if effect.before.kind == "symlink":
            safe_unlink(path)
        write_generated_file(path, content, read_only=False)
        path.chmod(effect.after.mode or 0o444)


def apply_assets(assessment: OwnerAssessment, consent: ApplyConsent) -> OwnerApplyResult:
    """Write retained bytes, report actual IDs, and never certify a failed batch."""
    ids = tuple(effect.id for effect in assessment.effects)
    if not assessment.complete or consent.overwrite_paths != assessment.consent.overwrite_paths:
        return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="failed", diagnostics=assessment.diagnostics)
    if not consent.automatic or not ids:
        return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="skipped")
    with recheck_assets(assessment) as diagnostics:
        if diagnostics:
            return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="precondition_changed", diagnostics=diagnostics)
        if assessment.owner_key == "runtime_bootstrap":
            from specify_cli.runtime.bootstrap import populate_from_package

            prepared = assessment.prepared
            if not isinstance(prepared, PreparedAssets):
                raise TypeError("Expected retained package assets")
            result = populate_from_package(prepared.lock_path.parent.parent, assessment=assessment, consent=consent)
            if result is None:
                raise TypeError("Runtime package writer omitted its apply result")
            return result
        return _apply_retained_assets(assessment)


def _write_order(write: AssetWrite) -> tuple[int, int, str]:
    effect = write.effect
    name = effect.destination.name
    stage = 3
    if effect.after.kind == "directory" and effect.action == "create":
        stage = 0
    elif name.startswith(".") and name.endswith(".lock"):
        stage = 1
    elif "/backups/state-" in effect.path:
        stage = 2
    elif name.endswith("-assets.json"):
        stage = 5
    elif name.endswith(".lock"):
        stage = 6
    elif effect.action == "delete":
        stage = 4
    depth = -len(effect.destination.parts) if effect.action == "delete" else len(effect.destination.parts)
    return stage, depth, effect.path


def _apply_retained_assets(assessment: OwnerAssessment) -> OwnerApplyResult:
    prepared = assessment.prepared
    if not isinstance(prepared, PreparedAssets):
        raise TypeError("Expected prepared global assets")
    # Parent creates first; inventory and version stamps last. A failed content
    # write must never stamp or certify the unattempted remainder.
    ordered = sorted(prepared.writes, key=_write_order)
    succeeded: list[str] = []
    with ExitStack() as locks:
        for index, write in enumerate(ordered):
            try:
                if write.effect.destination in prepared.lock_paths and write.effect.action == "create":
                    # First materialization of the persistent owner lock.
                    # Concurrent creation is already serialized by the cold-
                    # install sentinel/owner-lock this call runs under (see
                    # recheck_assets), so the canonical primitive's own
                    # open+lock+truncate (kernel.locks G1/G3) is sufficient
                    # here without needing an exclusive-create mode.
                    #
                    # A1 (#4714 WP04 review): a genuinely cold "create" write
                    # means the destination did NOT exist when this plan was
                    # built -- if it still does not exist now, this call must
                    # do the real lock+create. But if a racing peer
                    # materialized it between this stale plan's build and
                    # this apply, ``recheck_assets`` already found it existing
                    # and OS-locked it for real (its own per-path ``if
                    # path.exists(): machine_file_lock(path, ...)`` loop) --
                    # re-locking the SAME non-reentrant lock here would block
                    # forever against ourselves. Existence at this point is
                    # exactly that signal: nothing removes a lock file
                    # between recheck and this apply, so "exists now" implies
                    # "existed (and was locked) at recheck time."
                    # R-1 (plan.md): the documented cold-create exception --
                    # this lock is CREATED here, so it cannot be routed
                    # through _serialize_owner (which only locks paths that
                    # already exist); double-locking it there would self-
                    # deadlock on this same non-reentrant primitive.
                    if not write.effect.destination.exists():
                        locks.enter_context(machine_file_lock(write.effect.destination, blocking=True))
                    write.effect.destination.chmod(write.effect.after.mode or 0o644)
                else:
                    _write_asset(write)
            except (OSError, ValueError, UnicodeError) as exc:
                return OwnerApplyResult(
                    assessment.owner_key,
                    tuple(succeeded),
                    (write.effect.id,),
                    tuple(w.effect.id for w in ordered[index + 1 :]),
                    (Diagnostic("global_asset_write_failed", assessment.owner_key, "error", str(exc)),),
                    "partial" if succeeded else "failed",
                )
            succeeded.append(write.effect.id)
    return OwnerApplyResult(assessment.owner_key, tuple(succeeded))
