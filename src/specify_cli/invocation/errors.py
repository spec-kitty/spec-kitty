"""Structured error types for the invocation package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.invocation.modes import ModeOfWork


class InvocationError(Exception):
    """Base for all invocation errors."""


class ProfileNotFoundError(InvocationError):
    def __init__(self, profile_id: str, available: list[str]) -> None:
        self.profile_id = profile_id
        self.available = available
        super().__init__(f"Profile '{profile_id}' not found. Available: {available}")


class ContextUnavailableError(InvocationError):
    """Governance context could not be assembled (charter not synthesized)."""


class InvocationWriteError(InvocationError):
    """JSONL write failed. Invocation not started."""


class RouterAmbiguityError(InvocationError):
    def __init__(
        self,
        request_text: str,
        error_code: str,  # ROUTER_AMBIGUOUS | ROUTER_NO_MATCH | PROFILE_NOT_FOUND
        candidates: list[dict[str, str]],
        suggestion: str,
    ) -> None:
        self.request_text = request_text
        self.error_code = error_code
        self.candidates = candidates
        self.suggestion = suggestion
        super().__init__(f"{error_code}: {suggestion}")


class LegacyRecordError(InvocationError):
    """A kitty-ops JSONL line uses the pre-v2 (legacy) record shape.

    Raised by ``parse_op_event`` when a line cannot be parsed as a v2
    ``OpStartedEvent`` / ``OpCompletedEvent`` (e.g. a completed event without
    ``closed_by``). Readers should warn once — pointing at ``spec-kitty
    upgrade`` — and skip the record; the WP05 migration rewrites these files.
    """

    def __init__(self, invocation_id: str | None, reason: str) -> None:
        self.invocation_id = invocation_id
        self.reason = reason
        super().__init__(
            f"Legacy Op record{f' {invocation_id}' if invocation_id else ''}: {reason}. "
            "Run 'spec-kitty upgrade' to migrate kitty-ops records to the v2 schema."
        )


class AlreadyClosedError(InvocationError):
    def __init__(self, invocation_id: str) -> None:
        super().__init__(f"Invocation {invocation_id} is already closed.")


class InvalidModeForEvidenceError(InvocationError):
    """--evidence supplied on an invocation whose mode_of_work disallows
    Tier 2 promotion (advisory or query). See FR-009 / ADR-001."""

    #: The recorded mode when it is a recognised one; ``None`` on the
    #: :class:`UndeterminedModeForEvidenceError` subclass, where the record
    #: declares a value that maps to no ``ModeOfWork`` at all.
    mode: "ModeOfWork | None"

    def __init__(self, invocation_id: str, mode: "ModeOfWork") -> None:
        self.invocation_id = invocation_id
        self.mode = mode
        super().__init__(
            f"Cannot promote evidence on invocation {invocation_id}: "
            f"mode is {mode.value}; Tier 2 evidence is only allowed on "
            f"task_execution or mission_step invocations."
        )


class UnsupportedEvidenceError(InvocationError):
    """Evidence content cannot be stored as Tier 2 UTF-8 text (#5397).

    Raised by ``complete_invocation`` BEFORE any write, so the Op is left
    exactly as it was and a corrected retry can still close it.
    Deliberately NOT a subclass of InvalidModeForEvidenceError: the CLI maps
    that one to a human-only exit 2, while this one must reach the generic
    ``complete_failed`` JSON handler (exit 1, contract-frozen shape).
    """

    def __init__(self, invocation_id: str, evidence_label: str, reason: str) -> None:
        self.invocation_id = invocation_id
        self.evidence_label = evidence_label
        self.reason = reason
        super().__init__(
            f"Cannot use {evidence_label} as evidence for invocation {invocation_id}: "
            f"{reason}. Tier 2 evidence must be UTF-8 text. No completion was recorded "
            f"by this call; re-run complete with a UTF-8 text evidence file."
        )


class UndeterminedModeForEvidenceError(InvalidModeForEvidenceError):
    """--evidence supplied on an Op whose recorded ``mode_of_work`` is unreadable.

    Distinct from :class:`InvalidModeForEvidenceError`'s base case, which names
    a mode that is recognised and ineligible. Here the record declares a value
    that maps to no :class:`~specify_cli.invocation.modes.ModeOfWork`, so the
    Op's evidence eligibility **cannot be determined** — and inability to
    determine a permission is never that permission (#3030 FR-003, applied to
    FR-009's gate). Absence of the field is a different state entirely and
    keeps its documented legacy default; only malformation lands here.

    Subclasses the base error so the CLI's existing exit-2 handler covers it
    without a second except clause.
    """

    def __init__(self, invocation_id: str, raw_mode: object) -> None:
        self.invocation_id = invocation_id
        self.mode = None
        self.raw_mode = raw_mode
        # Deliberately bypasses InvalidModeForEvidenceError.__init__: that
        # constructor formats ``mode.value``, which no undetermined value has.
        InvocationError.__init__(
            self,
            f"Cannot promote evidence on invocation {invocation_id}: the record's "
            f"mode_of_work is {raw_mode!r}, which is not a recognised mode, so the "
            f"invocation's evidence eligibility cannot be determined. Repair the "
            f"kitty-ops record (or run 'spec-kitty upgrade') and retry.",
        )
