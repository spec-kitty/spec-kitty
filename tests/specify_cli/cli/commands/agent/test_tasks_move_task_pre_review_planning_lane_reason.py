"""#6792: the pre-review gate's reason must not deny a planning-lane WP's commit.

A ``planning_artifact`` WP commits its deliverables in the repository root
checkout — the normal path for the planning lane. Its workspace therefore *is*
that checkout, and the gate diffs it against the branch checked out there (a
default Mission's topic branch until it lands, ADR 2026-11-06-3), so the
merge-base diff is empty by construction and a clean working tree adds no dirty
paths. The gate correctly skips cheaply; what it must not do is record
"no changed files detected for this WP", because the commit on disk says
otherwise (#2741 asked for "committed-diff not inspected" at minimum).

These arms drive the production ``move-task --to for_review`` entry point over a
**real** git repository, so the empty diff comes from git rather than from a
mocked ``_mt_pre_review_changed_files``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    TasksPorts,
)
from specify_cli.cli.commands.agent import tasks_move_task_gates
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.status import Lane, StatusEvent, TransitionRequest
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = [pytest.mark.git_repo]

_MISSION = "gate-reason-6792"
_TARGET_BRANCH = "mission-target"

_PLANNING_WP = "WP09"
_CODE_WP = "WP01"

#: The pre-fix wording the planning lane must stop claiming.
_INCUMBENT_NO_CHANGES_REASON = "no changed files detected for this WP — skipping the gate cheaply"


class _RecordingCoordRouter:
    """A coord port that records transitions and refuses to commit anything."""

    def __init__(self, write_dir: Path) -> None:
        self.write_dir = write_dir
        self.status_calls: list[TransitionRequest] = []

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        del mission
        return self.write_dir

    def commit_status(self, request: TransitionRequest, *, capability: GuardCapability) -> CommitStatusResult:
        del capability
        self.status_calls.append(request)
        return CommitStatusResult(event=None, skipped=False)

    def commit_artifact(self, mission: object, paths: object, message: str, *, kind: object, policy: object) -> CommitArtifactResult:
        del mission, paths, message, kind, policy
        raise AssertionError("auto-commit is disabled in this test")


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _wp_frontmatter(wp_id: str, *, execution_mode: str, owned_files: tuple[str, ...]) -> str:
    owned = "\n".join(f"  - {entry}" for entry in owned_files)
    return (
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} fixture\n"
        f"execution_mode: {execution_mode}\n"
        "agent: testbot\n"
        "owned_files:\n"
        f"{owned}\n"
        "---\n\n"
        f"# {wp_id}\n\n"
        "## Activity Log\n"
    )


def _seed_in_progress(feature_dir: Path, wp_id: str, *, execution_mode: str) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"fixture-{wp_id}-in-progress",
            mission_slug=_MISSION,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-10-30T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode=execution_mode,
        ),
    )


def _build_fixture(tmp_path: Path) -> tuple[TasksPorts, _RecordingCoordRouter]:
    """A real git repo whose branch already carries the planning WP's deliverables.

    The checkout sits on the branch the gate diffs against and the tree is clean —
    exactly the shape that makes the gate's merge-base diff empty for a
    planning-lane WP.
    """
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tmp_path / ".kittify").mkdir()

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KXG2TDVPTZSYY58E578T5RX3",
                "mission_slug": _MISSION,
                "slug": _MISSION,
                "mission_type": "software-dev",
                "target_branch": _TARGET_BRANCH,
                "topology": "lanes",
                "vcs": "git",
            }
        ),
        encoding="utf-8",
    )

    def _write_lanes_json(*, planning_commit_sha: str | None) -> None:
        (feature_dir / "lanes.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "mission_slug": _MISSION,
                    "mission_id": "01KXG2TDVPTZSYY58E578T5RX3",
                    "mission_branch": f"kitty/mission-{_MISSION}",
                    "target_branch": _TARGET_BRANCH,
                    "computed_at": "2026-10-30T00:00:00+00:00",
                    "computed_from": "fixture:dependency_graph+ownership",
                    "planning_commit_sha": planning_commit_sha,
                    "planning_artifact_wps": [_PLANNING_WP],
                    "lanes": [
                        {
                            "lane_id": "lane-planning",
                            "wp_ids": [_PLANNING_WP],
                            "write_scope": ["docs/gate.md"],
                            "predicted_surfaces": [],
                            "depends_on_lanes": [],
                            "parallel_group": 0,
                        },
                        {
                            "lane_id": "lane-a",
                            "wp_ids": [_CODE_WP],
                            "write_scope": ["src/example.py"],
                            "predicted_surfaces": [],
                            "depends_on_lanes": [],
                            "parallel_group": 1,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    _write_lanes_json(planning_commit_sha=None)
    (tasks_dir / f"{_PLANNING_WP}-docs.md").write_text(
        _wp_frontmatter(_PLANNING_WP, execution_mode="planning_artifact", owned_files=("docs/gate.md", "docs/notes.md")),
        encoding="utf-8",
    )
    (tasks_dir / f"{_CODE_WP}-code.md").write_text(
        _wp_frontmatter(_CODE_WP, execution_mode="code_change", owned_files=("src/example.py",)),
        encoding="utf-8",
    )
    _seed_in_progress(feature_dir, _PLANNING_WP, execution_mode="worktree")
    _seed_in_progress(feature_dir, _CODE_WP, execution_mode="worktree")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gate.md").write_text("base\n", encoding="utf-8")

    _git(tmp_path, "init", "-q", "-b", _TARGET_BRANCH)
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture base")

    # Every WP's evidence window starts at the planning commit finalize-tasks
    # records; the fixture records the base commit.
    base_sha = _git(tmp_path, "rev-parse", "HEAD").strip()
    # The code lane exists from the planning commit onward and carries WP01's
    # work, so the code WP has a real evidence window. Its *workspace* is never
    # materialized here, which is what leaves the gate's changed-file set empty.
    _git(tmp_path, "checkout", "-q", "-b", f"kitty/mission-{_MISSION}-lane-a")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", f"feat({_CODE_WP}): fixture lane work")
    _git(tmp_path, "checkout", "-q", _TARGET_BRANCH)

    _write_lanes_json(planning_commit_sha=base_sha)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: record the planning commit")

    # The planning-lane WP commits its deliverables on the checked-out branch itself.
    (docs / "gate.md").write_text("changed by WP09\n", encoding="utf-8")
    (docs / "notes.md").write_text("planning notes\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", f"docs({_PLANNING_WP}): committed deliverables")

    assert _git(tmp_path, "status", "--porcelain").strip() == "", "fixture tree must be clean for the empty-diff shape"

    router = _RecordingCoordRouter(write_dir=feature_dir)
    ports = TasksPorts(
        fs=FakeFsReader(),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    return ports, router


def _invoke_move_task(tmp_path: Path, wp_id: str, ports: TasksPorts, *, json_output: bool) -> Any:
    args = ["move-task", wp_id, "--to", "for_review", "--mission", _MISSION, "--no-auto-commit"]
    if json_output:
        args.append("--json")
    with (
        setup_mocked_env(
            tmp_path,
            mission_slug=_MISSION,
            target_branch=_TARGET_BRANCH,
            extra_patches={
                "_validate_ready_for_review": (True, []),
                "_check_unchecked_subtasks": [],
            },
        ),
        patch("specify_cli.cli.commands.agent.tasks_move_task._default_move_task_ports", return_value=ports),
    ):
        return CliRunner().invoke(app, args)


def _move_to_for_review(tmp_path: Path, wp_id: str, ports: TasksPorts) -> dict[str, Any]:
    result = _invoke_move_task(tmp_path, wp_id, ports, json_output=True)
    assert result.exit_code == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_planning_lane_wp_records_that_the_committed_diff_was_not_inspected(tmp_path: Path) -> None:
    """SC-001/SC-004: a committed planning-lane WP gets a true reason, cheaply.

    The WP committed two files on the checked-out branch; the gate's empty-diff arm
    must say the committed diff was not inspected, keep the verdict
    non-blocking, apply the transition and dispatch no gate.
    """
    ports, router = _build_fixture(tmp_path)

    with patch.object(tasks_move_task_gates, "_mt_dispatch_transition_gates", side_effect=AssertionError("empty-diff arm must not dispatch a gate")):
        payload = _move_to_for_review(tmp_path, _PLANNING_WP, ports)

    gate = payload["pre_review_gate"]
    reason = gate["reason"]
    assert gate["outcome"] == "no_coverage"
    assert gate["blocked"] is False
    assert payload["transition_applied"] is True
    # Pin the audit sentence's shape: a loose "planning" substring would also
    # accept a reason such as "not a planning lane".
    assert reason.startswith("planning-lane WP — committed diff not inspected")
    assert reason != _INCUMBENT_NO_CHANGES_REASON
    assert "no changed files detected" not in reason
    # The cheap skip: nothing was scoped and no test command was selected.
    assert gate["test_targets"] == []
    assert len(router.status_calls) == 1


def test_planning_lane_wp_human_output_renders_the_same_reason(tmp_path: Path) -> None:
    """NFR-003: the JSON payload and the human line are the same verdict field."""
    ports, _router = _build_fixture(tmp_path)

    result = _invoke_move_task(tmp_path, _PLANNING_WP, ports, json_output=False)

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "planning-lane WP — committed diff not inspected" in result.stdout
    assert _INCUMBENT_NO_CHANGES_REASON not in result.stdout


def test_planning_artifact_falls_back_to_the_lanes_manifest_kind_view(tmp_path: Path) -> None:
    """SC-001 fallback: a WP with no declared mode is classified from ``lanes.json``.

    Older missions declare no ``execution_mode`` in the WP frontmatter. The
    manifest then answers the kind question: the WP sits in ``lane-planning`` and
    `planning_artifact_wps`` names it, so it still gets the honest reason rather
    than the false "no changed files detected" claim this mission removes.
    """
    ports, _router = _build_fixture(tmp_path)
    tasks_dir = tmp_path / "kitty-specs" / _MISSION / "tasks"
    (tasks_dir / f"{_PLANNING_WP}-docs.md").write_text(
        f"---\nwork_package_id: {_PLANNING_WP}\ntitle: {_PLANNING_WP} fixture\nagent: testbot\nowned_files:\n  - docs/gate.md\n---\n\n# {_PLANNING_WP}\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: drop the declared execution mode")

    payload = _move_to_for_review(tmp_path, _PLANNING_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"].startswith("planning-lane WP — committed diff not inspected")
    assert payload["transition_applied"] is True

    # The same manifest verdict keeps the lane test invocation away from the planning WP (#7547),
    # while a code WP in the same mission still gets one.
    def evidence_for(wp_id: str) -> tuple[Any, Any]:
        state = SimpleNamespace(
            wp=None,
            main_repo_root=tmp_path,
            mission_slug=_MISSION,
            task_id=wp_id,
            owned=None,
            pre_review_lane_id=None,
            pre_review_resolution_kind=None,
        )
        return tasks_move_task_gates._mt_lane_test_evidence(state, tmp_path)

    assert evidence_for(_PLANNING_WP) == (None, None)
    invocation, evidence_tree = evidence_for(_CODE_WP)
    assert invocation is not None
    assert evidence_tree is not None


def test_code_change_wp_with_empty_diff_keeps_the_incumbent_reason(tmp_path: Path) -> None:
    """SC-003: the new wording is reserved for the planning lane.

    On the same fixture, a ``code_change`` WP whose workspace carries no diff
    keeps the existing "no changed files detected" wording, so a blanket
    rewrite of the message cannot pass this suite.
    """
    ports, _router = _build_fixture(tmp_path)

    payload = _move_to_for_review(tmp_path, _CODE_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"] == _INCUMBENT_NO_CHANGES_REASON
    assert payload["transition_applied"] is True


def test_code_change_wp_placed_in_the_planning_lane_keeps_the_incumbent_reason(tmp_path: Path) -> None:
    """FR-002 ordering: a declared ``code_change`` mode outranks lane membership.

    A ``single_branch`` mission's repo-root ``lane-planning`` can legitimately
    hold CODE work packages, so classifying on lane membership alone would give
    this WP the planning-lane reason. The declared ``execution_mode`` wins.
    """
    ports, _router = _build_fixture(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / f"{_CODE_WP}-code.md").write_text(
        _wp_frontmatter(_CODE_WP, execution_mode="code_change", owned_files=("docs/notes.md",)),
        encoding="utf-8",
    )
    manifest = json.loads((feature_dir / "lanes.json").read_text(encoding="utf-8"))
    for lane in manifest["lanes"]:
        if lane["lane_id"] == "lane-a":
            lane["wp_ids"] = []
            lane["write_scope"] = []
        if lane["lane_id"] == "lane-planning":
            lane["wp_ids"] = [_PLANNING_WP, _CODE_WP]
    manifest["planning_artifact_wps"] = [_PLANNING_WP, _CODE_WP]
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: code WP placed in the planning lane")

    payload = _move_to_for_review(tmp_path, _CODE_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"] == _INCUMBENT_NO_CHANGES_REASON
    assert payload["transition_applied"] is True


def test_undeclared_code_wp_in_the_planning_lane_keeps_the_incumbent_reason(tmp_path: Path) -> None:
    """The manifest kind view, not lane membership, decides the fallback.

    A ``single_branch`` mission's one lane is ``lane-planning`` for code WPs too,
    so a WP with no declared mode that the manifest does NOT list in
    ``planning_artifact_wps`` is code work and keeps today's wording.
    """
    ports, _router = _build_fixture(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / f"{_CODE_WP}-code.md").write_text(
        f"---\nwork_package_id: {_CODE_WP}\ntitle: {_CODE_WP} fixture\nagent: testbot\nowned_files:\n  - docs/notes.md\n---\n\n# {_CODE_WP}\n",
        encoding="utf-8",
    )
    manifest = json.loads((feature_dir / "lanes.json").read_text(encoding="utf-8"))
    for lane in manifest["lanes"]:
        if lane["lane_id"] == "lane-a":
            lane["wp_ids"] = []
            lane["write_scope"] = []
        if lane["lane_id"] == "lane-planning":
            lane["wp_ids"] = [_PLANNING_WP, _CODE_WP]
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: undeclared code WP in the planning lane")

    payload = _move_to_for_review(tmp_path, _CODE_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"] == _INCUMBENT_NO_CHANGES_REASON
    assert payload["transition_applied"] is True


def test_planning_lane_classification_survives_an_unreadable_lanes_manifest(tmp_path: Path) -> None:
    """Edge case: an unknown lane degrades to today's wording, never a crash.

    The frontmatter here declares no ``execution_mode``, so the classification
    falls back to ``lanes.json``; a corrupt manifest must leave the verdict at
    the incumbent reason rather than converting the non-blocking skip into a
    resolution failure.
    """
    ports, _router = _build_fixture(tmp_path)
    tasks_dir = tmp_path / "kitty-specs" / _MISSION / "tasks"
    (tasks_dir / f"{_PLANNING_WP}-docs.md").write_text(
        f"---\nwork_package_id: {_PLANNING_WP}\ntitle: {_PLANNING_WP} fixture\nagent: testbot\nowned_files:\n  - docs/gate.md\n---\n\n# {_PLANNING_WP}\n",
        encoding="utf-8",
    )
    (tmp_path / "kitty-specs" / _MISSION / "lanes.json").write_text("{ not json", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: unreadable lanes manifest")

    payload = _move_to_for_review(tmp_path, _PLANNING_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"] == _INCUMBENT_NO_CHANGES_REASON
    assert payload["transition_applied"] is True


def test_declared_planning_mode_wins_over_a_silent_manifest_kind_view(tmp_path: Path) -> None:
    """The other half of the ordering: a declared planning mode needs no manifest help.

    A ``planning_artifact`` WP whose ``lanes.json`` does not name it in
    ``planning_artifact_wps`` (an older or partial manifest) still gets the
    honest reason, because the declared ``execution_mode`` is asked first and
    returns before the manifest is read at all.
    """
    ports, _router = _build_fixture(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    manifest = json.loads((feature_dir / "lanes.json").read_text(encoding="utf-8"))
    manifest["planning_artifact_wps"] = []
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: manifest kind view omits the planning WP")

    payload = _move_to_for_review(tmp_path, _PLANNING_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"].startswith("planning-lane WP — committed diff not inspected")
    assert payload["transition_applied"] is True


_DEFAULT_MISSION_BRANCH = f"kitty/mission-{_MISSION}-01KXG2TD"


def _build_default_single_branch_fixture(tmp_path: Path) -> TasksPorts:
    """A default ``single_branch`` Mission (ADR 2026-11-06-3) mid-flight.

    ``agent mission create`` with no ``--topology`` mints one Mission topic
    branch and checks it out in the write checkout; ``main`` stays the target.
    The topic branch is ahead of ``main`` by the planning commit and the
    planning WP's committed deliverables, and its one repo-root ``lane-planning``
    lane holds the code WP too.
    """
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / "README.md").write_text("target\n", encoding="utf-8")

    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "target base")
    _git(tmp_path, "checkout", "-q", "-b", _DEFAULT_MISSION_BRANCH)

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KXG2TDVPTZSYY58E578T5RX3",
                "mission_slug": _MISSION,
                "slug": _MISSION,
                "mission_type": "software-dev",
                "target_branch": "main",
                "mission_branch": _DEFAULT_MISSION_BRANCH,
                "topology": "single_branch",
                "topology_source": "default",
                "topology_settled": True,
                "vcs": "git",
            }
        ),
        encoding="utf-8",
    )

    def _write_lanes_json(*, planning_commit_sha: str | None) -> None:
        (feature_dir / "lanes.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "mission_slug": _MISSION,
                    "mission_id": "01KXG2TDVPTZSYY58E578T5RX3",
                    "mission_branch": _DEFAULT_MISSION_BRANCH,
                    "target_branch": "main",
                    "computed_at": "2026-10-30T00:00:00+00:00",
                    "computed_from": "fixture:dependency_graph+ownership",
                    "planning_commit_sha": planning_commit_sha,
                    "planning_artifact_wps": [_PLANNING_WP],
                    "lanes": [
                        {
                            "lane_id": "lane-planning",
                            "wp_ids": [_CODE_WP, _PLANNING_WP],
                            "write_scope": ["docs/gate.md", "src/example.py"],
                            "predicted_surfaces": [],
                            "depends_on_lanes": [],
                            "parallel_group": 0,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    _write_lanes_json(planning_commit_sha=None)
    (tasks_dir / f"{_PLANNING_WP}-docs.md").write_text(
        _wp_frontmatter(_PLANNING_WP, execution_mode="planning_artifact", owned_files=("docs/gate.md",)),
        encoding="utf-8",
    )
    (tasks_dir / f"{_CODE_WP}-code.md").write_text(
        _wp_frontmatter(_CODE_WP, execution_mode="code_change", owned_files=("src/example.py",)),
        encoding="utf-8",
    )
    _seed_in_progress(feature_dir, _PLANNING_WP, execution_mode="direct_repo")
    _seed_in_progress(feature_dir, _CODE_WP, execution_mode="direct_repo")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: planning commit on the Mission branch")
    # finalize-tasks records the planning commit; every WP's evidence window starts there.
    _write_lanes_json(planning_commit_sha=_git(tmp_path, "rev-parse", "HEAD").strip())
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture: record the planning commit")

    # Both WPs commit in the write checkout, on the Mission branch.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", f"feat({_CODE_WP}): committed work")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "gate.md").write_text("changed by WP09\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", f"docs({_PLANNING_WP}): committed deliverables")

    assert _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").strip() == _DEFAULT_MISSION_BRANCH
    assert _git(tmp_path, "status", "--porcelain").strip() == ""
    # The Mission branch really is ahead of the target: the empty diff below is
    # not an artefact of a branch with nothing on it.
    assert _git(tmp_path, "diff", "--name-only", "main...HEAD").strip() != ""

    router = _RecordingCoordRouter(write_dir=feature_dir)
    return TasksPorts(fs=FakeFsReader(), coord=router, git=FakeGitOps(), render=FakeRender())


def _move_default_mission_wp(tmp_path: Path, wp_id: str, ports: TasksPorts) -> dict[str, Any]:
    # ``_ensure_target_branch_checked_out`` respects the operator's current
    # branch, so move-task resolves the Mission topic branch the write checkout
    # sits on; the mocked resolver returns exactly that.
    args = ["move-task", wp_id, "--to", "for_review", "--mission", _MISSION, "--no-auto-commit", "--json"]
    with (
        setup_mocked_env(
            tmp_path,
            mission_slug=_MISSION,
            target_branch=_DEFAULT_MISSION_BRANCH,
            extra_patches={
                "_validate_ready_for_review": (True, []),
                "_check_unchecked_subtasks": [],
            },
        ),
        patch("specify_cli.cli.commands.agent.tasks_move_task._default_move_task_ports", return_value=ports),
    ):
        result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def test_default_single_branch_mission_planning_wp_still_has_an_empty_diff(tmp_path: Path) -> None:
    """Under the size-based default topology the empty diff still occurs.

    The planning WP committed on the Mission topic branch, which is ahead of
    ``main``; the gate diffs the write checkout against the branch move-task
    resolved (that same topic branch), so the changed-file set is empty and the
    record must say the committed diff was not inspected. The reason names the
    repository root checkout, never "the target branch", which a default
    Mission does not commit on before it lands.
    """
    ports = _build_default_single_branch_fixture(tmp_path)

    with patch.object(tasks_move_task_gates, "_mt_dispatch_transition_gates", side_effect=AssertionError("empty-diff arm must not dispatch a gate")):
        payload = _move_default_mission_wp(tmp_path, _PLANNING_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["blocked"] is False
    assert gate["reason"].startswith("planning-lane WP — committed diff not inspected")
    assert "target branch" not in gate["reason"]
    assert "repository root checkout" in gate["reason"]
    assert payload["transition_applied"] is True


def test_default_single_branch_mission_code_wp_keeps_the_incumbent_reason(tmp_path: Path) -> None:
    """The code WP sharing the one repo-root lane keeps today's wording.

    Its committed work is equally invisible to the gate; that wider limitation
    is #6851's scope, and this change deliberately leaves code WPs' wording
    alone (C-001).
    """
    ports = _build_default_single_branch_fixture(tmp_path)

    payload = _move_default_mission_wp(tmp_path, _CODE_WP, ports)

    gate = payload["pre_review_gate"]
    assert gate["outcome"] == "no_coverage"
    assert gate["reason"] == _INCUMBENT_NO_CHANGES_REASON
    assert payload["transition_applied"] is True
