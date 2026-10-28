"""Client-side shapes of the CLI to write-service protocol (#6675, ADR 2026-10-27-1).

The resident Java write service (ADR 2026-10-22-1) is reached over loopback
HTTP. Its contract is ``contracts/mission-write/openapi.yaml``; this module is
the CLI's typed view of it: the protocol constants, the refusal vocabulary,
the request shapes the EventBridge client sends, the response shapes it reads,
version negotiation and the endpoint file that names the running service.

There is no transport here. The client adapter that sends these shapes binds
behind the EventBridge port (``runtime.next._internal_runtime.events.
bind_event_bridge``) at the lane-transition cut-over (#6195). The service is
authoritative: any check this module makes is a shape check, never a domain
decision.

Standard library only; ``specify_cli.coordination`` is never imported here, so
the status package gains no import cycle (issue #6675, design note 2).
"""

from __future__ import annotations

import enum
import errno
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from kernel.paths import is_windows
from specify_cli.core.errors import StructuredError

if TYPE_CHECKING:
    from runtime.next.event_bridge import WorkPackageTransition

# The adapter-facing surface the write-service client imports when it binds at the #6195
# cut-over; until then each name is a priced dead-symbol allowlist entry
# (category_c_write_service_client_6675). Everything else stays importable (tests use it).
__all__ = [
    "PROTOCOL_ONLY_CODES",
    "REASON_CODE",
    "WRITE_PROTOCOL_HEADER",
    "AnnotationRequest",
    "TransitionBatch",
    "endpoint_file_path",
    "negotiate_protocol_version",
    "read_endpoint_file",
    "repository_id",
    "transition_unit_from",
]

WRITE_PROTOCOL_HEADER = "Spec-Kitty-Write-Protocol"
SUPPORTED_PROTOCOL_VERSIONS: tuple[int, ...] = (1,)
REASON_URN_PREFIX = "urn:spec-kitty:write-refusal:"
MAX_BATCH_UNITS = 64

ENDPOINT_DIRECTORY = "spec-kitty-write-service"
ENDPOINT_FILE = "endpoint.json"
ENDPOINT_SCHEMA_VERSION = 1
ENDPOINT_HOST = "127.0.0.1"
ENDPOINT_MAX_BYTES = 64 * 1024
TOKEN_MIN_LENGTH = 43  # 32 random bytes, URL-safe base64 without padding
_TOKEN_ALPHABET = re.compile(r"[A-Za-z0-9_-]+")
_PRIVATE_MODE_MASK = 0o077


class ProtocolShapeError(ValueError):
    """A request or response does not have the shape the contract defines."""


class WriteSurface(enum.StrEnum):
    """Which CLI write contract the request was resolved under.

    ``checkout_append`` is a direct append in the checkout that holds the Mission
    directory (the CLI's ``EventLogWriteTarget.PRIMARY_CHECKOUT_APPEND``, whose
    internal name predates the glossary); ``coordination_transaction_append`` is an
    append inside the coordination transaction.
    """

    CHECKOUT_APPEND = "checkout_append"
    COORDINATION_TRANSACTION_APPEND = "coordination_transaction_append"


# The CLI's EventLogWriteTarget values, mapped to the wire values.
_SURFACE_BY_TARGET: Mapping[str, WriteSurface] = MappingProxyType(
    {
        "primary_checkout_append": WriteSurface.CHECKOUT_APPEND,
        "coordination_transaction_append": WriteSurface.COORDINATION_TRANSACTION_APPEND,
    }
)


class WriteRefusalCode(enum.StrEnum):
    """Every ``code`` a write-service refusal carries (the contract's ``WriteRefusalCode``).

    The CLI codes are the strings the CLI raises today, verbatim; the
    protocol-only ones are listed in :data:`PROTOCOL_ONLY_CODES`.
    """

    TRANSITION_REJECTED = "TRANSITION_REJECTED"
    WP_ALREADY_CLAIMED = "WP_ALREADY_CLAIMED"
    DEPENDENCIES_NOT_SATISFIED = "DEPENDENCIES_NOT_SATISFIED"
    WP_NOT_FOUND = "WP_NOT_FOUND"
    MISSION_NOT_FOUND = "MISSION_NOT_FOUND"
    STATUS_LOCK_HELD = "STATUS_LOCK_HELD"
    BOOKKEEPING_DOUBLE_EVENT_ID = "BOOKKEEPING_DOUBLE_EVENT_ID"
    COORD_STATUS_SURFACE_DIVERGED = "COORD_STATUS_SURFACE_DIVERGED"
    PROTECTED_BRANCH_REFUSED = "PROTECTED_BRANCH_REFUSED"
    DESTINATION_REF_NOT_FOUND = "DESTINATION_REF_NOT_FOUND"
    DESTINATION_REF_INVALID_SHAPE = "DESTINATION_REF_INVALID_SHAPE"
    DESTINATION_REF_NOT_LOCAL = "DESTINATION_REF_NOT_LOCAL"
    BOOKKEEPING_WORKTREE_MISSING = "BOOKKEEPING_WORKTREE_MISSING"
    FALLBACK_COORD_WORKTREE_UNRESOLVED = "FALLBACK_COORD_WORKTREE_UNRESOLVED"
    COORDINATION_BRANCH_DELETED = "COORDINATION_BRANCH_DELETED"
    COORDINATION_WORKTREE_UNMATERIALIZED = "COORDINATION_WORKTREE_UNMATERIALIZED"
    OWNED_MISSION_PATH_REFUSED = "OWNED_MISSION_PATH_REFUSED"
    COORD_STATUS_SURFACE_UNREADABLE = "COORD_STATUS_SURFACE_UNREADABLE"
    STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED = "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED"
    BOOKKEEPING_COMMIT_FAILED = "BOOKKEEPING_COMMIT_FAILED"
    WRITE_LOCATION_UNVERIFIED = "WRITE_LOCATION_UNVERIFIED"
    REQUEST_MALFORMED = "REQUEST_MALFORMED"
    PROTOCOL_VERSION_UNSUPPORTED = "PROTOCOL_VERSION_UNSUPPORTED"
    WRITE_TOKEN_INVALID = "WRITE_TOKEN_INVALID"  # noqa: S105 -- a refusal code name, not a credential
    REQUEST_REFUSED = "REQUEST_REFUSED"
    EVENT_ID_CONFLICT = "EVENT_ID_CONFLICT"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"
    SERVICE_BUSY = "SERVICE_BUSY"
    SERVICE_DRAINING = "SERVICE_DRAINING"


_C = WriteRefusalCode
_STATUS_BY_FAMILY: dict[int, tuple[WriteRefusalCode, ...]] = {
    400: (_C.REQUEST_MALFORMED, _C.PROTOCOL_VERSION_UNSUPPORTED),
    401: (_C.WRITE_TOKEN_INVALID,),
    403: (_C.REQUEST_REFUSED,),
    404: (_C.WP_NOT_FOUND, _C.MISSION_NOT_FOUND),
    409: (
        _C.TRANSITION_REJECTED,
        _C.WP_ALREADY_CLAIMED,
        _C.DEPENDENCIES_NOT_SATISFIED,
        _C.STATUS_LOCK_HELD,
        _C.BOOKKEEPING_DOUBLE_EVENT_ID,
        _C.COORD_STATUS_SURFACE_DIVERGED,
        _C.EVENT_ID_CONFLICT,
    ),
    413: (_C.REQUEST_TOO_LARGE,),
    422: (
        _C.PROTECTED_BRANCH_REFUSED,
        _C.DESTINATION_REF_NOT_FOUND,
        _C.DESTINATION_REF_INVALID_SHAPE,
        _C.DESTINATION_REF_NOT_LOCAL,
        _C.BOOKKEEPING_WORKTREE_MISSING,
        _C.FALLBACK_COORD_WORKTREE_UNRESOLVED,
        _C.COORDINATION_BRANCH_DELETED,
        _C.COORDINATION_WORKTREE_UNMATERIALIZED,
        _C.OWNED_MISSION_PATH_REFUSED,
        _C.WRITE_LOCATION_UNVERIFIED,
    ),
    500: (_C.COORD_STATUS_SURFACE_UNREADABLE, _C.STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED, _C.BOOKKEEPING_COMMIT_FAILED),
    503: (_C.SERVICE_BUSY, _C.SERVICE_DRAINING),
}

#: The HTTP status each refusal code fixes.
REFUSAL_STATUS: Mapping[WriteRefusalCode, int] = MappingProxyType({code: status for status, codes in _STATUS_BY_FAMILY.items() for code in codes})

#: Codes the contract mints because the CLI has no counterpart today.
PROTOCOL_ONLY_CODES: frozenset[WriteRefusalCode] = frozenset(
    {
        _C.WRITE_LOCATION_UNVERIFIED,
        _C.REQUEST_MALFORMED,
        _C.PROTOCOL_VERSION_UNSUPPORTED,
        _C.WRITE_TOKEN_INVALID,
        _C.REQUEST_REFUSED,
        _C.EVENT_ID_CONFLICT,
        _C.REQUEST_TOO_LARGE,
        _C.SERVICE_BUSY,
        _C.SERVICE_DRAINING,
    }
)


class WriteRefusalReason(enum.StrEnum):
    """Why a guard refused a transition; carried as a URN in the refusal's ``type`` (provisional)."""

    UNKNOWN_LANE = "unknown_lane"
    ILLEGAL_TRANSITION = "illegal_transition"
    FORCE_REQUIRES_ACTOR_AND_REASON = "force_requires_actor_and_reason"
    ACTOR_REQUIRED = "actor_required"
    DEPENDENCIES_UNSATISFIED = "dependencies_unsatisfied"
    WORKSPACE_CONTEXT_REQUIRED = "workspace_context_required"
    IMPLEMENTATION_EVIDENCE_REQUIRED = "implementation_evidence_required"
    REASON_REQUIRED = "reason_required"
    REVIEW_REF_REQUIRED = "review_ref_required"
    REVIEWER_APPROVAL_REQUIRED = "reviewer_approval_required"
    REVIEW_EVIDENCE_INVALID = "review_evidence_invalid"
    FORCE_NOTE_REQUIRED = "force_note_required"
    DONE_EVIDENCE_INCOMPLETE = "done_evidence_incomplete"
    CLAIM_HELD_BY_OTHER_ACTOR = "claim_held_by_other_actor"
    START_REJECTED = "start_rejected"

    @property
    def urn(self) -> str:
        return f"{REASON_URN_PREFIX}{self.value}"


_R = WriteRefusalReason
#: The refusal code each guard reason travels under.
REASON_CODE: Mapping[WriteRefusalReason, WriteRefusalCode] = MappingProxyType(
    {
        reason: (
            _C.DEPENDENCIES_NOT_SATISFIED
            if reason is _R.DEPENDENCIES_UNSATISFIED
            else _C.WP_ALREADY_CLAIMED
            if reason is _R.CLAIM_HELD_BY_OTHER_ACTOR
            else _C.TRANSITION_REJECTED
        )
        for reason in WriteRefusalReason
    }
)
_REASON_BY_URN: Mapping[str, WriteRefusalReason] = MappingProxyType({reason.urn: reason for reason in WriteRefusalReason})


# -- requests -----------------------------------------------------------------


@dataclass(frozen=True)
class RequestContext:
    """Who asks, from which checkout, and where the CLI resolved the write to land."""

    actor: str
    checkout: str
    mission_directory: str
    write_surface: WriteSurface
    destination_ref: str | None = None

    def to_wire(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "checkout": self.checkout,
            "missionDirectory": self.mission_directory,
            "writeSurface": self.write_surface.value,
            "destinationRef": self.destination_ref,
        }


@dataclass(frozen=True)
class TransitionUnit:
    """One work package transition: the transition row, then its annotations, landing whole."""

    wp_id: str
    rows: tuple[Mapping[str, Any], ...]
    context: RequestContext

    def __post_init__(self) -> None:
        if not self.rows:
            raise ProtocolShapeError("a transition unit needs at least one row")

    def to_wire(self) -> dict[str, Any]:
        return {"wpId": self.wp_id, "rows": [dict(row) for row in self.rows], "context": self.context.to_wire()}


@dataclass(frozen=True)
class TransitionBatch:
    """Several units in one write and one ``fsync``, all or nothing."""

    units: tuple[TransitionUnit, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.units) <= MAX_BATCH_UNITS:
            raise ProtocolShapeError(f"a batch holds 1 to {MAX_BATCH_UNITS} units, not {len(self.units)}")

    def to_wire(self) -> dict[str, Any]:
        return {"units": [unit.to_wire() for unit in self.units]}


@dataclass(frozen=True)
class AnnotationRequest:
    """A standalone inner-state annotation of one work package."""

    wp_id: str
    row: Mapping[str, Any]
    context: RequestContext

    def to_wire(self) -> dict[str, Any]:
        return {"wpId": self.wp_id, "row": dict(self.row), "context": self.context.to_wire()}


def _relative(path: Path, base: Path, what: str) -> str:
    try:
        relative = path.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise ProtocolShapeError(f"the {what} is outside its base directory") from exc
    return relative.as_posix() or "."


def transition_unit_from(transition: WorkPackageTransition, *, checkout: Path, repository_root: Path) -> TransitionUnit:
    """Map the port's :class:`~runtime.next.event_bridge.WorkPackageTransition` to a request unit.

    ``checkout`` is the checkout that holds the Mission directory (the
    repository root checkout, a lane worktree, or the coordination worktree for
    a coordination append);
    ``repository_root`` is the repository root checkout. The write contract's
    target becomes ``writeSurface``; a direct append with no write contract is a
    checkout append.
    """
    rows = tuple(row.to_dict() for row in transition.rows)
    first = rows[0]
    actor, wp_id = first.get("actor"), first.get("wp_id")
    if not isinstance(actor, str) or not actor or not isinstance(wp_id, str) or not wp_id:
        raise ProtocolShapeError("the transition row names no actor or no work package")
    if any(row.get("wp_id") != wp_id for row in rows):
        raise ProtocolShapeError("every row of a unit names the same work package")
    target = getattr(transition.write_contract, "target", None)
    if target is None:
        surface = WriteSurface.CHECKOUT_APPEND
    elif (mapped := _SURFACE_BY_TARGET.get(str(getattr(target, "value", "")))) is not None:
        surface = mapped
    else:
        raise ProtocolShapeError("the write contract names a write target the protocol does not know")
    context = RequestContext(
        actor=actor,
        checkout=_relative(checkout, repository_root, "checkout"),
        mission_directory=_relative(transition.write_location, checkout, "write location"),
        write_surface=surface,
    )
    return TransitionUnit(wp_id=wp_id, rows=rows, context=context)


# -- responses ----------------------------------------------------------------


def _mapping(wire: Any) -> Mapping[str, Any]:
    if not isinstance(wire, Mapping):
        raise ProtocolShapeError("the body is not a JSON object")
    return wire


def _field(wire: Mapping[str, Any], name: str, kind: type | tuple[type, ...]) -> Any:
    value = _mapping(wire).get(name)
    # bool is an int subclass: an integer field never accepts True/False.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ProtocolShapeError(f"field {name!r} is missing or not of the contract's type")
    return value


def _string_tuple(wire: Mapping[str, Any], name: str) -> tuple[str, ...]:
    values = _field(wire, name, list)
    if not all(isinstance(value, str) for value in values):
        raise ProtocolShapeError(f"field {name!r} holds a non-string item")
    return tuple(values)


def _versions(values: Sequence[Any], name: str) -> tuple[int, ...]:
    if not values or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 1 for value in values):
        raise ProtocolShapeError(f"field {name!r} must be a non-empty list of positive integers")
    if any(earlier >= later for earlier, later in zip(values, values[1:], strict=False)):
        raise ProtocolShapeError(f"field {name!r} must be strictly ascending")
    return tuple(values)


@dataclass(frozen=True)
class DurabilityAck:
    """The unit was appended in one write and synced before this answer."""

    event_ids: tuple[str, ...]
    appended_lines: int
    fsynced: bool
    status_commit: str | None
    replayed: bool

    @classmethod
    def from_wire(cls, wire: Mapping[str, Any]) -> DurabilityAck:
        if _field(wire, "fsynced", bool) is not True:
            raise ProtocolShapeError("a durability acknowledgement must state fsynced: true")
        status_commit = wire.get("statusCommit")
        if status_commit is not None and not isinstance(status_commit, str):
            raise ProtocolShapeError("field 'statusCommit' is not a string or null")
        appended_lines = _field(wire, "appendedLines", int)
        if appended_lines < 0:
            raise ProtocolShapeError("field 'appendedLines' is negative")
        return cls(
            event_ids=_string_tuple(wire, "eventIds"),
            appended_lines=appended_lines,
            fsynced=True,
            status_commit=status_commit,
            replayed=_field(wire, "replayed", bool),
        )


@dataclass(frozen=True)
class BatchDurabilityAck:
    """One acknowledgement per unit, in order, behind one ``fsync`` (none for a fully replayed batch)."""

    units: tuple[DurabilityAck, ...]
    fsyncs: int

    @classmethod
    def from_wire(cls, wire: Mapping[str, Any]) -> BatchDurabilityAck:
        raw_units = _field(wire, "units", list)
        if not raw_units:
            raise ProtocolShapeError("a batch acknowledgement holds at least one unit")
        units = tuple(DurabilityAck.from_wire(unit) for unit in raw_units)
        fsyncs = _field(wire, "fsyncs", int)
        # One fsync behind any appended line; none when every unit was already persisted.
        if fsyncs != (0 if all(unit.replayed for unit in units) else 1):
            raise ProtocolShapeError("a batch is synced once, or not at all when every unit was replayed")
        return cls(units=units, fsyncs=fsyncs)


@dataclass(frozen=True)
class Handshake:
    """What the running service is, and which protocol majors it speaks."""

    protocol_versions: tuple[int, ...]
    service_version: str
    instance_id: str
    repository_id: str

    @classmethod
    def from_wire(cls, wire: Mapping[str, Any]) -> Handshake:
        return cls(
            protocol_versions=_versions(_field(wire, "protocolVersions", list), "protocolVersions"),
            service_version=_field(wire, "serviceVersion", str),
            instance_id=_field(wire, "instanceId", str),
            repository_id=_field(wire, "repositoryId", str),
        )


HEALTH_STATUSES = frozenset({"ready", "draining"})


@dataclass(frozen=True)
class Health:
    """Liveness for the launcher (#6676)."""

    status: str
    instance_id: str

    @classmethod
    def from_wire(cls, wire: Mapping[str, Any]) -> Health:
        status = _field(wire, "status", str)
        if status not in HEALTH_STATUSES:
            raise ProtocolShapeError(f"unknown health status {status!r}")
        return cls(status=status, instance_id=_field(wire, "instanceId", str))


@dataclass(frozen=True)
class WriteRefusal:
    """A refusal: the shared problem shape with a code, its fixed status and, for a guard, a reason.

    The client is lenient about the reason: an unknown ``type`` reads as no reason, and a reason
    under a code it is not bound to is kept as sent. The contract binds each reason to one code.
    """

    code: WriteRefusalCode
    status: int
    title: str
    detail: str | None = None
    reason: WriteRefusalReason | None = None

    @classmethod
    def from_wire(cls, wire: Mapping[str, Any]) -> WriteRefusal:
        try:
            code = WriteRefusalCode(_field(wire, "code", str))
        except ValueError as exc:
            raise ProtocolShapeError("unknown refusal code") from exc
        status = _field(wire, "status", int)
        if status != REFUSAL_STATUS[code]:
            raise ProtocolShapeError(f"{code.value} is answered with {REFUSAL_STATUS[code]}, not {status}")
        type_uri = wire.get("type")
        reason = _REASON_BY_URN.get(type_uri) if isinstance(type_uri, str) else None
        detail = wire.get("detail")
        return cls(code=code, status=status, title=_field(wire, "title", str), detail=detail if isinstance(detail, str) else None, reason=reason)


def negotiate_protocol_version(server_versions: Sequence[int]) -> int:
    """The highest protocol major both sides speak, or :class:`ProtocolShapeError`."""
    common = set(server_versions) & set(SUPPORTED_PROTOCOL_VERSIONS)
    if not common:
        raise ProtocolShapeError(f"no common protocol version: the service speaks {sorted(server_versions)}, the CLI {list(SUPPORTED_PROTOCOL_VERSIONS)}")
    return max(common)


def repository_id(git_common_dir: Path) -> str:
    """The identity a service reports for its clone: SHA-256 of the git common dir's real path.

    The path is the resolved path in forward-slash form (``Path.resolve().as_posix()``),
    UTF-8 encoded, case as the file system reports it; ADR 2026-10-27-1 D-4.
    """
    return hashlib.sha256(git_common_dir.resolve().as_posix().encode("utf-8")).hexdigest()  # noqa: TID251 -- protocol identity of a clone, not a charter hash


# -- endpoint file ------------------------------------------------------------


class EndpointRefusalCode(enum.StrEnum):
    """Why the endpoint file cannot be trusted; the write then refuses (fail closed)."""

    MISSING = "WRITE_SERVICE_ENDPOINT_MISSING"
    MALFORMED = "WRITE_SERVICE_ENDPOINT_MALFORMED"
    EXPOSED = "WRITE_SERVICE_ENDPOINT_EXPOSED"
    NOT_LOOPBACK = "WRITE_SERVICE_ENDPOINT_NOT_LOOPBACK"


class EndpointFileError(StructuredError):
    """The endpoint file is missing, malformed, readable by others, or names a non-loopback host.

    The message never carries the token or a field value from the file.
    """

    def __init__(self, code: EndpointRefusalCode, message: str) -> None:
        super().__init__(message)
        self.error_code = code.value


@dataclass(frozen=True)
class WriteServiceEndpoint:
    """The running service of one clone, as its endpoint file names it."""

    host: str
    port: int
    token: str = field(repr=False)
    instance_id: str
    pid: int
    protocol_versions: tuple[int, ...]
    started_at: str


def endpoint_file_path(git_common_dir: Path) -> Path:
    """Where the service of the clone with this git common dir writes its endpoint file."""
    return git_common_dir / ENDPOINT_DIRECTORY / ENDPOINT_FILE


def _refuse_exposed(file_stat: os.stat_result, directory_stat: os.stat_result) -> None:
    """Refuse a handle that is not a private regular file of this user in a private directory."""
    if not stat.S_ISREG(file_stat.st_mode):
        raise EndpointFileError(EndpointRefusalCode.EXPOSED, "the endpoint file is not a regular file")
    if is_windows():  # an owner-only ACL is the service's duty; Windows exposes no mode bits or uid to check
        return
    if file_stat.st_mode & _PRIVATE_MODE_MASK or directory_stat.st_mode & _PRIVATE_MODE_MASK:
        raise EndpointFileError(EndpointRefusalCode.EXPOSED, "the endpoint file or its directory is readable by other users")
    if file_stat.st_uid != os.getuid():
        raise EndpointFileError(EndpointRefusalCode.EXPOSED, "the endpoint file belongs to another user")


def _open_private(path: Path) -> int:
    """Open the endpoint file once, never following a final symbolic link, or refuse by name."""
    try:
        # Judged on lstat before any open: a FIFO or a device would block the open itself.
        if not stat.S_ISREG(path.lstat().st_mode):
            raise EndpointFileError(EndpointRefusalCode.EXPOSED, "the endpoint file is a symbolic link or not a regular file")
        # O_NONBLOCK: a FIFO swapped in after the lstat opens without blocking and is refused on fstat.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        return os.open(path, flags)
    except FileNotFoundError:
        raise EndpointFileError(EndpointRefusalCode.MISSING, "no write service endpoint file; the service is not running") from None
    except OSError as exc:
        # ELOOP is O_NOFOLLOW meeting a link swapped in after the lstat.
        code = EndpointRefusalCode.EXPOSED if exc.errno == errno.ELOOP else EndpointRefusalCode.MALFORMED
        raise EndpointFileError(code, f"the endpoint file cannot be opened ({exc.strerror or type(exc).__name__})") from None


_UNDECODABLE = object()


def _decode(raw: bytes) -> Any:
    """Parse the endpoint file, refusing outside the handler.

    A decode error carries the whole file text, token included, so the refusal is
    raised after the ``except`` block: it has no ``__cause__`` and no ``__context__``.
    """
    try:
        document: Any = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        # ValueError covers UnicodeDecodeError, JSONDecodeError and an integer past the digit limit;
        # RecursionError a pathologically nested document.
        document = _UNDECODABLE
    if document is _UNDECODABLE:
        raise EndpointFileError(EndpointRefusalCode.MALFORMED, "the endpoint file is not JSON")
    return document


def _load(path: Path) -> dict[str, Any]:
    descriptor = _open_private(path)
    try:
        _refuse_exposed(os.fstat(descriptor), path.parent.lstat())
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            raw = handle.read(ENDPOINT_MAX_BYTES + 1)
    except OSError as exc:
        raise EndpointFileError(EndpointRefusalCode.MALFORMED, f"the endpoint file cannot be read ({exc.strerror or type(exc).__name__})") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > ENDPOINT_MAX_BYTES:
        raise EndpointFileError(EndpointRefusalCode.MALFORMED, "the endpoint file is too large")
    document = _decode(raw)
    if not isinstance(document, dict):
        raise EndpointFileError(EndpointRefusalCode.MALFORMED, "the endpoint file is not a JSON object")
    return document


def _malformed(name: str) -> EndpointFileError:
    return EndpointFileError(EndpointRefusalCode.MALFORMED, f"the endpoint file's {name!r} is missing or invalid")


def _endpoint_from(document: Mapping[str, Any]) -> WriteServiceEndpoint:
    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != ENDPOINT_SCHEMA_VERSION:
        raise _malformed("schema_version")
    host = document.get("host")
    if not isinstance(host, str):
        raise _malformed("host")
    if host != ENDPOINT_HOST:
        raise EndpointFileError(EndpointRefusalCode.NOT_LOOPBACK, f"the endpoint file must name {ENDPOINT_HOST}")
    port = document.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise _malformed("port")
    token = document.get("token")
    if not isinstance(token, str) or len(token) < TOKEN_MIN_LENGTH or not _TOKEN_ALPHABET.fullmatch(token):
        raise _malformed("token")
    instance_id = document.get("instance_id")
    pid = document.get("pid")
    started_at = document.get("started_at")
    versions = document.get("protocol_versions")
    if not isinstance(instance_id, str) or not instance_id:
        raise _malformed("instance_id")
    if not isinstance(pid, int) or isinstance(pid, bool):
        raise _malformed("pid")
    if not isinstance(started_at, str):
        raise _malformed("started_at")
    try:
        protocol_versions = _versions(versions if isinstance(versions, list) else [], "protocol_versions")
    except ProtocolShapeError:
        raise _malformed("protocol_versions") from None
    return WriteServiceEndpoint(host, port, token, instance_id, pid, protocol_versions, started_at)


def read_endpoint_file(path: Path) -> WriteServiceEndpoint:
    """Read the endpoint file, refusing anything that could send a write to the wrong process.

    Every refusal is an :class:`EndpointFileError` with a code; no OS error escapes and no
    refusal chains an exception that could hold the file text.
    """
    return _endpoint_from(_load(path))
