"""Unit tests of the review-cycle adoption probe and the cycle-citation verifier (#7571 #7570 #3451).

Pure functions in ``specify_cli.review.cycle``: they read files and take the event log as an input,
never git. The probe decides whether an approval adopts a ``review-cycle-N.md`` the reviewer already
wrote (decision ``adoption_rule``: valid, referenced by no event, N above every referenced N, and the
reviewer of record's own identity); the verifier decides whether a ``cycle N`` citation in
``--approval-ref`` / ``--note`` names a current cycle (FR-010, research R7).

Each rule has a self-mutation check: the same inputs with one condition broken must change the
answer, so no test passes vacuously.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import DoneEvidence, Lane, ReviewApproval, ReviewResult, StatusEvent

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_MISSION = "001-adoption-probe"
_WP_ID = "WP01"
_WP_SLUG = "WP01-core"
_REVIEWER = "claude:sonnet:reviewer-renata"
_OTHER = "codex:gpt-5:reviewer-renata"


def _cycle() -> ModuleType:
    """The module under test, imported per test so each case reds on its own."""
    from specify_cli.review import cycle

    return cycle


def _pointer(n: int, *, mission: str = _MISSION, wp_slug: str = _WP_SLUG) -> str:
    return f"review-cycle://{mission}/{wp_slug}/review-cycle-{n}.md"


def _event(idx: int, to_lane: Lane, *, review_ref: str | None = None, result: tuple[str, int] | None = None, evidence: int | None = None) -> StatusEvent:
    review_result = ReviewResult(reviewer=_REVIEWER, verdict=result[0], reference=_pointer(result[1])) if result else None
    done_evidence = DoneEvidence(review=ReviewApproval(reviewer=_REVIEWER, verdict="approved", reference=_pointer(evidence))) if evidence else None
    return StatusEvent(
        event_id=f"e{idx:02d}",
        mission_slug=_MISSION,
        wp_id=_WP_ID,
        from_lane=Lane.PLANNED,
        to_lane=to_lane,
        at=f"2026-01-01T00:00:{idx:02d}+00:00",
        actor=_REVIEWER,
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
        review_result=review_result,
        evidence=done_evidence,
    )


def _write_cycle(wp_dir: Path, n: int, *, reviewer: str = _REVIEWER, wp_id: str = _WP_ID, cycle_number: int | None = None, raw: str | None = None) -> Path:
    path = wp_dir / f"review-cycle-{n}.md"
    if raw is not None:
        wp_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(raw, encoding="utf-8")
        return path
    ReviewCycleArtifact(
        cycle_number=cycle_number or n,
        wp_id=wp_id,
        mission_slug=_MISSION,
        reviewer_agent=reviewer,
        reviewed_at="2026-01-02T00:00:00Z",
        body="Approved: the work package does what its spec says.\n",
    ).write(path)
    return path


def _files(wp_dir: Path) -> dict[int, Path]:
    files: dict[int, Path] = _cycle().review_cycle_files_by_number((wp_dir,))
    return files


def _probe(wp_dir: Path, events: Sequence[StatusEvent], reviewer: str | None = _REVIEWER) -> Any:
    return _cycle().find_adoptable_review_cycle(
        files=_files(wp_dir),
        events=events,
        wp_id=_WP_ID,
        mission_slug=_MISSION,
        wp_slug=_WP_SLUG,
        reviewer_of_record=reviewer,
    )


def _verify(wp_dir: Path, events: Sequence[StatusEvent], *, approval_ref: str | None = None, note: str | None = None) -> str | None:
    refusal: str | None = _cycle().verify_cycle_citation(
        files=_files(wp_dir),
        events=events,
        wp_id=_WP_ID,
        mission_slug=_MISSION,
        wp_slug=_WP_SLUG,
        approval_ref=approval_ref,
        note=note,
    )
    return refusal


#: A first review: implemented, submitted, claimed. No cycle referenced yet.
_FIRST_CLAIM = [_event(1, Lane.FOR_REVIEW), _event(2, Lane.IN_REVIEW)]
#: A rejection that referenced cycle 1, rework, and a new claim.
_AFTER_REJECTION = [
    _event(1, Lane.IN_REVIEW),
    _event(2, Lane.PLANNED, review_ref=_pointer(1), result=("changes_requested", 1)),
    _event(3, Lane.FOR_REVIEW),
    _event(4, Lane.IN_REVIEW),
]


# ---------------------------------------------------------------------------
# parse_cycle_citations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("cycle 4 APPROVE", (4,), id="cycle-space-N"),
        pytest.param("Cycle 4 approve", (4,), id="case-insensitive"),
        pytest.param("see CYCLE-7", (7,), id="cycle-dash-N-upper"),
        pytest.param("per review-cycle-3.md", (3,), id="review-cycle-N-file"),
        pytest.param(_pointer(12), (12,), id="pointer-text"),
        pytest.param("cycle 2 and cycle 5", (2, 5), id="every-citation"),
        pytest.param("cycle 2, again cycle 2", (2,), id="deduplicated"),
    ],
)
def test_parse_cycle_citations_explicit_forms(text: str, expected: tuple[int, ...]) -> None:
    assert _cycle().parse_cycle_citations(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("recycle 2 the buffers", id="recycle"),
        pytest.param("the cycle time is fine", id="cycle-time"),
        pytest.param("one review cycle, no number", id="no-number"),
        pytest.param("lifecycle 3", id="lifecycle"),
        pytest.param("cycle 4th", id="ordinal"),
        pytest.param("cycle 0", id="zero-is-no-cycle"),
        pytest.param("approval://mission/reviewer", id="non-cycle-reference"),
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
    ],
)
def test_parse_cycle_citations_ignores_prose(text: str | None) -> None:
    assert _cycle().parse_cycle_citations(text) == ()


# ---------------------------------------------------------------------------
# cycle_numbers_referenced
# ---------------------------------------------------------------------------


def test_cycle_numbers_referenced_reads_every_reference_field() -> None:
    events = [
        _event(1, Lane.PLANNED, review_ref=_pointer(1)),
        _event(2, Lane.APPROVED, result=("approved", 2)),
        _event(3, Lane.DONE, evidence=3),
        _event(4, Lane.PLANNED, review_ref="force-override"),
        _event(5, Lane.APPROVED, review_ref="approval:WP01"),
    ]
    assert _cycle().cycle_numbers_referenced(events, _WP_ID) == frozenset({1, 2, 3})


def test_cycle_numbers_referenced_is_per_work_package_and_bounded() -> None:
    other = StatusEvent(**{**_event(9, Lane.PLANNED, review_ref=_pointer(9)).__dict__, "wp_id": "WP02"})
    events = [_event(1, Lane.PLANNED, review_ref=_pointer(1)), _event(2, Lane.PLANNED, review_ref=_pointer(2)), other]
    cycle = _cycle()
    assert cycle.cycle_numbers_referenced(events, _WP_ID) == frozenset({1, 2})
    assert cycle.cycle_numbers_referenced(events, _WP_ID, before_index=1) == frozenset({1})


# ---------------------------------------------------------------------------
# find_adoptable_review_cycle (decision adoption_rule)
# ---------------------------------------------------------------------------


def test_adopts_the_reviewers_own_post_claim_cycle(tmp_path: Path) -> None:
    path = _write_cycle(tmp_path, 1)
    result = _probe(tmp_path, _FIRST_CLAIM)
    assert result.kind == "adopt"
    assert result.path == path
    assert result.pointer == _pointer(1)


def test_no_cycle_file_means_nothing_to_adopt(tmp_path: Path) -> None:
    assert _probe(tmp_path, _FIRST_CLAIM).kind == "none"


def test_stale_cycle_is_never_adopted(tmp_path: Path) -> None:
    """FR-009: cycle 1 was answered by a rejection (referenced); it is not adopted, nothing is refused."""
    _write_cycle(tmp_path, 1)
    assert _probe(tmp_path, _AFTER_REJECTION).kind == "none"


def test_cycle_below_a_referenced_number_is_never_adopted(tmp_path: Path) -> None:
    """Condition 3: an unreferenced cycle 1 sits below the referenced cycle 2, so it is stale."""
    _write_cycle(tmp_path, 1)
    _write_cycle(tmp_path, 2)
    events = [_event(1, Lane.PLANNED, review_ref=_pointer(2), result=("changes_requested", 2)), _event(2, Lane.IN_REVIEW)]
    assert _probe(tmp_path, events).kind == "none"


def test_another_identity_is_not_adoptable(tmp_path: Path) -> None:
    path = _write_cycle(tmp_path, 1, reviewer=_OTHER)
    result = _probe(tmp_path, _FIRST_CLAIM)
    assert result.kind == "not_adoptable"
    assert result.path == path
    assert _OTHER in (result.reason or "")


def test_bare_tool_is_not_the_profiled_reviewer(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1, reviewer="claude")
    assert _probe(tmp_path, _FIRST_CLAIM).kind == "not_adoptable"


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("no frontmatter at all\n", id="no-frontmatter"),
        pytest.param("", id="empty-file"),
        pytest.param("---\ncycle_number: 1\n---\n\nbody\n", id="missing-fields"),
    ],
)
def test_invalid_post_claim_cycle_is_not_adoptable(tmp_path: Path, raw: str) -> None:
    path = _write_cycle(tmp_path, 1, raw=raw)
    result = _probe(tmp_path, _FIRST_CLAIM)
    assert result.kind == "not_adoptable"
    assert result.path == path


def test_cycle_number_disagreeing_with_its_filename_is_not_adoptable(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1, cycle_number=3)
    assert _probe(tmp_path, _FIRST_CLAIM).kind == "not_adoptable"


def test_cycle_of_another_work_package_is_not_adoptable(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1, wp_id="WP02")
    assert _probe(tmp_path, _FIRST_CLAIM).kind == "not_adoptable"


def test_several_valid_candidates_adopt_the_highest_and_report_the_rest(tmp_path: Path) -> None:
    lower = _write_cycle(tmp_path, 1)
    _write_cycle(tmp_path, 2)
    result = _probe(tmp_path, _FIRST_CLAIM)
    assert result.kind == "adopt"
    assert result.pointer == _pointer(2)
    assert result.ignored == (lower,)


def test_one_bad_candidate_refuses_even_beside_a_good_one(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    bad = _write_cycle(tmp_path, 2, reviewer=_OTHER)
    result = _probe(tmp_path, _FIRST_CLAIM)
    assert result.kind == "not_adoptable"
    assert result.path == bad


def test_unparseable_cycle_filenames_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "review-cycle-final.md").write_text("x", encoding="utf-8")
    (tmp_path / "review-feedback-1.md").write_text("x", encoding="utf-8")
    assert _files(tmp_path) == {}


def test_no_reviewer_of_record_adopts_nothing(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    assert _probe(tmp_path, _FIRST_CLAIM, reviewer=None).kind == "not_adoptable"


def test_first_directory_wins_for_a_number_on_two_surfaces(tmp_path: Path) -> None:
    coord, primary = tmp_path / "coord", tmp_path / "primary"
    first = _write_cycle(coord, 1)
    _write_cycle(primary, 1, reviewer=_OTHER)
    assert _cycle().review_cycle_files_by_number((coord, primary)) == {1: first}


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("referenced", id="break-condition-2-referenced-by-an-event"),
        pytest.param("lower", id="break-condition-3-below-a-referenced-number"),
        pytest.param("identity", id="break-condition-4-other-identity"),
        pytest.param("invalid", id="break-condition-1-invalid"),
    ],
)
def test_breaking_one_condition_changes_the_answer(tmp_path: Path, mutation: str) -> None:
    """Non-vacuity: the adoptable baseline adopts; each single broken condition stops adoption."""
    baseline = tmp_path / "baseline"
    _write_cycle(baseline, 2)
    assert _probe(baseline, _FIRST_CLAIM).kind == "adopt"

    mutated = tmp_path / mutation
    events: list[StatusEvent] = list(_FIRST_CLAIM)
    if mutation == "referenced":
        _write_cycle(mutated, 2)
        events.append(_event(3, Lane.APPROVED, result=("approved", 2)))
    elif mutation == "lower":
        _write_cycle(mutated, 2)
        events.insert(0, _event(0, Lane.PLANNED, review_ref=_pointer(3)))
    elif mutation == "identity":
        _write_cycle(mutated, 2, reviewer=_OTHER)
    else:
        _write_cycle(mutated, 2, raw="not a review cycle\n")
    assert _probe(mutated, events).kind != "adopt"


# ---------------------------------------------------------------------------
# verify_cycle_citation (FR-010)
# ---------------------------------------------------------------------------


def test_no_citation_verifies(tmp_path: Path) -> None:
    assert _verify(tmp_path, _FIRST_CLAIM, approval_ref="approval://x/y", note="Review passed") is None


def test_citation_of_a_current_cycle_verifies(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    assert _verify(tmp_path, _FIRST_CLAIM, note="cycle 1 APPROVE") is None
    assert _verify(tmp_path, _FIRST_CLAIM, approval_ref=_pointer(1)) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"note": "cycle 4 APPROVE"}, id="note"),
        pytest.param({"approval_ref": _pointer(4)}, id="pointer"),
        pytest.param({"approval_ref": "see review-cycle-4.md"}, id="ref-text"),
    ],
)
def test_citation_of_a_missing_cycle_names_the_expected_file(tmp_path: Path, kwargs: dict[str, str]) -> None:
    _write_cycle(tmp_path, 1)
    refusal = _verify(tmp_path, _FIRST_CLAIM, **kwargs)
    assert refusal is not None
    assert "REVIEW_CYCLE_CITATION_MISSING" in refusal
    assert "review-cycle-4.md" in refusal
    assert "does not exist" in refusal


def test_citation_of_an_invalid_cycle_is_refused(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1, raw="not a cycle\n")
    refusal = _verify(tmp_path, _FIRST_CLAIM, note="cycle 1")
    assert refusal is not None and "not a valid review cycle" in refusal


def test_citation_of_a_rejections_cycle_is_refused(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    refusal = _verify(tmp_path, _AFTER_REJECTION, note="cycle 1 APPROVE")
    assert refusal is not None and "rejection" in refusal


def test_citation_of_a_cycle_from_before_the_latest_claim_is_refused(tmp_path: Path) -> None:
    """R7: cycle 1 was referenced by an approval, then a rework and a new claim followed."""
    _write_cycle(tmp_path, 1)
    events = [
        _event(1, Lane.APPROVED, result=("approved", 1)),
        _event(2, Lane.PLANNED, review_ref="force-override"),
        _event(3, Lane.IN_REVIEW),
    ]
    refusal = _verify(tmp_path, events, note="cycle 1")
    assert refusal is not None and "before the latest review claim" in refusal


def test_reference_after_the_latest_claim_does_not_age_a_citation(tmp_path: Path) -> None:
    """Only references before the latest claim make a cycle stale; a later one (none in practice) does not."""
    _write_cycle(tmp_path, 2)
    events = [*_FIRST_CLAIM, _event(3, Lane.APPROVED, result=("approved", 2))]
    assert _verify(tmp_path, events, note="cycle 2") is None


@pytest.mark.parametrize(
    "pointer",
    [
        pytest.param(_pointer(1, mission="other-mission"), id="other-mission"),
        pytest.param(_pointer(1, wp_slug="WP02-other"), id="other-work-package"),
        pytest.param("review-cycle://broken", id="malformed"),
    ],
)
def test_pointer_to_another_work_package_is_refused(tmp_path: Path, pointer: str) -> None:
    _write_cycle(tmp_path, 1)
    refusal = _verify(tmp_path, _FIRST_CLAIM, approval_ref=pointer)
    assert refusal is not None and "REVIEW_CYCLE_CITATION_MISSING" in refusal


def test_every_citation_is_verified(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    refusal = _verify(tmp_path, _FIRST_CLAIM, approval_ref=_pointer(1), note="also cycle 9")
    assert refusal is not None and "review-cycle-9.md" in refusal


@pytest.mark.parametrize("mutation", ["missing", "rejection", "pre-claim"])
def test_breaking_one_citation_rule_changes_the_answer(tmp_path: Path, mutation: str) -> None:
    """Non-vacuity: a verifying citation stops verifying when one rule is broken."""
    baseline = tmp_path / "baseline"
    _write_cycle(baseline, 2)
    assert _verify(baseline, _FIRST_CLAIM, note="cycle 2") is None

    mutated = tmp_path / mutation
    events: list[StatusEvent] = list(_FIRST_CLAIM)
    if mutation != "missing":
        _write_cycle(mutated, 2)
    if mutation == "rejection":
        events = [_event(0, Lane.PLANNED, review_ref=_pointer(2), result=("changes_requested", 2)), *events]
    elif mutation == "pre-claim":
        events = [_event(0, Lane.APPROVED, result=("approved", 2)), *events]
    assert _verify(mutated, events, note="cycle 2") is not None


def test_codes_live_beside_the_cycle_grammar() -> None:
    cycle = _cycle()
    assert cycle.REVIEW_CYCLE_CITATION_MISSING == "REVIEW_CYCLE_CITATION_MISSING"
    assert cycle.REVIEW_CYCLE_NOT_ADOPTABLE == "REVIEW_CYCLE_NOT_ADOPTABLE"


def test_create_review_cycle_is_the_writer_and_the_old_name_its_alias() -> None:
    """FR-013: one writer, named for what it does; the old name stays as an alias (#6709)."""
    cycle = _cycle()
    assert cycle.create_rejected_review_cycle is cycle.create_review_cycle


# ---------------------------------------------------------------------------
# Legacy logs: a verdict that names no cycle (has_unaccounted_verdict)
# ---------------------------------------------------------------------------


def _legacy_approval(idx: int, reference: str) -> StatusEvent:
    """A pre-#7569 approval: it wrote a cycle file but recorded another reference."""
    return StatusEvent(
        **{
            **_event(idx, Lane.APPROVED).__dict__,
            "from_lane": Lane.IN_REVIEW,
            "review_result": ReviewResult(reviewer=_OTHER, verdict="approved", reference=reference),
        }
    )


@pytest.mark.parametrize("reference", ["approval:WP01", "auto-approval:WP01:20260101", "force-override", "LGTM in PR-42"])
def test_legacy_approval_without_a_pointer_adopts_and_refuses_nothing(tmp_path: Path, reference: str) -> None:
    """The old approval's cycle 1 is unreferenced and another identity's: neither adopted nor refused."""
    _write_cycle(tmp_path, 1, reviewer=_OTHER)
    events = [_legacy_approval(1, reference), _event(2, Lane.PLANNED, review_ref="force-override"), _event(3, Lane.IN_REVIEW)]
    cycle = _cycle()
    assert cycle.has_unaccounted_verdict(events, _WP_ID) is True
    assert _probe(tmp_path, events).kind == "none"


def test_synthetic_rejection_token_wrote_no_file_and_is_accounted_for(tmp_path: Path) -> None:
    _write_cycle(tmp_path, 1)
    events = [_event(1, Lane.PLANNED, review_ref="review:WP01", result=None), _event(2, Lane.IN_REVIEW)]
    assert _cycle().has_unaccounted_verdict(events, _WP_ID) is False
    assert _probe(tmp_path, events).kind == "adopt"


def test_approval_carried_to_done_is_not_a_verdict_of_its_own() -> None:
    carried = StatusEvent(**{**_event(2, Lane.DONE, evidence=1).__dict__, "from_lane": Lane.APPROVED})
    events = [_event(1, Lane.APPROVED, result=("approved", 1)), carried]
    assert _cycle().has_unaccounted_verdict(events, _WP_ID) is False


def test_feedback_path_and_path_references_name_their_cycle() -> None:
    cycle = _cycle()
    result_with_path = StatusEvent(
        **{
            **_event(1, Lane.APPROVED).__dict__,
            "review_result": ReviewResult(reviewer=_REVIEWER, verdict="approved", reference="approval:WP01", feedback_path="/x/tasks/WP01-core/review-cycle-3.md"),
        }
    )
    legacy_path = _event(2, Lane.PLANNED, review_ref="kitty-specs/m/tasks/WP01-core/review-cycle-4.md")
    prose = _event(3, Lane.PLANNED, review_ref="see review-cycle-5.md")
    assert cycle.cycle_numbers_referenced([result_with_path, legacy_path, prose], _WP_ID) == frozenset({3, 4})
    assert cycle.has_unaccounted_verdict([result_with_path], _WP_ID) is False
