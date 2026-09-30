"""SaaS-sink fanout deferral helper (T041, FR-022, NFR-009, SC-09).

This module is the thin adapter between :class:`BookkeepingTransaction`
and the SaaS event sink.  The transaction's :meth:`defer_outbound` hook
takes a zero-arg callable that fires **after the local commit succeeds**;
this module wraps that contract for the specific SaaS use case so call
sites stay one line:

    from specify_cli.coordination.outbound import queue_saas_emission
    queue_saas_emission(txn, event)

Rather than:

    from specify_cli.status import fire_saas_fanout
    txn.defer_outbound(lambda: fire_saas_fanout(...))

Rationale: FR-022 requires that no outbound side-effect fires if the
local commit rolls back.  Routing every SaaS emission through
``queue_saas_emission`` (which delegates to ``txn.defer_outbound``)
guarantees that property without spreading the contract across every
call site.

NFR-009 / SC-09 (no spurious outbound on rollback) is verified in
``tests/specify_cli/coordination/test_outbound.py``.

This module deliberately does **not** migrate existing direct callers of
``fire_saas_fanout``.  Migrating those call sites is out of scope for
WP09 (would expand the touched-files set well beyond hardening tests);
this module is the opt-in surface that future work can route through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.coordination.transaction import BookkeepingTransaction
    from specify_cli.status import StatusEvent


def queue_saas_emission(
    txn: BookkeepingTransaction,
    event: StatusEvent,
    *,
    mission_slug: str | None = None,
    repo_root: Any = None,
) -> None:
    """Register a SaaS outbound emission to fire after the local commit succeeds.

    Parameters
    ----------
    txn:
        The active :class:`BookkeepingTransaction`.
    event:
        The :class:`StatusEvent` to fan out.
    mission_slug:
        Optional override; defaults to ``txn.mission_slug`` when omitted.
    repo_root:
        Optional override; defaults to ``txn.repo_root`` when omitted.

    The emission is **not** fired synchronously.  It is appended to the
    transaction's ``_deferred`` queue and runs only after
    :func:`BookkeepingTransaction.commit` returns successfully.  On
    commit failure, the deferred queue is skipped — guaranteeing
    NFR-009 / SC-09 (no SaaS event for a rolled-back local commit).

    Individual fanout failures are logged inside
    :meth:`BookkeepingTransaction._run_deferred_outbound` but never abort
    the rest of the queue (best-effort per FR-022).
    """
    resolved_slug = mission_slug if mission_slug is not None else txn.mission_slug
    resolved_repo = repo_root if repo_root is not None else txn.repo_root

    def _fire() -> None:
        _send_to_saas(
            event,
            resolved_slug,
            resolved_repo,
        )

    txn.defer_outbound(_fire)


def _send_to_saas(
    event: StatusEvent,
    mission_slug: str,
    repo_root: Any,
) -> None:
    """Forward ``event`` to the canonical SaaS fanout adapter.

    The actual sink boundary lives in :mod:`specify_cli.status.adapters`
    as ``fire_saas_fanout``.  We import lazily so tests can monkeypatch
    the adapter without forcing this module to carry the dependency at
    import time.

    The default ``fire_saas_fanout`` signature accepts ``**kwargs`` and
    routes through the SaaS sync wiring.  Callers that already have a
    structured ``StatusEvent`` need only pass it through.
    """
    from specify_cli.status import fire_saas_fanout  # noqa: PLC0415
    from specify_cli.status import WPStatusChangeMetadata  # noqa: PLC0415

    fire_saas_fanout(
        wp_id=event.wp_id,
        from_lane=str(event.from_lane),
        to_lane=str(event.to_lane),
        actor=event.actor,
        mission_slug=mission_slug,
        mission_id=event.mission_id,
        metadata=WPStatusChangeMetadata.from_status_event(
            event, policy_metadata=event.policy_metadata
        ),
        # The emitting checkout root, so the Zeitgeist bridge resolves relay
        # credentials from it instead of the process cwd (#125).
        repo_root=repo_root,
    )
