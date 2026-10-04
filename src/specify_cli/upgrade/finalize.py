"""Shared post-migration finalizer for ``spec-kitty upgrade`` (FR-007/FR-011, C4).

``finalize_upgrade`` owns the ORDERING of the shared upgrade tail — activation
provisioning, surface repair, the single churn commit, and scoped mission-state
repair — but not the step implementations themselves. Those live one layer up
in ``cli.commands.upgrade`` (``_provision_missing_mission_type_activations``,
``_finalizer_step_surface_repair``, ...) and are supplied here as **injected
callables**. This module MUST NOT import ``cli.commands`` — the dependency
direction is ``cli.commands -> upgrade``, and the finalizer reaching back up
would both invert that layering and recreate the WP03<->WP04 cycle the split
exists to avoid (D-2, research.md D-11).

The finalizer is the single path for both the no-migrations (normalized) and
migrations-pending branches (D-3): callers wrap whichever ``UpgradeResult``
applies into an ``UpgradeOutcome`` before calling in — this module does not
branch on which case it received.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, nullcontext

from .outcome import RepairOutcome, UpgradeOutcome


def finalize_upgrade(
    outcome: UpgradeOutcome,
    *,
    provision_activations: Callable[[], Sequence[str]],
    run_surface_repair: Callable[[], bool],
    offer_repair: Callable[[], RepairOutcome],
    commit_churn: Callable[[], bool],
    should_commit: bool,
    repair_preflight: AbstractContextManager[Sequence[str]] | None = None,
) -> UpgradeOutcome:
    """Sequence the shared post-migration tail and derive the exit code once.

    Ordered steps (C4/D-4):
      1. ``provision_activations()`` — mission-type activation provisioning
         (+ any dry-run notice the callable itself prints, D-11). Its
         returned error strings feed ``outcome.activation_errors``.
      2. ``run_surface_repair()`` — surface-repair writes. Its boolean result
         feeds ``outcome.surface_drift_failed``.
      3. ``commit_churn()`` — the single churn commit, run iff *should_commit*
         (the decision from ``should_auto_commit``, C2). Surface-repair
         writes from step 2 land INSIDE this commit; mission-state repair
         (step 4) never does (D-4, #2491/SC-008).
      4. ``offer_repair()`` — the scoped mission-state consent gate, run
         inside a failure-isolating boundary (see :func:`_run_repair_isolated`)
         whose outcome does NOT feed ``exit_code`` (FR-014). Its own commit,
         if any, is the gate's responsibility, never folded into step 3.

    The exit code is derived exactly once, at the end, from ``outcome``
    (D-5) — no other site in the upgrade flow may compute it independently.
    """
    # Keep owner locks around only the two dependent write phases, never Git
    # commits or the independently consented mission-state repair prompt.
    with repair_preflight if repair_preflight is not None else nullcontext(()) as errors:
        outcome.activation_errors = list(errors)
        if not outcome.activation_errors:
            outcome.activation_errors = list(provision_activations())
        if not outcome.activation_errors:
            outcome.surface_drift_failed = bool(run_surface_repair())

    if should_commit and not outcome.activation_errors:
        outcome.committed = bool(commit_churn())

    outcome.repair = _run_repair_isolated(offer_repair)

    outcome.derive_exit_code()
    return outcome


def _run_repair_isolated(offer_repair: Callable[[], RepairOutcome]) -> RepairOutcome:
    """Run the scoped consent/repair step inside a failure-isolating boundary.

    A repair failure — or an unexpected exception raised by the injected
    callable itself — must never sink an otherwise-completed upgrade
    (FR-014): it is folded into ``RepairOutcome.failed`` here, and
    ``finalize_upgrade`` never lets it feed ``exit_code``.
    """
    try:
        return offer_repair()
    except Exception as exc:  # noqa: BLE001 - isolation boundary: repair must not crash the upgrade tail
        return RepairOutcome(failed=True, message=f"Mission-state repair boundary raised: {exc}")
