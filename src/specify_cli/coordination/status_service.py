"""Status/coordination source-of-truth boundary.

This module is the explicit contract layer for rc34-adjacent mission state
surfaces:

* status reads: primary checkout, coordination worktree, or coordination branch
  ref read via one ``git cat-file --batch`` without worktree creation; the ref
  reader is typed (:class:`RefRead`): an absent file on a readable ref is an
  empty history, a missing or unreadable ref raises
  :class:`StatusSurfaceRefUnreadable` (FR-004, ADR 2026-11-06-2);
* move-task/review handoff: read-only transactional snapshots use the same
  target as transactional writes;
* planning-artifact commits: append-preserving coordination event-log merge is a
  named helper, never a raw overwrite;
* event-log writes: primary-checkout appends and coordination-transaction
  appends are separate write contracts;
* bootstrap/repair: intentionally mutating paths remain outside read-only
  contracts and should call primary/coordination write contracts explicitly.

The key rule is visibility at the call site: callers choose a read source or a
write target by name. There is no global event-log path redirect.

A repository-root-labelled (``PRIMARY_CHECKOUT`` / ``PRIMARY_CHECKOUT_APPEND``)
contract may additionally carry the validated ``owned`` ownership fact
(WP06, FR-013/FR-014). Classification of whether such a contract's path
targets a coordination worktree is delegated entirely to
:func:`specify_cli.coordination.surface_resolver.primary_read_targets_coord_worktree`,
which consults the fact before path shape. There is deliberately no new
``StatusReadSource`` / ``EventLogWriteTarget`` member for an owned read (C-002):
an owned repository-root-labelled contract IS a ``primary_checkout`` contract,
just one that carries proof its path is safe.
"""

from __future__ import annotations

import enum
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

# The ONE status read-source enum (review cycle 1, N6): the read door's declared sources. A
# ``primary_checkout`` contract reads ``WRITE_CHECKOUT``, a ``coordination_worktree`` contract
# ``COORD_WORKTREE`` and a ``coordination_branch_ref`` contract ``COORD_BRANCH_REF``.
from specify_cli.status.read_surface import StatusReadSource

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

    from specify_cli.status import (
        CurrentWpState,
        EventStream,
        InnerStateChanged,
        StatusEvent,
    )


class EventLogWriteTarget(enum.StrEnum):
    """Explicit event-log mutation target."""

    PRIMARY_CHECKOUT_APPEND = "primary_checkout_append"
    COORDINATION_TRANSACTION_APPEND = "coordination_transaction_append"


class StatusContractError(TypeError):
    """Raised when a read-only contract is used for mutation or vice versa."""


STATUS_WRITE_TARGETS_LANE_CHECKOUT = "STATUS_WRITE_TARGETS_LANE_CHECKOUT"
"""Error code of :class:`StatusWriteTargetsLaneCheckout` (``contracts/error-codes.yaml``, FR-041)."""


class StatusWriteTargetsLaneCheckout(StatusContractError):
    """A status write whose target lies inside a registered lane checkout (FR-041).

    A lane checkout never shows the Mission's status files and a lane never
    changes them (ADR 2026-07-29-1, restated ruling 3). The worktree registry
    classifies the target (a linked checkout on a lane branch), never the
    ``.worktrees/`` path shape, so a lane checkout placed anywhere refuses.
    """

    error_code: str = STATUS_WRITE_TARGETS_LANE_CHECKOUT

    def __init__(self, *, target: Path, checkout: Path, branch: str) -> None:
        self.target = target
        self.checkout = checkout
        self.branch = branch
        super().__init__(
            f"Refusing a status write into {target}: it lies inside the lane checkout {checkout} (branch {branch}). "
            "A lane never changes the Mission's status files; status is written on the resolved status surface "
            f"(the coordination worktree, or the write checkout). Error code: {STATUS_WRITE_TARGETS_LANE_CHECKOUT}."
        )


def refuse_status_write_into_lane_checkout(target: Path) -> None:
    """Raise :class:`StatusWriteTargetsLaneCheckout` when *target* lies in a registered lane checkout.

    Raises:
        StatusWriteTargetsLaneCheckout: the registry places *target* in a lane checkout.
        WorktreeRegistryUnavailable: the registry cannot be read (fail closed).
    """
    from specify_cli.lanes.lane_checkout import lane_checkout_containing  # noqa: PLC0415 -- cold path, avoids a lanes<->coordination import cycle

    lane = lane_checkout_containing(target)
    if lane is not None and lane.branch is not None:
        raise StatusWriteTargetsLaneCheckout(target=target, checkout=lane.path, branch=lane.branch)


def _validate_read_labels(contract: EventLogReadContract) -> None:
    """Fold the duplicated ``PRIMARY_CHECKOUT`` / ``COORDINATION_WORKTREE``
    read-guard blocks that :func:`read_event_log` and :func:`read_event_stream_log`
    used to repeat (WP06 campsite; behaviour-preserving). Classification is
    delegated entirely to
    :func:`specify_cli.coordination.surface_resolver.primary_read_targets_coord_worktree`,
    which consults ``contract.owned`` (the validated fact, when present)
    before path shape. A ``COORDINATION_WORKTREE`` contract has no ``owned``
    field, so it always classifies by shape alone -- unchanged (FR-014).
    """
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415 -- cold path
        primary_read_targets_coord_worktree,
    )

    owned = contract.owned if contract.source == StatusReadSource.WRITE_CHECKOUT else None
    targets_coord = primary_read_targets_coord_worktree(contract.feature_dir, owned=owned)
    if contract.source == StatusReadSource.WRITE_CHECKOUT and targets_coord:
        raise StatusContractError("primary_checkout reads must not target coordination worktree paths")
    if contract.source == StatusReadSource.COORD_WORKTREE and not targets_coord:
        raise StatusContractError("coordination_worktree reads require a coordination worktree path")


@dataclass(frozen=True)
class EventLogReadContract:
    """Read-only event-log contract.

    ``feature_dir`` is the source directory for filesystem-backed reads. For a
    branch-ref read it names the mission directory inside the ref path, while
    ``parser_feature_dir`` points at the primary checkout for legacy
    slug-to-mission-id resolution.

    ``owned`` is the validated :class:`~mission_runtime.OwnedCheckout` fact
    for a ``PRIMARY_CHECKOUT`` contract whose path lives under an owned
    checkout (WP06). It is the LAST field so positional construction stays
    compatible, and it is ``None`` for every non-owned caller and for every
    other source (a coordination-labelled contract never carries a fact —
    see :func:`_validate_read_labels`).
    """

    source: StatusReadSource
    feature_dir: Path
    repo_root: Path | None = None
    destination_ref: str | None = None
    parser_feature_dir: Path | None = None
    owned: OwnedCheckout | None = None

    @classmethod
    def primary_checkout(cls, feature_dir: Path, *, owned: OwnedCheckout | None = None) -> EventLogReadContract:
        return cls(source=StatusReadSource.WRITE_CHECKOUT, feature_dir=feature_dir, owned=owned)

    @classmethod
    def coordination_worktree(cls, feature_dir: Path) -> EventLogReadContract:
        return cls(source=StatusReadSource.COORD_WORKTREE, feature_dir=feature_dir)

    @classmethod
    def coordination_branch_ref(
        cls,
        *,
        repo_root: Path,
        destination_ref: str,
        feature_dir: Path,
        parser_feature_dir: Path,
    ) -> EventLogReadContract:
        return cls(
            source=StatusReadSource.COORD_BRANCH_REF,
            feature_dir=feature_dir,
            repo_root=repo_root,
            destination_ref=destination_ref,
            parser_feature_dir=parser_feature_dir,
        )


@dataclass(frozen=True)
class EventLogWriteContract:
    """Mutating event-log contract.

    ``owned`` mirrors :attr:`EventLogReadContract.owned` (WP06): the validated
    fact for a ``PRIMARY_CHECKOUT_APPEND`` contract whose path lives under an
    owned checkout. Last field, default ``None``, for the same positional-
    compatibility reason.
    """

    target: EventLogWriteTarget
    feature_dir: Path
    owned: OwnedCheckout | None = None

    @classmethod
    def primary_checkout_append(cls, feature_dir: Path, *, owned: OwnedCheckout | None = None) -> EventLogWriteContract:
        return cls(
            target=EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND,
            feature_dir=feature_dir,
            owned=owned,
        )

    @classmethod
    def coordination_transaction_append(cls, feature_dir: Path) -> EventLogWriteContract:
        return cls(
            target=EventLogWriteTarget.COORDINATION_TRANSACTION_APPEND,
            feature_dir=feature_dir,
        )


STATUS_SURFACE_REF_UNREADABLE = "STATUS_SURFACE_REF_UNREADABLE"
"""Error code of :class:`StatusSurfaceRefUnreadable` (``contracts/error-codes.yaml``)."""

_BATCH_MISSING_MARKERS = (b"missing", b"ambiguous")


class StatusSurfaceRefUnreadable(RuntimeError):
    """A status read sourced from a ref hit a missing or unreadable ref or object, or git failed.

    Never read as an empty history (FR-004): a broken ref is not genesis. Carries a
    stable ``error_code`` so callers route without string parsing.
    """

    error_code: str = STATUS_SURFACE_REF_UNREADABLE

    def __init__(self, *, repo_root: Path, ref: str, path: str, detail: str) -> None:
        self.repo_root = repo_root
        self.ref = ref
        self.path = path
        self.detail = detail
        super().__init__(
            f"Cannot read {path} from ref {ref!r} in {repo_root}: {detail}. "
            f"A status history is never assumed empty when its ref cannot be read. "
            f"Error code: {STATUS_SURFACE_REF_UNREADABLE}."
        )


@dataclass(frozen=True)
class RefRead:
    """Typed result of a ref read: ``ABSENT`` or ``PRESENT(data)`` (data model §2).

    ``ABSENT`` means the ref resolved to a commit whose tree has no file at the
    path; readers map it to an empty history. A status read door applies its
    declared pre-seed fallback BEFORE reading an ABSENT result as empty
    (ADR 2026-11-06-2); this reader itself never falls back.
    """

    data: bytes | None = None
    ABSENT: ClassVar[RefRead]

    @property
    def absent(self) -> bool:
        return self.data is None

    @classmethod
    def present(cls, data: bytes) -> RefRead:
        return cls(data=data)


RefRead.ABSENT = RefRead()


def _split_batch_entry(output: bytes) -> tuple[bytes, bytes | None, bytes]:
    """Split one ``git cat-file --batch`` entry off *output*: ``(type, body, rest)``.

    ``body`` is ``None`` for a ``missing`` / ``ambiguous`` entry, whose ``type`` is
    that marker. Raises ``ValueError`` on truncated output.
    """
    newline = output.find(b"\n")
    if newline < 0:
        raise ValueError("truncated cat-file header")
    fields = output[:newline].split()
    if not fields:
        raise ValueError("empty cat-file header")
    if fields[-1] in _BATCH_MISSING_MARKERS:
        return fields[-1], None, output[newline + 1 :]
    if len(fields) != 3:
        raise ValueError(f"unexpected cat-file header {output[:newline]!r}")
    size = int(fields[2])
    start = newline + 1
    if len(output) < start + size:
        raise ValueError("truncated cat-file body")
    return fields[1], output[start : start + size], output[start + size + 1 :]


def _run_cat_file_batch(repo_root: Path, request: bytes, *, ref: str, path: str) -> bytes:
    """Run one batched object read; any failure to run git raises the typed error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "--batch"],
            input=request,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=str(exc)) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or f"git exit {result.returncode}"
        raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=detail)
    return result.stdout


def ref_names_object(repo_root: Path, ref: str) -> bool:
    """True when *ref* names an object in *repo_root* (``rev-parse --verify``; no object read).

    Named apart from ``specify_cli.lanes._git.ref_exists``, which peels to a commit
    (``<ref>^{commit}``) and so answers ``False`` for a ref naming a missing object; this one
    answers ``True`` there, so the object read reports the corruption (renamed in WP05).

    The one home of the declared ref-missing arm (FR-004) that a status read door
    checks before :func:`read_status_ref`: a ref that does not resolve, and a
    *repo_root* that is not a git repository, both answer ``False``. A ref that
    exists but names an object the repository lacks answers ``True``, so its read
    still raises :class:`StatusSurfaceRefUnreadable` (never read as genesis).
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", "--end-of-options", ref],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def read_status_ref(repo_root: Path, ref: str, path: str) -> RefRead:
    """Read *path* at *ref* with ONE ``git cat-file --batch`` subprocess (NFR-001).

    The ref and path travel on stdin, never in argv, so a ``-``-prefixed name can
    never be read as an option. The first request resolves ``<ref>^{commit}``,
    the second ``<ref>:<path>``:

    * the commit does not resolve (missing ref, missing object, ambiguous name)
      or git fails -> :class:`StatusSurfaceRefUnreadable`;
    * the commit resolves but the tree has no such path -> :attr:`RefRead.ABSENT`;
    * the path is a blob -> ``RefRead.present(<bytes>)``; anything else raises.

    A coordination branch that the resolver already classifies as deleted keeps
    raising ``CoordinationBranchDeleted`` there, before this reader runs.
    """
    request = f"{ref}^{{commit}}\n{ref}:{path}\n".encode()
    output = _run_cat_file_batch(repo_root, request, ref=ref, path=path)
    try:
        commit_type, _commit, rest = _split_batch_entry(output)
        if commit_type != b"commit":
            detail = f"ref does not resolve to a commit ({commit_type.decode(errors='replace')})"
            raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=detail)
        file_type, body, _rest = _split_batch_entry(rest)
    except ValueError as exc:
        raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=str(exc)) from exc
    if body is None:
        if file_type == b"missing":
            return RefRead.ABSENT
        raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=f"path is {file_type.decode(errors='replace')}")
    if file_type != b"blob":
        raise StatusSurfaceRefUnreadable(repo_root=repo_root, ref=ref, path=path, detail=f"path is a {file_type.decode(errors='replace')}, not a file")
    return RefRead.present(body)


def _read_ref_events_text(contract: EventLogReadContract) -> str | None:
    """Read a ``COORDINATION_BRANCH_REF`` contract's log text, or ``None`` when ABSENT."""
    from specify_cli.status import EVENTS_FILENAME  # noqa: PLC0415

    if contract.repo_root is None or contract.destination_ref is None:
        raise StatusContractError("coordination_branch_ref reads require repo_root and destination_ref")
    path = f"kitty-specs/{contract.feature_dir.name}/{EVENTS_FILENAME}"
    result = read_status_ref(contract.repo_root, contract.destination_ref, path)
    if result.data is None:
        return None
    return result.data.decode("utf-8", errors="replace")


def read_event_log(contract: EventLogReadContract) -> list[StatusEvent]:
    """Read events from the contract's explicit source without mutation."""
    from specify_cli.status import read_events, read_events_from_text  # noqa: PLC0415

    if not isinstance(contract, EventLogReadContract):
        raise StatusContractError("read_event_log requires EventLogReadContract")

    if contract.source in {
        StatusReadSource.WRITE_CHECKOUT,
        StatusReadSource.COORD_WORKTREE,
    }:
        _validate_read_labels(contract)
        return read_events(contract.feature_dir)

    if contract.source == StatusReadSource.COORD_BRANCH_REF:
        text = _read_ref_events_text(contract)
        if text is None:
            return []
        parser_feature_dir = contract.parser_feature_dir or contract.feature_dir
        return read_events_from_text(parser_feature_dir, text)

    raise StatusContractError(f"unsupported status read source: {contract.source}")


def read_event_stream_log(contract: EventLogReadContract) -> EventStream:
    """Read transitions and annotations from an explicit status source.

    This is the annotation-aware counterpart to :func:`read_event_log`.  It
    preserves the same source-label validation and branch-ref semantics while
    returning the complete event stream required by runtime-state reducers.
    """
    from specify_cli.status import (  # noqa: PLC0415
        EventStream,
        read_event_stream,
        read_event_stream_from_text,
    )

    if not isinstance(contract, EventLogReadContract):
        raise StatusContractError("read_event_stream_log requires EventLogReadContract")

    if contract.source in {
        StatusReadSource.WRITE_CHECKOUT,
        StatusReadSource.COORD_WORKTREE,
    }:
        _validate_read_labels(contract)
        return read_event_stream(contract.feature_dir)

    if contract.source == StatusReadSource.COORD_BRANCH_REF:
        text = _read_ref_events_text(contract)
        if text is None:
            return EventStream()
        parser_feature_dir = contract.parser_feature_dir or contract.feature_dir
        return read_event_stream_from_text(parser_feature_dir, text)

    raise StatusContractError(f"unsupported status read source: {contract.source}")


def wp_lane_actor_from_events(
    events: list[StatusEvent],
    wp_id: str,
    annotations: list[InnerStateChanged] | None = None,
) -> CurrentWpState:
    """Reduce already-read events into a :class:`CurrentWpState` snapshot.

    Lane and actor come from the transition fold; ``role`` is read from the
    resolved-binding ``role`` slot of the SAME reduction (C-002: no second
    reduce, no split-brain reader). ``role`` is annotation-folded, so callers
    that need it (the in-lock re-claim read) MUST pass ``annotations`` — the
    ``.lane``-only consumers (coherence / done bookkeeping) omit them and simply
    see ``role=None``. Role is never derived by splitting the compound actor
    string (#2861): ``actor`` is projected to its bare tool identity while
    ``role`` rides its own reduced slot.

    An *unseeded* WP (no events at all, or no snapshot entry for wp_id)
    defaults to ``Lane.GENESIS`` — matching the write-side
    ``_derive_from_lane`` behaviour (Contract 3, FR-008).
    """
    from specify_cli.status import (  # noqa: PLC0415
        CurrentWpState,
        Lane,
        actor_identity_str,
        reduce,
    )

    if not events and not annotations:
        return CurrentWpState(Lane.GENESIS, None, None)
    snapshot = reduce(events, annotations)
    state = snapshot.work_packages.get(wp_id)
    if not state:
        return CurrentWpState(Lane.GENESIS, None, None)
    try:
        lane = Lane(str(state.get("lane", Lane.GENESIS)))
    except ValueError:
        lane = Lane.GENESIS

    actor = state.get("actor")
    actor_key = actor_identity_str(actor) if actor is not None else ""
    role = state.get("role")
    return CurrentWpState(lane, actor_key or None, role)


def append_event_stream_log(
    contract: EventLogWriteContract,
    events: list[StatusEvent | InnerStateChanged],
) -> None:
    """Atomically append one mixed transition/annotation durability unit."""
    from specify_cli.status._unsafe import append_event_stream_atomic_verified as _append_event_stream_atomic_verified

    if not isinstance(contract, EventLogWriteContract):
        raise StatusContractError("append_event_stream_log requires EventLogWriteContract")
    _validate_write_contract(contract)
    _append_event_stream_atomic_verified(contract.feature_dir, events)


def _validate_write_contract(contract: EventLogWriteContract) -> None:
    """Mirrors :func:`_validate_read_labels` for the write contracts (WP06).

    Both :class:`EventLogWriteTarget` members are guarded: a
    ``PRIMARY_CHECKOUT_APPEND`` must not target a coordination worktree path,
    and a ``COORDINATION_TRANSACTION_APPEND`` must target one. Neither may
    target a registered lane checkout (FR-041), whatever its path shape.
    """
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415 -- cold path
        primary_read_targets_coord_worktree,
    )

    refuse_status_write_into_lane_checkout(contract.feature_dir)

    owned = contract.owned if contract.target == EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND else None
    targets_coord = primary_read_targets_coord_worktree(contract.feature_dir, owned=owned)
    if contract.target == EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND and targets_coord:
        raise StatusContractError("primary_checkout_append must not target coordination worktree paths")
    if contract.target == EventLogWriteTarget.COORDINATION_TRANSACTION_APPEND and not targets_coord:
        raise StatusContractError("coordination_transaction_append requires a coordination worktree path")


def merge_append_preserving_coordination_event_log_bytes(
    existing_coordination: bytes,
    incoming_primary_checkout: bytes,
) -> bytes:
    """Append-only union keyed by ``event_id`` for coordination writes.

    The existing coordination log is authoritative. Incoming primary-checkout
    rows may add new lifecycle/envelope rows or just-emitted transitions, but
    they must never remove a row already present on the coordination branch.
    """

    def _key(line: str) -> str:
        try:
            obj: Any = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return f"raw:{line}"
        if isinstance(obj, dict):
            event_id = obj.get("event_id")
            if isinstance(event_id, str) and event_id:
                return f"id:{event_id}"
        return f"raw:{line}"

    existing_lines = [
        line
        for line in existing_coordination.decode("utf-8", "replace").splitlines()
        if line.strip()
    ]
    seen = {_key(line) for line in existing_lines}
    merged = list(existing_lines)
    for line in incoming_primary_checkout.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        key = _key(line)
        if key not in seen:
            seen.add(key)
            merged.append(line)
    if not merged:
        return b""
    return ("\n".join(merged) + "\n").encode("utf-8")


__all__ = [
    "EventLogReadContract",
    "EventLogWriteContract",
    "StatusWriteTargetsLaneCheckout",
    "append_event_stream_log",
    "merge_append_preserving_coordination_event_log_bytes",
    "read_event_log",
    "read_event_stream_log",
    "ref_names_object",
    "refuse_status_write_into_lane_checkout",
    "wp_lane_actor_from_events",
]
