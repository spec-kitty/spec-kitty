"""Permanent guard for #3231 (FIXED) — a leftover finalize-tasks scaffold row
must not make the acceptance aggregate ``pending`` and block acceptance.

Fixed: https://github.com/Priivacy-ai/spec-kitty/issues/3231

Root cause and fix (``src/specify_cli/acceptance/matrix.py``):

* ``AcceptanceMatrix.overall_verdict`` used to let ``pending`` DOMINATE — one
  ``pending`` row outvoted any number of ``pass`` rows.
* The row-union reconciler ``reconcile_acceptance_matrix_documents``
  (``src/specify_cli/consolidation/drivers.py`` since #5119) admits BOTH sides' rows on
  an add/add divergence (``#3076`` FR-008), so after a mission→target squash
  merge the merged document legitimately contains the ``finalize-tasks``
  placeholder row (``AC-001``, ``pass_fail="pending"``, ``description`` AND
  ``notes`` both ``SCAFFOLD_TODO_MARKER``) alongside the real, all-``pass``
  criteria.
* The fix: ``overall_verdict`` now exempts a criterion from pending-dominates
  iff ``description == SCAFFOLD_TODO_MARKER`` (the discriminator unique to the
  empty placeholder — see ``_is_empty_scaffold``/C-003), and only when at
  least one non-scaffold criterion also exists. See
  ``tests/acceptance/test_overall_verdict_scaffold.py`` for the direct
  unit-level guard cases (partial authoring, all-scaffold, real ``AC-001``).

This drives the REAL production reconciler exactly as the issue measured it
(FILLED as *ours*, the scaffold PLACEHOLDER as *theirs*, empty base — the
add/add divergence) — pinning the fix at the integration seam where #3231 was
originally observed, not just at the ``overall_verdict`` unit level.
"""

from __future__ import annotations

import pytest

from specify_cli.acceptance.matrix import SCAFFOLD_TODO_MARKER
from specify_cli.consolidation.drivers import reconcile_acceptance_matrix_documents

pytestmark = pytest.mark.unit


def _pass_criterion(criterion_id: str) -> dict[str, object]:
    return {
        "criterion_id": criterion_id,
        "description": f"Verify {criterion_id} is satisfied",
        "proof_type": "automated_test",
        "pass_fail": "pass",
        "evidence": f"tests/test_{criterion_id.lower()}.py::test_it",
    }


def _scaffold_placeholder_row() -> dict[str, object]:
    # Exactly what `finalize-tasks` writes for an un-authored matrix
    # (src/specify_cli/acceptance/matrix.py scaffold builder).
    return {
        "criterion_id": "AC-001",
        "description": SCAFFOLD_TODO_MARKER,
        "proof_type": "automated_test",
        "pass_fail": "pending",
        "notes": SCAFFOLD_TODO_MARKER,
    }


def test_scaffold_pending_row_does_not_poison_acceptance_verdict() -> None:
    ours_filled = {
        "mission_slug": "example-mission",
        "criteria": [_pass_criterion("FR-001"), _pass_criterion("FR-003")],
    }
    theirs_scaffold = {
        "mission_slug": "example-mission",
        "criteria": [_scaffold_placeholder_row()],
    }
    # Empty base == the add/add divergence the row-union authority model faces.
    merged = reconcile_acceptance_matrix_documents({}, ours_filled, theirs_scaffold)

    real_criteria = [c for c in merged["criteria"] if c["criterion_id"] != "AC-001"]
    assert real_criteria, "sanity: the real, filled criteria survived the merge"
    assert all(c["pass_fail"] == "pass" for c in real_criteria), (
        "sanity: every real criterion is 'pass'; only the scaffold placeholder is 'pending'"
    )

    # Guard: a single admitted scaffold placeholder must not make the
    # aggregate 'pending' and block acceptance despite every real criterion
    # passing (defect #3231, fixed in AcceptanceMatrix.overall_verdict).
    assert merged["overall_verdict"] != "pending", (
        "a leftover finalize-tasks scaffold placeholder row must not poison the "
        f"acceptance aggregate; got overall_verdict={merged['overall_verdict']!r} "
        f"with rows={[(c['criterion_id'], c['pass_fail']) for c in merged['criteria']]}"
    )
