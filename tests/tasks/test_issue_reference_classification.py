"""Reference gating classification (WP01, #3469).

Covers the C1 clauses of ``contracts/classification-and-verdict-contract.md``
for the move-task-approval-ergonomics mission: every discovered ``#NNNN``
reference is labelled with a gating :class:`GatingClass` --
``implementation_target`` (gating), ``context_only`` (non-gating), or
``pr_or_commit_ref`` (non-gating) -- and the classification is a pure,
deterministic aggregate over ALL of a number's occurrences (FR-015), never
just the first (fail-safe default, FR-011).

T001 is the red-first regression test: it drives the classification through
the OBSERVABLE ``scaffold_issue_matrix`` path (not internal classifier
plumbing) so it is provably RED against the pre-WP01 behavior, where every
discovered reference scaffolds an identical gating (``"unknown"``-verdict)
row regardless of context.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tasks.issue_matrix import scaffold_issue_matrix
from specify_cli.tasks.issue_reference_discovery import (
    GatingClass,
    Occurrence,
    classify_occurrences,
    discover_issue_references,
    gating_issue_numbers,
    is_gating,
)

pytestmark = [pytest.mark.fast]


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _mission_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "099-classification-demo"
    feature_dir.mkdir(parents=True)
    return feature_dir


# ---------------------------------------------------------------------------
# T001 -- red-first regression, pinned to #3469, driven through the
# OBSERVABLE scaffold_issue_matrix path.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_scaffold_only_gates_implementation_targets_3469(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3469: a bare ``#100`` and a dual-cited ``#400`` gate; a context-marked
    ``#200`` and a PR-cited ``#300`` do not.

    Pre-fix, ``scaffold_issue_matrix`` writes every discovered reference as
    an identical ``"unknown"``-verdict gating row -- #200 and #300 would
    wrongly gate. Post-fix, only #100 and #400 (``implementation_target``)
    scaffold a gating (``"unknown"``) row; #200 and #300
    (``context_only`` / ``pr_or_commit_ref``) scaffold a non-gating
    (``"not-applicable"``) row instead -- present for the audit trail, but
    never blocking approval.
    """
    import mission_runtime

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)

    feature_dir = _mission_dir(tmp_path)
    spec_md = feature_dir / "spec.md"
    spec_md.write_text(
        "\n".join(
            [
                "# Spec",
                "",
                "Fixes #100 as part of this change.",
                "",
                "Follow-up: revisit #200 later once the dust settles.",
                "",
                "PR #300 landed the mechanical rename.",
                "See #300 in https://github.com/spec-kitty/spec-kitty/pull/300 for the diff.",
                "",
                "Parent context: #400 explains the prior history.",
                "This work implements #400 directly.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    from specify_cli.coordination import write_seam

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        stage = kwargs.get("stage")
        assert callable(stage)
        stage()
        return write_seam.WriteSeamResult(
            status="committed",
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)

    out_path = scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="099-classification-demo",
        policy=_Policy(),
    )

    assert out_path is not None
    assert out_path.exists()

    import json

    rows = json.loads(out_path.read_text(encoding="utf-8"))["rows"]
    assert set(rows) == {"#100", "#200", "#300", "#400"}

    # Gating: an unmarked bare ref (#100) and a dual-cited ref where one
    # occurrence is an implementation target (#400, impl-target wins).
    assert rows["#100"]["verdict"] == "unknown"
    assert rows["#400"]["verdict"] == "unknown"

    # Non-gating: a context-marked ref (#200) and a PR-cited ref (#300) --
    # present (audit trail), but not a gating row.
    assert rows["#200"]["verdict"] == "not-applicable"
    assert rows["#300"]["verdict"] == "not-applicable"


# ---------------------------------------------------------------------------
# T002/T005 -- classifier signal coverage, executed directly.
# ---------------------------------------------------------------------------


class TestClassifyOccurrences:
    def test_bare_unmarked_reference_is_implementation_target(self) -> None:
        occurrences = (Occurrence(source_file="spec.md", line_text="Fixes #100 here."),)

        assert classify_occurrences(occurrences) == GatingClass.IMPLEMENTATION_TARGET

    @pytest.mark.parametrize(
        "line_text",
        [
            "Follow-up: revisit #200 later.",
            "baseline-red until #200 lands.",
            "see #200 for the parent discussion thread.",
            "Parent context: #200 explains history.",
            "Tracked by the epic #200.",
        ],
    )
    def test_each_context_marker_form_demotes_to_context_only(self, line_text: str) -> None:
        occurrences = (Occurrence(source_file="spec.md", line_text=line_text),)

        assert classify_occurrences(occurrences) == GatingClass.CONTEXT_ONLY

    @pytest.mark.parametrize(
        "line_text",
        [
            "The parent widget must resolve #4521",
            "Epic groundwork: fix #4521",
            "Refactor the parent class to close #4521",
            "This epic-scale bug in #4521 needs a fix",
            "We see #4521 failures in prod and must fix them",
            "Users see #4521 errors when clicking",
        ],
    )
    def test_ambiguous_english_word_on_implementation_line_still_gates(self, line_text: str) -> None:
        """#3469 fail-open fold: ``parent``/``epic``/``see`` are ordinary
        English words here, not citation labels -- a bare match anywhere on
        the line must NOT demote a genuine implementation-target line."""
        occurrences = (Occurrence(source_file="spec.md", line_text=line_text),)

        assert classify_occurrences(occurrences) == GatingClass.IMPLEMENTATION_TARGET

    def test_pr_hash_form_is_pr_or_commit_ref(self) -> None:
        occurrences = (Occurrence(source_file="spec.md", line_text="PR #300 landed the rename."),)

        assert classify_occurrences(occurrences) == GatingClass.PR_OR_COMMIT_REF

    def test_pull_url_form_is_pr_or_commit_ref(self) -> None:
        occurrences = (
            Occurrence(
                source_file="spec.md",
                line_text=("See #300 in https://github.com/spec-kitty/spec-kitty/pull/300."),
            ),
        )

        assert classify_occurrences(occurrences) == GatingClass.PR_OR_COMMIT_REF

    def test_multi_occurrence_implementation_target_wins(self) -> None:
        occurrences = (
            Occurrence(source_file="spec.md", line_text="Parent context: #400."),
            Occurrence(source_file="plan.md", line_text="This work implements #400."),
        )

        assert classify_occurrences(occurrences) == GatingClass.IMPLEMENTATION_TARGET

    def test_mixed_non_gating_occurrences_resolve_to_context_only(self) -> None:
        """Neither occurrence is an implementation target, but they are not
        ALL PR/commit refs either -- the aggregate is not_all-PR non-gating,
        which resolves to the more conservative ``context_only``."""
        occurrences = (
            Occurrence(source_file="spec.md", line_text="Follow-up: see #500."),
            Occurrence(source_file="plan.md", line_text="PR #500 landed the fix."),
        )

        assert classify_occurrences(occurrences) == GatingClass.CONTEXT_ONLY

    def test_empty_occurrences_is_gating_fail_safe(self) -> None:
        assert classify_occurrences(()) == GatingClass.IMPLEMENTATION_TARGET

    def test_classifier_is_pure_and_deterministic(self) -> None:
        occurrences = (Occurrence(source_file="spec.md", line_text="Fixes #100 here."),)

        first = classify_occurrences(occurrences)
        second = classify_occurrences(occurrences)

        assert first == second == GatingClass.IMPLEMENTATION_TARGET


# ---------------------------------------------------------------------------
# Cross-repo exclusion still holds through the classification seam.
# ---------------------------------------------------------------------------


def test_cross_repo_url_still_excluded_from_discovery(tmp_path: Path) -> None:
    feature_dir = _mission_dir(tmp_path)
    (feature_dir / "spec.md").write_text(
        "Prior art: https://github.com/other-org/other-repo/issues/999.\n",
        encoding="utf-8",
    )

    refs = discover_issue_references(feature_dir)

    assert refs == []


# ---------------------------------------------------------------------------
# FR-012 -- the ONE shared gating helper WP02/WP03 consume.
# ---------------------------------------------------------------------------


class TestSharedGatingHelper:
    def test_gating_issue_numbers_excludes_non_gating_refs(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text(
            "\n".join(
                [
                    "Fixes #100 here.",
                    "Follow-up: revisit #200 later.",
                    "PR #300 landed the rename.",
                ]
            ),
            encoding="utf-8",
        )

        assert gating_issue_numbers(feature_dir) == {"#100"}

    def test_gating_issue_numbers_empty_mission_is_empty_set(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)

        assert gating_issue_numbers(feature_dir) == set()

    def test_is_gating_matches_gating_issue_numbers(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text(
            "\n".join(
                [
                    "Fixes #100 here.",
                    "Follow-up: revisit #200 later.",
                ]
            ),
            encoding="utf-8",
        )

        refs = discover_issue_references(feature_dir)
        gating_refs = {ref for ref in refs if is_gating(ref)}

        assert {f"#{ref.number}" for ref in gating_refs} == gating_issue_numbers(feature_dir)
        assert {ref.number for ref in gating_refs} == {100}


# ---------------------------------------------------------------------------
# T003 -- discovery retains ALL occurrences + attaches classification.
# ---------------------------------------------------------------------------


class TestDiscoveryRetainsOccurrencesAndClassification:
    def test_discovered_reference_carries_its_classification(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text("Fixes #100 here.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        assert len(refs) == 1
        assert refs[0].classification == GatingClass.IMPLEMENTATION_TARGET

    def test_discovered_reference_aggregates_occurrences_across_files(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text("Parent context: #400 explains history.\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text("This work implements #400 directly.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        assert len(refs) == 1
        ref = refs[0]
        assert len(ref.occurrences) == 2
        assert {occ.source_file for occ in ref.occurrences} == {"spec.md", "WP01.md"}
        # Aggregate: one occurrence is an implementation target -> gates,
        # even though the FIRST occurrence (spec.md) was context-only.
        assert ref.classification == GatingClass.IMPLEMENTATION_TARGET

    def test_existing_callers_still_read_ref_number_unaffected(self, tmp_path: Path) -> None:
        """Backward compatibility: the 4 pre-existing consumers only ever
        read ``ref.number`` -- confirm that keeps working unmodified."""
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text("Fixes #100 here.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        assert {ref.number for ref in refs} == {100}
