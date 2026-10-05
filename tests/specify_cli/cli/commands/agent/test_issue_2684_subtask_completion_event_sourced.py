"""Issue #2684 — subtask completion must be event-sourced, not gated on
``tasks.md`` checkbox bytes.

Formerly a red-first ``@pytest.mark.regression`` reproduction; relocated
here and un-marked (landing fold: make ``@pytest.mark.regression`` mean
exactly one thing) once the fix landed and this test started passing.
#2684 is fixed — this is now a permanent guard, not a red-first pin.

#2684 evicts runtime-mutable WP state out of ``tasks/WP##.md`` / ``tasks.md``
and into the append-only event log; the catfooding comment's **invariant (1)**
("Core — this ticket") is that **subtask completion is markdown-gated, not
event-sourced.** The eviction end-state is that ``tasks.md`` holds only *static
design intent* — the subtask checkbox is NOT the completion authority.

Root cause on this build (invariant 1)
--------------------------------------
The ``move-task <WP> --to for_review`` review gate refuses on unchecked
subtasks whose source of truth is ``tasks.md`` markdown bytes, never the log:

* ``tasks_transition_core.py:384`` ``_guard_subtasks`` refuses the
  ``for_review``/``approved``/``done`` transition whenever
  ``req.unchecked_subtasks`` is non-empty.
* ``tasks_move_task.py:507`` populates ``unchecked_subtasks`` from
  ``_tasks._check_unchecked_subtasks(...)``.
* ``tasks_shared.py:412`` ``_check_unchecked_subtasks`` reads
  ``tasks.md`` and returns the unchecked ``- [ ] T### …`` rows via
  ``core.subtask_rows.iter_wp_section_subtask_rows`` (pattern
  ``subtask_rows.py:39`` ``UNCHECKED_SUBTASK_ROW = ^-\\s*\\[\\s*\\]\\s*(T\\d{3,})``).
  It consults the ``tasks.md`` byte only — never ``status.events.jsonl``,
  the reduced snapshot, or the emitted ``HistoryAdded`` completion record.

So the subtask-completion authority is the markdown checkbox; the gate reads
markdown, never the event log.

Does a canonical event-log path for subtask completion exist?
-------------------------------------------------------------
Refuted-as-*gate-source*, confirmed-as-*record*. ``agent tasks mark-status
T00N --status done`` (``tasks_mark_status.py::_ms_emit_history``) DOES record
completion into the canonical append-only event system — it emits a
``HistoryAdded`` event ("Subtask(s) T001, T002, T003 marked as done") via the
sync emitter — but it also rewrites the ``tasks.md`` checkbox, and the review
gate reads *only* that markdown byte. There is no structured, gate-queried
subtask-completion event that ``_guard_subtasks`` consults. This confirms the
catfooding comment: completion is markdown-gated, not event-sourced.

Encoding used (fallback, per the ticket's AC-1/AC-3 framing)
------------------------------------------------------------
No canonical event path writes subtask completion *without* also writing the
``tasks.md`` checkbox, so we model the #2684 eviction end-state directly:

1. drive ``agent tasks mark-status T001 T002 T003 --status done`` through the
   REAL CLI — this records the completion in the append-only event log
   (``HistoryAdded``) AND (today) flips the ``tasks.md`` checkbox rows to
   ``- [x]``;
2. **reset the ``tasks.md`` checkbox rows back to ``- [ ] T00N``** — modelling
   the eviction end-state where ``tasks.md`` is *static/derived* and is NOT the
   subtask-completion authority; the append-only log RETAINS the completion
   record.

State under test: **the log says the subtasks are done, the ``tasks.md``
checkboxes say unchecked.** Invariant (1) demands the ``for_review`` transition
be ALLOWED (the gate must honor the log). This was RED before the fix (the
gate read markdown -> "unchecked subtasks"); #2684 is now fixed and the gate
honors the log, so this test is GREEN and stays as a permanent guard.

Harness: mirrors ``tests/regression/test_issue_2647_move_task_lane_worktree_cwd.py``
— a real ``create_mission_core(SINGLE_BRANCH)`` mission, WP01 claimed to
``in_progress`` through the real ``agent action implement`` entry point, and the
transition driven through the real ``agent tasks move-task`` Typer app. Marker
set is the exact ``test_issue_2508.py`` trio.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from specify_cli.analysis_report import write_analysis_report
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.status.bootstrap import bootstrap_canonical_state
from tests._factories import provision_test_charter
from tests.specify_cli.charter_preflight._fixtures import (
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_graph,
    seed_manifest,
    write_metadata,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


#: The three canonical subtasks WP01 carries in ``tasks.md``.
_SUBTASKS = ("T001", "T002", "T003")

#: Unchecked ``tasks.md`` body — the genuinely-incomplete state (control).
_TASKS_MD_UNCHECKED = (
    "# Tasks\n\n"
    "## WP01 - repro\n"
    "- [ ] T001 alpha\n"
    "- [ ] T002 beta\n"
    "- [ ] T003 gamma\n"
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _build_single_branch_mission_with_in_progress_wp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, Path]:
    """Materialise a single_branch mission with WP01 claimed to ``in_progress``.

    WP01's ``tasks.md`` section carries three UNCHECKED canonical subtask rows
    (``T001..T003``). A lane deliverable is committed so the for_review
    readiness guard is satisfied and ``_guard_subtasks`` is the discriminator.

    Returns ``(repo_root, mission_slug, feature_dir)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "issue-2684@example.invalid")
    _git(repo, "config", "user.name", "Issue 2684 Regression")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    # WP04 (C-A1): the provisioned charter is the sole mission-type activation
    # authority, so `create_mission_core`'s require-boundary fails closed
    # without a non-empty `mission_type_activations` list. Seed the full
    # default activation set via the production provisioner (same shared
    # helper used across the mission-creation test harness) rather than a
    # partial, hand-rolled `mission_type_activations`-only config.yaml.
    provision_test_charter(repo)

    # Fully-fresh charter so `agent action implement`'s preflight passes.
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo)
    seed_charter_yaml(repo)
    seed_manifest(repo, built_in_only=False)
    seed_graph(repo)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    # `main` is protected; this fixture's mission runs on a dedicated,
    # non-protected target branch checked out in the primary checkout.
    _git(repo, "checkout", "-b", "feature-work")

    # The worktree guard inspects the REAL process cwd (pytest may run inside a
    # spec-kitty lane worktree), so the create opts out with
    # `allow_worktree_context=True`; every resolver runs for real against `repo`.
    result = create_mission_core(
        repo,
        "issue-2684-repro",
        allow_worktree_context=True,
        friendly_name="Issue 2684 Regression",
        purpose_tldr="reproduce the markdown-gated subtask-completion bug",
        purpose_context=(
            "Drive the #2684 invariant-1 reproduction end to end so the "
            "review gate's subtask-completion source of truth stays proven."
        ),
        # #5100 WP05 (T024 blast radius): this fixture hand-writes a
        # ``lane-a`` CODE lane below and asserts ``.worktrees/*-lane-a``
        # -- exactly the manifest shape ``compute_lanes(topology=
        # single_branch)`` (WP05, IC-03) no longer allows: a mission
        # explicitly stamped ``single_branch`` now fails closed
        # (``SINGLE_BRANCH_CODE_LANES_UNMIGRATED``) against a hand-written
        # code-lane manifest, both at ``implement`` and at
        # ``finalize-tasks`` (``assert_topology_matches_manifest``,
        # ``mission_runtime/context.py``). This fixture's own concern
        # (#2684 -- subtask-completion event-sourcing) is orthogonal to
        # topology; a genuine ``lanes`` mission exercises the identical
        # ordinary code-lane worktree path this test needs, without
        # tripping the new single_branch guard.
        topology=MissionTopology.LANES,
    )
    feature_dir = result.feature_dir
    mission_slug = result.mission_slug
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("topology") == "lanes"
    assert meta.get("coordination_branch") is None, "a lanes (non-coord) mission is coordination-less"

    # #2684 target state requires the phase-1 cutover ON; the foundation
    # convention (status/emit.py::_phase1_snapshot_authority_active) is flag ON ->
    # snapshot-sourced completion, flag OFF -> legacy tasks.md (the pre-cutover
    # default). This out-of-map edit flips this pinned test onto that flag so
    # the invariant-1 assertion exercises the event-sourced reader, not the
    # untouched (flag OFF) legacy path.
    meta["status_phase"] = "1"
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n- **FR-001**: repro.\n", encoding="utf-8"
    )
    (feature_dir / "plan.md").write_text(
        "# Plan\n\n**Language/Version**: Python 3.11\n", encoding="utf-8"
    )
    # WP01 carries three UNCHECKED canonical subtask rows.
    (feature_dir / "tasks.md").write_text(_TASKS_MD_UNCHECKED, encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    # #2816 IC-10: the guard's subtask roster is the authored frontmatter
    # ``subtasks:`` list (static design intent) and completion is the reduced
    # event-log snapshot slot. WP01 authors its three canonical subtasks here so
    # the rerouted guard has a roster to block on (checkbox bytes are noise).
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Issue 2684 repro WP\n"
        "execution_mode: code_change\n"
        "agent: claude\n"
        "subtasks:\n"
        "- T001\n"
        "- T002\n"
        "- T003\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": mission_slug,
                "mission_id": meta["mission_id"],
                "mission_branch": f"kitty/mission-{mission_slug}",
                "target_branch": result.target_branch,
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": ["src/**"],
                        "predicted_surfaces": ["core"],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-07-08T00:00:00+00:00",
                "computed_from": "issue-2684-repro",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed mission artifacts")

    # Bootstrap canonical status (the finalize-tasks seed step) so WP01 has its
    # initial `planned` event before the claim.
    monkeypatch.chdir(repo)
    bootstrap_canonical_state(
        feature_dir, mission_slug, capability=GuardCapability.TEST_MODE
    )
    _git(repo, "add", "-A")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "bootstrap canonical status"],
        capture_output=True,
    )

    # Claim WP01 through the REAL entry point: creates the lane worktree and
    # records `planned -> claimed -> in_progress` on the target branch.
    implement = runner.invoke(
        root_app,
        ["agent", "action", "implement", "WP01", "--mission", mission_slug, "--agent", "claude"],
    )
    assert implement.exit_code == 0, implement.output

    lane_worktree = repo / ".worktrees" / f"{mission_slug}-lane-a"
    assert lane_worktree.exists(), "lane worktree was not materialised by implement"

    # A real implementer commits a deliverable on the lane branch, so the
    # for_review readiness guard passes and `_guard_subtasks` is the
    # discriminator (not a missing-deliverable refusal).
    (lane_worktree / "src").mkdir(exist_ok=True)
    (lane_worktree / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(lane_worktree, "add", ".")
    _git(lane_worktree, "commit", "-m", "feat(WP01): implement deliverable")

    return repo, mission_slug, feature_dir


def _invoke_move_to_for_review(mission_slug: str) -> object:
    """Drive ``agent tasks move-task WP01 --to for_review`` through the real app.

    ``--skip-pre-review-gate`` bypasses ONLY the pre-review pytest gate
    (``_mt_pre_review_gate_skip_reason``); it does NOT bypass ``_guard_subtasks``
    (a member of ``_GUARDS`` in ``decide_transition``), so the subtask guard
    remains the discriminator under test.
    """
    return runner.invoke(
        root_app,
        [
            "agent",
            "tasks",
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--mission",
            mission_slug,
            "--no-auto-commit",
            "--skip-pre-review-gate",
            "--json",
        ],
    )


def _new_lane(result: object) -> str | None:
    """Extract ``new_lane`` from a ``--json`` move-task envelope, if present."""
    text = (result.stdout or "").strip()  # type: ignore[attr-defined]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    lane = payload.get("new_lane")
    return str(lane) if lane is not None else None


def _record_subtasks_done_in_log_then_evict_markdown(
    feature_dir: Path, mission_slug: str
) -> None:
    """Record subtask completion in the append-only log, then reset the markdown.

    Models the #2684 eviction end-state (AC-1/AC-3): the append-only event log
    records the subtasks as complete, while the ``tasks.md`` checkboxes remain
    unchecked (static design intent, NOT the completion authority).

    Step 1 drives the REAL ``agent tasks mark-status ... --status done`` CLI,
    which emits the canonical ``HistoryAdded`` completion record into the
    append-only event system (``_ms_emit_history``) AND — on today's build —
    flips the ``tasks.md`` checkboxes. Step 2 resets those checkbox bytes back
    to ``- [ ]``, leaving the log's completion record intact.
    """
    mark = runner.invoke(
        root_app,
        [
            "agent",
            "tasks",
            "mark-status",
            *_SUBTASKS,
            "--status",
            "done",
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )
    assert mark.exit_code == 0, mark.output

    tasks_md = feature_dir / "tasks.md"
    # Evict the runtime-mutable checkbox state: reset every checked canonical
    # subtask row back to unchecked. The append-only log retains completion.
    evicted = re.sub(
        r"^-\s*\[[xX]\]\s*(T\d{3,})",
        r"- [ ] \1",
        tasks_md.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    tasks_md.write_text(evicted, encoding="utf-8")

    # Sanity: the eviction end-state is genuinely "log done, markdown unchecked".
    assert tasks_md.read_text(encoding="utf-8") == _TASKS_MD_UNCHECKED


def test_move_to_for_review_honors_log_recorded_subtask_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2684 invariant (1): subtask completion recorded in the canonical
    append-only log MUST allow ``move-task WP01 --to for_review`` WITHOUT relying
    on ``tasks.md`` checkbox bytes.

    Was RED before the fix: ``_guard_subtasks`` sourced ``unchecked_subtasks``
    from ``tasks.md`` markdown (``tasks_shared.py:412``), so with the checkboxes
    evicted back to ``- [ ]`` the gate refused with
    ``Cannot move WP01 to for_review - unchecked subtasks`` even though the log
    recorded T001..T003 as done. #2684 is now fixed: the gate's source of
    truth is the event log, not the markdown byte, and this is a permanent
    guard against the defect recurring.
    """
    repo, mission_slug, feature_dir = _build_single_branch_mission_with_in_progress_wp(
        tmp_path, monkeypatch
    )

    # Log says done; markdown checkboxes evicted back to unchecked.
    _record_subtasks_done_in_log_then_evict_markdown(feature_dir, mission_slug)

    result = _invoke_move_to_for_review(mission_slug)

    # THE INVARIANT: the transition must be ALLOWED because the log records the
    # subtasks as complete. On today's markdown-gated build this refuses — the
    # RED-for-the-right-reason assertion surfaces the exact refusal.
    assert "unchecked subtasks" not in (result.output or ""), (
        "#2684 invariant (1) violated: move-task --to for_review refused on "
        "unchecked tasks.md checkbox bytes even though subtask completion is "
        "recorded in the append-only log. The gate must honor the log, not the "
        f"markdown byte.\n{result.output}"
    )
    assert result.exit_code == 0, result.output
    assert _new_lane(result) == "for_review", result.output


def test_control_move_to_for_review_refused_when_subtasks_genuinely_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control (must PASS now): a WP whose subtasks are genuinely incomplete —
    no completion recorded in the log AND unchecked in ``tasks.md`` — is
    correctly REFUSED ``move-task --to for_review`` with the unchecked-subtasks
    error.

    This proves the primary test asserts "the gate honors the log", not "the
    gate always allows": when NOTHING records completion, the refusal is
    correct. Guards against a vacuous primary that would pass even if the gate
    were simply removed.
    """
    repo, mission_slug, _feature_dir = _build_single_branch_mission_with_in_progress_wp(
        tmp_path, monkeypatch
    )

    # No mark-status; no log completion record; tasks.md checkboxes unchecked.
    result = _invoke_move_to_for_review(mission_slug)

    assert result.exit_code != 0, result.output
    assert "unchecked subtasks" in (result.output or ""), result.output
    assert _new_lane(result) != "for_review", result.output
