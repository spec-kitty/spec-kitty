"""#7582 — the rollback-to-``planned`` subtask reset is recorded and can be narrowed.

Mission ``next-lifecycle-integrity-01M77BWP`` (WP04, FR-011..FR-015, SC-004).
Operator ruling 2026-11-12: a recorded reset with narrowing.

* FR-011 — every ``move-task --to planned`` records the reset on the PLANNED
  transition event as ``policy_metadata.rollback_reset`` (scope, reset ids,
  previously completed ids, reason), merged beside ``lane_head`` / ``wp_window``.
* FR-012 — ``--reset-subtasks T002[,T003]`` resets only the named ids.
* FR-013 — a narrowing is refused before any write when an id is not on the
  roster, an id is ``skipped``, no ``--note``/``--reason`` is given, or the
  target lane is not ``planned``; each refusal has its own message.
* FR-014 — without the flag every non-skipped subtask resets (#2513), and the
  ``for_review`` subtask gate still blocks on a reset subtask.
* FR-015 — the human line names the scope and the reason; ``--json`` gains
  ``subtasks_reset_scope`` / ``subtasks_reset_reason``.

The harness is copied from ``test_tasks_move_task_cli_4899.py``
(``_build_in_review_repo`` / ``_move_task_cli``) and extended: a two-subtask
roster seeded done through the same ``InnerStateChanged`` annotation
``mark-status`` writes, a lane branch carrying an owned-file commit (so the
transition is stamped with ``lane_head`` and the ``for_review`` evidence gate
passes), and ``*extra_args`` on the CLI driver.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from kernel.clock import parse_iso, timedelta
from specify_cli.cli.commands.agent import tasks
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import Lane, StatusEvent, WPInnerStateDelta, emit_inner_state_changed, wp_snapshot_state
from specify_cli.status.models import SubtaskStatus, SubtaskValue
from specify_cli.status.store import read_events
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_SLUG = "001-reset-mission"
_WP_SLUG = "WP01-test-task"
_ROSTER = ("T001", "T002")
_FEEDBACK_BODY = "## Reviewer feedback\n\nT002 regressed: the parser drops trailing commas.\n"
_EVENTS_FILE = "status.events.jsonl"


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _manifest(planning_commit_sha: str | None = None) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=f"mission-{_SLUG}",
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-27T00:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


def _write_wp(wp_path: Path) -> None:
    write_frontmatter(
        wp_path,
        {
            "work_package_id": "WP01",
            "subtasks": list(_ROSTER),
            "title": "Test Task",
            "phase": "Phase 1",
            "lane": "planned",
            "dependencies": [],
            "owned_files": ["src/**"],
            "assignee": "",
            "agent": "claude",
            "shell_pid": "",
            "review_status": "none",
            "review_feedback": "",
            "history": [],
        },
        "# WP01 Prompt\n",
    )


def _seed_hops(feature_dir: Path, hops: tuple[tuple[Lane, Lane], ...], *, prefix: str) -> None:
    """Append lane hops stamped strictly after the latest event (wall-clock reducer)."""
    events = read_events(feature_dir)
    latest = parse_iso(events[-1].at.replace("Z", "+00:00")) if events else parse_iso("2026-09-27T12:00:00+00:00")
    for index, (from_lane, to_lane) in enumerate(hops, start=1):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"01{prefix}{str(index).zfill(24 - len(prefix))}",
                mission_slug=_SLUG,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=(latest + timedelta(seconds=index)).isoformat(),
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )


def _seed_subtasks(repo: Path, feature_dir: Path, states: dict[str, SubtaskValue]) -> None:
    """Seed subtask state through the annotation ``mark-status`` writes."""
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(subtasks=states),
        actor="claude",
        mission_slug=_SLUG,
        repo_root=repo,
    )


_TO_IN_REVIEW: tuple[tuple[Lane, Lane], ...] = (
    (Lane.PLANNED, Lane.CLAIMED),
    (Lane.CLAIMED, Lane.IN_PROGRESS),
    (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
    (Lane.FOR_REVIEW, Lane.IN_REVIEW),
)


def _build_repo(
    root: Path,
    *,
    subtasks: dict[str, SubtaskValue] | None = None,
    approved: bool = False,
) -> tuple[Path, Path, Path]:
    """Build a git repo with WP01 (roster T001/T002) driven into ``in_review`` (or ``approved``).

    Returns ``(repo_root, feature_dir, sub_artifact_dir)``. The lane branch exists and carries
    one owned-file commit after the recorded planning commit, so every transition is stamped
    with ``lane_head`` and a later ``for_review`` passes the implementation-evidence gate.
    """
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".kittify").mkdir()

    feature_dir = repo / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "mission_slug": _SLUG,
                "created_at": "2026-09-27T00:00:00Z",
                "friendly_name": _SLUG,
                "mission": "software-dev",
                "slug": _SLUG,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(feature_dir, _manifest())
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 First\n- [x] T002 Second\n", encoding="utf-8")
    _write_wp(tasks_dir / f"{_WP_SLUG}.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "planning")
    planning_sha = _git(repo, "rev-parse", "HEAD")

    lane_branch = lane_created_branch(_manifest(), "lane-a")
    _git(repo, "checkout", "-q", "-b", lane_branch)
    (repo / "src").mkdir()
    (repo / "src" / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "src/impl.py")
    _git(repo, "commit", "-m", "implement WP01")
    _git(repo, "checkout", "-q", "main")

    write_lanes_json(feature_dir, _manifest(planning_commit_sha=planning_sha))
    hops = _TO_IN_REVIEW + (((Lane.IN_REVIEW, Lane.APPROVED),) if approved else ())
    _seed_hops(feature_dir, hops, prefix="SEED")
    _seed_subtasks(repo, feature_dir, subtasks if subtasks is not None else dict.fromkeys(_ROSTER, Lane.DONE))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed in-review fixture")
    return repo, feature_dir, tasks_dir / _WP_SLUG


def _move_task_cli(*, to: str, extra_args: tuple[str, ...] = (), agent: str = "reviewer-rita", auto_commit: bool = False) -> Any:
    """Invoke the REAL ``move-task`` CLI (cwd must be the repo) with optional extra args.

    ``auto_commit`` leaves the CLI's default auto-commit on, so an accepted move commits and moves
    HEAD: a refusal cell uses it to make its "HEAD unchanged" check discriminating. The fixture
    sits on protected ``main``, so the auto-commit run carries the operator override.
    """
    commit_flag = () if auto_commit else ("--no-auto-commit",)
    env = {"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"} if auto_commit else None
    args = ["move-task", "WP01", "--to", to, "--mission", _SLUG, "--agent", agent, *commit_flag, *extra_args]
    return CliRunner().invoke(tasks.app, args, env=env)


def _feedback(repo: Path) -> str:
    path = repo / "feedback.md"
    path.write_text(_FEEDBACK_BODY, encoding="utf-8")
    return str(path)


def _flat(output: str) -> str:
    """Collapse Rich line wrapping so a message can be matched as one string."""
    return " ".join(output.split())


def _planned_event(feature_dir: Path) -> StatusEvent:
    planned = [event for event in read_events(feature_dir) if event.wp_id == "WP01" and event.to_lane == Lane.PLANNED]
    assert planned, "no PLANNED transition was recorded"
    return planned[-1]


def _subtask_lanes(feature_dir: Path) -> dict[str, str]:
    state = wp_snapshot_state(feature_dir, "WP01") or {}
    return {str(tid): str(value) for tid, value in (state.get("subtasks") or {}).items()}


def _write_surface(repo: Path, feature_dir: Path, sub_artifact_dir: Path) -> tuple[str, bytes, tuple[str, ...], str]:
    """HEAD, the event log bytes, the review-cycle files and the git status (the refusal's no-write witness)."""
    cycles = tuple(sorted(p.name for p in sub_artifact_dir.glob("review-cycle-*.md"))) if sub_artifact_dir.exists() else ()
    return (
        _git(repo, "rev-parse", "HEAD"),
        (feature_dir / _EVENTS_FILE).read_bytes(),
        cycles,
        _git(repo, "status", "--porcelain", "--untracked-files=all"),
    )


def _narrowed_args(repo: Path, *, ids: str = "T002", note: str | None = "T002 regressed") -> tuple[str, ...]:
    args: tuple[str, ...] = ("--review-feedback-file", _feedback(repo), "--reset-subtasks", ids)
    return args + (("--note", note) if note is not None else ())


def _assert_refused_before_any_write(
    repo: Path,
    feature_dir: Path,
    sub_artifact_dir: Path,
    *,
    to: str,
    extra_args: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    before = _write_surface(repo, feature_dir, sub_artifact_dir)
    # Auto-commit stays on: an accepted move would commit (see the positive control below), so
    # an unchanged HEAD is evidence of the refusal, not of ``--no-auto-commit``.
    result = _move_task_cli(to=to, extra_args=extra_args, auto_commit=True)
    output = _flat(result.output)
    assert result.exit_code != 0, f"the narrowing must be refused, got exit 0:\n{result.output}"
    for fragment in expected:
        assert fragment in output, f"refusal must say {fragment!r}; got:\n{result.output}"
    # The feedback file the args wrote is the only new path; nothing else may move.
    after = _write_surface(repo, feature_dir, sub_artifact_dir)
    assert after[0] == before[0], "HEAD moved on a refused move"
    assert after[1] == before[1], "the event log changed on a refused move"
    assert after[2] == before[2] == (), "a review-cycle record was written on a refused move"
    assert after[3] == before[3], f"the working tree changed on a refused move:\n{after[3]}"


# --------------------------------------------------------------------------- #
# FR-011 / FR-014 — the full reset is recorded on the PLANNED transition
# --------------------------------------------------------------------------- #


def test_full_rejection_records_full_reset_beside_lane_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)

    result = _move_task_cli(to="planned", extra_args=("--review-feedback-file", _feedback(repo)))

    assert result.exit_code == 0, result.output
    assert _subtask_lanes(feature_dir) == {"T001": "planned", "T002": "planned"}
    event = _planned_event(feature_dir)
    metadata = event.policy_metadata or {}
    assert event.review_ref is not None and event.review_ref.startswith("review-cycle://")
    assert metadata.get("rollback_reset") == {
        "scope": "full",
        "reset": ["T001", "T002"],
        "previously_completed": ["T001", "T002"],
        "reason": f"rollback to planned: in_review -> planned ({event.review_ref})",
    }
    # Positive control: the record merges with the pipeline's stamp, never replaces it.
    assert metadata.get("lane_head"), f"lane_head was lost from the PLANNED event: {metadata}"
    assert "full reset: rollback to planned: in_review -> planned" in _flat(result.output)


# --------------------------------------------------------------------------- #
# FR-012 — a narrowed reset resets only the named ids
# --------------------------------------------------------------------------- #


def test_narrowed_rejection_resets_only_named_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)

    result = _move_task_cli(to="planned", extra_args=_narrowed_args(repo))

    assert result.exit_code == 0, result.output
    assert _subtask_lanes(feature_dir) == {"T001": "done", "T002": "planned"}
    metadata = _planned_event(feature_dir).policy_metadata or {}
    assert metadata.get("rollback_reset") == {
        "scope": "narrowed",
        "reset": ["T002"],
        "previously_completed": ["T002"],
        "reason": "T002 regressed",
    }
    assert metadata.get("lane_head")
    assert "↺ Reset 1 of 2 subtask(s) to planned (narrowed: T002 regressed)" in _flat(result.output)


# --------------------------------------------------------------------------- #
# FR-013 — narrowing refusals, each before any write and each with its own message
# --------------------------------------------------------------------------- #


def test_accepted_narrowing_with_auto_commit_moves_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control for the refusal cells: the same move, accepted, commits and moves HEAD."""
    repo, feature_dir, sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    args = _narrowed_args(repo)
    before = _write_surface(repo, feature_dir, sub)

    result = _move_task_cli(to="planned", extra_args=args, auto_commit=True)

    assert result.exit_code == 0, result.output
    assert _write_surface(repo, feature_dir, sub)[0] != before[0], "an accepted move with auto-commit must move HEAD"


def test_unknown_id_is_refused_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    _assert_refused_before_any_write(
        repo,
        feature_dir,
        sub,
        to="planned",
        extra_args=_narrowed_args(repo, ids="T009"),
        expected=("T009", "not on WP01's subtask roster"),
    )


def test_missing_reason_is_refused_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    _assert_refused_before_any_write(
        repo,
        feature_dir,
        sub,
        to="planned",
        extra_args=_narrowed_args(repo, note=None),
        expected=("--reset-subtasks requires --note/--reason",),
    )


def test_wrong_target_lane_is_refused_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    _assert_refused_before_any_write(
        repo,
        feature_dir,
        sub,
        to="for_review",
        extra_args=("--reset-subtasks", "T001", "--note", "x"),
        expected=("--reset-subtasks applies only to --to planned", "for_review"),
    )


@pytest.mark.parametrize("ids", ["[/x]", "[bold]T1"])
def test_markup_in_reset_ids_is_echoed_literally_and_refused(ids: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Operator input is escaped before Rich renders it: a stray closing tag never crashes the refusal."""
    repo, feature_dir, sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    _assert_refused_before_any_write(
        repo,
        feature_dir,
        sub,
        to="planned",
        extra_args=_narrowed_args(repo, ids=ids),
        expected=(f"{ids} is not on WP01's subtask roster", "RESET_SUBTASKS_UNKNOWN_IDS"),
    )


def test_skipped_id_is_refused_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, sub = _build_repo(tmp_path, subtasks={"T001": Lane.DONE, "T002": SubtaskStatus.SKIPPED})
    monkeypatch.chdir(repo)
    _assert_refused_before_any_write(
        repo,
        feature_dir,
        sub,
        to="planned",
        extra_args=_narrowed_args(repo),
        expected=("T002", "is skipped"),
    )


# --------------------------------------------------------------------------- #
# FR-014 — the for_review subtask gate still blocks on a reset subtask
# --------------------------------------------------------------------------- #


def test_for_review_gate_blocks_on_narrowed_reset_subtask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)
    assert _move_task_cli(to="planned", extra_args=_narrowed_args(repo)).exit_code == 0

    _seed_hops(feature_dir, ((Lane.PLANNED, Lane.CLAIMED), (Lane.CLAIMED, Lane.IN_PROGRESS)), prefix="RECLAIM")
    blocked = _move_task_cli(to="for_review", agent="claude")

    assert blocked.exit_code != 0, blocked.output
    blocked_output = _flat(blocked.output)
    assert "unchecked subtasks" in blocked_output, blocked.output
    assert "T002" in blocked_output
    assert "[ ] T001" not in blocked_output, "the narrowed reset kept T001 done; the gate must not name it"

    _seed_subtasks(repo, feature_dir, {"T002": Lane.DONE})
    retried = _move_task_cli(to="for_review", agent="claude")

    retried_output = _flat(retried.output)
    assert "unchecked subtasks" not in retried_output, retried.output
    assert "[ ] T002" not in retried_output


# --------------------------------------------------------------------------- #
# --note / --reason precedence, reopen, JSON, skipped exclusion
# --------------------------------------------------------------------------- #


def test_last_of_note_and_reason_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)

    result = _move_task_cli(
        to="planned",
        extra_args=("--review-feedback-file", _feedback(repo), "--reset-subtasks", "T002", "--note", "a", "--reason", "b"),
    )

    assert result.exit_code == 0, result.output
    record = (_planned_event(feature_dir).policy_metadata or {}).get("rollback_reset") or {}
    assert record.get("reason") == "b"


def test_reopen_from_approved_records_full_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path, approved=True)
    monkeypatch.chdir(repo)

    result = _move_task_cli(
        to="planned",
        extra_args=("--force", "--review-feedback-file", _feedback(repo), "--note", "reopen: regression found"),
    )

    assert result.exit_code == 0, result.output
    assert _subtask_lanes(feature_dir) == {"T001": "planned", "T002": "planned"}
    event = _planned_event(feature_dir)
    assert (event.policy_metadata or {}).get("rollback_reset") == {
        "scope": "full",
        "reset": ["T001", "T002"],
        "previously_completed": ["T001", "T002"],
        "reason": "reopen: regression found",
    }
    assert (event.policy_metadata or {}).get("lane_head")


def test_json_output_carries_scope_and_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _feature_dir, _sub = _build_repo(tmp_path)
    monkeypatch.chdir(repo)

    result = _move_task_cli(to="planned", extra_args=(*_narrowed_args(repo), "--json"))

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["subtasks_reset_scope"] == "narrowed"
    assert payload["subtasks_reset_reason"] == "T002 regressed"
    # The existing #3578 keys are unchanged.
    assert payload["subtasks_reset_count"] == 1
    assert payload["subtasks_reset_ids"] == ["T002"]
    assert payload["subtasks_previously_completed"] == ["T002"]
    assert payload["subtasks_never_completed"] == []


def test_skipped_subtask_is_never_in_a_full_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir, _sub = _build_repo(tmp_path, subtasks={"T001": Lane.DONE, "T002": SubtaskStatus.SKIPPED})
    monkeypatch.chdir(repo)

    result = _move_task_cli(to="planned", extra_args=("--review-feedback-file", _feedback(repo)))

    assert result.exit_code == 0, result.output
    assert _subtask_lanes(feature_dir) == {"T001": "planned", "T002": "skipped"}
    record = (_planned_event(feature_dir).policy_metadata or {}).get("rollback_reset") or {}
    assert record.get("scope") == "full"
    assert record.get("reset") == ["T001"]
    assert record.get("previously_completed") == ["T001"]


# --------------------------------------------------------------------------- #
# Cutover pin — the new key counts as runtime evidence (harmless, pinned)
# --------------------------------------------------------------------------- #


def test_rollback_reset_counts_as_runtime_evidence_for_cutover() -> None:
    """A PLANNED event carrying ``rollback_reset`` beside ``lane_head`` counts as runtime evidence.

    ``cutover_eligibility._policy_metadata_carries_runtime_evidence`` treats every key other
    than the provenance stamps (``lane_head``, ``wp_window``) as runtime evidence, so the new
    record makes the PLANNED event count. That is harmless: a WP can only be rolled back to
    ``planned`` after it left ``planned``, and that move (a claim) already carried policy
    metadata that counts, so the WP's eligibility verdict cannot change. Pinned here so a
    change to either side is a deliberate decision (research R-6).
    """
    from specify_cli.status.cutover_eligibility import _policy_metadata_carries_runtime_evidence

    record = {"scope": "full", "reset": ["T001"], "previously_completed": ["T001"], "reason": "x"}
    assert _policy_metadata_carries_runtime_evidence({"rollback_reset": record, "lane_head": "abc123"}) is True
    # Control: the provenance stamp alone does not count.
    assert _policy_metadata_carries_runtime_evidence({"lane_head": "abc123"}) is False
