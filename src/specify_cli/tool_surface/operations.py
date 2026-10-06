"""Immutable in-process owner assessments; no discovery, I/O or replay format.

Root paths are supplied by existing owner resolvers. Lexical destination identity
never follows a link. Owners retain confinement observations and recheck them
under their lock before applying their opaque prepared bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from hashlib import sha256  # noqa: TID251 - stdlib-only physical effect identity, not charter content hashing.
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re


PHASES = ("global_bootstrap", "migrations", "metadata", "provisioning", "manifest_repair", "surface_repair")


def _immutable(value: object) -> None:
    """Reject live containers/callbacks, including inside frozen owner payloads."""
    if value is None or isinstance(value, (str, bytes, bool, int, float, Path)):
        return
    if isinstance(value, (tuple, frozenset)):
        for item in value:
            _immutable(item)
        return
    params = getattr(value, "__dataclass_params__", None)
    if not isinstance(value, type) and is_dataclass(value) and params is not None and params.frozen:
        for item_field in fields(value):
            _immutable(getattr(value, item_field.name))
        return
    raise TypeError("Owner data must be deeply immutable; use tuples, bytes or frozen values")


def _relative_path(path: str) -> None:
    if (
        not path
        or "\\" in path
        or "\x00" in path
        or ":" in path
        or PurePosixPath(path).is_absolute()
        or PureWindowsPath(path).drive
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError(f"Expected normalized confined relative path: {path!r}")


def _one_of(value: str, choices: tuple[str, ...], name: str) -> None:
    if value not in choices:
        raise ValueError(f"Invalid {name}: {value!r}")


@dataclass(frozen=True)
class OperationRoot:
    """Already resolved root identity; construction performs no filesystem reads."""

    root_id: str
    scope: str
    path: Path

    def __post_init__(self) -> None:
        _one_of(self.scope, ("global", "project", "worktree"), "scope")
        if not self.root_id or not self.path.is_absolute() or ".." in self.path.parts:
            raise ValueError("Root requires an identity and an absolute normalized path")


@dataclass(frozen=True)
class FileState:
    """Exact node observation. Literal link targets and mtime never prove ownership."""

    kind: str
    sha256: str | None = None
    target: str | None = None
    mode: int | None = None
    mtime_ns: int | None = None

    def __post_init__(self) -> None:
        _immutable(self)
        _one_of(self.kind, ("absent", "file", "directory", "symlink"), "node kind")
        if self.kind == "absent":
            valid = self.sha256 is None and self.target is None and self.mode is None and self.mtime_ns is None
        else:
            valid = type(self.mode) is int and 0 <= self.mode <= 0o7777
            valid = valid and (self.mtime_ns is None or type(self.mtime_ns) is int)
            valid = valid and (self.target is not None if self.kind == "symlink" else self.target is None)
            valid = valid and (bool(re.fullmatch("[a-f0-9]{64}", self.sha256 or "")) if self.kind == "file" else self.sha256 is None)
        if not valid:
            raise ValueError(f"Invalid state for {self.kind}")


@dataclass(frozen=True)
class OwnershipProof:
    """Exact manifest entry or owner contract reference, separate from disk hashes."""

    kind: str
    reference: str

    def __post_init__(self) -> None:
        _immutable(self)
        _one_of(self.kind, ("manifest", "managed_path", "canonical_content"), "ownership proof")
        if not self.reference:
            raise ValueError("Ownership requires an exact reference")


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
class PhysicalEffect:
    """One net persistent change, retaining every logical owner and ownership proof."""

    owner: str
    phase: str
    root: OperationRoot
    path: str
    action: str
    before: FileState
    after: FileState
    reason: str
    ownership: tuple[OwnershipProof, ...]
    logical_owners: tuple[str, ...]
    surface_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _relative_path(self.path)
        _one_of(self.phase, PHASES, "phase")
        if self.action != _action(self.before, self.after):
            raise ValueError("Effect action does not match its before/after states")
        if not self.owner or not self.reason or not self.ownership or not self.logical_owners:
            raise ValueError("Effect requires owner, reason, exact ownership and logical owners")
        _immutable(self)
        object.__setattr__(self, "logical_owners", tuple(sorted(set(self.logical_owners))))
        object.__setattr__(self, "surface_ids", tuple(sorted(set(self.surface_ids))))
        object.__setattr__(self, "ownership", tuple(sorted(set(self.ownership), key=lambda p: (p.kind, p.reference))))

    @property
    def id(self) -> str:
        """Stable logical effect ID, independent of new clocks and fixture paths."""
        identity = (self.phase, self.owner, self.root.root_id, self.path, self.action)
        return sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()

    @property
    def destination(self) -> Path:
        """Lexical physical destination; do not resolve an untrusted child link."""
        return self.root.path.joinpath(*self.path.split("/"))

    @property
    def sort_key(self) -> tuple[int, str, str, str]:
        """Contract phase order, then executable owner, root and relative path."""
        return PHASES.index(self.phase), self.owner, self.root.root_id, self.path


_CONFLICT_FIELDS = ("owner", "phase", "action", "before", "after")


def _differing_fields(previous: PhysicalEffect, effect: PhysicalEffect) -> tuple[str, ...]:
    """Names of the identity fields on which two effects at one destination disagree."""
    return tuple(name for name in _CONFLICT_FIELDS if getattr(previous, name) != getattr(effect, name))


def _is_shared_directory_create(previous: PhysicalEffect, effect: PhysicalEffect) -> bool:
    """True when two owners plan the identical ``create absent -> directory`` effect.

    Only the owner may differ; the merged effect keeps both owners' claims.
    """
    return (
        previous.action == effect.action == "create"
        and previous.phase == effect.phase
        and previous.before == effect.before
        and previous.before.kind == "absent"
        and previous.after == effect.after
        and previous.after.kind == "directory"
    )


def coalesce_effects(effects: tuple[PhysicalEffect, ...]) -> tuple[PhysicalEffect, ...]:
    """Deduplicate equivalent intent; never synthesize a writer across owners."""
    destinations: dict[Path, PhysicalEffect] = {}
    roots: dict[str, Path] = {}
    for effect in sorted(effects, key=lambda e: e.sort_key):
        root_path = roots.setdefault(effect.root.root_id, effect.root.path)
        if root_path != effect.root.path:
            raise ValueError("Root identity conflict: one root ID names distinct resolved paths")
        previous = destinations.get(effect.destination)
        if previous is None:
            destinations[effect.destination] = effect
            continue
        differing = _differing_fields(previous, effect)
        if differing and not _is_shared_directory_create(previous, effect):
            raise ValueError(f"Owner effect conflict at {effect.destination}: {previous.owner} vs {effect.owner} (differs in: {', '.join(differing)})")
        destinations[effect.destination] = replace(
            previous,
            logical_owners=previous.logical_owners + effect.logical_owners,
            surface_ids=previous.surface_ids + effect.surface_ids,
            ownership=previous.ownership + effect.ownership,
            reason=min(previous.reason, effect.reason),
        )
    return tuple(sorted(destinations.values(), key=lambda e: e.sort_key))


@dataclass(frozen=True)
class Disposition:
    """An unchanged, preserved, consent-requiring or inapplicable non-write."""

    owner: str
    root_id: str | None
    path: str | None
    state: str
    reason: str

    def __post_init__(self) -> None:
        _immutable(self)
        if not self.owner or not self.reason:
            raise ValueError("Disposition requires an owner and reason")
        _one_of(self.state, ("unchanged", "preserve", "consent_required", "not_applicable"), "disposition")
        if self.path is not None:
            _relative_path(self.path)


@dataclass(frozen=True)
class Diagnostic:
    """Explicit completeness/conflict information; never an empty-success fallback."""

    code: str
    owner: str | None
    severity: str
    message: str

    def __post_init__(self) -> None:
        _immutable(self)
        _one_of(self.severity, ("info", "warning", "error"), "severity")
        if not self.code or not self.message:
            raise ValueError("Diagnostic requires code and message")


@dataclass(frozen=True)
class InputObservation:
    """Owner-named input fingerprint (config, source, parent, manifest or clock)."""

    name: str
    value: object

    def __post_init__(self) -> None:
        _immutable(self.value)


@dataclass(frozen=True)
class ApplyConsent:
    """Explicit automatic-work consent; drift requires exact fresh owner preparation.

    No mission-repair or blanket --yes overwrite permission is represented here.
    """

    automatic: bool = False
    overwrite_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _immutable(self.overwrite_paths)
        for path in self.overwrite_paths:
            _relative_path(path)


@dataclass(frozen=True)
class AssessmentInputs:
    """Resolved root and immutable projected owner data, never a virtual filesystem."""

    root: OperationRoot
    projected: object = None
    consent: ApplyConsent = ApplyConsent()

    def __post_init__(self) -> None:
        _immutable(self)


@dataclass(frozen=True)
class OwnerAssessment:
    """One executable owner's whole-root preparation; prepared data stays in process."""

    owner_key: str
    root: OperationRoot
    effects: tuple[PhysicalEffect, ...] = ()
    dispositions: tuple[Disposition, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    complete: bool = True
    inputs_fingerprint: tuple[InputObservation, ...] = ()
    prepared: object = None
    consent: ApplyConsent = ApplyConsent()

    def __post_init__(self) -> None:
        _immutable(self)
        if any(effect.owner != self.owner_key for effect in self.effects):
            raise ValueError("Assessment effects require the same executable owner")


@dataclass(frozen=True)
class OwnerApplyResult:
    """Actual effect IDs after application, including truthful partial I/O outcomes."""

    owner_key: str
    succeeded: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    outcome: str = "applied"

    def __post_init__(self) -> None:
        _immutable(self)
        _one_of(self.outcome, ("applied", "partial", "failed", "skipped", "precondition_changed"), "apply outcome")
        ids = self.succeeded + self.failed + self.skipped
        if len(set(ids)) != len(ids):
            raise ValueError("Apply result IDs must be unique and disjoint")
        if self.outcome == "precondition_changed" and self.succeeded:
            raise ValueError("Changed preconditions must stop the whole batch before writes")
        if self.outcome == "applied" and self.failed:
            raise ValueError("Failed effects cannot be reported as an applied batch")
        if self.outcome in {"failed", "skipped"} and self.succeeded:
            raise ValueError("A batch with succeeded effects must report its partial outcome")
