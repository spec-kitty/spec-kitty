"""Tests for acceptance matrix, evidence validation, and negative invariants."""

import json
import sys

import pytest

from specify_cli.acceptance import matrix as acceptance_matrix_module
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    MATRIX_FILENAME,
    NegativeInvariant,
    enforce_negative_invariants,
    read_acceptance_matrix,
    validate_manual_evidence,
    validate_matrix_evidence,
    write_acceptance_matrix,
)

pytestmark = pytest.mark.fast


def test_legacy_module_reexports_matrix_filename():
    assert MATRIX_FILENAME == "acceptance-matrix.json"


class TestAcceptanceCriterion:
    def test_default_pending(self):
        c = AcceptanceCriterion(criterion_id="AC-01", description="Test", proof_type="automated_test")
        assert c.pass_fail == "pending"


class TestAcceptanceMatrix:
    def test_verdict_all_pass(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail="pass"),
            ],
        )
        assert m.overall_verdict == "pass"

    def test_verdict_any_fail(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail="pass"),
                AcceptanceCriterion("AC-02", "Test", "manual_qa", pass_fail="fail"),
            ],
        )
        assert m.overall_verdict == "fail"

    def test_verdict_pending(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail="pass"),
                AcceptanceCriterion("AC-02", "Test", "manual_qa", pass_fail="pending"),
            ],
        )
        assert m.overall_verdict == "pending"

    def test_verdict_invariant_still_present(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail="pass"),
            ],
            negative_invariants=[
                NegativeInvariant("NI-01", "Old route gone", "grep_absence", result="still_present"),
            ],
        )
        assert m.overall_verdict == "fail"

    def test_verdict_invariant_verification_error_fails_closed(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail="pass"),
            ],
            negative_invariants=[
                NegativeInvariant("NI-01", "Old route gone", "grep_absence", result="verification_error"),
            ],
        )
        assert m.overall_verdict == "fail"

    def test_empty_matrix_pending(self):
        m = AcceptanceMatrix(mission_slug="test")
        assert m.overall_verdict == "pending"

    @pytest.mark.parametrize("pass_fail", ["failed", "FAIL", "Pending", None, ["fail"]])
    def test_verdict_invalid_criterion_result_fails_closed(self, pass_fail):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Test", "automated_test", pass_fail=pass_fail),
            ],
        )

        assert m.overall_verdict == "fail"

    @pytest.mark.parametrize("result", ["absent", "STILL_PRESENT", "Pending", None, ["still_present"]])
    def test_verdict_invalid_negative_invariant_result_fails_closed(self, result):
        m = AcceptanceMatrix(
            mission_slug="test",
            negative_invariants=[
                NegativeInvariant("NI-01", "Old route gone", "grep_absence", result=result),
            ],
        )

        assert m.overall_verdict == "fail"


class TestPersistence:
    def test_round_trip(self, tmp_path):
        matrix = AcceptanceMatrix(
            mission_slug="010-feat",
            criteria=[
                AcceptanceCriterion("AC-01", "Test passes", "automated_test", pass_fail="pass"),
            ],
            negative_invariants=[
                NegativeInvariant("NI-01", "No legacy route", "grep_absence",
                                  verification_command="/old-route", result="confirmed_absent"),
            ],
        )
        write_acceptance_matrix(tmp_path, matrix)
        restored = read_acceptance_matrix(tmp_path)
        assert restored is not None
        assert restored.mission_slug == "010-feat"
        assert [c.criterion_id for c in restored.criteria] == ["AC-01"]
        assert [n.invariant_id for n in restored.negative_invariants] == ["NI-01"]
        assert restored.overall_verdict == "pass"

    def test_missing_returns_none(self, tmp_path):
        assert read_acceptance_matrix(tmp_path) is None

    def test_preserves_extension_fields_on_round_trip(self, tmp_path):
        matrix_data = {
            "mission_slug": "010-feat",
            "narrowed_acceptance_counter": 23,
            "substitutions": [
                {
                    "criterion_id": "AC-01",
                    "substitute_evidence": "vitest contract coverage",
                },
            ],
            "criteria": [
                {
                    "criterion_id": "AC-01",
                    "description": "Test passes",
                    "proof_type": "automated_test",
                    "pass_fail": "pass",
                    "scope_note": "Narrowed acceptance rationale",
                    "deferred_findings_ref": "docs/backlog/follow-ups.md",
                },
            ],
            "negative_invariants": [
                {
                    "invariant_id": "NI-01",
                    "description": "No legacy route",
                    "verification_method": "grep_absence",
                    "verification_command": "/old-route",
                    "result": "confirmed_absent",
                    "verification_pattern": "operator-authored extension",
                },
            ],
        }
        (tmp_path / MATRIX_FILENAME).write_text(json.dumps(matrix_data), encoding="utf-8")

        matrix = read_acceptance_matrix(tmp_path)
        assert matrix is not None
        write_acceptance_matrix(tmp_path, matrix)

        restored = json.loads((tmp_path / MATRIX_FILENAME).read_text(encoding="utf-8"))
        assert restored["narrowed_acceptance_counter"] == 23
        assert restored["substitutions"] == matrix_data["substitutions"]
        assert restored["criteria"][0]["scope_note"] == "Narrowed acceptance rationale"
        assert restored["criteria"][0]["deferred_findings_ref"] == "docs/backlog/follow-ups.md"
        assert restored["negative_invariants"][0]["verification_pattern"] == "operator-authored extension"

    def test_round_trip_without_extensions_does_not_emit_extras_key(self, tmp_path):
        matrix = AcceptanceMatrix(
            mission_slug="010-feat",
            criteria=[
                AcceptanceCriterion("AC-01", "Test passes", "automated_test", pass_fail="pass"),
            ],
            negative_invariants=[
                NegativeInvariant("NI-01", "No legacy route", "grep_absence", result="confirmed_absent"),
            ],
        )

        write_acceptance_matrix(tmp_path, matrix)
        first_write = (tmp_path / MATRIX_FILENAME).read_text(encoding="utf-8")
        restored = read_acceptance_matrix(tmp_path)
        assert restored is not None
        write_acceptance_matrix(tmp_path, restored)

        assert (tmp_path / MATRIX_FILENAME).read_text(encoding="utf-8") == first_write
        data = json.loads((tmp_path / MATRIX_FILENAME).read_text(encoding="utf-8"))
        assert "extras" not in data
        assert "extras" not in data["criteria"][0]
        assert "extras" not in data["negative_invariants"][0]


class TestManualEvidence:
    def test_valid_manual_qa(self):
        c = AcceptanceCriterion(
            "AC-01", "Check dashboard", "manual_qa",
            evidence="http://localhost:8000/dashboard",
            verified_at="2026-04-03T12:00:00Z",
            verified_by="qa-operator",
            pass_fail="pass",
        )
        assert validate_manual_evidence(c) == []

    def test_missing_evidence(self):
        c = AcceptanceCriterion("AC-01", "Check dashboard", "manual_qa")
        errors = validate_manual_evidence(c)
        assert len(errors) == 3
        assert any("evidence" in e for e in errors)
        assert any("verified_at" in e for e in errors)
        assert any("verified_by" in e for e in errors)

    def test_non_manual_qa_ignored(self):
        c = AcceptanceCriterion("AC-01", "Test", "automated_test")
        assert validate_manual_evidence(c) == []

    def test_matrix_level_validation(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Auto", "automated_test"),
                AcceptanceCriterion("AC-02", "Manual", "manual_qa"),  # Missing evidence
            ],
        )
        errors = validate_matrix_evidence(m)
        assert len(errors) == 3  # evidence, verified_at, verified_by

    def test_matrix_level_validation_rejects_invalid_verdict_values(self):
        m = AcceptanceMatrix(
            mission_slug="test",
            criteria=[
                AcceptanceCriterion("AC-01", "Auto", "automated_test", pass_fail="failed"),
            ],
            negative_invariants=[
                NegativeInvariant("NI-01", "Legacy route gone", "grep_absence", result="absent"),
            ],
        )

        errors = validate_matrix_evidence(m)

        assert "AC-01: pass_fail must be one of deferred, fail, pass, pending; got 'failed'" in errors
        assert (
            "NI-01: result must be one of confirmed_absent, deferred_to_consolidation, "
            "pending, still_present, verification_error; got 'absent'"
        ) in errors


class TestNegativeInvariants:
    def test_grep_absence_confirmed(self, tmp_path):
        # Create a repo dir with a file that does NOT contain the pattern
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

        invariants = [
            NegativeInvariant(
                "NI-01", "No legacy route",
                "grep_absence",
                verification_command="old_legacy_route",
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)
        assert results[0].result == "confirmed_absent"

    def test_grep_absence_invalid_regex_is_not_confirmed_absent(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("forbidden_thing()\n")

        invariants = [
            NegativeInvariant(
                "NI-01", "No forbidden call",
                "grep_absence",
                verification_command="forbidden[",
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)

        assert results[0].result == "verification_error"
        assert "grep verification failed (exit 2)" in (results[0].evidence or "")

    def test_grep_absence_execution_failure_is_not_confirmed_absent(self, tmp_path, monkeypatch):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

        def fail_to_start(*_args, **_kwargs):
            raise OSError("grep unavailable")

        monkeypatch.setattr(acceptance_matrix_module.subprocess, "run", fail_to_start)

        invariants = [
            NegativeInvariant(
                "NI-01", "No legacy route",
                "grep_absence",
                verification_command="old_legacy_route",
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)

        assert results[0].result == "verification_error"
        assert "grep failed to start: grep unavailable" in (results[0].evidence or "")

    def test_grep_absence_still_present(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("old_legacy_route = '/old'\n")

        invariants = [
            NegativeInvariant(
                "NI-01", "No legacy route",
                "grep_absence",
                verification_command="old_legacy_route",
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)
        assert results[0].result == "still_present"

    def test_grep_absence_ignores_matrix_file(self, tmp_path):
        """grep_absence should not match its own acceptance-matrix definition."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)
        pattern = "old_legacy_route"
        (feature_dir / MATRIX_FILENAME).write_text(
            "{\n"
            '  "mission_slug": "test-mission",\n'
            '  "negative_invariants": [\n'
            f'    {{"verification_method": "grep_absence", "verification_command": "{pattern}"}}\n'
            "  ]\n"
            "}\n",
            encoding="utf-8",
        )

        results = enforce_negative_invariants(
            tmp_path,
            [
                NegativeInvariant(
                    "NI-01",
                    "No legacy route",
                    "grep_absence",
                    verification_command=pattern,
                ),
            ],
        )

        assert results[0].result == "confirmed_absent"

    def test_grep_absence_scope_excludes_prose_false_positive(self, tmp_path):
        """#1834(c): a pattern present ONLY in a mission's own prose (docs/spec)
        must NOT false-positive as still_present when the invariant is scoped to
        a code dir. Whole-repo would find the prose mention; the scope excludes
        it -> confirmed_absent.
        """
        pattern = "old_legacy_route"
        # Prose path that mentions the pattern (the mission's own WP/spec text).
        (tmp_path / "kitty-specs" / "m").mkdir(parents=True)
        (tmp_path / "kitty-specs" / "m" / "spec.md").write_text(
            f"We removed the {pattern} surface entirely.\n", encoding="utf-8"
        )
        # Code dir that is genuinely clean of the pattern.
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def main(): pass\n")

        scoped = NegativeInvariant(
            "NI-01", "No legacy route in code",
            "grep_absence",
            verification_command=pattern,
            scope="src",
        )
        assert enforce_negative_invariants(tmp_path, [scoped])[0].result == (
            "confirmed_absent"
        )

        # Sanity: the SAME invariant without a scope finds the prose mention and
        # (wrongly, for the mission's purpose) reports still_present — proving the
        # scope is what excludes the false positive.
        unscoped = NegativeInvariant(
            "NI-02", "No legacy route anywhere",
            "grep_absence",
            verification_command=pattern,
        )
        assert enforce_negative_invariants(tmp_path, [unscoped])[0].result == (
            "still_present"
        )

    def test_grep_absence_scope_still_catches_offender_in_scope(self, tmp_path):
        """A scoped invariant still reports still_present when the pattern IS
        present inside the scoped code path — scoping narrows, it does not
        blind the check."""
        pattern = "old_legacy_route"
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text(f"{pattern} = '/old'\n")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.md").write_text("nothing here\n")

        scoped = NegativeInvariant(
            "NI-01", "No legacy route in code",
            "grep_absence",
            verification_command=pattern,
            scope="src",
        )
        result = enforce_negative_invariants(tmp_path, [scoped])[0]
        assert result.result == "still_present"
        # Scope survives enforcement (round-trips on re-serialization).
        assert result.scope == "src"

    def test_custom_command_pass(self, tmp_path):
        invariants = [
            NegativeInvariant(
                "NI-01", "No stale files",
                "custom_command",
                verification_command=f'"{sys.executable}" -c "import sys; sys.exit(0)"',
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)
        assert results[0].result == "confirmed_absent"

    def test_custom_command_preserves_posix_command_substitution(self, tmp_path):
        invariants = [
            NegativeInvariant(
                "NI-01", "No stale files",
                "custom_command",
                verification_command='test -z "$(printf \'\')"',
            ),
        ]

        results = enforce_negative_invariants(tmp_path, invariants)

        assert results[0].result == "confirmed_absent"

    def test_custom_command_fail(self, tmp_path):
        invariants = [
            NegativeInvariant(
                "NI-01", "Check fails",
                "custom_command",
                verification_command=f'"{sys.executable}" -c "import sys; sys.exit(1)"',
            ),
        ]
        results = enforce_negative_invariants(tmp_path, invariants)
        assert results[0].result == "still_present"

    def test_custom_command_missing_executable_returns_evidence(self, tmp_path):
        invariants = [
            NegativeInvariant(
                "NI-01", "Check fails",
                "custom_command",
                verification_command="definitely-not-a-spec-kitty-command",
            ),
        ]

        results = enforce_negative_invariants(tmp_path, invariants)

        assert results[0].result == "still_present"
        assert "not found" in (results[0].evidence or "")

    @pytest.mark.windows_ci
    def test_custom_command_posix_shell_syntax_fails_clear_on_windows(self, tmp_path):
        invariants = [
            NegativeInvariant(
                "NI-01", "No stale files",
                "custom_command",
                verification_command='python -c "print(1)" && echo done',
            ),
        ]

        results = enforce_negative_invariants(tmp_path, invariants)

        assert results[0].result == "pending"
        assert "POSIX shell syntax" in (results[0].evidence or "")

    def test_enforcement_preserves_negative_invariant_extensions(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "src").mkdir()
        (repo_root / "src" / "app.py").write_text("def main(): pass\n")

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)
        matrix_data = {
            "mission_slug": "010-feat",
            "criteria": [],
            "negative_invariants": [
                {
                    "invariant_id": "NI-01",
                    "description": "No legacy route",
                    "verification_method": "grep_absence",
                    "verification_command": "old_legacy_route",
                    "result": "pending",
                    "verification_pattern": "operator-authored extension",
                },
            ],
        }
        (feature_dir / MATRIX_FILENAME).write_text(json.dumps(matrix_data), encoding="utf-8")

        matrix = read_acceptance_matrix(feature_dir)
        assert matrix is not None
        matrix.negative_invariants = enforce_negative_invariants(
            repo_root,
            matrix.negative_invariants,
        )
        write_acceptance_matrix(feature_dir, matrix)

        restored = json.loads((feature_dir / MATRIX_FILENAME).read_text(encoding="utf-8"))
        assert restored["negative_invariants"][0]["result"] == "confirmed_absent"
        assert restored["negative_invariants"][0]["verification_pattern"] == "operator-authored extension"


class TestScaffoldAcceptanceMatrix:
    """Finding 6: ``scaffold_acceptance_matrix`` writes a schema-valid file."""

    def test_scaffold_empty_but_valid_when_no_requirements(self, tmp_path):
        from specify_cli.acceptance.matrix import (
            SCAFFOLD_TODO_MARKER,
            scaffold_acceptance_matrix,
        )

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)

        out_path = scaffold_acceptance_matrix(feature_dir, "010-feat", requirement_ids=[])

        assert out_path == feature_dir / MATRIX_FILENAME
        assert out_path.exists()

        # Schema-valid: round-trips through read_acceptance_matrix.
        matrix = read_acceptance_matrix(feature_dir)
        assert matrix is not None
        assert matrix.mission_slug == "010-feat"
        # Empty-but-valid scaffold has a clear TODO marker.
        assert [c.criterion_id for c in matrix.criteria] == ["AC-001"]
        assert SCAFFOLD_TODO_MARKER in (matrix.criteria[0].notes or "")
        # Verdict stays pending until evidence is supplied.
        assert matrix.overall_verdict == "pending"

    def test_scaffold_derives_criteria_from_requirements(self, tmp_path):
        from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)

        scaffold_acceptance_matrix(feature_dir, "010-feat", requirement_ids=["FR-001", "FR-002"])

        matrix = read_acceptance_matrix(feature_dir)
        assert matrix is not None
        assert [c.criterion_id for c in matrix.criteria] == ["FR-001", "FR-002"]
        assert all(c.pass_fail == "pending" for c in matrix.criteria)

    def test_scaffold_is_idempotent(self, tmp_path):
        from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)

        # Operator-curated content must survive a re-scaffold.
        curated = AcceptanceMatrix(
            mission_slug="010-feat",
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-CUSTOM",
                    description="Operator authored",
                    proof_type="manual_qa",
                ),
            ],
        )
        write_acceptance_matrix(feature_dir, curated)

        scaffold_acceptance_matrix(feature_dir, "010-feat", requirement_ids=["FR-001"])

        matrix = read_acceptance_matrix(feature_dir)
        assert matrix is not None
        assert [c.criterion_id for c in matrix.criteria] == ["AC-CUSTOM"]
