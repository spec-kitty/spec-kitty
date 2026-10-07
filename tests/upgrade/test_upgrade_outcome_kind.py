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
_PROJECT = Path("/proj")
_DRIFT_PATHS = (_PROJECT / ".claude/agents/a.md", _PROJECT / ".claude/agents/b.md")
_DRIFT_REASONS = {_DRIFT_PATHS[0]: "Managed profile drift requires exact-path consent", _DRIFT_PATHS[1]: "edited by hand"}
_DRIFT_LINES = [
    "Not updated, your local edit was kept: .claude/agents/a.md (Managed profile drift requires exact-path consent)",
    "Not updated, your local edit was kept: .claude/agents/b.md (edited by hand)",
]
_DRIFT_GUIDANCE = (
    "To take the current version of a file, delete it and run 'spec-kitty upgrade' again. "
    "To keep your edit, leave the file as it is. 'spec-kitty doctor tool-surfaces' shows each file's state."
)
_DRIFT_CLOSING = "Upgrade finished, but 2 managed file(s) with local edits were not updated."

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
    (UpgradeOutcomeKind.DRIFT_UNRESOLVED, False): _DRIFT_CLOSING,
    (UpgradeOutcomeKind.DRIFT_UNRESOLVED, True): _DRIFT_CLOSING,
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
_MESSAGES_BY_INPUT = {
    "migration_failed": [_MIGRATION_ERROR],
    "activation": [_ACTIVATION_ERROR],
    "worktree": [_WORKTREE_FAILURE],
    "commit_recovery": [_COMMIT_ERROR],
    "repair_preparation": [_PREPARATION_ERROR],
    "repair_failed": [_REPAIR_MESSAGE],
    "preview_incomplete": [_PREVIEW_NOTICE],
    "drift": [*_DRIFT_LINES, _DRIFT_GUIDANCE],
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
    outcome = UpgradeOutcome(result=result, had_migrations=had_migrations, project_root=_PROJECT)
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
    messages = tuple(_MESSAGES_BY_INPUT[name][0] for name in ("repair_failed", "preview_incomplete") if name in held)
    outcome.record_surface_repair(
        SurfaceRepairReport(
            drifted_paths=_DRIFT_PATHS if "drift" in held else (),
            drifted_reasons=_DRIFT_REASONS if "drift" in held else {},
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
    assert outcome.exit_code == (1 if held else 0)

    assert outcome.errors() == [message for name in _ERROR_ORDER if name in held for message in _MESSAGES_BY_INPUT[name]]


def test_repair_failure_with_two_drifted_files_is_failed_and_reports_both() -> None:
    """Precedence: a repair failure beats drift, and both messages and the count survive."""
    outcome = _build(frozenset({"repair_failed", "drift"}), had_migrations=False, dry_run=False)

    assert outcome.kind is UpgradeOutcomeKind.FAILED
    assert outcome.reasons == (UpgradeFailureReason.SURFACE_REPAIR_FAILED, UpgradeFailureReason.SURFACE_DRIFT)
    assert outcome.errors() == [_REPAIR_MESSAGE, *_DRIFT_LINES, _DRIFT_GUIDANCE]
    assert outcome.closing_line() == "Upgrade failed."
    assert outcome.exit_code == 1


@pytest.mark.parametrize("repair", [RepairOutcome(reported=True), RepairOutcome(failed=True, message="boom"), RepairOutcome(pending=True)])
@pytest.mark.parametrize("had_migrations", [False, True])
def test_mission_state_repair_never_adds_a_reason_or_an_error(repair: RepairOutcome, had_migrations: bool) -> None:
    outcome = _build(frozenset(), had_migrations=had_migrations, dry_run=False)
    before = (outcome.kind, outcome.reasons, outcome.errors(), outcome.status, outcome.closing_line())
    outcome.repair = repair

    assert (outcome.kind, outcome.reasons, outcome.errors(), outcome.status, outcome.closing_line()) == before
    assert outcome.exit_code == 0


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
    assert outcome.exit_code == 1


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
        f"Not updated, your local edit was kept: {_DRIFT_PATHS[0]}",
        _DRIFT_GUIDANCE,
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


def test_each_preserved_file_is_named_relative_to_the_project_and_the_list_is_capped() -> None:
    inside = _PROJECT / ".claude/agents/a.md"
    outside = Path("/home/someone/.claude/skills/x/SKILL.md")
    many = [_PROJECT / f"skills/s{index}.md" for index in range(21)]
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=True, from_version=_FROM, to_version=_TO),
        project_root=_PROJECT,
        drifted_paths=[inside, outside, *many],
        drifted_reasons={inside: "edited by hand"},
    )

    errors = outcome.errors()

    assert errors[0] == "Not updated, your local edit was kept: .claude/agents/a.md (edited by hand)"
    assert errors[1] == f"Not updated, your local edit was kept: {outside}"  # outside the project: given as is, no reason known
    assert errors[2] == "Not updated, your local edit was kept: skills/s0.md"
    assert len(errors) == 20 + 2  # the first twenty files, "... and N more", the guidance
    assert errors[-2] == "... and 3 more"
    assert errors[-1] == _DRIFT_GUIDANCE
    assert outcome.closing_line() == "Upgrade finished, but 23 managed file(s) with local edits were not updated."
    # The guidance names what is true: delete + re-run recreates a file, doctor only shows state, nothing overwrites.
    assert "--fix" not in errors[-1]
    assert "overwrite" not in errors[-1].lower()


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
    assert outcome.exit_code == 0


def test_the_truth_table_exercises_every_failure_reason() -> None:
    """A new ``UpgradeFailureReason`` member must get a row in the matrix, not be silently untested."""
    exercised = {_REASON_BY_INPUT[name] for held, _, _ in _ALL_CASES for name in held}

    assert exercised == set(UpgradeFailureReason)
    assert set(_REASON_BY_INPUT.values()) == set(UpgradeFailureReason)
    # A new ``UpgradeOutcomeKind`` must likewise be produced by the table and have a status and a closing line here.
    produced = {_expected_kind(held, had_migrations=had_migrations) for held, had_migrations, _ in _ALL_CASES}
    assert produced == set(UpgradeOutcomeKind) == set(_STATUS_BY_KIND) == {kind for kind, _ in _CLOSING_LINES}
