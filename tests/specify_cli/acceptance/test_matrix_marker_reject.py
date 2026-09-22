"""FR-004 (acceptance-matrix-merge-fail-closed-01M34HG8, WP02 / T005-T006).

Defense-in-depth read guard: ``AcceptanceMatrix.from_dict`` must reject a
string field that carries a raw, unresolved git conflict marker
(``<<<<<<<`` / ``=======`` / ``>>>>>>>``) instead of silently round-tripping
it. Before this guard, a marker landing in ``pass_fail``/``result`` merely
happened to coerce ``overall_verdict`` to a false ``fail`` via the existing
out-of-domain-value branch; a marker in a prose-only field (e.g. ``notes``)
left no signal at all that the file was merge-damaged. WP01 (a parallel
lane, ``merge_driver.py``) closes the write side of the same defect; this
WP closes the read side.
"""

from __future__ import annotations

import pytest

from specify_cli.acceptance.matrix import (
    AcceptanceMatrix,
    AcceptanceMatrixParseError,
)


def _base_criterion(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "criterion_id": "AC-001",
        "description": "Verify FR-001 is satisfied",
        "proof_type": "automated_test",
        "pass_fail": "pending",
    }
    data.update(overrides)
    return data


class TestConflictMarkerRejection:
    def test_marker_in_pass_fail_raises_naming_the_field(self) -> None:
        data = {
            "mission_slug": "marker-mission",
            "criteria": [_base_criterion(pass_fail="<<<<<<< HEAD")],
            "negative_invariants": [],
        }
        with pytest.raises(AcceptanceMatrixParseError) as exc_info:
            AcceptanceMatrix.from_dict(data)
        err = exc_info.value
        assert err.section == "criteria"
        assert err.item_index == 0
        assert "pass_fail" in err.reason
        assert "AC-001" in err.reason

    def test_marker_in_prose_field_also_raises(self) -> None:
        """A marker in a field that does NOT feed ``overall_verdict`` (e.g.
        ``notes``) must still be caught — that is exactly the silent-gap
        case a value-blind ``from_dict`` misses today."""
        data = {
            "mission_slug": "marker-mission",
            "criteria": [_base_criterion(notes="=======\nconflicting notes from both branches")],
            "negative_invariants": [],
        }
        with pytest.raises(AcceptanceMatrixParseError) as exc_info:
            AcceptanceMatrix.from_dict(data)
        err = exc_info.value
        assert err.section == "criteria"
        assert "notes" in err.reason

    def test_marker_in_negative_invariant_field_raises(self) -> None:
        data = {
            "mission_slug": "marker-mission",
            "criteria": [],
            "negative_invariants": [
                {
                    "invariant_id": "NI-001",
                    "description": "no debug prints",
                    "verification_method": "grep_absence",
                    "evidence": ">>>>>>> feature-branch",
                }
            ],
        }
        with pytest.raises(AcceptanceMatrixParseError) as exc_info:
            AcceptanceMatrix.from_dict(data)
        err = exc_info.value
        assert err.section == "negative_invariants"
        assert err.item_index == 0
        assert "evidence" in err.reason
        assert "NI-001" in err.reason

    def test_clean_matrix_parses_fine(self) -> None:
        data = {
            "mission_slug": "clean-mission",
            "criteria": [_base_criterion(pass_fail="pass")],
            "negative_invariants": [
                {
                    "invariant_id": "NI-001",
                    "description": "no debug prints",
                    "verification_method": "grep_absence",
                    "result": "confirmed_absent",
                }
            ],
        }
        matrix = AcceptanceMatrix.from_dict(data)
        assert matrix.mission_slug == "clean-mission"
        assert matrix.criteria[0].pass_fail == "pass"
        assert matrix.negative_invariants[0].result == "confirmed_absent"

    def test_authored_out_of_domain_pass_fail_still_yields_fail_verdict(self) -> None:
        """C-001: an authored, merely out-of-domain token (not a conflict
        marker) must NOT be rejected by this guard — it still flows through
        unchanged and ``overall_verdict`` recomputes to ``fail`` exactly as
        before (no over-rejection)."""
        data = {
            "mission_slug": "out-of-domain-mission",
            "criteria": [_base_criterion(pass_fail="maybe")],
            "negative_invariants": [],
        }
        matrix = AcceptanceMatrix.from_dict(data)
        assert matrix.criteria[0].pass_fail == "maybe"
        assert matrix.overall_verdict == "fail"
