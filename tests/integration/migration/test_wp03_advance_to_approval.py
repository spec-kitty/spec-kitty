"""WP03 review rework — BLOCKER 1: recovered mission is CLI-advanceable.

Mission ``canonical-state-recovery-01M2ZE3D`` / WP03.

``spec.md``'s own acceptance test (the "Independent Test" for this mission):
"Reproduce the #4758 wedge (finalize-tasks then move-task, no ``lanes.json``),
run the repair command, then successfully advance the WP through approval --
end to end, CLI only." The WP03 review (reviewer-renata, commit
``66cfc08af3``) REJECTED the work package because no test exercised this
claim through the real ``move-task`` CLI -- only the internal
``lanes.json``-shape assertions in
``tests/unit/migration/test_mission_state_lanes_rebuild.py`` were covered.
This module closes that gap.

In the now-fixed codebase, ``finalize-tasks`` itself writes ``lanes.json``
for owned WPs (WP01 of this same mission), so the #4758 wedge can no longer
be produced through the documented command sequence -- it is reproduced
directly at the canonical event-log layer instead, exactly mirroring
``test_mission_state_lanes_rebuild.py``'s ``_seed_wedged_events``: the event
log is advanced past ``planned`` while ``lanes.json`` stays absent, modeling
the historical bug/interruption move-task itself could never produce through
its own guarded path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.migration.mission_state import LANES_REBUILT_ACTION, repair_repo
from specify_cli.status.bootstrap import bootstrap_canonical_state
from specify_cli.status.emit import emit_status_transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
_MISSION_SLUG = "073-wp03-advance"
_AGENT = "codex"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def _disable_move_task_sync_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic run + the one sanctioned protected-branch waiver.

    Mirrors ``tests/tasks/test_move_task_git_validation_unit.py``: this
    fixture repo stays on ``main`` throughout (no separate mission branch is
    checked out), which move-task's protected-branch pre-check would
    otherwise refuse before ever reaching the canonical-status logic under
    test here. ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` is the one
    documented operator escape hatch for exactly this (``core/commit_guard.py``).
    """
    import specify_cli.status.emit as status_emit

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


def _build_wedged_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real, committed git repo carrying the #4758 wedge.

    WP01's canonical event log is past ``planned`` (``claimed``) while
    ``lanes.json`` is absent from disk -- the exact shape
    ``specify_cli.lanes.persistence.is_execution_wedged`` detects and this
    WP's ``doctor mission-state --fix`` repairs.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "wp03-e2e@spec-kitty.test")
    _git(repo, "config", "user.name", "wp03 e2e")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("agents:\n  available: [codex]\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed repo")

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_type": "software-dev",
                "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "mission_slug": _MISSION_SLUG,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    (repo / "src" / "wp01").mkdir(parents=True)
    (repo / "src" / "wp01" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "execution_mode: code_change\n"
        "owned_files:\n  - src/wp01/**\n"
        "authoritative_surface: src/wp01/\n"
        "subtasks: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed mission (pre-wedge)")

    # Reproduce the #4758 wedge directly at the canonical event-log layer --
    # bypassing move-task, which would itself refuse without lanes.json (the
    # wedge is, by definition, a state move-task cannot produce through its
    # own guarded path; it models an earlier bug/interruption).
    bootstrap_canonical_state(feature_dir, _MISSION_SLUG, repo_root=repo)
    emit_status_transition(
        feature_dir,
        wp_id="WP01",
        to_lane="claimed",
        actor=_AGENT,
        mission_slug=_MISSION_SLUG,
        repo_root=repo,
        ensure_sync_daemon=False,
        fan_out=False,
    )
    assert read_lanes_json(feature_dir) is None, "fixture precondition: wedge has no lanes.json"

    # Commit the wedge state (mirrors finalize-tasks committing canonical
    # status on the historical, buggy tree): repair_repo's git-safe guard
    # refuses a dirty mission dir, and a real committed wedge is what the
    # documented recovery path actually repairs in production.
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed #4758 wedge: WP01 claimed, no lanes.json")

    return repo, feature_dir


def test_repaired_wedge_advances_to_approval_on_default_lane_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """spec.md Independent Test: repair, then advance to approval, CLI only.

    BLOCKER 1 (WP03 review rework): no prior test drove the "advanceable to
    approval" claim through the real ``move-task`` CLI on the default
    (non-``--owned-checkout``) lane path. GREEN here proves
    FR-003/NFR-001/SC-002/User-Story-1/T013 for the mainstream path: after
    ``doctor mission-state --fix``, the recovered mission's WP claims,
    progresses, and reaches ``approved`` without any transition refusing.
    """
    repo, feature_dir = _build_wedged_repo(tmp_path)

    report = repair_repo(repo, mission=_MISSION_SLUG)
    result = next(m for m in report.missions if m.mission_slug == _MISSION_SLUG)
    assert result.status != "error", result.validation_errors
    assert LANES_REBUILT_ACTION in result.meta_actions

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None, "#4758 regression: mission is still wedged after 'doctor mission-state --fix'."
    # BLOCKER 2's companion fix: the rebuild now records a captured
    # target-branch tip rather than a bare ``None``.
    assert lanes.planning_commit_sha is not None

    monkeypatch.chdir(repo)

    def _move(to: str, *extra: str) -> None:
        invocation = runner.invoke(
            tasks_app,
            ["move-task", "WP01", "--to", to, "--agent", _AGENT, "--mission", _MISSION_SLUG, "--json", *extra],
        )
        assert invocation.exit_code == 0, invocation.output

    # WP01 is already "claimed" (the wedge) -- resume to in_progress, then
    # drive the rest of the chain through to approval. No step should refuse.
    _move("doing")
    _move("for_review")
    _move("in_review", "--reviewer", "reviewer")
    _move("approved", "--reviewer", "reviewer", "--approval-ref", "local-review")

    events = [json.loads(line) for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    transitions = [row["to_lane"] for row in events if row.get("wp_id") == "WP01" and "to_lane" in row]
    assert transitions == ["planned", "claimed", "in_progress", "for_review", "in_review", "approved"]

    final_state = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))["work_packages"]["WP01"]
    assert final_state["lane"] == "approved"


# ---------------------------------------------------------------------------
# BLOCKER 2 companion: prove the captured-sha fix is what unblocks
# ``--owned-checkout`` review directly at the named consumer,
# ``tasks_move_task.py::_mt_resolve_owned_review_base`` -- the ONE consumer
# that hard-raises ``OWNED_REVIEW_BASE_INVALID`` on a ``None`` recorded
# ``planning_commit_sha`` (the review's exact citation). Reproducing the
# owned-checkout CLI chain end-to-end additionally requires threading the
# write-routing owned-checkout identity through ``bootstrap_canonical_state``/
# ``repair_repo`` (a primary-partition-anchored operation --
# ``enforce_primary_write_ownership`` refuses a direct write from an owned
# lane checkout); that is a materially bigger, orthogonal surface than this
# fix. This test instead calls the exact function the review named, against
# a REAL rebuilt ``lanes.json`` (via ``repair_repo`` on the same wedge
# fixture as the default-lane test above), proving both the pre-fix refusal
# and the post-fix success -- the precise BLOCKER 2 contract -- without
# needing the full multi-worktree owned-checkout harness.
# ---------------------------------------------------------------------------


def test_owned_review_base_refuses_on_none_and_succeeds_on_captured_sha(tmp_path: Path) -> None:
    """BLOCKER 2: ``_mt_resolve_owned_review_base`` refuses on ``None``, not on
    a captured target-branch-tip sha.

    Mirrors ``tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py``'s
    own pattern of driving ``tasks_move_task`` internals with a lightweight
    stand-in for ``_MoveTaskState`` (that test's
    ``test_owned_gate_baseline_reads_selected_mission_directory`` does the
    same for ``_mt_resolve_gate_baseline``) -- ``_mt_resolve_owned_review_base``
    only reads ``st.owned.root`` and ``st.feature_dir``.
    """
    from types import SimpleNamespace

    from mission_runtime import ActionContextError

    from specify_cli.cli.commands.agent.tasks_move_task import (
        _mt_resolve_owned_review_base,
    )
    from specify_cli.lanes.persistence import write_lanes_json

    repo, feature_dir = _build_wedged_repo(tmp_path)
    report = repair_repo(repo, mission=_MISSION_SLUG)
    result = next(m for m in report.missions if m.mission_slug == _MISSION_SLUG)
    assert result.status != "error", result.validation_errors

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None
    assert lanes.planning_commit_sha is not None, "BLOCKER 2: rebuild must capture the target-branch tip, not None"

    # A real implementation commit ahead of the captured base, so the
    # captured-sha case has something to diff (the guard also requires
    # base != HEAD and base an ancestor of HEAD).
    (repo / "src" / "wp01" / "mod.py").write_text("x = 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "implement WP01")

    # #4827/WP03/T015: `_mt_resolve_owned_review_base` now also classifies
    # the recorded pin against the TARGET-BRANCH tip, captured from
    # `st.main_repo_root` (mirroring `owned.primary`), never `owned.root`
    # (see that function's docstring). This single-checkout fixture has no
    # separate primary/owned split, so `repo` stands in for both.
    st = SimpleNamespace(
        owned=SimpleNamespace(root=repo),
        feature_dir=feature_dir,
        main_repo_root=repo,
        target_branch="main",
    )

    # Post-fix: a captured sha resolves cleanly -- no refusal.
    base = _mt_resolve_owned_review_base(st)
    assert base == lanes.planning_commit_sha

    # Pre-fix shape, reproduced directly: a bare ``None`` recorded sha (what
    # this rebuild used to write) hard-refuses with OWNED_REVIEW_BASE_INVALID
    # -- exactly the gap BLOCKER 2 named.
    lanes.planning_commit_sha = None
    write_lanes_json(feature_dir, lanes)
    with pytest.raises(ActionContextError) as excinfo:
        _mt_resolve_owned_review_base(st)
    assert excinfo.value.code == "OWNED_REVIEW_BASE_INVALID"


# ---------------------------------------------------------------------------
# #4827 pre-PR squad finding [MEDIUM]: no test asserted the ORPHANED branch of
# ``_mt_resolve_owned_review_base`` (the ``OWNED_REVIEW_BASE_ORPHANED`` raise
# at ~L726-732) -- only the pre-existing ``None``/``OWNED_REVIEW_BASE_INVALID``
# shape above was covered. This closes that gap: a recorded pin whose commit
# OBJECT is still present but is no longer an ancestor of the target-branch
# tip (the mid-mission rebase/rewrite shape ``classify_recorded_pin`` calls
# ``PinClass.ORPHANED``) must refuse BEFORE any diff is computed against it,
# never silently resolve a dead base.
# ---------------------------------------------------------------------------


def _rev_parse(repo: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_owned_review_base_refuses_on_orphaned_pin(tmp_path: Path) -> None:
    """``_mt_resolve_owned_review_base`` raises ``OWNED_REVIEW_BASE_ORPHANED``
    for a recorded pin that is present-but-unreachable from the target-branch
    tip, and never reaches the ``resolve_commit``/merge-base diff logic below
    that check (a dead base is never computed).
    """
    from types import SimpleNamespace

    from mission_runtime import ActionContextError

    from specify_cli.cli.commands.agent.tasks_move_task import (
        _mt_resolve_owned_review_base,
    )
    from specify_cli.lanes.persistence import write_lanes_json

    repo, feature_dir = _build_wedged_repo(tmp_path)
    report = repair_repo(repo, mission=_MISSION_SLUG)
    result = next(m for m in report.missions if m.mission_slug == _MISSION_SLUG)
    assert result.status != "error", result.validation_errors

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None

    # Produce a commit object that still exists in the object store but is
    # NOT an ancestor of main's tip: commit on a throwaway branch, capture
    # its sha, then delete the branch. The loose object survives (no gc
    # runs in this fixture), so `git cat-file -e` still finds it while
    # `git merge-base --is-ancestor` correctly reports "not an ancestor" --
    # exactly the ORPHANED shape (present, unreachable).
    _git(repo, "checkout", "-qb", "throwaway")
    (repo / "orphan.txt").write_text("orphaned content\n", encoding="utf-8")
    _git(repo, "add", "orphan.txt")
    _git(repo, "commit", "-qm", "orphaned planning commit candidate")
    orphaned_sha = _rev_parse(repo, "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "throwaway")

    # A real implementation commit ahead of HEAD, so a healthy pin would
    # otherwise have something to diff -- proves the refusal is about
    # classification, not merely "nothing to diff".
    (repo / "src" / "wp01" / "mod.py").write_text("x = 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "implement WP01")

    lanes.planning_commit_sha = orphaned_sha
    write_lanes_json(feature_dir, lanes)

    st = SimpleNamespace(
        owned=SimpleNamespace(root=repo),
        feature_dir=feature_dir,
        main_repo_root=repo,
        target_branch="main",
    )

    with pytest.raises(ActionContextError) as excinfo:
        _mt_resolve_owned_review_base(st)
    assert excinfo.value.code == "OWNED_REVIEW_BASE_ORPHANED"
    assert orphaned_sha in str(excinfo.value)
    assert "orphaned" in str(excinfo.value)
    # The recovery hint -- not a generic re-run -- must be present.
    assert "finalize-tasks --refresh-planning-commit --allow-orphaned" in str(excinfo.value)
