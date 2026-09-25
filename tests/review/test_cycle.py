from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.review.cycle import (
    CreatedRejectedReviewCycle,
    ReviewCycleError,
    VerdictPersistenceOutcome,
    build_review_cycle_pointer,
    create_rejected_review_cycle,
    is_synthetic_review_ref,
    next_review_feedback_source_path,
    resolve_review_cycle_pointer,
    review_feedback_source_path,
    validate_review_artifact_file,
    validate_review_cycle_pointer,
)
from specify_cli.status import TransitionRequest

pytestmark = pytest.mark.git_repo


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)


def test_create_rejected_cycle_returns_canonical_pointer_and_review_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Fix the rejected behavior.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="codex",
    )

    assert created.artifact_path == tasks_dir / "WP01-core" / "review-cycle-1.md"
    assert created.pointer == "review-cycle://001-mission/WP01-core/review-cycle-1.md"
    assert created.review_result.verdict == "changes_requested"
    assert created.review_result.reference == created.pointer
    assert created.review_result.feedback_path == str(created.artifact_path)
    assert validate_review_artifact_file(created.artifact_path).body.startswith("**Issue**")


def test_empty_feedback_fails_before_artifact_write(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feedback = tmp_path / "feedback.md"
    feedback.write_text(" \n", encoding="utf-8")

    with pytest.raises(ReviewCycleError, match="empty"):
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            feedback_source=feedback,
            reviewer_agent="codex",
        )

    assert not (repo / "kitty-specs").exists()


def test_invalid_review_cycle_pointer_segments_are_rejected() -> None:
    with pytest.raises(ReviewCycleError):
        validate_review_cycle_pointer("review-cycle://../WP01/review-cycle-1.md")
    with pytest.raises(ReviewCycleError):
        build_review_cycle_pointer("001-mission", "WP01-core", "notes.md")


def test_resolve_canonical_pointer_validates_required_frontmatter(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    artifact_dir = repo / "kitty-specs" / "001-mission" / "tasks" / "WP01-core"
    artifact_dir.mkdir(parents=True)
    invalid = artifact_dir / "review-cycle-1.md"
    invalid.write_text("---\nverdict: rejected\n---\n\nbody\n", encoding="utf-8")

    resolved = resolve_review_cycle_pointer(
        repo,
        "review-cycle://001-mission/WP01-core/review-cycle-1.md",
    )

    assert resolved.kind == "canonical"
    assert resolved.path is None


def test_resolve_canonical_pointer_returns_valid_artifact(tmp_path: Path) -> None:
    # T046: this fixture calls create_rejected_review_cycle, which (T041) now
    # acquires feature_status_lock -- feature_status_lock_path resolves
    # through _git_common_dir(repo_root), which shells out to
    # `git rev-parse --git-common-dir` with cwd=repo_root. A bare, never-
    # created tmp_path/"repo" directory makes that subprocess call raise
    # FileNotFoundError (no such cwd) instead of the tolerant "not a git
    # repo" fallback -- so this fixture needs a real, initialized repo at
    # its OWN root, the same pattern every other fixture in this file uses
    # (never an ancestor -- that would reintroduce the #2990 hazard from the
    # other direction).
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: canonical context.\n", encoding="utf-8")
    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="codex",
    )

    resolved = resolve_review_cycle_pointer(repo, created.pointer)

    assert resolved.kind == "canonical"
    assert resolved.path == created.artifact_path.resolve()
    assert resolved.warnings == ()


def test_legacy_feedback_pointer_resolves_with_warning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    common_dir = repo / ".git"
    feedback_file = common_dir / "spec-kitty" / "feedback" / "001-mission" / "WP01" / "feedback.md"
    feedback_file.parent.mkdir(parents=True)
    feedback_file.write_text("legacy feedback", encoding="utf-8")

    with patch("specify_cli.review.cycle._resolve_git_common_dir", return_value=common_dir):
        resolved = resolve_review_cycle_pointer(repo, "feedback://001-mission/WP01/feedback.md")

    assert resolved.kind == "legacy"
    assert resolved.path == feedback_file.resolve()
    assert resolved.warnings


def test_sentinel_pointer_is_not_feedback_artifact(tmp_path: Path) -> None:
    resolved = resolve_review_cycle_pointer(tmp_path, "action-review-claim")

    assert resolved.kind == "sentinel"
    assert resolved.path is None


def test_synthetic_review_ref_tokens_are_recognized() -> None:
    """#4327: the synthetic marker tokens ``move-task`` mints when no real
    pointer exists are markers, not artifact pointers."""
    assert is_synthetic_review_ref("review:WP01")
    assert is_synthetic_review_ref("approval:WP01")
    assert is_synthetic_review_ref("auto-approval:WP01:20260920")
    assert is_synthetic_review_ref("  review:WP01  ")  # tolerated whitespace


def test_synthetic_review_ref_recognizer_never_matches_real_pointers_or_prose() -> None:
    """The recognizer must not eat a real pointer family or a sentinel."""
    assert not is_synthetic_review_ref("review-cycle://mission/WP01-core/review-cycle-2.md")
    assert not is_synthetic_review_ref("feedback://mission/WP01/feedback.md")
    assert not is_synthetic_review_ref("action-review-claim")
    assert not is_synthetic_review_ref("force-override")
    assert not is_synthetic_review_ref("https://example.invalid/pr/42")
    assert not is_synthetic_review_ref("Reviewed the diff and it looks good.")
    # A bare prefix with nothing after it is not a token.
    assert not is_synthetic_review_ref("review:")
    assert not is_synthetic_review_ref("")
    assert not is_synthetic_review_ref("   ")


MISSION_SLUG = "annoying-bugs-sweep-01KYHQ9F"
WP_ID = "WP03"
WP_SLUG = "WP03-ledger-grammar"


def test_self_referential_feedback_source_is_rejected(tmp_path: Path) -> None:
    """Permanent guard for #2996(b) -- fixed: handing
    ``create_rejected_review_cycle`` the WP's OWN prior ``review-cycle-N.md``
    as ``feedback_source`` is refused, not silently duplicated into a new
    cycle.

    History (issue #2996(b)): ``create_rejected_review_cycle``
    (``src/specify_cli/review/cycle.py:277-346``) used to validate
    ``feedback_source`` only for existence / is-a-file / non-empty content
    and computed the next cycle number purely from
    ``len(sub_artifact_dir.glob("review-cycle-*.md")) + 1``
    (``ReviewCycleArtifact.next_cycle_number``,
    ``src/specify_cli/review/artifacts.py:288-295``) -- it never inspected
    *what* ``feedback_source`` pointed at. Passing the WP's own
    ``review-cycle-1.md`` (the ``--review-feedback-file`` shape from the
    ticket) was accepted: its full text -- frontmatter delimiters and all --
    was read as plain body content and written out as ``review-cycle-2.md``,
    fabricating a duplicate cycle that outranked the real reviewer's original
    verdict (``ReviewCycleArtifact.latest`` always returns the
    highest-numbered file).

    This test asserts the artifact-first, guard-second contract that now
    holds since #2996(b) was fixed: this suite was extracted out of
    ``tests/regression/`` (2026-08 landing fold) once the guard landed and
    the reproduction turned green, per the regression-suite exit rule
    (``tests/regression/README.md``).
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    real_feedback = tmp_path / "feedback.md"
    real_feedback.write_text(
        "**Issue**: Ledger grammar drops the census delimiter.\n",
        encoding="utf-8",
    )

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=real_feedback,
        reviewer_agent="reviewer-renata",
    )
    assert created.artifact_path == wp_dir / "review-cycle-1.md"
    assert created.artifact.reviewer_agent == "reviewer-renata"

    # Hand the WP's OWN canonical review-cycle-1.md back in as the feedback
    # source -- the exact ``--review-feedback-file <review-cycle-1.md path>``
    # shape from the ticket -- with an empty reviewer_agent (also from the
    # ticket).
    #
    # The match pattern is deliberately narrower than the original
    # "review-cycle|duplicate|feedback": today's PRE-EXISTING guards ("Review
    # feedback file not found: ..." / "Review feedback file is empty: ...")
    # both contain the word "feedback", so that loose an alternation lets an
    # unrelated failure satisfy this assertion for the wrong reason. Only a
    # message that names the self-reference explicitly can match here.
    with pytest.raises(
        ReviewCycleError, match=r"own review-cycle|self-referential feedback"
    ) as exc_info:
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            wp_slug=WP_SLUG,
            feedback_source=created.artifact_path,
            reviewer_agent="",
        )

    # The operator's stated preference is loud failures WITH clear
    # instructions: the message must name what was wrong (feedback_source is
    # the WP's own prior review-cycle artifact) and tell the caller what to
    # do instead (pass the underlying reviewer feedback, not a prior cycle
    # artifact).
    message = str(exc_info.value)
    assert created.artifact_path.name in message, (
        "error message must name the offending review-cycle artifact so the "
        f"caller can identify it -- got: {message!r}"
    )
    assert any(
        word in message.lower() for word in ("instead", "use ", "pass ", "provide ")
    ), (
        "error message must be actionable -- it must tell the caller what to "
        f"do instead of the self-referential feedback_source -- got: {message!r}"
    )

    # These hold once the guard exists: no fabricated cycle-2, and the real
    # reviewer's cycle-1 verdict remains the authoritative "latest".
    assert not (wp_dir / "review-cycle-2.md").exists()
    latest = ReviewCycleArtifact.latest(wp_dir)
    assert latest is not None
    assert latest.reviewer_agent == "reviewer-renata"


def test_review_prompt_feedback_path_is_accepted_as_a_feedback_source(
    tmp_path: Path,
) -> None:
    """Guard for #3430: the rejection command ``agent action review`` prints
    must be runnable verbatim.

    The prompt names ``review_feedback_path`` twice -- once as the file the
    reviewer writes, once as the ``--review-feedback-file`` argument -- so
    whatever :func:`review_feedback_source_path` returns has to survive
    ``_guard_feedback_source_provenance``. It did not: the prompt advertised
    the WP's own ``review-cycle-N.md``, which is precisely what the guard
    refuses, so every rejection cost a cycle to discover the printed command
    could not be followed.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG
    wp_dir.mkdir()

    # The path the review prompt tells the reviewer to write feedback to, for
    # the first cycle (``len(glob("review-cycle-*.md")) + 1`` in workflow.py).
    feedback = review_feedback_source_path(wp_dir, 1)
    assert feedback.parent == wp_dir, "the prompt promises an in-repo path"
    feedback.write_text(
        "**Issue 1**: Ledger grammar drops the census delimiter.\n",
        encoding="utf-8",
    )

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    # The tool authors the verdict artifact itself, so the reviewer's feedback
    # file and the generated cycle must be two distinct files.
    assert created.artifact_path == wp_dir / "review-cycle-1.md"
    assert created.artifact_path != feedback

    # The next cycle's advertised path does not collide with the artifact just
    # written either.
    assert review_feedback_source_path(wp_dir, 2).name not in {
        path.name for path in wp_dir.glob("review-cycle-*.md")
    }


def test_next_review_feedback_source_path_matches_writer_allocation(
    tmp_path: Path,
) -> None:
    """#3243: the advertised feedback path is numbered by the SAME max+1
    authority the rejection writer allocates the artifact with.

    The prompt used to derive its advertised number as a COUNT of
    ``review-cycle-*.md`` files + 1, which diverges from the writer's
    ``max(parsed) + 1`` allocation whenever the count is not the max — and
    the mismatch is not cosmetic: the reviewer authors feedback at the
    advertised number, then the rejection allocates a DIFFERENT cycle
    number, so the "predicts the next rejection artifact path" contract the
    review prompt exists for silently breaks.
    """
    wp_dir = tmp_path / "kitty-specs" / "mission" / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True)

    # Empty dir -> cycle 1.
    assert next_review_feedback_source_path(wp_dir).name == "review-feedback-1.md"

    # A duplicate pair (the exact on-disk state #3243 reports: cycles 1 and 2
    # both present) -> the next number is max+1 = 3.
    (wp_dir / "review-cycle-1.md").write_text("cycle 1\n", encoding="utf-8")
    (wp_dir / "review-cycle-2.md").write_text("cycle 2\n", encoding="utf-8")
    assert next_review_feedback_source_path(wp_dir).name == "review-feedback-3.md"

    # A numbering GAP (1 and 3 present, 2 deleted) -> max+1 = 4. The count
    # derivation advertises 3 here — one behind the writer's allocation.
    (wp_dir / "review-cycle-2.md").unlink()
    (wp_dir / "review-cycle-3.md").write_text("cycle 3\n", encoding="utf-8")
    assert next_review_feedback_source_path(wp_dir).name == "review-feedback-4.md"


def test_next_review_feedback_source_path_refuses_unparseable_sibling(
    tmp_path: Path,
) -> None:
    """#3243/#3430: an unparseable sibling makes the derivation refuse, so a
    caller advertising the path fails closed with the repair message instead
    of printing a rejection command the writer would refuse.

    The count derivation silently included ``review-cycle-final.md`` in the
    total, advertising a number the writer's ``next_cycle_number`` refuses to
    allocate at all — the printed command was not runnable as printed.
    """
    wp_dir = tmp_path / "kitty-specs" / "mission" / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True)
    (wp_dir / "review-cycle-1.md").write_text("cycle 1\n", encoding="utf-8")
    (wp_dir / "review-cycle-final.md").write_text("not a number\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unparseable review-cycle filename"):
        next_review_feedback_source_path(wp_dir)


def test_guard_feedback_source_provenance_refuses_by_parse_alone_no_verdict_read(
    tmp_path: Path,
) -> None:
    """T032 (WP06, D-PLAN-5): ``_guard_feedback_source_provenance`` refuses a
    prior review-cycle artifact purely because it PARSES as one
    (``ReviewCycleArtifact.from_file`` succeeds) -- it never reads, branches
    on, or otherwise depends on a ``verdict`` value. This is not merely
    "unaffected by the field removal" as an accident: ``ReviewCycleArtifact``
    has no ``verdict`` attribute at all (WP06, FR-003/SC-007), so any
    verdict-based branching would raise ``AttributeError`` immediately. The
    absence of that crash, across a fixture where the artifact genuinely has
    no verdict field to read, is the direct, non-vacuous proof.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact
    from specify_cli.review.cycle import _guard_feedback_source_provenance

    assert not hasattr(ReviewCycleArtifact, "verdict"), (
        "this test's premise requires ReviewCycleArtifact to genuinely carry "
        "no verdict field -- if this fails, the guard could no longer be "
        "proven verdict-blind by this mechanism"
    )

    sub_artifact_dir = tmp_path / "tasks" / "WP01-some-title"
    sub_artifact_dir.mkdir(parents=True)
    prior_cycle_path = sub_artifact_dir / "review-cycle-1.md"
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug="verdict-guard-demo",
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-08-06T00:00:00+00:00",
        body="**Issue**: original reviewer feedback.\n",
    ).write(prior_cycle_path)

    # feedback_source is a DIFFERENT file (not the prior cycle's own path --
    # exercising the CONTENT-identity leg specifically, not the path leg),
    # whose content is a byte-copy of the prior cycle's full serialized text.
    resubmitted = tmp_path / "resubmitted-feedback.md"
    resubmitted.write_text(prior_cycle_path.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ReviewCycleError, match="parses as a review-cycle artifact"):
        _guard_feedback_source_provenance(
            feedback_source=resubmitted, sub_artifact_dir=sub_artifact_dir
        )

    # Non-vacuity control: genuine reviewer PROSE (no frontmatter at all, so
    # ``from_file`` cannot parse it) is admitted -- proving the guard
    # actually discriminates on parseability, not a blanket refusal.
    genuine_feedback = tmp_path / "genuine-feedback.md"
    genuine_feedback.write_text("**Issue**: a distinct, new finding.\n", encoding="utf-8")
    _guard_feedback_source_provenance(
        feedback_source=genuine_feedback, sub_artifact_dir=sub_artifact_dir
    )  # must not raise


def test_duplicate_prose_in_an_ordinary_feedback_file_is_admitted(
    tmp_path: Path,
) -> None:
    """Permanent guard, T045 (FR-004/SC-001/US1 AC5): an ORDINARY feedback
    file (never a review-cycle artifact) whose prose happens to duplicate a
    prior cycle's body verbatim must be ADMITTED and recorded as a genuine
    new cycle -- not refused. (Un-marked from ``@pytest.mark.regression`` in
    the 2026-08 landing fold: this test was never a red-first #2996
    reproduction -- it landed already green alongside the T045 rewrite -- so
    it belongs in this file's permanent suite per the regression-suite exit
    rule, ``tests/regression/README.md``.)

    HISTORY -- read before touching this test again: this test was
    previously named ``test_new_cycle_body_never_duplicates_a_prior_cycle_file``
    and asserted the OPPOSITE -- that this exact scenario must raise
    ``ReviewCycleError``. That assertion was WRONG against this mission's
    finalized spec, for three independent reasons (operator ruling, recorded
    here so nobody re-derives or re-litigates it):

    1. **US1 Acceptance Scenario 5** (spec.md): "Given a reviewer who finds
       the same defect a second time, When they submit reviewer feedback
       identical to a prior cycle's, Then the rejection is accepted and
       recorded as a new cycle." This test drives exactly that scenario, and
       the spec requires ADMISSION.
    2. **SC-001** names the OLD refusal behaviour as the defect being fixed,
       quoting the very error this test used to assert:
       ``ReviewCycleError: feedback_source content duplicates a prior
       review-cycle artifact (review-cycle-1.md) verbatim``.
    3. **spec.md's Revision History** records that the original SC-001 was
       refuted: "the real defect is the opposite: a second rejection with
       identical feedback is permanently refused" -- resolved to FR-004 + US1
       AC5, with an explicit warning that a literal reading of the OLD
       wording "would have had an implementer delete the content-identity
       guard and re-open #990/#2996(b)" -- precisely the trap the narrowed,
       parse-based guard (:func:`_guard_feedback_source_provenance`) avoids.

    The old test's own justification cited spec.md Acceptance Scenario 2 ("the
    operation is refused") -- a MISATTRIBUTION: that scenario is about a
    transition failing after a write ("no approved verdict is readable... the
    latest verdict is still rejected"), not content duplication. It said
    nothing that supported the old assertion.

    This is NOT a weakening of the #990/#2996(b) control. The old test's own
    docstring stated it drove "an ORDINARY feedback file -- never a
    review-cycle artifact" -- by construction it was never a #990 test. The
    #990/#2996(b) control lives in ``_guard_feedback_source_provenance``'s
    path leg (``test_self_referential_feedback_source_is_rejected``, still
    refuses) PLUS the parse-based content leg
    (``test_a_byte_copy_of_a_stored_artifact_under_a_new_name_is_still_rejected``
    below, added alongside this rewrite to carry #990/#2996(b) forward
    explicitly). C-002 protects that control's GUARANTEE, not this test's
    prior, over-broad collateral refusal.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    real_feedback = tmp_path / "feedback.md"
    real_feedback.write_text(
        "**Issue**: Ledger grammar drops the census delimiter.\n",
        encoding="utf-8",
    )
    cycle1 = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=real_feedback,
        reviewer_agent="reviewer-renata",
    )
    cycle1_bytes_before = cycle1.artifact_path.read_bytes()

    # An ORDINARY feedback file -- never a review-cycle artifact -- whose
    # content happens to duplicate cycle-1's body verbatim (US1 AC5's "the
    # same defect a second time" scenario).
    duplicate_feedback = tmp_path / "duplicate-feedback.md"
    duplicate_feedback.write_text(cycle1.artifact.body, encoding="utf-8")

    cycle2 = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=duplicate_feedback,
        reviewer_agent="reviewer-second-opinion",
    )

    # Admitted as a genuine new cycle, correctly numbered.
    assert cycle2.artifact_path == wp_dir / "review-cycle-2.md"
    assert cycle2.artifact.cycle_number == 2
    assert cycle2.artifact.body == cycle1.artifact.body
    assert cycle2.artifact.reviewer_agent == "reviewer-second-opinion"

    # The prior cycle's on-disk bytes are unchanged -- admission is a NEW
    # write, never a mutation of cycle 1.
    assert cycle1.artifact_path.read_bytes() == cycle1_bytes_before

    latest = ReviewCycleArtifact.latest(wp_dir)
    assert latest is not None
    assert latest.cycle_number == 2
    assert latest.reviewer_agent == "reviewer-second-opinion"


def test_a_byte_copy_of_a_stored_artifact_under_a_new_name_is_still_rejected(
    tmp_path: Path,
) -> None:
    """Permanent guard for #990/#2996(b), carried forward by T045's narrowed
    content leg: a BYTE-COPY of a stored ``review-cycle-N.md`` artifact,
    saved under a DIFFERENT name/path that does not itself match the
    ``review-cycle-N.md`` shape (so the PATH leg does not fire), must still
    be refused -- because its content PARSES as a ``ReviewCycleArtifact``
    (it genuinely IS a verdict record, just relocated/renamed).

    This is the case that makes
    ``test_duplicate_prose_in_an_ordinary_feedback_file_is_admitted``'s
    admission defensible rather than a #990/#2996(b) regression: distinct,
    ordinary reviewer PROSE that merely repeats earlier words is admitted
    (that test), but an actual copy of the artifact FILE itself -- frontmatter
    and all -- is not "prose"; it parses as a verdict record and stays
    refused, regardless of where it is saved. Un-marked from
    ``@pytest.mark.regression`` in the 2026-08 landing fold (never a
    red-first reproduction; #990/#2996(b) is fixed) per
    ``tests/regression/README.md``'s exit rule.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    real_feedback = tmp_path / "feedback.md"
    real_feedback.write_text(
        "**Issue**: Ledger grammar drops the census delimiter.\n",
        encoding="utf-8",
    )
    cycle1 = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=real_feedback,
        reviewer_agent="reviewer-renata",
    )

    # A BYTE-COPY of the stored artifact, saved OUTSIDE sub_artifact_dir under
    # a name that does NOT match review-cycle-N.md -- the path leg is moot
    # here; only the content-parse leg can catch this.
    relocated_copy = tmp_path / "renamed-copy-of-cycle-1.md"
    relocated_copy.write_bytes(cycle1.artifact_path.read_bytes())

    with pytest.raises(ReviewCycleError, match=r"parses as a review-cycle artifact"):
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            wp_slug=WP_SLUG,
            feedback_source=relocated_copy,
            reviewer_agent="reviewer-renata",
        )

    assert not (wp_dir / "review-cycle-2.md").exists()


def test_hand_edited_own_path_feedback_source_is_still_rejected(tmp_path: Path) -> None:
    """Permanent guard, T006 step 2 (#2996(b)): a feedback file at a
    ``review-cycle-N.md``-shaped path inside the WP's OWN directory is
    refused even when its content has been hand-edited to no longer
    duplicate any existing cycle's body.

    Both ``test_self_referential_feedback_source_is_rejected`` (exact-path,
    exact-content) and ``test_new_cycle_body_never_duplicates_a_prior_cycle_file``
    (content-only, different path) can each be satisfied by a fix that only
    implements ONE of the two checks. This is the case that forces genuine
    path-based detection to exist alongside content-based detection: the path
    is the WP's own review-cycle home, but the content is deliberately
    different from every existing cycle's body. Un-marked from
    ``@pytest.mark.regression`` in the 2026-08 landing fold (never a
    red-first reproduction; #2996(b) is fixed) per
    ``tests/regression/README.md``'s exit rule.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    real_feedback = tmp_path / "feedback.md"
    real_feedback.write_text(
        "**Issue**: Ledger grammar drops the census delimiter.\n",
        encoding="utf-8",
    )
    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=real_feedback,
        reviewer_agent="reviewer-renata",
    )

    # Hand-edit cycle-1's own file in place: same path, deliberately DIFFERENT
    # (non-duplicate) content.
    created.artifact_path.write_text(
        "---\nverdict: rejected\n---\n\nThis text does not match any prior body.\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewCycleError, match=r"own review-cycle"):
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            wp_slug=WP_SLUG,
            feedback_source=created.artifact_path,
            reviewer_agent="reviewer-renata",
        )

    assert not (wp_dir / "review-cycle-2.md").exists()


def test_unreadable_prior_cycle_does_not_crash_the_provenance_scan(
    tmp_path: Path,
) -> None:
    """Permanent guard, M3 (adversarial squad, PR #3156): a prior
    ``review-cycle-N.md`` that is not valid UTF-8 must be SKIPPED by the
    provenance scan, not crash it.

    ``_guard_feedback_source_provenance`` best-effort-falls-back on
    ``ValueError`` from ``ReviewCycleArtifact.from_file`` by re-reading the
    same file with the same ``encoding="utf-8"`` -- which raises the
    IDENTICAL ``UnicodeDecodeError`` (a ``ValueError`` subclass) a second
    time, this time uncaught. One non-UTF-8 or unreadable prior artifact in a
    WP dir then bricks EVERY subsequent review-cycle write for that WP. An
    unparseable/unreadable prior artifact cannot be the duplicate being
    searched for, so it must simply be skipped. Un-marked from
    ``@pytest.mark.regression`` in the 2026-08 landing fold (never a
    red-first reproduction; the crash is fixed) per
    ``tests/regression/README.md``'s exit rule.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG
    wp_dir.mkdir(parents=True)

    # A prior "review-cycle-1.md" that is NOT valid UTF-8 (and thus also not
    # parseable as frontmatter) -- simulates a corrupted or binary-garbled
    # prior artifact reaching the provenance scan.
    (wp_dir / "review-cycle-1.md").write_bytes(b"---\nverdict: rejected\n---\n\n\xff\xfe\x00bad")

    real_feedback = tmp_path / "feedback.md"
    real_feedback.write_text(
        "**Issue**: New, unrelated feedback.\n", encoding="utf-8"
    )

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=real_feedback,
        reviewer_agent="reviewer-renata",
    )

    assert created.artifact_path == wp_dir / "review-cycle-2.md"
    assert created.review_result.verdict == "changes_requested"


def test_frontmatter_shaped_feedback_prose_resubmitted_verbatim_is_admitted(
    tmp_path: Path,
) -> None:
    """Permanent guard. M4 lineage (adversarial squad, PR #3156), reassessed
    under T045's operator ruling: a feedback file that merely OPENS with a
    ``---``
    frontmatter-shaped block of plain prose (not valid YAML frontmatter --
    ``"Blocking issues"`` is a bare scalar, not a mapping, so it does NOT
    parse as a ``ReviewCycleArtifact``) is an ORDINARY feedback file, never a
    stored verdict record. Re-submitting it VERBATIM a second time is US1
    Acceptance Scenario 5's exact scenario ("a reviewer... submit[s] reviewer
    feedback identical to a prior cycle's") and must be ADMITTED.

    HISTORY: this test previously asserted the OPPOSITE (refusal), under the
    name ``test_resubmitted_feedback_with_its_own_frontmatter_is_still_rejected``,
    reasoning that the resubmission was "exactly the #990/#2996(b) shape the
    guard exists to refuse." Re-examined under the SAME operator ruling that
    corrected ``test_duplicate_prose_in_an_ordinary_feedback_file_is_admitted``
    (see that test's docstring for the full spec citations -- US1 AC5, SC-001,
    spec.md's Revision History): the premise was wrong. #990/#2996(b) is about
    a feedback_source that IS a prior verdict record (by path, or by content
    that PARSES as one -- see
    ``test_a_byte_copy_of_a_stored_artifact_under_a_new_name_is_still_rejected``).
    A feedback file that never parses as an artifact -- even one that visually
    resembles frontmatter -- is not that; resubmitting its identical prose is
    exactly what FR-004/US1 AC5 licenses. The ORIGINAL M4 finding this test's
    name preserves (frontmatter-stripping must run symmetrically on both
    sides of a comparison) is now moot: T045 retired the body-equality
    comparison entirely in favor of the self-contained parse-check, so there
    is no longer an asymmetric-stripping bug to guard against. Un-marked
    from ``@pytest.mark.regression`` in the 2026-08 landing fold (never a
    red-first reproduction) per ``tests/regression/README.md``'s exit rule.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    # Feedback file that itself opens with a frontmatter-SHAPED block but is
    # not valid YAML frontmatter -- an ORDINARY feedback file, not a stored
    # artifact.
    feedback = tmp_path / "feedback.md"
    feedback.write_text(
        "---\nBlocking issues\n---\nFix the null check.\n", encoding="utf-8"
    )

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )
    assert created.artifact_path == wp_dir / "review-cycle-1.md"

    # Re-submit the SAME feedback file verbatim -- US1 AC5's "identical
    # feedback" re-report -- must now be admitted as cycle 2.
    resubmitted = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    assert resubmitted.artifact_path == wp_dir / "review-cycle-2.md"
    assert resubmitted.artifact.body == created.artifact.body


def test_concurrent_verdict_writes_do_not_clobber_each_other(tmp_path: Path) -> None:
    """T040/T041 (FR-005/NFR-006): two callers racing
    ``create_rejected_review_cycle`` for the SAME ``wp_id``/``wp_slug`` must
    each produce a distinct, correct record -- never a silent loss where one
    caller's write clobbers the other's while BOTH callers report success.

    A threaded harness racing on a ``threading.Barrier`` is sufficient here:
    ``feature_status_lock`` is a real inter-process ``FileLock`` keyed on a
    path under the shared git common-dir, so two threads in this process
    contend on the exact same lock FILE two separate OS processes would.
    This is deliberately NOT SC-004's full durability-matrix bar (50+
    iterations across 2+ real OS processes, not threads) -- that heavier bar
    belongs to WP15's coverage over the real command surface.
    # TODO(WP15): upgrade to a real multi-process (not threaded) harness for
    # SC-004's full bar (>=50 iterations, 2+ OS processes) -- this fixture's
    # shape (two distinct feedback files, a barrier, disk-state assertions)
    # carries over unchanged; only the ``threading.Thread``/``Barrier`` pair
    # needs to become ``multiprocessing.Process``/a process-safe barrier.

    RED-FIRST EVIDENCE (T040, observed against the pre-T041 writer with NO
    lock on the allocate-then-write path): both threads reported SUCCESS,
    but only ONE ``review-cycle-*.md`` file existed on disk afterward --
    both threads' ``next_cycle_number`` calls read the (empty) directory
    before either write landed, so both allocated cycle 1 and raced to the
    identical path; whichever write landed last silently clobbered the
    other's content, with ZERO exception raised to either caller. See this
    WP's Activity Log / final report for the verbatim captured failure.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG

    feedback_a = tmp_path / "feedback-a.md"
    feedback_a.write_text("Reviewer A's feedback.\n", encoding="utf-8")
    feedback_b = tmp_path / "feedback-b.md"
    feedback_b.write_text("Reviewer B's feedback.\n", encoding="utf-8")

    barrier = threading.Barrier(2)
    results: dict[str, CreatedRejectedReviewCycle] = {}
    errors: dict[str, Exception] = {}

    def _race(name: str, feedback: Path, reviewer: str) -> None:
        barrier.wait()
        try:
            results[name] = create_rejected_review_cycle(
                main_repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                wp_slug=WP_SLUG,
                feedback_source=feedback,
                reviewer_agent=reviewer,
            )
        except Exception as exc:
            errors[name] = exc

    thread_a = threading.Thread(target=_race, args=("a", feedback_a, "reviewer-a"))
    thread_b = threading.Thread(target=_race, args=("b", feedback_b, "reviewer-b"))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert not errors, f"unexpected exception(s) from concurrent writers: {errors}"
    assert set(results) == {"a", "b"}, "both concurrent callers must report a result"

    on_disk = sorted(wp_dir.glob("review-cycle-*.md"))
    assert {p.name for p in on_disk} == {"review-cycle-1.md", "review-cycle-2.md"}, (
        "expected exactly the two distinct, stably-named review-cycle "
        f"artifacts, found {[p.name for p in on_disk]}"
    )
    bodies = {p.name: validate_review_artifact_file(p).body for p in on_disk}
    assert set(bodies.values()) == {
        "Reviewer A's feedback.\n",
        "Reviewer B's feedback.\n",
    }, f"both callers' distinct bodies must survive on disk intact: {bodies}"
    assert results["a"].artifact_path != results["b"].artifact_path


def test_crash_orphan_between_write_and_commit_permits_a_clean_retry(
    tmp_path: Path,
) -> None:
    """T043/T044 (FR-003): a process killed cleanly AFTER ``artifact.write()``
    + ``validate_review_artifact_file()`` landed but BEFORE the commit call
    ever started leaves an uncommitted "orphan" ``review-cycle-N.md`` on
    disk. A hard ``SIGKILL`` cannot be caught by any ``try/except`` -- this
    is a DIFFERENT mechanism than T043's validation-failure compensator, so
    it is reproduced directly: write a real, fully-valid orphan artifact to
    disk (bypassing ``create_rejected_review_cycle``/the commit step
    entirely -- the exact on-disk state a clean kill between a completed
    write and a not-yet-started commit leaves behind), then call
    ``create_rejected_review_cycle`` again with the SAME feedback, exactly
    as a caller's retry (or ``move-task`` re-invoked) would.

    Scoped precisely to spec.md's Acceptance Scenario 4 ("a process killed
    between the write and the commit") -- NOT a mid-write kill, which can
    leave a partially-written file on some filesystems and is a different,
    out-of-scope hazard no pure-Python mitigation can fully close.

    RED-FIRST EVIDENCE (T044, observed against the pre-T043/T045 writer):
    the identical retry was NOT idempotent -- it hit the (pre-narrowing)
    content-identity guard against its own orphan and was refused FOREVER
    with "feedback_source content duplicates a prior review-cycle artifact
    (review-cycle-1.md) verbatim", with no path to recover short of manually
    deleting the orphan file. See this WP's Activity Log / final report for
    the verbatim captured failure.

    GREEN (post T045): T045's narrowed guard no longer refuses plain
    reviewer prose merely because it repeats a prior stored body verbatim,
    so the retry succeeds cleanly. The orphan itself is NOT cleaned up by
    this call (nothing this writer's own T043 compensator wrote during this
    test run, so it never had a chance to intercept anything) -- it remains
    on disk as inert, untracked cycle-1 clutter, a consciously accepted
    residual for the genuine-crash case. The retry's own outcome -- a
    correct new record, allocated at the NEXT cycle number rather than
    colliding with the orphan -- requires zero manual cleanup, which is the
    actual FR-003 guarantee this test proves.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / MISSION_SLUG / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{WP_SLUG}.md").write_text("# WP03\n", encoding="utf-8")
    wp_dir = tasks_dir / WP_SLUG
    wp_dir.mkdir(parents=True)

    feedback_text = "**Issue**: Ledger grammar drops the census delimiter.\n"
    feedback = tmp_path / "feedback.md"
    feedback.write_text(feedback_text, encoding="utf-8")

    # Simulate the crash: write the orphan artifact DIRECTLY (bypassing
    # create_rejected_review_cycle and its commit step entirely).
    orphan = ReviewCycleArtifact(
        cycle_number=1,
        wp_id=WP_ID,
        mission_slug=MISSION_SLUG,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-01-01T00:00:00Z",
        body=feedback_text,
    )
    orphan.write(wp_dir / "review-cycle-1.md")

    # The identical retry, exactly as a caller (or move-task re-invoked)
    # would perform it.
    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_slug=WP_SLUG,
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
    )

    assert retried.review_result.verdict == "changes_requested"
    assert retried.artifact.reviewer_agent == "reviewer-renata"
    # The orphan (cycle 1) still occupies its slot; the retry lands as the
    # NEXT number rather than colliding with or silently overwriting it.
    assert retried.artifact.cycle_number == 2
    assert retried.artifact_path == wp_dir / "review-cycle-2.md"
    assert retried.artifact_path.exists()


def test_create_rejected_review_cycle_with_approved_verdict(tmp_path: Path) -> None:
    """T006 step 3: the generalized writer, called with ``verdict="approved"``
    against a WP whose latest artifact is ``rejected``, writes a new
    highest-numbered artifact with ``verdict: approved`` and a real
    ``reviewer_agent``.
    """
    from specify_cli.review.artifacts import ReviewCycleArtifact

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")

    rejection_feedback = tmp_path / "rejection-feedback.md"
    rejection_feedback.write_text("**Issue**: Missing regression test.\n", encoding="utf-8")
    rejected_cycle = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=rejection_feedback,
        reviewer_agent="reviewer-renata",
    )
    assert rejected_cycle.review_result.verdict == "changes_requested"

    approval_feedback = tmp_path / "approval-feedback.md"
    approval_feedback.write_text(
        "Approved by reviewer-renata: the missing test was added.\n", encoding="utf-8"
    )
    approved_cycle = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=approval_feedback,
        reviewer_agent="reviewer-renata",
        verdict="approved",
    )

    assert approved_cycle.artifact.cycle_number == 2
    assert approved_cycle.artifact.reviewer_agent == "reviewer-renata"
    assert approved_cycle.review_result.verdict == "approved"

    latest = ReviewCycleArtifact.latest(tasks_dir / "WP01-core")
    assert latest is not None
    assert latest.cycle_number == 2


def _unprotect_main(repo: Path) -> None:
    """Disable branch protection so a real commit lands on ``main`` (T006 step 4).

    Mirrors ``tests/coordination/test_analysis_report_rehome.py``'s
    ``_disable_branch_protection`` fixture idiom.
    """
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        "protection:\n  protected_branches: []\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test: unprotect main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_create_rejected_review_cycle_commits_the_written_artifact(tmp_path: Path) -> None:
    """T006 step 4 / T004: passing a ``commit_router`` actually commits the write.

    Real git-fixture repo (real ``git init``), the REAL ``RealCoordCommitRouter``
    (no stubbed ``safe_commit`` -- NFR-001), post-call proof read straight from
    ``git status --porcelain`` and ``git log`` -- mirrors quickstart.md's FR-001
    commit-step verification and the fixture idiom in
    ``tests/coordination/test_analysis_report_rehome.py``.
    """
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)

    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    # ``as_posix`` because ``str(Path)`` yields backslash separators on Windows,
    # which never match git's forward-slash porcelain output — the assert would
    # be vacuously true there instead of proving the artifact was committed (#3834).
    rel = created.artifact_path.relative_to(repo).as_posix()
    assert rel not in status.stdout, (
        f"the written artifact is NOT committed -- git status still shows it:\n"
        f"{status.stdout}"
    )

    log = subprocess.run(
        ["git", "log", "-1", "--name-only", "--pretty=format:"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "review-cycle-1.md" in log.stdout


@dataclass
class _FailingCommitRouter:
    """Stub ``CoordCommitRouter`` whose ``commit_artifact`` simulates a real
    commit failure (mirrors what ``commit_for_mission`` returns when it catches
    a ``ProtectedBranchRefused``/``CalledProcessError`` -- see
    ``coordination/commit_router.py``'s ``_STATUS_ERROR`` branch) without
    needing a real protected-branch git fixture. Modeled on
    ``_RecordingCoordRouter`` in
    ``test_tasks_move_task_pre_review_gate_observability.py``.
    """

    calls: list[Path] = field(default_factory=list)

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used by this call site")

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used by this call site")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.calls.extend(paths)
        return CommitArtifactResult(
            status="error",
            placement_ref=str(paths[0]) if paths else "",
            diagnostic="simulated ProtectedBranchRefused: destination branch is protected",
        )


def test_create_rejected_review_cycle_raises_when_commit_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Cycle 2 fix (#2697) + M2 (adversarial squad, PR #3156) established a
    non-``"committed"`` ``CommitArtifactResult`` as a hard failure that also
    rolled back the orphaned write.

    WP05 (verdict-seam-write-unification-01KZ9Q35, T026/D-PLAN-11) INVERTS
    this test's premise: with every verdict reader now on the event
    authority, the per-file ``.md`` commit is demoted to best-effort
    (``contracts/verdict-durability-write.md`` G1/NFR-004). A non-committed
    result is now a logged WARNING, not a raised ``ReviewCycleError`` --
    and (M2's rollback being scoped to genuine infra exceptions only, see
    ``create_rejected_review_cycle``'s own comment) the written artifact is
    no longer unlinked on a merely-non-committed result: an uncommitted
    ``.md`` is tolerated now that it is not the verdict's authority. An
    immediate retry with the SAME feedback and a working commit router
    therefore behaves exactly like T043/T045's crash-orphan retry (see
    ``test_crash_orphan_between_write_and_commit_permits_a_clean_retry``):
    it succeeds cleanly, allocated at the NEXT cycle number -- the orphan is
    inert clutter, not a collision.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    router = _FailingCommitRouter()

    with caplog.at_level("WARNING", logger="specify_cli.review.cycle"):
        created = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            feedback_source=feedback,
            reviewer_agent="reviewer-renata",
            commit_router=router,
        )

    assert created.artifact_path.exists(), (
        "T026 demote: a best-effort commit failure no longer rolls back the "
        "already-written artifact -- only a genuine infra exception does"
    )
    assert any(
        "Failed to commit review-cycle" in record.message for record in caplog.records
    ), (
        "a best-effort commit failure must still be logged as a WARNING, "
        f"never silently dropped; records={caplog.records}"
    )

    # The router WAS invoked once, with the written artifact path -- the
    # failure is real, not swallowed.
    artifact_path = tasks_dir / "WP01-core" / "review-cycle-1.md"
    assert router.calls == [artifact_path]
    assert created.artifact_path == artifact_path
    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == "commit_error"
    retained_bytes = artifact_path.read_bytes()

    # An immediate retry with the SAME feedback, now with a working commit
    # router, succeeds cleanly and lands at the NEXT cycle number -- the
    # T026-demoted orphan is inert clutter on disk, not a collision (T045's
    # narrowed content-identity guard no longer refuses plain reviewer prose
    # merely because it repeats a prior stored body verbatim).
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )
    assert retried.artifact_path == artifact_path
    assert retried.artifact.cycle_number == 1
    assert retried.artifact_path.read_bytes() == retained_bytes
    assert retried.persistence.classification == "durable"
    assert retried.persistence.verdict_durably_persisted


@dataclass
class _RaisingCommitRouter:
    """Stub ``CoordCommitRouter`` whose ``commit_artifact`` raises a bare
    exception directly (NOT a ``CommitArtifactResult`` with ``status="error"``,
    and NOT a ``ReviewCycleError``) -- mirrors a raise-based failure escaping
    from the mission-resolution/router layer underneath ``commit_artifact``
    itself (e.g. ``MissionSelectorAmbiguous`` or an ``OSError`` from the git
    invocation), as opposed to ``_FailingCommitRouter``'s modeled
    result-object failure that ``_commit_review_cycle_artifact`` converts into
    ``ReviewCycleError``.
    """

    calls: list[Path] = field(default_factory=list)

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used by this call site")

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used by this call site")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.calls.extend(paths)
        raise RuntimeError("simulated raise-based commit failure (not ReviewCycleError)")


def test_raise_based_commit_failure_retains_artifact_and_returns_failure(
    tmp_path: Path,
) -> None:
    """Landing-pass fold (#2697 shape): a raise-based commit failure --
    anything that is not a ``ReviewCycleError`` -- must roll back the
    orphaned write exactly like the ``ReviewCycleError`` path above, and must
    propagate the original exception rather than being swallowed.

    Before this fix, ``create_rejected_review_cycle``'s rollback was scoped
    to ``except ReviewCycleError``, so a bare-exception failure from the
    commit_router (e.g. a raised ``MissionSelectorAmbiguous`` or ``OSError``)
    escaped the rollback entirely and orphaned an uncommitted verdict
    artifact on disk -- one the working-tree reader would treat as latest
    (the #2697 shape this mission exists to close).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    router = _RaisingCommitRouter()

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=router,
    )

    # The router WAS invoked once, with the written artifact path -- the
    # failure is real, not swallowed.
    artifact_path = tasks_dir / "WP01-core" / "review-cycle-1.md"
    assert router.calls == [artifact_path]
    assert artifact_path.exists()
    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == "commit_exception"
    assert created.persistence.evidence_ref == (
        "kitty-specs/001-mission/tasks/WP01-core/review-cycle-1.md"
    )
    assert not created.persistence.verdict_durably_persisted


def test_validation_failure_after_write_leaves_no_orphaned_artifact(
    tmp_path: Path,
) -> None:
    """T043: widen the write-side compensator to cover
    ``validate_review_artifact_file`` failures, not only commit failures.

    Before this fix, ``artifact.write()`` and ``validate_review_artifact_file()``
    sat OUTSIDE the existing ``try/except ReviewCycleError: unlink; raise``
    compensator (which wrapped only the commit call) -- so a validation
    failure left the just-written artifact orphaned on disk with no
    rollback. Forcing ``validate_review_artifact_file`` to raise
    unconditionally (patched at its call site's own module symbol,
    ``specify_cli.review.cycle.validate_review_artifact_file`` -- the same
    bare name :func:`_allocate_and_write_review_cycle_locked` resolves
    through the module's globals at call time) and asserting the artifact
    file does not survive proves the widened compensator actually runs, not
    merely a comment claiming it does.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    def _always_raise(path: Path) -> None:
        raise ReviewCycleError("forced validation failure for T043")

    with (
        patch("specify_cli.review.cycle.validate_review_artifact_file", _always_raise),
        pytest.raises(ReviewCycleError, match="forced validation failure"),
    ):
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            feedback_source=feedback,
            reviewer_agent="reviewer-renata",
        )

    assert not (tasks_dir / "WP01-core" / "review-cycle-1.md").exists(), (
        "a validate_review_artifact_file failure must leave no orphaned "
        "artifact on disk -- the widened T043 compensator must have "
        "unlinked it"
    )
    assert not list((tasks_dir / "WP01-core").glob("review-cycle-*.md"))


@dataclass
class _ContendingThenSucceedingCommitRouter:
    """Spy ``CoordCommitRouter`` simulating T042's transient index.lock
    contention window: the FIRST ``commit_artifact`` call reports
    ``status="error"`` while a real ``index.lock`` marker sits under the
    repo's ``.git`` dir (so ``git_operation_in_progress`` reports ``True``);
    the SECOND call clears the marker and succeeds -- modelling the lock
    being released between this writer's bounded retry attempts."""

    lock_marker: Path
    attempts: int = 0

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used by this call site")

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used by this call site")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.attempts += 1
        placement_ref = str(paths[0]) if paths else ""
        if self.attempts < 2:
            return CommitArtifactResult(
                status="error",
                placement_ref=placement_ref,
                diagnostic="simulated transient index.lock contention",
            )
        self.lock_marker.unlink(missing_ok=True)
        return CommitArtifactResult(
            status="committed", placement_ref=placement_ref, commit_hash="deadbeef"
        )


def test_commit_retries_on_index_lock_contention_and_then_succeeds(
    tmp_path: Path,
) -> None:
    """T042: a transient ``index.lock`` contention window retries the SAME
    ``commit_artifact`` call and succeeds once the probe stops firing.

    Uses a REAL ``index.lock`` marker file under the repo's own ``.git`` dir
    (the same primary-checkout layout ``_resolve_git_dirs`` scans) so
    ``git_operation_in_progress`` -- the existing, unmocked, filesystem-only
    probe -- genuinely reports ``True`` on the first attempt, proving the
    retry gates on the REAL probe, not a stubbed boolean.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    lock_marker = repo / ".git" / "index.lock"
    lock_marker.write_text("", encoding="utf-8")

    router = _ContendingThenSucceedingCommitRouter(lock_marker=lock_marker)
    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=router,
    )

    assert router.attempts == 2, (
        "expected exactly one retry after the first index.lock-contending "
        f"error, observed {router.attempts} attempt(s)"
    )
    assert created.artifact_path.exists()
    assert not lock_marker.exists()


@dataclass
class _AlwaysContendingCommitRouter:
    """Spy ``CoordCommitRouter`` where every ``commit_artifact`` call reports
    ``status="error"`` while the ``index.lock`` marker never clears -- T042's
    "retries exhausted, contention never resolved" case."""

    attempts: int = 0

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used by this call site")

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used by this call site")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.attempts += 1
        return CommitArtifactResult(
            status="error",
            placement_ref=str(paths[0]) if paths else "",
            diagnostic="simulated permanent index.lock contention",
        )


def test_commit_retries_are_bounded_and_report_exhausted_contention(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T042: when the probe keeps firing across every bounded retry attempt,
    the retry loop still bails out at the same bound and still distinguishes
    "exhausted contention retries" from a plain commit failure in its
    message.

    WP05 (verdict-seam-write-unification-01KZ9Q35, T026/D-PLAN-11) INVERTS
    the failure mode this pins: the exhausted-contention outcome is now a
    logged WARNING (not a raised ``ReviewCycleError``), and -- per M2's
    rollback being scoped to genuine infra exceptions only -- the write is
    NO LONGER rolled back on a merely-non-committed result; T042's bounded
    retry count (``_COMMIT_CONTENTION_MAX_ATTEMPTS == 3``) is unaffected by
    the demote and is still asserted literally here.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    lock_marker = repo / ".git" / "index.lock"
    lock_marker.write_text("", encoding="utf-8")
    try:
        router = _AlwaysContendingCommitRouter()
        with caplog.at_level("WARNING", logger="specify_cli.review.cycle"):
            create_rejected_review_cycle(
                main_repo_root=repo,
                mission_slug="001-mission",
                wp_id="WP01",
                wp_slug="WP01-core",
                feedback_source=feedback,
                reviewer_agent="reviewer-renata",
                commit_router=router,
            )
        # _COMMIT_CONTENTION_MAX_ATTEMPTS is 3 (module constant) -- asserted
        # as a literal here so this test fails loudly if that bound ever
        # changes without an accompanying review of this expectation.
        assert router.attempts == 3
        assert (tasks_dir / "WP01-core" / "review-cycle-1.md").exists(), (
            "T026 demote: an exhausted-contention commit failure no longer "
            "rolls back the already-written artifact"
        )
        assert any(
            "Exhausted contention retries" in record.message
            for record in caplog.records
        ), (
            "an exhausted-contention failure must still be distinguished "
            f"from a plain commit failure in the logged WARNING; "
            f"records={caplog.records}"
        )
    finally:
        lock_marker.unlink(missing_ok=True)


def test_create_rejected_review_cycle_without_commit_router_is_unchanged(
    tmp_path: Path,
) -> None:
    """T006 step 5: backward compatibility -- omitting ``verdict``/``commit_router``
    (every existing caller's shape) still produces identical ``rejected``,
    uncommitted behavior.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Fix the rejected behavior.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="codex",
    )

    assert created.review_result.verdict == "changes_requested"
    assert created.artifact_path == tasks_dir / "WP01-core" / "review-cycle-1.md"
    assert created.artifact_path.exists()
    # No commit_router was supplied -- the write must remain uncommitted:
    # nothing under kitty-specs/ has ever been staged/committed in this
    # fixture, so git still reports it as untracked.
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "kitty-specs" in status.stdout, (
        "an uncommitted write should still show as untracked in git status"
    )


@pytest.mark.performance
def test_create_rejected_review_cycle_completes_within_a_fixed_time_budget(
    tmp_path: Path,
) -> None:
    """NFR-003: one write + one ``commit_artifact`` call completes quickly.

    A fixed-budget check (not a before/after benchmark) is proportionate here:
    the new work per write is one filesystem write plus one additional git
    commit -- the same shape the existing rejection path already performs
    today.
    """
    import time

    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True
    )
    _unprotect_main(repo)

    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    started = time.perf_counter()
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0, (
        f"create_rejected_review_cycle (write + commit) took {elapsed:.3f}s, "
        "expected under a generous 2s fixed budget on CI hardware"
    )


@dataclass
class _CountingCommitRouter:
    """Spy ``CoordCommitRouter`` counting ``commit_artifact`` invocations only
    (T075) -- ``commit_status`` is asserted unreachable because this writer's
    call site never invokes it at all; that leg belongs to a DIFFERENT
    module (``tasks_move_task.py``'s ``_mt_execute``), outside this WP's
    owned surface.
    """

    invocation_count: int = 0

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used by this call site")

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        raise AssertionError(
            "commit_status belongs to a different call site (_mt_execute), "
            "outside this WP's owned surface"
        )

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.invocation_count += 1
        return CommitArtifactResult(
            status="committed",
            placement_ref=str(paths[0]) if paths else "",
            commit_hash="deadbeef",
        )


def test_create_rejected_review_cycle_invokes_commit_artifact_at_most_once(
    tmp_path: Path,
) -> None:
    """T075: NFR-005's countable clause, restated against the ONE named port
    method this WP's writer actually calls.

    NFR-005 as spec.md words it ("at most one durable-persistence invocation
    per verdict", full stop) is unsatisfiable literally -- plan.md's
    Technical Context corrects this explicitly: every verdict already costs
    TWO durable-persistence invocations (one ``commit_artifact`` call for
    the review-cycle record, made HERE by
    ``_commit_review_cycle_artifact``; one ``commit_status`` call for the
    status event, made by a DIFFERENT call site --
    ``tasks_move_task.py``'s ``_mt_execute``), and FR-001's authority split
    REQUIRES both to exist. A countable clause nobody can satisfy is not a
    requirement, it is decoration.

    This restates the clause as: recording one verdict invokes THIS
    writer's own ``commit_artifact`` port method AT MOST ONCE. It
    deliberately does not (and must not) also count ``commit_status`` --
    a future reader must not attempt to collapse the review-cycle write and
    the status-event emit into a single invocation, which the authority
    split forbids. The existing fixed-budget wall-clock assertion
    (``test_create_rejected_review_cycle_completes_within_a_fixed_time_budget``)
    is unchanged by this test -- this is an ADDITIONAL, countable assertion
    alongside it, not a replacement.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Needs another pass.\n", encoding="utf-8")

    router = _CountingCommitRouter()
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=router,
    )

    assert router.invocation_count == 1, (
        "recording one verdict must invoke commit_artifact at most once "
        f"(observed {router.invocation_count} invocations)"
    )


def test_persistence_outcome_rejects_contradictory_states() -> None:
    with pytest.raises(ValueError, match="true durability flag"):
        VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=False,
            evidence_ref="kitty-specs/m/tasks/WP01/review-cycle-1.md",
            destination_ref="main",
            reason=None,
            message="not actually durable",
        )
    with pytest.raises(ValueError, match="durable outcome requires"):
        VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=True,
            evidence_ref=None,
            destination_ref="main",
            reason=None,
            message="durable",
        )
    with pytest.raises(ValueError, match="must not carry"):
        VerdictPersistenceOutcome(
            classification="durable",
            verdict_durably_persisted=True,
            evidence_ref="kitty-specs/m/tasks/WP01/review-cycle-1.md",
            destination_ref="main",
            reason="contradiction",
            message="durable but contradictory",
        )
    with pytest.raises(ValueError, match="non-durable outcome requires"):
        VerdictPersistenceOutcome(
            classification="persistence_failed",
            verdict_durably_persisted=False,
            evidence_ref="kitty-specs/m/tasks/WP01/review-cycle-1.md",
            destination_ref="main",
            reason=None,
            message="failed",
        )
    with pytest.raises(ValueError, match="only durable"):
        VerdictPersistenceOutcome(
            classification="busy",
            verdict_durably_persisted=True,
            evidence_ref=None,
            destination_ref=None,
            reason="queue_timeout",
            message="busy",
        )


def test_committed_without_destination_readback_is_failure_and_retained(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: not really committed.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=_CountingCommitRouter(),
    )

    assert created.artifact_path.exists()
    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == "destination_readback_missing"
    assert not created.persistence.verdict_durably_persisted


def test_committed_with_mismatched_destination_bytes_is_failure(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    with patch(
        "specify_cli.review.cycle._read_artifact_at_ref",
        return_value=b"different committed bytes",
    ):
        created = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="local evidence bytes",
            reviewer_agent="reviewer-renata",
            commit_router=_CountingCommitRouter(),
        )

    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == "destination_readback_mismatch"
    assert created.artifact_path.exists()


@dataclass
class _TimeoutCommitRouter(_FailingCommitRouter):
    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.calls.extend(paths)
        raise TimeoutError("simulated commit timeout")


def test_commit_timeout_is_typed_failure_with_retained_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="timeout evidence",
        reviewer_agent="reviewer-renata",
        commit_router=_TimeoutCommitRouter(),
    )

    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == "commit_timeout"
    assert created.artifact_path.read_text(encoding="utf-8").endswith("timeout evidence")


def test_real_commit_is_durable_only_after_exact_ref_readback(tmp_path: Path) -> None:
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: proven at destination.\n", encoding="utf-8")

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    assert created.persistence == VerdictPersistenceOutcome(
        classification="durable",
        verdict_durably_persisted=True,
        evidence_ref="kitty-specs/001-mission/tasks/WP01-core/review-cycle-1.md",
        destination_ref="main",
        reason=None,
        message="Review-cycle evidence is committed and verified at main.",
    )


def test_nonidentical_retry_does_not_adopt_retained_record(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)

    first = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="first body",
        reviewer_agent="reviewer-renata",
        commit_router=_FailingCommitRouter(),
    )
    second = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="different body",
        reviewer_agent="reviewer-renata",
        commit_router=_FailingCommitRouter(),
    )

    assert first.artifact_path.name == "review-cycle-1.md"
    assert second.artifact_path.name == "review-cycle-2.md"


def test_cycle_writer_never_acquires_verdict_save_queue(tmp_path: Path) -> None:
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    with patch(
        "specify_cli.review.verdict_commit_queue.acquire_verdict_save_queue",
        side_effect=AssertionError("cycle.py must not acquire the verdict queue"),
    ):
        local = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="local-only evidence",
            reviewer_agent="reviewer-renata",
        )
        retained = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="automatic retained evidence",
            reviewer_agent="reviewer-renata",
            commit_router=_FailingCommitRouter(),
        )
        retried = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="automatic retained evidence",
            reviewer_agent="reviewer-renata",
            commit_router=RealCoordCommitRouter(),
        )

    assert local.persistence.classification == "local_only"
    assert local.persistence.reason == "no_auto_commit"
    assert retained.persistence.classification == "persistence_failed"
    assert retried.persistence.classification == "durable"
    assert retried.artifact_path == retained.artifact_path


@dataclass
class _FixedStatusCommitRouter:
    status: str
    invocation_count: int = 0

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        raise AssertionError("feature_write_dir is not used")

    def commit_status(
        self, request: TransitionRequest, *, capability: GuardCapability
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.invocation_count += 1
        return CommitArtifactResult(
            status=self.status,
            placement_ref="main",
            diagnostic=f"simulated {self.status}",
        )


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("unchanged", "unchanged_unverified"),
        ("no_op_wrong_surface", "wrong_surface"),
    ],
)
def test_unverified_router_noops_are_failures_with_retained_evidence(
    tmp_path: Path, status: str, reason: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    router = _FixedStatusCommitRouter(status=status)

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body=f"evidence for {status}",
        reviewer_agent="reviewer-renata",
        commit_router=router,
    )

    assert created.artifact_path.exists()
    assert created.persistence.classification == "persistence_failed"
    assert created.persistence.reason == reason
    assert not created.persistence.verdict_durably_persisted


def test_identical_already_committed_retry_is_idempotently_durable(
    tmp_path: Path,
) -> None:
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    first = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="same evidence",
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )
    retained_bytes = first.artifact_path.read_bytes()
    router = _FixedStatusCommitRouter(status="error")

    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="same evidence",
        reviewer_agent="reviewer-renata",
        commit_router=router,
    )

    assert retried.artifact_path == first.artifact_path
    assert retried.artifact_path.read_bytes() == retained_bytes
    assert retried.persistence.classification == "durable"
    assert router.invocation_count == 0
    assert not (first.artifact_path.parent / "review-cycle-2.md").exists()


def test_ambiguous_identical_pending_records_fail_without_guessing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    first = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="same evidence",
        reviewer_agent="reviewer-renata",
    )
    duplicate = first.artifact_path.parent / "review-cycle-2.md"
    duplicate.write_bytes(first.artifact_path.read_bytes())

    with pytest.raises(ReviewCycleError, match="Multiple identical pending"):
        create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="same evidence",
            reviewer_agent="reviewer-renata",
            commit_router=_FixedStatusCommitRouter(status="error"),
        )


def test_real_commit_preserves_unrelated_partially_staged_state(tmp_path: Path) -> None:
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    unrelated.write_text("staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True)
    unrelated.write_text("worktree\n", encoding="utf-8")
    untracked = repo / "notes.tmp"
    # ``write_bytes`` so the fixture's newline bytes are LF on Windows too —
    # ``write_text`` would leave CRLF there and the byte-exact untouched
    # assert below could never hold (#3834).
    untracked.write_bytes(b"leave me alone\n")
    before_cached = subprocess.run(
        ["git", "diff", "--cached", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    before_worktree = subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout

    created = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="preserve unrelated state",
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    # #4888 (epic #4915) rewrote ``safe_commit`` to commit EXACTLY the
    # requested paths via ``git commit --only``, which structurally
    # disregards whatever else is staged/dirty in the index -- there is no
    # stash/pop dance that could collide with the unrelated partially-staged
    # ``unrelated.txt`` below, so the real commit succeeds and the evidence
    # readback verifies durable. The point of this test is (and remains) the
    # preservation assertions after it: an unrelated partially-staged file
    # must come through the commit completely untouched.
    assert created.persistence.classification == "durable"
    assert created.persistence.reason is None
    assert created.artifact_path.exists()
    assert subprocess.run(
        ["git", "diff", "--cached", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_cached
    assert subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_worktree
    assert untracked.read_bytes() == b"leave me alone\n"


def test_automatic_adoption_never_runs_git_while_feature_lock_is_held(
    tmp_path: Path,
) -> None:
    from specify_cli.status import locking as status_locking

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    original_popen = subprocess.Popen
    seen_git: list[tuple[str, ...]] = []
    violations: list[tuple[str, ...]] = []

    def guarded_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        command_value = kwargs.get("args", args[0] if args else ())
        command = tuple(str(part) for part in command_value)  # type: ignore[union-attr]
        if command and command[0] == "git":
            seen_git.append(command)
            if status_locking._get_thread_locks():
                violations.append(command)
        return original_popen(*args, **kwargs)  # type: ignore[arg-type]

    with patch("subprocess.Popen", guarded_popen):
        retained = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="lock boundary evidence",
            reviewer_agent="reviewer-renata",
            commit_router=_FailingCommitRouter(),
        )
        retried = create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug="001-mission",
            wp_id="WP01",
            wp_slug="WP01-core",
            body="lock boundary evidence",
            reviewer_agent="reviewer-renata",
            commit_router=_FailingCommitRouter(),
        )

    assert retained.artifact_path == retried.artifact_path
    assert any("show" in command for command in seen_git), seen_git
    assert violations == []


@pytest.mark.parametrize("artifact_state", ["untracked", "staged", "partially_staged"])
def test_retained_artifact_retry_preserves_unrelated_state(
    tmp_path: Path, artifact_state: str
) -> None:
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    retained = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="retry this exact evidence",
        reviewer_agent="reviewer-renata",
        commit_router=_FailingCommitRouter(),
    )
    if artifact_state in {"staged", "partially_staged"}:
        subprocess.run(
            ["git", "add", str(retained.artifact_path.relative_to(repo))],
            cwd=repo,
            check=True,
        )
    if artifact_state == "partially_staged":
        artifact_text = retained.artifact_path.read_text(encoding="utf-8")
        # ``newline="\n"`` keeps the rewrite in the artifact's canonical LF form
        # (``ReviewCycleArtifact.write`` writes bytes): a default text-mode write
        # would re-encode the file CRLF on Windows, and Git's clean filter would
        # then store LF — making the exact-bytes durability readback mismatch by
        # construction (#3834).
        retained.artifact_path.write_text(
            "".join(
                "reviewed_at: '2099-01-01T00:00:00+00:00'\n"
                if line.startswith("reviewed_at:")
                else line
                for line in artifact_text.splitlines(keepends=True)
            ),
            encoding="utf-8",
            newline="\n",
        )
        validate_review_artifact_file(retained.artifact_path)

    unrelated.write_text("worktree-only\n", encoding="utf-8")
    untracked = repo / "notes.tmp"
    # ``write_bytes``: deterministic LF fixture bytes on Windows too (#3834).
    untracked.write_bytes(b"leave untouched\n")
    before_unrelated_diff = subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    before_artifact = retained.artifact_path.read_bytes()
    artifact_rel = retained.artifact_path.relative_to(repo).as_posix()
    before_artifact_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", artifact_rel],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected_prefix = {
        "untracked": "??",
        "staged": "A ",
        "partially_staged": "AM",
    }[artifact_state]
    assert before_artifact_status.startswith(expected_prefix), before_artifact_status

    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="retry this exact evidence",
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    assert retried.artifact_path == retained.artifact_path
    assert retried.artifact_path.read_bytes() == before_artifact
    assert retried.persistence.classification == "durable"
    shown = subprocess.run(
        [
            "git",
            "show",
            f"main:{retried.artifact_path.relative_to(repo).as_posix()}",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    assert shown == before_artifact
    assert subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_unrelated_diff
    assert untracked.read_bytes() == b"leave untouched\n"


@pytest.mark.parametrize("artifact_state", ["staged", "partially_staged"])
def test_retained_artifact_retry_preserves_unrelated_staged_index_on_commit(
    tmp_path: Path, artifact_state: str
) -> None:
    """A successful retry commits only the retained artifact via ``--only``.

    #4888 (epic #4915) rewrote ``safe_commit`` to stage and commit EXACTLY
    the requested path via ``git commit --only``, which structurally
    disregards whatever else is staged or dirty in the index -- there is no
    stash/pop dance that an unrelated staged (or partially-staged) file
    could collide with. So a real commit of the retained, already-staged
    artifact here succeeds (``durable``), while ``unrelated.txt`` (staged
    *and* worktree-dirty) and the untracked ``notes.tmp`` pass through
    completely untouched. This test was originally written against the
    pre-#4888 stash-based ``safe_commit``, which refused to commit whenever
    unrelated content was staged; that refusal was the bug #4888 fixed, not
    a contract this test may keep asserting.
    """
    from specify_cli.agent_tasks_ports import RealCoordCommitRouter

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / "001-mission" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-core.md").write_text("# WP01\n", encoding="utf-8")
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    retained = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="retained staged evidence",
        reviewer_agent="reviewer-renata",
        commit_router=_FailingCommitRouter(),
    )
    artifact_rel = retained.artifact_path.relative_to(repo).as_posix()
    subprocess.run(["git", "add", artifact_rel], cwd=repo, check=True)
    if artifact_state == "partially_staged":
        artifact_text = retained.artifact_path.read_text(encoding="utf-8")
        # ``newline="\n"``: same canonical-LF rationale as the sibling test
        # above — a default text-mode write re-encodes CRLF on Windows (#3834).
        retained.artifact_path.write_text(
            "".join(
                "reviewed_at: '2099-01-01T00:00:00+00:00'\n"
                if line.startswith("reviewed_at:")
                else line
                for line in artifact_text.splitlines(keepends=True)
            ),
            encoding="utf-8",
            newline="\n",
        )
    unrelated.write_text("staged unrelated\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True)
    unrelated.write_text("worktree unrelated\n", encoding="utf-8")
    untracked = repo / "notes.tmp"
    untracked.write_text("untracked unrelated\n", encoding="utf-8")

    # Scoped to ``unrelated.txt``/``notes.tmp`` only: unlike them, the
    # artifact itself is EXPECTED to change state (staged -> committed) when
    # the retry succeeds, so it is asserted separately below rather than
    # folded into these "untouched" comparisons.
    before_cached = subprocess.run(
        ["git", "diff", "--cached", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    before_worktree = subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    before_bytes = retained.artifact_path.read_bytes()
    before_unrelated_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", "unrelated.txt", "notes.tmp"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout

    retried = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug="001-mission",
        wp_id="WP01",
        wp_slug="WP01-core",
        body="retained staged evidence",
        reviewer_agent="reviewer-renata",
        commit_router=RealCoordCommitRouter(),
    )

    assert retried.artifact_path == retained.artifact_path
    assert retried.artifact_path.read_bytes() == before_bytes
    assert retried.persistence.classification == "durable"
    assert retried.persistence.reason is None
    assert not (retained.artifact_path.parent / "review-cycle-2.md").exists()
    shown = subprocess.run(
        ["git", "show", f"main:{artifact_rel}"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    assert shown == before_bytes
    assert subprocess.run(
        ["git", "diff", "--cached", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_cached
    assert subprocess.run(
        ["git", "diff", "--", "unrelated.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_worktree
    assert subprocess.run(
        ["git", "status", "--porcelain=v1", "--", "unrelated.txt", "notes.tmp"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout == before_unrelated_status
    # The artifact itself is now committed and clean -- no longer staged.
    assert (
        subprocess.run(
            ["git", "status", "--porcelain=v1", "--", artifact_rel],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )
