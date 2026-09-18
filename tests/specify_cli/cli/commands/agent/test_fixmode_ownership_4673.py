"""#4673 (WP03): fix-mode ownership after rejection.

Field repro: after a reviewer rejects a WP (``move-task --to planned
--review-feedback-file ...``) and the implementer successfully claims it again
in fix mode, the ordinary resubmission (``move-task --to for_review --agent
<implementer>`` — no ``--force``) is refused with an "Agent mismatch" error
even though the implementer IS the legitimate current owner.

Root (grounded, C-006 — three ownership authorities, named and bounded):

* the transition-derived ``actor`` slot (overwritten every hop);
* the runtime ``agent`` slot (released on rejection via
  ``release_runtime_claim``, read by the move-task ownership gate,
  ``tasks_move_task.py:355``);
* a sticky resolved-binding ``role`` slot, NOT released with the claim.

Two CLI-local mechanisms combined to produce the bug:

(a) ``_mt_emit_runtime_state`` (``tasks_move_task.py``) built ONE
    ``InnerStateChanged`` delta on a rejection carrying BOTH
    ``fields["agent"] = st.agent`` (the REVIEWER performing the rejection —
    the reviewer's own prior review-claim had already stamped the runtime
    ``agent`` slot to their identity) AND ``release_runtime_claim=True``. The
    reducer applies the release-clear BEFORE its replace-slot loop, so the
    concrete ``agent`` value in the SAME delta overwrote the just-released
    slot right back to the reviewer — the release never actually took effect
    for an ORDINARY rejection (fixed by suppressing the restamp when the
    requested agent is the SAME as the prior owner on a ``planned`` target;
    a genuine same-move re-plant of a DIFFERENT identity still wins, see
    ``test_move_task_rollback_clears_claim.py``).

(b) ``_guard_agent_ownership`` (``tasks_transition_core.py``) compared the
    runtime ``agent`` slot by RAW STRING equality, not through the tool-scoped
    ``_actor_key`` projection WP01 (#4665) introduced one layer down — so a
    dict-vs-compact-string submission of the SAME logical agent still tripped
    this gate even after WP01 landed.

Even with (a) fixed, a THIRD, upstream mechanism can still bite (C-001): the
shared ``spec-kitty-events`` reducer folds ALL transitions first, THEN ALL
``InnerStateChanged`` annotations in one dedicated post-pass — never
interleaved by timestamp (``spec_kitty_events.diary.reduce_parsed``, steps
3-4). A stale ``release_runtime_claim`` annotation from the EARLIER rejection
is therefore replayed AFTER a LATER fix-mode claim's ``policy_metadata``-
derived ``agent`` has already landed in the (earlier) transition-fold pass,
clobbering it back to falsy. T012 closes this by threading the claim owner
through the SAME per-transition ``annotation_delta`` channel the sticky
``role`` slot already rides (which is immune to this precisely because it
is not in ``_CLAIM_RELEASE_SLOTS``): a fresh, later-timestamped ``agent``
annotation always wins the post-pass over the stale release, regardless of
fold order.

Test harness note: mirrors ``test_move_task_rollback_clears_claim.py`` /
``test_move_task_reject_fix_approve_cycle.py`` — GENESIS->PLANNED and the
reviewer's for_review->in_review review-claim are seeded directly via
``append_event`` (that hop's real CLI surface is ``agent action review``, a
wholly separate command not under test here); every hop actually exercising
the #4673 fix (claim, rejection, fix-mode reclaim, resubmission) drives the
REAL ``move-task`` CLI entry point.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.status import Lane
from specify_cli.status.models import InnerStateChanged, StatusEvent, WPInnerStateDelta
from specify_cli.status.reducer import reduce as reduce_snapshot
from specify_cli.status.store import (
    append_annotations_atomic_verified,
    append_event,
    read_event_stream,
)
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_MISSION_SLUG = "001-fixmode-ownership-4673"
_IMPLEMENTER = "implementer"
_REVIEWER = "reviewer"
_OTHER_AGENT = "someone-else"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _seed_claim_through_in_review(feature_dir: Path) -> None:
    """Seed genesis -> planned -> claimed(implementer) -> ... -> in_review(reviewer).

    The ``planned -> claimed`` hop carries the claim triple on its
    ``policy_metadata`` (FR-004), exactly as a real implement claim does —
    the ONLY transition the shared reducer's transition-fold pass reads a
    runtime slot from directly (``spec_kitty_events.diary._wp_state_from_event``).
    The ``for_review -> in_review`` hop is a plain transition PLUS a separate
    ``InnerStateChanged`` annotation carrying the reviewer's claim — mirroring
    ``agent action review``'s real production path
    (``workflow_executor.review_claim_transition`` -> ``start_review_status``,
    a wholly separate command from ``move-task``, not under test here) — so
    the runtime ``agent``/``role`` slots are already "reviewer" BEFORE the
    rejection under test runs (matching the live sequencing: a reviewer must
    claim the review before they can reject it).
    """
    hops = [
        (Lane.GENESIS, Lane.PLANNED, None, "fixture"),
        (
            Lane.PLANNED,
            Lane.CLAIMED,
            {"shell_pid": 111, "agent": _IMPLEMENTER},
            _IMPLEMENTER,
        ),
        (Lane.CLAIMED, Lane.IN_PROGRESS, None, _IMPLEMENTER),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW, None, _IMPLEMENTER),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW, None, _REVIEWER),
    ]
    for idx, (frm, to, policy_metadata, actor) in enumerate(hops, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{idx}",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=frm,
                to_lane=to,
                at=f"2026-01-01T00:00:{idx:02d}+00:00",
                actor=actor,
                force=True,
                execution_mode="worktree",
                policy_metadata=policy_metadata,
            ),
        )
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01HXYZ00000000000000000006",
                wp_id="WP01",
                at="2026-01-01T00:00:06+00:00",
                actor=_REVIEWER,
                delta=WPInnerStateDelta(shell_pid=222, agent=_REVIEWER, role="reviewer"),
            )
        ],
    )


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "4673@example.invalid")
    _git(repo, "config", "user.name", "Fixmode Ownership")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("auto_commit: false\nprotection:\n  protected_branches: []\n", encoding="utf-8")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n\n(no subtasks)\n", encoding="utf-8")
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed fixmode-ownership-4673 fixture")
    _seed_claim_through_in_review(feature_dir)

    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _snapshot_wp_state(feature_dir: Path) -> dict[str, object]:
    stream = read_event_stream(feature_dir)
    snapshot = reduce_snapshot(stream.transitions, stream.annotations)
    return snapshot.work_packages.get("WP01") or {}


def _last_transition_actor(feature_dir: Path) -> object:
    stream = read_event_stream(feature_dir)
    return stream.transitions[-1].actor


def _move(args: list[str]) -> Result:
    return CliRunner().invoke(tasks_app, ["move-task", *args])


def test_fixmode_resubmission_needs_no_force_after_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The canonical #4673 e2e: implement -> for_review -> in_review ->
    rejection -> fix-mode reclaim -> resubmission WITHOUT --force.

    Asserts the THREE named ownership authorities (C-006) at each hop — the
    transition ``actor`` slot, the runtime ``agent`` slot, and the sticky
    ``role`` slot — never the same slot read twice.
    """
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)

    # --- Positive control: BEFORE the rejection, the reviewer's own claim is
    # live across all three authorities. ---
    before = _snapshot_wp_state(feature_dir)
    assert before.get("agent") == _REVIEWER, "runtime agent slot: reviewer's review-claim"
    assert before.get("role") == "reviewer", "sticky role slot: reviewer's review-claim"

    # --- The reviewer rejects, exactly as the generated completion command
    # shapes it (workflow_executor.py's ``_completion_commands``): --to
    # planned --review-feedback-file <path> --agent <reviewer_identity>. ---
    feedback = repo / "review-feedback-1.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")
    rejected = _move(
        [
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _REVIEWER,
            "--no-auto-commit",
        ]
    )
    assert rejected.exit_code == 0, rejected.output

    after_rejection = _snapshot_wp_state(feature_dir)
    # Named-slot assertion (C-006): the transition ``actor`` slot legitimately
    # records who performed the rejection (the reviewer) ...
    assert _last_transition_actor(feature_dir) == _REVIEWER, "transition actor slot: reviewer performed the rejection"
    # ... but the runtime ``agent`` slot must be genuinely RELEASED — no live
    # claim survives an ordinary rejection (the #4673 precise live root: this
    # slot used to still read 'reviewer' here).
    assert not after_rejection.get("agent"), f"runtime agent slot not released after rejection: {after_rejection.get('agent')!r}"

    # --- The implementer claims the WP again in fix mode (a real
    # planned -> claimed transition, exactly as ``spec-kitty implement``
    # drives it). ---
    reclaimed = _move(
        [
            "WP01",
            "--to",
            "claimed",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _IMPLEMENTER,
            "--shell-pid",
            "333",
            "--no-auto-commit",
        ]
    )
    assert reclaimed.exit_code == 0, reclaimed.output

    after_reclaim = _snapshot_wp_state(feature_dir)
    # Runtime agent slot: the fix-mode claim recorded the NEW implementer.
    assert after_reclaim.get("agent") == _IMPLEMENTER, f"runtime agent slot did not record the fix-mode implementer: {after_reclaim.get('agent')!r}"
    # Sticky role slot: refreshed to implementer at the new claim (distinct
    # slot from ``agent`` — C-006 forbids asserting the same slot twice).
    assert after_reclaim.get("role") == "implementer", f"role slot: {after_reclaim.get('role')!r}"

    _move(["WP01", "--to", "in_progress", "--mission", _MISSION_SLUG, "--agent", _IMPLEMENTER, "--no-auto-commit"])

    # --- The ordinary resubmission: NO --force. This is the exact #4673
    # regression — pre-fix, this was refused with "Agent mismatch". ---
    resubmitted = _move(
        [
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _IMPLEMENTER,
            "--no-auto-commit",
        ]
    )
    assert resubmitted.exit_code == 0, resubmitted.output
    assert "Agent mismatch" not in resubmitted.output

    after_resubmit = _snapshot_wp_state(feature_dir)
    assert after_resubmit.get("agent") == _IMPLEMENTER
    assert _last_transition_actor(feature_dir) == _IMPLEMENTER


def test_genuinely_different_agent_is_still_refused_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-008: the ownership guard stays real. A genuinely different agent
    trying to submit the implementer's WP for review is still refused."""
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)
    feedback = repo / "review-feedback-1.md"
    feedback.write_text("## Issues\n\nFix this thing.\n", encoding="utf-8")

    _move(
        [
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(feedback),
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _REVIEWER,
            "--no-auto-commit",
        ]
    )
    _move(
        [
            "WP01",
            "--to",
            "claimed",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _IMPLEMENTER,
            "--shell-pid",
            "333",
            "--no-auto-commit",
        ]
    )
    _move(["WP01", "--to", "in_progress", "--mission", _MISSION_SLUG, "--agent", _IMPLEMENTER, "--no-auto-commit"])

    refused = _move(
        [
            "WP01",
            "--to",
            "for_review",
            "--mission",
            _MISSION_SLUG,
            "--agent",
            _OTHER_AGENT,
            "--no-auto-commit",
        ]
    )
    assert refused.exit_code != 0, refused.output
    assert "Agent mismatch" in refused.output

    # The genuine owner is unaffected by the refused attempt.
    state = _snapshot_wp_state(feature_dir)
    assert state.get("agent") == _IMPLEMENTER
