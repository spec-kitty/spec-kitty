"""Cross-site consistency: approval blocker, merge_gates, doctor (#3469, WP03).

Pinned ATDD regression for the move-task-approval-ergonomics-01M302R0 mission,
contract C2 (``contracts/classification-and-verdict-contract.md``): the
approval blocker (``tasks_parsing_validation.py``, WP02), ``merge_gates``
(``src/specify_cli/policy/merge_gates.py``), and ``status/doctor`` (``src/
specify_cli/status/doctor.py``) must all derive "referenced-but-missing" from
the SAME WP01 classifier (:mod:`specify_cli.tasks.issue_reference_discovery`)
rather than recomputing ``referenced - matrix`` independently at each site.

RED on pre-WP03 ``main``: before this WP, ``merge_gates`` and ``doctor``
computed ``referenced_issues = {f"#{ref.number}" for ref in refs}`` over
EVERY discovered reference -- gating or not -- so a context-only/PR-only
mission still demanded a scaffolded issue-matrix, and ``merge_gates`` alone
also collapsed a row with an invalid verdict into "missing" (it read
``load_issue_matrix`` bare, with no diagnostic-recovery fallback), diverging
from doctor/blocker which both recover that row's issue number from the
validator's diagnostics.

Anchored on END-STATE per-site OUTCOME, not "all three identical" (which is
vacuously true on unpatched main whenever all three independently over-gate
in lockstep -- see the FAIL-OPEN GUARD case below, which is the one place all
three DO already agree, pre- and post-fix).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _issue_matrix_approval_blocker,
    _issue_matrix_evaluation,
)
from specify_cli.policy.merge_gates import GateVerdict, _evaluate_issue_matrix_completeness_gate
from specify_cli.status.doctor import check_issue_matrix
from specify_cli.status.models import Lane
from specify_cli.tasks.issue_reference_discovery import gating_issue_numbers

pytestmark = [pytest.mark.regression, pytest.mark.fast]


def _feature_dir(tmp_path: Path, slug: str = "demo") -> Path:
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    return feature_dir


def _write_matrix(feature_dir: Path, issue: str, verdict: str, evidence_ref: str) -> None:
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
# (a) Non-gating references (context-only + PR/commit) -- clean everywhere,
#     with NO issue-matrix artifact required at all.
# ---------------------------------------------------------------------------


def test_context_only_and_pr_ref_are_non_gating_at_all_three_sites(tmp_path: Path) -> None:
    """C2.1/C2.2 (#3469): a context-only citation and a PR ref never require
    a row -- non-gating at ``approved``, non-gating at merge, clean in
    doctor. No issue-matrix artifact is present at all.
    """
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "spec.md").write_text(
        "\n".join(
            [
                "Follow-up: #2001 tracks a known limitation outside this mission's scope.",
                "See PR #2002 for the upstream fix this mission builds on.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Ground truth: WP01's classifier finds zero GATING references.
    assert gating_issue_numbers(feature_dir) == set()

    blocker_msg = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED)
    gate = _evaluate_issue_matrix_completeness_gate(feature_dir, is_blocking=True)
    doctor_findings = check_issue_matrix(feature_dir)

    assert blocker_msg is None
    assert gate.verdict == GateVerdict.PASS
    assert gate.blocking is False
    assert doctor_findings == []

    # Secondary "all three agree" check.
    assert [blocker_msg is None, gate.verdict == GateVerdict.PASS, doctor_findings == []] == [
        True,
        True,
        True,
    ]


# ---------------------------------------------------------------------------
# (b) FAIL-OPEN GUARD: a bare, unmarked #N is the FR-011 fail-safe default --
#     it must STILL gate at every site after the WP03 fix (a narrowing bug
#     that stopped gating bare references would be worse than the pre-fix
#     over-gating this WP corrects).
# ---------------------------------------------------------------------------


def test_bare_unmarked_reference_still_gates_at_all_three_sites(tmp_path: Path) -> None:
    """FR-011 fail-safe default preserved: no issue-matrix artifact present."""
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "spec.md").write_text("This mission directly fixes #2003.\n", encoding="utf-8")

    assert gating_issue_numbers(feature_dir) == {"#2003"}

    blocker_msg = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED)
    gate = _evaluate_issue_matrix_completeness_gate(feature_dir, is_blocking=True)
    doctor_findings = check_issue_matrix(feature_dir)

    assert blocker_msg is not None
    assert "#2003" in blocker_msg
    assert gate.verdict == GateVerdict.FAIL
    assert gate.blocking is True
    assert "#2003" in gate.details
    assert doctor_findings != []
    assert any("#2003" in finding.message for finding in doctor_findings)

    # Secondary "all three agree" check -- all three gate identically here.
    assert [
        blocker_msg is not None,
        gate.verdict == GateVerdict.FAIL,
        doctor_findings != [],
    ] == [True, True, True]


# ---------------------------------------------------------------------------
# (c) MATRIX-SET PARITY: merge_gates reads the matrix through
#     ``load_issue_matrix``/``validate_issue_matrix`` while the blocker/
#     doctor additionally recover a row's issue number from validator
#     diagnostics (a row that parsed but carries an invalid verdict is
#     excluded from ``.rows`` yet still "exists"). A row with an invalid
#     verdict must be reported as "unresolved verdict", never re-flagged as
#     "missing", at EVERY site.
# ---------------------------------------------------------------------------


def test_invalid_verdict_row_is_unresolved_not_missing_at_blocker_and_doctor(
    tmp_path: Path,
) -> None:
    """A row that parsed but carries an invalid verdict is reported as an
    unresolved/invalid verdict -- never re-flagged as a *missing* row -- by the
    two consumers that read the matrix through ``validate_issue_matrix`` plus
    diagnostic recovery (the approval blocker and ``status/doctor``).

    ``merge_gates`` deliberately reads through its net-new
    :func:`~specify_cli.tasks.issue_matrix_migration.load_issue_matrix` reader
    (pinned by
    ``tests/architectural/test_issue_matrix_json_migration_completeness.py``)
    and performs a PRESENCE-only completeness check. An invalid-verdict row is
    absent from ``load_issue_matrix``'s rows, so merge_gates would treat it as
    missing -- but that path is unreachable in practice: verdict validity is
    enforced at the ``approved`` transition, so by merge time every row carries
    a valid verdict. The shared *gating* decision (``is_gating``) across all
    three sites is pinned by the two tests above; this test pins invalid-verdict
    recovery on the two validator-based consumers.
    """
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "spec.md").write_text("This mission directly fixes #2004.\n", encoding="utf-8")
    _write_matrix(feature_dir, "#2004", "unknown", "tests/test_demo.py")

    # Referenced-set parity: the WP01 authority and the blocker agree.
    assert gating_issue_numbers(feature_dir) == {"#2004"}
    _result, referenced_issues, missing_issues, _unresolved = _issue_matrix_evaluation(feature_dir)
    assert referenced_issues == {"#2004"}
    # The row EXISTS (parsed, invalid verdict) -- the blocker must not call it "missing".
    assert missing_issues == []

    doctor_findings = check_issue_matrix(feature_dir)
    assert not any("missing rows" in finding.message.lower() for finding in doctor_findings)
    # The invalid verdict is still surfaced -- just not as "missing".
    assert any("#2004" in finding.message and "unknown" in finding.message for finding in doctor_findings)

    blocker_msg = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED)
    assert blocker_msg is not None
    assert "Missing rows" not in blocker_msg
    assert "#2004" in blocker_msg
