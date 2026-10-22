"""Statistical performance proof for one uncontended durable verdict save.

The benchmark deliberately times the real ``move-task`` approval command rather
than the review-cycle writer in isolation.  Repository construction, mission
seeding, resolver patch installation, and per-round reset all happen in
``benchmark.pedantic``'s untimed setup callback.  Consequently each measured
round contains the checkout-wide queue, evidence allocation/write/commit,
governed-ref read-back, queue release, and authoritative event persistence, but
does not charge one-off fixture work to NFR-003.

Every round uses a fresh repository and a valid ``in_review -> approved``
transition.  Post-measurement assertions prove that a successful sample is
durable and correlated; a fast refusal, local-only result, absent event, or
uncommitted evidence can therefore never satisfy the benchmark.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    RealCoordCommitRouter,
    RealFsReader,
    RealGitOps,
    RealRender,
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.review.cycle import (
    create_rejected_review_cycle,
    resolve_review_cycle_pointer,
)
from specify_cli.status import TransitionRequest, read_events
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_VERDICT_SAVE_MEDIAN_QUARANTINE = pytest.mark.quarantine(
    reason="spec-kitty#901: wall-clock median budget flakes under shared-runner xdist load; passes alone and on serial re-run"
)

_MISSION = "verdict-save-performance"
_MISSION_ID = "01M0SBENCHMARK000000000000"
_WP_ID = "WP01"
_ROUNDS = 5
_WARMUP_ROUNDS = 1
_MEDIAN_BUDGET_SECONDS = 2.0
_SANITY_MAX_SECONDS = 10.0


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one checked Git command against the synthetic repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_bytes(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run Git without newline decoding when evidence bytes are authoritative."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Verdict Benchmark")
    _git(repo, "config", "user.email", "benchmark@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.autocrlf", "false")


def _seed_wp(repo: Path) -> Path:
    """Create one valid single-branch mission and its work-package prompt."""
    feature_dir = repo / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION}),
        encoding="utf-8",
    )
    (tasks_dir / f"{_WP_ID}-benchmark.md").write_text(
        "---\n"
        f"work_package_id: {_WP_ID}\n"
        "title: Verdict benchmark\n"
        "execution_mode: code_change\n"
        "agent: implementation-bot\n"
        "subtasks: [T001]\n"
        "owned_files:\n  - src/benchmark/**\n"
        "authoritative_surface: src/benchmark/\n"
        "---\n\n"
        f"# {_WP_ID}\n\n"
        "## Activity Log\n",
        encoding="utf-8",
    )
    config_dir = repo / ".kittify"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "protection:\n  protected_branches: []\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed benchmark mission")
    return feature_dir


def _at(sequence: int) -> str:
    return f"2026-01-01T00:{sequence:02d}:00+00:00"


def _seed_lane_event(
    feature_dir: Path,
    *,
    sequence: int,
    to_lane: Lane,
    review_result: ReviewResult | None = None,
) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"benchmark-{sequence}-{to_lane.value}",
            mission_slug=_MISSION,
            wp_id=_WP_ID,
            from_lane=Lane.PLANNED,
            to_lane=to_lane,
            at=_at(sequence),
            actor="benchmark-fixture",
            force=True,
            execution_mode="worktree",
            review_result=review_result,
        ),
    )


def _prepare_review_state(repo: Path, feature_dir: Path) -> None:
    """Seed a prior rejection, then reopen the WP for a genuine approval."""
    _seed_lane_event(feature_dir, sequence=0, to_lane=Lane.IN_REVIEW)
    rejected = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=_MISSION,
        wp_id=_WP_ID,
        wp_slug=f"{_WP_ID}-benchmark",
        body="Correctness feedback before the measured approval.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
        commit_router=RealCoordCommitRouter(),
    )
    _seed_lane_event(
        feature_dir,
        sequence=1,
        to_lane=Lane.PLANNED,
        review_result=rejected.review_result,
    )
    _seed_lane_event(feature_dir, sequence=2, to_lane=Lane.IN_REVIEW)
    # The command starts from a normal clean checkout.  This final fixture
    # commit is setup work and is never part of a measured interval.
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed in-review benchmark state")


@dataclass
class _ProductionDelegatingRouter:
    """Fix only the fixture's write directory; delegate both writes for real."""

    feature_dir: Path
    delegate: RealCoordCommitRouter = field(default_factory=RealCoordCommitRouter)

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        assert mission.mission_slug == _MISSION
        return self.feature_dir

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        return self.delegate.commit_status(request, capability=capability)

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        return self.delegate.commit_artifact(
            mission,
            paths,
            message,
            kind=kind,
            policy=policy,
        )


@dataclass
class _PreparedRound:
    repo: Path
    feature_dir: Path
    environment: AbstractContextManager[None]
    payload: dict[str, object] | None = None


def _command_args() -> _MoveTaskArgs:
    return _MoveTaskArgs(
        task_id=_WP_ID,
        to="approved",
        mission=_MISSION,
        agent=None,
        assignee=None,
        shell_pid=None,
        note="Benchmark approval",
        review_feedback_file=None,
        approval_ref="approval:benchmark",
        reviewer="reviewer-renata",
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=True,
        json_output=True,
    )


def _ports(repo: Path, feature_dir: Path) -> TasksPorts:
    return TasksPorts(
        fs=RealFsReader(),
        coord=_ProductionDelegatingRouter(feature_dir),
        git=RealGitOps(repo),
        render=RealRender(),
    )


def _enter_command_environment(repo: Path) -> AbstractContextManager[None]:
    environment = setup_mocked_env(
        repo,
        mission_slug=_MISSION,
        target_branch="main",
        auto_commit_default=True,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    )
    environment.__enter__()
    return environment


def _invoke_real_reviewer_command(args: _MoveTaskArgs, ports: TasksPorts) -> None:
    """Timed callable: the complete production reviewer-command orchestrator."""
    _do_move_task(args, ports=ports)


def _approval_events(feature_dir: Path) -> list[StatusEvent]:
    return [event for event in read_events(feature_dir) if event.wp_id == _WP_ID and event.review_result is not None and event.review_result.verdict == "approved"]


def _assert_durable_round(round_: _PreparedRound, payload: dict[str, object]) -> None:
    """Prove the command's event points to exact evidence bytes at its Git ref."""
    assert payload["result"] == "success"
    assert payload["verdict_durably_persisted"] is True
    assert payload["durability_classification"] == "durable"
    assert payload["durability_reason"] is None

    evidence_ref = payload["evidence_ref"]
    destination_ref = payload["destination_ref"]
    review_feedback = payload["review_feedback"]
    assert isinstance(evidence_ref, str)
    assert isinstance(destination_ref, str)
    assert isinstance(review_feedback, str)

    evidence_path = round_.repo / evidence_ref
    assert evidence_path.is_file()
    committed = _git_bytes(round_.repo, "show", f"{destination_ref}:{evidence_ref}")
    assert committed.stdout == evidence_path.read_bytes()

    resolved = resolve_review_cycle_pointer(round_.repo, review_feedback)
    assert resolved.path is not None
    assert resolved.path.resolve() == evidence_path.resolve()

    events = _approval_events(round_.feature_dir)
    assert len(events) == 1
    event = events[0]
    assert event.review_result is not None
    assert event.review_result.reference == review_feedback
    assert event.review_result.feedback_path == str(evidence_path)
    assert event.evidence is not None
    assert event.evidence.review.reference == review_feedback
    assert event.evidence.review.verdict == "approved"
    round_.payload = payload


def _decode_payloads(output: str) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        decoded: Any = json.loads(stripped)
        if isinstance(decoded, dict) and decoded.get("result") == "success":
            payloads.append(decoded)
    return payloads


def test_uncontended_verdict_fixture_runs_the_real_durable_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T026 smoke: the representative fixture completes one durable save."""
    repo = tmp_path / "smoke"
    _init_repo(repo)
    feature_dir = _seed_wp(repo)
    _prepare_review_state(repo, feature_dir)
    environment = _enter_command_environment(repo)
    try:
        _invoke_real_reviewer_command(_command_args(), _ports(repo, feature_dir))
    finally:
        environment.__exit__(None, None, None)

    payloads = _decode_payloads(capsys.readouterr().out)
    (payload,) = payloads
    round_ = _PreparedRound(repo=repo, feature_dir=feature_dir, environment=environment)
    _assert_durable_round(round_, payload)


@pytest.mark.performance
@pytest.mark.benchmark(group="review")
@_VERDICT_SAVE_MEDIAN_QUARANTINE
def test_uncontended_real_verdict_save_median_is_below_two_seconds(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    benchmark: BenchmarkFixture,
) -> None:
    """T027/T028: statistically prove SC-006 on complete durable saves."""
    prepared: list[_PreparedRound] = []
    active: list[_PreparedRound] = []

    def _setup() -> tuple[tuple[_MoveTaskArgs, TasksPorts], dict[str, object]]:
        sample = len(prepared)
        repo = tmp_path / f"sample-{sample}"
        _init_repo(repo)
        feature_dir = _seed_wp(repo)
        _prepare_review_state(repo, feature_dir)
        environment = _enter_command_environment(repo)
        round_ = _PreparedRound(
            repo=repo,
            feature_dir=feature_dir,
            environment=environment,
        )
        prepared.append(round_)
        active.append(round_)
        return ((_command_args(), _ports(repo, feature_dir)), {})

    def _teardown(_args: _MoveTaskArgs, _ports_: TasksPorts) -> None:
        round_ = active.pop()
        round_.environment.__exit__(None, None, None)

    # pytest-benchmark 5.2.3 ships ``pedantic`` without a typed signature.
    benchmark.pedantic(  # type: ignore[no-untyped-call]
        _invoke_real_reviewer_command,
        setup=_setup,
        teardown=_teardown,
        rounds=_ROUNDS,
        warmup_rounds=_WARMUP_ROUNDS,
        iterations=1,
    )

    payloads = _decode_payloads(capsys.readouterr().out)
    assert len(payloads) == len(prepared) == _ROUNDS + _WARMUP_ROUNDS
    for round_, payload in zip(prepared, payloads, strict=True):
        _assert_durable_round(round_, payload)

    assert benchmark.stats is not None
    stats = benchmark.stats.stats
    assert stats.median < _MEDIAN_BUDGET_SECONDS, (
        f"SC-006: median uncontended durable verdict save was {stats.median:.3f}s; required < {_MEDIAN_BUDGET_SECONDS:.1f}s"
    )
    assert stats.max < _SANITY_MAX_SECONDS, f"slowest uncontended durable verdict save was {stats.max:.3f}s; this exceeds the loose secondary sanity ceiling"
