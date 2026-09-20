"""Regression: `not-applicable` issue-matrix verdict (#3469, WP02).

Pinned ATDD regression for the move-task-approval-ergonomics-01M302R0
mission: :class:`~specify_cli.cli.commands.review._issue_matrix
.IssueMatrixVerdict` gains a ``not-applicable`` member that is **non-gating**
at the ``approved`` transition and **terminal** at ``done``/merge (contrast
``in-mission``, which is accepted at ``approved`` but rejected at ``done``).
See ``contracts/classification-and-verdict-contract.md`` C3 and
``data-model.md`` under
``kitty-specs/move-task-approval-ergonomics-01M302R0/``.

RED on the pre-WP02 codebase: ``not-applicable`` did not exist as an
``IssueMatrixVerdict`` member, so every row-level assertion below failed with
a "verdict '...' is not in the allowed set" approval-blocker message (or a
``ValueError``/``IssueVerdictError`` at the CLI-validation layer), and the
approval blocker gated on every discovered reference regardless of the WP01
classifier's output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.issue_verdict import IssueVerdictError, _validate_verdict
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _issue_matrix_approval_blocker,
)
from specify_cli.cli.commands.review._issue_matrix import IssueMatrixVerdict
from specify_cli.status.models import Lane

pytestmark = [pytest.mark.regression, pytest.mark.fast]


def _write_issue_matrix(
    feature_dir: Path,
    verdict: str,
    evidence_ref: str = "context only -- no work owed by this mission",
    issue: str = "#1582",
) -> None:
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue | verdict | evidence_ref |",
                "| --- | --- | --- |",
                f"| {issue} | {verdict} | {evidence_ref} |",
            ]
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# C3.1/C3.2 -- vocabulary: additive, four legacy values unchanged
# ---------------------------------------------------------------------------


def test_not_applicable_is_a_genuine_issue_matrix_verdict_member() -> None:
    """C3.1: `not-applicable` parses as a genuine `IssueMatrixVerdict` member."""
    assert IssueMatrixVerdict("not-applicable") is IssueMatrixVerdict.NOT_APPLICABLE


def test_legacy_verdicts_still_validate_unchanged() -> None:
    """C3.2/NFR-001: the four pre-existing verdicts are unaffected (additive-only,
    no reorder/rename -- an existing issue-matrix.json needs no migration)."""
    assert IssueMatrixVerdict("fixed") is IssueMatrixVerdict.FIXED
    assert IssueMatrixVerdict("verified-already-fixed") is IssueMatrixVerdict.VERIFIED_ALREADY_FIXED
    assert IssueMatrixVerdict("deferred-with-followup") is IssueMatrixVerdict.DEFERRED_WITH_FOLLOWUP
    assert IssueMatrixVerdict("in-mission") is IssueMatrixVerdict.IN_MISSION


# ---------------------------------------------------------------------------
# CLI acceptance -- `issue-verdict --verdict not-applicable`
# ---------------------------------------------------------------------------


def test_issue_verdict_cli_validation_accepts_not_applicable() -> None:
    """`issue-verdict --verdict not-applicable` is accepted by CLI validation.

    ``_validate_verdict`` is the sole gatekeeper the ``issue-verdict`` command
    routes ``--verdict`` through (raises ``IssueVerdictError`` for anything
    outside the closed set) -- exercising it directly is the precise unit
    check for "the CLI accepts this value" without rebuilding the command's
    full write-seam harness.
    """
    assert _validate_verdict("not-applicable") == "not-applicable"


def test_issue_verdict_cli_validation_still_rejects_unknown_values() -> None:
    with pytest.raises(IssueVerdictError) as exc_info:
        _validate_verdict("wontfix")
    assert exc_info.value.code == "invalid_verdict"
    assert "not-applicable" in str(exc_info.value)


# ---------------------------------------------------------------------------
# C3.3 -- non-gating at `approved`
# ---------------------------------------------------------------------------


def test_not_applicable_row_does_not_block_approved_transition(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_issue_matrix(feature_dir, "not-applicable")

    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED) is None
    # Default target_lane (unspecified) behaves like `approved`.
    assert _issue_matrix_approval_blocker(feature_dir) is None


# ---------------------------------------------------------------------------
# C3.4 -- terminal at `done`/merge (contrast `in-mission`)
# ---------------------------------------------------------------------------


def test_not_applicable_row_is_terminal_at_done(tmp_path: Path) -> None:
    """Unlike `in-mission`, `not-applicable` passes the `done`/merge
    completeness gate unchanged -- it never re-blocks at merge."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_issue_matrix(feature_dir, "not-applicable")

    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE) is None


def test_in_mission_still_blocks_done_unlike_not_applicable(tmp_path: Path) -> None:
    """Contrast fixture: `in-mission` on the SAME reference still blocks
    `done` -- confirms `not-applicable`'s terminal behavior is not just an
    accidental blanket pass-through."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_issue_matrix(feature_dir, "in-mission", evidence_ref="WP14 (this mission)")

    blocker = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE)
    assert blocker is not None
    assert "in-mission" in blocker


# ---------------------------------------------------------------------------
# T009 -- approval blocker gates only implementation_target references
# ---------------------------------------------------------------------------


def test_approval_blocker_never_requires_matrix_for_context_only_reference(
    tmp_path: Path,
) -> None:
    """FR-011/FR-013 lever SSOT: classification decides row-REQUIREMENT.

    A purely context-only reference (WP01 classifier: `context_only`, via
    the `baseline-red` marker) never requires an issue-matrix row -- or even
    an issue-matrix artifact at all. No `issue-matrix.md`/`.json` exists in
    this fixture; approval must not be blocked.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Known baseline-red until #1582 lands.\n", encoding="utf-8")

    assert _issue_matrix_approval_blocker(feature_dir) is None


def test_approval_blocker_still_gates_implementation_target_reference(
    tmp_path: Path,
) -> None:
    """Control fixture: an unmarked bare `#NNNN` (implementation_target,
    FR-011 fail-safe default) still requires a matrix -- the classifier
    wiring narrows gating, it does not disable it."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "#1582" in blocker
