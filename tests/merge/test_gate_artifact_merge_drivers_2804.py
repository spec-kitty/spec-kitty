"""#2804 driver-level unit gate -- row-union authority model (#3076).

Deleted by ``b04da00e1`` when the acceptance/issue-matrix merge drivers moved
from a whole-file "more-filled-side" heuristic to the row-aware, base-aware
(3-way) reconciler in ``merge_driver.py`` (FR-008). This module restores the
gate as an in-memory unit overlay, calling
:func:`reconcile_acceptance_matrix_documents` /
:func:`reconcile_issue_matrix_documents` directly -- no git repo, no
``spec-kitty merge-driver-*`` subprocess, no ``pip install -e .``.

**Sibling cross-reference (C-003):**
``tests/specify_cli/cli/commands/test_row_aware_merge_driver.py`` owns the
GENERAL row-union contract (disjoint-row union, stale-residue drop, same-field
conflict markers, intra-side duplicate-key guards, byte-determinism; 37
tests) -- it has zero coverage of the scaffold-marker / accepted-evidence
framing below. This module is the narrow #2804 overlay: it pins the specific
invariant that a coordination gate artifact's already-*filled* criterion (a
real accepted-evidence handle, marker-free prose) is never silently reset
back to :data:`SCAFFOLD_TODO_MARKER` placeholder content by a mission->target
squash merge, and that when a NON-verdict field genuinely diverges on both
sides the filled target survives (target-authoritative tie: no conflict
marker embedded, no silent reset — #4880 removed the in-band marker embed;
a genuinely-diverged VERDICT field instead fails closed in the sibling's
coverage). It is NOT a duplicate of the sibling's general coverage.

Integration-level regression: ``tests/merge/
test_issue_2804_merge_resets_gate_artifacts.py`` (untouched by this module,
C-001) exercises the same invariant through a real git merge; this module is
the fast (< 5s), driver-unit companion.

C-002 / #3231: the acceptance-matrix reconciler recomputes ``overall_verdict``
via ``AcceptanceMatrix.from_dict(...).to_dict()`` and legitimately admits
``pending`` (and ``pass_pending_consolidation``) as non-failing outcomes. No
assertion below demands ``pass`` on an admitted-scaffold-row input -- doing so
would silently encode the out-of-scope #3231 product fix into this gate.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from specify_cli.acceptance.matrix import SCAFFOLD_TODO_MARKER, VERDICT_PASS_PENDING_CONSOLIDATION
from specify_cli.cli.commands.merge_driver import (
    reconcile_acceptance_matrix_documents,
    reconcile_issue_matrix_documents,
)

pytestmark = [pytest.mark.unit]

# Cross-references the accepted-evidence handle used by the integration
# marker (tests/merge/test_issue_2804_merge_resets_gate_artifacts.py) so a
# reader can tell the two modules are pinning the same real-world artifact
# shape, not two unrelated inventions.
ACCEPTED_EVIDENCE_HANDLE = "d5b8324f9"

# The acceptance-matrix reconciler recomputes ``overall_verdict``; this is the
# domain of non-failing outcomes a correctly-merged, evidence-bearing document
# may legitimately land on (C-002 / #3231: ``pending`` MUST stay admissible).
ADMISSIBLE_MERGED_VERDICTS = frozenset({"pass", "pending", VERDICT_PASS_PENDING_CONSOLIDATION})


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _filled_criterion(criterion_id: str = "AC-001", pass_fail: str = "pass") -> dict[str, Any]:
    """A real, filled acceptance criterion: accepted evidence handle, no
    scaffold marker in any field."""
    return {
        "criterion_id": criterion_id,
        "description": f"{criterion_id} verified end to end",
        "proof_type": "automated_test",
        "pass_fail": pass_fail,
        "evidence": ACCEPTED_EVIDENCE_HANDLE,
        "notes": "real note",
    }


def _scaffold_criterion(criterion_id: str = "AC-001", evidence: str | None = None) -> dict[str, Any]:
    """A placeholder criterion as ``finalize-tasks`` scaffolds it: the
    marker in BOTH ``description`` and ``notes`` (matrix.py:531,534)."""
    return {
        "criterion_id": criterion_id,
        "description": SCAFFOLD_TODO_MARKER,
        "proof_type": "automated_test",
        "pass_fail": "pending",
        "evidence": evidence,
        "notes": SCAFFOLD_TODO_MARKER,
    }


FILLED_ACCEPTANCE_DOC = {"criteria": [_filled_criterion()]}
PLACEHOLDER_ACCEPTANCE_DOC = {"criteria": [_scaffold_criterion()]}

FILLED_ISSUE_DOC = {"rows": {"#3232": {"verdict": "verified", "evidence_ref": ACCEPTED_EVIDENCE_HANDLE}}}
PLACEHOLDER_ISSUE_DOC = {"rows": {"#3232": {"verdict": "unknown"}}}


# ---------------------------------------------------------------------------
# T001 -- fixture self-control (A6): no fixture makes a survival assertion
# vacuous -- the handle really is present on the filled side and really is
# absent from the placeholder side.
# ---------------------------------------------------------------------------


def test_fixtures_are_not_vacuous() -> None:
    assert ACCEPTED_EVIDENCE_HANDLE in json.dumps(FILLED_ACCEPTANCE_DOC)
    assert ACCEPTED_EVIDENCE_HANDLE not in json.dumps(PLACEHOLDER_ACCEPTANCE_DOC)
    assert ACCEPTED_EVIDENCE_HANDLE in json.dumps(FILLED_ISSUE_DOC)
    assert ACCEPTED_EVIDENCE_HANDLE not in json.dumps(PLACEHOLDER_ISSUE_DOC)


# ---------------------------------------------------------------------------
# T002 -- A1 + A2: clean-merge survival (FR-002)
# ---------------------------------------------------------------------------


def test_a1_filled_ours_survives_scaffold_theirs_equal_base() -> None:
    """The mission branch (``theirs``) still carries the scaffold (== base);
    the target (``ours``) already has the accepted fill. The merge must keep
    the fill, not reset it back to the placeholder."""
    base = PLACEHOLDER_ACCEPTANCE_DOC
    ours = FILLED_ACCEPTANCE_DOC
    theirs = base

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    merged_criterion = merged["criteria"][0]
    assert merged_criterion["criterion_id"] == "AC-001"
    assert ACCEPTED_EVIDENCE_HANDLE in json.dumps(merged)
    assert SCAFFOLD_TODO_MARKER not in json.dumps(merged_criterion)
    assert merged["overall_verdict"] == "pass"


def test_a1_control_scaffold_only_yields_no_handle() -> None:
    """Fabrication-axis non-vacuity control for A1: when the fill is authored
    on NEITHER side (scaffold stands in for both ours and theirs), the accepted
    evidence handle cannot appear in the merged document -- proving A1's
    handle-survival assertion is not satisfied by the handle materialising from
    nowhere. (The side-selection falsifiability -- "take-theirs would lose the
    fill" -- is covered by the main A1 test, which fails if the reconciler's
    ``theirs == base -> ours`` branch is inverted.)"""
    base = PLACEHOLDER_ACCEPTANCE_DOC
    theirs = base

    # The fill (FILLED_ACCEPTANCE_DOC from test_a1) never reaches the reconciler:
    # scaffold on both ours and theirs, so the merged doc can contain the handle
    # only if it were fabricated -- it is not.
    regressed = reconcile_acceptance_matrix_documents(base, theirs, theirs)

    regressed_criterion = regressed["criteria"][0]
    assert ACCEPTED_EVIDENCE_HANDLE not in json.dumps(regressed)
    assert SCAFFOLD_TODO_MARKER in json.dumps(regressed_criterion)


def test_a2_filled_theirs_survives_scaffold_ours_equal_base() -> None:
    """Symmetric to A1: the fill was authored on ``theirs`` (the mission
    branch), ``ours`` (the target) still has the scaffold == base."""
    base = PLACEHOLDER_ACCEPTANCE_DOC
    ours = base
    theirs = FILLED_ACCEPTANCE_DOC

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    merged_criterion = merged["criteria"][0]
    assert ACCEPTED_EVIDENCE_HANDLE in json.dumps(merged)
    assert SCAFFOLD_TODO_MARKER not in json.dumps(merged_criterion)
    assert merged["overall_verdict"] == "pass"


# ---------------------------------------------------------------------------
# T003 -- A3: prose divergence with equal pass_fail raises fail-closed (FR-003)
# ---------------------------------------------------------------------------


def test_a3_prose_divergence_with_equal_pass_fail_prefers_target_no_abort() -> None:
    """``pass_fail`` is equal on both sides (both ``pending``); only PROSE
    (``description``/``evidence``/``notes``) diverges — the target (``ours``,
    filled) carries real content, the incoming lane carries a scaffold
    placeholder. #4880 fails closed only on a genuinely-diverged VERDICT-
    authority field; a NON-verdict field never aborts and never embeds a
    conflict marker — it prefers the target side (#2804 / #1732 target-
    authoritative tie convention, so a filled row survives a scaffold on the
    other side). The merge therefore resolves cleanly, keeping ``ours``' prose,
    and no marker string is embedded."""
    base: dict[str, Any] = {}
    ours = {
        "criteria": [
            {
                "criterion_id": "AC-001",
                "description": "real description",
                "proof_type": "automated_test",
                "pass_fail": "pending",
                "evidence": ACCEPTED_EVIDENCE_HANDLE,
                "notes": "real notes",
            }
        ]
    }
    theirs = {
        "criteria": [
            {
                "criterion_id": "AC-001",
                "description": SCAFFOLD_TODO_MARKER,
                "proof_type": "automated_test",
                "pass_fail": "pending",
                "evidence": "TODO: evidence",
                "notes": SCAFFOLD_TODO_MARKER,
            }
        ]
    }

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    (criterion,) = merged["criteria"]
    assert criterion["evidence"] == ACCEPTED_EVIDENCE_HANDLE  # target's filled prose survives
    assert criterion["description"] == "real description"
    assert criterion["notes"] == "real notes"
    assert "<<<<<<<" not in json.dumps(merged)  # no conflict marker embedded
    assert merged["overall_verdict"] != "fail"  # pass_fail unchanged (pending), no silent flip


def test_a3_control_scaffold_only_drops_the_handle() -> None:
    """Fabrication-axis non-vacuity control for A3: when the accepted evidence
    on ``ours`` never reaches the reconciler (scaffold stands in for both sides),
    the handle cannot appear in the merged document -- so A3's in-conflict
    handle-survival assertion is not satisfied by fabrication. (The side-selection
    falsifiability is covered by the main A3 test, which fails if the conflict
    filled target is inverted to a theirs-only pick.)"""
    base: dict[str, Any] = {}
    theirs = {
        "criteria": [
            {
                "criterion_id": "AC-001",
                "description": SCAFFOLD_TODO_MARKER,
                "proof_type": "automated_test",
                "pass_fail": "pending",
                "evidence": "TODO: evidence",
                "notes": SCAFFOLD_TODO_MARKER,
            }
        ]
    }

    regressed = reconcile_acceptance_matrix_documents(base, theirs, theirs)

    assert ACCEPTED_EVIDENCE_HANDLE not in json.dumps(regressed)


# ---------------------------------------------------------------------------
# T004 -- A4: admissible-verdict domain, disjoint add/add (FR-004)
# ---------------------------------------------------------------------------


def test_a4_disjoint_add_add_admits_pass_alongside_scaffold_row() -> None:
    """Genuine disjoint union: ``ours`` adds a filled AC-001 (pass), ``theirs``
    independently adds an empty scaffold AC-002. Both rows survive and the
    recomputed verdict lands on the admissible ``pass`` -- NOT ``fail`` and NOT
    silently reset -- which is the merge-driver invariant this A4/FR-004 case
    pins.

    The concrete value is ``pass`` (not ``pending``) since #3231 landed on
    2026-08-13: ``overall_verdict`` now exempts an empty scaffold placeholder
    (``description == SCAFFOLD_TODO_MARKER``) from the pending-dominates rule
    once at least one real criterion exists. AC-002 is exactly that contentless
    placeholder and AC-001 is a real pass, so the leftover scaffold no longer
    blocks acceptance. Before #3231 this asserted ``pending`` on the stated
    assumption that #3231 was out of scope; that assumption is now false."""
    base: dict[str, Any] = {}
    ours = {"criteria": [_filled_criterion(criterion_id="AC-001", pass_fail="pass")]}
    theirs = {"criteria": [_scaffold_criterion(criterion_id="AC-002")]}

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    criterion_ids = {c["criterion_id"] for c in merged["criteria"]}
    assert criterion_ids == {"AC-001", "AC-002"}
    assert ACCEPTED_EVIDENCE_HANDLE in json.dumps(merged)
    assert merged["overall_verdict"] == "pass"
    assert merged["overall_verdict"] in ADMISSIBLE_MERGED_VERDICTS
    assert merged["overall_verdict"] != "fail"


def test_a4_control_invalid_pass_fail_still_fails() -> None:
    """Non-vacuity control: the admissible-domain assertion above genuinely
    bites -- an out-of-domain ``pass_fail`` value recomputes to ``fail``, so
    this gate is not vacuously green for any verdict string."""
    base: dict[str, Any] = {}
    ours = {"criteria": [_filled_criterion(criterion_id="AC-001", pass_fail="pass")]}
    theirs = {
        "criteria": [
            {
                "criterion_id": "AC-002",
                "description": "invalid row",
                "proof_type": "automated_test",
                "pass_fail": "definitely-not-valid",
                "evidence": None,
                "notes": None,
            }
        ]
    }

    merged = reconcile_acceptance_matrix_documents(base, ours, theirs)

    assert merged["overall_verdict"] == "fail"


# ---------------------------------------------------------------------------
# T005 -- A5: issue-matrix terminal survival (FR-005)
# ---------------------------------------------------------------------------


def test_a5_issue_matrix_terminal_verdict_and_evidence_ref_survive() -> None:
    """The issue-matrix reconciler does NO verdict recomputation (there is no
    ``AcceptanceMatrix`` layer) -- survival here is pure per-field 3-way
    union: ``_merge_field`` returns the changed side when the OTHER side ==
    base. ``ours`` still == base (``unknown``); ``theirs`` carries the
    terminal ``verified`` verdict plus the accepted evidence_ref."""
    base = PLACEHOLDER_ISSUE_DOC
    ours = base
    theirs = FILLED_ISSUE_DOC

    merged = reconcile_issue_matrix_documents(base, ours, theirs)

    merged_row = merged["rows"]["#3232"]
    assert merged_row["verdict"] != "unknown"
    assert merged_row["evidence_ref"] == ACCEPTED_EVIDENCE_HANDLE


def test_a5_control_take_theirs_equal_base_drops_terminal_verdict() -> None:
    """Control: if both sides are the placeholder (the terminal fill on
    ``theirs`` never reaches the reconciler), the row stays ``unknown`` with
    no ``evidence_ref`` -- the merge did not fabricate survival."""
    base = PLACEHOLDER_ISSUE_DOC

    regressed = reconcile_issue_matrix_documents(base, base, base)

    regressed_row = regressed["rows"]["#3232"]
    assert regressed_row["verdict"] == "unknown"
    assert "evidence_ref" not in regressed_row
