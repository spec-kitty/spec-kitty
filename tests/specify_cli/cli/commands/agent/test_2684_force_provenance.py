"""#2684 / SC-007: persisted force-provenance is honest.

Formerly a red-first ``@pytest.mark.regression`` reproduction; relocated here
and un-marked (landing fold: make ``@pytest.mark.regression`` mean exactly
one thing) once the fix landed and this module started passing. #2684 is
fixed — this is now a permanent regression guard for the false-force
provenance bug, not a red-first pin.

Drives the **real** ``move-task`` entry point (Typer ``CliRunner``) and reads the
**persisted** ``StatusEvent.force`` off ``status.events.jsonl`` — never the plan
object — asserting the false-force provenance bug (found during #2736 / PR #2810)
is fixed for the CLI-reachable evidence-gated backward edges, without
over-suppressing genuine force.

Evidence-gated force-free edges (persisted ``force`` falsy):

* ``in_progress -> planned`` (``reason`` evidence).
* ``approved -> planned`` (``review_ref`` evidence).
* ``in_review -> planned`` / ``in_review -> in_progress`` — WP06 threads the
  structured ``review_result`` into ``build_transition_plan``, so these
  evidence-gated rejections persist ``force`` falsy. (Re-pointed here from the
  WP02-window truthful-force controls once WP06 landed its force-free flip.)

Genuine-force positive control (persisted ``force`` truthfully ``True``):

* leaving terminal ``done`` via ``--force`` — non-vacuous: fails loudly if T007
  over-suppresses (silent provenance loss the other way).

Truthful-force control (force-free-legal, but no CLI flag reaches its evidence):

* ``approved -> in_progress`` — force-free-legal WITH a ``review_ref``, but the
  caller-side seam that threads that ref lives in ``tasks_move_task.py`` (WP06-
  owned) and no CLI flag reaches it, so the persisted force is truthfully ``True``
  (T009 edge case: "force-free-legal edge but the caller omits evidence →
  persisted force truthy (honest)"). Its evidence-supplied flip is proven at the
  plan layer in
  ``test_tasks_transition_core.py::test_non_force_backward_with_evidence_is_force_free``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event, read_events
from tests.mocked_env import setup_mocked_env

if TYPE_CHECKING:
    from click.testing import Result

pytestmark = [pytest.mark.integration, pytest.mark.fast]

runner = CliRunner()


def _seed_wp_in_lane(
    tmp_path: Path, *, mission_slug: str, wp_id: str, lane: str
) -> Path:
    """Seed a feature dir with ``wp_id`` at ``lane`` in the canonical event log."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n"
        f"execution_mode: code_change\nagent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            reason=f"seed to {lane}",
        ),
    )
    return feature_dir


def _feedback_file(tmp_path: Path) -> Path:
    fb = tmp_path / "feedback.md"
    fb.write_text("**Issue**: provenance regression.\n\nRedo.\n", encoding="utf-8")
    return fb


def _invoke(tmp_path: Path, mission_slug: str, args: list[str]) -> Result:
    with setup_mocked_env(
        tmp_path, mission_slug=mission_slug, workspace_resolution=FileNotFoundError
    ):
        return runner.invoke(app, args, catch_exceptions=False)


def _persisted_force(feature_dir: Path, wp_id: str) -> bool:
    events = [e for e in read_events(feature_dir) if e.wp_id == wp_id]
    assert events, f"no persisted events for {wp_id}"
    return bool(events[-1].force)


# ---------------------------------------------------------------------------
# #3307: the review-rejection family (`* -> planned`) force-promotes to conform
# to the shared spec-kitty-events wire contract (the SaaS ingestion authority),
# which declares these edges force=True-required regardless of local evidence.
# Emitting force=False here produced contract-invalid events the SaaS silently
# dropped at sync. The structured rewind rationale still travels on the wire.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "starting_lane, target",
    [
        ("in_progress", "planned"),  # review-rejection family
        ("approved", "planned"),  # review-rejection family
        ("in_review", "planned"),  # review-rejection family
    ],
)
def test_review_rejection_family_persists_force_true(
    tmp_path: Path, starting_lane: str, target: str
) -> None:
    mission_slug = f"prov-{starting_lane}-{target}"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(
        tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane=starting_lane
    )
    feedback = _feedback_file(tmp_path)

    args = [
        "move-task",
        wp_id,
        "--to",
        target,
        "--mission",
        mission_slug,
        "--no-auto-commit",
    ]
    if target == "planned":
        args += ["--review-feedback-file", str(feedback)]

    result = _invoke(tmp_path, mission_slug, args)

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    assert _persisted_force(feature_dir, wp_id) is True, (
        f"{starting_lane} -> {target}: review-rejection family must persist "
        f"force=True to conform to the shared spec-kitty-events wire contract"
    )


# ---------------------------------------------------------------------------
# #3307: `in_review -> in_progress` is NOT in the mandatory-force `* -> planned`
# family, so the shared contract permits it force-free — but ONLY with a
# `review_ref` (which WP06 threads from the structured review_result). It stays
# force-free and carries that reference on the wire.
# ---------------------------------------------------------------------------


def test_in_review_to_in_progress_stays_force_free_with_review_ref(
    tmp_path: Path,
) -> None:
    mission_slug = "prov-in_review-in_progress"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(
        tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_review"
    )
    # #4899: in_review -> in_progress is a review-rejection edge (the
    # re-implement edge) and now durably requires reviewer feedback, exactly
    # like in_review -> planned — a bare CLI flag with no feedback file is
    # refused rather than silently accepted.
    feedback = _feedback_file(tmp_path)

    result = _invoke(
        tmp_path,
        mission_slug,
        [
            "move-task",
            wp_id,
            "--to",
            "in_progress",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    assert _persisted_force(feature_dir, wp_id) is False, (
        "in_review -> in_progress is force-free-legal WITH a review_ref; "
        "it must not be force-promoted"
    )


# ---------------------------------------------------------------------------
# Genuine-force positive control (non-vacuous): leaving terminal `done`
# ---------------------------------------------------------------------------


def test_genuine_force_leaving_done_persists_force_truthy(tmp_path: Path) -> None:
    """Leaving a terminal ``done`` state has no FSM edge, so ``--force`` is a real
    guard-bypass and the persisted ``force`` MUST stay truthful. Fails loudly if
    T007 over-suppresses (silent provenance loss the other way)."""
    mission_slug = "prov-done-force"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(
        tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="done"
    )

    result = _invoke(
        tmp_path,
        mission_slug,
        [
            "move-task",
            wp_id,
            "--to",
            "in_progress",
            "--force",
            "--note",
            "genuine force: leaving terminal done",
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"forced move failed:\n{result.output}"
    assert _persisted_force(feature_dir, wp_id) is True, (
        "leaving terminal done via --force must persist force=True (genuine bypass)"
    )


# ---------------------------------------------------------------------------
# Truthful-force control: force-free-legal edge whose evidence seam no CLI flag
# reaches (the two ``in_review -> *`` edges were re-pointed force-free above once
# WP06 threaded their ``review_result``; ``approved -> in_progress`` remains here).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "starting_lane, target",
    [
        ("approved", "in_progress"),  # review_ref seam is caller-side; no CLI flag reaches it
    ],
)
def test_wp02_window_edges_persist_force_truthy(
    tmp_path: Path, starting_lane: str, target: str
) -> None:
    """This edge is force-free-legal WITH a ``review_ref``, but the review_ref seam
    is caller-side (``tasks_move_task.py``, WP06-owned) and no CLI flag reaches it,
    so the persisted ``force`` is truthfully ``True`` — honest, not a false stamp.
    (The two ``in_review -> *`` edges, which WP06 threads force-free, now live in
    ``test_evidence_gated_backward_edge_persists_force_free``.)"""
    mission_slug = f"prov-{starting_lane}-{target}"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(
        tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane=starting_lane
    )
    args = [
        "move-task",
        wp_id,
        "--to",
        target,
        "--mission",
        mission_slug,
        "--no-auto-commit",
    ]
    if target == "planned":
        args += ["--review-feedback-file", str(_feedback_file(tmp_path))]

    result = _invoke(tmp_path, mission_slug, args)

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    assert _persisted_force(feature_dir, wp_id) is True, (
        f"{starting_lane} -> {target}: WP02 threads no force-free evidence, so the "
        f"persisted force is honestly True (WP06 flips it)"
    )
