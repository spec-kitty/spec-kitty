"""Migration engine: backfill runtime state into the event log + fail-closed verify.

Realises **IC-03** (per-field backfill + fail-closed verify) and gates the reader
cutover for every downstream field vertical (WP05-WP09). The pinned migration
order this module implements the *first two steps* of is::

    backfill -> verify(pre-strip, FAIL-CLOSED) -> reader cutover -> writer cutover
             -> strip mutable fields -> delete fallbacks -> land hash guard

This WP owns **backfill + verify + the ``MUTABLE_FIELDS`` field-moves** only. It
does **not** perform reader/writer cutover (the field verticals do) and does
**not** delete the legacy fallbacks (WP10 does, gated on this backfill).

Backfill (:func:`backfill_runtime_state`)
    For every WP in the live corpus, reconstruct the frontmatter/checkbox runtime
    state that is about to be stripped into seed events:

    - the **claim** state (``shell_pid`` / ``shell_pid_created_at`` / ``agent``)
      rides a seed ``planned -> claimed`` :class:`StatusEvent` whose
      ``policy_metadata`` sidecar the WP01 reducer folds into the snapshot slots
      (FR-004 claim path);
    - ``assignee`` / ``tracker_refs`` / subtask completion / ``review`` ride seed
      :class:`InnerStateChanged` annotations with a typed :class:`WPInnerStateDelta`.

    Every seed ``event_id`` is a **deterministic namespaced ULID**
    (``mission_id + wp_id + field``), so a re-run mints byte-identical ids and the
    idempotency check (skip an id already on disk) makes a second run seed nothing
    (NFR-002). When a WP already has transition or annotation history, every
    seed timestamp is clamped strictly below its earliest raw ``(at, event_id)``
    key. With no history, the existing claimed/synthesized anchor remains the
    deterministic fallback.

    **Claim-anchor synthesis (#2848).** The ``claimed`` timestamp a WP's other
    seeds clamp to normally comes from the event log (:func:`_claim_anchors`).
    When that log is missing or truncated but the WP's frontmatter still carries
    real claim state (``agent`` / ``shell_pid`` / ``shell_pid_created_at``),
    treating the WP as "never claimed" would silently drop that data (the pre-fix
    behavior: :func:`verify_backfill` returned a vacuous ``ok=True, wp_count=0``
    and the mission still flipped to snapshot authority with an empty runtime).
    :func:`_resolve_anchor` instead synthesizes a deterministic anchor from the
    frontmatter itself (``shell_pid_created_at``, falling back to the mission's
    ``meta.json`` ``created_at``) so the claim is seeded and recoverable via
    :func:`~specify_cli.status.wp_view.reconstruct_wp_view`. A WP with no claim
    fields at all (or claim fields but no honest timestamp anywhere to anchor
    them to) remains genuinely never-claimed and is skipped, as before.

    NOTE on the emit seam: the public :func:`~specify_cli.status.emit.emit_inner_state_changed`
    mints a *random* ULID, which cannot satisfy the deterministic-idempotent seed
    contract. The backfill therefore reuses the exact internals that API is built
    on — the sanctioned ``wp_state.annotate()`` non-transition seam plus the
    durability-verified store append (:func:`append_event_stream_atomic_verified`)
    — but supplies its own deterministic ``event_id``. The seeds are ordinary
    WP01 events: the reducer folds them into the snapshot with no special-casing.

Verify (:func:`verify_backfill`) — **fail-closed**
    Asserts every value produced by the OLD frontmatter/checkbox reader exists in
    its deterministic seed row, independently witnesses all three claim-borne
    slots, and requires an exact compatibility repair when a persisted pre-floor
    seed corrupts current state. Legitimate later events remain authoritative.
    The proof reads the **un-stripped** frontmatter:
    :func:`strip_mutable_fields` MUST NOT run before verify. The verifier also
    checks WP/count integrity, rejects corrupt deterministic seed rows, and raises
    :class:`MigrationOrderingError`. Any mismatch, ordering violation, or corrupt
    seed **aborts before reader cutover** — never a warning.

Honesty bound (no-data-loss)
    "No data loss" is asserted against deterministic seed-row payload parity and
    WP/count integrity, **not** temporal fidelity: backfilled subtask-completion
    timestamps are historical ordering anchors, seed ULIDs are content-namespaced
    (not chronological), and a later legitimate annotation may supersede a seed.
    The contract holds only because **no consumer reads subtask-completion time or
    relies on seed-ULID chronological order** — this is asserted as an explicit
    precondition in the test-suite.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from kernel.clock import UTC, datetime, timedelta, parse_iso, from_epoch
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from specify_cli.core.owned_mission import OwnedMission

from specify_cli.core.checkout_identity import (
    FailClosedRefusal,
    Intent,
    resolve_checkout_identity,
)
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.core.subtask_rows import iter_wp_section_subtask_rows
from specify_cli.core.utils import ensure_within_any
from specify_cli.mission_metadata import load_meta
from specify_cli.status import (
    EventStream,
    InnerStateChanged,
    Lane,
    ReviewOverride,
    Status,
    StatusEvent,
    StoreError,
    WPInnerStateDelta,
    annotate,
    feature_status_lock,
    materialize_snapshot,
    read_event_stream,
    reduce,
)
from specify_cli.status._unsafe import append_event_stream_atomic_verified
from specify_cli.workspace import canonicalize_feature_dir
from specify_cli.workspace.root_resolver import resolve_status_lock_root

from .mission_state import deterministic_ulid

logger = logging.getLogger(__name__)

#: Actor recorded on seed events (migration provenance, not a live agent).
BACKFILL_ACTOR = "migration:backfill_runtime_state"

#: Distinct provenance for append-only repairs of persisted pre-floor seeds.
COMPATIBILITY_REPAIR_ACTOR = f"{BACKFILL_ACTOR}:compatibility"

#: Smallest timestamp movement the ISO event format can express deterministically.
_ORDERING_TICK = timedelta(microseconds=1)

#: Snapshot slots the seed ``planned -> claimed`` carrier populates via its
#: ``policy_metadata`` sidecar, and which :func:`verify_backfill` independently
#: witnesses. Kept in one place so the builder (:func:`_unmigrated_claim_slots`),
#: the already-migrated probe (:func:`_snapshot_claim_slots`) and the witness
#: denominator (:func:`_claim_witness_denominator`) can never drift apart.
_CLAIM_SLOTS = ("shell_pid", "shell_pid_created_at", "agent")

#: Seed-owned snapshot slots a compatibility annotation can restore.
_SEED_RUNTIME_SLOTS = (
    "shell_pid",
    "shell_pid_created_at",
    "agent",
    "assignee",
    "tracker_refs",
    "subtasks",
    "review",
)

#: The concrete ``review_artifact_override_*`` frontmatter keys the write half
#: (``tasks_materialization._persist_review_artifact_override``) emits. Enumerated
#: — never glob-guessed — and consumed by both the legacy reader here and the
#: ``strip_frontmatter.MUTABLE_FIELDS`` extension.
_REVIEW_OVERRIDE_KEYS = (
    "review_artifact_override_at",
    "review_artifact_override_actor",
    "review_artifact_override_wp_id",
    "review_artifact_override_reason",
)

#: Snapshot runtime slots sourced from WP *frontmatter* (not from tasks.md
#: checkboxes). The ordering guard keys on these: a snapshot slot present here
#: whose frontmatter key has already been stripped proves a strip-before-verify.
_FRONTMATTER_SOURCED_SLOTS = ("shell_pid", "shell_pid_created_at", "agent", "assignee", "tracker_refs", "review")

BackfillAction = Literal["wrote", "skip", "error"]


class BackfillVerificationError(RuntimeError):
    """Fail-closed abort: the reduced snapshot did not match the OLD reader.

    Raised by :func:`run_backfill_and_verify` when :func:`verify_backfill`
    reports a count/value mismatch (including a fault-injected corrupt seed).
    This is terminal — the caller MUST NOT advance to reader cutover.
    """


class MigrationOrderingError(RuntimeError):
    """Fail-closed abort: verify was asked to run against stripped frontmatter.

    The pinned order is ``backfill -> verify(pre-strip) -> cutover -> strip``.
    If :func:`strip_mutable_fields` has already removed a frontmatter key whose
    value the snapshot still carries, the OLD reader would read empty and yield a
    vacuous false green. Detecting that is itself fail-closed.
    """


class LegacyRuntimeReadError(RuntimeError):
    """Fail-closed abort: a WP artifact cannot be parsed for migration."""


@dataclass(frozen=True)
class LegacyWPRuntime:
    """Pre-eviction runtime state reconstructed from ONE WP's legacy read path.

    This is the OLD frontmatter/checkbox reader's per-WP view — the ground truth
    :func:`verify_backfill` compares the reduced snapshot against.
    """

    wp_id: str
    shell_pid: int | None = None
    shell_pid_created_at: str | None = None
    agent: str | None = None
    assignee: str | None = None
    tracker_refs: tuple[str, ...] = ()
    #: subtask-id -> completion status (``Lane.DONE`` / ``Lane.PLANNED``).
    subtasks: dict[str, Status] = field(default_factory=dict)
    review: ReviewOverride | None = None
    #: Frontmatter keys actually present on disk (drives the ordering guard).
    frontmatter_keys: frozenset[str] = frozenset()

    def has_evictable_state(self) -> bool:
        """True when this WP carries any runtime state that must be seeded."""
        return bool(
            self.shell_pid is not None
            or self.shell_pid_created_at is not None
            or self.agent is not None
            or self.assignee is not None
            or self.tracker_refs
            or self.subtasks
            or (self.review is not None and self.review.complete)
        )

    def has_claim_state(self) -> bool:
        """True when frontmatter carries claim state (``agent``/``shell_pid``/``shell_pid_created_at``).

        Distinct from :meth:`has_evictable_state`: a WP can carry non-claim
        runtime state (``assignee``/``tracker_refs``/``subtasks``) with no claim
        at all. This narrower predicate drives claim-anchor synthesis (a
        never-claimed WP must not get a fabricated claim just because it has an
        assignee) — see :func:`_resolve_anchor`.
        """
        return self.shell_pid is not None or self.shell_pid_created_at is not None or self.agent is not None

@dataclass
class BackfillResult:
    """Per-mission result from :func:`backfill_runtime_state`.

    Attributes:
        feature_dir: Absolute path to the mission directory.
        slug: Directory name used as the mission slug.
        action: ``"wrote"`` — one or more seeds appended; ``"skip"`` — nothing to
            seed or already fully seeded (idempotent no-op); ``"error"`` — an
            unrecoverable per-mission error.
        seeded_count: Number of NEW seed or compatibility-repair events appended
            this run (0 on a converged re-run).
        reason: Human-readable explanation (populated on ``"skip"``/``"error"``).
        warnings: Non-fatal per-WP warnings (e.g. a never-claimed WP skipped, or a
            claim anchor synthesized from frontmatter — #2848).
    """

    feature_dir: Path
    slug: str
    action: BackfillAction
    seeded_count: int = 0
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerifyResult:
    """Fail-closed result of :func:`verify_backfill`.

    ``ok`` is True only when every legacy-derived deterministic seed is present
    with its exact payload and the WP/count integrity guards pass.
    ``mismatches`` carries a human-readable line per divergence for diagnostics;
    the runner treats any non-``ok`` result as a terminal abort (no reader
    cutover).
    """

    ok: bool
    wp_count: int
    mismatches: tuple[str, ...] = ()

    def raise_if_failed(self) -> None:
        """Raise :class:`BackfillVerificationError` unless verify passed."""
        if not self.ok:
            raise BackfillVerificationError(
                "backfill verify failed (fail-closed; no reader cutover): "
                + "; ".join(self.mismatches)
            )


# ---------------------------------------------------------------------------
# Deterministic seed identity
# ---------------------------------------------------------------------------


def _mission_id(read_dir: Path) -> str:
    """Return the canonical ``mission_id`` (ULID) or fall back to the slug.

    The mission_id is the deterministic-ULID namespace root. A legacy mission
    without a minted ``mission_id`` degrades to its directory name — still stable
    per corpus, which is all the seed determinism requires.

    *read_dir* is the canonical PRIMARY leg (NFR-004 / R5) — mirrors
    :func:`_synthesize_claim_anchor`'s pinned leg (#2966 part-1). ``meta.json``
    (``PRIMARY_METADATA``) lives only on the PRIMARY leg; a caller seeding
    events into a distinct COORD-partition directory (``feature_dir`` in
    :func:`backfill_runtime_state`) must never have this read its COORD leg's
    own ``meta.json`` — that leg typically carries none at all, which used to
    silently degrade every seed id to the COORD *directory name* instead of
    the mission's real ULID (and left the written event's own ``mission_id``
    field ``None``, since it then equalled the mission slug).
    """
    meta = load_meta(read_dir, allow_missing=True, on_malformed="none")
    if meta is not None:
        raw = meta.get("mission_id")
        if raw:
            return str(raw)
    return read_dir.name


def _seed_id(mission_id: str, wp_id: str, field_name: str) -> str:
    """Return the deterministic namespaced seed ULID for one (wp, field).

    Namespaced on ``mission_id | wp_id | field`` (``|`` separator, matching the
    ``rebuild_state._deterministic_id`` precedent) so the same corpus mints
    byte-identical ids across runs (idempotency) and each field vertical gets a
    distinct, collision-free id.
    """
    return str(deterministic_ulid(f"{mission_id}|{wp_id}|{field_name}"))


def _repair_id(mission_id: str, wp_id: str, repair_kind: str) -> str:
    """Return a deterministic ID in the append-only compatibility namespace."""
    return str(
        deterministic_ulid(
            f"{mission_id}|{wp_id}|compatibility-repair-v1|{repair_kind}"
        )
    )


def _is_migration_actor(actor: object) -> bool:
    """True for both ordinary seeds and compatibility repair events."""
    return actor in (BACKFILL_ACTOR, COMPATIBILITY_REPAIR_ACTOR)


def _parse_ordering_timestamp(raw: str, *, wp_id: str) -> datetime:
    """Parse an event timestamp used to derive a strict ordering neighbour."""
    try:
        parsed = parse_iso(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MigrationOrderingError(
            f"{wp_id}: cannot represent a strict seed history floor below "
            f"malformed event timestamp {raw!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise MigrationOrderingError(
            f"{wp_id}: cannot represent a strict seed history floor below "
            f"timezone-naive event timestamp {raw!r}"
        )
    return parsed


def _encode_ordering_timestamp(shifted: datetime, like: str) -> str:
    """Render *shifted* with the same UTC designator *like* carries.

    Preserving the designator is load-bearing, not cosmetic:
    :func:`~specify_cli.status.reducer.reduce` folds on the RAW ``(at, event_id)``
    string tuple, so every ordering guard here compares ISO strings *lexically*.
    ``datetime.isoformat`` always emits ``+00:00``; mixing that into a
    ``Z``-encoded log makes the comparison meaningless.
    """
    encoded = shifted.isoformat()
    if like.endswith("Z") and encoded.endswith("+00:00"):
        return encoded[: -len("+00:00")] + "Z"
    return encoded


def _shift_ordering_timestamp(
    raw: str,
    *,
    wp_id: str,
    direction: Literal["before", "after"],
) -> str:
    """Move *raw* in *direction* far enough to also sort that way, failing closed.

    The postcondition is *lexical*, because the reducer's fold key is the raw
    string (see :func:`_encode_ordering_timestamp`). One microsecond satisfies it
    for ``+00:00`` stamps in both directions, but NOT for a whole-second ``Z``
    stamp shifted forward: ``'2026-01-02T04:00:00Z'`` is the lexical MAXIMUM of
    every ISO rendering of an instant inside that second, since the only
    characters ISO-8601 allows after the seconds digits are ``'.'`` (0x2E),
    ``'+'`` (0x2B) and ``'-'`` (0x2D) — all below ``'Z'`` (0x5A). No sub-second
    tick can climb above it, so the shift escalates to the neighbouring whole
    second, which differs at or left of the seconds field and therefore dominates
    any suffix. Both operands then render fraction-free, making lexical and
    chronological order agree again.

    Before this, ``_compatibility_repair_at`` aborted the whole cutover with
    :class:`MigrationOrderingError` on every ``Z``-encoded corpus mission — the
    guard was right and the encoding was wrong.
    """
    parsed = _parse_ordering_timestamp(raw, wp_id=wp_id)
    sign = -1 if direction == "before" else 1
    try:
        encoded = _encode_ordering_timestamp(parsed + sign * _ORDERING_TICK, raw)
        if (encoded < raw) is not (direction == "before"):
            encoded = _encode_ordering_timestamp(
                parsed.replace(microsecond=0) + sign * timedelta(seconds=1),
                raw,
            )
    except OverflowError as exc:
        raise MigrationOrderingError(
            f"{wp_id}: cannot represent a strict seed history floor {direction} "
            f"event timestamp {raw!r}"
        ) from exc
    return encoded


def _combined_events(
    transitions: list[StatusEvent],
    annotations: list[InnerStateChanged],
) -> tuple[StatusEvent | InnerStateChanged, ...]:
    """Splice a transitions list and an annotations list into one typed sequence.

    ``(*transitions, *annotations)`` inline at a call site makes mypy infer the
    *join* of ``StatusEvent`` and ``InnerStateChanged`` for the resulting
    tuple's element type. The two dataclasses share no base other than
    ``object``, so the join — and therefore every element mypy sees pulled
    from that tuple — degrades to ``object``, which then cascades into
    "object has no attribute ..." errors at every read site downstream. Typing
    the return here once pins the true ``StatusEvent | InnerStateChanged``
    union at the single point the two streams are combined.
    """
    return (*transitions, *annotations)


def _wp_events(
    stream: EventStream,
    wp_id: str,
    *,
    include_seeds: bool,
) -> list[StatusEvent | InnerStateChanged]:
    """Return *wp_id* events with this module's own rows filtered out.

    Compatibility-repair rows are ALWAYS dropped: both callers derive a position
    relative to pre-repair history, so letting an already-persisted repair row
    into the input would make the answer drift on every re-run.

    *include_seeds* selects what else survives:

    ``True``
        Keep :data:`BACKFILL_ACTOR` seed rows — the "history the repair must land
        after" for :func:`_compatibility_repair_at`, which exists precisely to
        supersede a persisted seed.
    ``False``
        Drop every migration row, seeds included — the AUTHENTIC-only history
        :func:`_wp_history_floor` needs so repeated invocations derive the same
        floor.
    """
    events: list[StatusEvent | InnerStateChanged] = [
        event
        for event in _combined_events(stream.transitions, stream.annotations)
        if event.wp_id == wp_id
    ]
    if include_seeds:
        return [
            event
            for event in events
            if event.actor != COMPATIBILITY_REPAIR_ACTOR
        ]
    return [event for event in events if not _is_migration_actor(event.actor)]


def _wp_history_floor(stream: EventStream, wp_id: str) -> str | None:
    """Return a timestamp strictly below all legitimate history for *wp_id*.

    Migration rows are excluded so repeated invocations derive the same floor.
    The final raw-key assertion intentionally mirrors the reducer's exact
    ``(at, event_id)`` comparison instead of assuming chronological parsing and
    lexical ordering are interchangeable.
    """
    history = _wp_events(stream, wp_id, include_seeds=False)
    if not history:
        return None
    history_keys = [(event.at, event.event_id) for event in history]
    for event in history:
        _parse_ordering_timestamp(event.at, wp_id=wp_id)
    earliest_at = min(history_keys)[0]
    floor = _shift_ordering_timestamp(
        earliest_at,
        wp_id=wp_id,
        direction="before",
    )
    if not all((floor, "") < key for key in history_keys):
        raise MigrationOrderingError(
            f"{wp_id}: cannot represent a strict seed history floor below "
            f"the reducer key {min(history_keys)!r}"
        )
    return floor


def _compatibility_repair_at(stream: EventStream, wp_id: str) -> str:
    """Return a stable timestamp strictly after pre-repair history for *wp_id*."""
    history = _wp_events(stream, wp_id, include_seeds=True)
    if not history:
        raise MigrationOrderingError(
            f"{wp_id}: compatibility repair requested without persisted history"
        )
    history_keys = [(event.at, event.event_id) for event in history]
    latest_at = max(history_keys)[0]
    repair_at = _shift_ordering_timestamp(
        latest_at,
        wp_id=wp_id,
        direction="after",
    )
    if not all((repair_at, "") > key for key in history_keys):
        raise MigrationOrderingError(
            f"{wp_id}: cannot place compatibility repair after reducer key "
            f"{max(history_keys)!r}"
        )
    return repair_at


# ---------------------------------------------------------------------------
# OLD reader (pre-eviction frontmatter + tasks.md checkboxes)
# ---------------------------------------------------------------------------


def _coerce_tracker_refs(raw: Any) -> tuple[str, ...]:
    """Normalise a frontmatter ``tracker_refs`` value to a tuple of strings."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(part.strip() for part in raw.split(",") if part.strip())
    if isinstance(raw, (list, tuple)):
        return tuple(str(item).strip() for item in raw if str(item).strip())
    return ()


def _review_from_frontmatter(frontmatter: dict[str, Any], wp_id: str) -> ReviewOverride | None:
    """Reconstruct a :class:`ReviewOverride` from the override quartet, if complete."""
    at = frontmatter.get("review_artifact_override_at")
    actor = frontmatter.get("review_artifact_override_actor")
    override_wp = frontmatter.get("review_artifact_override_wp_id") or wp_id
    reason = frontmatter.get("review_artifact_override_reason")
    if not (at and actor and reason):
        return None
    override = ReviewOverride(at=str(at), actor=str(actor), wp_id=str(override_wp), reason=str(reason))
    return override if override.complete else None


def _subtasks_from_tasks_md(tasks_md_text: str, wp_id: str) -> dict[str, Status]:
    """Read per-subtask completion for *wp_id* from a ``tasks.md`` body.

    Reuses the canonical fence-aware, first-``WPxx``-heading walker
    (``core.subtask_rows.iter_wp_section_subtask_rows``) — the same source the
    lane-transition guard and dashboard consume — so the backfill never forks the
    "what counts as a subtask" definition. A checked row folds to ``Lane.DONE``,
    an unchecked row to ``Lane.PLANNED`` (a not-done sentinel).
    """
    result: dict[str, Status] = {}
    for task_id, checked in iter_wp_section_subtask_rows(tasks_md_text, wp_id):
        result[task_id] = Lane.DONE if checked else Lane.PLANNED
    return result


def _wp_code(wp_file: Path) -> str:
    """Derive the ``WPxx`` code from a WP filename stem."""
    import re

    m = re.match(r"^(WP\d+)", wp_file.stem)
    return m.group(1) if m else wp_file.stem


def read_legacy_runtime(feature_dir: Path) -> dict[str, LegacyWPRuntime]:
    """Reconstruct every WP's pre-eviction runtime state (the OLD reader).

    Reads each ``tasks/WP*.md`` frontmatter (``shell_pid`` / ``shell_pid_created_at``
    / ``agent`` / ``assignee`` / ``tracker_refs`` / ``review_artifact_override_*``)
    and the per-WP ``tasks.md`` checkbox section (subtask completion). This is the
    ground truth :func:`verify_backfill` compares the reduced snapshot against and
    the source :func:`backfill_runtime_state` seeds from.

    Returns a mapping keyed by ``WPxx`` code; only WPs that carry some evictable
    runtime state are included.
    """
    from specify_cli.frontmatter import FrontmatterManager

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return {}

    tasks_md = feature_dir / "tasks.md"
    tasks_md_text = tasks_md.read_text(encoding="utf-8") if tasks_md.exists() else ""

    manager = FrontmatterManager()
    out: dict[str, LegacyWPRuntime] = {}

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            frontmatter, _body = manager.read(wp_file)
        except Exception as exc:  # noqa: BLE001 - translate parser failures to migration domain
            raise LegacyRuntimeReadError(
                f"cannot read {wp_file.name} for legacy runtime: {exc}"
            ) from exc

        wp_id = _wp_code(wp_file)
        shell_pid_raw = frontmatter.get("shell_pid")
        agent_raw = frontmatter.get("agent")
        runtime = LegacyWPRuntime(
            wp_id=wp_id,
            shell_pid=int(shell_pid_raw) if isinstance(shell_pid_raw, (int, str)) and str(shell_pid_raw).strip().isdigit() else None,
            shell_pid_created_at=(str(frontmatter["shell_pid_created_at"]) if frontmatter.get("shell_pid_created_at") else None),
            agent=(str(agent_raw) if isinstance(agent_raw, str) and agent_raw.strip() else None),
            assignee=(str(frontmatter["assignee"]) if frontmatter.get("assignee") else None),
            tracker_refs=_coerce_tracker_refs(frontmatter.get("tracker_refs")),
            subtasks=_subtasks_from_tasks_md(tasks_md_text, wp_id),
            review=_review_from_frontmatter(frontmatter, wp_id),
            frontmatter_keys=frozenset(frontmatter.keys()),
        )
        if runtime.has_evictable_state() or runtime.frontmatter_keys:
            out[wp_id] = runtime

    return out


# ---------------------------------------------------------------------------
# Claim anchor (from the existing event log)
# ---------------------------------------------------------------------------


def _claim_anchors(feature_dir: Path) -> dict[str, str]:
    """Return each WP's ``claimed`` timestamp anchor from the existing event log.

    The anchor is the ``at`` of the WP's first transition *into* ``claimed``; if
    the WP never entered ``claimed`` explicitly it falls back to the WP's earliest
    transition ``at``. Migration seeds and compatibility repairs are excluded,
    so repeated invocations cannot move their own anchor. A WP with no
    legitimate transitions is absent from this mapping — this function is
    event-log-only. :func:`_resolve_anchor` layers
    frontmatter-synthesized anchors on top of this for the missing/truncated-log
    case (#2848); it is that layered resolver, not this one, that decides
    whether a WP is genuinely never-claimed.
    """
    earliest = _earliest_transition_ats(feature_dir)
    claimed: dict[str, str] = {}
    for ev in _authentic_transitions(feature_dir):
        if ev.to_lane == Lane.CLAIMED and (ev.wp_id not in claimed or ev.at < claimed[ev.wp_id]):
            claimed[ev.wp_id] = ev.at
    return {wp_id: claimed.get(wp_id, earliest[wp_id]) for wp_id in earliest}


def _authentic_stream(feature_dir: Path) -> tuple[list[StatusEvent], list[InnerStateChanged]]:
    """Return the event log with this migration's OWN seed rows removed.

    Every input the seed builder derives its output from must come from
    *authentic* history. A previously written seed is this module's own output
    from an earlier run; folding it back in makes the seed a function of the
    last run rather than of the corpus, and the payload then drifts on each
    re-run — breaking the byte-stable idempotency contract (NFR-002) and, worse,
    silently retiring :func:`_verify_expected_seed_events`' tamper proof (the
    expectation would dissolve the moment the seed it is meant to check exists).

    "Our own output" is decided by the single canonical predicate
    :func:`_is_migration_actor`, so compatibility repairs
    (:data:`COMPATIBILITY_REPAIR_ACTOR`) are excluded alongside ordinary seeds:
    a repair row folded back in would make the next run's seed a function of the
    previous run's repair. Keying on the migration actors is exact — no live
    agent writes them.

    This is the on-disk entry point for the same filter
    :func:`_stream_without_migration` applies to an already-loaded stream; both
    delegate to that one implementation so the two halves (build / verify) can
    never disagree about what counts as authentic.
    """
    authentic = _stream_without_migration(read_event_stream(feature_dir))
    return (authentic.transitions, authentic.annotations)


def _authentic_transitions(feature_dir: Path) -> list[StatusEvent]:
    """Return the event log's transitions with this migration's own seeds removed."""
    return _authentic_stream(feature_dir)[0]


def _earliest_transition_ats(feature_dir: Path) -> dict[str, str]:
    """Return each WP's earliest *authentic* transition ``at`` from the event log.

    Event-log-only, like :func:`_claim_anchors`: a WP with no authentic
    transitions is absent from the mapping. This is the "recorded lane history
    starts here" boundary :func:`_retro_claim_at` orders the retroactive claim
    seed against.
    """
    earliest: dict[str, str] = {}
    for ev in _authentic_transitions(feature_dir):
        if ev.wp_id not in earliest or ev.at < earliest[ev.wp_id]:
            earliest[ev.wp_id] = ev.at
    return earliest


def _instant_before(at: str) -> str | None:
    """Return the ISO-8601 instant one microsecond before *at*, or ``None``.

    ``None`` signals an unparseable timestamp — an already-malformed log entry
    is a signal to leave the anchor alone, not to raise (same never-raises
    posture as :func:`_parse_epoch_or_iso`).
    """
    try:
        parsed = parse_iso(at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed - timedelta(microseconds=1)).isoformat()


def _snapshot_claim_slots(stream: EventStream) -> dict[str, dict[str, Any]]:
    """Return, per WP, the claim slot VALUES authentic history already carries.

    The backfill's contract is "no legacy frontmatter value is lost", not "every
    legacy value is re-stated". A claim slot the canonical model already holds
    *with the same value* has nothing left to migrate, so minting a lane-shaped
    carrier for it is pure write amplification on a seam (``accept``) that is
    otherwise lane-neutral — the ``accept`` gate's event-count-neutrality
    contract (#2985 corroborating red).

    Values, not bare slot names: keying suppression on mere *presence* would
    discard a legacy value whenever authentic history holds a DIFFERENT one for
    the same slot. Nothing else records it — the module's own downstream strip
    step then deletes the frontmatter it came from — which is exactly the loss
    C-002 bars and ``contracts/birth-cutover-ordering.md`` invariant 5 forbids
    ("present in the raw seed evidence"). Invariant 5's second clause already
    lets a later legitimate writer win the *reduced* fold, so archiving a
    divergent legacy value in the raw log costs nothing observable.

    Reduced over :func:`_stream_without_migration`, never the raw log: the
    answer must be the same before and after this module writes its own seeds,
    or the seed payload would differ between the write run and every later
    verify run. That same property is what lets the *witness*
    (:func:`_claim_witness_denominator`) consult this probe without becoming
    tautological — no row this module emits can change the answer.

    Read-only: reduces in memory rather than going through
    ``materialize_snapshot``, so building seeds never writes a ``status.json``
    view as a side effect.
    """
    authentic = _stream_without_migration(stream)
    snapshot = reduce(authentic.transitions, authentic.annotations)
    return {
        wp_id: {
            slot: value
            for slot in _CLAIM_SLOTS
            if (value := wp.get(slot)) not in (None, "", [], {})
        }
        for wp_id, wp in snapshot.work_packages.items()
    }


def _unmigrated_claim_slots(
    runtime: LegacyWPRuntime,
    present: dict[str, Any],
) -> dict[str, Any]:
    """Return the claim ``policy_metadata`` payload still worth seeding.

    A legacy claim value is dropped only when authentic history already carries
    that EXACT value (see :func:`_snapshot_claim_slots`); a divergent authentic
    value leaves the legacy one un-archived and so keeps its carrier slot. An
    empty result means the carrier transition is not minted at all.
    """
    return {
        slot: value
        for slot, value in _legacy_claim_slots(runtime).items()
        if present.get(slot) != value
    }


def _retro_claim_at(anchor: str, earliest_at: str | None) -> str:
    """Return the seed claim transition's ``at``, forced before recorded history.

    The seed ``planned -> claimed`` transition is a *carrier* for pre-eviction
    claim metadata (``shell_pid`` / ``agent``), never a statement about the WP's
    current lane. :func:`~specify_cli.status.reducer.reduce` folds transitions in
    ``(at, event_id)`` order and the last one wins, so a seed that ties with — or
    outlives — the WP's real history silently REGRESSES the reduced lane (a
    ``done`` WP reappearing as ``claimed``; #1883 accept-convergence red).

    The tie is not hypothetical: :func:`_claim_anchors` falls back to the WP's
    *earliest transition* ``at`` whenever the log holds no explicit ``claimed``
    event (force-jumped or pruned history), and the seed's deterministic
    ``event_id`` then decides the fold order by pure lexical luck.

    So the seed is pinned strictly before the WP's earliest recorded transition
    whenever the anchor does not already precede it. The shift is one microsecond
    — the anchor is documented fictional time (see :func:`_build_seed_events`),
    and the seeded runtime *values* are unchanged, only their fold position.
    A WP with no recorded transitions at all (``earliest_at is None``) has no
    history to order against and keeps its anchor verbatim.
    """
    if earliest_at is None or anchor < earliest_at:
        return anchor
    shifted = _instant_before(earliest_at)
    return anchor if shifted is None else shifted


def _parse_epoch_or_iso(raw: str | None) -> str | None:
    """Coerce a legacy timestamp string to ISO-8601 UTC, or ``None`` if unparseable.

    ``shell_pid_created_at`` is written as a raw epoch-seconds float string (the
    process-start baseline ``implement`` records); tolerate a genuine ISO-8601
    string too, in case an older or hand-edited corpus carries one. Never
    raises — an unparseable value is a signal to fall back, not an error.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return from_epoch(float(text)).isoformat()
    except ValueError:
        pass
    try:
        parsed = parse_iso(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _synthesize_claim_anchor(read_dir: Path, runtime: LegacyWPRuntime) -> str | None:
    """Synthesize a deterministic claim anchor from frontmatter, or ``None``.

    Used only when the event log carries no transition for this WP at all — a
    missing/truncated log must not silently drop a real claim (#2848). Sourced
    entirely from data already on disk (never the wall clock), so a re-run
    reproduces the exact same anchor byte-for-byte:

    1. ``shell_pid_created_at`` (the process-start baseline) if parseable.
    2. The mission's ``meta.json`` ``created_at`` (mission-creation time) —
       later than the true claim, but a real, deterministic, always-honest
       lower bound when no per-WP timestamp survived.

    Both sources are read from *read_dir* — the mission's PRIMARY-partition
    leg, where ``tasks/`` frontmatter and ``meta.json`` canonically live
    (NFR-004 / R5). This is the pinned canonical leg for anchor synthesis: the
    caller may be seeding events into a distinct COORD-partition directory
    (``feature_dir`` in :func:`backfill_runtime_state`), and that COORD leg's
    own ``meta.json`` — if it carries one at all — must never be consulted
    here. Reading from any leg other than *read_dir* would let two callers
    that pass different COORD directories for the same mission synthesize two
    different anchors, producing a flipped-but-unverifiable corpus.

    Returns ``None`` when neither source yields a timestamp — that WP has claim
    *fields* (e.g. a bare ``agent``) but no honest time to anchor them to, so it
    is treated the same as genuinely never-claimed (fail-closed, no fabricated
    time).
    """
    from_shell_pid = _parse_epoch_or_iso(runtime.shell_pid_created_at)
    if from_shell_pid is not None:
        return from_shell_pid
    meta = load_meta(read_dir, allow_missing=True, on_malformed="none")
    if meta is not None:
        created_at = meta.get("created_at")
        if isinstance(created_at, str) and created_at.strip():
            return created_at
    return None


def _resolve_anchor(
    read_dir: Path,
    wp_id: str,
    runtime: LegacyWPRuntime,
    event_log_anchors: dict[str, str],
) -> tuple[str | None, bool]:
    """Resolve *wp_id*'s claim anchor: ``(anchor, was_synthesized)``.

    Prefers the event log. When the log carries no transition for this WP but
    its frontmatter carries claim state (:meth:`LegacyWPRuntime.has_claim_state`),
    synthesizes a deterministic anchor from that frontmatter instead of treating
    the WP as never-claimed — a truncated/missing event log must not silently
    drop a real claim (Defect: #2848). Returns ``(None, False)`` only for a
    genuinely never-claimed WP: no event-log anchor AND no claim state (or claim
    state with no honest timestamp) to synthesize from.

    *read_dir* is the canonical PRIMARY leg passed through to
    :func:`_synthesize_claim_anchor` (NFR-004 / R5) — see that function's
    docstring for why the synthesis fallback must never read the COORD
    write leg's own ``meta.json``.
    """
    anchor = event_log_anchors.get(wp_id)
    if anchor is not None:
        return anchor, False
    if not runtime.has_claim_state():
        return None, False
    synthesized = _synthesize_claim_anchor(read_dir, runtime)
    return synthesized, synthesized is not None


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


def _resolve_seed_anchor(
    stream: EventStream,
    read_dir: Path,
    wp_id: str,
    runtime: LegacyWPRuntime,
    anchors: dict[str, str],
) -> tuple[str | None, bool]:
    """Resolve *wp_id*'s seed ordering time: ``(anchor, was_synthesized)``.

    This is the migration's *eligibility contract* for one WP, expressed
    independently of :func:`_build_seed_events`: when the WP already carries
    legitimate history the seed rides the strict per-WP floor; otherwise the
    claimed/synthesized anchor contract applies. ``(None, False)`` means the
    migration is contractually forbidden to mint a seed for this WP (genuinely
    never-claimed, or claim fields with no honest time).

    Both the writer (:func:`_build_seed_events`) and the independent claim-slot
    witness (:func:`_verify_claim_slot_witnesses`) resolve eligibility through
    this helper, so the witness never derives its denominator from the builder's
    emitted rows — the tautology plan IC-02 / C-002 prohibit.
    """
    floor = _wp_history_floor(stream, wp_id)
    if floor is not None:
        return floor, False
    return _resolve_anchor(read_dir, wp_id, runtime, anchors)


def _legacy_claim_slots(runtime: LegacyWPRuntime) -> dict[str, Any]:
    """Return every non-null legacy claim slot for one WP, in canonical order."""
    return {
        slot: value
        for slot in _CLAIM_SLOTS
        if (value := getattr(runtime, slot)) is not None
    }


def _claim_carrier(
    *,
    slug: str,
    mission_id: str,
    wp_id: str,
    at: str,
    policy_metadata: dict[str, Any],
) -> StatusEvent:
    """Return the seed ``planned -> claimed`` claim-metadata carrier row.

    Single canonical authority for the carrier's *shape*. The builder mints it
    for real, and :func:`_legacy_contract_carriers` mints reference copies used
    to tell an older-contract row apart from a tampered one — so the two can
    never drift on an envelope field.
    """
    return StatusEvent(
        event_id=_seed_id(mission_id, wp_id, "claim"),
        mission_slug=slug,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at=at,
        actor=BACKFILL_ACTOR,
        force=False,
        execution_mode="worktree",
        policy_metadata=policy_metadata,
        mission_id=mission_id if mission_id != slug else None,
    )


def _build_seed_events(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    anchors: dict[str, str],
    warnings: list[str],
) -> tuple[list[StatusEvent], list[InnerStateChanged]]:
    """Build (claim transitions, annotations) seed events for a corpus.

    Seed ``event_id``s are deterministic namespaced ULIDs. Two ordering rules
    compose here, and both must hold:

    1. **Shared per-WP floor** (:func:`_resolve_seed_anchor`): when the WP already
       carries authentic transition *or annotation* history, every seed — the
       claim carrier and each reconstructed annotation alike — uses one shared
       timestamp strictly below the earliest raw reducer key. With no history at
       all, the claimed/synthesized anchor contract is unchanged and the
       annotations share that anchor, so their fold ordering (post-transition,
       via the WP01 event-kind partition) stays deterministic.
    2. **Retroactive claim pin** (:func:`_retro_claim_at`): the claim
       *transition*'s ``at`` is additionally pinned strictly before the WP's
       earliest recorded transition, so a retroactive metadata carrier can never
       win the reducer's ``(at, event_id)`` fold and regress a finished WP back
       to ``claimed`` (#2985 / #1883). Rule 1 already satisfies this whenever the
       WP has history, so the pin is a belt-and-braces floor for the anchor
       paths rule 1 leaves untouched — it is never allowed to move a seed
       *later*.

    The carrier is minted only for the claim slots authentic history does not
    already hold (:func:`_unmigrated_claim_slots`); an already-migrated claim has
    nothing left to migrate, so re-stating it would be pure write amplification
    on the otherwise lane-neutral ``accept`` seam. Suppression here cannot hide
    data loss: :func:`_verify_claim_slot_witnesses` derives its denominator from
    :func:`read_legacy_runtime` and the same authentic-history probe, never from
    the rows this function emits.

    Subtask-completion ``at`` is clamped to the resolved anchor (fictional time,
    documented). The truthful ``review_artifact_override_at`` is preserved
    *inside* the delta's
    :class:`ReviewOverride`, not on the envelope.

    When the event log carries no anchor for a WP that nonetheless has claim
    state in frontmatter, the anchor is synthesized (:func:`_resolve_anchor`) so
    a missing/truncated event log never silently drops a real claim (#2848). A
    WP with neither an event-log anchor nor synthesizable claim state is
    genuinely never-claimed and is skipped (warned, not failed).

    *read_dir* is the canonical PRIMARY leg passed through to
    :func:`_resolve_anchor` for the synthesis fallback (NFR-004 / R5) and to
    :func:`_mission_id` (#2966 part-1) — it is intentionally distinct from
    *feature_dir* (the event-write leg) so neither the resolved anchor
    payload nor the seed-id namespace ever depends on which COORD directory
    happens to be seeded.
    """
    slug = feature_dir.name
    mission_id = _mission_id(read_dir)
    # Recorded lane history the retroactive claim seed must fold BEFORE
    # (:func:`_retro_claim_at`) so it can never regress a WP's reduced lane.
    earliest_ats = _earliest_transition_ats(feature_dir)
    transitions: list[StatusEvent] = []
    annotations: list[InnerStateChanged] = []
    stream = read_event_stream(feature_dir)
    # Claim slots the canonical model already holds — nothing left to migrate
    # there, so no lane-shaped carrier is minted for them.
    present_claim_slots = _snapshot_claim_slots(stream)

    for wp_id, runtime in sorted(legacy.items()):
        anchor, synthesized = _resolve_seed_anchor(
            stream,
            read_dir,
            wp_id,
            runtime,
            anchors,
        )
        if anchor is None:
            if runtime.has_evictable_state():
                warnings.append(f"{wp_id}: no claim anchor (never-claimed WP) — runtime seed skipped")
            continue
        if synthesized:
            warnings.append(
                f"{wp_id}: no claim anchor in event log — synthesized from frontmatter claim state"
            )

        # Claim state rides a seed planned->claimed transition whose
        # policy_metadata sidecar the reducer folds into the snapshot slots —
        # but only for the slots the snapshot does not already carry.
        policy_metadata = _unmigrated_claim_slots(runtime, present_claim_slots.get(wp_id, {}))
        if policy_metadata:
            transitions.append(
                _claim_carrier(
                    slug=slug,
                    mission_id=mission_id,
                    wp_id=wp_id,
                    at=_retro_claim_at(anchor, earliest_ats.get(wp_id)),
                    policy_metadata=policy_metadata,
                )
            )

        # assignee / tracker_refs / subtasks / review ride annotations. Each is a
        # distinct namespaced seed so idempotency skips them independently.
        _append_annotation(annotations, mission_id, wp_id, anchor, "assignee", WPInnerStateDelta(assignee=runtime.assignee) if runtime.assignee else None)
        _append_annotation(
            annotations,
            mission_id,
            wp_id,
            anchor,
            "tracker_refs",
            WPInnerStateDelta(tracker_refs=list(runtime.tracker_refs)) if runtime.tracker_refs else None,
        )
        _append_annotation(
            annotations,
            mission_id,
            wp_id,
            anchor,
            "subtasks",
            WPInnerStateDelta(subtasks=dict(runtime.subtasks)) if runtime.subtasks else None,
        )
        _append_annotation(
            annotations,
            mission_id,
            wp_id,
            anchor,
            "review",
            WPInnerStateDelta(review=runtime.review) if (runtime.review is not None and runtime.review.complete) else None,
        )
    return transitions, annotations


def _append_annotation(
    annotations: list[InnerStateChanged],
    mission_id: str,
    wp_id: str,
    at: str,
    field_name: str,
    delta: WPInnerStateDelta | None,
) -> None:
    """Append a deterministic-id seed annotation for one field, if the delta is present."""
    if delta is None or delta.is_empty():
        return
    annotations.append(
        annotate(
            wp_id,
            delta,
            actor=BACKFILL_ACTOR,
            at=at,
            event_id=_seed_id(mission_id, wp_id, field_name),
        )
    )


def _event_payload_without_at(
    event: StatusEvent | InnerStateChanged,
) -> dict[str, Any]:
    """Return the typed wire payload without its historical envelope time."""
    payload: dict[str, Any] = event.to_dict()
    payload.pop("at", None)
    return payload


@dataclass(frozen=True)
class _LegacyCarrier:
    """The pre-#2985 claim carrier for one WP, plus why today's build differs.

    Attributes:
        row: The exact row the old contract would have minted (``at`` is not
            part of the comparison and is left empty).
        fully_superseded: ``True`` when AUTHENTIC history already holds every
            legacy claim slot, so the corrected builder is contractually
            required to emit no carrier at all
            (:func:`_unmigrated_claim_slots`). Derived from the legacy reader
            and the migration-filtered event log — never from the builder — so
            a builder that merely *forgets* to emit a carrier is not mistaken
            for a legitimately superseded one.
    """

    row: StatusEvent
    fully_superseded: bool


def _legacy_contract_carriers(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    stream: EventStream,
) -> dict[str, _LegacyCarrier]:
    """Return, keyed by seed id, the carrier the PRE-#2985 builder would mint.

    The old contract put *every* non-null legacy claim slot on one carrier at
    the WP's claim anchor. The corrected builder narrows that payload to the
    slots authentic history does not already hold
    (:func:`_unmigrated_claim_slots`) and pins it below the per-WP history floor,
    so on a corpus seeded before the fix the persisted row legitimately differs
    from today's expectation in both ``at`` and ``policy_metadata``.

    Reconstructing the old row exactly — rather than tolerating *any* divergence
    — is what keeps a genuinely tampered seed a hard mismatch: a corrupted slot
    value or envelope field no longer equals this reference, so it never reaches
    the append-only repair path (FR-010) and stays fail-closed.
    """
    slug = feature_dir.name
    mission_id = _mission_id(read_dir)
    present_claim_slots = _snapshot_claim_slots(stream)
    carriers: dict[str, _LegacyCarrier] = {}
    for wp_id, runtime in legacy.items():
        claim_slots = _legacy_claim_slots(runtime)
        if not claim_slots:
            continue
        row = _claim_carrier(
            slug=slug,
            mission_id=mission_id,
            wp_id=wp_id,
            at="",
            policy_metadata=claim_slots,
        )
        carriers[row.event_id] = _LegacyCarrier(
            row=row,
            fully_superseded=not _unmigrated_claim_slots(
                runtime,
                present_claim_slots.get(wp_id, {}),
            ),
        )
    return carriers


def _matches_legacy_contract(
    actual: StatusEvent | InnerStateChanged,
    legacy_carriers: dict[str, _LegacyCarrier],
    *,
    require_superseded: bool = False,
) -> bool:
    """True iff *actual* is byte-equal (modulo ``at``) to the old-contract row.

    With *require_superseded*, additionally demand that today's builder is
    *contractually forbidden* to emit the row at all. That guard is what keeps
    a builder which wrongly suppresses claim carriers from being read as
    evidence that the persisted row is obsolete (plan IC-02 / C-002).
    """
    carrier = legacy_carriers.get(actual.event_id)
    if carrier is None or (require_superseded and not carrier.fully_superseded):
        return False
    return _event_payload_without_at(actual) == _event_payload_without_at(carrier.row)


def _misaligned_seed_wps(
    stream: EventStream,
    expected_transitions: list[StatusEvent],
    expected_annotations: list[InnerStateChanged],
    legacy_carriers: dict[str, _LegacyCarrier],
) -> set[str]:
    """Return WPs whose persisted seed rows predate the corrected seed contract.

    Reducer rows are immutable and deduplicated on first write, so a seed the
    old contract already persisted can never be rewritten in place. Two shapes
    qualify, and only these two:

    * the row is semantically the seed we would write today but sits at the old
      (pre-floor) ``at``; and
    * the row is the old contract's full-payload claim carrier
      (:func:`_legacy_contract_carriers`) — whether the corrected builder would
      narrow its payload today or suppress it entirely because authentic history
      now holds every slot.

    Anything else — a mutated slot value, a mutated envelope field — is
    tampering, is *not* returned here, and therefore stays a hard mismatch in
    :func:`_verify_expected_seed_events`.
    """
    expected_by_id: dict[str, StatusEvent | InnerStateChanged] = {
        event.event_id: event
        for event in _combined_events(expected_transitions, expected_annotations)
    }
    misaligned: set[str] = set()
    for actual in _combined_events(stream.transitions, stream.annotations):
        if actual.actor != BACKFILL_ACTOR:
            continue
        expected = expected_by_id.get(actual.event_id)
        if expected is None:
            if _matches_legacy_contract(
                actual, legacy_carriers, require_superseded=True
            ):
                misaligned.add(actual.wp_id)
            continue
        if actual.to_dict() == expected.to_dict():
            continue
        if _event_payload_without_at(actual) == _event_payload_without_at(
            expected
        ) or _matches_legacy_contract(actual, legacy_carriers):
            misaligned.add(actual.wp_id)
    return misaligned


def _stream_without_migration(stream: EventStream) -> EventStream:
    """Return only legitimate, non-migration history."""
    return EventStream(
        transitions=[
            event
            for event in stream.transitions
            if not _is_migration_actor(event.actor)
        ],
        annotations=[
            event
            for event in stream.annotations
            if not _is_migration_actor(event.actor)
        ],
    )


def _stream_without_compatibility_repairs(stream: EventStream) -> EventStream:
    """Return persisted history before any compatibility repair rows."""
    return EventStream(
        transitions=[
            event
            for event in stream.transitions
            if event.actor != COMPATIBILITY_REPAIR_ACTOR
        ],
        annotations=[
            event
            for event in stream.annotations
            if event.actor != COMPATIBILITY_REPAIR_ACTOR
        ],
    )


def _repair_scalar_value(
    desired: dict[str, Any],
    current: dict[str, Any],
    slot: str,
) -> Any | None:
    """Return a changed non-null replacement value, or ``None`` if unchanged."""
    desired_value = desired.get(slot)
    if desired_value == current.get(slot):
        return None
    if desired_value is None:
        raise MigrationOrderingError(
            f"cannot append-only repair {slot!r}: the corrected seed history "
            "requires clearing a value"
        )
    return desired_value


def _runtime_repair_delta(
    desired: dict[str, Any],
    current: dict[str, Any],
) -> WPInnerStateDelta:
    """Build the minimal annotation that restores seed-owned runtime slots."""
    shell_pid = _repair_scalar_value(desired, current, "shell_pid")
    shell_pid_created_at = _repair_scalar_value(
        desired,
        current,
        "shell_pid_created_at",
    )
    agent = _repair_scalar_value(desired, current, "agent")
    assignee = _repair_scalar_value(desired, current, "assignee")

    tracker_refs_replace: list[str] | None = None
    if desired.get("tracker_refs") != current.get("tracker_refs"):
        tracker_refs_replace = list(desired.get("tracker_refs") or [])

    subtasks: dict[str, Status] | None = None
    if desired.get("subtasks") != current.get("subtasks"):
        subtasks = {
            str(task_id): Status(str(status))
            for task_id, status in dict(desired.get("subtasks") or {}).items()
        }

    review: ReviewOverride | None = None
    if desired.get("review") != current.get("review"):
        review_raw = desired.get("review")
        if not isinstance(review_raw, dict):
            raise MigrationOrderingError(
                "cannot append-only repair 'review': corrected seed history "
                "requires clearing or has an invalid review value"
            )
        review = ReviewOverride.from_dict(review_raw)

    return WPInnerStateDelta(
        shell_pid=int(shell_pid) if shell_pid is not None else None,
        shell_pid_created_at=(
            str(shell_pid_created_at)
            if shell_pid_created_at is not None
            else None
        ),
        agent=str(agent) if agent is not None else None,
        assignee=str(assignee) if assignee is not None else None,
        tracker_refs_replace=tracker_refs_replace,
        subtasks=subtasks,
        review=review,
    )


def _plan_compatibility_repairs(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    stream: EventStream,
    expected_transitions: list[StatusEvent],
    expected_annotations: list[InnerStateChanged],
    new_transitions: list[StatusEvent],
    new_annotations: list[InnerStateChanged],
) -> tuple[list[StatusEvent], list[InnerStateChanged]]:
    """Plan deterministic repairs for persisted seeds that predate the floor.

    The target is the snapshot produced by corrected seeds followed by all
    legitimate history. The pre-repair comparison includes any missing,
    correctly ordered seeds planned in this same invocation, preventing a
    partial legacy corpus from receiving unnecessary repair rows.

    *read_dir* supplies the ``mission_id`` namespace, exactly as it does for
    :func:`_build_seed_events` (#2966 part-1), so a repair id never depends on
    which COORD directory happens to be seeded.
    """
    misaligned_wps = _misaligned_seed_wps(
        stream,
        expected_transitions,
        expected_annotations,
        _legacy_contract_carriers(feature_dir, read_dir, legacy, stream),
    )
    if not misaligned_wps:
        return [], []

    legitimate = _stream_without_migration(stream)
    desired_snapshot = reduce(
        [*expected_transitions, *legitimate.transitions],
        [*expected_annotations, *legitimate.annotations],
    )
    persisted_pre_repair = _stream_without_compatibility_repairs(stream)
    simulated_stream = EventStream(
        transitions=[*persisted_pre_repair.transitions, *new_transitions],
        annotations=[*persisted_pre_repair.annotations, *new_annotations],
    )
    current_snapshot = reduce(
        simulated_stream.transitions,
        simulated_stream.annotations,
    )
    mission_id = _mission_id(read_dir)
    slug = feature_dir.name
    transition_repairs: list[StatusEvent] = []
    annotation_repairs: list[InnerStateChanged] = []

    for wp_id in sorted(misaligned_wps):
        desired = desired_snapshot.work_packages.get(wp_id, {})
        current = current_snapshot.work_packages.get(wp_id, {})
        repair_at = _compatibility_repair_at(simulated_stream, wp_id)
        desired_lane = desired.get("lane")
        current_lane = current.get("lane")
        if desired_lane is not None and desired_lane != current_lane:
            transition_repairs.append(
                StatusEvent(
                    event_id=_repair_id(mission_id, wp_id, "lane"),
                    mission_slug=slug,
                    wp_id=wp_id,
                    from_lane=Lane(str(current_lane)),
                    to_lane=Lane(str(desired_lane)),
                    at=repair_at,
                    actor=COMPATIBILITY_REPAIR_ACTOR,
                    force=False,
                    execution_mode="worktree",
                    reason="append-only repair for persisted pre-floor seed",
                    mission_id=mission_id if mission_id != slug else None,
                )
            )

        delta = _runtime_repair_delta(desired, current)
        if not delta.is_empty():
            annotation_repairs.append(
                annotate(
                    wp_id,
                    delta,
                    actor=COMPATIBILITY_REPAIR_ACTOR,
                    at=repair_at,
                    event_id=_repair_id(mission_id, wp_id, "runtime"),
                )
            )

    return transition_repairs, annotation_repairs


def _runtime_feature_dir(feature_dir: Path, owned: OwnedMission | None) -> Path:
    """Keep explicit single-branch IO on the exact threaded mission root."""
    if owned is None:
        canonical: Path = canonicalize_feature_dir(feature_dir)
        return canonical
    from mission_runtime import ActionContextError

    # #3866: ``owned`` is the caller-validated value object — re-deriving it
    # through ``resolve_owned_mission`` (ownership claim + mission resolve +
    # git branch probes) per backfill/cutover phase was pure re-resolution of
    # a value the caller already holds. The exact-directory guard below keeps
    # every write anchored to that validated mission root.
    if feature_dir.resolve() != owned.directory:
        raise ActionContextError("OWNED_MISSION_PATH_REFUSED", "Runtime state must use the selected mission directory.")
    directory: Path = owned.directory
    return directory


def backfill_runtime_state(
    feature_dir: Path, *, read_dir: Path | None = None, dry_run: bool = False,
    owned: OwnedMission | None = None,
) -> BackfillResult:
    """Idempotently seed one mission's frontmatter/checkbox runtime state as events.

    Resolves the write target via :func:`canonicalize_feature_dir` (never
    ``Path.cwd()`` — C-003 / #2647), reconstructs each WP's pre-eviction runtime
    state, and appends the missing seed events through the durability-verified
    store seams. Determinism + idempotency: seed ids are content-namespaced ULIDs,
    and any seed whose id is already on disk is skipped, so a second run seeds
    nothing (NFR-002).

    Args:
        feature_dir: kitty-specs mission directory (canonicalized here) — the
            event-write anchor: the existing event log is read from here for
            the claim-anchor lookup and idempotency check, and new seed
            events are appended here.
        read_dir: Optional distinct directory to read the legacy ``tasks/``
            frontmatter from (placement-port-residuals-closure-01KYDEF0
            FR-002 / IC-02 — the read/write-leg decoupling). Defaults to
            *feature_dir*, so every existing single-leg caller (the corpus
            walk, the CLI backfill command) is byte-unchanged. The two-leg
            cutover caller (:func:`~specify_cli.migration.runtime_state_cutover.cutover_mission`)
            passes the mission's PRIMARY dir here while *feature_dir* stays
            the COORD leg the event log canonically lives on (I-02) — NOT a
            leg swap, only the ``tasks/`` read moves.
        dry_run: When True, compute the would-seed count without writing.
        owned: Explicit single-branch ownership. Both directories are revalidated
            against this exact mission before writes; no legacy primary redirect.

    Returns:
        A :class:`BackfillResult` describing what happened.
    """
    feature_dir = _runtime_feature_dir(feature_dir, owned)
    read_dir = _runtime_feature_dir(read_dir, owned) if read_dir is not None else feature_dir
    slug = feature_dir.name

    if not (read_dir / "tasks").is_dir():
        return BackfillResult(feature_dir=feature_dir, slug=slug, action="skip", reason="no tasks/ directory")

    # fsm-write-path-integrity WP01 (FR-002, writer family 7): the claim-anchor
    # read, the idempotency read (``read_event_stream``) and the seed append all
    # run under ONE acquisition of the mission status lock keyed on
    # ``feature_dir.name`` -- the former read-outside/append-twice shape was a
    # TOCTOU window plus a two-append window. No ``nullcontext()`` degrade at
    # this site (conscious choice): the lock root resolver never fails. No git
    # subprocess runs inside the section (NFR-001); the ``dry_run`` early
    # return inside the lock is fine.
    with feature_status_lock(resolve_status_lock_root(feature_dir), feature_dir.name):
        return _backfill_runtime_state_locked(feature_dir, read_dir, slug, dry_run=dry_run)


def _backfill_runtime_state_locked(
    feature_dir: Path, read_dir: Path, slug: str, *, dry_run: bool,
) -> BackfillResult:
    """Read legacy state + the event log and append the seeds; caller holds the lock."""
    warnings: list[str] = []
    try:
        legacy = read_legacy_runtime(read_dir)
        anchors = _claim_anchors(feature_dir)
        transitions, annotations = _build_seed_events(feature_dir, read_dir, legacy, anchors, warnings)
    except (StoreError, LegacyRuntimeReadError) as exc:
        return BackfillResult(feature_dir=feature_dir, slug=slug, action="error", reason=f"event log unreadable: {exc}", warnings=warnings)

    # Idempotency: drop any seed whose deterministic id is already on disk.
    stream = read_event_stream(feature_dir)
    existing_ids = {
        event.event_id
        for event in _combined_events(stream.transitions, stream.annotations)
    }
    new_transitions = [e for e in transitions if e.event_id not in existing_ids]
    new_annotations = [a for a in annotations if a.event_id not in existing_ids]
    repair_transitions, repair_annotations = _plan_compatibility_repairs(
        feature_dir,
        read_dir,
        legacy,
        stream,
        transitions,
        annotations,
        new_transitions,
        new_annotations,
    )
    new_transitions.extend(
        event
        for event in repair_transitions
        if event.event_id not in existing_ids
    )
    new_annotations.extend(
        event
        for event in repair_annotations
        if event.event_id not in existing_ids
    )
    seeded_count = len(new_transitions) + len(new_annotations)

    if seeded_count == 0:
        return BackfillResult(feature_dir=feature_dir, slug=slug, action="skip", reason="nothing new to seed (idempotent)", warnings=warnings)

    if dry_run:
        return BackfillResult(feature_dir=feature_dir, slug=slug, action="wrote", seeded_count=seeded_count, reason="dry-run (no write)", warnings=warnings)

    # One atomic write for the transition + annotation pair (a single
    # ``os.replace``), replacing the former two-append window.
    append_event_stream_atomic_verified(
        feature_dir, list(_combined_events(new_transitions, new_annotations)),
    )

    logger.info("Backfilled %d runtime seed event(s) for %s", seeded_count, slug)
    return BackfillResult(feature_dir=feature_dir, slug=slug, action="wrote", seeded_count=seeded_count, warnings=warnings)


def backfill_runtime_state_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[BackfillResult]:
    """Walk ``kitty-specs/`` and idempotently backfill every mission.

    Mirrors :func:`~specify_cli.migration.backfill_identity.backfill_repo`. The
    write target is always resolved from each mission directory, never
    ``Path.cwd()`` (C-003).

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When True, compute results without writing.
        mission_slug: When provided, scope the walk to a single mission directory.

    Returns:
        One :class:`BackfillResult` per mission directory visited.
    """
    kitty_specs = repo_root / "kitty-specs"
    results: list[BackfillResult] = []
    if not kitty_specs.is_dir():
        logger.warning("kitty-specs/ not found at %s", repo_root)
        return results

    if mission_slug is not None:
        assert_safe_path_segment(mission_slug)
        candidates = [kitty_specs / mission_slug] if (kitty_specs / mission_slug).is_dir() else []
        if not candidates:
            logger.warning("No mission directory found for slug %r", mission_slug)
            return results
        try:
            candidates = [ensure_within_any(candidates[0], roots=[kitty_specs])]
        except ValueError as exc:
            raise ValueError(
                f"Mission directory resolves outside kitty-specs: {candidates[0]}"
            ) from exc
    else:
        candidates = []
        for entry in sorted(kitty_specs.iterdir()):
            if not entry.is_dir():
                continue
            try:
                candidates.append(ensure_within_any(entry, roots=[kitty_specs]))
            except ValueError:
                logger.warning(
                    "Skipping mission directory that resolves outside kitty-specs: %s",
                    entry,
                )

    for feature_dir in candidates:
        results.append(backfill_runtime_state(feature_dir, dry_run=dry_run))
    return results


# ---------------------------------------------------------------------------
# Fail-closed verify
# ---------------------------------------------------------------------------


def _assert_unstripped(
    wp_id: str,
    runtime: LegacyWPRuntime,
    seeded_slots: set[str],
) -> None:
    """Raise :class:`MigrationOrderingError` if the frontmatter was stripped early.

    Non-vacuous ordering guard: if the reduced snapshot carries a
    frontmatter-sourced slot for this WP but the WP file no longer carries the
    corresponding frontmatter key, ``strip_mutable_fields`` ran before verify and
    the OLD reader would read empty -> vacuous false green. Fail closed.
    """
    for slot in sorted(seeded_slots):
        key = "review_artifact_override_at" if slot == "review" else slot
        if key not in runtime.frontmatter_keys:
            raise MigrationOrderingError(
                f"{wp_id}: deterministic seed carries {slot!r} but frontmatter key {key!r} is absent — "
                "strip_mutable_fields ran before verify (pinned order is backfill -> verify(pre-strip) -> cutover -> strip)"
            )


def _seeded_frontmatter_slots(
    feature_dir: Path,
    read_dir: Path,
    wp_ids: set[str],
) -> dict[str, set[str]]:
    """Return frontmatter slots proven to have deterministic migration seeds.

    The order guard must inspect migration provenance, not the latest snapshot:
    a legitimate runtime annotation may populate a slot that was never present
    in legacy frontmatter. Deterministic seed IDs let us distinguish those cases.

    *read_dir* is threaded through to :func:`_mission_id` (#2966 part-1) so the
    seed ids rebuilt here match the same PRIMARY-namespaced ids
    :func:`_build_seed_events` actually wrote — otherwise a two-leg verify call
    would look up seed ids namespaced on the COORD leg and never find the
    genuine seeds, silently voiding this ordering guard.
    """
    stream = read_event_stream(feature_dir)
    transitions = {event.event_id: event for event in stream.transitions}
    annotations = {event.event_id: event for event in stream.annotations}
    mission_id = _mission_id(read_dir)
    slots_by_wp: dict[str, set[str]] = {}
    for wp_id in wp_ids:
        slots: set[str] = set()
        claim = transitions.get(_seed_id(mission_id, wp_id, "claim"))
        if claim is not None:
            policy_metadata = claim.policy_metadata or {}
            slots.update(
                slot
                for slot in ("shell_pid", "shell_pid_created_at", "agent")
                if slot in policy_metadata
            )
        for field_name, slot in (
            ("assignee", "assignee"),
            ("tracker_refs", "tracker_refs"),
            ("review", "review"),
        ):
            if _seed_id(mission_id, wp_id, field_name) in annotations:
                slots.add(slot)
        slots_by_wp[wp_id] = slots
    return slots_by_wp


def _seed_field_label(expected: StatusEvent | InnerStateChanged) -> str:
    """Return the human field name a seed-row mismatch is reported against."""
    if isinstance(expected, StatusEvent):
        return "claim"
    return next(
        (
            name
            for name, value in expected.delta.to_dict().items()
            if value is not None
        ),
        "annotation",
    )


def _subtask_seed_is_superseded_by_legitimate_history(
    expected: StatusEvent | InnerStateChanged,
    actual: StatusEvent | InnerStateChanged,
    stream: EventStream,
) -> bool:
    """Accept an immutable planned seed only when real history proves completion."""
    if not isinstance(expected, InnerStateChanged) or not isinstance(
        actual, InnerStateChanged
    ):
        return False
    expected_subtasks = expected.delta.to_dict().get("subtasks")
    actual_subtasks = actual.delta.to_dict().get("subtasks")
    if not isinstance(expected_subtasks, dict) or not isinstance(
        actual_subtasks, dict
    ):
        return False
    if expected_subtasks.keys() != actual_subtasks.keys():
        return False
    changed = False
    for task_id, expected_status in expected_subtasks.items():
        actual_status = actual_subtasks[task_id]
        if actual_status == expected_status:
            continue
        if (
            actual_status != Status.PLANNED.value
            or expected_status != Status.DONE.value
        ):
            return False
        changed = True
    if not changed:
        return False

    try:
        seed_at = _parse_ordering_timestamp(actual.at, wp_id=actual.wp_id)
        has_exact_later_witness = any(
            event.wp_id == actual.wp_id
            and not _is_migration_actor(event.actor)
            and _parse_ordering_timestamp(event.at, wp_id=event.wp_id) > seed_at
            and event.delta.to_dict().get("subtasks") == expected_subtasks
            for event in stream.annotations
        )
    except MigrationOrderingError:
        return False
    if not has_exact_later_witness:
        return False

    authentic = _stream_without_migration(stream)
    snapshot = reduce(authentic.transitions, authentic.annotations)
    return bool(
        snapshot.work_packages.get(actual.wp_id, {}).get("subtasks")
        == expected_subtasks
    )


def _seed_row_mismatch(
    expected: StatusEvent | InnerStateChanged,
    actual: StatusEvent | InnerStateChanged | None,
    field_name: str,
    legacy_carriers: dict[str, _LegacyCarrier],
    stream: EventStream,
) -> str | None:
    """Return one expected seed row's mismatch text, or ``None`` if it is sound.

    Absence is always a mismatch. A row that is present but not byte-identical
    is tolerated here in exactly the two cases :func:`_misaligned_seed_wps`
    routes to the append-only repair path — an old ``at`` with an otherwise
    identical payload, and the pre-#2985 full-payload claim carrier
    (:func:`_matches_legacy_contract`). Event rows are immutable and deduplicated
    on first write, so those cannot be corrected in place; the proof obligation
    moves to :func:`_verify_compatibility_repairs`, which requires the
    deterministic repair witness AND that it restores the desired lane and every
    seed-owned runtime slot. Any other divergence is tampering and stays red.
    """
    if actual is None:
        return f"{expected.wp_id}: {field_name} mismatch (deterministic seed missing)"
    if actual.to_dict() == expected.to_dict():
        return None
    if _event_payload_without_at(actual) == _event_payload_without_at(expected):
        return None
    if _matches_legacy_contract(actual, legacy_carriers):
        return None
    if field_name == "subtasks" and _subtask_seed_is_superseded_by_legitimate_history(
        expected, actual, stream
    ):
        return None
    return (
        f"{expected.wp_id}: {field_name} mismatch "
        "(deterministic seed payload diverged)"
    )


def _verify_expected_seed_events(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    anchors: dict[str, str],
) -> list[str]:
    """Verify every deterministic migration seed exists with its exact payload.

    The reduced snapshot is latest-wins runtime state, so a legitimate later
    reassignment can differ from the legacy value without losing history. The
    no-data-loss proof therefore pins the deterministic seed row itself: every
    seed that :func:`_build_seed_events` derives from the legacy source must be
    present byte-semantically (same typed ``to_dict`` payload). Later events may
    then replace the current snapshot value without making cutover verification
    falsely reject an already-active mission.

    *read_dir* is threaded through to :func:`_build_seed_events` so the
    *expected* rows are rebuilt from the same canonical PRIMARY leg the actual
    seed was written from (NFR-004 / R5) — otherwise a two-leg verify call
    would rebuild its expectation from the wrong anchor and spuriously report
    a payload mismatch.
    """
    expected_transitions, expected_annotations = _build_seed_events(
        feature_dir,
        read_dir,
        legacy,
        anchors,
        [],
    )
    stream = read_event_stream(feature_dir)
    actual_by_id: dict[str, StatusEvent | InnerStateChanged] = {
        event.event_id: event
        for event in _combined_events(stream.transitions, stream.annotations)
    }
    legacy_carriers = _legacy_contract_carriers(feature_dir, read_dir, legacy, stream)
    mismatches: list[str] = []

    for expected in _combined_events(expected_transitions, expected_annotations):
        mismatch = _seed_row_mismatch(
            expected,
            actual_by_id.get(expected.event_id),
            _seed_field_label(expected),
            legacy_carriers,
            stream,
        )
        if mismatch is not None:
            mismatches.append(mismatch)

    return mismatches


def _verify_compatibility_repairs(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    expected_transitions: list[StatusEvent],
    expected_annotations: list[InnerStateChanged],
) -> list[str]:
    """Verify old seed rows have every required deterministic repair witness."""
    stream = read_event_stream(feature_dir)
    expected_repair_transitions, expected_repair_annotations = (
        _plan_compatibility_repairs(
            feature_dir,
            read_dir,
            legacy,
            stream,
            expected_transitions,
            expected_annotations,
            [],
            [],
        )
    )
    actual_by_id: dict[str, StatusEvent | InnerStateChanged] = {
        event.event_id: event
        for event in _combined_events(stream.transitions, stream.annotations)
    }
    mismatches: list[str] = []
    for expected in _combined_events(
        expected_repair_transitions, expected_repair_annotations
    ):
        actual = actual_by_id.get(expected.event_id)
        if actual is None:
            mismatches.append(
                f"{expected.wp_id}: compatibility repair witness missing"
            )
        elif actual.to_dict() != expected.to_dict():
            mismatches.append(
                f"{expected.wp_id}: compatibility repair witness diverged"
            )

    legitimate = _stream_without_migration(stream)
    desired_snapshot = reduce(
        [*expected_transitions, *legitimate.transitions],
        [*expected_annotations, *legitimate.annotations],
    )
    actual_snapshot = reduce(stream.transitions, stream.annotations)
    for wp_id in sorted(
        _misaligned_seed_wps(
            stream,
            expected_transitions,
            expected_annotations,
            _legacy_contract_carriers(feature_dir, read_dir, legacy, stream),
        )
    ):
        desired = desired_snapshot.work_packages.get(wp_id, {})
        actual_state = actual_snapshot.work_packages.get(wp_id, {})
        for slot in ("lane", *_SEED_RUNTIME_SLOTS):
            if desired.get(slot) != actual_state.get(slot):
                mismatches.append(
                    f"{wp_id}: compatibility repair did not restore {slot}"
                )
    return mismatches


@dataclass(frozen=True)
class _ClaimWitnessRow:
    """One WP's independently derived claim-slot proof obligation.

    Attributes:
        wp_id: The work package the obligation belongs to.
        claim_slots: Every non-null legacy claim slot and its legacy value —
            the *reduced* half's denominator. Derived from
            :func:`read_legacy_runtime` alone.
        carrier_slots: The subset the deterministic seed carrier must witness
            in the *raw* event log. The complement is carried by authentic
            history instead (:func:`_snapshot_claim_slots`).
    """

    wp_id: str
    claim_slots: dict[str, Any]
    carrier_slots: frozenset[str]


def _claim_witness_denominator(
    stream: EventStream,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    anchors: dict[str, str],
) -> list[_ClaimWitnessRow]:
    """Return, per WP, every legacy claim slot and which ones a seed row owes.

    The denominator comes straight from :func:`read_legacy_runtime` output plus
    the independently resolved eligibility contract (:func:`_resolve_seed_anchor`)
    — never from :func:`_build_seed_events`. A builder that suppresses or omits
    claim transitions therefore cannot shrink the set of slots this witness
    demands (plan IC-02 / C-002).

    A WP with no resolvable anchor is contractually un-seedable (genuinely
    never-claimed, or claim fields with no honest timestamp); the writer warns
    rather than seeds, so the witness mirrors that skip instead of demanding a
    row the migration is forbidden to mint.

    ``carrier_slots`` narrows the *raw* half of the proof to the slots the
    migration is actually allowed to mint a carrier for. It is computed by
    applying the one canonical rule (:func:`_unmigrated_claim_slots`) to the
    authentic-history probe (:func:`_snapshot_claim_slots`) — both of which read
    the event log with this module's own rows filtered out, so the builder's
    output still cannot shrink it. A slot outside ``carrier_slots`` is one the
    canonical model already carries in authentic history; the reduced half below
    still proves that value survives, so no slot is left unwitnessed.
    """
    present_claim_slots = _snapshot_claim_slots(stream)
    owed: list[_ClaimWitnessRow] = []
    for wp_id, runtime in sorted(legacy.items()):
        claim_slots = _legacy_claim_slots(runtime)
        if not claim_slots:
            continue
        anchor, _synthesized = _resolve_seed_anchor(
            stream,
            read_dir,
            wp_id,
            runtime,
            anchors,
        )
        if anchor is None:
            continue
        owed.append(
            _ClaimWitnessRow(
                wp_id=wp_id,
                claim_slots=claim_slots,
                carrier_slots=frozenset(
                    _unmigrated_claim_slots(
                        runtime,
                        present_claim_slots.get(wp_id, {}),
                    )
                ),
            )
        )
    return owed


def _verify_claim_slot_witnesses(
    feature_dir: Path,
    read_dir: Path,
    legacy: dict[str, LegacyWPRuntime],
    anchors: dict[str, str],
) -> list[str]:
    """Independently prove each legacy claim slot in raw and reduced evidence.

    For every eligible non-null ``shell_pid`` / ``shell_pid_created_at`` /
    ``agent`` the migration still owes a carrier for
    (:attr:`_ClaimWitnessRow.carrier_slots`), the deterministic raw claim row is
    looked up by its own seed id and required to carry that exact value. An
    absent row is a mismatch, not a skip — that absence is precisely the #2985
    data loss this witness exists to catch.

    A slot outside ``carrier_slots`` is already held by *authentic* (non-
    migration) history, so the migration is contractually forbidden to re-state
    it (:func:`_unmigrated_claim_slots`) and demanding a raw seed row for it
    would be demanding a row that must not exist. Those slots are still proved,
    by the reduced half below.

    The reduced snapshot must equal the legacy value unless a later legitimate
    writer owns the slot, in which case the later value must win.
    """
    stream = read_event_stream(feature_dir)
    mission_id = _mission_id(read_dir)
    actual_transitions = {event.event_id: event for event in stream.transitions}
    legitimate_stream = _stream_without_migration(stream)
    legitimate_snapshot = reduce(
        legitimate_stream.transitions,
        legitimate_stream.annotations,
    )
    actual_snapshot = reduce(stream.transitions, stream.annotations)
    mismatches: list[str] = []

    for row in _claim_witness_denominator(
        stream,
        read_dir,
        legacy,
        anchors,
    ):
        wp_id = row.wp_id
        claim = actual_transitions.get(_seed_id(mission_id, wp_id, "claim"))
        raw: dict[str, Any] = (claim.policy_metadata or {}) if claim is not None else {}
        legitimate = legitimate_snapshot.work_packages.get(wp_id, {})
        actual = actual_snapshot.work_packages.get(wp_id, {})
        for slot, legacy_value in sorted(row.claim_slots.items()):
            if slot in row.carrier_slots:
                if claim is None:
                    mismatches.append(
                        f"{wp_id}: raw claim-slot witness missing for {slot} "
                        "(deterministic claim seed absent)"
                    )
                elif raw.get(slot) != legacy_value:
                    mismatches.append(
                        f"{wp_id}: raw claim-slot witness for {slot} diverged"
                    )
            later_value = legitimate.get(slot)
            expected_value = (
                later_value
                if later_value is not None
                else legacy_value
            )
            if actual.get(slot) != expected_value:
                owner = (
                    "later legitimate writer"
                    if later_value is not None
                    else "legacy seed"
                )
                mismatches.append(
                    f"{wp_id}: reduced claim-slot witness for {slot} "
                    f"does not match {owner}"
                )
    return mismatches


def _has_snapshot_runtime(wp: dict[str, Any]) -> bool:
    """True iff a reduced-snapshot WP carries any runtime-slot value."""
    return any(
        wp.get(slot) not in (None, [], {})
        for slot in (
            "shell_pid",
            "shell_pid_created_at",
            "agent",
            "assignee",
            "tracker_refs",
            "subtasks",
            "review",
            "role",
            "agent_profile",
            "agent_profile_version",
            "model",
            "provider",
        )
    )


def _invocation_write_refusal(
    feature_dir: Path, intent: Intent, *, owned: OwnedMission | None = None,
) -> FailClosedRefusal | None:
    """Return the fail-closed refusal when *feature_dir*'s invoking checkout does
    not own the redirected path a WRITE-guarding verify is about to read (#3049).

    The false-green this closes (WP05 / FR-005): invoked from a foreign lane
    worktree, the cutover flow's :func:`verify_backfill` canonicalizes
    *feature_dir* to the primary/coord checkout — the deliberate C-003 write
    target — and then reads that same redirected path, so the cutover guard
    passes no matter which checkout invoked it.

    The guard is made invoking-checkout-aware WITHOUT moving the write target:

    * *intent* is :attr:`~specify_cli.core.checkout_identity.Intent.PRIMARY_READ`
      (the default for a bare, read-only verify such as the ``is_cut_over``
      doctor) — the invocation is only *reading* the deliberate primary anchor,
      never blessing a write from a checkout it must own, so it is NEVER refused
      (WP01 INV-2: ``write_refusal`` is silent for every ``PRIMARY_READ``).
    * When :func:`canonicalize_feature_dir` does NOT redirect the read
      (``canonical == feature_dir``), the invocation reads exactly the checkout
      it points at — the primary checkout, or an already-canonical *registered*
      coordination worktree — so it owns what it reads and proceeds unchanged
      (``None``; no new refusal on the owner path).
    * Only a WRITE-guarding verify (the cutover flow threads
      :attr:`~specify_cli.core.checkout_identity.Intent.WRITE`) whose read was
      redirected AND whose invoking checkout is a foreign lane worktree is
      refused fail-closed — the single #3128 write-refusal seam, whose message
      names the canonical target checkout it declined to bless (INV-5).

    Ownership is resolved from *feature_dir* itself (which carries the invoking
    checkout's root — it is built as ``<invoking-root>/kitty-specs/<slug>`` by
    the command that resolved the root), so the decision is independent of
    ``Path.cwd()`` and of the ``paths.py`` re-anchoring resolvers (WP01 INV-4).
    """
    if intent is not Intent.WRITE:
        return None
    canonical = _runtime_feature_dir(feature_dir, owned)
    if canonical == feature_dir:
        return None
    identity = resolve_checkout_identity(feature_dir, Intent.WRITE)
    return identity.write_refusal()


def verify_backfill(
    feature_dir: Path,
    *,
    read_dir: Path | None = None,
    intent: Intent = Intent.PRIMARY_READ,
    owned: OwnedMission | None = None,
) -> VerifyResult:
    """Fail-closed proof that OLD-reader values survive in deterministic seeds.

    Rebuilds the expected deterministic rows from the OLD frontmatter/checkbox
    reader (:func:`read_legacy_runtime`) and compares each exact typed payload to
    the raw event stream. The current reduced snapshot may legitimately be newer
    because runtime slots are latest-wins.

    Fail-closed:
        - a corrupt/unreadable event log -> ``ok=False`` (terminal);
        - any seed-payload, conflict, or count mismatch -> ``ok=False`` (terminal);
        - a frontmatter already stripped at verify time -> :class:`MigrationOrderingError`.

    The strip is a *downstream* step, never a precondition of verify.

    Args:
        feature_dir: kitty-specs mission directory — the event-log/snapshot
            anchor (claim anchors, the reduced snapshot, the raw event
            stream).
        read_dir: Optional distinct directory to read the legacy ``tasks/``
            frontmatter from (placement-port-residuals-closure-01KYDEF0
            FR-002 / IC-02 — mirrors :func:`backfill_runtime_state`'s
            read/write-leg split). Defaults to *feature_dir*.
        intent: Whether this verify guards a WRITE (the cutover flow — a foreign
            lane invocation that reads a redirected primary path is refused
            fail-closed, #3049 / WP05) or is a bare ``PRIMARY_READ`` (the
            default — a read-only verify such as the ``is_cut_over`` doctor,
            never refused). See :func:`_invocation_write_refusal`.
        owned: Explicit ownership to revalidate instead of redirecting to primary.

    Returns:
        A :class:`VerifyResult`; call :meth:`VerifyResult.raise_if_failed` (or use
        :func:`run_backfill_and_verify`) to turn a non-``ok`` result into an abort.
        A foreign-lane WRITE invocation returns a non-``ok`` result whose single
        mismatch is the checkout-naming refusal message.

    Raises:
        MigrationOrderingError: if verify is run after ``strip_mutable_fields``.
    """
    scope = {"owned": owned} if owned is not None else {}
    refusal = _invocation_write_refusal(feature_dir, intent, **scope)
    if refusal is not None:
        return VerifyResult(ok=False, wp_count=0, mismatches=(refusal.message(),))
    feature_dir = _runtime_feature_dir(feature_dir, owned)
    read_dir = _runtime_feature_dir(read_dir, owned) if read_dir is not None else feature_dir
    try:
        legacy = read_legacy_runtime(read_dir)
    except LegacyRuntimeReadError as exc:
        return VerifyResult(
            ok=False,
            wp_count=0,
            mismatches=(f"legacy runtime unreadable: {exc}",),
        )

    try:
        snapshot = materialize_snapshot(feature_dir)
    except StoreError as exc:
        return VerifyResult(ok=False, wp_count=0, mismatches=(f"event log unreadable: {exc}",))

    mismatches: list[str] = []
    # A WP is the backfill's responsibility to seed ONLY when it has a claim
    # anchor: a never-claimed WP (no transition events AND no synthesizable
    # frontmatter claim state) is skipped by _build_seed_events (warn, not
    # fail), so verify mirrors that skip via the same _resolve_anchor — an
    # anchor-less WP is never a count mismatch (Defect 1, spec Edge Case). A WP
    # whose anchor was synthesized from frontmatter (#2848) IS counted here —
    # that is precisely the case verify must stop treating as vacuous.
    anchors = _claim_anchors(feature_dir)
    seeded_wps = {
        wp_id
        for wp_id, runtime in legacy.items()
        if runtime.has_evictable_state() and _resolve_anchor(read_dir, wp_id, runtime, anchors)[0] is not None
    }

    # Count parity, DATA-LOSS direction: a seeded WP whose snapshot carries no
    # runtime at all.
    snapshot_runtime_wps = {wp_id for wp_id, wp in snapshot.work_packages.items() if _has_snapshot_runtime(wp)}
    for wp_id in sorted(seeded_wps - snapshot_runtime_wps):
        mismatches.append(f"{wp_id}: legacy carries runtime state but snapshot has none (count mismatch)")

    # Reverse direction is tolerant of the already-migrated / mid-migration state
    # (Defect 3): a WP whose snapshot carries runtime the legacy FRONTMATTER lacks
    # is valid IFF it still has a legacy WP row (a real WP file, its runtime merely
    # event-sourced now — the actively-running mission does exactly this). A
    # snapshot WP with NO legacy row at all (no WP file) is a phantom / injected
    # entry and is still caught fail-closed.
    legacy_wp_ids = set(legacy.keys())
    for wp_id in sorted(snapshot_runtime_wps - legacy_wp_ids):
        mismatches.append(f"{wp_id}: snapshot carries runtime state but no legacy WP row exists (phantom / injected)")

    # The legacy-derived values must exist exactly in their deterministic seed
    # rows. Compare those raw rows rather than the latest-wins snapshot value:
    # an already-active mission can legitimately carry a later reassignment.
    mismatches.extend(_verify_expected_seed_events(feature_dir, read_dir, legacy, anchors))
    expected_transitions, expected_annotations = _build_seed_events(
        feature_dir,
        read_dir,
        legacy,
        anchors,
        [],
    )
    mismatches.extend(
        _verify_compatibility_repairs(
            feature_dir,
            read_dir,
            legacy,
            expected_transitions,
            expected_annotations,
        )
    )
    # Independent of the seed builder: the denominator is read_legacy_runtime
    # output plus _resolve_seed_anchor, so a builder that suppresses claim
    # transitions cannot mask a missing raw claim seed (IC-02 / C-002).
    mismatches.extend(
        _verify_claim_slot_witnesses(
            feature_dir,
            read_dir,
            legacy,
            anchors,
        )
    )

    # Preserve the strip-order guard using deterministic seed provenance. Current
    # snapshot values may be ahead of legacy (even at the same timestamp), so
    # snapshot presence alone is not evidence that frontmatter was stripped.
    seeded_slots = _seeded_frontmatter_slots(feature_dir, read_dir, legacy_wp_ids)
    for wp_id in sorted(legacy_wp_ids):
        _assert_unstripped(wp_id, legacy[wp_id], seeded_slots[wp_id])

    return VerifyResult(ok=not mismatches, wp_count=len(seeded_wps), mismatches=tuple(mismatches))


def run_backfill_and_verify(feature_dir: Path, *, dry_run: bool = False) -> tuple[BackfillResult, VerifyResult]:
    """Run the pinned ``backfill -> verify(pre-strip, fail-closed)`` unit.

    This enforces the order by construction: it seeds, then verifies against the
    still-un-stripped frontmatter, and turns a non-``ok`` verify into a terminal
    :class:`BackfillVerificationError`. It never strips — the strip is a
    downstream step owned by the field verticals / WP10.

    Returns:
        ``(BackfillResult, VerifyResult)`` on success (verify ``ok``).

    Raises:
        BackfillVerificationError: on any count/value mismatch (fail-closed).
        MigrationOrderingError: if the frontmatter was stripped before verify.
    """
    backfill_result = backfill_runtime_state(feature_dir, dry_run=dry_run)
    if backfill_result.action == "error":
        raise BackfillVerificationError(
            backfill_result.reason or "backfill failed before verify"
        )
    verify_result = verify_backfill(feature_dir)
    verify_result.raise_if_failed()
    return backfill_result, verify_result


# ---------------------------------------------------------------------------
# T013: zero-reader verification for history[] / progress
# ---------------------------------------------------------------------------

#: Fields proven dead by the runtime-state eviction: no live reader anywhere
#: consumes them for a decision, so they are safe to delete (``history[]`` +
#: ``add_history_entry`` in WP07/T028; the ``progress`` field is already inert).
#: This module produces the *proof* (:func:`assert_zero_readers`); it performs no
#: deletion.
ZERO_READER_FIELDS = ("history", "progress")

#: Basenames carrying the ``history`` *writer* read-modify-write machinery
#: (``FrontmatterManager.add_history_entry`` + the ``WPMetadata`` merge
#: carry-forward). These touch ``history[]`` to *append*, never to consume it for
#: a decision, and are WP07/T028's to delete. They are excluded from the
#: zero-*reader* proof so the proof measures genuine consumers, not the doomed
#: writer. Once WP07/T028 removes them the exclusion becomes a no-op.
HISTORY_WRITER_SEAMS = frozenset({"frontmatter.py", "wp_metadata.py"})


def find_field_readers(
    src_root: Path,
    field_name: str,
    *,
    exclude_basenames: frozenset[str] = frozenset(),
) -> list[str]:
    """Return ``path:line`` sites that appear to *read* ``field_name`` from a mapping.

    A grep-style scan over ``*.py`` under ``src_root`` for frontmatter/metadata
    read patterns — ``["field"]`` / ``['field']`` / ``.get("field")`` / ``.field``
    attribute access. Write-only markers (``set_scalar``/``add_history_entry``/
    ``del``/``pop``) and the field-registry declarations
    (``MUTABLE_FIELDS``/``STATIC_FIELDS``/…) are NOT counted — this proves *no
    live reader*, not *no mention*. ``exclude_basenames`` drops whole files (e.g.
    the ``history`` writer seams WP07/T028 owns) from the audit.

    Used by :func:`assert_zero_readers` and the WP03 zero-reader tests to gate the
    eventual deletion (WP07/T028 for ``history[]``, WP10 for the fallbacks).
    """
    import re

    read_patterns = [
        re.compile(rf"""\[\s*["']{re.escape(field_name)}["']\s*\]"""),
        re.compile(rf"""\.get\(\s*["']{re.escape(field_name)}["']"""),
        re.compile(rf"""(?<![\w.])\.{re.escape(field_name)}\b"""),
    ]
    # Write seams / registry declarations that mention the field but do not read it.
    write_markers = (
        "set_scalar",
        "add_history_entry",
        "del ",
        ".pop(",
        "MUTABLE_FIELDS",
        "STATIC_FIELDS",
        "RETIRED_FIELDS",
        "ZERO_READER_FIELDS",
    )

    hits: list[str] = []
    self_path = Path(__file__).resolve()
    for py_file in sorted(src_root.rglob("*.py")):
        if py_file.resolve() == self_path or py_file.name in exclude_basenames:
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            # Module imports (``from .progress import …``) name a module, not a
            # frontmatter field read — never a live reader of the field.
            if stripped.startswith(("import ", "from ")):
                continue
            if any(marker in line for marker in write_markers):
                continue
            if any(pat.search(line) for pat in read_patterns):
                hits.append(f"{py_file}:{lineno}")
    return hits


def assert_zero_readers(
    src_root: Path,
    fields: tuple[str, ...] = ZERO_READER_FIELDS,
    *,
    exclude_basenames: frozenset[str] = HISTORY_WRITER_SEAMS,
) -> None:
    """Raise if any of *fields* still has a live *reader* under *src_root*.

    The proof that gates deletion of ``history[]`` (WP07/T028) and confirms
    ``progress`` is inert (FR-010). Non-vacuous: it fails loudly the moment a
    consumer is (re)introduced. By default the ``history`` writer seams
    (:data:`HISTORY_WRITER_SEAMS`) are excluded — they append, they do not consume
    — so the proof measures genuine readers. This function only *proves*; it
    deletes nothing.
    """
    offenders: dict[str, list[str]] = {}
    for field_name in fields:
        readers = find_field_readers(src_root, field_name, exclude_basenames=exclude_basenames)
        if readers:
            offenders[field_name] = readers
    if offenders:
        raise AssertionError(f"zero-reader verification failed; live readers found: {offenders}")


__all__ = [
    "BackfillResult",
    "MigrationOrderingError",
    "VerifyResult",
    "backfill_runtime_state",
    "read_legacy_runtime",
    "verify_backfill",
]
