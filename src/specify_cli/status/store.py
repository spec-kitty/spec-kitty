"""JSONL event store for status events.

Provides append-only persistence of StatusEvent records to a JSONL file
(status.events.jsonl). Each line is a JSON object with deterministic
(sorted) key ordering.

Back-compat reader (T024, FR-023):
    Events written before WP05 carry only ``mission_slug`` for mission
    identity. Events written after WP05 carry both ``mission_slug`` AND
    ``mission_id`` (a ULID from meta.json).

    The :func:`read_events` reader tolerates both shapes and resolves the
    ``mission_id`` for legacy events by reading the corresponding
    ``meta.json`` file. The slug→mission_id mapping is cached per call
    inside ``_SlugResolver`` to avoid repeated disk reads.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kernel.paths import is_windows
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import (
    MissionMetaReadError,
    assert_safe_path_segment,
    load_meta_fail_closed,
)
from specify_cli.core.utils import ensure_within_any
from specify_cli.events import sanitize_event_for_log

from .models import EventStream, InnerStateChanged, StatusEvent

#: Wire discriminator for off-axis runtime-state annotation events
#: (``InnerStateChanged``). These are surfaced to ``reduce()`` — never
#: skip-and-dropped — and are decoded by ``InnerStateChanged.from_dict``,
#: never ``StatusEvent.from_dict``.
ANNOTATION_KIND = "annotation"

logger = logging.getLogger(__name__)

EVENTS_FILENAME = "status.events.jsonl"

# Regex patterns for identity classification (T024)
_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_MISSION_SLUG_PATTERN = re.compile(r"^\d{3}-[a-z0-9-]+$")
_WP_ID_PATTERN = re.compile(r"^WP\d+$")


class StoreError(Exception):
    """Raised when the event store encounters corruption or I/O errors."""


class EventPersistenceError(StoreError):
    """Raised when an appended transition cannot be verified by readback."""

    def __init__(
        self,
        *,
        problem: str,
        feature_dir: Path,
        expected: StatusEvent,
    ) -> None:
        self.problem = problem
        self.feature_dir = feature_dir
        self.event_path = _events_path(feature_dir)
        self.expected_event_id = expected.event_id
        self.mission_slug = expected.mission_slug
        self.mission_id = expected.mission_id
        self.wp_id = expected.wp_id
        self.target_lane = str(expected.to_lane)
        mission_id_text = self.mission_id or "unknown"
        super().__init__(
            "Status transition event persistence verification failed: "
            f"{problem}; mission_slug={self.mission_slug}; "
            f"mission_id={mission_id_text}; wp_id={self.wp_id}; "
            f"target_lane={self.target_lane}; event_id={self.expected_event_id}; "
            f"event_path={self.event_path}"
        )

    def to_diagnostic(self) -> dict[str, str | None]:
        """Return the contract-required structured diagnostic payload."""
        return {
            "error": str(self),
            "diagnostic_code": "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED",
            "violated_invariant": "STA-002",
            "remediation": (
                "Inspect status_events_path for filesystem errors or event log "
                "corruption, then rerun the transition command after local "
                "status persistence is healthy."
            ),
            "mission_slug": self.mission_slug,
            "mission_id": self.mission_id,
            "work_package_id": self.wp_id,
            "wp_id": self.wp_id,
            "to_lane": self.target_lane,
            "requested_lane": self.target_lane,
            "event_id": self.expected_event_id,
            "status_events_path": str(self.event_path),
        }


def _events_path(feature_dir: Path) -> Path:
    """Return the canonical path to the events JSONL file."""
    return feature_dir / EVENTS_FILENAME


class _SlugResolver:
    """Cache-backed slug → mission_id resolver.

    Reads ``meta.json`` from the kitty-specs directory alongside the
    event log to resolve a legacy ``mission_slug`` to its canonical
    ``mission_id`` (ULID).  Results are cached in memory to avoid
    repeated disk reads within a single :func:`read_events` call.

    Orphaned slugs (whose meta.json does not exist or does not contain
    a ``mission_id``) are logged as a warning and return ``None``.
    """

    def __init__(self, feature_dir: Path) -> None:
        # feature_dir is the directory that owns status.events.jsonl.
        # The slug→dir mapping uses sibling kitty-specs directories.
        self._feature_dir = feature_dir
        self._mission_specs_root: Path | None = self._find_mission_specs_root()
        self._cache: dict[str, str | None] = {}

    def _find_mission_specs_root(self) -> Path | None:
        """Resolve the kitty-specs root that owns this feature dir's siblings.

        This is a **feature-dir-relative** lookup, NOT a canonical-repo-root
        resolution: ``_SlugResolver`` reads *sibling* missions' ``meta.json`` from
        the same ``kitty-specs/`` directory that contains ``self._feature_dir``.
        Anchoring on ``feature_dir`` (rather than ``resolve_canonical_root``) is
        both correct for that purpose and CWD-invariant (pure path arithmetic on
        the given feature dir). It also stays robust when the feature dir is not
        inside a git repo (offline repair, orphaned events, bare-dir fixtures) —
        where the canonical-root resolver would jump to an unrelated repo root and
        miss the co-located ``meta.json`` (post-merge regression fix; the genuine
        lock-anchor sites — emit/wpl/lifecycle — remain on ``resolve_canonical_root``).
        """
        candidate = self._feature_dir.parent
        if candidate.name == KITTY_SPECS_DIR:
            return candidate
        two_up = candidate.parent
        if two_up.name == KITTY_SPECS_DIR:
            return two_up
        return candidate

    @staticmethod
    def _is_safe_slug(mission_slug: str) -> bool:
        """Return True when *mission_slug* is a safe single path segment.

        The slug is UNTRUSTED — it flows straight out of a ``status.events.jsonl``
        event record (``mission_slug`` / ``feature_slug``). Delegates to the
        canonical ``assert_safe_path_segment`` guard (the same one the sibling
        ``aggregate._validate_mission_slug`` uses) so a traversal slug such as
        ``"../../../../tmp/evil"`` can never build a ``meta_path`` outside the
        specs root. On rejection this logs a warning and returns False so the
        caller can fail closed (return None) rather than raise.
        """
        try:
            assert_safe_path_segment(mission_slug)
        except ValueError as exc:
            logger.warning(
                "Refusing to resolve unsafe mission_slug %r (traversal guard); mission_id will be None: %s",
                mission_slug,
                exc,
            )
            return False
        return True

    def _is_contained(self, mission_slug: str, meta_path: Path) -> bool:
        """Return True when *meta_path* resolves inside the specs root.

        The segment grammar (``_is_safe_slug``) rejects ``..`` and separators, but
        a grammar-valid slug can still name a **symlink directory** under the specs
        root whose target lives elsewhere — the composed ``meta_path`` would then
        ``resolve()`` outside the root and read an attacker-controlled file. The
        canonical ``ensure_within_any`` seam (C-002) catches this by validating the
        *resolved* path against the trusted root.

        ``roots`` is **keyword-only**: the positional form would raise ``TypeError``
        and the containment would silently never run. The logical (un-resolved)
        ``_mission_specs_root`` is passed deliberately — ``ensure_within_any``
        resolves both sides with ``resolve(strict=False)``, so a legitimate slug
        under a *symlinked* specs root still validates (NFR-003, no macOS false
        reject) while a symlink escaping the root is rejected.

        Fail-closed (C-004): on ``ValueError`` return False (the caller returns
        ``None``), logging at most one WARNING per distinct slug — the caller caches
        the result so a repeated bad slug is neither re-checked nor re-warned
        (NFR-004).
        """
        root = self._mission_specs_root
        if root is None:  # pragma: no cover - guarded by caller
            return False
        try:
            ensure_within_any(meta_path, roots=[root])
        except ValueError as exc:
            logger.warning(
                "Refusing to resolve mission_slug %r: composed meta path escapes the specs root (symlink/containment guard); mission_id will be None: %s",
                mission_slug,
                exc,
            )
            return False
        return True

    def resolve(self, mission_slug: str) -> str | None:
        """Return the mission_id for *mission_slug*, or None if unresolvable.

        Reads ``<mission_specs_root>/<mission_slug>/meta.json`` and extracts
        the ``mission_id`` field.  Returns None if the file is missing,
        the field is absent, or JSON is malformed (logs a warning).
        """
        if mission_slug in self._cache:
            return self._cache[mission_slug]

        if not self._is_safe_slug(mission_slug):
            # Fail-closed: a hostile/corrupt slug (e.g. "../../etc") must never
            # build a path that escapes the specs root. Cache the None result so
            # the same bad slug is not re-validated on subsequent events.
            self._cache[mission_slug] = None
            return None

        mission_id: str | None = None
        if self._mission_specs_root is not None:
            meta_path = self._mission_specs_root / mission_slug / "meta.json"
            if not self._is_contained(mission_slug, meta_path):
                # Fail-closed: the slug passed the segment grammar but the composed
                # path still escapes the specs root — e.g. ``mission_slug`` names a
                # *symlink directory* under the root whose target lives elsewhere
                # (FR-002, IC-01). The grammar gate cannot see this; resolved-path
                # containment can. Cache None so the same bad slug is not re-checked
                # nor re-warned (NFR-004).
                self._cache[mission_slug] = None
                return None
            if meta_path.exists():
                try:
                    # FR-007: fail-closed reader routing. Malformed meta surfaces
                    # typed MissionMetaReadError instead of raw ValueError.
                    data = load_meta_fail_closed(meta_path.parent)
                except (OSError, MissionMetaReadError) as exc:
                    logger.warning(
                        "Could not read meta.json for slug %r: %s",
                        mission_slug,
                        exc,
                    )
                else:
                    if isinstance(data, dict):
                        mission_id = data.get("mission_id") or None
            else:
                logger.warning(
                    "No meta.json found for mission_slug %r (orphaned event); mission_id will be None for these events",
                    mission_slug,
                )

        self._cache[mission_slug] = mission_id
        return mission_id


def _resolve_mission_id_from_dict(
    raw: dict[str, Any],
    resolver: _SlugResolver,
) -> str | None:
    """Resolve the canonical mission_id from a raw event dict.

    Strategy (T024):
    1. If the event already carries ``mission_id`` (new-format), use it.
    2. If ``aggregate_id`` looks like a ULID, treat it as ``mission_id``.
    3. If ``mission_slug`` / ``feature_slug`` is present, resolve via meta.json.
    4. Return None for unresolvable events (caller logs/skips as appropriate).
    """
    # New-format event: mission_id field present directly
    if raw.get("mission_id"):
        return str(raw["mission_id"])

    # Legacy path: try to resolve from mission_slug
    slug = raw.get("mission_slug") or raw.get("feature_slug") or ""
    if slug:
        return resolver.resolve(slug)

    return None


def append_event(feature_dir: Path, event: StatusEvent) -> None:
    """Atomically append a StatusEvent as a single JSON line.

    Creates parent directories and the file if they do not exist.
    Uses ``sort_keys=True`` for deterministic key ordering.
    """
    path = _events_path(feature_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_event_for_log(event.to_dict())
    line = json.dumps(sanitized, sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _event_matches_expected(actual: StatusEvent, expected: StatusEvent) -> bool:
    """Return True when *actual* is durable evidence for *expected*."""
    if actual.event_id != expected.event_id:
        return False
    if actual.mission_slug != expected.mission_slug:
        return False
    if expected.mission_id is not None and actual.mission_id != expected.mission_id:
        return False
    return bool(actual.wp_id == expected.wp_id and actual.to_lane == expected.to_lane)


def verify_event_readback(feature_dir: Path, expected: StatusEvent) -> None:
    """Fail unless the expected event can be read back from JSONL."""
    try:
        events = read_events(feature_dir)
    except Exception as exc:
        raise EventPersistenceError(
            problem=f"readback failed: {exc}",
            feature_dir=feature_dir,
            expected=expected,
        ) from exc

    if not any(_event_matches_expected(actual, expected) for actual in events):
        raise EventPersistenceError(
            problem="expected event missing after append",
            feature_dir=feature_dir,
            expected=expected,
        )


def append_event_verified(feature_dir: Path, event: StatusEvent) -> None:
    """Append one event and require a successful post-write readback."""
    try:
        append_event(feature_dir, event)
    except Exception as exc:
        raise EventPersistenceError(
            problem=f"append failed: {exc}",
            feature_dir=feature_dir,
            expected=event,
        ) from exc
    verify_event_readback(feature_dir, event)


def append_primary_checkout_event_verified(feature_dir: Path, event: StatusEvent) -> None:
    """Append one event to the primary-checkout event log.

    Coordination worktree callers must not use this helper; they route through
    ``coordination.status_service.EventLogWriteContract`` instead.
    """
    append_event_verified(feature_dir, event)


def append_raw_rows_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomically append pre-serialized event dicts as sanitized JSONL lines.

    Public, envelope-agnostic promotion of the write-ahead-then-atomic-rename
    primitive (F2-T1, F2.md section 3.3): read existing text, append the new
    sanitized rows, and ``os.replace`` a temp file so crash recovery never
    observes a half-written batch. Takes an explicit *path* rather than a
    ``feature_dir`` so it can serve as the single durability mechanism for
    BOTH ``status.events.jsonl`` (mission-scoped, inside a ``feature_dir``)
    and ``.kittify/canonical-events.jsonl`` (project-scoped, not inside any
    ``feature_dir``) -- F2.md section 3.1 item 3 names this as the intent a
    ``feature_dir``-only signature cannot satisfy.

    No behavior change for existing ``StatusEvent`` callers: they continue to
    call the private :func:`_append_serialized_atomic` wrapper below, which
    computes the identical ``feature_dir / EVENTS_FILENAME`` path and
    delegates here.
    """
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_text_without_following_symlinks(path)
    if existing and not existing.endswith("\n"):
        existing += "\n"

    additions = "".join(json.dumps(sanitize_event_for_log(row), sort_keys=True) + "\n" for row in rows)
    fd, raw_tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(raw_tmp_path)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(existing)
            fh.write(additions)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        replaced = True
        _fsync_directory(path.parent)
    finally:
        if not replaced:
            tmp_path.unlink(missing_ok=True)


def _append_serialized_atomic(feature_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Thin, behavior-preserving wrapper over :func:`append_raw_rows_atomic`.

    Existing ``StatusEvent``/``InnerStateChanged`` callers keep calling this
    private name with a ``feature_dir``; it resolves the identical
    ``feature_dir / EVENTS_FILENAME`` path :func:`_events_path` always
    computed and delegates to the public, path-parameterized primitive. No
    on-disk behavior change (F2-T1, F2.md section 3.3).
    """
    append_raw_rows_atomic(_events_path(feature_dir), rows)


def _fsync_directory(directory: Path) -> None:
    """Persist an atomic rename's directory entry on supported platforms."""
    if is_windows():
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    dir_fd = os.open(directory, flags)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _read_text_without_following_symlinks(path: Path) -> str:
    """Read an existing event log without following its final path component."""
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow == 0 and path.is_symlink():
        raise StoreError(f"Refusing to read symbolic link event log: {path}")
    try:
        fd = os.open(path, os.O_RDONLY | no_follow)
    except FileNotFoundError:
        return ""
    except OSError as exc:
        if path.is_symlink():
            raise StoreError(f"Refusing to read symbolic link event log: {path}") from exc
        raise
    with os.fdopen(fd, "r", encoding="utf-8") as fh:
        return fh.read()


def append_events_atomic(feature_dir: Path, events: list[StatusEvent]) -> None:
    """Atomically persist a batch of StatusEvents as JSONL lines.

    The existing single-event append remains the compatibility path. Composite
    lifecycle operations use this helper so crash recovery never observes only
    half of a logical operation such as ``planned -> claimed -> in_progress``.
    """
    _append_serialized_atomic(feature_dir, [event.to_dict() for event in events])


def append_annotations_atomic_verified(
    feature_dir: Path,
    annotations: list[InnerStateChanged],
) -> None:
    """Durably append off-axis ``InnerStateChanged`` annotations and verify.

    Mirrors :func:`append_events_atomic_verified` (the durability-verified
    path) for the annotation partition: it appends atomically, then requires
    every annotation to read back through :func:`read_event_stream` (the
    annotation-aware read path — ``StatusEvent``'s ``to_lane``-keyed readback
    cannot see an annotation). Raises :class:`StoreError` if the batch cannot
    be appended or an appended annotation is missing on readback.
    """
    if not annotations:
        return
    try:
        _append_serialized_atomic(feature_dir, [a.to_dict() for a in annotations])
    except Exception as exc:
        raise StoreError(f"annotation append failed: {exc}") from exc

    persisted_ids = {a.event_id for a in read_event_stream(feature_dir).annotations}
    for annotation in annotations:
        if annotation.event_id not in persisted_ids:
            raise StoreError(f"annotation {annotation.event_id} missing after append (readback failed)")


def append_event_stream_atomic_verified(
    feature_dir: Path,
    events: list[StatusEvent | InnerStateChanged],
) -> None:
    """Atomically append a mixed transition/annotation unit and verify it.

    Claim operations use this seam when a lane transition and its resolved
    binding annotation must become durable together. A single ``os.replace``
    prevents observers from seeing the claim without its actual binding.
    """
    if not events:
        return
    expected_transition = next(
        (event for event in events if isinstance(event, StatusEvent)),
        None,
    )
    try:
        _append_serialized_atomic(feature_dir, [event.to_dict() for event in events])
    except Exception as exc:
        if expected_transition is not None:
            raise EventPersistenceError(
                problem=f"append failed: {exc}",
                feature_dir=feature_dir,
                expected=expected_transition,
            ) from exc
        raise StoreError(f"event-stream append failed: {exc}") from exc

    stream = read_event_stream(feature_dir)
    persisted_annotation_ids = {annotation.event_id for annotation in stream.annotations}
    for event in events:
        if isinstance(event, StatusEvent):
            verify_event_readback(feature_dir, event)
        elif event.event_id not in persisted_annotation_ids:
            raise StoreError(f"annotation {event.event_id} missing after mixed append (readback failed)")


def append_events_atomic_verified(feature_dir: Path, events: list[StatusEvent]) -> None:
    """Atomically append a batch and require every event to be readable."""
    if not events:
        return
    try:
        append_events_atomic(feature_dir, events)
    except Exception as exc:
        raise EventPersistenceError(
            problem=f"append failed: {exc}",
            feature_dir=feature_dir,
            expected=events[0],
        ) from exc
    for event in events:
        verify_event_readback(feature_dir, event)


def append_primary_checkout_events_atomic_verified(
    feature_dir: Path,
    events: list[StatusEvent],
) -> None:
    """Append a batch to the primary-checkout event log."""
    append_events_atomic_verified(feature_dir, events)


def read_events_raw(feature_dir: Path) -> list[dict[str, Any]]:
    """Read raw JSON dicts from the events file.

    Returns an empty list when the file does not exist.
    Blank lines are silently skipped.
    Raises :class:`StoreError` on invalid JSON, including the 1-based
    line number in the message.
    """
    path = _events_path(feature_dir)
    if not path.exists():
        return []

    results: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise StoreError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(obj, dict):
                raise StoreError(f"Invalid event structure on line {line_number}: expected JSON object")
            results.append(obj)
    return results


# Registration point: any new non-lane lifecycle event that uses the "type"
# envelope shape MUST be added here, or both read_events and
# `doctor mission-state --fix` will fail loudly on that mission with
# "missing required to_lane" (the SNAPSHOT_DRIFT symptom from issue #1782).
_RETROSPECTIVE_LIFECYCLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "RetrospectiveCaptured",
        "RetrospectiveCaptureFailed",
        "RetrospectiveSkipped",
    }
)


def is_retrospective_lifecycle_event(obj: Mapping[str, Any]) -> bool:
    """Return True for retrospective lifecycle rows using the ``type`` envelope.

    These rows are written to status.events.jsonl by design (see
    contracts/retrospective-events.contract.md) and read back by
    retrospective consumers; they are descriptive lifecycle events, not
    lane transitions, and must be skipped in place — never removed.
    """
    event_type = obj.get("type")
    return isinstance(event_type, str) and event_type in _RETROSPECTIVE_LIFECYCLE_EVENT_TYPES


def is_non_lane_event(obj: dict[str, Any]) -> bool:
    """Return True for non-lane events that intentionally share the JSONL file."""
    # InnerStateChanged annotations are NOT skip-and-dropped: they are surfaced
    # to reduce() via the annotation read path. This explicit branch is placed
    # FIRST (before the ``event_type`` presence-skip below) so that even if a
    # future annotation envelope grows an ``event_type`` key, the annotation can
    # never be silently re-skipped (FR-001 discriminator reconciliation).
    if obj.get("kind") == ANNOTATION_KIND:
        return False

    event_name = obj.get("event_name")
    if isinstance(event_name, str) and event_name.startswith("retrospective."):
        return True

    # WP03: Skip the three new canonical retrospective lifecycle events which use
    # a "type" field (not "event_name") per contracts/retrospective-events.contract.md.
    # These are descriptive lifecycle events, not lane transitions.
    if is_retrospective_lifecycle_event(obj):
        return True

    # Why: Skip mission-level events (DecisionPointOpened,
    # DecisionPointResolved, DecisionPointDeferred,
    # DecisionPointCanceled, DecisionPointWidened, and any future
    # event-type written by a non-status-emitter subsystem) that
    # share status.events.jsonl with lane-transition events.
    # Two cooperating subsystems write to this file with incompatible
    # schemas: the status emitter writes lane-transition events
    # (carrying wp_id, from_lane, to_lane), while the Decision Moment
    # Protocol writes mission-level events that carry a top-level
    # `event_type` field instead. Discriminating on event_type
    # PRESENCE (not a specific value allowlist) is future-proof AND
    # preserves the existing fail-loud contract for malformed
    # lane-transition events: a corrupted lane event missing wp_id
    # but ALSO missing event_type still hits StatusEvent.from_dict
    # below and raises as today. See FR-010.
    return "event_type" in obj


def _partition_event_stream_from_text(feature_dir: Path, content: str) -> EventStream:
    """Deserialize JSONL text into an :class:`EventStream`.

    Partitions each line by its wire discriminator:

    - ``kind == "annotation"`` decodes via :meth:`InnerStateChanged.from_dict`
      into the ``annotations`` list (never through ``StatusEvent.from_dict``,
      which hard-requires ``from_lane``/``to_lane``).
    - retrospective / decision (non-lane) events are skipped in place.
    - everything else decodes as a lane ``StatusEvent`` (with ``mission_id``
      back-fill for legacy rows) into the ``transitions`` list.

    A dict carrying an unknown ``kind`` value is a hard error (fail loud — a
    silent skip would lose runtime state). Handles both legacy events
    (``mission_slug`` only) and new events (``mission_slug`` + ``mission_id``).

    Blank lines are silently skipped. Raises :class:`StoreError` on invalid
    JSON **or** invalid event structure, including the 1-based line number.
    """
    resolver = _SlugResolver(feature_dir)
    transitions: list[StatusEvent] = []
    annotations: list[InnerStateChanged] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise StoreError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(obj, dict):
            raise StoreError(f"Invalid event structure on line {line_number}: expected JSON object")

        kind = obj.get("kind")
        if kind is not None:
            if kind == ANNOTATION_KIND:
                try:
                    annotations.append(InnerStateChanged.from_dict(obj))
                except (KeyError, ValueError, TypeError) as exc:
                    raise StoreError(f"Invalid event structure on line {line_number}: {exc}") from exc
                continue
            # An unknown kind is never silently skipped — fail loud.
            raise StoreError(f"Unknown event kind {kind!r} on line {line_number}")

        if is_non_lane_event(obj):
            continue

        try:
            # Resolve mission_id from the raw dict before parsing,
            # so that from_dict() receives it even for legacy events.
            resolved_mission_id = _resolve_mission_id_from_dict(obj, resolver)
            if resolved_mission_id is not None and "mission_id" not in obj:
                # Inject resolved value so from_dict() populates the field
                obj = {**obj, "mission_id": resolved_mission_id}
            event = StatusEvent.from_dict(obj)
        except (KeyError, ValueError, TypeError) as exc:
            raise StoreError(f"Invalid event structure on line {line_number}: {exc}") from exc
        transitions.append(event)
    return EventStream(transitions=transitions, annotations=annotations)


def read_events_from_text(feature_dir: Path, content: str) -> list[StatusEvent]:
    """Deserialize lane ``StatusEvent`` objects from JSONL text.

    Backward-compatible transitions-only view. Off-axis ``annotation`` events
    are partitioned out and NOT returned here — use
    :func:`read_event_stream_from_text` when the annotations are needed.

    Handles both legacy events (``mission_slug`` only) and new events
    (``mission_slug`` + ``mission_id``).  For legacy events, the
    ``mission_id`` is resolved from the corresponding ``meta.json`` via
    the slug resolver (cached per call).

    Blank lines are silently skipped.
    Raises :class:`StoreError` on invalid JSON **or** invalid event
    structure, including the 1-based line number in the message.
    """
    return _partition_event_stream_from_text(feature_dir, content).transitions


def read_event_stream_from_text(feature_dir: Path, content: str) -> EventStream:
    """Deserialize JSONL text into an :class:`EventStream` (transitions +
    annotations). Same parsing semantics as :func:`read_events_from_text`,
    but surfaces the off-axis ``annotation`` events instead of dropping them.
    """
    return _partition_event_stream_from_text(feature_dir, content)


def read_events(feature_dir: Path) -> list[StatusEvent]:
    """Read and deserialize lane ``StatusEvent`` objects from the events file.

    Backward-compatible transitions-only view (off-axis ``annotation`` events
    are partitioned out). Use :func:`read_event_stream` when the reducer needs
    the annotations too.

    Handles both legacy events (``mission_slug`` only) and new events
    (``mission_slug`` + ``mission_id``).  For legacy events, the
    ``mission_id`` is resolved from the corresponding ``meta.json`` via
    the slug resolver (cached per call).

    Returns an empty list when the file does not exist.
    Blank lines are silently skipped.
    Raises :class:`StoreError` on invalid JSON **or** invalid event
    structure, including the 1-based line number in the message.
    """
    path = _events_path(feature_dir)
    if not path.exists():
        return []

    return read_events_from_text(feature_dir, path.read_text(encoding="utf-8"))


def read_event_stream(feature_dir: Path) -> EventStream:
    """Read the events file into an :class:`EventStream`.

    This is the annotation-aware read path the reducer uses: it surfaces both
    lane ``transitions`` and off-axis ``annotations`` to ``reduce()`` without
    changing the on-disk file. Returns an empty stream when the file does not
    exist.
    """
    path = _events_path(feature_dir)
    if not path.exists():
        return EventStream(transitions=[], annotations=[])

    return read_event_stream_from_text(feature_dir, path.read_text(encoding="utf-8"))
