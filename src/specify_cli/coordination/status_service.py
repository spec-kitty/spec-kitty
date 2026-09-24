"""Status/coordination source-of-truth boundary.

This module is the explicit contract layer for rc34-adjacent mission state
surfaces:

* status reads: primary checkout, coordination worktree, or coordination branch
  ref read via ``git show`` without worktree creation;
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
"""

from __future__ import annotations

import enum
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.status import (
        CurrentWpState,
        EventStream,
        InnerStateChanged,
        StatusEvent,
    )


class StatusReadSource(enum.StrEnum):
    """Explicit status read source."""

    PRIMARY_CHECKOUT = "primary_checkout"
    OWNED_CHECKOUT = "owned_checkout"
    COORDINATION_WORKTREE = "coordination_worktree"
    COORDINATION_BRANCH_REF = "coordination_branch_ref"


class EventLogWriteTarget(enum.StrEnum):
    """Explicit event-log mutation target."""

    PRIMARY_CHECKOUT_APPEND = "primary_checkout_append"
    LEGACY_LANE_APPEND = "legacy_lane_append"
    COORDINATION_TRANSACTION_APPEND = "coordination_transaction_append"


class StatusContractError(TypeError):
    """Raised when a read-only contract is used for mutation or vice versa."""


def _is_coordination_worktree_path(path: Path) -> bool:
    """Return True for contract paths rooted under the in-repo worktrees dir.

    This is a contract-label *consistency* guard (does the caller's labelled
    contract — primary vs coordination — match the path's worktree shape), not
    a topology-routing decision. The shape *proposal* is delegated to the
    blessed seam primitive :func:`is_under_worktrees_segment` so the
    ``".worktrees" in parts`` idiom lives only inside the topology authority
    module (C-SEAM-1). Routing/canonical-surface decisions go through
    :func:`is_registered_coord_worktree`, which additionally consults the git
    registry (name proposes, registry disposes).
    """
    from specify_cli.coordination.surface_resolver import is_under_worktrees_segment

    return is_under_worktrees_segment(path)


@dataclass(frozen=True)
class EventLogReadContract:
    """Read-only event-log contract.

    ``feature_dir`` is the source directory for filesystem-backed reads. For a
    branch-ref read it names the mission directory inside the ref path, while
    ``parser_feature_dir`` points at the primary checkout for legacy
    slug-to-mission-id resolution.
    """

    source: StatusReadSource
    feature_dir: Path
    repo_root: Path | None = None
    destination_ref: str | None = None
    parser_feature_dir: Path | None = None
    owned_root: Path | None = None

    @classmethod
    def owned_checkout(
        cls, feature_dir: Path, *, repo_root: Path, owned_root: Path
    ) -> EventLogReadContract:
        """Carry explicit checkout scope; readers validate it before opening events."""
        return cls(
            source=StatusReadSource.OWNED_CHECKOUT,
            feature_dir=feature_dir,
            repo_root=repo_root,
            owned_root=owned_root,
        )

    @classmethod
    def primary_checkout(cls, feature_dir: Path) -> EventLogReadContract:
        return cls(source=StatusReadSource.PRIMARY_CHECKOUT, feature_dir=feature_dir)

    @classmethod
    def coordination_worktree(cls, feature_dir: Path) -> EventLogReadContract:
        return cls(source=StatusReadSource.COORDINATION_WORKTREE, feature_dir=feature_dir)

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
            source=StatusReadSource.COORDINATION_BRANCH_REF,
            feature_dir=feature_dir,
            repo_root=repo_root,
            destination_ref=destination_ref,
            parser_feature_dir=parser_feature_dir,
        )


@dataclass(frozen=True)
class EventLogWriteContract:
    """Mutating event-log contract."""

    target: EventLogWriteTarget
    feature_dir: Path

    @classmethod
    def primary_checkout_append(cls, feature_dir: Path) -> EventLogWriteContract:
        return cls(
            target=EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND,
            feature_dir=feature_dir,
        )

    @classmethod
    def coordination_transaction_append(cls, feature_dir: Path) -> EventLogWriteContract:
        return cls(
            target=EventLogWriteTarget.COORDINATION_TRANSACTION_APPEND,
            feature_dir=feature_dir,
        )

    @classmethod
    def legacy_lane_append(cls, feature_dir: Path) -> EventLogWriteContract:
        return cls(
            target=EventLogWriteTarget.LEGACY_LANE_APPEND,
            feature_dir=feature_dir,
        )


def _validate_owned_read(contract: EventLogReadContract) -> None:
    """Validate owned authority without weakening primary/coordination labels."""
    from specify_cli.core.owned_mission import resolve_owned_mission
    from specify_cli.core.paths import get_main_repo_root

    if contract.repo_root is None or contract.owned_root is None:
        raise StatusContractError("owned_checkout reads require primary and owned roots")
    if get_main_repo_root(contract.repo_root).resolve() != contract.repo_root.resolve():
        raise StatusContractError("owned_checkout repo_root must identify the primary checkout")
    owned = resolve_owned_mission(contract.repo_root, contract.owned_root, contract.feature_dir.name)
    if owned.directory != contract.feature_dir.resolve():
        raise StatusContractError("owned_checkout mission directory does not match the validated checkout")


def read_event_log(contract: EventLogReadContract) -> list[StatusEvent]:
    """Read events from the contract's explicit source without mutation."""
    from specify_cli.status import EVENTS_FILENAME, read_events, read_events_from_text  # noqa: PLC0415

    if not isinstance(contract, EventLogReadContract):
        raise StatusContractError("read_event_log requires EventLogReadContract")

    if contract.source == StatusReadSource.OWNED_CHECKOUT:
        _validate_owned_read(contract)
        return read_events(contract.feature_dir)

    if contract.source in {
        StatusReadSource.PRIMARY_CHECKOUT,
        StatusReadSource.COORDINATION_WORKTREE,
    }:
        if (
            contract.source == StatusReadSource.PRIMARY_CHECKOUT
            and _is_coordination_worktree_path(contract.feature_dir)
        ):
            raise StatusContractError(
                "primary_checkout reads must not target coordination worktree paths"
            )
        if (
            contract.source == StatusReadSource.COORDINATION_WORKTREE
            and not _is_coordination_worktree_path(contract.feature_dir)
        ):
            raise StatusContractError(
                "coordination_worktree reads require a coordination worktree path"
            )
        return read_events(contract.feature_dir)

    if contract.source == StatusReadSource.COORDINATION_BRANCH_REF:
        if contract.repo_root is None or contract.destination_ref is None:
            raise StatusContractError(
                "coordination_branch_ref reads require repo_root and destination_ref"
            )
        events_ref = (
            f"{contract.destination_ref}:"
            f"kitty-specs/{contract.feature_dir.name}/{EVENTS_FILENAME}"
        )
        result = subprocess.run(
            ["git", "-C", str(contract.repo_root), "show", events_ref],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return []
        parser_feature_dir = contract.parser_feature_dir or contract.feature_dir
        return read_events_from_text(parser_feature_dir, result.stdout)

    raise StatusContractError(f"unsupported status read source: {contract.source}")


def read_event_stream_log(contract: EventLogReadContract) -> EventStream:
    """Read transitions and annotations from an explicit status source.

    This is the annotation-aware counterpart to :func:`read_event_log`.  It
    preserves the same source-label validation and branch-ref semantics while
    returning the complete event stream required by runtime-state reducers.
    """
    from specify_cli.status import (  # noqa: PLC0415
        EVENTS_FILENAME,
        EventStream,
        read_event_stream,
        read_event_stream_from_text,
    )

    if not isinstance(contract, EventLogReadContract):
        raise StatusContractError("read_event_stream_log requires EventLogReadContract")

    if contract.source == StatusReadSource.OWNED_CHECKOUT:
        _validate_owned_read(contract)
        return read_event_stream(contract.feature_dir)

    if contract.source in {
        StatusReadSource.PRIMARY_CHECKOUT,
        StatusReadSource.COORDINATION_WORKTREE,
    }:
        if (
            contract.source == StatusReadSource.PRIMARY_CHECKOUT
            and _is_coordination_worktree_path(contract.feature_dir)
        ):
            raise StatusContractError(
                "primary_checkout reads must not target coordination worktree paths"
            )
        if (
            contract.source == StatusReadSource.COORDINATION_WORKTREE
            and not _is_coordination_worktree_path(contract.feature_dir)
        ):
            raise StatusContractError(
                "coordination_worktree reads require a coordination worktree path"
            )
        return read_event_stream(contract.feature_dir)

    if contract.source == StatusReadSource.COORDINATION_BRANCH_REF:
        if contract.repo_root is None or contract.destination_ref is None:
            raise StatusContractError(
                "coordination_branch_ref reads require repo_root and destination_ref"
            )
        events_ref = (
            f"{contract.destination_ref}:"
            f"kitty-specs/{contract.feature_dir.name}/{EVENTS_FILENAME}"
        )
        result = subprocess.run(
            ["git", "-C", str(contract.repo_root), "show", events_ref],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return EventStream()
        parser_feature_dir = contract.parser_feature_dir or contract.feature_dir
        return read_event_stream_from_text(parser_feature_dir, result.stdout)

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


def append_event_log(
    contract: EventLogWriteContract,
    event: StatusEvent | InnerStateChanged,
) -> None:
    """Append one event using an explicit mutating contract."""
    from specify_cli.status._unsafe import append_annotations_atomic_verified as _append_annotations_atomic_verified
    from specify_cli.status._unsafe import append_event_verified as _append_event_verified

    if not isinstance(contract, EventLogWriteContract):
        raise StatusContractError("append_event_log requires EventLogWriteContract")
    _validate_write_contract(contract)
    from specify_cli.status import InnerStateChanged  # noqa: PLC0415

    if isinstance(event, InnerStateChanged):
        _append_annotations_atomic_verified(contract.feature_dir, [event])
    else:
        _append_event_verified(contract.feature_dir, event)


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
    if (
        contract.target == EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND
        and _is_coordination_worktree_path(contract.feature_dir)
    ):
        raise StatusContractError(
            "primary_checkout_append must not target coordination worktree paths"
        )
    if (
        contract.target == EventLogWriteTarget.COORDINATION_TRANSACTION_APPEND
        and not _is_coordination_worktree_path(contract.feature_dir)
    ):
        raise StatusContractError(
            "coordination_transaction_append requires a coordination worktree path"
        )


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
    "append_event_stream_log",
    "merge_append_preserving_coordination_event_log_bytes",
    "read_event_log",
    "read_event_stream_log",
    "wp_lane_actor_from_events",
]
