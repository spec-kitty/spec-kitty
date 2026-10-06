"""Hidden git merge-driver entrypoints for Spec Kitty repositories.

Seven custom drivers keep mission bookkeeping semantic under the mission→target
``git merge --squash`` in ``lanes/consolidation.py::_merge_branch_into`` (#4892 dropped
the old ``-X theirs``; ordinary source paths now fail closed on conflict). A
custom driver takes over conflict resolution on the paths it is registered for,
so target-newer canonical state is reconciled rather than clobbered or
hard-conflicting (#2709 / FR-003 / FR-004 / FR-008):

- ``merge-driver-event-log``         — ``status.events.jsonl`` union (append-only log).
- ``merge-driver-meta``              — ``meta.json`` field merge, base-aware for
  ordinary merges (a key changed or deleted on one side only survives; on a
  genuine conflict acceptance/VCS/lifecycle keys are target-authoritative (the
  accepted-newer ``ours`` side) and planning keys mission-authoritative
  (``theirs``; preserves the #1732 planning-artifact authority); coupled key
  groups move as one unit; ``acceptance_history`` unioned). The consolidation
  pipeline's mission→target squash opts into the two-way rule through the
  ``META_DRIVER_TWO_WAY_ENV`` environment variable, read here (#5460).
- ``merge-driver-traces``            — ``traces/*.md`` markdown union: order-preserving
  line-level dedup so both sides' sections survive without duplication.
- ``merge-driver-acceptance-matrix`` — ``acceptance-matrix.json`` row-aware,
  base-aware (3-way) merge over ``criteria``/``negative_invariants``, keyed by
  ``criterion_id``/``invariant_id`` (FR-008 / see ``contracts/merge-driver-
  algorithm.md``).
- ``merge-driver-issue-matrix``      — ``issue-matrix.json`` row-aware,
  base-aware (3-way) merge over ``rows``, keyed by canonicalized ``issue_ref``.
- ``merge-driver-review-cycle``      — ``tasks/<wp>/review-cycle-*.md``
  best-effort, non-aborting reconciliation of a two-verdict collision (see
  ``specify_cli.consolidation.drivers.run_review_cycle_driver``'s docstring for the
  full history).
- ``merge-driver-decision-index``    — ``decisions/index.json`` union keyed by
  ``decision_id``, terminal-beats-open fold precedence (FR-009b / see
  ``specify_cli.consolidation.drivers.run_decision_index_driver``'s docstring).

Git invokes a driver with ``%O %A %B`` = base / ours / theirs and expects the
merged result written to the ``ours`` (``%A``) path with exit 0. Under the squash
integration ``ours`` is the target checkout (e.g. ``main``) and ``theirs`` is the
mission branch.

**Placement (#5119 / FR-002/FR-003/C-001).** This module is a THIN adapter
over ``specify_cli.consolidation.drivers`` — the single owner of every driver's
file-level body, reconciliation logic, and serialization (moved there so the
in-process driver replay, ``consolidation/git_probes.py``, executes the exact SAME
body a real ``git merge --squash`` subprocess invocation would). Every
function here keeps its pre-move name, parameters, and ``typer.Argument``
declarations (the registrar at ``cli/commands/__init__.py:341
_register_merge_driver`` binds them by attribute; C-001 holds — no
user-facing behavior, argument order, or exit code changed) and does nothing
but call its body and translate the body's
:class:`~specify_cli.consolidation.drivers.MergeDriverError` /
:class:`~specify_cli.consolidation.drivers.MergeDriverOutcome` into
``typer.echo``/``typer.Exit``.
"""

from __future__ import annotations

import os
from functools import partial

import typer

from specify_cli.consolidation.drivers import (
    META_DRIVER_TWO_WAY_ENV,
    MERGE_DRIVER_BODIES,
    MergeDriverBody,
    MergeDriverError,
    run_meta_driver,
)


def _run(body: MergeDriverBody, base_path: str, ours_path: str, theirs_path: str) -> None:
    """Execute *body* and translate its contract to the CLI's exit protocol.

    A :class:`MergeDriverError` becomes ``typer.echo(str(exc), err=True)`` +
    ``typer.Exit(1)`` — ``str(exc)`` is the exact stderr text, never
    reformatted. A returned ``outcome.notice`` (review-cycle's collision
    notice today) is echoed to stdout; the driver still exits 0.
    """
    try:
        outcome = body(base_path, ours_path, theirs_path)
    except MergeDriverError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if outcome.notice:
        typer.echo(outcome.notice)


def merge_driver_event_log(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Merge ``status.events.jsonl`` conflict inputs using event-log semantics."""
    _run(MERGE_DRIVER_BODIES["merge-driver-event-log"], base_path, ours_path, theirs_path)


def merge_driver_meta(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Field-merge conflicting ``meta.json`` blobs; write result to ``ours``."""
    # Base-aware (reads ``%O``) unless the consolidation pipeline's squash set the
    # two-way opt-out variable (#5460). The environment is read here, in the shell,
    # never in the driver body. Kept as a comment, not docstring text: the docstring
    # is the command's help and is pinned by the committed completion manifest.
    two_way = os.environ.get(META_DRIVER_TWO_WAY_ENV) == "1"
    _run(partial(run_meta_driver, two_way=two_way), base_path, ours_path, theirs_path)


def merge_driver_traces(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Union conflicting ``traces/*.md`` documents; write result to ``ours`` (#4894).

    3-way base-aware: reads ``%O`` so a section theirs left UNCHANGED from
    base, while ours edited the same section, is recognized as stale and
    dropped rather than resurrected alongside ours' edit (see
    :func:`specify_cli.consolidation.drivers._drop_stale_theirs_trace_blocks`). The
    remaining union is still section-granularity and append-only via
    :func:`specify_cli.consolidation.drivers.union_trace_texts` -- never a lossy
    line-level global dedup, never fail-closed on an ordinary repeat.
    """
    _run(MERGE_DRIVER_BODIES["merge-driver-traces"], base_path, ours_path, theirs_path)


def merge_driver_issue_matrix(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Row-aware, 3-way merge of ``issue-matrix.json``; write result to ``ours`` (FR-008)."""
    _run(MERGE_DRIVER_BODIES["merge-driver-issue-matrix"], base_path, ours_path, theirs_path)


def merge_driver_acceptance_matrix(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Row-aware, 3-way merge of ``acceptance-matrix.json``; write result to ``ours`` (FR-008)."""
    _run(MERGE_DRIVER_BODIES["merge-driver-acceptance-matrix"], base_path, ours_path, theirs_path)


def merge_driver_review_cycle(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Reconcile a ``review-cycle-N.md`` collision, best-effort, non-aborting.

    Two distinct verdict documents colliding under the same filename are
    NEVER unioned/field-merged/interleaved into one document -- see the
    module-level design-decision comment in ``specify_cli.consolidation.drivers``,
    immediately above :func:`specify_cli.consolidation.drivers.run_review_cycle_driver`,
    for the full reasoning (embed both verbatim, never fabricate a blended
    verdict). Unlike WP18's original T077 driver, a divergent collision no
    longer aborts the squash (FR-014/D-PLAN-6): the ``.md`` render is
    non-authoritative, unread prose now that ``status.events.jsonl``'s
    ``review_result`` event slot is the sole verdict authority, so refusing
    the merge over it is no longer justified.

    Identical content on both sides (byte-for-byte) is the trivial fast path:
    resolves cleanly, exit 0, never reported as a conflict. Otherwise, both
    raw documents are embedded verbatim inside standard git-style conflict
    markers (never blended field-by-field -- a review verdict has no safely
    mergeable sub-fields the way a JSON matrix row does) and the driver
    exits 0, so ``git merge --squash`` treats the path as resolved
    and the squash proceeds.
    """
    _run(MERGE_DRIVER_BODIES["merge-driver-review-cycle"], base_path, ours_path, theirs_path)


def merge_driver_decision_index(
    base_path: str = typer.Argument(..., metavar="BASE"),
    ours_path: str = typer.Argument(..., metavar="OURS"),
    theirs_path: str = typer.Argument(..., metavar="THEIRS"),
) -> None:
    """Union ``decisions/index.json`` entries keyed by ``decision_id`` (FR-009b/#5023).

    See ``specify_cli.consolidation.drivers.run_decision_index_driver``'s
    docstring for the full collision/precedence semantics: a terminal status
    (resolved/deferred/canceled) beats ``open``; the one legal reopen pair
    (deferred -> resolved) takes the reopen target; any other divergence, or
    malformed input, is a conflict (non-zero exit) -- never a silently
    picked side.
    """
    _run(MERGE_DRIVER_BODIES["merge-driver-decision-index"], base_path, ours_path, theirs_path)
