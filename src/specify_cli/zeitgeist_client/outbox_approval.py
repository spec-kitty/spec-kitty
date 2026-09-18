"""Z8-C: the bundled outside-model approval surface for locally queued
Zeitgeist prose (program-graph handle Z8-C, "Bundled outside-model approval
surface", parent Z8 "Human-gated prose outbox").

Z8's own node criterion is the frame this module has to satisfy: "Default-
deny TTL-bounded prose outbox, idempotent receipts, publisher attestation,
and approval outside model context are bundled through Spec Kitty; final
approval is never model-callable or inferred." Z8-Z (a separate Bead, the
``zeitgeist`` repo's own server-side outbox/receipt mechanics) is NOT a
dependency of this node — Z8-C is scoped to the CLIENT surface only:
"Bundle inspect/approve/reject client surface in normal Spec Kitty install,
outside model-callable MCP, with exact disclosure, actor/context/attestation
binding, timeout/revoke, stdout/log redaction, and no separate sidecar/
download." Everything below is in-process inside ``zeitgeist_client`` — the
same package Z1/Z4-C/Z7-C already bundle into the one Spec Kitty wheel; there
is no second package, daemon, or download this module depends on.

THE HARD TRUST REQUIREMENT (read this before touching :func:`approve`/
:func:`reject`/:func:`revoke`): a human's final disposition of queued prose
must be a real, out-of-model gesture, structurally unreachable from any
model, agent, tool, or CLI-automation path. This is enforced by exactly ONE
seam, :func:`_capture_human_gesture`, which every decision function routes
through and NONE of them lets a caller skip:

* It opens the process's controlling terminal directly
  (:func:`_controlling_tty`, ``/dev/tty``) — never ``sys.stdin``/``sys.
  stdout``, which a script, a subprocess an MCP client's own launcher
  spawns, or a piped/redirected CLI invocation fully controls. A process
  with no controlling terminal (the shape of every one of those callers)
  gets ``None`` back, and the decision function raises
  :class:`HumanGestureRequired` before anything is written.
* The human must type back a per-ITEM challenge (the pending item's own
  content-hash prefix) — not a generic "y"/"yes"/enter. This binds the
  gesture to the exact content being decided (actor/context/attestation
  binding: an attestation harvested against one item's challenge cannot
  confirm a different item), and defeats a blind "always answer yes"
  automation that has no idea what the challenge value is.
* :func:`approve`/:func:`reject`/:func:`revoke` take exactly ``(item_id,
  *, actor)`` — no ``attestation=``/``force=``/``yes=``/``skip_confirmation=``
  parameter exists anywhere on the public surface for a caller to inject a
  fabricated gesture or ask to skip capturing a real one. This module also
  never reads any environment variable (see
  ``test_outbox_approval_module_never_reads_os_environ``) — there is no
  ``SPEC_KITTY_..._AUTO_APPROVE``-shaped knob to set.
* :mod:`mcp_stdio` (Z7-C's stdio MCP adapter) exposes exactly
  ``zeitgeist_status``/``zeitgeist_watch`` and imports nothing from this
  module — a model talking to Spec Kitty over MCP has structurally no tool
  that reaches ``approve``/``reject``/``revoke`` at all (see
  ``test_mcp_server_exposes_no_outbox_approval_tool``).

EXACT DISCLOSURE / STDOUT-LOG REDACTION. The full, verbatim pending content
is shown to the human in exactly two places: :func:`show` (an explicit,
per-id inspect call a human asked for by name) and the confirmation prompt
:func:`_capture_human_gesture` writes DIRECTLY to the controlling terminal
device — never through ``sys.stdout``/``print``/a logger. Anything that
flows through this process's own stdout or a log file (:func:`list_pending`,
:func:`redacted_preview`) sees only a bounded, truncated preview, never the
exact prose — so a shell-history capture, a CI log, or a piped ``list``
output can never leak the full content of something still awaiting a human
disposition.

CONTENT-ADDRESSED, IDEMPOTENT. A pending item's ``item_id`` is a SHA-256
digest over its own (repo, audience, content, context) — resubmitting
identical content is a no-op (returns the existing item, never restarts its
TTL clock and never duplicates it: see :func:`submit`). A decision's
``receipt_id`` is a SHA-256 digest over (item_id, decision, actor,
decided_at); retrying an already-recorded decision (crash-then-retry, or a
caller simply calling ``approve()`` twice) returns the SAME receipt without
requiring a second human gesture — genuine idempotency, not merely
"harmless to call again" (see
``test_approving_an_already_approved_item_again_returns_the_same_receipt_
without_a_new_gesture``). Flipping to a DIFFERENT decision than the one
already recorded is refused (:class:`ConflictingDecision`) — a decision, once
made, is never silently overridden.

TTL / DEFAULT-DENY / REVOKE. Every submitted item carries an expiry
(:data:`DEFAULT_TTL_S`, clamped to :data:`MAX_TTL_S` — never "forever"). Past
that instant a pending item is swept to ``"expired"`` and can never be
approved (:class:`Expired`, fail-closed — this is the "default-deny" half of
Z8's own criterion: silence is never approval). An already-approved item can
still be pulled back before whatever consumes it acts, via :func:`revoke`
(also human-gesture-gated) — the timeout and revoke halves of Z8-C's own
node criterion.

Storage: one local JSON file, ``<runtime_state_root>/zeitgeist-outbox.json``
(``kernel.paths.get_runtime_state_root()``), lock-guarded via
``kernel.locks.machine_file_lock`` (migrated off ``filelock`` by mission
cross-os-primitive-unification WP05/#4714) — a sibling of, deliberately not
sharing, ``credentials.py``'s ``zeitgeist-credentials`` file (same "own
file, not shared" reasoning that module's docstring gives for not reusing
``tracker/credentials.py``). Local-first: no network call anywhere in this
module.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

from kernel.clock import datetime, now_utc, parse_iso, timedelta
from kernel.locks import machine_file_lock
from kernel.paths import get_runtime_state_root

OUTBOX_FILENAME = "zeitgeist-outbox.json"
_LOCK_SUFFIX = ".lock"

#: Default pending-approval window. Deliberately short — a queued item is
#: meant to be looked at soon, not to sit around indefinitely.
DEFAULT_TTL_S: float = 15 * 60.0

#: Absolute ceiling no caller-supplied ``ttl_s`` can exceed. "Bounded", per
#: Z8's own criterion, is a hard clamp enforced here regardless of what a
#: caller asks for — never a longer-than-requested wait dressed up as still
#: pending.
MAX_TTL_S: float = 24 * 60 * 60.0

#: How much of a challenge/content-hash prefix is shown/typed back. Long
#: enough that a blind guess is not viable, short enough to type by hand.
_CHALLENGE_LEN = 8

#: :func:`redacted_preview`'s bound — see the module docstring's "stdout/log
#: redaction" note.
_REDACTED_PREVIEW_LEN = 40

_PENDING = "pending"
_APPROVED = "approved"
_REJECTED = "rejected"
_EXPIRED = "expired"
_REVOKED = "revoked"
_TERMINAL_DECISIONS = frozenset({_APPROVED, _REJECTED, _REVOKED})


class OutboxError(Exception):
    """Base class for every fault this module raises."""


class NotFound(OutboxError):
    def __init__(self, item_id: str) -> None:
        super().__init__(f"no item {item_id!r} in the local prose outbox")
        self.item_id = item_id


class Expired(OutboxError):
    def __init__(self, item_id: str) -> None:
        super().__init__(f"item {item_id!r} expired before a human disposition arrived; fails closed, never approvable after its TTL — default-deny")
        self.item_id = item_id


class ConflictingDecision(OutboxError):
    def __init__(self, item_id: str, existing: str, attempted: str) -> None:
        super().__init__(f"item {item_id!r} was already decided {existing!r}; refusing to flip it to {attempted!r}")
        self.item_id = item_id
        self.existing = existing
        self.attempted = attempted


class InvalidTransition(OutboxError):
    def __init__(self, item_id: str, status: str, action: str) -> None:
        super().__init__(f"cannot {action} item {item_id!r}: it is {status!r}, not a valid starting state for {action}")
        self.item_id = item_id


class HumanGestureRequired(OutboxError):
    """A decision could not be bound to a real, out-of-model human gesture.
    See the module docstring's "hard trust requirement" section — this is
    the one seam every decision path fails closed through."""


@dataclasses.dataclass(frozen=True)
class PendingItem:
    item_id: str
    repo: str
    audience: str
    content: str
    context: dict[str, Any]
    created_at: str
    expires_at: str
    status: str


@dataclasses.dataclass(frozen=True)
class Receipt:
    receipt_id: str
    item_id: str
    decision: str
    actor: str
    decided_at: str
    attestation: dict[str, Any]


class _TTY(Protocol):
    def write(self, text: str) -> int: ...
    def flush(self) -> None: ...
    def readline(self) -> str: ...
    def close(self) -> None: ...


# --- time / hashing primitives ----------------------------------------------


def _now() -> datetime:
    return now_utc()


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _content_hash(*, repo: str, audience: str, content: str, context: Mapping[str, Any]) -> str:
    canon = _canonical_json({"repo": repo, "audience": audience, "content": content, "context": dict(context)})
    # Content-addressed item identity, not a charter evidence hash — a
    # file/record-integrity digest, exactly TID251's declared exception.
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()  # noqa: TID251


def _receipt_hash(*, item_id: str, decision: str, actor: str, decided_at: str) -> str:
    canon = _canonical_json({"item_id": item_id, "decision": decision, "actor": actor, "decided_at": decided_at})
    # Content-addressed receipt identity — see _content_hash's note above.
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()  # noqa: TID251


def redacted_preview(content: str) -> str:
    """A bounded-length preview safe for stdout/log output — never the exact
    prose. See the module docstring's "exact disclosure / stdout-log
    redaction" section for where full content IS shown instead."""
    if len(content) <= _REDACTED_PREVIEW_LEN:
        return content
    return content[:_REDACTED_PREVIEW_LEN] + "…"


# --- storage -------------------------------------------------------------


def _store_path() -> Path:
    return get_runtime_state_root() / OUTBOX_FILENAME


def _lock_path() -> Path:
    path = _store_path()
    return path.with_suffix(path.suffix + _LOCK_SUFFIX)


def _empty_store() -> dict[str, Any]:
    return {"items": {}, "receipts": {}}


def _read_all() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _empty_store()
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt/unreadable store is treated as empty, matching
        # credentials.py's precedent — a read fault must never crash a
        # caller that only wants to know "is anything pending".
        return _empty_store()
    data.setdefault("items", {})
    data.setdefault("receipts", {})
    return data


def _write_all(data: Mapping[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)  # atomic on POSIX and Windows (same volume)


def _sweep_expired(data: dict[str, Any]) -> bool:
    changed = False
    now = _now()
    for row in data["items"].values():
        if row["status"] == _PENDING and parse_iso(row["expires_at"]) <= now:
            row["status"] = _EXPIRED
            changed = True
    return changed


def _item_from_row(item_id: str, row: Mapping[str, Any]) -> PendingItem:
    return PendingItem(
        item_id=item_id,
        repo=row["repo"],
        audience=row["audience"],
        content=row["content"],
        context=dict(row["context"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        status=row["status"],
    )


def _receipt_from_row(receipt_id: str, row: Mapping[str, Any]) -> Receipt:
    return Receipt(
        receipt_id=receipt_id,
        item_id=row["item_id"],
        decision=row["decision"],
        actor=row["actor"],
        decided_at=row["decided_at"],
        attestation=dict(row["attestation"]),
    )


def _find_receipt_id(data: Mapping[str, Any], *, item_id: str, decision: str) -> str | None:
    receipts = cast("dict[str, dict[str, Any]]", data["receipts"])
    for receipt_id, row in receipts.items():
        if row["item_id"] == item_id and row["decision"] == decision:
            return receipt_id
    return None


# --- submit / inspect --------------------------------------------------------


def submit(
    *,
    repo: str,
    audience: str,
    content: str,
    context: Mapping[str, Any] | None = None,
    ttl_s: float = DEFAULT_TTL_S,
) -> PendingItem:
    """Queue ``content`` for human disposition. Content-addressed and
    idempotent: resubmitting byte-identical (repo, audience, content,
    context) while the earlier submission is still pending returns that SAME
    pending item unchanged (its TTL clock is never restarted by a retry). If
    that content was already decided, the decision stands — the same content
    cannot be silently re-queued for a second chance at a different verdict.
    """
    if not repo:
        raise ValueError("repo must be non-empty")
    if not audience:
        raise ValueError("audience must be non-empty")
    if not content:
        raise ValueError("content must be non-empty")
    if ttl_s <= 0:
        raise ValueError("ttl_s must be > 0")
    ctx = dict(context or {})
    item_id = _content_hash(repo=repo, audience=audience, content=content, context=ctx)
    bounded_ttl_s = min(float(ttl_s), MAX_TTL_S)

    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)
    with lock:
        data = _read_all()
        _sweep_expired(data)
        existing = data["items"].get(item_id)
        if existing is not None:
            return _item_from_row(item_id, existing)
        now = _now()
        row = {
            "repo": repo,
            "audience": audience,
            "content": content,
            "context": ctx,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=bounded_ttl_s)),
            "status": _PENDING,
        }
        data["items"][item_id] = row
        _write_all(data)
        return _item_from_row(item_id, row)


def list_pending(*, repo: str | None = None) -> list[PendingItem]:
    """Every item still awaiting a human disposition, oldest first. Never
    shows the exact content in a form meant for ambient stdout/log output —
    callers that render this list should use :func:`redacted_preview` on
    ``.content``, not print it verbatim (the CLI layer does exactly that)."""
    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)
    with lock:
        data = _read_all()
        if _sweep_expired(data):
            _write_all(data)
        rows = [(item_id, row) for item_id, row in data["items"].items() if row["status"] == _PENDING]
    items = [_item_from_row(item_id, row) for item_id, row in rows]
    if repo is not None:
        items = [item for item in items if item.repo == repo]
    items.sort(key=lambda item: item.created_at)
    return items


_ALL_STATUSES: tuple[str, ...] = (_PENDING, _APPROVED, _REJECTED, _EXPIRED, _REVOKED)


def status_counts(*, repo: str | None = None) -> dict[str, int]:
    """Counts of items by status, optionally scoped to ``repo`` — never
    content (O1-C's operability report's "revoke" signal reads this, not
    :func:`list_pending`, so a signal built purely from aggregate counts can
    never carry even a redacted preview). Sweeps expired items first, same
    as :func:`list_pending`/:func:`show`, so the counts are current."""
    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)
    with lock:
        data = _read_all()
        if _sweep_expired(data):
            _write_all(data)
        rows = list(data["items"].values())
    counts = dict.fromkeys(_ALL_STATUSES, 0)
    for row in rows:
        if repo is not None and row["repo"] != repo:
            continue
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def show(item_id: str) -> PendingItem:
    """The exact full record for ``item_id``, in any status — an explicit,
    per-id inspect action the caller named by hash. This is one of the two
    places this module discloses exact content (see the module docstring)."""
    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)
    with lock:
        data = _read_all()
        if _sweep_expired(data):
            _write_all(data)
        row = data["items"].get(item_id)
    if row is None:
        raise NotFound(item_id)
    return _item_from_row(item_id, row)


def get_receipt(item_id: str) -> Receipt | None:
    """The receipt recording ``item_id``'s current decision, if any."""
    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)
    with lock:
        data = _read_all()
        row = data["items"].get(item_id)
        if row is None:
            raise NotFound(item_id)
        status = row["status"]
        if status not in _TERMINAL_DECISIONS:
            return None
        receipt_id = _find_receipt_id(data, item_id=item_id, decision=status)
        if receipt_id is None:
            return None
        return _receipt_from_row(receipt_id, data["receipts"][receipt_id])


# --- the human-gesture seam ---------------------------------------------------


def _controlling_tty() -> _TTY | None:
    """Open the process's controlling terminal directly — never
    ``sys.stdin``/``sys.stdout``. Returns ``None`` (never raises) whenever
    there is none: a piped script, a subprocess an MCP client's own launcher
    spawns, a CI job, or any other non-interactive caller. See the module
    docstring's "hard trust requirement" section — this is the ONE structural
    gate every decision path routes through, and there is deliberately no
    parameter or environment variable anywhere in this module that
    substitutes for a real open of this device."""
    try:
        return open("/dev/tty", "r+", encoding="utf-8", buffering=1)  # noqa: SIM115 - closed by the caller, not a context manager here
    except OSError:
        return None


def _capture_human_gesture(*, item: PendingItem, decision: str, actor: str) -> dict[str, Any]:
    tty = _controlling_tty()
    if tty is None:
        raise HumanGestureRequired(
            f"cannot {decision} item {item.item_id!r}: no controlling terminal is available. "
            "This decision requires a human typing at a real terminal — not a script, a pipe, "
            "an MCP tool call, or a CI job."
        )
    challenge = item.item_id[:_CHALLENGE_LEN]
    try:
        tty.write(
            "\n--- Zeitgeist prose outbox: human disposition required ---\n"
            f"item id     : {item.item_id}\n"
            f"repo        : {item.repo}\n"
            f"audience    : {item.audience}\n"
            f"context     : {_canonical_json(item.context)}\n"
            f"decision    : {decision}\n"
            f"actor       : {actor}\n"
            "\nEXACT CONTENT (verbatim, nothing paraphrased or summarized):\n"
            "-----8<-----\n"
            f"{item.content}\n"
            "----->8-----\n"
            f"\nType the challenge below to {decision} this item — anything else cancels:\n"
            f"  {challenge}\n> "
        )
        tty.flush()
        typed = tty.readline().strip()
    finally:
        tty.close()
    if typed != challenge:
        raise HumanGestureRequired(f"confirmation phrase for item {item.item_id!r} did not match; {decision} refused")
    return {
        "source": "controlling_tty",
        "tty_device": "/dev/tty",
        "item_id": item.item_id,
        "challenge": challenge,
        "confirmed": True,
    }


# --- decide: approve / reject / revoke ---------------------------------------


def _validate_transition(row: Mapping[str, Any], *, item_id: str, decision: str) -> None:
    """Called only when ``row["status"] != decision`` — the idempotent
    same-decision-already-recorded retry short-circuits in :func:`_decide`
    before this runs."""
    status = row["status"]
    if status == _EXPIRED:
        raise Expired(item_id)
    if decision == _REVOKED:
        if status != _APPROVED:
            raise InvalidTransition(item_id, status, "revoke")
        return
    # decision in {approved, rejected}, status != decision already ruled out
    if status != _PENDING:
        raise ConflictingDecision(item_id, status, decision)


def _decide(item_id: str, *, decision: str, actor: str) -> Receipt:
    if not actor:
        raise ValueError("actor must be non-empty")
    lock = machine_file_lock(_lock_path(), blocking=True, timeout_s=None)

    with lock:
        data = _read_all()
        _sweep_expired(data)
        row = data["items"].get(item_id)
        if row is None:
            raise NotFound(item_id)
        if row["status"] == decision:
            # Idempotent retry of an already-recorded decision: return the
            # existing receipt, never a second human gesture (crash-safe
            # retry — see the module docstring). Checked BEFORE transition
            # validation so e.g. a second revoke() on an already-revoked
            # item (status == "revoked", not "approved") short-circuits here
            # rather than hitting _validate_transition's "must be approved"
            # guard.
            receipt_id = _find_receipt_id(data, item_id=item_id, decision=decision)
            assert receipt_id is not None  # a decided item always has a receipt
            return _receipt_from_row(receipt_id, data["receipts"][receipt_id])
        _validate_transition(row, item_id=item_id, decision=decision)
        starting_status = row["status"]
        item = _item_from_row(item_id, row)

    # Interactive I/O happens OUTSIDE the lock — a human taking their time to
    # read and type must never block other processes' reads/writes.
    attestation = _capture_human_gesture(item=item, decision=decision, actor=actor)
    decided_at = _iso(_now())
    receipt_id = _receipt_hash(item_id=item_id, decision=decision, actor=actor, decided_at=decided_at)

    with lock:
        data = _read_all()
        row = data["items"].get(item_id)
        if row is None:
            raise NotFound(item_id)
        if row["status"] != starting_status:
            # Lost a race with another decider between the two lock windows.
            raise ConflictingDecision(item_id, row["status"], decision)
        row["status"] = decision
        row["decided_at"] = decided_at
        row["decided_by"] = actor
        data["items"][item_id] = row
        receipt_row = {
            "item_id": item_id,
            "decision": decision,
            "actor": actor,
            "decided_at": decided_at,
            "attestation": attestation,
        }
        data["receipts"][receipt_id] = receipt_row
        _write_all(data)
        return _receipt_from_row(receipt_id, receipt_row)


def approve(item_id: str, *, actor: str) -> Receipt:
    """Approve ``item_id``. Requires a real human gesture at the controlling
    terminal (see the module docstring) — there is no parameter here to
    supply or skip that."""
    return _decide(item_id, decision=_APPROVED, actor=actor)


def reject(item_id: str, *, actor: str) -> Receipt:
    """Reject ``item_id``. Same human-gesture requirement as :func:`approve`."""
    return _decide(item_id, decision=_REJECTED, actor=actor)


def revoke(item_id: str, *, actor: str) -> Receipt:
    """Pull back an already-approved ``item_id`` before whatever consumes it
    acts on that approval. Only valid from ``"approved"``; same human-gesture
    requirement as :func:`approve`."""
    return _decide(item_id, decision=_REVOKED, actor=actor)
