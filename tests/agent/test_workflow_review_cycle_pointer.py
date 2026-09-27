from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import workflow, workflow_executor
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.frontmatter import write_frontmatter
from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.integration.coord_topology_fixture import _build_coord_topology
from tests.specify_cli.cli.commands.agent.test_tasks_move_task_seam import (
    _PARITY_MISSION_SLUG,
    _PARITY_WP_SLUG,
    _build_in_review_repo,
    _move_task_cli,
)

pytestmark = pytest.mark.git_repo


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def review_pointer_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    mission_slug = "001-review-pointer"
    feature_dir = repo / "kitty-specs" / mission_slug
    wp_dir = feature_dir / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("### WP01 - Core\n\n- [x] T001 Done\n", encoding="utf-8")
    write_frontmatter(
        feature_dir / "tasks" / "WP01-core.md",
        {
            "work_package_id": "WP01",
            "title": "Core",
            "subtasks": ["T001"],
            "dependencies": [],
            "review_status": "",
            "review_feedback": "",
        },
        "# WP01\n",
    )
    ReviewCycleArtifact(
        cycle_number=2,
        wp_id="WP01",
        mission_slug=mission_slug,
        reviewer_agent="codex",
        reviewed_at="2026-04-10T06:36:14Z",
        affected_files=[AffectedFile(path="src/app.py", line_range="10-20")],
        reproduction_command="pytest tests/agent -q",
        body="**Issue**: Persist canonical review feedback.\n",
    ).write(wp_dir / "review-cycle-2.md")
    return repo, feature_dir, mission_slug


def test_canonical_review_cycle_pointer_resolves_for_fix_context(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    has_feedback, ref, path, source = workflow._resolve_review_feedback_context(
        feature_dir,
        "WP01",
        "",
    )

    assert has_feedback is True
    assert source == "canonical"
    assert ref == pointer
    assert path == feature_dir / "tasks" / "WP01-core" / "review-cycle-2.md"
    assert ReviewCycleArtifact.from_file(path).body.startswith("**Issue**")


def test_fix_context_skips_action_review_claim_sentinel(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-claim",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="action-review-claim",
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:01+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    ref, path, _ = workflow._latest_review_feedback_reference(feature_dir, "WP01")

    assert ref == pointer
    assert path is not None


def test_fix_context_skips_synthetic_approval_token(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    """#4327 field-evidence regression (2026-09-19): an APPROVED work package
    whose newest ``review_ref`` is the synthetic ``auto-approval:<WP>:<date>``
    token must resolve to "no feedback present" -- the token is a verdict
    marker, not a path. Before the fix the token (or, earlier, the operator's
    ``--note`` prose that used to fill the slot) was resolved as a pointer,
    found no artifact, and made ``agent action implement`` refuse to re-claim
    the approved WP with a bogus "review feedback artifact is missing" error."""
    repo, feature_dir, mission_slug = review_pointer_repo
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-approve",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="auto-approval:WP01:20260920",
            reason="Codex APPROVE after 3 review cycles: all findings closed; 41 tests; suite green.",
        ),
    )

    has_feedback, ref, path, source = workflow._resolve_review_feedback_context(
        feature_dir,
        "WP01",
        "",
    )

    assert has_feedback is False
    assert ref is None
    assert path is None
    assert source is None


def test_fix_context_skips_synthetic_rejection_token_and_falls_back_to_real_pointer(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    """A synthetic ``review:<WP>`` token (a rejection that left no feedback
    artifact) is skipped like a sentinel; an OLDER real pointer still wins the
    scan, exactly as it does for ``action-review-claim``."""
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject-no-artifact",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:01+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="review:WP01",
        ),
    )

    ref, path, _ = workflow._latest_review_feedback_reference(feature_dir, "WP01")

    assert ref == pointer
    assert path is not None


def test_legacy_feedback_pointer_remains_readable_with_deprecated_kind(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    common_dir = repo / ".git"
    legacy = common_dir / "spec-kitty" / "feedback" / "001-review-pointer" / "WP01" / "feedback.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy feedback", encoding="utf-8")

    resolved = workflow._resolve_review_feedback_pointer(
        repo,
        "feedback://001-review-pointer/WP01/feedback.md",
    )

    assert resolved == legacy.resolve()


# ---------------------------------------------------------------------------
# T009 (#5024, WP02): a fix-mode render failure must surface an
# OPERATOR-VISIBLE warning, never fall silently through to a feedback-less
# full prompt (SC-003/FR-006). Paired with the success-path positive control
# exercised by the SC-005 tests below (real rejection -> real fix-mode
# render succeeds and shows the feedback).
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_fix_mode_render_failure_emits_visible_warning_not_silent_fallthrough(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A malformed review-cycle artifact drives ``ReviewCycleArtifact.from_file``
    to raise inside ``implement_try_render_fix_mode_prompt``. The function must
    still degrade to ``None`` (full prompt fallback) but ONLY after printing a
    visible warning on the console surface the implementer reads -- a
    ``logger.warning`` call alone (invisible in normal CLI usage) is not
    sufficient."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    mission_slug = "003-fix-mode-failure"
    feature_dir = repo / "kitty-specs" / mission_slug
    wp_dir = feature_dir / "tasks" / "WP01-core"
    wp_dir.mkdir(parents=True)

    broken_ref = f"review-cycle://{mission_slug}/WP01-core/review-cycle-9.md"
    broken_file = wp_dir / "review-cycle-9.md"
    # Malformed artifact (no YAML frontmatter) -- ReviewCycleArtifact.from_file
    # raises ReviewArtifactReadError, driving the except arm under test.
    broken_file.write_text("not a valid review-cycle artifact\n", encoding="utf-8")

    result = workflow_executor.implement_try_render_fix_mode_prompt(
        fix_mode_active=True,
        feature_dir=feature_dir,
        wp_slug="WP01-core",
        review_feedback_ref=broken_ref,
        review_feedback_file=broken_file,
        workspace_path=repo,
        mission_slug=mission_slug,
        normalized_wp_id="WP01",
        repo_root=repo,
    )

    assert result is None, "a render failure must fall through to the full prompt (return None), never crash"
    visible_output = capsys.readouterr().out
    assert "WP01" in visible_output
    assert visible_output.strip(), (
        "a fix-mode render failure must print an operator-visible warning on the console surface the implementer reads, not rely solely on logger.warning"
    )


# ---------------------------------------------------------------------------
# T008 (#5024, WP02): coord-topology STATUS_STATE split (SC-004) + no-pre-seed
# end-to-end anti-mask (SC-005). Written RED-first per NFR-002/C-011: before
# T010's read-split, the event-log read in ``latest_review_feedback_reference``
# is taken off whatever ``feature_dir`` it is handed -- PRIMARY on the real
# ``implement_resolve_feedback_and_gate`` call path -- so a durable rejection
# record that lives on the COORD partition (status.events.jsonl on the
# materialized coord worktree) is invisible to the render path even though a
# resolvable artifact already exists (F4: INDEPENDENT-RED, not a downstream
# consequence of WP01's write-side fix).
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_coord_status_state_split_resolves_feedback_file_contents(tmp_path: Path) -> None:
    """SC-004 (coord half, issue #5024): a durable resolvable rejection record
    already present on the COORD partition must resolve to the ACTUAL
    reviewer-feedback file CONTENTS when read through the PRIMARY
    ``feature_dir`` the real render call path holds -- not merely a truthy
    ``review_ref`` string (a pointer mis-resolved against the wrong tree would
    still return a non-None path pointing nowhere real, passing a weaker
    assertion vacuously)."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    feedback_text = "**Issue**: SC-004 coord-partition feedback must render on the fix-mode prompt.\n"
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug=ctx.slug,
        reviewer_agent="codex",
        reviewed_at="2026-04-10T06:36:14Z",
        affected_files=[AffectedFile(path="src/app.py", line_range="1-5")],
        reproduction_command="pytest tests/agent -q",
        body=feedback_text,
    ).write(ctx.primary_feature_dir / "tasks" / "WP01" / "review-cycle-1.md")

    pointer = f"review-cycle://{ctx.slug}/WP01/review-cycle-1.md"
    # The durable record lives on the COORD partition (the materialized coord
    # worktree's status.events.jsonl) -- NOT on the PRIMARY decoy the fixture
    # seeds.
    append_event(
        ctx.coord_feature_dir,
        StatusEvent(
            event_id="coord-seed-reject",
            mission_slug=ctx.slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    # The real render call path reads the PRIMARY ``feature_dir``
    # (``implement_resolve_feedback_and_gate`` passes a WORK_PACKAGE_TASK /
    # PRIMARY dir) -- this must still discover the COORD-partition record.
    ref, resolved_path, _ = workflow._latest_review_feedback_reference(ctx.primary_feature_dir, "WP01")

    assert ref == pointer
    assert resolved_path is not None, "coord-partition rejection record must resolve to a readable artifact"
    assert resolved_path.exists(), f"resolved feedback file missing: {resolved_path}"
    assert ReviewCycleArtifact.from_file(resolved_path).body == feedback_text


@pytest.mark.regression
def test_single_branch_status_state_reroute_is_a_noop(
    review_pointer_repo: tuple[Path, Path, str],
) -> None:
    """T012 (#5024): the STATUS_STATE read-split introduced for the coord
    render fix (SC-004) must be a no-op on a single-branch mission, where
    PRIMARY == COORD == repo_root collapse to the same directory. Explicit
    dual-topology non-regression leg alongside the coord-half test above."""
    repo, feature_dir, mission_slug = review_pointer_repo
    pointer = f"review-cycle://{mission_slug}/WP01-core/review-cycle-2.md"
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-reject-single-branch-noop",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref=pointer,
        ),
    )

    has_feedback, ref, path, source = workflow._resolve_review_feedback_context(feature_dir, "WP01", "")

    assert has_feedback is True
    assert source == "canonical"
    assert ref == pointer
    assert path == feature_dir / "tasks" / "WP01-core" / "review-cycle-2.md"


# ---------------------------------------------------------------------------
# SC-005 (#5024, WP02): one continuous, no-pre-seed end-to-end flow -- a
# reviewer's specific feedback text -> a REAL ``move-task`` rejection onto the
# ``in_review -> in_progress`` re-implement edge (WP01's real write path, NOT a
# pre-seeded fixture) -> the regenerated fix-mode prompt must render that EXACT
# text, on BOTH topologies.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_sc005_no_preseed_rejection_renders_feedback_text_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Coord-topology leg: the anti-mask control. Fails if EITHER WP01's write
    gate (``is_review_rejection_edge``) OR this WP's STATUS_STATE render split
    is left unfixed -- unlike ``test_coord_status_state_split_...`` above,
    nothing here pre-seeds a resolvable record; the rejection text originates
    from a REAL ``move-task WP01 --to in_progress --review-feedback-file``
    invocation."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    hops: tuple[tuple[Lane, Lane], ...] = (
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW),
    )
    for index, (from_lane, to_lane) in enumerate(hops, start=1):
        append_event(
            ctx.coord_feature_dir,
            StatusEvent(
                event_id=f"01SC005COORD{str(index).zfill(14)}",
                mission_slug=ctx.slug,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-09-27T12:00:{index:02d}Z",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

    feedback_text = "## Reviewer feedback\n\nSC-005 coord anti-mask: fix the retry backoff.\n"
    feedback_file = tmp_path / "sc005-coord-feedback.md"
    feedback_file.write_text(feedback_text, encoding="utf-8")

    monkeypatch.chdir(ctx.repo)
    runner = CliRunner()
    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "in_progress",
            "--mission",
            ctx.slug,
            "--agent",
            "reviewer-rita",
            "--review-feedback-file",
            str(feedback_file),
            "--no-auto-commit",
        ],
    )
    assert result.exit_code == 0, result.stdout

    ref, resolved_path, _ = workflow._latest_review_feedback_reference(ctx.primary_feature_dir, "WP01")
    assert ref is not None, "the real move-task rejection must have recorded a resolvable review_ref"
    assert resolved_path is not None and resolved_path.exists()

    fix_prompt_path = workflow_executor.implement_try_render_fix_mode_prompt(
        fix_mode_active=True,
        feature_dir=ctx.primary_feature_dir,
        wp_slug="WP01",
        review_feedback_ref=ref,
        review_feedback_file=resolved_path,
        workspace_path=ctx.repo / ".worktrees" / f"{ctx.slug}-lane-a",
        mission_slug=ctx.slug,
        normalized_wp_id="WP01",
        repo_root=ctx.repo,
    )

    assert fix_prompt_path is not None, "fix-mode prompt generation must not fall through to None"
    prompt_text = fix_prompt_path.read_text(encoding="utf-8")
    assert "fix the retry backoff" in prompt_text


@pytest.mark.regression
def test_sc005_no_preseed_rejection_renders_feedback_text_single_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-branch leg (T012 parity): PRIMARY == COORD == repo_root, so this
    must stay green both before and after the STATUS_STATE split."""
    repo, feature_dir, _sub_artifact_dir = _build_in_review_repo(tmp_path / "sc005-single")
    monkeypatch.chdir(repo)

    feedback_text = "## Reviewer feedback\n\nSC-005 single-branch parity: fix the retry backoff.\n"
    feedback_file = repo / "sc005-single-feedback.md"
    feedback_file.write_text(feedback_text, encoding="utf-8")

    result = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_file)
    assert result.exit_code == 0, result.stdout

    ref, resolved_path, _ = workflow._latest_review_feedback_reference(feature_dir, "WP01")
    assert ref is not None
    assert resolved_path is not None and resolved_path.exists()

    fix_prompt_path = workflow_executor.implement_try_render_fix_mode_prompt(
        fix_mode_active=True,
        feature_dir=feature_dir,
        wp_slug=_PARITY_WP_SLUG,
        review_feedback_ref=ref,
        review_feedback_file=resolved_path,
        workspace_path=repo,
        mission_slug=_PARITY_MISSION_SLUG,
        normalized_wp_id="WP01",
        repo_root=repo,
    )

    assert fix_prompt_path is not None
    prompt_text = fix_prompt_path.read_text(encoding="utf-8")
    assert "fix the retry backoff" in prompt_text
