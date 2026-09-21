"""WP09 / FR-005 (#3035): Gate 4 ``not_applicable`` on zero GATING references.

Covers T034/T035/T044: ``_evaluate_issue_matrix`` (Gate 4, post-merge only)
must record ``not_applicable`` -- never a fabricated matrix or a hard fail --
when the mission's GATING issue references (per
:func:`~specify_cli.tasks.issue_reference_discovery.gating_issue_numbers`,
the SAME shared gating authority the approval blocker, ``merge_gates``, and
``status/doctor`` consume, #3469) come up empty. When gating references DO
exist, fail-closed enforcement is retained unchanged.

NOTE (#3469 / landing fold for #4820): prior to this fold, this gate short-
circuited on RAW reference presence
(:func:`~specify_cli.tasks.issue_reference_discovery.discover_issue_references`)
rather than the gating subset. A mission citing ONLY a non-gating reference
(e.g. ``"See #123 for background."``) passed the approval blocker/merge
gate/doctor cleanly (all three already filtered to the gating subset) but
then hard-failed THIS gate post-merge, because the raw scan still found the
non-gating reference. ``test_non_gating_reference_only_is_not_applicable``
below pins the corrected behaviour. Fixture text also changed: ``"See #N"``
is classified ``context_only`` (non-gating) by
:func:`~specify_cli.tasks.issue_reference_discovery.classify_occurrence`, so
the fail-closed "references exist, no matrix -> FAIL" fixtures now use a
genuinely gating (implementation-target) sentence instead.

T044 (C-008 / B-1): a JSON-only (B3) mission must not be hard-failed by a
hardcoded ``issue-matrix.md`` ``.exists()`` precheck -- the presence gate now
goes through WP05's dir-based reader
(:func:`~specify_cli.tasks.issue_matrix_migration.issue_matrix_artifact_present`),
which resolves JSON-first with ``.md`` failover.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.review import MissionReviewDiagnostic, MissionReviewMode
from specify_cli.cli.commands.review import _evaluate_issue_matrix as evaluate_issue_matrix

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _RecordingConsole:
    """Minimal console double: records printed lines, no Rich markup needed."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, message: str = "") -> None:
        self.lines.append(str(message))


def _write_spec_with_reference(feature_dir: Path, issue_number: str = "1234") -> None:
    """Write a spec citing a GATING (implementation-target) reference.

    NOTE (#3469): NOT ``"See #N"`` -- that phrasing classifies as
    ``context_only`` (non-gating) under
    :func:`~specify_cli.tasks.issue_reference_discovery.classify_occurrence`
    and owes no issue-matrix row. Callers of this helper exercise the
    fail-closed "gating reference exists, no matrix -> FAIL" path, so the
    fixture text must actually be gating.
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(
        f"# Spec\n\nFix the pagination bug in #{issue_number}.\n",
        encoding="utf-8",
    )


def _write_spec_with_non_gating_reference(feature_dir: Path, issue_number: str = "1234") -> None:
    """Write a spec citing ONLY a non-gating (context-only) reference."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(
        f"# Spec\n\nSee #{issue_number} for background.\n",
        encoding="utf-8",
    )


def _write_valid_json_matrix(feature_dir: Path, issue_number: str = "1234") -> None:
    import json

    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {
                    f"#{issue_number}": {
                        "verdict": "fixed",
                        "evidence_ref": "tests/specify_cli/cli/commands/review/"
                        "test_zero_reference_not_applicable.py",
                        "title": "Zero-reference not_applicable",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T034 -- zero references -> not_applicable, never a hard fail
# ---------------------------------------------------------------------------


def test_zero_references_is_not_applicable_in_post_merge(tmp_path: Path) -> None:
    """A mission with no scanned artifact referencing a GH issue is not_applicable."""
    feature_dir = tmp_path / "kitty-specs" / "zero-ref-mission"
    feature_dir.mkdir(parents=True)
    # No spec.md / plan.md / tasks / contracts / issue-matrix at all.

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result == "not_applicable"
    assert findings == []


def test_zero_references_is_not_applicable_even_with_issue_refs_only_in_matrix(
    tmp_path: Path,
) -> None:
    """Discovery scans spec/plan/research/tasks/contracts -- NOT issue-matrix.md itself.

    A stray ``#NNN`` that only appears inside ``issue-matrix.md`` (never in a
    scanned artifact) must not count as a canonical reference -- the WP08
    discovery definition is authoritative, this gate does not re-scan.
    """
    feature_dir = tmp_path / "kitty-specs" / "matrix-only-ref-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "# Issue Matrix",
                "",
                "| issue | verdict | evidence_ref |",
                "|-------|---------|--------------|",
                "| #999 | fixed | commit abc123 |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result == "not_applicable"
    assert findings == []


def test_not_applicable_skips_gate_entirely_outside_post_merge(tmp_path: Path) -> None:
    """Non post-merge modes stay not_applicable regardless of references (unchanged)."""
    feature_dir = tmp_path / "kitty-specs" / "lightweight-mission"
    _write_spec_with_reference(feature_dir)

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.LIGHTWEIGHT,
        console=console,
        findings=findings,
    )

    assert result == "not_applicable"
    assert findings == []


def test_non_gating_reference_only_is_not_applicable(tmp_path: Path) -> None:
    """A mission citing ONLY a non-gating reference is not_applicable, not FAIL.

    #3469 / landing fold for #4820: this gate used to short-circuit on RAW
    reference presence (:func:`discover_issue_references`) rather than the
    shared gating subset (:func:`gating_issue_numbers`). A mission whose only
    citation is context-only (e.g. ``"See #N for background."``) passes the
    approval blocker, ``merge_gates``, and ``status/doctor`` cleanly -- all
    three already filter to the gating subset -- so it must ALSO be
    ``not_applicable`` here, never a post-merge ISSUE_MATRIX_MISSING hard
    fail, even though no issue-matrix artifact exists.
    """
    feature_dir = tmp_path / "kitty-specs" / "non-gating-only-mission"
    _write_spec_with_non_gating_reference(feature_dir, issue_number="1234")
    # No issue-matrix.md / issue-matrix.json.

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result == "not_applicable"
    assert findings == []


# ---------------------------------------------------------------------------
# T035 -- references present -> fail-closed retained
# ---------------------------------------------------------------------------


def test_references_present_and_matrix_missing_is_fail_closed(tmp_path: Path) -> None:
    """A mission that references a GH issue but ships no matrix fails hard."""
    feature_dir = tmp_path / "kitty-specs" / "has-ref-no-matrix-mission"
    _write_spec_with_reference(feature_dir)
    # No issue-matrix.md / issue-matrix.json.

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result is False
    assert len(findings) == 1
    assert findings[0]["type"] == "issue_matrix_violation"
    assert findings[0]["diagnostic_code"] == str(MissionReviewDiagnostic.ISSUE_MATRIX_MISSING)


def test_references_present_and_matrix_invalid_is_fail_closed(tmp_path: Path) -> None:
    """A present-but-schema-invalid matrix still fails with its specific diagnostic.

    ``issue_matrix_present`` (the bool this function returns) reports mere
    PRESENCE, not validity -- schema violations surface as
    ``issue_matrix_violation`` findings, which ``write_review_report``
    treats as a hard failure regardless of the presence flag (see
    ``_HARD_FAILURE_FINDING_TYPES`` in ``_report.py``). This is a regression
    guard for the "malformed matrix parses to zero valid rows" trap: the
    presence gate (``issue_matrix_artifact_present``) must not misreport
    this case as merely "missing" (that would swallow the real
    ``ISSUE_MATRIX_VERDICT_UNKNOWN`` diagnostic) -- see the CLI-level
    ``test_review_post_merge_invalid_issue_matrix_exits_nonzero`` in
    ``test_review_git_baseline.py`` for the end-to-end fail-closed proof.
    """
    feature_dir = tmp_path / "kitty-specs" / "has-ref-invalid-matrix-mission"
    _write_spec_with_reference(feature_dir, issue_number="123")
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "# Issue Matrix",
                "",
                "| issue | verdict | evidence_ref |",
                "|-------|---------|--------------|",
                "| #123 | deferred | commit abc123 |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result is True
    assert len(findings) == 1
    assert findings[0]["type"] == "issue_matrix_violation"
    assert findings[0]["diagnostic_code"] == str(
        MissionReviewDiagnostic.ISSUE_MATRIX_VERDICT_UNKNOWN
    )


def test_references_present_and_valid_matrix_passes(tmp_path: Path) -> None:
    """A mission with references AND a valid matrix still passes Gate 4."""
    feature_dir = tmp_path / "kitty-specs" / "has-ref-valid-matrix-mission"
    _write_spec_with_reference(feature_dir, issue_number="123")
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "# Issue Matrix",
                "",
                "| issue | verdict | evidence_ref |",
                "|-------|---------|--------------|",
                "| #123 | fixed | commit abc123 |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result is True
    assert findings == []


# ---------------------------------------------------------------------------
# T044 -- C-008 / B-1: JSON-only (B3) mission must not be hard-failed by the
# hardcoded ``.md`` .exists() precheck this WP deletes.
# ---------------------------------------------------------------------------


def test_references_present_json_only_matrix_passes(tmp_path: Path) -> None:
    """A JSON-only mission (no ``issue-matrix.md`` at all) must not hard-fail.

    Pre-fix, ``issue_matrix_path.exists()`` checked ONLY ``issue-matrix.md``
    and returned the hard failure before ``validate_issue_matrix`` (which is
    already JSON-aware) ever ran. This is the B3 greenfield-JSON regression
    #3035/C-008/B-1 names.
    """
    feature_dir = tmp_path / "kitty-specs" / "json-only-mission"
    _write_spec_with_reference(feature_dir, issue_number="1234")
    _write_valid_json_matrix(feature_dir, issue_number="1234")
    assert not (feature_dir / "issue-matrix.md").exists()

    findings: list[dict[str, str]] = []
    console = _RecordingConsole()

    result = evaluate_issue_matrix(
        feature_dir=feature_dir,
        review_mode=MissionReviewMode.POST_MERGE,
        console=console,
        findings=findings,
    )

    assert result is True
    assert findings == []
