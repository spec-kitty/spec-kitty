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
            raise ValueError(f"Asset changed during preparation: {path}")
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


def incomplete(owner: str, root: OperationRoot, error: Exception) -> OwnerAssessment:
    """A source/config failure never becomes a complete empty assessment."""
    return OwnerAssessment(owner, root, complete=False, diagnostics=(Diagnostic("global_assets_unavailable", owner, "error", str(error)),))


_RetriedBuild = TypeVar("_RetriedBuild")

#: #4017 rescope, sequential after WP02's own lock-path work in this file: a
#: SECOND, distinct race from the post-lock recheck WP03 already fixed in
#: bootstrap.py. This one is unlocked-phase and generic to every owner.
_TORN_READ_RETRY_ATTEMPTS = 3
_TORN_READ_MESSAGE_PREFIX = "Asset changed during preparation:"


def retry_torn_read(build: Callable[[], _RetriedBuild]) -> _RetriedBuild:
    """Re-run one owner's WHOLE unlocked assess pass on a benign observe-phase torn read.

    ``observe()`` raises "Asset changed during preparation" when the SAME
    path is observed twice with different states within one assess pass --
    e.g. an owner's own inventory JSON, read once at
    ``AssetPreparation.__init__`` and again at ``finish()``'s effect
    computation, materialized by a concurrent peer sharing this same
    spec-kitty-home in between. That is a torn read of the peer's in-flight
    write, not asset-input drift (FR-002/C-002 already cover genuine drift);
    the peer converges to canonical bytes quickly, so re-running the whole
    pass from scratch resolves it.

    ``build`` MUST construct a fresh ``AssetPreparation`` (and do everything
    through ``finish()``) on every call, so a retry starts from a clean,
    re-read ``self.observed`` rather than the stale snapshot that raised --
    and it MUST stop short of any shared, non-retriable side effect (such as
    ``_GlobalAssetPreparation.include()``), which callers perform exactly
    once on the stabilized result. This is generic across every global
    owner (bootstrap/commands/skills); none is special-cased.

    Only ``ValueError`` messages starting with the torn-read prefix are
    retried, and only up to a small, fixed bound -- any other exception, or
    a torn read that still has not stabilized on the final attempt,
    propagates immediately so a genuine failure is never masked.
    """
    for _ in range(_TORN_READ_RETRY_ATTEMPTS - 1):
        try:
            return build()
        except ValueError as exc:
            if not str(exc).startswith(_TORN_READ_MESSAGE_PREFIX):
                raise
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
        write = writes_by_path.get(observation.path / name)
        if write is None or not _content_equal(node_state(observation.path / name), write.effect.after):
            return False
    return all(_content_equal(node_state(p), writes_by_path[p].effect.after) for p in content_paths)


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
            if (current.state, current.identity) != (observation.state, observation.identity):
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
    time the anchor flock is actually granted, a genuine concurrent peer
    holding it while writing will have finished and the home will be fully
    materialized -- a true SOURCE-read drift (never tolerated, FR-003/C-002)
    still refuses once the under-lock recheck runs.
    """
    from specify_cli.runtime.bootstrap import _lock_exclusive

    diagnostics = check_assets(assessment)
    prepared = assessment.prepared
    if not assessment.effects or not isinstance(prepared, PreparedAssets):
        yield diagnostics
        return
    if set(prepared.lock_paths) <= _HELD_LOCKS.get():
        yield diagnostics
        return
    with ExitStack() as stack:
        if any(not path.exists() for path in prepared.lock_paths) and os.name != "nt":
            # POSIX directories support flock without creating a lock artifact.
            # Serialize cold installers on the stable reporting anchor until
            # apply creates and acquires the existing owner-specific lock.
            descriptor = os.open(prepared.anchor, os.O_RDONLY)
            stack.callback(os.close, descriptor)
            _lock_exclusive(descriptor)
        for path in prepared.lock_paths:
            if path.exists():
                stream = stack.enter_context(path.open("r"))
                _lock_exclusive(stream)
        token = _HELD_LOCKS.set(_HELD_LOCKS.get() | set(prepared.lock_paths))
        try:
            yield check_assets(assessment)
        finally:
            _HELD_LOCKS.reset(token)


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
            path.rmdir()
        else:
            path.unlink()
    elif effect.action == "chmod":
        path.chmod(effect.after.mode or 0o444)
    elif effect.after.kind == "directory":
        path.mkdir(mode=effect.after.mode or 0o755)
        path.chmod(effect.after.mode or 0o755)
    elif effect.after.kind == "symlink":
        if effect.after.target is None:
            raise ValueError("Missing retained link target")
        path.symlink_to(effect.after.target)
    else:
        if content is None:
            raise ValueError("Missing prepared file bytes")
        if effect.before.kind == "symlink":
            path.unlink()
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
    from specify_cli.runtime.bootstrap import _lock_exclusive

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
                    stream = locks.enter_context(write.effect.destination.open("x"))
                    write.effect.destination.chmod(write.effect.after.mode or 0o644)
                    _lock_exclusive(stream)
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
