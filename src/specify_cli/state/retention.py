"""Local event-log retention engine behind ``spec-kitty doctor event-logs`` (#6610).

Why this module exists
----------------------
Run journals, per-Mission glossary logs and local caches under ``.kittify/``
grow without bound (ADR 2026-10-13-2 D-3, gap G-9). This engine scans the
gitignored surfaces the state registry's cleanup policy marks
``ledger_retention`` or ``rebuildable`` (:mod:`specify_cli.state.contract`,
FR-013: there is no second list here), gives every item a verdict with one
reason, and, on apply, deletes the candidates under the right locks.

- ``ledger_retention`` items (run directories, per-Mission glossary logs) are
  candidates only when they are outside the newest ``keep_runs`` of their kind,
  older than ``max_age_days`` (newest file modification time), their Mission is
  found in this checkout, their work is over, and no lock is held on them
  (FR-007, FR-008). A run's work is over when its Mission is merged or the run
  itself recorded ``MissionRunCompleted``; a glossary log's when its Mission is
  completed (merged, or every WP terminal). A run's Mission comes from its
  run-index entry (``next`` records none in ``state.json``).
- ``rebuildable`` items (derived Mission views) are candidates whatever their
  age, unless locked (FR-010). The Op index is not in scope (operator ruling
  2026-10-28): ``invocations list`` trusts a partial index.
- Lock files, the non-Mission glossary logs (``_cli``, ``_renderer``) and every
  tracked file are never candidates (FR-011, C-002).

It is reader/doctor side (C-001): it never calls an event-log door
(``event_log_lock``, ``append_event_log_lines``, ``append_event``). Locks are
probed and held with the kernel primitive on the same lock files the writers
take. No lock file is ever deleted on its own (kernel lock guarantee G3); a run
directory is removed whole, its ``state.json.lock`` with it, only while its
run-cursor lock is held. The module carries no Rich/typer: the CLI renders
:meth:`RetentionPlan.to_dict` / :meth:`RetentionResult.to_dict`.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from glossary.events import EVENT_LOG_SUFFIX, GLOSSARY_EVENTS_DIR, sanitize_mission_id
from kernel.clock import DEFAULT_CLOCK
from kernel.event_log_append import event_log_lock_path
from kernel.locks import LockAcquireTimeout, LockNotAcquired, SyncMachineFileLock, machine_file_lock
from kernel.no_follow import NoFollowPathError
from runtime.next import run_index
from runtime.next.run_lock import try_run_cursor_lock
from specify_cli.core.ledger_retention import RetentionLimits
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.mission_metadata import META_FILENAME
from specify_cli.state.contract import STATE_SURFACES, RetentionRule, get_surfaces_by_retention
from specify_cli.status.views import DERIVED_VIEWS_DIR
from spec_kitty_events.mission_next import MISSION_RUN_COMPLETED
from specify_cli.status.lifecycle import is_mission_completed, is_mission_merged

# Only what ``doctor event-logs`` imports is exported. The vocabulary constants,
# item/failure types and the path-guard error stay public module names (the
# report and the tests read them) without claiming a cross-module caller.
__all__ = [
    "RetentionPlan",
    "RetentionPolicyDriftError",
    "RetentionResult",
    "apply_retention",
    "scan_retention",
]

# ---------------------------------------------------------------------------
# Vocabulary (data-model.md)
# ---------------------------------------------------------------------------

KIND_RUN = "run"
KIND_MISSION_LOG = "mission_log"
KIND_CACHE = "cache"

VERDICT_CANDIDATE = "candidate"
VERDICT_KEPT = "kept"

REASON_COMPLETED = "past retention; Mission completed"
REASON_REBUILDABLE = "rebuildable cache"
REASON_WITHIN_KEEP_RUNS = "within keep_runs"
REASON_YOUNGER_THAN_MAX_AGE = "younger than max_age_days"
REASON_MISSION_OPEN = "Mission is open"
REASON_MISSION_NOT_FOUND = "Mission not found"
REASON_LOCK_HELD = "lock held"

# Registry surface names this engine has a collector for.
_SURFACE_RUN_SNAPSHOT = "runtime_run_snapshot"
_SURFACE_RUN_EVENT_LOG = "runtime_run_event_log"
_SURFACE_RUN_FROZEN_TEMPLATE = "runtime_frozen_template"
_SURFACE_GLOSSARY_LOG = "glossary_fallback_events"
_SURFACE_DERIVED_VIEWS = "derived_mission_views"

_PRUNING_RULES = (RetentionRule.LEDGER_RETENTION, RetentionRule.REBUILDABLE)

# Every root and file name below comes from its owner (AR-M1); a unit test
# pins each against the registry ``path_pattern`` of the surface it scans.
_RUNS_DIR = run_index.runs_root(Path())
_GLOSSARY_LOG_DIR = GLOSSARY_EVENTS_DIR
_GLOSSARY_LOG_SUFFIX = EVENT_LOG_SUFFIX
#: Glossary logs that name no Mission (``_cli``, ``_renderer``) start with this.
_NON_MISSION_LOG_PREFIX = "_"
_DERIVED_DIR = DERIVED_VIEWS_DIR


def _registry_file_name(surface_name: str) -> str:
    """The file name a registry surface's ``path_pattern`` ends in (the run store has no owner constant)."""
    return Path(next(s.path_pattern for s in STATE_SURFACES if s.name == surface_name)).name


_RUN_STATE_FILENAME = _registry_file_name("runtime_run_snapshot")
_RUN_EVENTS_FILENAME = _registry_file_name("runtime_run_event_log")
_LOCK_SUFFIX = ".lock"
_SECONDS_PER_DAY = 86400.0


class RetentionPolicyDriftError(RuntimeError):
    """The registry's cleanup policy and this engine's collectors disagree (FR-013).

    A surface declared ``ledger_retention`` or ``rebuildable`` has no collector
    here, a collector's surface family is only partly selected, or a surface
    moved to the other pruning rule. Refusing beats guessing what to delete.
    """


class UnsafeRetentionPathError(OSError):
    """A deletion target lies outside the local tier the engine may touch (C-002)."""


# ---------------------------------------------------------------------------
# Plan objects (contracts/doctor-event-logs.md JSON shape)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionItem:
    """One scanned unit with its verdict and the one reason for it."""

    surface: str
    kind: str
    path: Path
    mission: str | None
    age_days: float
    verdict: str
    reason: str

    def to_dict(self, repo_root: Path) -> dict[str, Any]:
        """The report entry: repo-relative POSIX path, no verdict (the list carries it)."""
        return {
            "surface": self.surface,
            "kind": self.kind,
            "path": _relative(self.path, repo_root),
            "mission": self.mission,
            "age_days": round(self.age_days, 2),
            "reason": self.reason,
        }

    def kept_because(self, reason: str) -> RetentionItem:
        """This item re-judged as kept (a candidate whose lock was held at apply)."""
        return replace(self, verdict=VERDICT_KEPT, reason=reason)


@dataclass(frozen=True)
class RetentionPlan:
    """The preview: every scanned item, candidate or kept."""

    limits: RetentionLimits
    items: list[RetentionItem]

    @property
    def candidates(self) -> list[RetentionItem]:
        return [item for item in self.items if item.verdict == VERDICT_CANDIDATE]

    @property
    def kept(self) -> list[RetentionItem]:
        return [item for item in self.items if item.verdict == VERDICT_KEPT]

    def to_dict(self, repo_root: Path) -> dict[str, Any]:
        """The ``--json`` report of a preview: nothing deleted, failed or unindexed."""
        return _report(self, repo_root, applied=False, kept=self.kept, deleted=(), failed=(), removed_index_entries=())


@dataclass(frozen=True)
class RetentionFailure:
    """A candidate whose deletion raised; the error text is kept for the report."""

    item: RetentionItem
    error: str

    def to_dict(self, repo_root: Path) -> dict[str, Any]:
        return {**self.item.to_dict(repo_root), "error": self.error}


@dataclass
class RetentionResult:
    """The outcome of :func:`apply_retention` over one plan."""

    plan: RetentionPlan
    deleted: list[RetentionItem] = field(default_factory=list)
    failed: list[RetentionFailure] = field(default_factory=list)
    removed_index_entries: list[str] = field(default_factory=list)
    kept_at_apply: list[RetentionItem] = field(default_factory=list)

    def to_dict(self, repo_root: Path) -> dict[str, Any]:
        """The ``--apply --json`` report: a candidate found locked at apply is listed as kept."""
        return _report(
            self.plan,
            repo_root,
            applied=True,
            kept=[*self.plan.kept, *self.kept_at_apply],
            deleted=self.deleted,
            failed=[failure.to_dict(repo_root) for failure in self.failed],
            removed_index_entries=self.removed_index_entries,
        )


def _report(
    plan: RetentionPlan,
    repo_root: Path,
    *,
    applied: bool,
    kept: Iterable[RetentionItem],
    deleted: Iterable[RetentionItem],
    failed: Iterable[dict[str, Any]],
    removed_index_entries: Iterable[str],
) -> dict[str, Any]:
    return {
        "applied": applied,
        "limits": plan.limits.to_dict(),
        "candidates": [item.to_dict(repo_root) for item in plan.candidates],
        "kept": [item.to_dict(repo_root) for item in kept],
        "deleted": [item.to_dict(repo_root) for item in deleted],
        "failed": list(failed),
        "removed_index_entries": list(removed_index_entries),
    }


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Mission resolution (built once per scan; completion memoized)
# ---------------------------------------------------------------------------


def _claim(table: dict[str, Path | None], key: str, feature_dir: Path) -> None:
    """Map *key* to *feature_dir*; a key claimed by two Mission directories maps to ``None``.

    An ambiguous slug, id or log stem is never resolved first-match-wins: the item
    reads as ``Mission not found`` and is kept (DS-L2).
    """
    if key in table and table[key] != feature_dir:
        table[key] = None
    else:
        table.setdefault(key, feature_dir)


class _Missions:
    """The Missions of this checkout, by directory name, recorded slug and log stem."""

    def __init__(self, repo_root: Path, now: datetime) -> None:
        self._now = now
        self._by_slug: dict[str, Path | None] = {}
        self._by_id: dict[str, Path | None] = {}
        self._by_stem: dict[str, Path | None] = {}
        self._facts: dict[tuple[str, Path], bool] = {}
        for meta_path in sorted((repo_root / KITTY_SPECS_DIR).glob(f"*/{META_FILENAME}")):
            self._register(meta_path.parent)

    def _register(self, feature_dir: Path) -> None:
        meta = load_meta_or_empty(feature_dir)
        _claim(self._by_slug, feature_dir.name, feature_dir)
        slug = meta.get("mission_slug")
        if isinstance(slug, str) and slug:
            _claim(self._by_slug, slug, feature_dir)
        mission_id = meta.get("mission_id")
        if isinstance(mission_id, str) and mission_id:
            _claim(self._by_id, mission_id, feature_dir)
            _claim(self._by_stem, sanitize_mission_id(mission_id), feature_dir)

    def by_slug(self, slug: object) -> Path | None:
        return self._by_slug.get(slug) if isinstance(slug, str) else None

    def by_id(self, mission_id: str) -> Path | None:
        return self._by_id.get(mission_id)

    def by_log_stem(self, stem: str) -> Path | None:
        return self._by_stem.get(stem)

    def _fact(self, name: str, feature_dir: Path, probe: Callable[[], bool]) -> bool:
        """Lazy, memoized lifecycle fact; a corrupt ``meta.json`` reads as open (fail safe)."""
        key = (name, feature_dir)
        if key not in self._facts:
            try:
                self._facts[key] = probe()
            except MissionMetaReadError:
                self._facts[key] = False
        return self._facts[key]

    def is_completed(self, feature_dir: Path) -> bool:
        """Merged, or every WP terminal (:func:`~specify_cli.status.lifecycle.is_mission_completed`)."""
        return self._fact("completed", feature_dir, lambda: is_mission_completed(feature_dir, now=self._now))

    def is_merged(self, feature_dir: Path) -> bool:
        """A live merge marker (:func:`~specify_cli.status.lifecycle.is_mission_merged`)."""
        return self._fact("merged", feature_dir, lambda: is_mission_merged(feature_dir))


# ---------------------------------------------------------------------------
# Units and collectors
# ---------------------------------------------------------------------------

_LockFactory = Callable[[], SyncMachineFileLock]


@dataclass(frozen=True)
class _Unit:
    """One deletable unit before its verdict."""

    surface: str
    kind: str
    path: Path
    age_days: float
    feature_dir: Path | None
    lock: _LockFactory | None = None

    def judged(self, verdict: str, reason: str) -> RetentionItem:
        mission = self.feature_dir.name if self.feature_dir is not None else None
        return RetentionItem(self.surface, self.kind, self.path, mission, self.age_days, verdict, reason)


@dataclass(frozen=True)
class _ScanContext:
    repo_root: Path
    now_epoch: float
    missions: _Missions

    def age_days(self, mtime: float) -> float:
        return max(0.0, (self.now_epoch - mtime) / _SECONDS_PER_DAY)


def _newest_mtime(path: Path) -> float:
    """Newest modification time of a file, or of any file under a directory.

    Lock sidecars are skipped: taking a lock (including this engine's own
    probe) writes to them, which is not activity on the item. Directory
    mtimes are skipped too (creating a lock sidecar bumps them); an empty
    directory falls back to its own mtime.
    """
    if not path.is_dir():
        return path.stat().st_mtime
    newest: float | None = None
    stack = [path]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif not entry.name.endswith(_LOCK_SUFFIX):
                    mtime = entry.stat(follow_symlinks=False).st_mtime
                    newest = mtime if newest is None else max(newest, mtime)
    return newest if newest is not None else path.stat().st_mtime


def _age_or_none(ctx: _ScanContext, path: Path) -> float | None:
    """The item's age, or ``None`` when it vanished mid-scan (the item is skipped)."""
    try:
        return ctx.age_days(_newest_mtime(path))
    except FileNotFoundError:
        return None


def _real_dirs(root: Path) -> list[Path]:
    """The directories directly under *root*; symlinks are never collected (C-002)."""
    return [path for path in sorted(root.iterdir()) if path.is_dir() and not path.is_symlink()]


def _writers_log_lock(path: Path) -> _LockFactory:
    """The writers' interim event-log lock on *path*, taken with the kernel primitive (C-001)."""
    # interim-locked-delete: retires at the #6193 handover (kernel.event_log_append).
    return lambda: machine_file_lock(event_log_lock_path(path), blocking=False)


def _run_lock(run_dir: Path) -> _LockFactory:
    return lambda: try_run_cursor_lock(run_dir)


def _mission_of_record(record: dict[str, Any], missions: _Missions) -> Path | None:
    """Resolve the Mission a run record names (an index entry or a legacy snapshot).

    ``mission_id`` is the only runtime identity: a recorded id resolves by id
    alone, and an id this checkout does not know is ``Mission not found``
    (FR-008, a Mission on another branch), never a slug match. The slug is
    read only from a record that carries no ``mission_id``.
    """
    mission_id = record.get("mission_id")
    if mission_id is None or mission_id == "":
        return missions.by_slug(record.get("mission_slug"))
    return missions.by_id(mission_id) if isinstance(mission_id, str) else None


def _entry_run_dir(entry: object, repo_root: Path) -> Path | None:
    """The resolved run directory an index entry names, or ``None`` (malformed or foreign)."""
    if not isinstance(entry, dict):
        return None
    stored = entry.get("run_dir")
    if not isinstance(stored, str) or not stored:
        return None
    try:
        return run_index.resolve_run_dir(stored, repo_root).resolve()
    except run_index.RunDirOutsideRepoError:
        return None  # a foreign entry is the migration's to heal, never ours to read or drop


def _index_entries_by_run_dir(repo_root: Path) -> dict[Path, list[dict[str, Any]]]:
    """The run-index entries grouped by the run directory they resolve to (read once per scan)."""
    index = run_index.read_index_file(run_index.feature_runs_path(repo_root))
    if not isinstance(index, dict):
        return {}
    by_dir: dict[Path, list[dict[str, Any]]] = {}
    for entry in index.values():
        target = _entry_run_dir(entry, repo_root)
        if target is not None:
            by_dir.setdefault(target, []).append(entry)
    return by_dir


def _read_snapshot_mission(run_dir: Path, missions: _Missions) -> Path | None:
    """Legacy fallback: the Mission a run's own snapshot records; unreadable reads as unknown."""
    try:
        state = json.loads((run_dir / _RUN_STATE_FILENAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _mission_of_record(state, missions) if isinstance(state, dict) else None


def _run_mission(run_dir: Path, entries: list[dict[str, Any]], missions: _Missions) -> Path | None:
    """Resolve a run's Mission: its run-index entry first, its snapshot only when unindexed.

    ``next`` records the Mission of a run in the run index
    (``feature-runs.json``: ``mission_id`` / ``mission_slug``), not in
    the run's ``state.json``. A run with no index entry falls back to the
    snapshot's own ``mission_id`` / ``mission_slug`` (older writers); a run
    that neither names is ``Mission not found``. Entries that disagree read as
    unknown.
    """
    if not entries:
        return _read_snapshot_mission(run_dir, missions)
    resolved = {_mission_of_record(entry, missions) for entry in entries}
    return resolved.pop() if len(resolved) == 1 else None


def _collect_runs(ctx: _ScanContext) -> list[_Unit]:
    root = ctx.repo_root / _RUNS_DIR
    if not root.is_dir():
        return []
    entries_by_dir = _index_entries_by_run_dir(ctx.repo_root)
    units: list[_Unit] = []
    for run_dir in _real_dirs(root):
        age = _age_or_none(ctx, run_dir)
        if age is None:
            continue
        units.append(
            _Unit(
                surface=_SURFACE_RUN_EVENT_LOG,
                kind=KIND_RUN,
                path=run_dir,
                age_days=age,
                feature_dir=_run_mission(run_dir, entries_by_dir.get(run_dir.resolve(), []), ctx.missions),
                lock=_run_lock(run_dir),
            )
        )
    return units


def _collect_glossary_logs(ctx: _ScanContext) -> list[_Unit]:
    log_dir = ctx.repo_root / _GLOSSARY_LOG_DIR
    if not log_dir.is_dir():
        return []
    units: list[_Unit] = []
    for log in sorted(log_dir.glob(f"*{_GLOSSARY_LOG_SUFFIX}")):
        if log.name.startswith(_NON_MISSION_LOG_PREFIX) or log.is_symlink() or not log.is_file():
            continue  # FR-011: _cli / _renderer name no Mission and are never listed; symlinks never.
        age = _age_or_none(ctx, log)
        if age is None:
            continue
        # The stem is the sanitized mission_id; there is no slug fallback here.
        stem = log.name.removesuffix(_GLOSSARY_LOG_SUFFIX)
        units.append(
            _Unit(
                surface=_SURFACE_GLOSSARY_LOG,
                kind=KIND_MISSION_LOG,
                path=log,
                age_days=age,
                feature_dir=ctx.missions.by_log_stem(stem),
                lock=_writers_log_lock(log),
            )
        )
    return units


def _collect_derived_views(ctx: _ScanContext) -> list[_Unit]:
    derived = ctx.repo_root / _DERIVED_DIR
    if not derived.is_dir():
        return []
    units: list[_Unit] = []
    for view_dir in _real_dirs(derived):
        age = _age_or_none(ctx, view_dir)
        if age is not None:
            units.append(_Unit(_SURFACE_DERIVED_VIEWS, KIND_CACHE, view_dir, age, ctx.missions.by_slug(view_dir.name)))
    return units


def _run_finished(run_dir: Path) -> bool:
    """True when the run's own journal records ``MissionRunCompleted`` (read-only; torn lines skipped)."""
    try:
        with (run_dir / _RUN_EVENTS_FILENAME).open(encoding="utf-8") as journal:
            for line in journal:
                if MISSION_RUN_COMPLETED in line and _is_completion_row(line):
                    return True
    except (OSError, UnicodeDecodeError):
        return False
    return False


def _is_completion_row(line: str) -> bool:
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(row, dict) and row.get("event_type") == MISSION_RUN_COMPLETED


def _run_is_done(run_dir: Path, feature_dir: Path, missions: _Missions) -> bool:
    """A run is eligible when its Mission is merged or the run itself finished (DS-M2)."""
    return missions.is_merged(feature_dir) or _run_finished(run_dir)


def _mission_is_completed(_path: Path, feature_dir: Path, missions: _Missions) -> bool:
    """A per-Mission log is eligible when its Mission is completed (merged, or every WP terminal)."""
    return missions.is_completed(feature_dir)


_DonePredicate = Callable[[Path, Path, _Missions], bool]


@dataclass(frozen=True)
class _Collector:
    """The scanner for one registry surface family and the rule it serves.

    ``done`` decides, for a ``ledger_retention`` item past both limits whose
    Mission was found, whether that item's work is over (``past retention;
    Mission completed``) or not (``Mission is open``).
    """

    surfaces: frozenset[str]
    rule: RetentionRule
    root: Path
    collect: Callable[[_ScanContext], list[_Unit]]
    done: _DonePredicate = _mission_is_completed


#: One collector per surface family. Which of them run is decided by the
#: registry's cleanup policy alone (FR-013); this table only says HOW to scan.
_COLLECTORS: tuple[_Collector, ...] = (
    _Collector(
        frozenset({_SURFACE_RUN_SNAPSHOT, _SURFACE_RUN_EVENT_LOG, _SURFACE_RUN_FROZEN_TEMPLATE}),
        RetentionRule.LEDGER_RETENTION,
        _RUNS_DIR,
        _collect_runs,
        done=_run_is_done,
    ),
    _Collector(frozenset({_SURFACE_GLOSSARY_LOG}), RetentionRule.LEDGER_RETENTION, _GLOSSARY_LOG_DIR, _collect_glossary_logs),
    _Collector(frozenset({_SURFACE_DERIVED_VIEWS}), RetentionRule.REBUILDABLE, _DERIVED_DIR, _collect_derived_views),
)


def _select_collectors() -> list[_Collector]:
    """The collectors the registry policy selects; refuse on any drift (FR-013)."""
    selected = {surface.name: rule for rule in _PRUNING_RULES for surface in get_surfaces_by_retention(rule)}
    covered = {name for collector in _COLLECTORS for name in collector.surfaces}
    orphans = sorted(set(selected) - covered)
    if orphans:
        raise RetentionPolicyDriftError(
            f"State surface(s) {', '.join(orphans)} are declared for doctor event-logs cleanup but it has no collector "
            "for them. Add a collector in specify_cli/state/retention.py or change their cleanup policy."
        )
    chosen: list[_Collector] = []
    for collector in _COLLECTORS:
        rules = {name: selected.get(name) for name in sorted(collector.surfaces)}
        if all(rule is None for rule in rules.values()):
            continue
        mismatched = [name for name, rule in rules.items() if rule is not collector.rule]
        if mismatched:
            raise RetentionPolicyDriftError(
                f"State surface(s) {', '.join(mismatched)} must be declared {collector.rule.value} together with "
                f"{', '.join(sorted(collector.surfaces))}; the registry policy declares {rules}."
            )
        chosen.append(collector)
    return chosen


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


def _lock_is_held(lock: _LockFactory | None) -> bool:
    """Probe a lock without waiting; never create a lock file in a preview.

    A lock path with nothing at it is held by nobody, so it is not created; a
    dangling symlink is something (``os.path.lexists``), never read as absent.
    Every unknown lock state reads as held, never as free:

    * a lock path that cannot be computed (git unavailable, ``OSError``);
    * a probe that raises ``OSError`` (permissions);
    * a lock path that is a symlink, whether its target exists or dangles:
      ``kernel.locks`` opens it with ``O_NOFOLLOW`` and raises
      :class:`~kernel.no_follow.NoFollowPathError`, a ``RuntimeError``.
    """
    if lock is None:
        return False
    try:
        probe = lock()
    except (OSError, NoFollowPathError):
        return True
    if not os.path.lexists(probe.lock_path):
        return False
    try:
        with probe:
            return False
    except (LockNotAcquired, OSError, NoFollowPathError):
        return True


def _ledger_verdict(unit: _Unit, rank: int, limits: RetentionLimits, missions: _Missions, done: _DonePredicate) -> RetentionItem:
    """First match wins; the expensive checks run only for items past both limits."""
    if rank < limits.keep_runs:
        return unit.judged(VERDICT_KEPT, REASON_WITHIN_KEEP_RUNS)
    if unit.age_days <= limits.max_age_days:
        return unit.judged(VERDICT_KEPT, REASON_YOUNGER_THAN_MAX_AGE)
    if unit.feature_dir is None:
        return unit.judged(VERDICT_KEPT, REASON_MISSION_NOT_FOUND)
    if not done(unit.path, unit.feature_dir, missions):
        return unit.judged(VERDICT_KEPT, REASON_MISSION_OPEN)
    if _lock_is_held(unit.lock):
        return unit.judged(VERDICT_KEPT, REASON_LOCK_HELD)
    return unit.judged(VERDICT_CANDIDATE, REASON_COMPLETED)


def _rebuildable_verdict(unit: _Unit) -> RetentionItem:
    if _lock_is_held(unit.lock):
        return unit.judged(VERDICT_KEPT, REASON_LOCK_HELD)
    return unit.judged(VERDICT_CANDIDATE, REASON_REBUILDABLE)


def _judge(collector: _Collector, units: list[_Unit], limits: RetentionLimits, missions: _Missions) -> list[RetentionItem]:
    # Newest first: rank 0 is the most recently modified item of this kind.
    ordered = sorted(units, key=lambda unit: (unit.age_days, unit.path.as_posix()))
    if collector.rule is RetentionRule.REBUILDABLE:
        return [_rebuildable_verdict(unit) for unit in ordered]
    return [_ledger_verdict(unit, rank, limits, missions, collector.done) for rank, unit in enumerate(ordered)]


def scan_retention(repo_root: Path, limits: RetentionLimits, *, now: datetime | None = None) -> RetentionPlan:
    """Scan the registry-selected surfaces and judge every item. Changes nothing.

    Args:
        repo_root: The project root.
        limits: The effective ``ledger.retention`` limits.
        now: The reference time for ages and Mission completion; defaults to
            the kernel clock.

    Raises:
        RetentionPolicyDriftError: the registry policy and the collectors disagree.
    """
    moment = now if now is not None else DEFAULT_CLOCK.now()
    collectors = _select_collectors()
    missions = _Missions(repo_root, moment)
    ctx = _ScanContext(repo_root=repo_root, now_epoch=moment.timestamp(), missions=missions)
    items: list[RetentionItem] = []
    for collector in collectors:
        items.extend(_judge(collector, collector.collect(ctx), limits, missions))
    return RetentionPlan(limits=limits, items=items)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

#: The only places a deletion may land (C-002 defence in depth): strictly inside
#: the gitignored root a collector scans.
_DELETABLE_ROOTS = tuple(collector.root for collector in _COLLECTORS)


def _assert_deletable(repo_root: Path, path: Path) -> None:
    """Refuse any target that is not strictly inside the local tier."""
    try:
        relative = Path(os.path.normpath(path)).relative_to(os.path.normpath(repo_root))
    except ValueError:
        raise UnsafeRetentionPathError(f"{path}: outside the project; doctor event-logs deletes nothing there.") from None
    for root in _DELETABLE_ROOTS:
        if len(relative.parts) > len(root.parts) and relative.parts[: len(root.parts)] == root.parts:
            return
    raise UnsafeRetentionPathError(
        f"{path}: not in the local event-log tier ({', '.join(r.as_posix() for r in _DELETABLE_ROOTS)}); doctor event-logs never deletes it."
    )


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path)


def _entry_points_at(entry: object, run_dir: Path, repo_root: Path) -> bool:
    target = _entry_run_dir(entry, repo_root)
    return target is not None and target == run_dir.resolve()


def _drop_index_entries(repo_root: Path, run_dir: Path) -> list[str]:
    """Remove the run-index entries that resolve to *run_dir*; caller holds the index lock."""
    index_path = run_index.feature_runs_path(repo_root)
    index = run_index.read_index_file(index_path)
    if not isinstance(index, dict):
        return []  # a non-mapping index names no run; it is left exactly as stored
    removed = [key for key, entry in index.items() if _entry_points_at(entry, run_dir, repo_root)]
    if removed:
        # The raw writer keeps every other entry exactly as stored.
        run_index.write_index_file(index_path, {key: entry for key, entry in index.items() if key not in removed})
    return removed


def _unlink_run_files(run_dir: Path) -> None:
    """Unlink the run's snapshot, then its journal; caller holds the run-cursor lock.

    Both are plain files no lock holds open, so Windows can unlink them under
    the lock. The snapshot goes first: once it is gone no ``next`` can advance
    the run, and an error here stops the deletion before the tree is touched.
    """
    (run_dir / _RUN_STATE_FILENAME).unlink(missing_ok=True)
    (run_dir / _RUN_EVENTS_FILENAME).unlink(missing_ok=True)


def _delete_run(repo_root: Path, item: RetentionItem) -> list[str]:
    """Unlink a run from the index and drop its snapshot under its locks, then remove its directory unlocked.

    Lock order: run-cursor lock (non-blocking) -> run-index lock (bounded wait)
    -> drop the index entries -> unlink ``state.json`` and ``run.events.jsonl``
    -> release both locks -> remove the rest of the directory.
    The nesting is one-way: no path holds the index lock while waiting on a
    run-cursor lock (``runtime.next.run_lock`` C-002), so it cannot deadlock.
    The directory is removed only after both locks are released because the
    run-cursor lock file (``state.json.lock``) lives inside it, and Windows
    cannot remove a directory that holds an open file. The run's
    ``state.json.lock`` goes with its directory, never on its own (G3).

    Once the entry is gone, ``next`` resolves no run for that Mission and starts
    a fresh one in a new directory (ADR 2026-10-13-2 D-3: the index never names
    a run that is gone). A ``next`` that already resolved this run and waits on
    its run-cursor lock can take it in the gap between the release and the
    removal; the snapshot is already gone then, so its re-read fails and it
    writes nothing. Residual: taking that lock goes through
    ``kernel.locks._ensure_dir``, which may recreate an empty run directory
    holding only ``state.json.lock`` after the removal; it names no Mission, so
    later scans keep it as ``Mission not found`` (tracked with #6739).

    Trade-off: the entries are dropped BEFORE the files go. If an unlink or the
    removal then fails (an open handle, permissions), the run stays on disk
    without an index entry and the item is reported in ``failed`` with its
    path; ``next`` starts a fresh run for that Mission. A failed snapshot unlink
    leaves the tree untouched. The other order could leave the index naming a
    half-removed run, which D-3 forbids.
    """
    with try_run_cursor_lock(item.path), run_index.index_lock(repo_root):
        removed = _drop_index_entries(repo_root, item.path)
        _unlink_run_files(item.path)
    _remove_tree(item.path)
    return removed


def _delete_locked_log(_repo_root: Path, item: RetentionItem) -> list[str]:
    """Unlink a log under the writers' event-log lock; its lock and sidecars stay."""
    # interim-locked-delete: retires at the #6193 handover (kernel.event_log_append).
    with machine_file_lock(event_log_lock_path(item.path), blocking=False):
        item.path.unlink()
    return []


def _delete_cache_dir(_repo_root: Path, item: RetentionItem) -> list[str]:
    _remove_tree(item.path)
    return []


_Deleter = Callable[[Path, RetentionItem], list[str]]

_DELETERS: dict[str, _Deleter] = {
    _SURFACE_RUN_EVENT_LOG: _delete_run,
    _SURFACE_GLOSSARY_LOG: _delete_locked_log,
    _SURFACE_DERIVED_VIEWS: _delete_cache_dir,
}


def _delete(repo_root: Path, item: RetentionItem) -> list[str]:
    _assert_deletable(repo_root, item.path)
    deleter = _DELETERS.get(item.surface)
    if deleter is None:
        raise UnsafeRetentionPathError(f"{item.path}: surface {item.surface} has no deletion rule.")
    return deleter(repo_root, item)


def apply_retention(repo_root: Path, plan: RetentionPlan) -> RetentionResult:
    """Delete every candidate of *plan*, re-checking its lock; never abort the loop.

    A candidate whose lock is held now, or whose lock file is a symlink
    (``NoFollowPathError``, read as held exactly as in the preview), is kept
    (``lock held``); a deletion that raises is recorded in ``failed`` with its
    error text and the rest proceed.
    """
    result = RetentionResult(plan=plan)
    for item in plan.candidates:
        try:
            removed = _delete(repo_root, item)
        except (LockNotAcquired, NoFollowPathError):
            result.kept_at_apply.append(item.kept_because(REASON_LOCK_HELD))
        except (OSError, LockAcquireTimeout) as exc:
            result.failed.append(RetentionFailure(item=item, error=str(exc)))
        else:
            result.deleted.append(item)
            result.removed_index_entries.extend(removed)
    return result
