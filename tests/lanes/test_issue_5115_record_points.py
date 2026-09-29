"""#5115 review cycles 1-2: the explicit ``record_tip`` record points.

Each of these calls is the ONLY tip-recording path when the post-commit
recorder hook is not installed -- a foreign hook occupies the slot (C-010
skips installation), or a ``core.hooksPath`` repo the installer never
reached. Every test here writes a FOREIGN ``post-commit`` hook FIRST, drives
the real production function, and asserts the tip is recorded anyway
through the explicit call -- never through the (absent) hook.

Mutation table (each verified: mutate -> the corresponding test here goes
red -> restore -- see the WP07 cycle-2/cycle-3 handoff reports for the exact
commands):

* M2 ``tasks_move_task._mt_commit_lane_deliverables`` ->
  ``test_for_review_auto_commit_records_tip_despite_foreign_hook``
* M3 ``auto_rebase._finalize_auto_rebase`` ->
  ``test_auto_rebase_commit_records_tip_despite_foreign_hook``
* M4 ``implement_support.reenter_lane_self_heal`` ->
  ``test_reenter_self_heal_records_tip_despite_foreign_hook``
* M6 ``worktree_allocator`` CRASH_RECOVERY route ->
  ``test_crash_recovery_records_tip_despite_foreign_hook``
* M7 ``agent.status.emit`` for_review (T032) ->
  ``test_status_emit_for_review_records_tip_despite_foreign_hook``
* M8 ``orchestrator_api.commands.transition`` for_review (T032) ->
  ``test_orchestrator_transition_for_review_records_tip_despite_foreign_hook``

Each mutation is: delete the named production call, confirm the paired test
above goes red, restore.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.lane_tip import read_tip
from specify_cli.policy.lane_tip_recorder import install_lane_tip_recorder

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_FOREIGN_HOOK_BODY = "#!/bin/sh\necho custom-hook\nexit 0\n"

runner = CliRunner()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _install_foreign_post_commit_hook(repo: Path) -> Path:
    """Occupy the ``post-commit`` slot with a foreign (non-spec-kitty) hook.

    Confirms, via the REAL installer, that C-010 skips it (the recorder
    never gets a chance to run) -- so any tip recorded afterwards must have
    come from an explicit ``record_tip`` call, not the hook.
    """
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign = hooks_dir / "post-commit"
    foreign.write_text(_FOREIGN_HOOK_BODY, encoding="utf-8")
    foreign.chmod(0o755)

    installed = install_lane_tip_recorder(repo)
    assert all(p.name != "post-commit" for p in installed), "the foreign hook must be skipped, not overwritten"
    assert foreign.read_text(encoding="utf-8") == _FOREIGN_HOOK_BODY, "the foreign hook's bytes must survive install"
    return foreign


# ---------------------------------------------------------------------------
# M2 -- tasks_move_task._mt_commit_lane_deliverables (for_review auto-commit)
# ---------------------------------------------------------------------------


def _make_lane_worktree_for_move_task(tmp_path: Path, mission_slug: str, branch: str) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "keep.txt").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")

    _install_foreign_post_commit_hook(repo)

    lane_wt = repo / ".worktrees" / f"{mission_slug}-lane-a"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(lane_wt), "main")
    (lane_wt / "src" / "feature.py").write_text("print('work')\n", encoding="utf-8")
    return repo, lane_wt


def test_for_review_auto_commit_records_tip_despite_foreign_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState, _mt_commit_lane_deliverables
    from specify_cli.workspace.context import ResolvedWorkspace

    mission_slug = "mt-5115-record-01KZZTE1"
    branch = f"kitty/mission-{mission_slug}-lane-a"
    repo, lane_wt = _make_lane_worktree_for_move_task(tmp_path, mission_slug, branch)

    assert read_tip(repo, branch) is None, "nothing spec-kitty-managed has recorded a tip yet"

    resolved = ResolvedWorkspace(
        mission_slug=mission_slug,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name=f"{mission_slug}-lane-a",
        worktree_path=lane_wt,
        branch_name=branch,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )
    monkeypatch.setattr(_tasks, "resolve_workspace_for_wp", lambda *a, **k: resolved)  # noqa: ARG005

    st = _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=mission_slug,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=True,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=True,
        json_output=True,
    )
    st.main_repo_root = repo
    st.mission_slug = mission_slug

    _mt_commit_lane_deliverables(st)

    head = _git(lane_wt, "rev-parse", "HEAD")
    assert read_tip(repo, branch) == head, "M2: the for_review auto-commit must record the tip even with a foreign hook"


# ---------------------------------------------------------------------------
# M3 -- auto_rebase._finalize_auto_rebase (the auto-rebase merge commit)
# ---------------------------------------------------------------------------


def _write_pyproject(path: Path, deps: list[str]) -> None:
    body = '[project]\nname = "demo"\ndependencies = [\n' + "".join(f'  "{d}",\n' for d in deps) + "]\n"
    path.write_text(body, encoding="utf-8")


def test_auto_rebase_commit_records_tip_despite_foreign_hook(tmp_path: Path) -> None:
    from specify_cli.lanes.auto_rebase import attempt_auto_rebase
    from specify_cli.lanes.models import ExecutionLane

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo"])
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-q", "-m", "seed")

    _install_foreign_post_commit_hook(repo)

    mission_slug = "auto-rebase-5115-01KZZTE2"
    mission_branch = f"kitty/mission-{mission_slug}"
    _git(repo, "branch", mission_branch, "main")
    _git(repo, "checkout", "-q", mission_branch)
    _write_pyproject(repo / "pyproject.toml", ["alpha", "bravo", "charlie"])
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-q", "-m", "mission: add charlie")
    _git(repo, "checkout", "-q", "main")

    branch_b = f"kitty/mission-{mission_slug}-lane-a"
    worktree_b = repo / ".worktrees" / f"{mission_slug}-lane-a"
    worktree_b.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", branch_b, str(worktree_b), "main")
    _write_pyproject(worktree_b / "pyproject.toml", ["alpha", "bravo", "delta"])
    _git(worktree_b, "add", "pyproject.toml")
    _git(worktree_b, "config", "user.email", "t@example.com")
    _git(worktree_b, "config", "user.name", "test")
    _git(worktree_b, "commit", "-q", "-m", "lane: add delta")

    assert read_tip(repo, branch_b) is None

    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("pyproject.toml",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )
    report = attempt_auto_rebase(
        lane=lane,
        branch=branch_b,
        mission_branch=mission_branch,
        repo_root=repo,
        worktree_path=worktree_b,
    )

    assert report.succeeded is True, f"halt_reason={report.halt_reason}"
    head = _git(worktree_b, "rev-parse", "HEAD")
    assert read_tip(repo, branch_b) == head, "M3: the auto-rebase commit must record the tip even with a foreign hook"


# ---------------------------------------------------------------------------
# M4 -- implement_support.reenter_lane_self_heal (code-lane re-entry)
# ---------------------------------------------------------------------------


def _write_code_lane_meta_and_lanes(repo: Path, mission_slug: str) -> None:
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_slug,
                "mission_slug": mission_slug,
                "mid8": mission_slug[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-09-29T00:00:00+00:00",
                "friendly_name": "5115 self-heal record-point fixture",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lanes_payload = {
        "version": 1,
        "mission_slug": mission_slug,
        "mission_id": mission_slug,
        "mission_branch": f"kitty/mission-{mission_slug}",
        "target_branch": "main",
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
        "computed_at": "2026-09-29T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
        "planning_commit_sha": None,
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes_payload, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "chore: planning artifacts")


def test_reenter_self_heal_records_tip_despite_foreign_hook(tmp_path: Path) -> None:
    from specify_cli.lanes.implement_support import reenter_lane_self_heal
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")

    _install_foreign_post_commit_hook(repo)

    mission_slug = "self-heal-5115-01KZZTE3"
    _write_code_lane_meta_and_lanes(repo, mission_slug)

    worktree_path, branch = predict_lane_worktree(repo, mission_slug, "lane-a")
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree_path), "main")
    (worktree_path / "lane_a_output.txt").write_text("lane-a code\n", encoding="utf-8")
    _git(worktree_path, "add", "lane_a_output.txt")
    _git(worktree_path, "commit", "-q", "-m", "lane-a: real work, made while the hook was foreign")

    assert read_tip(repo, branch) is None, "the foreign hook must not have recorded anything"

    result = reenter_lane_self_heal(repo, mission_slug, "WP01")

    assert result == worktree_path
    head = _git(worktree_path, "rev-parse", "HEAD")
    assert read_tip(repo, branch) == head, "M4: self-heal re-entry must record the tip even with a foreign hook"


# ---------------------------------------------------------------------------
# M6 -- worktree_allocator.allocate_lane_worktree, CRASH_RECOVERY route
# ---------------------------------------------------------------------------


def test_crash_recovery_records_tip_despite_foreign_hook(tmp_path: Path) -> None:
    """#5115 review cycle 2, Issue 1: the CRASH_RECOVERY ``record_tip`` call
    (~``worktree_allocator.py:1131``) is the backfill-on-touch for a lane
    whose branch survived but whose worktree DIRECTORY was lost (FR-021).
    Without it, a foreign-hook lane whose tip was never otherwise recorded
    stays unrecorded after re-attachment -- and if the branch is later
    deleted, the guard fails open (a stale/absent tip reading as absorbed).

    Mirrors ``tests/specify_cli/lanes/test_worktree_allocator_recovery.py``'s
    own crash-recovery trigger: delete ONLY the worktree directory (keep the
    branch), which is the real CRASH_RECOVERY condition -- not a full
    ``git worktree remove`` + branch delete (that is the #4889/#5115 DESTROYED
    case, covered elsewhere).
    """
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")

    _install_foreign_post_commit_hook(repo)

    mission_slug = "crash-recovery-5115-01KZZTE4"
    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=None,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-29T00:00:00Z",
        computed_from="test",
    )

    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=mission_slug,
        wp_id="WP01",
        lanes_manifest=manifest,
    )

    # The FRESH route's own record_tip call (unrelated to this test) records
    # the tip at CREATION time -- base, since nothing has been committed on
    # the lane yet. Capture it so the next assertion proves the tip goes
    # STALE (not None) once real work lands with no hook to refresh it.
    fresh_tip = read_tip(repo, branch)
    assert fresh_tip is not None

    # Real work, ahead of base -- the foreign hook is still occupying the
    # post-commit slot, so nothing records the tip through it: it stays
    # stale at the FRESH value captured above.
    (worktree_path / "work.txt").write_text("real work\n", encoding="utf-8")
    _git(worktree_path, "add", "work.txt")
    _git(worktree_path, "commit", "-q", "-m", "lane: real work before the worktree is lost")
    head = _git(worktree_path, "rev-parse", "HEAD")
    assert head != fresh_tip, "sanity: the new commit must actually move the branch tip"
    assert read_tip(repo, branch) == fresh_tip, "the foreign hook must not have refreshed the (now-stale) tip"

    # Simulate the crash: only the WORKTREE DIRECTORY is lost. The branch
    # (and its commit) survive in the object store -- the real
    # CRASH_RECOVERY trigger.
    shutil.rmtree(worktree_path)
    assert not worktree_path.exists(), "pre-condition: worktree directory gone, branch kept"

    recovered_path, recovered_branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=mission_slug,
        wp_id="WP01",
        lanes_manifest=manifest,
    )

    assert recovered_path == worktree_path
    assert recovered_branch == branch
    assert read_tip(repo, branch) == head, "M6: CRASH_RECOVERY must backfill the tip even with a foreign hook"


# ---------------------------------------------------------------------------
# M7/M8 -- the two for_review transition record points (T032, #5115 review
# cycle 2 Issue 2): ``agent status emit`` and the orchestrator ``transition``.
#
# Neither surface always auto-commits (unlike move-task's M2), so under a
# foreign hook they are the only chance to record a lane's tip before some
# later touch. Both share the same non-coord LANES mission fixture
# (``_build_lanes_mission``) that ``test_issue_5115_destroyed_lane_non_coord``
# uses for the guard itself, seeded to ``in_progress`` and driven through the
# REAL for_review transition entry point (real committed work satisfies the
# commit-beyond-base gate honestly -- ``--subtasks-complete`` /
# ``--implementation-evidence-present`` bypass only the unrelated tasks.md
# completeness inference, not the gate this WP cares about).
# ---------------------------------------------------------------------------


def _seed_for_review_ready_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, *, tag: str) -> tuple[Path, str, str, str]:
    """Build a non-coord mission, foreign-hook it, and get WP01's lane to
    ``in_progress`` with a real, unrecorded commit beyond base.

    Returns ``(repo_root, mission_dirname, branch_name, head_sha)``.
    """
    from tests.lanes.test_issue_4889_destroyed_lane_guard import _ids
    from tests.lanes.test_issue_5115_destroyed_lane_non_coord import _build_lanes_mission
    from tests.lanes.test_lane_allocation_integrity_e2e import _commit_real_work, _run_cli_implement, _wp_context
    from tests.utils import _seed_canonical_wp_state

    ids = _ids(f"{tag}-{request.node.name}")
    repo_root, mission_dirname = _build_lanes_mission(tmp_path, monkeypatch, mission_slug=ids.mission_slug)

    # Foreign hook FIRST -- before the lane worktree (and its recorder-hook
    # install attempt) is ever created.
    _install_foreign_post_commit_hook(repo_root)

    claim = _run_cli_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    context = _wp_context(repo_root, mission_dirname, "WP01")
    worktree_path = repo_root / context.worktree_path
    branch_name = context.branch_name

    # ``implement``'s own FRESH-route allocation already records a tip at
    # CREATION time (== base, before any lane work exists) -- unrelated to
    # this fixture's foreign hook. Capture it so the next assertion proves
    # the tip goes STALE (not None) once real work lands with no hook to
    # refresh it -- the exact fail-open gap this WP closes.
    fresh_tip = read_tip(repo_root, branch_name)
    assert fresh_tip is not None

    head_sha = _commit_real_work(worktree_path)
    assert head_sha != fresh_tip, "sanity: the new commit must actually move the branch tip"
    assert read_tip(repo_root, branch_name) == fresh_tip, "the foreign hook must not have refreshed the (now-stale) tip"

    _seed_canonical_wp_state(
        repo_root,
        mission_dirname,
        "WP01",
        "in_progress",
        actor="test-agent",
        assignee="test-agent",
        shell_pid="4242",
        timestamp="2026-01-01T00:00:02Z",
    )

    return repo_root, mission_dirname, branch_name, head_sha


def test_status_emit_for_review_records_tip_despite_foreign_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """M7: ``agent status emit ... --to for_review`` records the lane tip."""
    from specify_cli.cli.commands.agent.status import app as status_app
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)  # noqa: ARG005

    repo_root, mission_dirname, branch_name, head_sha = _seed_for_review_ready_lane(tmp_path, monkeypatch, request, tag="status-emit")

    result = runner.invoke(
        status_app,
        [
            "emit",
            "WP01",
            "--to",
            "for_review",
            "--actor",
            "test-agent",
            "--mission",
            mission_dirname,
            "--subtasks-complete",
            "--implementation-evidence-present",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    assert read_tip(repo_root, branch_name) == head_sha, "M7: agent status emit's for_review transition must record the tip even with a foreign hook"


def test_orchestrator_transition_for_review_records_tip_despite_foreign_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """M8: the orchestrator ``transition ... --to for_review`` records the lane tip."""
    from unittest.mock import patch

    from specify_cli.orchestrator_api.commands import app as orchestrator_app
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)  # noqa: ARG005

    repo_root, mission_dirname, branch_name, head_sha = _seed_for_review_ready_lane(tmp_path, monkeypatch, request, tag="orch-transition")

    policy = json.dumps(
        {
            "orchestrator_id": "wp07-5115",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )

    with patch("specify_cli.orchestrator_api.commands._get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            orchestrator_app,
            [
                "transition",
                "--mission",
                mission_dirname,
                "--wp",
                "WP01",
                "--to",
                "for_review",
                "--actor",
                "claude",
                "--policy",
                policy,
                "--subtasks-complete",
                "--implementation-evidence-present",
            ],
        )
    assert result.exit_code == 0, result.output

    assert read_tip(repo_root, branch_name) == head_sha, "M8: the orchestrator transition's for_review path must record the tip even with a foreign hook"


# ---------------------------------------------------------------------------
# M9 (review cycle 3, Issue 1) -- a planning_artifact WP reaching for_review
# through the two REAL for_review transition surfaces must succeed and land
# the event WITHOUT ever creating a tip ref anywhere -- the mission-level
# proof that record_tip_for_wp's planning-lane skip actually holds end to
# end (the unit-level spy in test_lane_tip.py proves the skip fires before
# a branch name is even resolved; these two prove the whole transition still
# lands cleanly for a real repo-root lane WP).
# ---------------------------------------------------------------------------


def _no_lane_tip_refs_exist(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "for-each-ref", "refs/spec-kitty/lane-tip/"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == ""


def test_status_emit_for_review_of_a_planning_wp_lands_with_no_tip_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """M9 item 1a: ``agent status emit --to for_review`` on a planning_artifact
    WP (repo-root lane) succeeds, lands the event, and creates no tip ref."""
    from tests.lanes.test_claim_base import _planning_lane_legacy_repo
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import _MISSION_SLUG, _WP_SELF
    from specify_cli.cli.commands.agent.status import app as status_app
    from specify_cli.status.reducer import materialize
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)  # noqa: ARG005

    repo = _planning_lane_legacy_repo(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)

    result = runner.invoke(
        status_app,
        [
            "emit",
            _WP_SELF,
            "--to",
            "for_review",
            "--actor",
            "test-agent",
            "--mission",
            _MISSION_SLUG,
            "--force",
            "--reason",
            "M9 planning-wp force jump to for_review",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    snapshot = materialize(feature_dir)
    assert str(snapshot.work_packages[_WP_SELF]["lane"]) == "for_review"
    assert _no_lane_tip_refs_exist(repo)


def test_orchestrator_transition_for_review_of_a_planning_wp_lands_with_no_tip_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M9 item 1b: the orchestrator ``transition --to for_review`` on the same
    kind of planning_artifact WP succeeds, lands the event, and creates no
    tip ref."""
    from unittest.mock import patch

    from tests.lanes.test_claim_base import _planning_lane_legacy_repo
    from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import _MISSION_SLUG, _WP_SELF
    from specify_cli.orchestrator_api.commands import app as orchestrator_app
    from specify_cli.status.reducer import materialize
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)  # noqa: ARG005

    repo = _planning_lane_legacy_repo(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)

    policy = json.dumps(
        {
            "orchestrator_id": "wp07-5115-m9",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )

    with patch("specify_cli.orchestrator_api.commands._get_main_repo_root", return_value=repo):
        result = runner.invoke(
            orchestrator_app,
            [
                "transition",
                "--mission",
                _MISSION_SLUG,
                "--wp",
                _WP_SELF,
                "--to",
                "for_review",
                "--actor",
                "claude",
                "--policy",
                policy,
                "--force",
                "--note",
                "M9 planning-wp force jump to for_review",
            ],
        )
    assert result.exit_code == 0, result.output

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    snapshot = materialize(feature_dir)
    assert str(snapshot.work_packages[_WP_SELF]["lane"]) == "for_review"
    assert _no_lane_tip_refs_exist(repo)
