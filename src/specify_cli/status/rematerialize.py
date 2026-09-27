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
    when ``feature_dir`` carries no event log — a mission dir that never had a
    ``status.events.jsonl`` has no authoritative state to derive a snapshot
    from, so there is nothing to reconcile and the caller should treat the
    snapshot as absent rather than fabricate an empty one.
    """
    if not (feature_dir / EVENTS_FILENAME).exists():
        return False
    materialize(feature_dir)
    return True
