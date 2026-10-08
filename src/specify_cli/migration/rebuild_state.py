"""Rebuild canonical event log from legacy artifacts.

This module holds the per-mission event-rebuild *implementation*. It is an
internal detail of the migration package: the single public seam is
:func:`specify_cli.migration.mission_state.rebuild_mission_event_log`
(#1754), which adapts this module's :class:`RebuildResult` down to a stable
count-shaped contract. New code must call the ``mission_state`` entry rather
than importing :func:`rebuild_event_log` directly.

Cross-validates ALL available sources (existing status.events.jsonl,
status.json snapshot, frontmatter ``lane`` fields) and produces a
reconciled, deduplicated, identity-enriched event log.

Existing event logs are NOT blindly trusted — they are reconciled
against other sources and corrective synthetic events are emitted for
contradictions.

For mid-flight features a full event chain is generated
(planned → claimed → in_progress → current_lane) so the history is
realistic rather than a single jump.

Determinism
-----------
As of Mission 8 (Priivacy-ai/spec-kitty#926, #930) this module is
deterministic: synthetic ``event_id`` values are derived from a sha256
seed over stable inputs (feature slug, WP code, from-lane, to-lane, and a
step index) rather than minted from a random ULID source, and synthetic
timestamps are anchored to ``_MIGRATION_EPOCH`` with explicit per-step
offsets instead of ``datetime.now()``. Two runs against the same legacy
fixture therefore produce byte-identical ``status.events.jsonl`` output.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import warnings
from dataclasses import dataclass, field
from kernel.clock import UTC, parse_iso
from pathlib import Path
from typing import Any, cast

from specify_cli.migration.canonicalization import (
    CanonicalRule,
    CanonicalStepResult,
    MigrationContext,
    apply_rules,
)
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.status import feature_status_lock, mission_lock_key
from specify_cli.workspace.root_resolver import resolve_status_lock_root

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministic ID generation (Mission 8)
# ---------------------------------------------------------------------------

# Crockford alphabet — matches ``mission_state._CROCKFORD`` so generated
# IDs from this legacy path are interchangeable with the canonical path.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _deterministic_id(*parts: str) -> str:
    """Return a 26-char Crockford ULID derived from *parts*.

    Hashes the joined parts with sha256 using ``|`` as the separator, then
    renders the first 16 digest bytes as a 26-char Crockford-base32 string.
    The same inputs always yield the same output, so synthetic events
    minted by this module are reproducible across runs.
    """
    seed = "|".join(parts).encode("utf-8")
    value = int.from_bytes(hashlib.sha256(seed).digest()[:16], "big")  # noqa: TID251 - production raw SHA-256 owner
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


# Compatibility shim retained because internal callers and tests may still
# import the symbol. Internally we always go through ``_deterministic_id``;
# this wrapper now returns a fixed deterministic value and warns on call.
def _generate_ulid() -> str:  # pragma: no cover - compatibility shim
    warnings.warn(
        "specify_cli.migration.rebuild_state._generate_ulid is deprecated; "
        "use _deterministic_id(...) with stable seed parts instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _deterministic_id("legacy", "_generate_ulid")


# ---------------------------------------------------------------------------
# Deterministic timestamp anchor (Mission 8)
# ---------------------------------------------------------------------------

# All synthetic events emitted by this module anchor their ``at`` field at
# this fixed epoch. The original per-step offset machinery in
# ``_make_migration_timestamp`` still spreads chain events backwards in
# time, but the *baseline* is no longer ``datetime.now(UTC)``.
_MIGRATION_EPOCH = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class RebuildResult:
    """Outcome of rebuilding the event log for a single feature."""

    feature_slug: str
    events_generated: int = 0        # Brand-new synthetic events created
    events_kept: int = 0             # Existing events preserved unchanged
    events_corrected: int = 0        # Existing events that were enriched / fixed
    conflicts_found: int = 0         # Source-level lane disagreements
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


# ---------------------------------------------------------------------------
# Lane ordering for realistic event chains
# ---------------------------------------------------------------------------

# Ordered list of lanes used to build a realistic history chain.
# "approved" is treated the same as "done" for legacy purposes.
_LANE_ORDER: list[str] = [
    "planned",
    "claimed",
    "in_progress",
    "for_review",
    "done",
]

_TERMINAL_LANES: frozenset[str] = frozenset({"done", "canceled", "approved"})

_VALID_LANES: frozenset[str] = frozenset(
    {"planned", "claimed", "in_progress", "for_review", "done", "blocked", "canceled", "approved"}
)


def _resolve_alias(lane: str) -> str:
    """Resolve legacy aliases to canonical lane names."""
    aliases = {
        "doing": "in_progress",
        "review": "for_review",
        "complete": "done",
        "cancelled": "canceled",
    }
    return aliases.get(lane.strip().lower(), lane.strip().lower())


def _make_migration_timestamp(base_ts: str, offset_seconds: int = 0) -> str:
    """Construct an ISO 8601 UTC timestamp, optionally offset from *base_ts*.

    Mission 8: when *base_ts* is unparseable we fall back to
    ``_MIGRATION_EPOCH`` instead of ``datetime.now(UTC)`` so the legacy
    rebuild path stays deterministic for any caller.
    """
    try:
        dt = parse_iso(base_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = parse_iso(_MIGRATION_EPOCH)
    if offset_seconds:
        from kernel.clock import timedelta
        dt = dt - timedelta(seconds=offset_seconds)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------


def _read_existing_events(feature_dir: Path) -> list[dict[str, Any]]:
    """Read raw event dicts from status.events.jsonl; return [] on error."""
    events_file = feature_dir / "status.events.jsonl"
    if not events_file.exists():
        return []
    results: list[dict[str, Any]] = []
    try:
        with events_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    results.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping corrupt event line in %s: %s", events_file, exc)
    except OSError as exc:
        logger.warning("Cannot read events file %s: %s", events_file, exc)
    return results


def _read_status_json(feature_dir: Path) -> dict[str, Any] | None:
    """Return the status.json snapshot dict or None if absent/corrupt."""
    status_file = feature_dir / "status.json"
    if not status_file.exists():
        return None
    try:
        with status_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Cannot read status.json in %s: %s", feature_dir, exc)
    return None


def _read_frontmatter_lanes(feature_dir: Path) -> dict[str, str]:
    """Return mapping of wp_code → canonical lane from WP frontmatter."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return {}
    lanes: dict[str, str] = {}
    try:
        from specify_cli.frontmatter import read_frontmatter
    except ImportError:
        return {}
    import re
    _WP_RE = re.compile(r"^(WP\d{2,})")
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        m = _WP_RE.match(wp_file.stem)
        if not m:
            continue
        wp_code = m.group(1)
        try:
            fm, _ = read_frontmatter(wp_file)
            raw_lane = fm.get("lane") or "planned"
            lanes[wp_code] = _resolve_alias(str(raw_lane))
        except Exception as exc:
            logger.debug("Cannot read frontmatter for %s: %s", wp_file.name, exc)
    return lanes


# ---------------------------------------------------------------------------
# Event deduplication
# ---------------------------------------------------------------------------


def _dedup_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove exact-duplicate event_id entries; keep first occurrence.

    Returns (deduplicated_events, dropped_count).
    """
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    dropped = 0
    for evt in events:
        eid = evt.get("event_id", "")
        if eid in seen:
            dropped += 1
        else:
            seen.add(eid)
            result.append(evt)
    return result, dropped


# ---------------------------------------------------------------------------
# Identity enrichment
# ---------------------------------------------------------------------------


def _enrich_event_identity(
    evt: dict[str, Any],
    feature_slug: str,
    wp_id_map: dict[str, str],
) -> tuple[dict[str, Any], bool]:
    """Backfill mission_slug / work_package_id fields if absent.

    Returns (enriched_dict, was_modified).
    """
    changed = False
    evt = dict(evt)  # shallow copy

    wp_code = evt.get("wp_id", "")
    if "work_package_id" not in evt and wp_code in wp_id_map:
        evt["work_package_id"] = wp_id_map[wp_code]
        changed = True

    if "mission_slug" not in evt:
        evt["mission_slug"] = feature_slug
        changed = True

    return evt, changed


# ---------------------------------------------------------------------------
# Synthetic event generation helpers
# ---------------------------------------------------------------------------


def _build_chain(
    wp_code: str,
    feature_slug: str,
    wp_id_map: dict[str, str],
    target_lane: str,
    migration_timestamp: str,
) -> list[dict[str, Any]]:
    """Build a realistic transition chain from planned to *target_lane*.

    If the target is 'planned' no events are emitted (it is the initial
    state).  For mid-flight WPs a chain like planned→claimed→in_progress
    is generated with the corrective synthetic final event.
    """
    if target_lane == "planned":
        return []

    # Build path through canonical lanes
    path: list[str] = ["planned"]
    if target_lane in _TERMINAL_LANES and target_lane in _LANE_ORDER:
        path = _LANE_ORDER[: _LANE_ORDER.index(min(
            (lane for lane in _LANE_ORDER if lane == target_lane or target_lane in ("done", "approved")),
            default=target_lane,
        )) + 1]
    else:
        # Walk through _LANE_ORDER up to target
        for lane in _LANE_ORDER:
            if lane != "planned":
                path.append(lane)
            if lane == target_lane:
                break
        else:
            # target_lane not in _LANE_ORDER (e.g. blocked/canceled)
            path = ["planned", "claimed", "in_progress", target_lane]

    # Fallback when target is done/approved
    if target_lane in ("done", "approved") and "done" not in path:
        path = _LANE_ORDER[:]

    work_package_id = wp_id_map.get(wp_code, "")
    events: list[dict[str, Any]] = []

    # Spread events backwards in time: oldest event is furthest in past
    step_seconds = 300  # 5 minutes between steps

    for i, (from_lane, to_lane) in enumerate(zip(path, path[1:], strict=False)):
        offset = (len(path) - 2 - i) * step_seconds
        ts = _make_migration_timestamp(migration_timestamp, offset_seconds=offset)
        evt: dict[str, Any] = {
            "event_id": _deterministic_id(
                feature_slug,
                wp_code,
                from_lane,
                to_lane,
                "chain",
                str(i),
            ),
            "mission_slug": feature_slug,
            "wp_id": wp_code,
            "from_lane": from_lane,
            "to_lane": to_lane,
            "at": ts,
            "actor": "migration",
            "force": True,
            "execution_mode": "unknown",
            "reason": "bootstrapped from legacy state",
            "review_ref": None,
            "evidence": None,
        }
        if work_package_id:
            evt["work_package_id"] = work_package_id
        events.append(evt)

    return events


# ---------------------------------------------------------------------------
# Deterministic per-fixture timestamp derivation (Mission 8)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Per-rule pure functions for _derive_migration_timestamp
# State type: tuple[Path, list[str]] — (feature_dir, candidates)
# Tactic: chain-of-responsibility-rule-pipeline (Transformer flavor),
#         refactoring-extract-first-order-concept
# ---------------------------------------------------------------------------

# Type alias for the state used by the timestamp-source pipeline.
_TimestampState = tuple[Path, list[str]]


def _rule_collect_event_timestamps(
    state: _TimestampState, _ctx: MigrationContext
) -> CanonicalStepResult[_TimestampState]:
    """Source 1: collect 'at' timestamps from status.events.jsonl."""
    feature_dir, candidates = state
    new_candidates = list(candidates)
    for evt in _read_existing_events(feature_dir):
        ts = evt.get("at")
        if isinstance(ts, str) and ts:
            new_candidates.append(ts)
    if new_candidates == candidates:
        return CanonicalStepResult.passthrough(state)
    return CanonicalStepResult(state=(feature_dir, new_candidates), actions=())


def _rule_collect_materialized_at(
    state: _TimestampState, _ctx: MigrationContext
) -> CanonicalStepResult[_TimestampState]:
    """Source 2: collect 'materialized_at' from status.json."""
    feature_dir, candidates = state
    new_candidates = list(candidates)
    status = _read_status_json(feature_dir)
    if status:
        ts = status.get("materialized_at")
        if isinstance(ts, str) and ts:
            new_candidates.append(ts)
    if new_candidates == candidates:
        return CanonicalStepResult.passthrough(state)
    return CanonicalStepResult(state=(feature_dir, new_candidates), actions=())


def _rule_collect_wp_last_transition(
    state: _TimestampState, _ctx: MigrationContext
) -> CanonicalStepResult[_TimestampState]:
    """Source 3: collect WP 'last_transition_at' values from status.json work_packages."""
    feature_dir, candidates = state
    new_candidates = list(candidates)
    status = _read_status_json(feature_dir)
    if status:
        for wp_state in (status.get("work_packages") or {}).values():
            if isinstance(wp_state, dict):
                ts = wp_state.get("last_transition_at")
                if isinstance(ts, str) and ts:
                    new_candidates.append(ts)
    if new_candidates == candidates:
        return CanonicalStepResult.passthrough(state)
    return CanonicalStepResult(state=(feature_dir, new_candidates), actions=())


def _rule_collect_meta_created_at(
    state: _TimestampState, _ctx: MigrationContext
) -> CanonicalStepResult[_TimestampState]:
    """Source 4: collect 'created_at' from meta.json."""
    feature_dir, candidates = state
    new_candidates = list(candidates)
    # post-#2091 silent contract: load_meta_or_empty absorbs a missing or
    # malformed meta.json to {}, matching the prior try/except-debug-log
    # absorption (ts stays None -> no candidate appended).
    meta = load_meta_or_empty(feature_dir)
    ts = meta.get("created_at")
    if isinstance(ts, str) and ts:
        new_candidates.append(ts)
    if new_candidates == candidates:
        return CanonicalStepResult.passthrough(state)
    return CanonicalStepResult(state=(feature_dir, new_candidates), actions=())


# Ordered source-collection rule tuple.
# Tactics: chain-of-responsibility-rule-pipeline (Transformer flavor)
# cast: each function matches CanonicalRule[_TimestampState] by structural subtyping;
# mypy cannot infer Protocol compliance from bare callables in a tuple literal.
_TIMESTAMP_SOURCE_RULES: tuple[CanonicalRule[_TimestampState], ...] = cast(
    "tuple[CanonicalRule[_TimestampState], ...]",
    (
        _rule_collect_event_timestamps,
        _rule_collect_materialized_at,
        _rule_collect_wp_last_transition,
        _rule_collect_meta_created_at,
    ),
)


def _derive_migration_timestamp(feature_dir: Path) -> str:
    """Return a deterministic ISO-8601 timestamp for synthetic events.

    Prefers, in order, the latest ``at`` timestamp present in
    ``status.events.jsonl``, the ``materialized_at`` and per-WP
    ``last_transition_at`` values in ``status.json``, and the
    ``created_at`` field in ``meta.json``. Falls back to
    ``_MIGRATION_EPOCH`` only when none of those produce a usable
    timestamp. The result is a pure function of *feature_dir* contents,
    so two rebuild runs over the same fixture produce identical
    timestamps (Mission 8).

    Delegates to :data:`_TIMESTAMP_SOURCE_RULES` via :func:`apply_rules`
    (Transformer-flavor rule pipeline, ``chain-of-responsibility-rule-pipeline``).
    """
    from kernel.clock import timedelta

    ctx = MigrationContext(mission_slug="", mission_id="", line_number=0)
    result = apply_rules(_TIMESTAMP_SOURCE_RULES, (feature_dir, []), ctx)
    candidates: list[str] = result.state[1] if result.state is not None else []
    if not candidates:
        return _MIGRATION_EPOCH
    # Sort lexicographically — ISO-8601 timestamps sort correctly that way.
    latest = max(candidates)
    # Bump by one second so synthetic corrective events are strictly later
    # than any real event we observed.
    try:
        dt = parse_iso(latest.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return _MIGRATION_EPOCH
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt + timedelta(seconds=1)).isoformat()


# ---------------------------------------------------------------------------
# Core rebuild logic
# ---------------------------------------------------------------------------


def rebuild_event_log(
    feature_dir: Path,
    feature_slug: str,
    wp_id_map: dict[str, str],
) -> RebuildResult:
    """Rebuild the canonical event log from all available legacy sources.

    Cross-validates existing ``status.events.jsonl``, ``status.json``, and
    frontmatter ``lane`` fields.  Produces a reconciled, deduplicated,
    identity-enriched event log.

    Family 9 of the writer census (mission ``fsm-write-path-integrity-01M1TZV6``
    WP07, ``design-notes/WP01-lock-rules.md`` addendum): the whole read ->
    reconcile -> atomic rewrite (``tmp.open("w")`` + ``os.replace``) runs
    under ONE acquisition of the mission status lock (L1) keyed on the mission
    directory name. A shell append that arrives while the rebuild runs waits
    on the lock and lands after the rewrite instead of being erased by it;
    locking only the ``os.replace`` would leave the read-to-write window open
    (WP01 rule: the idempotency read belongs inside the acquisition).

    * No ``nullcontext()`` degrade (conscious per-site choice): one-shot
      migration, lock cost irrelevant; ``resolve_status_lock_root`` never
      raises and the lock degrades to a deterministic per-tree file.
    * Lock timeout: the lock's default (unbounded). The only caller is the
      legacy-migration entry point in ``migration/mission_state.py``; neither
      the verdict-save queue (rule a) nor the merge sentinel (rule b) reaches
      it.
    * Nothing inside the critical section spawns git (NFR-001): the module
      only reads mission files and rewrites the log.

    Args:
        feature_dir: Path to the feature directory (e.g. ``kitty-specs/057-…``).
        feature_slug: Slug of the feature (e.g. ``"057-…"``).
        wp_id_map: Mapping of ``wp_code → work_package_id`` from identity
            backfill (WP12).  Used to enrich events that lack
            ``work_package_id``.

    Returns:
        :class:`RebuildResult` with counts and warnings for the feature.
    """
    lock_root = resolve_status_lock_root(feature_dir)
    with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
        return _rebuild_event_log_locked(feature_dir, feature_slug, wp_id_map)


def _rebuild_event_log_locked(  # noqa: C901
    feature_dir: Path,
    feature_slug: str,
    wp_id_map: dict[str, str],
) -> RebuildResult:
    """Body of :func:`rebuild_event_log`; the caller holds the mission lock.

    Pre-existing ``C901`` suppression carried over unchanged with the body
    (the six-step reconcile is above the ceiling on the WP07 base; splitting
    it is out of this WP's scope).
    """
    result = RebuildResult(feature_slug=feature_slug)
    # Mission 8: derive ``migration_ts`` from the latest stable timestamp
    # present in the legacy fixture rather than ``datetime.now(UTC)``. Two
    # runs over the same input therefore produce byte-identical synthetic
    # events. The fallback is the fixed ``_MIGRATION_EPOCH`` constant.
    migration_ts = _derive_migration_timestamp(feature_dir)

    # ------------------------------------------------------------------
    # Step 1: Read all sources
    # ------------------------------------------------------------------
    existing_events = _read_existing_events(feature_dir)
    status_json = _read_status_json(feature_dir)
    frontmatter_lanes = _read_frontmatter_lanes(feature_dir)
    # If there are no WPs and no event log → nothing to do
    if not existing_events and not frontmatter_lanes:
        result.skipped = True
        return result

    # ------------------------------------------------------------------
    # Step 2: Determine authoritative current lane per WP from all sources
    # ------------------------------------------------------------------

    # Collect lanes from status.json snapshot
    status_json_lanes: dict[str, str] = {}
    status_json_ts: str | None = None
    if status_json:
        status_json_ts = status_json.get("materialized_at")
        for wp_code, wp_state in status_json.get("work_packages", {}).items():
            if isinstance(wp_state, dict):
                raw = wp_state.get("lane", "planned")
                status_json_lanes[wp_code] = _resolve_alias(str(raw))

    # Collect lanes from event log terminal states.
    # Use the event with the NEWEST "at" timestamp per WP, not the last file position,
    # so that out-of-order appends (e.g. back-dated corrective events) are handled
    # correctly.
    event_log_lanes: dict[str, str] = {}
    event_log_ts: dict[str, str] = {}
    _wp_events: dict[str, list[dict[str, Any]]] = {}
    for evt in existing_events:
        wp_code = evt.get("wp_id", "")
        if wp_code:
            _wp_events.setdefault(wp_code, []).append(evt)
    for wp_code, wp_events in _wp_events.items():
        terminal_event = max(wp_events, key=lambda e: e.get("at", ""))
        event_log_lanes[wp_code] = _resolve_alias(terminal_event.get("to_lane", "planned"))
        event_log_ts[wp_code] = terminal_event.get("at", "")

    # Gather all known WPs
    all_wp_codes: set[str] = (
        set(frontmatter_lanes.keys())
        | set(status_json_lanes.keys())
        | set(event_log_lanes.keys())
    )

    # ------------------------------------------------------------------
    # Step 3: Resolve authoritative lane per WP, detect conflicts
    # ------------------------------------------------------------------
    authoritative_lanes: dict[str, str] = {}

    for wp_code in sorted(all_wp_codes):
        candidates: list[tuple[str, str, str | None]] = []  # (source, lane, timestamp)

        if wp_code in event_log_lanes:
            candidates.append(("event_log", event_log_lanes[wp_code], event_log_ts.get(wp_code)))

        if wp_code in status_json_lanes:
            candidates.append(("status_json", status_json_lanes[wp_code], status_json_ts))

        if wp_code in frontmatter_lanes:
            candidates.append(("frontmatter", frontmatter_lanes[wp_code], None))

        if not candidates:
            authoritative_lanes[wp_code] = "planned"
            continue

        unique_lanes = {c[1] for c in candidates}
        if len(unique_lanes) == 1:
            authoritative_lanes[wp_code] = candidates[0][1]
        else:
            # Conflict: pick the most-recently-timestamped source
            result.conflicts_found += 1
            # Sort by timestamp descending (None sorts last)
            candidates_with_ts = [
                (src, lane, ts) for src, lane, ts in candidates if ts
            ]
            if candidates_with_ts:
                candidates_with_ts.sort(key=lambda x: x[2], reverse=True)
                winner_src, winner_lane, winner_ts = candidates_with_ts[0]
            else:
                # All timestamps missing — prefer event_log > status_json > frontmatter
                pref_order = ["event_log", "status_json", "frontmatter"]
                winner_src, winner_lane = candidates[0][0], candidates[0][1]
                for pref in pref_order:
                    for src, lane, _ in candidates:
                        if src == pref:
                            winner_src, winner_lane = src, lane
                            break

            loser_sources = [f"{src}={ln}" for src, ln, _ in candidates if src != winner_src]
            msg = (
                f"{feature_slug}/{wp_code}: lane conflict "
                f"({', '.join(loser_sources)} vs {winner_src}={winner_lane}). "
                f"Using {winner_src}."
            )
            logger.warning(msg)
            result.warnings.append(msg)
            authoritative_lanes[wp_code] = winner_lane

    # ------------------------------------------------------------------
    # Step 4: Dedup and identity-enrich existing events
    # ------------------------------------------------------------------
    existing_events, dropped = _dedup_events(existing_events)
    if dropped:
        result.warnings.append(f"Dropped {dropped} duplicate events (same event_id).")

    enriched_events: list[dict[str, Any]] = []
    corrections = 0
    for evt in existing_events:
        enriched, changed = _enrich_event_identity(evt, feature_slug, wp_id_map)
        enriched_events.append(enriched)
        if changed:
            corrections += 1
    result.events_corrected += corrections
    result.events_kept = len(enriched_events)

    # ------------------------------------------------------------------
    # Step 5: Check whether the event log's terminal state for each WP
    #         matches the authoritative lane; emit corrective events if not
    # ------------------------------------------------------------------
    corrective_events: list[dict[str, Any]] = []

    for wp_code, auth_lane in sorted(authoritative_lanes.items()):
        log_lane = event_log_lanes.get(wp_code)

        if log_lane is not None and log_lane == auth_lane:
            # Event log is consistent — nothing to do
            continue

        if log_lane is not None and log_lane != auth_lane:
            # Contradiction: emit a corrective synthetic event
            msg = (
                f"{feature_slug}/{wp_code}: event log says '{log_lane}' "
                f"but authoritative source says '{auth_lane}'. "
                "Emitting corrective synthetic event."
            )
            logger.warning(msg)
            result.warnings.append(msg)

            work_package_id = wp_id_map.get(wp_code, "")
            corrective_evt: dict[str, Any] = {
                "event_id": _deterministic_id(
                    feature_slug,
                    wp_code,
                    log_lane or "",
                    auth_lane,
                    "corrective",
                ),
                "mission_slug": feature_slug,
                "wp_id": wp_code,
                "from_lane": log_lane,
                "to_lane": auth_lane,
                "at": migration_ts,
                "actor": "migration",
                "force": True,
                "execution_mode": "unknown",
                "reason": "reconciled from authoritative source",
                "review_ref": None,
                "evidence": None,
            }
            if work_package_id:
                corrective_evt["work_package_id"] = work_package_id
            corrective_events.append(corrective_evt)
            result.events_corrected += 1

        elif log_lane is None:
            # No event log entry for this WP — generate synthetic chain
            chain = _build_chain(
                wp_code=wp_code,
                feature_slug=feature_slug,
                wp_id_map=wp_id_map,
                target_lane=auth_lane,
                migration_timestamp=migration_ts,
            )
            if chain:
                corrective_events.extend(chain)
                result.events_generated += len(chain)

    # ------------------------------------------------------------------
    # Step 6: Write the reconciled event log atomically
    # ------------------------------------------------------------------
    final_events = enriched_events + corrective_events

    if not final_events:
        # Nothing to write — feature may genuinely have no transitions
        result.skipped = True
        return result

    events_file = feature_dir / "status.events.jsonl"
    tmp_file = feature_dir / "status.events.jsonl.tmp"

    try:
        feature_dir.mkdir(parents=True, exist_ok=True)
        with tmp_file.open("w", encoding="utf-8") as fh:
            for evt in final_events:
                fh.write(json.dumps(evt, sort_keys=True) + "\n")
        os.replace(str(tmp_file), str(events_file))
    except OSError as exc:
        msg = f"Failed to write event log for {feature_slug}: {exc}"
        logger.error(msg)
        result.errors.append(msg)
        if tmp_file.exists():
            with contextlib.suppress(OSError):
                tmp_file.unlink()
        return result
    finally:
        if tmp_file.exists():
            with contextlib.suppress(OSError):
                tmp_file.unlink()

    return result
