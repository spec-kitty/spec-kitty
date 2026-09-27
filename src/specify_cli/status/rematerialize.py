"""Single canonical authority for regenerating the derived ``status.json``.

``status.events.jsonl`` is the sole authority for work-package lane state; the
committed ``status.json`` is a *derived, disposable* reduced snapshot of it
(see :mod:`specify_cli.status.reducer`). Whenever the event log is reconciled
during a git operation — lane allocation's planning/dependency merges
(#5160 friction 1) and the mission→target squash seam (#4955) — the snapshot
must be **regenerated from the merged log**, never git-merged as if it were an
authoritative artifact. A three-way merge of a reduced JSON object either
conflicts (fail-closed) or corrupts the snapshot; regeneration is the only
correct reconciliation.

This module is that one authority (NFR-002): callers that hold a materialized
worktree checkout call :func:`reconcile_status_snapshot`, which delegates to the
canonical :func:`specify_cli.status.reducer.materialize` — the same full-fidelity
reducer (cancellation/implementer provenance, schema-version replay, mission
identity) the rest of the system reads. Do not fork the reduce→materialize
logic; extend it in the reducer instead.

Level note: this is the *file-in-worktree* authority (reads the on-disk event
log, atomically rewrites the on-disk ``status.json``). Its sibling
:func:`specify_cli.merge.bookkeeping_projection._rematerialize_status_snapshot`
is the *bytes→bytes* authority for the coord→target bookkeeping projection
(takes union-merged event bytes, returns snapshot bytes for the caller to write
to a target path). Different I/O models, same single reducer underneath — keep
them separate; do not collapse one into the other.
"""

from __future__ import annotations

from pathlib import Path

from .reducer import materialize
from .store import EVENTS_FILENAME

__all__ = ["reconcile_status_snapshot"]


def reconcile_status_snapshot(feature_dir: Path) -> bool:
    """Regenerate ``feature_dir/status.json`` from its event log.

    Reads ``feature_dir/status.events.jsonl`` and atomically rewrites
    ``status.json`` to ``materialize(reduce(events))`` via the canonical
    :func:`~specify_cli.status.reducer.materialize`. Use this after a git
    operation has reconciled (union-merged) the event log but left the derived
    snapshot conflicting or stale.

    Returns ``True`` when the snapshot was regenerated, and ``False`` (a no-op)
    when ``feature_dir`` has no authoritative event log to derive from — either
    ``status.events.jsonl`` is absent (a mission dir that never had one, or a
    coord lane worktree where status files are sparse-excluded from disk) or it
    is present but empty. In every no-op case there is no authoritative state to
    reduce, so the caller must treat the snapshot as unreconciled (fail closed)
    rather than fabricate or commit a degenerate empty snapshot over whatever is
    on disk.
    """
    events_path = feature_dir / EVENTS_FILENAME
    if not events_path.exists():
        return False
    # An existing-but-empty log carries no authoritative state; regenerating from
    # it would write a degenerate empty snapshot. Treat it as nothing to reconcile.
    try:
        if not events_path.read_text(encoding="utf-8").strip():
            return False
    except OSError:
        return False
    materialize(feature_dir)
    return True
