"""Truth table of ``UpgradeOutcome``: kind, reasons, messages, status and closing line.

No CLI here: every combination of the failure inputs the finalizer can record is
built directly and the outcome's derived values are compared with the contract
(``contracts/upgrade-outcome-contract.md``) and the five invariants of
``data-model.md``. The expected values below are written out independently of
the implementation (an explicit order, an explicit closing-line table), so a
change to the production precedence or wording fails here.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from specify_cli.upgrade.outcome import (
    RepairOutcome,
    SurfaceRepairReport,
    UpgradeFailureReason,
    UpgradeOutcome,
    UpgradeOutcomeKind,
)
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FROM = "3.1.0"
_TO = "3.2.0"
_DRIFT_PATHS = (Path("/proj/.claude/agents/a.md"), Path("/proj/.claude/agents/b.md"))
_DRIFT_MESSAGE = "Unresolved tool-surface drift in 2 file(s); run 'spec-kitty doctor tool-surfaces' to review."

# Message each failure input contributes; the order here is the contract's order for ``errors()``.
_MIGRATION_ERROR = "migration boom"
_COMMIT_ERROR = "auto-commit recovery boom"
_ACTIVATION_ERROR = "activation boom"
_PREPARATION_ERROR = "Owner effect conflict at /proj/.claude"
_WORKTREE_FAILURE = "lane-a: schema stamp failed"
_REPAIR_MESSAGE = "Tool-surface repair for agent_profiles was not applied (failed); re-run 'spec-kitty upgrade'."
_PREVIEW_NOTICE = "Supporting repair preview incomplete: owner assessment incomplete."

# The contract's order of ``errors()``: migration-run errors (which include a commit-recovery
# failure appended after them), activation errors, worktree failures, repair messages, drift.
_ERROR_ORDER = ("migration_failed", "commit_recovery", "activation", "worktree", "repair_preparation", "repair_failed", "preview_incomplete", "drift")
_FAILURE_INPUTS = ("migration_failed", "activation", "worktree", "commit_recovery", "repair_preparation", "repair_failed", "preview_incomplete", "drift")

# Closing lines by (kind, dry_run), spelled out here rather than imported.
_CLOSING_LINES = {
    (UpgradeOutcomeKind.NO_OP, False): "Project is already up to date!",
    (UpgradeOutcomeKind.NO_OP, True): "Project is already up to date!",
    (UpgradeOutcomeKind.APPLIED, False): f"Upgrade complete! {_FROM} -> {_TO}",
    (UpgradeOutcomeKind.APPLIED, True): f"Dry run complete — no changes applied. ({_FROM} -> {_TO} previewed)",
    (UpgradeOutcomeKind.DRIFT_UNRESOLVED, False): "Upgrade finished with unresolved tool-surface drift.",
    (UpgradeOutcomeKind.DRIFT_UNRESOLVED, True): "Upgrade finished with unresolved tool-surface drift.",
    (UpgradeOutcomeKind.FAILED, False): "Upgrade failed.",
    (UpgradeOutcomeKind.FAILED, True): "Upgrade failed.",
}
_STATUS_BY_KIND = {
    UpgradeOutcomeKind.APPLIED: "success",
    UpgradeOutcomeKind.NO_OP: "up_to_date",
    UpgradeOutcomeKind.DRIFT_UNRESOLVED: "failed",
    UpgradeOutcomeKind.FAILED: "failed",
}
_REASON_BY_INPUT = {
    "migration_failed": UpgradeFailureReason.MIGRATION_FAILED,
    "activation": UpgradeFailureReason.ACTIVATION_ERROR,
    "worktree": UpgradeFailureReason.WORKTREE_FAILURE,
    "commit_recovery": UpgradeFailureReason.COMMIT_RECOVERY_FAILED,
    "repair_preparation": UpgradeFailureReason.REPAIR_PREPARATION_FAILED,
    "repair_failed": UpgradeFailureReason.SURFACE_REPAIR_FAILED,
    "preview_incomplete": UpgradeFailureReason.PREVIEW_INCOMPLETE,
    "drift": UpgradeFailureReason.SURFACE_DRIFT,
}
_MESSAGE_BY_INPUT = {
    "migration_failed": _MIGRATION_ERROR,
    "activation": _ACTIVATION_ERROR,
    "worktree": _WORKTREE_FAILURE,
    "commit_recovery": _COMMIT_ERROR,
    "repair_preparation": _PREPARATION_ERROR,
    "repair_failed": _REPAIR_MESSAGE,
    "preview_incomplete": _PREVIEW_NOTICE,
    "drift": _DRIFT_MESSAGE,
}


def _reachable(held: frozenset[str], *, dry_run: bool) -> bool:
    """Whether the finalizer can produce this combination (it skips steps after an earlier failure)."""
    if held & {"repair_failed", "preview_incomplete", "drift"} and held & {"migration_failed", "activation", "repair_preparation"}:
        return False  # the surface-repair step never runs after a failed migration, a preparation failure or an activation error
    if "repair_preparation" in held and (dry_run or held & {"migration_failed", "activation"}):
        return False  # repairs are prepared only on a real run after a successful migration, and a preparation failure skips activation
    if "commit_recovery" in held and (dry_run or held & {"activation", "repair_preparation"}):
        return False  # the commit step does not run on a dry run, after an activation error or a preparation failure
    if "preview_incomplete" in held and not dry_run:
        return False  # only a dry run previews
    return not (held & {"repair_failed", "drift"} and dry_run)  # a dry run never applies a repair


def _cases() -> list[tuple[frozenset[str], bool, bool]]:
    cases = []
    for flags in itertools.product((False, True), repeat=len(_FAILURE_INPUTS)):
        held = frozenset(name for name, on in zip(_FAILURE_INPUTS, flags, strict=True) if on)
        for had_migrations, dry_run in itertools.product((False, True), repeat=2):
            if _reachable(held, dry_run=dry_run):
                cases.append((held, had_migrations, dry_run))
    return cases


def _build(held: frozenset[str], *, had_migrations: bool, dry_run: bool) -> UpgradeOutcome:
    result = UpgradeResult(success="migration_failed" not in held, from_version=_FROM, to_version=_TO, dry_run=dry_run)
    outcome = UpgradeOutcome(result=result, had_migrations=had_migrations)
    if "migration_failed" in held:
        result.errors.append(_MIGRATION_ERROR)
    if "commit_recovery" in held:
        outcome.commit_recovery_failed = True
        result.errors.append(_COMMIT_ERROR)
    if "activation" in held:
        outcome.activation_errors = [_ACTIVATION_ERROR]
    if "worktree" in held:
        outcome.worktree_failures = [_WORKTREE_FAILURE]
    if "repair_preparation" in held:
        outcome.repair_preparation_errors = [_PREPARATION_ERROR]
    messages = tuple(_MESSAGE_BY_INPUT[name] for name in ("repair_failed", "preview_incomplete") if name in held)
    outcome.record_surface_repair(
        SurfaceRepairReport(
            drifted_paths=_DRIFT_PATHS if "drift" in held else (),
            failed="repair_failed" in held,
            preview_incomplete="preview_incomplete" in held,
            failure_messages=messages,
        )
    )
    return outcome


def _expected_kind(held: frozenset[str], *, had_migrations: bool) -> UpgradeOutcomeKind:
    if not held:
        return UpgradeOutcomeKind.APPLIED if had_migrations else UpgradeOutcomeKind.NO_OP
    if held == {"drift"}:
        return UpgradeOutcomeKind.DRIFT_UNRESOLVED
    return UpgradeOutcomeKind.FAILED


def _case_id(case: tuple[frozenset[str], bool, bool]) -> str:
    held, had_migrations, dry_run = case
    return "+".join(sorted(held) or ["clean"]) + ("|migrations" if had_migrations else "|no-migrations") + ("|dry-run" if dry_run else "")


_ALL_CASES = _cases()


@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(case) for case in _ALL_CASES])
def test_outcome_truth_table(case: tuple[frozenset[str], bool, bool]) -> None:
    held, had_migrations, dry_run = case
    outcome = _build(held, had_migrations=had_migrations, dry_run=dry_run)
    kind = _expected_kind(held, had_migrations=had_migrations)
    expected_order = [name for name in _FAILURE_INPUTS if name in held]

    assert outcome.reasons == tuple(_REASON_BY_INPUT[name] for name in expected_order)
    assert outcome.kind is kind
    assert outcome.status == _STATUS_BY_KIND[kind]
    assert outcome.effective_success is (not held)
    assert outcome.closing_line() == _CLOSING_LINES[(kind, dry_run)]
    assert outcome.derive_exit_code() == (1 if held else 0)

    assert outcome.errors() == [_MESSAGE_BY_INPUT[name] for name in _ERROR_ORDER if name in held]


@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(case) for case in _ALL_CASES])
def test_outcome_invariants(case: tuple[frozenset[str], bool, bool]) -> None:
    held, had_migrations, dry_run = case
    outcome = _build(held, had_migrations=had_migrations, dry_run=dry_run)
    exit_code = outcome.derive_exit_code()
    errors = outcome.errors()

    # 1. exit 0 iff the kind is applied or no-op
    assert (exit_code == 0) is (outcome.kind in {UpgradeOutcomeKind.APPLIED, UpgradeOutcomeKind.NO_OP})
    # 2. status is "failed" iff the exit code is non-zero
    assert (outcome.status == "failed") is (exit_code != 0)
    # 3. a non-zero exit always has at least one error
    assert exit_code == 0 or errors
    # 4. the drift message appears iff a file is drifted, and its count is that number
    drift_lines = [error for error in errors if error.startswith("Unresolved tool-surface drift in ")]
    assert bool(drift_lines) is ("drift" in held)
    assert all(f"in {len(_DRIFT_PATHS)} file(s)" in line for line in drift_lines)
    assert not any("in 0 file(s)" in error for error in errors)
    # every explaining message of a held input is listed, once
    for name in held:
        assert errors.count(_MESSAGE_BY_INPUT[name]) == 1
    # 5. a mission-state repair never contributes a reason (see the dedicated tests below)


def test_repair_failure_with_two_drifted_files_is_failed_and_reports_both() -> None:
    """Precedence: a repair failure beats drift, and both messages and the count survive."""
    outcome = _build(frozenset({"repair_failed", "drift"}), had_migrations=False, dry_run=False)

    assert outcome.kind is UpgradeOutcomeKind.FAILED
    assert outcome.reasons == (UpgradeFailureReason.SURFACE_REPAIR_FAILED, UpgradeFailureReason.SURFACE_DRIFT)
    assert outcome.errors() == [_REPAIR_MESSAGE, _DRIFT_MESSAGE]
    assert outcome.closing_line() == "Upgrade failed."
    assert outcome.derive_exit_code() == 1


@pytest.mark.parametrize("repair", [RepairOutcome(declined=True), RepairOutcome(ran=True, failed=True, message="boom"), RepairOutcome(pending=True)])
@pytest.mark.parametrize("had_migrations", [False, True])
def test_mission_state_repair_never_adds_a_reason_or_an_error(repair: RepairOutcome, had_migrations: bool) -> None:
    outcome = _build(frozenset(), had_migrations=had_migrations, dry_run=False)
    before = (outcome.kind, outcome.reasons, outcome.errors(), outcome.status, outcome.closing_line())
    outcome.repair = repair

    assert (outcome.kind, outcome.reasons, outcome.errors(), outcome.status, outcome.closing_line()) == before
    assert outcome.derive_exit_code() == 0


def test_mission_state_repair_failure_the_gate_did_not_show_is_a_warning_only() -> None:
    outcome = _build(frozenset(), had_migrations=False, dry_run=False)
    outcome.result.warnings.append("a run warning")
    outcome.repair = RepairOutcome(failed=True, message="Mission-state repair boundary raised: boom", surface_message=True)

    assert outcome.warnings() == ["a run warning", "Mission-state repair boundary raised: boom"]
    assert outcome.kind is UpgradeOutcomeKind.NO_OP
    assert outcome.errors() == []


def test_mission_state_repair_failure_the_gate_already_showed_is_not_repeated() -> None:
    outcome = _build(frozenset(), had_migrations=False, dry_run=False)
    outcome.repair = RepairOutcome(failed=True, message="gate printed this itself")

    assert outcome.warnings() == []


@pytest.mark.parametrize(
    ("held", "expected"),
    [
        ("migration_failed", "The migrations did not complete."),
        ("commit_recovery", "The upgrade changes could not be committed cleanly."),
        ("repair_failed", "Tool-surface repair did not complete; re-run 'spec-kitty upgrade'."),
        ("preview_incomplete", "The upgrade preview could not be completed."),
    ],
)
def test_a_reason_without_a_message_still_gets_an_error_line(held: str, expected: str) -> None:
    """Invariant 3 holds even when the failing step left no message of its own."""
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=held != "migration_failed", from_version=_FROM, to_version=_TO, dry_run=held == "preview_incomplete"),
        commit_recovery_failed=held == "commit_recovery",
        surface_repair_failed=held == "repair_failed",
        preview_incomplete=held == "preview_incomplete",
    )

    assert outcome.errors() == [expected]
    assert outcome.derive_exit_code() == 1


def test_a_repair_failure_without_a_message_is_named_next_to_the_drift_line() -> None:
    """The generic repair line is per reason: another message in the list does not suppress it."""
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO),
        drifted_paths=[_DRIFT_PATHS[0]],
        surface_repair_failed=True,
    )

    assert outcome.kind is UpgradeOutcomeKind.FAILED
    assert outcome.errors() == [
        "Tool-surface repair did not complete; re-run 'spec-kitty upgrade'.",
        "Unresolved tool-surface drift in 1 file(s); run 'spec-kitty doctor tool-surfaces' to review.",
    ]


def test_an_incomplete_preview_without_a_message_is_named_next_to_another_error() -> None:
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO, dry_run=True),
        worktree_failures=[_WORKTREE_FAILURE],
        preview_incomplete=True,
    )

    assert outcome.errors() == [_WORKTREE_FAILURE, "The upgrade preview could not be completed."]


def test_worktree_failure_mirrored_into_result_errors_is_listed_once() -> None:
    """The migrations path mirrors worktree failures into ``result.errors``; the list de-duplicates."""
    outcome = UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO, errors=[_WORKTREE_FAILURE]), had_migrations=True)
    outcome.worktree_failures = [_WORKTREE_FAILURE, "lane-b: schema stamp failed"]

    assert outcome.errors() == [_WORKTREE_FAILURE, "lane-b: schema stamp failed"]


def test_drift_message_points_at_the_review_command_and_never_at_an_overwrite_option() -> None:
    outcome = _build(frozenset({"drift"}), had_migrations=False, dry_run=False)

    (message,) = outcome.errors()
    assert "spec-kitty doctor tool-surfaces" in message
    assert "--fix" not in message
    assert "overwrite" not in message.lower()


def test_recording_a_second_report_replaces_the_first() -> None:
    outcome = _build(frozenset({"repair_failed", "drift"}), had_migrations=False, dry_run=False)

    outcome.record_surface_repair(SurfaceRepairReport())

    assert outcome.reasons == ()
    assert outcome.drifted_paths == []
    assert outcome.surface_repair_messages == []
    assert outcome.kind is UpgradeOutcomeKind.NO_OP


def test_a_success_that_carries_an_error_diagnostic_still_lists_it() -> None:
    """``errors()`` reports what was collected; the kind and exit code are decided by reasons alone."""
    outcome = UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO, errors=["an error diagnostic"]))

    assert outcome.errors() == ["an error diagnostic"]
    assert outcome.derive_exit_code() == 0


def _only_migration_failed() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=False, from_version=_FROM, to_version=_TO))


def _only_activation_error() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), activation_errors=[_ACTIVATION_ERROR])


def _only_worktree_failure() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), worktree_failures=[_WORKTREE_FAILURE])


def _only_commit_recovery_failed() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), commit_recovery_failed=True)


def _only_repair_preparation_failed() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), repair_preparation_errors=[_PREPARATION_ERROR])


def _only_surface_repair_failed() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), surface_repair_failed=True)


def _only_preview_incomplete() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO, dry_run=True), preview_incomplete=True)


def _only_surface_drift() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO), drifted_paths=[_DRIFT_PATHS[0]])


# One factory per failure reason: each builds an outcome in which ONLY that reason holds.
_OUTCOME_BY_REASON = {
    UpgradeFailureReason.MIGRATION_FAILED: _only_migration_failed,
    UpgradeFailureReason.ACTIVATION_ERROR: _only_activation_error,
    UpgradeFailureReason.WORKTREE_FAILURE: _only_worktree_failure,
    UpgradeFailureReason.COMMIT_RECOVERY_FAILED: _only_commit_recovery_failed,
    UpgradeFailureReason.REPAIR_PREPARATION_FAILED: _only_repair_preparation_failed,
    UpgradeFailureReason.SURFACE_REPAIR_FAILED: _only_surface_repair_failed,
    UpgradeFailureReason.PREVIEW_INCOMPLETE: _only_preview_incomplete,
    UpgradeFailureReason.SURFACE_DRIFT: _only_surface_drift,
}


def test_the_truth_table_exercises_every_failure_reason() -> None:
    """A new ``UpgradeFailureReason`` member must get a row in the matrix, not be silently untested."""
    exercised = {_REASON_BY_INPUT[name] for held, _, _ in _ALL_CASES for name in held}

    assert exercised == set(UpgradeFailureReason)
    assert set(_REASON_BY_INPUT.values()) == set(UpgradeFailureReason)


def test_every_failure_reason_has_a_single_reason_factory() -> None:
    assert set(_OUTCOME_BY_REASON) == set(UpgradeFailureReason)


@pytest.mark.parametrize("reason", list(UpgradeFailureReason), ids=lambda reason: reason.value)
def test_a_lone_failure_reason_exits_non_zero_and_explains_itself(reason: UpgradeFailureReason) -> None:
    """Invariant 3 for every reason on its own: it is reported, it fails the run, and it says why."""
    outcome = _OUTCOME_BY_REASON[reason]()

    assert outcome.reasons == (reason,)
    assert outcome.derive_exit_code() != 0
    assert outcome.errors()
