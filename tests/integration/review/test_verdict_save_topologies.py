"""Real-command verdict durability across all governed Mission topologies.

The command result is deliberately not the oracle.  Every automatic-save cell
resolves STATUS_STATE and REVIEW_CYCLE placement independently, reads the exact
event from the governed status ref, and ``git show``-reads the evidence bytes
from the governed review ref.  Local-only cells prove that neither the verdict
queue nor the commit router is entered.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, chdir, contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any, cast
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.agent_tasks_ports import (
    MissionHandle,
    RealCoordCommitRouter,
    default_ports,
)
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.cli.commands.agent import tasks_verdict_persistence as persistence_module
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.lanes import ExecutionLane, LanesManifest, write_lanes_json
from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.review.verdict_commit_queue import (
    acquire_verdict_save_queue,
    verdict_save_queue_is_held,
)
from specify_cli.status import StatusEvent, TransitionRequest
from specify_cli.status.store import read_events
from tests._factories import make_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_ID = "WP01"
_TARGET_BRANCH = "test/verdict-topology-target"
_TOPOLOGIES = tuple(MissionTopology)
_MODES = (True, False)


@dataclass(frozen=True)
class _Fixture:
    repo: Path
    mission: str
    mission_id: str
    topology: MissionTopology
    feature_dir: Path
    status_dir: Path
    target_branch: str
    lane_worktree: Path | None


@dataclass(frozen=True)
class _CommandResult:
    reviewer: str
    result: Result
    payload: dict[str, Any] | None
    seam_hits: tuple[str, ...] = ()


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _git_show(repo: Path, ref: str, relative_path: str) -> subprocess.CompletedProcess[str]:
    return _git(repo, "show", f"{ref}:{relative_path}", check=False)


def _git_show_bytes(repo: Path, ref: str, relative_path: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{relative_path}"],
        check=False,
        capture_output=True,
    )


def _assert_git_blob_exact(
    repo: Path,
    ref: str,
    relative_path: str,
    expected: bytes,
) -> bytes:
    shown = _git_show_bytes(repo, ref, relative_path)
    assert shown.returncode == 0, f"missing governed blob: ref={ref!r}, path={relative_path!r}, stderr={shown.stderr!r}"
    assert shown.stdout == expected, f"governed blob mismatch: ref={ref!r}, path={relative_path!r}, expected={expected!r}, actual={shown.stdout!r}"
    return shown.stdout


def _json_payload(output: str) -> dict[str, Any] | None:
    for line in reversed(output.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.name", "Topology Contract")
    _git(repo, "config", "user.email", "topology-contract@spec-kitty.test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init topology contract")


def _write_wp(feature_dir: Path) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / "WP01-topology-contract.md"
    wp_path.write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Topology contract fixture\n"
        "execution_mode: code_change\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/topology-contract/**\n"
        "authoritative_surface: src/topology-contract/\n"
        "---\n\n"
        "# Topology contract fixture\n",
        encoding="utf-8",
    )
    return wp_path


def _write_lane_manifest(feature_dir: Path, mission: str, mission_id: str) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=mission,
        mission_id=mission_id,
        mission_branch=mission_branch_name(mission, mission_id=mission_id),
        target_branch=_TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(_WP_ID,),
                write_scope=("src/topology-contract/**",),
                predicted_surfaces=("tests",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-08-24T00:00:00+00:00",
        computed_from="WP05 real-topology contract",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _seed_in_review(fixture: _Fixture) -> None:
    request = TransitionRequest(
        feature_dir=fixture.status_dir,
        mission_slug=fixture.mission,
        repo_root=fixture.repo,
        wp_id=_WP_ID,
        to_lane="in_review",
        actor="topology-seed",
        force=True,
        reason="seed real-command reviewer state",
        execution_mode="worktree",
    )
    result = default_ports().coord.commit_status(
        request,
        capability=GuardCapability.STANDARD,
    )
    assert result.event is not None and result.event.to_lane.value == "in_review"


def _build_fixture(tmp_path: Path, topology: MissionTopology) -> _Fixture:
    repo = tmp_path / topology.value
    _init_repo(repo)
    created = make_mission(
        repo,
        f"verdict-{topology.value.replace('_', '-')}",
        topology=topology,
        target_branch=_TARGET_BRANCH,
    )
    _write_wp(created.feature_dir)
    mission_id = str(created.meta["mission_id"])
    manifest = None
    if topology in {MissionTopology.LANES, MissionTopology.LANES_WITH_COORD}:
        manifest = _write_lane_manifest(created.feature_dir, created.mission_slug, mission_id)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed topology work package")

    lane_worktree = None
    if manifest is not None:
        lane_worktree, lane_branch = allocate_lane_worktree(
            repo,
            created.mission_slug,
            _WP_ID,
            manifest,
        )
        assert lane_worktree.is_dir()
        assert _git(lane_worktree, "branch", "--show-current").stdout.strip() == lane_branch
        delivery = lane_worktree / "src" / "topology-contract" / "delivery.txt"
        delivery.parent.mkdir(parents=True)
        delivery.write_text("representative lane delivery\n", encoding="utf-8")
        _git(lane_worktree, "add", delivery.relative_to(lane_worktree).as_posix())
        _git(lane_worktree, "commit", "-m", "test: seed representative lane delivery")

    handle = MissionHandle(repo_root=repo, mission_slug=created.mission_slug)
    status_dir = RealCoordCommitRouter().feature_write_dir(handle)
    fixture = _Fixture(
        repo=repo,
        mission=created.mission_slug,
        mission_id=mission_id,
        topology=topology,
        feature_dir=created.feature_dir,
        status_dir=status_dir,
        target_branch=_TARGET_BRANCH,
        lane_worktree=lane_worktree,
    )
    _seed_in_review(fixture)
    return fixture


def _invoke_verdict(
    fixture: _Fixture,
    *,
    reviewer: str,
    auto_commit: bool,
    target_lane: str = "planned",
    body: str = "Changes requested by topology contract.\n",
) -> _CommandResult:
    feedback = fixture.repo.parent / f"{fixture.mission}-{reviewer}.md"
    feedback.write_text(body, encoding="utf-8")
    args = [
        "tasks",
        "move-task",
        _WP_ID,
        "--to",
        target_lane,
        "--mission",
        fixture.mission,
        "--agent",
        reviewer,
        "--reviewer",
        reviewer,
        "--json",
        "--auto-commit" if auto_commit else "--no-auto-commit",
    ]
    if target_lane == "planned":
        args.extend(["--review-feedback-file", str(feedback)])
    else:
        args.extend(
            [
                "--approval-ref",
                f"approval://{fixture.mission}/{reviewer}",
                "--note",
                f"{reviewer} approved the topology contract",
            ]
        )
    if target_lane == "done":
        args.extend(
            [
                "--force",
                "--done-override-reason",
                "real-command topology fixture has no merged delivery branch",
            ]
        )
    with chdir(fixture.repo):
        result = CliRunner().invoke(agent_app, args, catch_exceptions=True)
    return _CommandResult(reviewer, result, _json_payload(result.output))


def _relative_evidence_path(fixture: _Fixture, payload: dict[str, Any]) -> str:
    raw = payload.get("evidence_ref")
    assert isinstance(raw, str) and raw, payload
    path = Path(raw)
    if path.is_absolute():
        return path.relative_to(fixture.repo).as_posix()
    return raw


def _events_from_governed_ref(fixture: _Fixture) -> list[StatusEvent]:
    status_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.STATUS_STATE).ref
    relative = f"kitty-specs/{fixture.mission}/status.events.jsonl"
    shown = _git_show_bytes(fixture.repo, status_ref, relative)
    assert shown.returncode == 0, f"status event ref unreadable: topology={fixture.topology.value}, status_ref={status_ref}, stderr={shown.stderr!r}"
    with tempfile.TemporaryDirectory(prefix="verdict-status-readback-") as temp_dir:
        materialized = Path(temp_dir) / "kitty-specs" / fixture.mission
        materialized.mkdir(parents=True)
        (materialized / "status.events.jsonl").write_bytes(shown.stdout)
        (materialized / "meta.json").write_bytes((fixture.feature_dir / "meta.json").read_bytes())
        return cast(list[StatusEvent], read_events(materialized))


def _worktree_for_ref(repo: Path, ref: str) -> Path | None:
    current_path: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{ref}" and current_path is not None:
            return current_path
    return None


def _assert_event_correlation(
    fixture: _Fixture,
    payload: dict[str, Any],
    *,
    reviewer: str,
    expected_verdict: str,
    committed: bool,
) -> None:
    event_id = payload.get("event_id")
    pointer = payload.get("review_feedback")
    assert isinstance(event_id, str) and isinstance(pointer, str), payload
    if committed:
        raw_events = _events_from_governed_ref(fixture)
        matches = [event for event in raw_events if event.event_id == event_id]
        assert len(matches) == 1, (
            f"event correlation failed: topology={fixture.topology.value}, "
            f"event_id={event_id}, status_ref="
            f"{placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.STATUS_STATE).ref}, "
            f"review_ref={placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref}"
        )
        status_event = matches[0]
        review = status_event.review_result
        assert status_event.event_id == event_id
        assert status_event.mission_slug == fixture.mission
        assert status_event.mission_id == fixture.mission_id
        assert status_event.wp_id == _WP_ID
        assert review is not None
        assert review.reviewer == reviewer
        assert review.verdict == expected_verdict
        assert review.reference == pointer
        return

    status_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.STATUS_STATE).ref
    governed_worktree = _worktree_for_ref(fixture.repo, status_ref)
    event_dirs = {fixture.status_dir, fixture.feature_dir}
    if governed_worktree is not None:
        event_dirs.add(governed_worktree / "kitty-specs" / fixture.mission)
    local_matches_by_id = {
        status_event.event_id: status_event for event_dir in event_dirs for status_event in read_events(event_dir) if status_event.event_id == event_id
    }
    local_matches = list(local_matches_by_id.values())
    assert len(local_matches) == 1
    review_result = local_matches[0].review_result
    assert local_matches[0].event_id == event_id
    assert local_matches[0].mission_slug == fixture.mission
    assert local_matches[0].mission_id == fixture.mission_id
    assert local_matches[0].wp_id == _WP_ID
    assert review_result is not None
    assert review_result.reviewer == reviewer
    assert review_result.verdict == expected_verdict
    assert review_result.reference == pointer
    governed_matches = [event for event in _events_from_governed_ref(fixture) if event.event_id == event_id]
    assert len(governed_matches) <= 1
    if governed_matches:
        governed_event = governed_matches[0]
        governed_review = governed_event.review_result
        assert governed_event.mission_slug == fixture.mission
        assert governed_event.mission_id == fixture.mission_id
        assert governed_event.wp_id == _WP_ID
        assert governed_review is not None
        assert governed_review.reviewer == reviewer
        assert governed_review.verdict == expected_verdict
        assert governed_review.reference == pointer


@contextmanager
def _tracked_queue(hits: list[str], repository: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    hits.append("queue")
    with acquire_verdict_save_queue(repository, timeout_seconds=timeout_seconds):
        yield


@pytest.mark.parametrize("topology", _TOPOLOGIES, ids=lambda value: value.value)
@pytest.mark.parametrize("auto_commit", _MODES, ids=("automatic", "local-only"))
def test_real_command_matrix_uses_governed_refs_and_explicit_commit_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    topology: MissionTopology,
    auto_commit: bool,
) -> None:
    fixture = _build_fixture(tmp_path, topology)
    body = f"{topology.value} {'automatic' if auto_commit else 'local-only'} verdict.\n"
    queue_hits: list[str] = []
    commit_hits: list[str] = []

    if auto_commit:
        real_commit = RealCoordCommitRouter.commit_artifact

        def tracked_commit(router: RealCoordCommitRouter, *args: Any, **kwargs: Any) -> Any:
            commit_hits.append("evidence_commit")
            return real_commit(router, *args, **kwargs)

        monkeypatch.setattr(
            persistence_module,
            "acquire_verdict_save_queue",
            lambda repository, timeout_seconds=10.0: _tracked_queue(queue_hits, repository, timeout_seconds),
        )
        monkeypatch.setattr(RealCoordCommitRouter, "commit_artifact", tracked_commit)
    else:

        def forbidden_queue(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("local-only verdict entered the automatic queue")

        def forbidden_commit(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("local-only verdict entered the commit router")

        monkeypatch.setattr(persistence_module, "acquire_verdict_save_queue", forbidden_queue)
        monkeypatch.setattr(RealCoordCommitRouter, "commit_artifact", forbidden_commit)

    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-matrix",
        auto_commit=auto_commit,
        body=body,
    )
    assert command.result.exit_code == 0, command.result.output
    payload = command.payload
    assert payload is not None and payload.get("result") == "success", command.result.output

    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    status_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.STATUS_STATE).ref
    relative = _relative_evidence_path(fixture, payload)
    local_path = fixture.repo / relative
    assert local_path.is_file()
    generated_evidence = local_path.read_bytes()
    if auto_commit:
        assert queue_hits == ["queue"]
        assert commit_hits == ["evidence_commit"]
        assert payload["durability_classification"] == "durable"
        assert payload["verdict_durably_persisted"] is True
        assert payload["durability_reason"] is None
        assert payload["destination_ref"] == review_ref
        evidence = _assert_git_blob_exact(fixture.repo, review_ref, relative, generated_evidence)
        assert b"reviewer_agent: reviewer-matrix" in evidence
        assert body.strip().encode() in evidence
        _assert_event_correlation(
            fixture,
            payload,
            reviewer="reviewer-matrix",
            expected_verdict="changes_requested",
            committed=True,
        )
    else:
        assert queue_hits == [] and commit_hits == []
        assert payload["durability_classification"] == "local_only"
        assert payload["verdict_durably_persisted"] is False
        assert payload["durability_reason"] == "no_auto_commit"
        assert payload["destination_ref"] is None
        assert body.strip().encode() in generated_evidence
        assert _git_show(fixture.repo, review_ref, relative).returncode != 0
        _assert_event_correlation(
            fixture,
            payload,
            reviewer="reviewer-matrix",
            expected_verdict="changes_requested",
            committed=False,
        )

    diagnostic = (
        f"topology={topology.value}, mode={'automatic' if auto_commit else 'local-only'}, status_ref={status_ref}, review_ref={review_ref}, payload={payload}"
    )
    assert status_ref and review_ref, diagnostic


def test_coordination_cell_rejects_a_deliberately_wrong_primary_ref(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.COORD)
    body = "coordination destination must not be inferred from primary.\n"
    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-wrong-ref",
        auto_commit=True,
        body=body,
    )
    assert command.result.exit_code == 0, command.result.output
    assert command.payload is not None
    relative = _relative_evidence_path(fixture, command.payload)
    governed_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    assert governed_ref != fixture.target_branch
    generated_evidence = (fixture.repo / relative).read_bytes()
    with pytest.raises(AssertionError, match="missing governed blob"):
        _assert_git_blob_exact(fixture.repo, fixture.target_branch, relative, generated_evidence)
    _assert_git_blob_exact(fixture.repo, governed_ref, relative, generated_evidence)


def test_exact_tuple_oracle_rejects_wrong_verdict_and_nonidentical_committed_bytes(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.SINGLE_BRANCH)
    body = "exact tuple causal control marker.\n"
    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-exact-control",
        auto_commit=True,
        body=body,
    )
    assert command.result.exit_code == 0, command.result.output
    payload = command.payload
    assert payload is not None
    with pytest.raises(AssertionError):
        _assert_event_correlation(
            fixture,
            payload,
            reviewer="reviewer-exact-control",
            expected_verdict="approved",
            committed=True,
        )
    _assert_event_correlation(
        fixture,
        payload,
        reviewer="reviewer-exact-control",
        expected_verdict="changes_requested",
        committed=True,
    )

    relative = _relative_evidence_path(fixture, payload)
    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    generated_evidence = (fixture.repo / relative).read_bytes()
    _assert_git_blob_exact(fixture.repo, review_ref, relative, generated_evidence)
    markers = (body.strip().encode(), b"reviewer_agent: reviewer-exact-control")
    mutants = (
        generated_evidence + b"# altered committed tail\n",
        generated_evidence[:-1],
    )
    for mutant in mutants:
        assert all(marker in mutant for marker in markers)
        fake_readback = subprocess.CompletedProcess(
            args=["git", "show"],
            returncode=0,
            stdout=mutant,
            stderr=b"",
        )
        with (
            patch(f"{__name__}._git_show_bytes", return_value=fake_readback),
            pytest.raises(AssertionError, match="governed blob mismatch"),
        ):
            _assert_git_blob_exact(
                fixture.repo,
                review_ref,
                relative,
                generated_evidence,
            )


def _reopen_after_rejection(fixture: _Fixture) -> None:
    request = TransitionRequest(
        feature_dir=fixture.status_dir,
        mission_slug=fixture.mission,
        repo_root=fixture.repo,
        wp_id=_WP_ID,
        to_lane="in_review",
        actor="topology-reopen",
        force=True,
        reason="reopen after representative rejection",
        execution_mode="worktree",
    )
    default_ports().coord.commit_status(request, capability=GuardCapability.STANDARD)


@pytest.mark.parametrize("target_lane", ("approved", "done"))
def test_real_command_records_approval_for_approved_and_done_targets(
    tmp_path: Path,
    target_lane: str,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.LANES)
    reviewer = "reviewer-reject"
    rejected = _invoke_verdict(
        fixture,
        reviewer=reviewer,
        auto_commit=True,
        body="representative rejection before approval.\n",
    )
    assert rejected.result.exit_code == 0, rejected.result.output
    _reopen_after_rejection(fixture)

    approved = _invoke_verdict(
        fixture,
        reviewer=reviewer,
        auto_commit=True,
        target_lane=target_lane,
    )
    assert approved.result.exit_code == 0, approved.result.output
    payload = approved.payload
    assert payload is not None and payload["durability_classification"] == "durable"
    assert payload["verdict_durably_persisted"] is True
    _assert_event_correlation(
        fixture,
        payload,
        reviewer=reviewer,
        expected_verdict="approved",
        committed=True,
    )
    relative = _relative_evidence_path(fixture, payload)
    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    generated_evidence = (fixture.repo / relative).read_bytes()
    evidence = _assert_git_blob_exact(fixture.repo, review_ref, relative, generated_evidence)
    assert f"Approved by {reviewer}".encode() in evidence
    assert f"reviewer_agent: {reviewer}".encode() in evidence


def test_automatic_commit_failure_is_never_mislabeled_local_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.SINGLE_BRANCH)

    def failed_commit(*_args: Any, **_kwargs: Any) -> Any:
        from specify_cli.agent_tasks_ports import CommitArtifactResult

        return CommitArtifactResult(
            status="error",
            placement_ref=fixture.target_branch,
            diagnostic="injected automatic commit failure",
        )

    monkeypatch.setattr(RealCoordCommitRouter, "commit_artifact", failed_commit)
    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-commit-failure",
        auto_commit=True,
    )
    assert command.result.exit_code != 0
    payload = command.payload
    assert payload is not None
    assert payload["durability_classification"] == "persistence_failed"
    assert payload["verdict_durably_persisted"] is False
    assert payload["durability_classification"] != "local_only"


@dataclass
class _CompensationObservation:
    evidence_verified_before_event: bool = False
    queue_held_during_compensation: bool = False
    deletion_target: str | None = None
    deletion_paths: tuple[str, ...] = ()


def _install_event_failure(
    monkeypatch: pytest.MonkeyPatch,
    fixture: _Fixture,
    observation: _CompensationObservation,
) -> None:
    def fail_after_evidence(st: Any, _ports: Any) -> None:
        signal = st.pending_verdict_write
        assert signal is not None and signal.durably_persisted
        relative = signal.artifact_path.relative_to(fixture.repo).as_posix()
        target = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
        observation.evidence_verified_before_event = _git_show(fixture.repo, target, relative).returncode == 0
        raise RuntimeError("injected status event failure after durable evidence")

    real_held = persistence_module._revert_committed_verdict_write_held

    def observe_held(st: Any, signal: Any) -> None:
        observation.queue_held_during_compensation = verdict_save_queue_is_held(fixture.repo)
        real_held(st, signal)

    monkeypatch.setattr(move_task_module, "_mt_execute", fail_after_evidence)
    monkeypatch.setattr(
        persistence_module,
        "_revert_committed_verdict_write_held",
        observe_held,
    )


def test_event_failure_reacquires_queue_and_removes_only_committed_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.LANES_WITH_COORD)
    observation = _CompensationObservation()
    _install_event_failure(monkeypatch, fixture, observation)
    from specify_cli import git as git_module

    real_safe_commit = git_module.safe_commit

    def observe_delete(*args: Any, **kwargs: Any) -> Any:
        observation.deletion_target = kwargs["target"].ref
        observation.deletion_paths = tuple(str(path) for path in kwargs["paths"])
        return real_safe_commit(*args, **kwargs)

    monkeypatch.setattr(git_module, "safe_commit", observe_delete)
    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-compensated",
        auto_commit=True,
    )
    assert command.result.exit_code != 0
    assert "injected status event failure" in command.result.output
    assert observation.evidence_verified_before_event
    assert observation.queue_held_during_compensation
    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    assert observation.deletion_target == review_ref
    (deletion_path,) = observation.deletion_paths
    relative = Path(deletion_path).relative_to(Path(deletion_path).anchor).as_posix()
    relative = relative.split("/kitty-specs/", 1)[-1]
    relative = f"kitty-specs/{relative}"
    assert _git_show(fixture.repo, review_ref, relative).returncode != 0
    log = _git(fixture.repo, "log", review_ref, "--name-only", "--pretty=format:").stdout
    assert Path(relative).name in log
    assert not any(event.review_result is not None and event.review_result.reviewer == "reviewer-compensated" for event in read_events(fixture.status_dir))


def test_compensation_failure_is_loud_and_leaves_only_noncurrent_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.COORD)
    observation = _CompensationObservation()
    _install_event_failure(monkeypatch, fixture, observation)
    from specify_cli import git as git_module

    def fail_delete(*args: Any, **kwargs: Any) -> Any:
        observation.deletion_target = kwargs["target"].ref
        observation.deletion_paths = tuple(str(path) for path in kwargs["paths"])
        raise RuntimeError("injected compensation deletion failure")

    monkeypatch.setattr(git_module, "safe_commit", fail_delete)
    command = _invoke_verdict(
        fixture,
        reviewer="reviewer-compensation-failed",
        auto_commit=True,
    )
    assert command.result.exit_code != 0
    assert observation.evidence_verified_before_event
    assert observation.queue_held_during_compensation
    assert observation.deletion_target == placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    assert "injected status event failure" in command.result.output
    assert "injected compensation deletion failure" in command.result.output
    assert "ALSO failed" in command.result.output
    relative_path = observation.deletion_paths[0].split("/kitty-specs/", 1)[-1]
    relative_path = f"kitty-specs/{relative_path}"
    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    assert _git_show(fixture.repo, review_ref, relative_path).returncode == 0
    assert not any(event.review_result is not None and event.review_result.reviewer == "reviewer-compensation-failed" for event in read_events(fixture.status_dir))


@contextmanager
def _unlocked(hits: list[str], label: str, *_args: Any, **_kwargs: Any) -> Iterator[None]:
    hits.append(f"lock:{label}")
    yield


@dataclass(frozen=True)
class _MutantResult:
    reviewer: str
    exit_code: int
    payload: dict[str, Any] | None
    output: str
    seam_hits: tuple[str, ...]


def _event_mutant_worker(
    repo_text: str,
    mission: str,
    reviewer: str,
    body: str,
    captured_self: Any,
    captured_peer: Any,
    release_self: Any,
    output: Any,
) -> None:
    repo = Path(repo_text)
    feedback = repo.parent / f"{mission}-{reviewer}-mutant.md"
    feedback.write_text(body, encoding="utf-8")
    hits: list[str] = []
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"SPECIFY_REPO_ROOT": str(repo)}))
        stack.enter_context(patch("specify_cli.status.emit._saas_fan_out"))
        lock_targets = {
            "tasks": "specify_cli.cli.commands.agent.tasks.feature_status_lock",
            "emit": "specify_cli.status.emit.feature_status_lock",
            "transaction": "specify_cli.coordination.transaction.feature_status_lock",
        }
        for label, target in lock_targets.items():
            stack.enter_context(
                patch(
                    target,
                    lambda *args, _label=label, **kwargs: _unlocked(hits, _label, *args, **kwargs),
                )
            )
        from specify_cli.status import store as status_store

        real_replace = status_store.os.replace
        first_status_replace = True

        def ordered_replace(source: Any, destination: Any) -> None:
            nonlocal first_status_replace
            if first_status_replace and Path(destination).name == "status.events.jsonl":
                first_status_replace = False
                hits.append("staged_event_replace")
                captured_self.set()
                if not captured_peer.wait(9):
                    raise TimeoutError("peer did not stage its stale event replacement")
                if release_self is not None and not release_self.wait(9):
                    raise TimeoutError("stale event writer was not released")
            real_replace(source, destination)

        stack.enter_context(patch.object(status_store.os, "replace", ordered_replace))
        old_cwd = Path.cwd()
        try:
            os.chdir(repo)
            result = CliRunner().invoke(
                agent_app,
                [
                    "tasks",
                    "move-task",
                    _WP_ID,
                    "--to",
                    "planned",
                    "--mission",
                    mission,
                    "--agent",
                    reviewer,
                    "--reviewer",
                    reviewer,
                    "--review-feedback-file",
                    str(feedback),
                    "--auto-commit",
                    "--json",
                ],
                catch_exceptions=True,
            )
        finally:
            os.chdir(old_cwd)
    output.put(
        _MutantResult(
            reviewer=reviewer,
            exit_code=result.exit_code,
            payload=_json_payload(result.output),
            output=result.output,
            seam_hits=tuple(hits),
        )
    )


def _missing_event_classification(
    fixture: _Fixture,
    results: list[_MutantResult],
) -> str:
    if any(result.exit_code != 0 or result.payload is None for result in results):
        return "command_failed"
    payloads = [result.payload for result in results if result.payload is not None]
    review_ref = placement_seam(fixture.repo, fixture.mission).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    for payload in payloads:
        relative = _relative_evidence_path(fixture, payload)
        if _git_show(fixture.repo, review_ref, relative).returncode != 0:
            return "missing_committed_evidence"
    event_ids = {str(payload["event_id"]) for payload in payloads}
    governed_ids = {event.event_id for event in _events_from_governed_ref(fixture)}
    return "missing_authoritative_event" if event_ids - governed_ids else "mutant_survived"


@pytest.mark.stress
def test_coordination_transaction_lock_negative_control_reports_exact_missing_event_cause(
    tmp_path: Path,
) -> None:
    fixture = _build_fixture(tmp_path, MissionTopology.LANES_WITH_COORD)
    ctx = multiprocessing.get_context("spawn")
    captured_a, captured_b, release_b = ctx.Event(), ctx.Event(), ctx.Event()
    output = ctx.Queue()
    processes = [
        ctx.Process(
            target=_event_mutant_worker,
            args=(
                str(fixture.repo),
                fixture.mission,
                reviewer,
                f"{reviewer} coordination transaction mutant.\n",
                captured,
                peer,
                release,
                output,
            ),
        )
        for reviewer, captured, peer, release in (
            ("reviewer-a", captured_a, captured_b, None),
            ("reviewer-b", captured_b, captured_a, release_b),
        )
    ]
    for process in processes:
        process.start()
    try:
        assert captured_a.wait(8) and captured_b.wait(8), "both stale event writes must stage"
        first = output.get(timeout=30)
        assert first.reviewer == "reviewer-a", first
        release_b.set()
        second = output.get(timeout=30)
        results = [first, second]
        assert all("lock:transaction" in result.seam_hits for result in results)
        assert all("staged_event_replace" in result.seam_hits for result in results)
        assert _missing_event_classification(fixture, results) == "missing_authoritative_event"
    except Empty as exc:
        raise AssertionError("timed out waiting for mutated real-command results") from exc
    finally:
        release_b.set()
        for process in processes:
            process.join(timeout=15)
            assert not process.is_alive(), f"spawn worker hung: pid={process.pid}"
            assert process.exitcode == 0, f"spawn worker crashed: pid={process.pid}, exit={process.exitcode}"
