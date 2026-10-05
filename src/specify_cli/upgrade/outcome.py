"""Outcome value objects for ``spec-kitty upgrade`` (FR-007, D-3, D-9).

``UpgradeOutcome`` is the single object the finalizer produces and everything
the command reports about a run derives from (D-5): the exit code, the outcome
kind, the reasons a run is not a success, the ordered error and warning
messages, the JSON ``status`` and the closing line of the text output. No
presentation code assembles any of these on its own, so the closing line, the
machine-readable status and the exit code can never describe different results.

It *composes* the existing ``UpgradeResult`` (``runner.py``) as a field rather
than replacing it, so JSON and human renderers keep the fields they already
consume (``from_version``, ``to_version``, ``migrations_applied`` and friends).

``SurfaceRepairReport`` is the return contract for the finalizer's surface-repair
step: it separates the three conditions a single boolean used to carry
(unresolved drift, a repair that was not applied, an incomplete dry-run
preview) so each is reported for what it is.

``RepairOutcome`` is the return contract for the scoped mission-state repair
gate (``_teamspace_mission_state_gate.offer_teamspace_mission_state_migration``,
D-9) — it replaces the three ``typer.Exit(1)`` raises that function used to
perform. ``declined`` is set ONLY on the post-consent-decision deny path;
``pending`` is set by the gate's pre-consent early returns instead. This
distinction is what makes a consent spy test non-fakeable (contracts C3):
"repair not called" alone proves nothing when the fixture never reached the
consent decision in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from .runner import UpgradeResult

_DRIFT_MESSAGE = "Unresolved tool-surface drift in {count} file(s); run 'spec-kitty doctor tool-surfaces' to review."

_CLOSING_NO_OP = "Project is already up to date!"
_CLOSING_APPLIED = "Upgrade complete! {from_version} -> {to_version}"
_CLOSING_APPLIED_DRY_RUN = "Dry run complete — no changes applied. ({from_version} -> {to_version} previewed)"
_CLOSING_DRIFT_UNRESOLVED = "Upgrade finished with unresolved tool-surface drift."
_CLOSING_FAILED = "Upgrade failed."


class UpgradeOutcomeKind(StrEnum):
    """What one completed upgrade run amounts to."""

    APPLIED = "applied"
    NO_OP = "no_op"
    DRIFT_UNRESOLVED = "drift_unresolved"
    FAILED = "failed"


SUCCESS_KINDS: frozenset[UpgradeOutcomeKind] = frozenset({UpgradeOutcomeKind.APPLIED, UpgradeOutcomeKind.NO_OP})
"""The kinds that exit 0; every other kind is a failure that must say why."""


class UpgradeFailureReason(StrEnum):
    """Why a run is not a success. Declaration order is the order of ``reasons``."""

    MIGRATION_FAILED = "migration_failed"
    ACTIVATION_ERROR = "activation_error"
    WORKTREE_FAILURE = "worktree_failure"
    COMMIT_RECOVERY_FAILED = "commit_recovery_failed"
    REPAIR_PREPARATION_FAILED = "repair_preparation_failed"
    SURFACE_REPAIR_FAILED = "surface_repair_failed"
    PREVIEW_INCOMPLETE = "preview_incomplete"
    SURFACE_DRIFT = "surface_drift"


_UNEXPLAINED_FAILURE_MESSAGES: dict[UpgradeFailureReason, str] = {
    UpgradeFailureReason.MIGRATION_FAILED: "The migrations did not complete.",
    UpgradeFailureReason.COMMIT_RECOVERY_FAILED: "The upgrade changes could not be committed cleanly.",
    UpgradeFailureReason.SURFACE_REPAIR_FAILED: "Tool-surface repair did not complete; re-run 'spec-kitty upgrade'.",
    UpgradeFailureReason.PREVIEW_INCOMPLETE: "The upgrade preview could not be completed.",
}
"""Fallback wording for a reason that left no message of its own (invariant 3)."""


@dataclass(frozen=True)
class SurfaceRepairReport:
    """What the surface-repair step found, split by condition.

    ``drifted_paths`` are managed files preserved pending the operator's consent.
    ``failed`` means a repair was not applied. ``preview_incomplete`` means a
    dry-run preview could not be completed. ``failure_messages`` carries one
    reason per non-applied repair that gave no error diagnostic of its own, and
    the notice of an incomplete preview.
    """

    drifted_paths: tuple[Path, ...] = ()
    failed: bool = False
    preview_incomplete: bool = False
    failure_messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepairOutcome:
    """Return contract for the scoped mission-state repair gate (D-9).

    ``surface_message`` marks an outcome whose ``message`` was NOT already shown
    to the operator by the gate itself (the finalizer's isolation boundary sets
    it), so the upgrade outcome must list it among its warnings.
    """

    pending: bool = False
    declined: bool = False
    ran: bool = False
    failed: bool = False
    message: str = ""
    surface_message: bool = False


@dataclass
class UpgradeOutcome:
    """The single object every renderer + the exit code derive from (D-3/D-5).

    Composes ``UpgradeResult`` rather than replacing it (see module docstring).
    A mission-state ``repair`` outcome never contributes a reason (FR-014): it
    is an optional, separately-consented step that must not sink an otherwise
    completed upgrade.
    """

    result: UpgradeResult
    manual_review_paths: list[Path] = field(default_factory=list)
    worktree_failures: list[str] = field(default_factory=list)
    activation_errors: list[str] = field(default_factory=list)
    repair_preparation_errors: list[str] = field(default_factory=list)
    repair: RepairOutcome = field(default_factory=RepairOutcome)
    committed: bool = False
    exit_code: int = 0
    had_migrations: bool = False
    drifted_paths: list[Path] = field(default_factory=list)
    surface_repair_failed: bool = False
    preview_incomplete: bool = False
    surface_repair_messages: list[str] = field(default_factory=list)
    commit_recovery_failed: bool = False

    def record_surface_repair(self, report: SurfaceRepairReport) -> None:
        """Fold the surface-repair step's report into the outcome."""
        self.drifted_paths = list(report.drifted_paths)
        self.surface_repair_failed = report.failed
        self.preview_incomplete = report.preview_incomplete
        self.surface_repair_messages = list(report.failure_messages)

    @property
    def reasons(self) -> tuple[UpgradeFailureReason, ...]:
        """Every reason this run is not a success, in declaration order."""
        held = (
            (UpgradeFailureReason.MIGRATION_FAILED, not self.result.success),
            (UpgradeFailureReason.ACTIVATION_ERROR, bool(self.activation_errors)),
            (UpgradeFailureReason.WORKTREE_FAILURE, bool(self.worktree_failures)),
            (UpgradeFailureReason.COMMIT_RECOVERY_FAILED, self.commit_recovery_failed),
            (UpgradeFailureReason.REPAIR_PREPARATION_FAILED, bool(self.repair_preparation_errors)),
            (UpgradeFailureReason.SURFACE_REPAIR_FAILED, self.surface_repair_failed),
            (UpgradeFailureReason.PREVIEW_INCOMPLETE, self.preview_incomplete),
            (UpgradeFailureReason.SURFACE_DRIFT, bool(self.drifted_paths)),
        )
        return tuple(reason for reason, holds in held if holds)

    @property
    def kind(self) -> UpgradeOutcomeKind:
        """Failed beats drift-unresolved; otherwise applied or no-op by whether migrations ran."""
        reasons = self.reasons
        if not reasons:
            return UpgradeOutcomeKind.APPLIED if self.had_migrations else UpgradeOutcomeKind.NO_OP
        if reasons == (UpgradeFailureReason.SURFACE_DRIFT,):
            return UpgradeOutcomeKind.DRIFT_UNRESOLVED
        return UpgradeOutcomeKind.FAILED

    @property
    def effective_success(self) -> bool:
        """True iff no reason holds: the migration result AND every finalizer-owned signal succeeded."""
        return not self.reasons

    @property
    def status(self) -> str:
        """The JSON ``status`` word: ``success``, ``up_to_date`` or ``failed``."""
        kind = self.kind
        if kind is UpgradeOutcomeKind.APPLIED:
            return "success"
        if kind is UpgradeOutcomeKind.NO_OP:
            return "up_to_date"
        return "failed"

    def errors(self) -> list[str]:
        """Every message that explains a non-success, ordered and de-duplicated.

        Order: migration errors, activation errors, worktree failures, repair-preparation
        errors, surface-repair failure messages, then the drift message when any file is drifted (its count
        is ``len(drifted_paths)``). A surface-repair or preview reason that left no
        message of its own gets its generic line even when other messages exist;
        any other reason gets one only when the list would otherwise be empty, so a
        non-zero exit never has an empty list (invariant 3).
        """
        collected = [
            *self.result.errors,
            *self.activation_errors,
            *self.worktree_failures,
            *self.repair_preparation_errors,
            *self.surface_repair_messages,
        ]
        if not self.surface_repair_messages:
            collected.extend(self._unexplained_surface_messages())
        if self.drifted_paths:
            collected.append(_DRIFT_MESSAGE.format(count=len(self.drifted_paths)))
        errors = list(dict.fromkeys(collected))
        if not errors:
            errors = [_UNEXPLAINED_FAILURE_MESSAGES[reason] for reason in self.reasons[:1] if reason in _UNEXPLAINED_FAILURE_MESSAGES]
        return errors

    def _unexplained_surface_messages(self) -> list[str]:
        """Generic lines for a surface-repair or preview reason that recorded no message."""
        held = (
            (UpgradeFailureReason.SURFACE_REPAIR_FAILED, self.surface_repair_failed),
            (UpgradeFailureReason.PREVIEW_INCOMPLETE, self.preview_incomplete),
        )
        return [_UNEXPLAINED_FAILURE_MESSAGES[reason] for reason, holds in held if holds]

    def warnings(self) -> list[str]:
        """Non-fatal messages: the run's warnings plus a mission-state repair failure the gate did not show."""
        warnings = list(self.result.warnings)
        if self.repair.failed and self.repair.surface_message and self.repair.message:
            warnings.append(self.repair.message)
        return warnings

    def closing_line(self) -> str:
        """The headline a text-mode run ends on (plain text, no markup)."""
        kind = self.kind
        if kind is UpgradeOutcomeKind.NO_OP:
            return _CLOSING_NO_OP
        if kind is UpgradeOutcomeKind.DRIFT_UNRESOLVED:
            return _CLOSING_DRIFT_UNRESOLVED
        if kind is UpgradeOutcomeKind.FAILED:
            return _CLOSING_FAILED
        template = _CLOSING_APPLIED_DRY_RUN if self.result.dry_run else _CLOSING_APPLIED
        return template.format(from_version=self.result.from_version, to_version=self.result.to_version)

    def derive_exit_code(self) -> int:
        """Compute, store, and return ``exit_code`` from ``kind``.

        This is the ONLY site that computes the upgrade exit code (D-5) —
        callers must not derive it independently from ``result.success`` or
        any other formula.
        """
        self.exit_code = 0 if self.kind in SUCCESS_KINDS else 1
        return self.exit_code
