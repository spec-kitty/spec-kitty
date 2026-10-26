"""Enumerated raw-append access to ``status.events.jsonl`` (FR-010).

Why this module exists
----------------------
The status FSM (``status/emit.py`` and ``coordination/transaction.py``) is
the sole authority over what lands in a mission's ``status.events.jsonl``:
it validates the transition, takes the mission status lock (L1), appends,
materializes, and fans out. The raw append primitives in ``status/store.py``
bypass every one of those steps -- they are the durability mechanism, not a
write door. Mission ``fsm-write-path-integrity-01M1TZV6`` found four raw
writers that had grown around the FSM without its lock (WP01 census families
4-7, ``design-notes/WP01-lock-rules.md`` section 1), and its own writes gate
then found a fifth (family 8, WP07 addendum); the facade used to hand those
primitives to anyone who asked, so the census decayed silently.

This module is the ONLY sanctioned import path for those primitives from
outside ``specify_cli.status``. The public facade (``specify_cli.status``)
no longer exports them; ``from specify_cli.status import append_raw_rows_atomic`` is an
``ImportError``. Modules inside ``specify_cli.status`` may keep importing
``store`` directly (same-package reuse).

What is allowed
---------------
``ALLOWED_CALLERS`` enumerates every module that may reach a raw append
primitive -- through this module, through ``status.store`` directly (the
in-package shells), or through the ``coordination.status_service`` wrappers
that delegate here (analysis finding I1: a boundary-exempt module must not be
able to reach the store behind the gate's back). Each entry names the WP01
census family it belongs to. The set is **shrink-only**: an entry may be
removed when a writer is retired, but a new writer must route through the
FSM (``emit_status_transition`` / ``BookkeepingTransaction``), not be added
here.

What enforces it
----------------
``tests/architectural/test_status_unsafe_allowlist.py`` AST-scans ``src/``
for every raw-append door and fails when an importer is not in
``ALLOWED_CALLERS``, when ``ALLOWED_CALLERS`` is not a subset of the test's
committed baseline (shrink-only), or when an entry no longer imports a door
(stale entry). ``tests/architectural/test_status_events_writes_gate.py``
(FR-011) independently fails any write-mode open of a ``status.events.jsonl``
path outside ``status/store.py``. Both gates carry non-vacuity floors.
"""

from __future__ import annotations

from .store import (
    append_annotations_atomic_verified,
    append_event_stream_atomic_verified,
    append_events_atomic_verified,
    append_primary_checkout_events_atomic_verified,
    append_raw_rows_atomic,
)

__all__ = [
    "ALLOWED_CALLERS",
    "append_annotations_atomic_verified",
    "append_event_stream_atomic_verified",
    "append_events_atomic_verified",
    "append_primary_checkout_events_atomic_verified",
    "append_raw_rows_atomic",
]

#: Dotted module paths that may reach a raw append primitive. Shrink-only:
#: ``test_status_unsafe_allowlist.py`` pins this set against its committed
#: baseline and fails when any other ``src/`` module imports a door. One
#: line per entry naming the WP01 census family (``design-notes/WP01-lock-
#: rules.md`` section 1) or the shell it implements.
ALLOWED_CALLERS: frozenset[str] = frozenset(
    {
        # Family 1 (flat shell): emit_status_transition, the batch door and
        # emit_inner_state_changed; imports ``store`` as a module object.
        "specify_cli.status.emit",
        # Family 2: the lifecycle appender (mission + project canonical logs)
        # delegates every row to ``append_raw_rows_atomic``.
        "specify_cli.status.lifecycle_events",
        # Family 3 (coord shell): the ``append_event_stream_log``
        # write funnel ``BookkeepingTransaction``
        # commits through; the only module that names the verified
        # primitives on behalf of the coordination pipeline.
        "specify_cli.coordination.status_service",
        # The EventBridge local file adapter (#6603, ADR 2026-10-14-1 D-1):
        # the work package transition door the three shells share (the flat
        # shell, the batch door and ``BookkeepingTransaction``, family 3,
        # which left this set when its unit moved behind the port). The
        # transition doors' unit goes through the bridge; ``status.emit``
        # (``emit_inner_state_changed``) and ``status_service`` still reach
        # the primitives directly.
        "specify_cli.events.event_bridge",
        # Family 4: retrospective run-terminus (superseded -- no new callers),
        # ``append_raw_rows_atomic`` under ``retro_status_lock``.
        "specify_cli.retrospective.events",
        # Family 5: retrospective lifecycle (live post-merge path), Lamport
        # read + build + ``append_raw_rows_atomic`` under one L1 acquisition.
        "specify_cli.retrospective.lifecycle_events",
        # Family 6: verdict-provenance backfill, ``append_events_atomic_verified``
        # under L1 (one-shot migration).
        "specify_cli.migration.verdict_provenance_backfill",
        # Family 7: runtime-state backfill, one
        # ``append_event_stream_atomic_verified`` for the transition +
        # annotation pair under one L1 acquisition (one-shot migration).
        "specify_cli.migration.backfill_runtime_state",
        # Family 8 (WP07 census addendum): decision-point rows
        # (DecisionPointOpened / DecisionPointResolved), one
        # ``append_raw_rows_atomic`` + Lamport readback under one L1
        # acquisition. Found by the WP03 writes gate as a raw unlocked
        # ``open("a")`` the WP01 census had not enumerated.
        "specify_cli.decisions.emit",
    }
)
