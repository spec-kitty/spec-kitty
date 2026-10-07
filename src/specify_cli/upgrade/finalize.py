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

from .outcome import MissionStateReportOutcome, SurfaceRepairReport, UpgradeOutcome


def finalize_upgrade(
    outcome: UpgradeOutcome,
    *,
    provision_activations: Callable[[], Sequence[str]],
    run_surface_repair: Callable[[], SurfaceRepairReport],
    report_mission_state: Callable[[], MissionStateReportOutcome],
    commit_churn: Callable[[], bool],
    should_commit: bool,
    repair_preflight: AbstractContextManager[Sequence[str]] | None = None,
) -> UpgradeOutcome:
    """Sequence the shared post-migration tail and record each step's result on the outcome.

    Ordered steps (C4/D-4):
      0. ``repair_preflight`` — the repair preparation and preflight errors feed
         ``outcome.repair_preparation_errors``; when any exist, steps 1-3 are skipped.
      1. ``provision_activations()`` — mission-type activation provisioning
         (+ any dry-run notice the callable itself prints, D-11). Its
         returned error strings feed ``outcome.activation_errors``.
      2. ``run_surface_repair()`` — surface-repair writes. The
         ``SurfaceRepairReport`` it returns is recorded on the outcome
         (drifted files, a repair that was not applied, an incomplete
         preview), so each condition is reported for what it is.
      3. ``commit_churn()`` — the single churn commit, run iff *should_commit*
         (the decision from ``should_auto_commit``, C2). Surface-repair
         writes from step 2 land INSIDE this commit; mission-state repair
         (step 4) never does (D-4, #2491/SC-008).
      4. ``report_mission_state()`` — the report-only mission-state gate (it never
         repairs; ADR 2026-10-07-1), run inside a failure-isolating boundary
         (see :func:`_run_report_isolated`) whose outcome does NOT feed
         ``exit_code`` (FR-014).

    The exit code is not computed here: ``UpgradeOutcome.exit_code`` derives it from
    the outcome's kind whenever it is read (D-5), so it can never disagree with the
    kind, the status or the closing line.
    """
    # Keep owner locks around only the two dependent write phases, never Git
    # commits or the independently consented mission-state repair prompt.
    with repair_preflight if repair_preflight is not None else nullcontext(()) as errors:
        outcome.repair_preparation_errors = list(errors)
        if not outcome.repair_preparation_errors:
            outcome.activation_errors = list(provision_activations())
        if not outcome.repair_preparation_errors and not outcome.activation_errors:
            outcome.record_surface_repair(run_surface_repair())

    if should_commit and not outcome.repair_preparation_errors and not outcome.activation_errors:
        outcome.committed = bool(commit_churn())

    outcome.repair = _run_report_isolated(report_mission_state)
    return outcome


def _run_report_isolated(report_mission_state: Callable[[], MissionStateReportOutcome]) -> MissionStateReportOutcome:
    """Run the scoped consent/repair step inside a failure-isolating boundary.

    A repair failure — or an unexpected exception raised by the injected
    callable itself — must never sink an otherwise-completed upgrade
    (FR-014): it is folded into ``MissionStateReportOutcome.failed`` here, and
    ``finalize_upgrade`` never lets it feed ``exit_code``. The gate never saw
    this failure, so its message is flagged for the outcome to list as a warning.
    """
    try:
        return report_mission_state()
    except Exception as exc:  # noqa: BLE001 - isolation boundary: repair must not crash the upgrade tail
        return MissionStateReportOutcome(failed=True, message=f"Mission-state report boundary raised: {exc}", surface_message=True)
