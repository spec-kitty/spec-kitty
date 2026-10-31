"""Log-kind helper behind ``spec-kitty events tail``'s ``--log`` selector (#6611).

Private module (the ``cli/commands/_<name>.py`` convention): the closed kind
registry, per-kind canonical-path resolution, latest-run journal selection and
the deterministic human-readable event renderer. The CLI shell
(``events.py``) stays a thin consumer; the core reader
(``status/tail_reader.py``) is untouched by the whole mission (spec C-004).

Design invariants (mission ``events-tail-multi-log-and-json-01M66F8A``):

- C-001: the kind set is CLOSED — exactly the seven ledgers every writer in
  ``src/`` already emits. Adding a kind is a spec change, not a code tweak.
- C-002: NO new resolution code — every rule is a join over ``repo_root``,
  the resolved mission, or the caller-provided ``surface_dir``. The shell
  keeps owning the topology-aware surface resolution and its failure modes;
  it resolves the status surface LAZILY (only the COORD-partition kinds
  ``status``/``decisions`` consume it), so a broken coordination surface
  never blocks a project-scoped or primary-partition kind.
- The runs directory comes from the canonical
  ``runtime.next.run_index.runs_root()`` helper (single canonical authority).
  The run-index FILE (``feature-runs.json``) is deliberately not consulted:
  it records the CURRENT run per mission, while a ``--log run`` subscriber
  wants the most recently modified journal across ALL runs of the mission
  (including historical ones) — see the mission's research.md review round
  for the divergence policy.

This module performs no mutating IO (no mkdir, no writes) beyond reading run
``state.json`` files, listing the runs directory and stat-ing journals; it is
a pure seam: everything else arrives as a parameter.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime.next.run_index import runs_root as _runs_root

from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.status import mission_event_log_path, project_event_log_path

__all__ = [
    "SUPPORTED_LOG_KINDS",
    "COORD_LOG_KINDS",
    "RunLogUnavailable",
    "render_event_line",
    "resolve_log_path",
]

#: C-001 scope lock — the closed set of tail-able ledgers, in help-text order.
SUPPORTED_LOG_KINDS = (
    "status",
    "decisions",
    "mission",
    "run",
    "glossary",
    "ops",
    "canonical",
)

#: The COORD-partition kinds that consume the resolved status surface (#5466).
#: Exported so the shell (events.py) does not redefine it (single authority,
#: mission-review finding 1).
COORD_LOG_KINDS = frozenset({"status", "decisions"})

#: ``state.json`` (the ``MissionRunSnapshot`` shape) back-reference fields.
_RUN_STATE_FILENAME = "state.json"
_RUN_JOURNAL_FILENAME = "run.events.jsonl"

#: Human-mode rendering caps (contract, cli-contract.md "default (human)").
_HUMAN_LINE_MAX = 400
_HUMAN_ELLIPSIS = "..."

#: Reader-injected cursor keys — plumbing, never human-mode content.
_CURSOR_KEYS = frozenset({"tail_offset", "tail_invariant"})


class RunLogUnavailable(Exception):
    """No run journal belongs to the mission (typed refusal, FR-007)."""


def resolve_log_path(
    repo_root: Path,
    resolved: ResolvedMission,
    kind: str,
    surface_dir: Path | None,
) -> Path:
    """Resolve ``kind`` to its canonical log path (C-002: joins only).

    ``surface_dir`` is the resolved status-surface directory (#5466) and is
    consumed ONLY by the COORD-partition kinds (``status``/``decisions``);
    every other kind ignores it, so the shell resolves it lazily.
    """
    if kind not in SUPPORTED_LOG_KINDS:
        raise ValueError(f"unknown log kind: {kind!r} (supported: {', '.join(SUPPORTED_LOG_KINDS)})")

    if kind in COORD_LOG_KINDS:
        if surface_dir is None:
            raise ValueError(f"log kind {kind!r} requires a resolved status surface")
        if kind == "status":
            status_path: Path = mission_event_log_path(surface_dir)
            return status_path
        return surface_dir / "decisions.events.jsonl"

    if kind == "mission":
        mission_events: Path = resolved.feature_dir / "mission-events.jsonl"
        return mission_events
    if kind == "glossary":
        # Writer: src/glossary/events.py. `sanitize_mission_id` is identity on
        # ResolvedMission.mission_id's validated ULID, so the join is exact; do
        # NOT reuse the writer's `get_event_log_path` — it has an mkdir side
        # effect, and readers must stay pure.
        return repo_root / ".kittify" / "events" / "glossary" / f"{resolved.mission_id}.events.jsonl"
    if kind == "ops":
        return repo_root / "kitty-ops" / "lifecycle.jsonl"
    if kind == "canonical":
        canonical_path: Path = project_event_log_path(repo_root)
        return canonical_path

    # kind == "run" — latest-run selection with its typed refusal (FR-003/007).
    return latest_run_journal(repo_root, resolved)


def latest_run_journal(repo_root: Path, resolved: ResolvedMission) -> Path:
    """Return the most recently modified run journal belonging to the mission.

    Scans ``runs_root(repo_root)`` (the canonical runs-dir helper); a run dir
    matches when its ``state.json`` ``mission_id`` equals the mission's ULID,
    or — legacy rows without one — its ``mission_slug`` equals the mission's
    slug. Among matching run dirs that have a journal, the newest journal
    mtime wins. Unreadable/missing ``state.json`` is skipped silently (spec
    Edge Cases: skipped, never fatal). Raises :class:`RunLogUnavailable` when
    no run belongs to the mission — never returns another mission's journal.
    """
    runs_dir = _runs_root(repo_root)
    if not runs_dir.is_dir():
        raise RunLogUnavailable(f"no run journals for mission {resolved.mission_slug}: runs directory {runs_dir} does not exist")

    best_journal: Path | None = None
    best_mtime: float | None = None
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        state_path = run_dir / _RUN_STATE_FILENAME
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # missing/corrupt state.json: skipped, never fatal
        if not isinstance(state, dict):
            continue
        if not _run_belongs_to_mission(state, resolved):
            continue
        journal = run_dir / _RUN_JOURNAL_FILENAME
        try:
            mtime = journal.stat().st_mtime
        except OSError:
            continue  # matching run without a journal: not a candidate
        if best_mtime is None or mtime > best_mtime:
            best_mtime = mtime
            best_journal = journal

    if best_journal is None:
        raise RunLogUnavailable(f"no run journals for mission {resolved.mission_slug} under {runs_dir}")
    return best_journal


def _run_belongs_to_mission(state: Mapping[str, Any], resolved: ResolvedMission) -> bool:
    """Mission→run matching: ULID first, legacy-slug fallback (FR-003)."""
    mission_id = state.get("mission_id")
    if isinstance(mission_id, str) and mission_id:
        id_match: bool = mission_id == resolved.mission_id
        return id_match
    mission_slug = state.get("mission_slug")
    if isinstance(mission_slug, str) and mission_slug:
        slug_match: bool = mission_slug == resolved.mission_slug
        return slug_match
    return False


def render_event_line(event: Mapping[str, Any]) -> str:
    """Render one event as a deterministic, plain-text human line.

    Shape (contract, ``cli-contract.md`` "default (human)")::

        <timestamp|at|-> <event_type|type|-> <compact JSON, keys sorted>

    - The reader-injected ``tail_offset``/``tail_invariant`` cursor keys are
      omitted (cursor plumbing, not content).
    - A ``log_truncated`` signal renders as its own warning line.
    - The line is truncated at 400 characters plus ``...`` (the ``--json``
      stream is the machine channel and is never truncated).
    - Determinism (NFR-003): the same event mapping always renders to the
      same line.
    """
    if event.get("type") == "log_truncated":
        line = f"log truncated ({event.get('reason', 'unknown')}) at offset {event.get('detected_at_offset', '?')} — resynced from offset 0"
        return line if len(line) <= _HUMAN_LINE_MAX else line[:_HUMAN_LINE_MAX] + _HUMAN_ELLIPSIS

    timestamp = _first_present(event, ("timestamp", "at"))
    kind = _first_present(event, ("event_type", "type"))
    payload = event.get("payload")
    if isinstance(payload, Mapping):
        remainder: Mapping[str, Any] = payload
    else:
        remainder = {key: value for key, value in event.items() if key not in _CURSOR_KEYS and key not in ("timestamp", "at", "event_type", "type")}
    remainder_json = json.dumps(remainder, sort_keys=True, default=str)
    line = f"{timestamp} {kind} {remainder_json}"
    if len(line) <= _HUMAN_LINE_MAX:
        return line
    return line[:_HUMAN_LINE_MAX] + _HUMAN_ELLIPSIS


def _first_present(event: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = event.get(key)
        if value is not None:
            return value
    return "-"
