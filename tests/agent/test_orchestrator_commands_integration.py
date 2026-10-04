"""Integration tests for orchestrator_api commands.

Uses CliRunner to invoke commands against a fake mission directory
with a real event log (no subprocess, no git).

Exception: ``TestAcceptMission.test_all_done_accepted`` /
``test_all_approved_accepted`` (#4934, WP03 of accept-fails-closed-01M3HS4V)
use ``_make_acceptable_mission`` instead of ``_make_mission`` -- with
``accept-mission`` now applying the host readiness verdict, a mission with no
real git repo, no ``lanes.json`` and no acceptance matrix can never reach
``summary.ok``, so these two positive-control tests need the real thing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
from specify_cli.status.models import TransitionRequest
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest

import pytest

pytestmark = pytest.mark.git_repo

runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


# ── Fixtures ──────────────────────────────────────────────────────


def _write_tasks_index(mission_dir: Path, wp_rows: dict[str, int]) -> None:
    """Write ``tasks.md`` with a ``## WPxx`` section + ``- [x] T### …`` rows per WP.

    Mirrors the real tasks.md shape counted by
    ``core.subtask_rows.count_wp_section_subtask_rows`` — a heading whose first
    ``WPxx`` token names the section, followed by canonical checked subtask
    rows. All rows are checked ([x]) so ``_infer_subtasks_complete`` reports the
    WP complete and the in_progress -> for_review gate passes.
    """
    lines = ["# Tasks", ""]
    task_no = 1
    for wp_id, count in wp_rows.items():
        lines.append(f"## {wp_id} Test {wp_id}")
        lines.append("")
        for _ in range(count):
            lines.append(f"- [x] T{task_no:03d} subtask for {wp_id}")
            task_no += 1
        lines.append("")
    (mission_dir / "tasks.md").write_text("\n".join(lines), encoding="utf-8")


def _make_mission(tmp_path: Path, mission_slug: str = "099-test-mission") -> tuple[Path, Path]:
    """Create a minimal mission directory with tasks.

    Returns:
        (repo_root, mission_dir)
    """
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\nlane: planned\ndependencies: []\nsubtasks: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    # Top-level tasks.md index carrying the canonical checkbox rows the
    # in_progress -> for_review subtask-completeness gate (#846 / #2574) reads.
    # Rows are complete ([x]) by default so the standard "advance to for_review"
    # setups pass; tests needing an INCOMPLETE WP tailor their own setup.
    _write_tasks_index(mission_dir, {"WP01": 2, "WP02": 2})

    meta = {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Test Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-18T00:00:00+00:00",
        "status_phase": 1,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _seed_planned_events(mission_dir, mission_slug, ("WP01", "WP02"))
    return repo_root, mission_dir


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _commit_all(repo_root: Path, message: str) -> None:
    """Commit every change (e.g. freshly-appended status events) so the
    acceptance readiness check's ``git_dirty`` gate sees a clean tree."""
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)


def _make_acceptable_mission(tmp_path: Path, mission_slug: str = "099-test-mission") -> tuple[Path, Path]:
    """A REAL-git variant of ``_make_mission`` for the two accept-mission
    positive-control tests below (#4934, WP03).

    ``accept-mission`` now applies the host readiness verdict
    (``collect_feature_summary(..., strict_metadata=True).ok``), which
    requires a real git repo (branch resolution), the path-convention
    dirs (``src``/``tests``/``docs``), ``spec.md``/``plan.md``, a
    ``lanes.json`` manifest, and a passing acceptance matrix -- none of
    which the git-free ``_make_mission`` fixture provides. Everything else
    (mission dir layout, WP task files, tasks.md index, meta.json shape)
    mirrors ``_make_mission`` exactly so the two repaired tests keep
    proving what they always proved.
    """
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(repo_root)], check=True, capture_output=True)
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")

    for convention_dir in ("src", "tests", "docs"):
        (repo_root / convention_dir).mkdir(parents=True, exist_ok=True)
        (repo_root / convention_dir / ".gitkeep").write_text("", encoding="utf-8")
    (mission_dir / "contracts").mkdir(parents=True, exist_ok=True)
    (mission_dir / "contracts" / ".gitkeep").write_text("", encoding="utf-8")

    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\nlane: planned\ndependencies: []\nsubtasks: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    _write_tasks_index(mission_dir, {"WP01": 2, "WP02": 2})
    for fname in ("spec.md", "plan.md"):
        (mission_dir / fname).write_text(f"# {fname}\nDone.\n", encoding="utf-8")

    mission_id = derive_mission_id(mission_slug)
    meta = {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mission_id[:8],
        "friendly_name": "Test Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-18T00:00:00+00:00",
        "status_phase": 1,
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _seed_planned_events(mission_dir, mission_slug, ("WP01", "WP02"))

    write_single_lane_manifest(mission_dir, wp_ids=("WP01", "WP02"), target_branch="main", mission_id=mission_id)
    write_acceptance_matrix(
        mission_dir,
        AcceptanceMatrix(
            mission_slug=mission_slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC-001",
                    description="WP01/WP02 complete as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                    evidence="test evidence",
                )
            ],
        ),
    )

    _commit_all(repo_root, "seed acceptable mission")
    return repo_root, mission_dir


from tests.status.conftest import seed_wp_to_planned as _seed_wp_to_planned


def _seed_planned_events(mission_dir: Path, mission_slug: str, wp_ids: tuple[str, ...]) -> None:
    """Seed WPs out of the non-display 'genesis' state into 'planned'."""
    for wp_id in wp_ids:
        _seed_wp_to_planned(mission_dir, wp_id, slug=mission_slug)


def _valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "test-orch",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _emit_event(mission_dir: Path, wp_id: str, from_lane: str, to_lane: str, actor: str = "test") -> None:
    """Helper to emit a status event directly.

    WPs are seeded to 'planned' by the mission factories (_make_mission /
    _make_mission_with_suffixed_wps), so transitions starting at 'planned' are
    legal without an additional genesis -> planned seed here.
    """
    from specify_cli.status.emit import emit_status_transition

    slug = mission_dir.parent.parent.name + "-" + mission_dir.name
    if to_lane == "in_progress" and from_lane == "planned":
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=slug, wp_id=wp_id, to_lane="claimed", actor=actor))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=slug, wp_id=wp_id, to_lane="in_progress", actor=actor))
    else:
        emit_status_transition(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=slug,
                wp_id=wp_id,
                to_lane=to_lane,
                actor=actor,
            )
        )


def _emit_planned_to_done(mission_dir: Path, mission_slug: str, wp_id: str, actor: str = "test") -> None:
    """Transition a WP all the way to done."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult

    # ``policy_metadata={"agent": actor}`` on the planned -> claimed hop is
    # what the reducer's implementer-of-record projection reads (#4786,
    # ``status/reducer.py::_project_implementer_of_record``) -- without it a
    # strict-metadata readiness check (accept-mission, #4934) reports the WP
    # as "never claimed" even though it reached done/approved here.
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="claimed",
            actor=actor,
            policy_metadata={"agent": actor},
        )
    )
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="in_progress", actor=actor))
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="for_review", actor=actor))
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="in_review", actor=actor))
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="done",
            actor=actor,
            evidence={
                "review": {
                    "reviewer": "reviewer-agent",
                    "verdict": "approved",
                    "reference": "review-001",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-agent",
                verdict="approved",
                reference="review-001",
            ),
        )
    )


def _emit_planned_to_approved(
    mission_dir: Path,
    mission_slug: str,
    wp_id: str,
    actor: str = "test",
) -> None:
    """Transition a WP to approved."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult

    # See ``_emit_planned_to_done``'s comment on ``policy_metadata``.
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="claimed",
            actor=actor,
            policy_metadata={"agent": actor},
        )
    )
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="in_progress", actor=actor))
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="for_review", actor=actor))
    emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id=wp_id, to_lane="in_review", actor=actor))
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="approved",
            actor=actor,
            evidence={
                "review": {
                    "reviewer": "reviewer-agent",
                    "verdict": "approved",
                    "reference": "review-001",
                }
            },
            review_result=ReviewResult(
                reviewer="reviewer-agent",
                verdict="approved",
                reference="review-001",
            ),
        )
    )


def _emit_planned_to_canceled(
    mission_dir: Path,
    mission_slug: str,
    wp_id: str,
    *,
    reason_source: str | None,
    actor: str = "test",
) -> None:
    """Cancel a planned WP, stamping the provenance discriminator (FR-009).

    ``reason_source="operator"`` marks a documented (operator-authored)
    cancellation whose dependents must become claimable; any other value (or
    ``None``) is a synthetic cancellation that stays dependency-blocking.
    """
    from specify_cli.status.emit import emit_status_transition

    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane="canceled",
            actor=actor,
            reason="replan",
            reason_source=reason_source,
        )
    )


# ── contract-version ──────────────────────────────────────────────


class TestContractVersion:
    def test_envelope_shape_and_version(self, tmp_path):
        result = runner.invoke(app, ["contract-version"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["error_code"] is None
        assert data["data"]["api_version"] == CONTRACT_VERSION
        assert "min_supported_provider_version" in data["data"]
        assert data["command"] == "orchestrator-api.contract-version"


# ── mission-state ─────────────────────────────────────────────────


class TestMissionState:
    def test_mission_state_with_event_log(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # Emit one transition
        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="test-actor"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["mission_slug"] == mission_slug
        wps = {wp["wp_id"]: wp for wp in data["data"]["work_packages"]}
        assert "WP01" in wps
        assert wps["WP01"]["lane"] == "claimed"

    def test_mission_not_found(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--mission", "nonexistent-mission"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "MISSION_NOT_FOUND"

    def test_mission_state_does_not_write_status_snapshot(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        status_path = mission_dir / "status.json"
        assert not status_path.exists()

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        assert not status_path.exists()


# ── list-ready ────────────────────────────────────────────────────


class TestListReady:
    def test_planned_wp_with_satisfied_deps_is_ready(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["list-ready", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["mission_slug"] == mission_slug
        ready = {wp["wp_id"] for wp in data["data"]["ready_work_packages"]}
        # Both WP01 and WP02 have no deps, so both should be ready
        assert "WP01" in ready
        assert "WP02" in ready

    def test_in_progress_wp_not_in_ready(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="test"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="test"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["list-ready", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        ready_ids = {wp["wp_id"] for wp in data["data"]["ready_work_packages"]}
        assert "WP01" not in ready_ids
        assert "WP02" in ready_ids

    def test_list_ready_does_not_write_status_snapshot(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        status_path = mission_dir / "status.json"
        assert not status_path.exists()

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["list-ready", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        assert not status_path.exists()

    def test_dep_blocked_wp_excluded_from_ready(self, tmp_path):
        """A planned WP whose dependency is not approved/done is filtered out of ready."""
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )

        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="test"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="test"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["list-ready", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        ready_ids = {wp["wp_id"] for wp in json.loads(result.output)["data"]["ready_work_packages"]}
        # WP01 is in_progress (not planned); WP02's dependency is unsatisfied. Neither ready.
        assert ready_ids == set()

    def test_dep_satisfied_by_approved_makes_wp_ready(self, tmp_path):
        """An `approved` dependency (not yet merged) satisfies list-ready."""
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )
        _emit_planned_to_approved(mission_dir, mission_slug, "WP01")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["list-ready", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        ready_ids = {wp["wp_id"] for wp in json.loads(result.output)["data"]["ready_work_packages"]}
        # WP01 is approved (not planned) so not itself ready; WP02's dependency is
        # satisfied by `approved`, so WP02 is ready.
        assert "WP02" in ready_ids
        assert "WP01" not in ready_ids


# ── start-implementation ──────────────────────────────────────────


class TestStartImplementation:
    def test_no_policy_returns_error(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                ["start-implementation", "--mission", "099-test-mission", "--wp", "WP01", "--actor", "claude"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "POLICY_METADATA_REQUIRED"

    def test_dangerous_flags_secret_returns_json_error_without_leak(self, tmp_path):
        policy = json.loads(_valid_policy_json())
        policy["dangerous_flags"] = ["AWS_SECRET_ACCESS_KEY=abc123"]

        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                "099-test-mission",
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                json.dumps(policy),
            ],
        )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "POLICY_VALIDATION_FAILED"
        assert "dangerous_flags[0]" in data["data"]["message"]
        assert "AWS_SECRET_ACCESS_KEY" not in result.output
        assert "abc123" not in result.output

    def test_planned_wp_composite_transition(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["from_lane"] == "planned"
        assert data["data"]["to_lane"] == "in_progress"
        assert data["data"]["policy_metadata_recorded"] is True
        assert data["data"]["no_op"] is False
        from specify_cli.status.store import read_events

        events = read_events(mission_dir)
        # Exclude the genesis->planned seeds; assert only the composite
        # start-implementation transitions for WP01.
        wp01_transitions = [(event.from_lane, event.to_lane) for event in events if event.wp_id == "WP01" and str(event.from_lane) != "genesis"]
        assert wp01_transitions == [
            ("planned", "claimed"),
            ("claimed", "in_progress"),
        ]

    def test_dependency_blocked_wp_rejected_without_events(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        wp02_path = mission_dir / "tasks" / "WP02.md"
        wp02_path.write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )

        from specify_cli.status.emit import emit_status_transition
        from specify_cli.status.store import read_events

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="seed"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="seed"))
        before_events = read_events(mission_dir)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP02",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "DEPENDENCIES_NOT_SATISFIED"
        assert data["data"]["wp_id"] == "WP02"
        assert data["data"]["unsatisfied_dependencies"] == ["WP01"]
        assert read_events(mission_dir) == before_events

    def test_dependency_satisfied_by_approved_allows_start(self, tmp_path):
        """An `approved` dependency unblocks starting the dependent WP.

        ``done`` is emitted only by the whole-mission merge, so requiring it would
        deadlock the chain; ``approved`` (review passed, merge pending) must allow
        the dependent WP to start.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )
        _emit_planned_to_approved(mission_dir, mission_slug, "WP01")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP02",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP02"
        assert data["data"]["to_lane"] == "in_progress"

    def test_operator_canceled_dependency_admits_claim(self, tmp_path):
        """FR-009: start-implementation (the external-API CLAIM gate) admits a
        dependent of a canceled-with-operator-provenance dependency.

        A documented (operator-authored) cancellation is an acceptable ending,
        so WP02 must no longer be stranded on the orchestrator-api claim path —
        parity with implement.py's ``_ensure_wp_claim_preconditions``.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )
        _emit_planned_to_canceled(mission_dir, mission_slug, "WP01", reason_source="operator")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP02",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP02"
        assert data["data"]["to_lane"] == "in_progress"

    def test_synthetic_canceled_dependency_still_blocks_claim(self, tmp_path):
        """FR-009: a synthetic (undocumented) cancellation stays dependency-blocking.

        Without operator provenance the cancellation is not an acceptable
        ending, so start-implementation must still reject WP02 fail-closed.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )
        _emit_planned_to_canceled(mission_dir, mission_slug, "WP01", reason_source="synthetic")

        from specify_cli.status.store import read_events

        before_events = read_events(mission_dir)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP02",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "DEPENDENCIES_NOT_SATISFIED"
        assert data["data"]["wp_id"] == "WP02"
        assert data["data"]["unsatisfied_dependencies"] == ["WP01"]
        assert read_events(mission_dir) == before_events

    def test_resume_in_progress_wp_not_blocked_by_unsatisfied_dependency(self, tmp_path):
        """Re-running start on an already in_progress WP must not be dep-gated.

        The dependency gate guards only the not-yet-started claim transition. A WP
        that is already in_progress (e.g. its dependency's approval was later
        reverted) must still resume as a no-op rather than being rejected.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        (mission_dir / "tasks" / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\nlane: planned\ndependencies: [WP01]\nsubtasks: []\n---\n\n# WP02\n",
            encoding="utf-8",
        )

        from specify_cli.status.emit import emit_status_transition

        # WP02 was started earlier, when WP01 was still approved; WP01's approval
        # was later reverted to planned. Reconstruct that historical in_progress
        # state directly: the claim happened when the dependency WAS satisfied, so
        # force the setup transition past the (now-unsatisfied) dependency gate
        # with a reason. This only stages the precondition — the behaviour under
        # test is that the LATER, un-forced resume below is not re-gated.
        emit_status_transition(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=mission_slug,
                wp_id="WP02",
                to_lane="claimed",
                actor="claude",
                force=True,
                reason="setup: claimed while WP01 was approved",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=mission_slug,
                wp_id="WP02",
                to_lane="in_progress",
                actor="claude",
                force=True,
                reason="setup: started while WP01 was approved",
            )
        )

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP02",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP02"
        assert data["data"]["no_op"] is True

    def test_claimed_same_actor_resumes_to_in_progress(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="claude"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["from_lane"] == "claimed"
        assert data["data"]["to_lane"] == "in_progress"
        assert data["data"]["no_op"] is False

    def test_already_in_progress_same_actor_noop(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # First put WP01 in_progress as claude
        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="claude"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="claude"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["no_op"] is True

    def test_already_claimed_different_actor_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # Put WP01 in claimed state as "other-agent"
        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="other-agent"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "WP_ALREADY_CLAIMED"

    @pytest.mark.parametrize(("actor", "admitted"), [("claude", True), ("gemini", False)])
    def test_in_progress_after_rework_verdict_admits_only_the_implementer(self, tmp_path, actor, admitted):
        """#5377: after a reviewer's ``in_review -> in_progress`` verdict the slot holds the
        reviewer; the implementer of record resumes (no-op), a third tool is refused."""
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        from specify_cli.status.emit import emit_status_transition
        from specify_cli.status.models import ReviewResult

        rework_ref = "review-cycle://099-test-mission/WP01/review-cycle-1.md"
        for to_lane in ("claimed", "in_progress", "for_review"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=mission_dir,
                    mission_slug=mission_slug,
                    wp_id="WP01",
                    to_lane=to_lane,
                    actor="claude",
                    force=to_lane == "for_review",
                    reason="fixture",
                )
            )
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_review", actor="codex"))
        emit_status_transition(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=mission_slug,
                wp_id="WP01",
                to_lane="in_progress",
                actor="codex",
                review_ref=rework_ref,
                review_result=ReviewResult(reviewer="codex", verdict="changes_requested", reference=rework_ref),
            )
        )

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                ["start-implementation", "--mission", mission_slug, "--wp", "WP01", "--actor", actor, "--policy", _valid_policy_json()],
            )

        data = json.loads(result.output)
        if admitted:
            assert result.exit_code == 0, result.output
            assert data["data"]["no_op"] is True
        else:
            assert result.exit_code == 1, result.output
            assert data["error_code"] == "WP_ALREADY_CLAIMED"


# ── start-review ──────────────────────────────────────────────────


class TestStartReview:
    def test_no_review_ref_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-review",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "TRANSITION_REJECTED"

    def test_valid_start_review(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # Put WP01 in for_review state
        from specify_cli.status.emit import emit_status_transition

        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="claimed", actor="claude"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="in_progress", actor="claude"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug=mission_slug, wp_id="WP01", to_lane="for_review", actor="claude"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-review",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "reviewer",
                    "--policy",
                    _valid_policy_json(),
                    "--review-ref",
                    "review-feedback-001",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["to_lane"] == "in_review"
        assert data["data"]["policy_metadata_recorded"] is True


# ── transition ────────────────────────────────────────────────────


class TestTransition:
    def test_invalid_transition_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            # planned -> done is not a valid transition
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "done",
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "TRANSITION_REJECTED"

    def test_terminal_transition_no_policy_required(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            # planned -> canceled should succeed without --policy
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "canceled",
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["to_lane"] == "canceled"
        assert data["data"]["policy_metadata_recorded"] is False

    def test_run_affecting_transition_requires_policy(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "claimed",
                    "--actor",
                    "claude",
                    # no --policy
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "POLICY_METADATA_REQUIRED"

    def test_transition_passes_review_handoff_flags_to_status_emit(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path, "099-test-feature")
        mission_slug = "099-test-feature"

        emit_mock = MagicMock()
        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.coordination.status_transition.emit_status_transition_transactional",
                emit_mock,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "for_review",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                    "--subtasks-complete",
                    "--implementation-evidence-present",
                ],
            )

        assert result.exit_code == 0, result.output
        req = emit_mock.call_args.args[0]
        assert req.subtasks_complete is True
        assert req.implementation_evidence_present is True

    def test_transition_passes_done_evidence_to_status_emit(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path, "099-test-feature")
        mission_slug = "099-test-feature"

        emit_mock = MagicMock()
        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.coordination.status_transition.emit_status_transition_transactional",
                emit_mock,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "done",
                    "--actor",
                    "reviewer",
                    "--review-ref",
                    "review-001",
                    "--review-result-json",
                    '{"reviewer":"reviewer","verdict":"approved","reference":"review-001"}',
                    "--evidence-json",
                    '{"review":{"reviewer":"reviewer","verdict":"approved","reference":"review-001"}}',
                ],
            )

        assert result.exit_code == 0, result.output
        req = emit_mock.call_args.args[0]
        assert req.review_ref == "review-001"
        assert req.review_result.reviewer == "reviewer"
        assert req.review_result.verdict == "approved"
        assert req.review_result.reference == "review-001"
        assert req.evidence == {
            "review": {
                "reviewer": "reviewer",
                "verdict": "approved",
                "reference": "review-001",
            }
        }

    def test_transition_rejects_invalid_evidence_json(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path, "099-test-feature")
        mission_slug = "099-test-feature"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--to",
                    "done",
                    "--actor",
                    "reviewer",
                    "--evidence-json",
                    '{"review":',
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "USAGE_ERROR"

    @pytest.mark.parametrize(
        "payload",
        [
            '{"reviewer":',
            "[]",
            '{"reviewer":"reviewer","verdict":"approved"}',
            '{"reviewer":"reviewer","verdict":"maybe","reference":"review-001"}',
        ],
    )
    def test_transition_rejects_invalid_review_result_json(self, tmp_path, payload):
        repo_root, _ = _make_mission(tmp_path, "099-test-feature")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    "099-test-feature",
                    "--wp",
                    "WP01",
                    "--to",
                    "done",
                    "--actor",
                    "reviewer",
                    "--review-result-json",
                    payload,
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "USAGE_ERROR"


# ── append-history ────────────────────────────────────────────────
#
# WP08 (runtime-state-eviction, FR-007 / T031): ``append-history`` no longer
# mutates the WP prompt file or calls ``safe_commit`` -- it emits a ``note``
# ``InnerStateChanged`` annotation via WP01's ``emit_inner_state_changed``.
# The old safe-commit-failure-mode tests (``SAFE_COMMIT_PROTECTED_BRANCH`` /
# ``SAFE_COMMIT_BACKSTOP`` / ``SAFE_COMMIT_NOT_A_WORKTREE``) pinned a git-commit
# code path that no longer exists on this command; they are replaced below by
# the event-sourced contract (annotation persisted, WP file byte-unchanged, a
# failed emit still surfaces a structured envelope).


class TestAppendHistory:
    def test_appends_entry_and_returns_history_id(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "append-history",
                    "--mission",
                    mission_slug,
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--note",
                    "Started implementation",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["history_entry_id"].startswith("hist-")
        assert data["data"]["wp_id"] == "WP01"

    def test_note_annotation_persisted_and_wp_file_unchanged(self, tmp_path):
        """WP08 / FR-007: the note lands as an event, the WP file never changes."""
        from specify_cli.status.store import read_event_stream

        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        wp_path = mission_dir / "tasks" / "WP01.md"
        original = wp_path.read_text(encoding="utf-8")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "append-history",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--note",
                    "Started implementation",
                ],
            )

        assert result.exit_code == 0, result.output
        assert wp_path.read_text(encoding="utf-8") == original

        stream = read_event_stream(mission_dir)
        notes = [ann for ann in stream.annotations if ann.wp_id == "WP01" and ann.delta.note is not None]
        assert len(notes) == 1
        assert "Started implementation" in notes[0].delta.note
        assert notes[0].actor == "claude"

    def test_emit_failure_surfaces_structured_error_envelope(self, tmp_path):
        """A failed emit still returns ``_fail``'s structured envelope (WP08 DoD).

        Never a bare traceback -- the orchestrator-api machine contract always
        emits a single JSON error object on failure.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        wp_path = mission_dir / "tasks" / "WP01.md"
        original = wp_path.read_text(encoding="utf-8")

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                # WP02 (verdict-seam-boundary-hardening-01KZG179, T006): the
                # command now resolves this via ``from specify_cli.status
                # import emit_inner_state_changed`` (the facade symbol),
                # not the ``status.emit`` submodule object, so the mock
                # target moves to the facade's own already-bound attribute.
                "specify_cli.status.emit_inner_state_changed",
                side_effect=ValueError("boom"),
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "append-history",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--note",
                    "Started implementation",
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "HISTORY_COMMIT_FAILED"
        assert wp_path.read_text(encoding="utf-8") == original

    def test_succeeds_without_git_no_commit_required(self, tmp_path):
        """WP08 regression pin: ``append-history`` needs no git commit at all now.

        ``_make_mission`` is a deliberately git-free fixture (module docstring:
        "no subprocess, no git"). Historically this command still shelled out to
        ``safe_commit`` internally (mocked away by every other test in this
        class); now that the write is a pure event-log annotation, a bare
        non-git ``repo_root`` is no longer a failure mode.
        """
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        wp_path = mission_dir / "tasks" / "WP01.md"
        original = wp_path.read_text(encoding="utf-8")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "append-history",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "claude",
                    "--note",
                    "Started implementation",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert wp_path.read_text(encoding="utf-8") == original

    def test_wp_not_found_error(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "append-history",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP99",
                    "--actor",
                    "claude",
                    "--note",
                    "nonexistent",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "WP_NOT_FOUND"


# ── accept-mission ────────────────────────────────────────────────


class TestAcceptMission:
    def test_all_done_accepted(self, tmp_path):
        repo_root, mission_dir = _make_acceptable_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # Transition all WPs to done
        _emit_planned_to_done(mission_dir, mission_slug, "WP01")
        _emit_planned_to_done(mission_dir, mission_slug, "WP02")
        _commit_all(repo_root, "WP01/WP02 -> done")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "accept-mission",
                    "--mission",
                    mission_slug,
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["mission_slug"] == mission_slug
        assert data["data"]["accepted"] is True
        assert data["data"]["accepted_wps"] == ["WP01", "WP02"]
        assert data["data"]["approved_wps"] == []
        assert data["data"]["done_wps"] == ["WP01", "WP02"]
        assert data["data"]["merge_pending_wps"] == []

        # Verify meta.json was written
        meta = json.loads((mission_dir / "meta.json").read_text())
        assert "accepted_at" in meta
        assert data["data"]["accepted_at"] == meta["accepted_at"]
        assert meta["accepted_by"] == "claude"

    def test_all_approved_accepted(self, tmp_path):
        repo_root, mission_dir = _make_acceptable_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        _emit_planned_to_approved(mission_dir, mission_slug, "WP01")
        _emit_planned_to_approved(mission_dir, mission_slug, "WP02")
        _commit_all(repo_root, "WP01/WP02 -> approved")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "accept-mission",
                    "--mission",
                    mission_slug,
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["accepted"] is True
        assert data["data"]["accepted_wps"] == ["WP01", "WP02"]
        assert data["data"]["approved_wps"] == ["WP01", "WP02"]
        assert data["data"]["done_wps"] == []
        assert data["data"]["merge_pending_wps"] == ["WP01", "WP02"]

        from specify_cli.status.reducer import materialize

        snapshot = materialize(mission_dir)
        assert snapshot.work_packages["WP01"]["lane"] == "approved"
        assert snapshot.work_packages["WP02"]["lane"] == "approved"

    def test_incomplete_wps_returns_error(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # Only do WP01
        _emit_planned_to_done(mission_dir, mission_slug, "WP01")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "accept-mission",
                    "--mission",
                    mission_slug,
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "MISSION_NOT_READY"
        assert "WP02" in data["data"]["incomplete_wps"]

    def test_malformed_path_conventions_returns_envelope(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"
        # The clean-working-tree probe now fails closed on an unreadable repo (it
        # used to read as "clean"), so the fixture's fake ``.git`` directory must
        # become a real repository for acceptance to reach the path-conventions check.
        import shutil
        import subprocess

        shutil.rmtree(repo_root / ".git")
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
        (repo_root / ".kittify").mkdir()
        (repo_root / ".kittify" / "config.yaml").write_text(
            "project:\n  path_conventions:\n    workspace: 123\n",
            encoding="utf-8",
        )

        _emit_planned_to_approved(mission_dir, mission_slug, "WP01")
        _emit_planned_to_approved(mission_dir, mission_slug, "WP02")

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "accept-mission",
                    "--mission",
                    mission_slug,
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 1, result.output
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["error_code"] == "MISSION_NOT_READY"
        assert "project.path_conventions.workspace" in data["data"]["message"]


# ── merge-mission ─────────────────────────────────────────────────


class TestMergeMission:
    def test_preflight_fails_returns_error(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        mock_preflight = MagicMock()
        mock_preflight.target_branch = "main"
        mock_preflight.errors = ["lanes.json is missing for this mission"]

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._build_merge_preflight",
                return_value=mock_preflight,
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "consolidate-mission",
                    "--mission",
                    mission_slug,
                    "--target",
                    "main",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "PREFLIGHT_FAILED"
        assert "lanes.json" in data["data"]["errors"][0]

    def test_merge_success(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        mock_preflight = MagicMock()
        mock_preflight.target_branch = "main"
        mock_preflight.errors = []

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._build_merge_preflight",
                return_value=mock_preflight,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._execute_lane_merge",
            ) as execute_merge,
        ):
            result = runner.invoke(
                app,
                [
                    "consolidate-mission",
                    "--mission",
                    mission_slug,
                    "--target",
                    "main",
                    "--strategy",
                    "merge",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["mission_slug"] == mission_slug
        assert data["data"]["merged"] is True
        assert data["data"]["target_branch"] == "main"
        assert data["data"]["strategy"] == "merge"
        execute_merge.assert_called_once()
        assert execute_merge.call_args.kwargs["strategy"] == "merge"

    def test_rebase_strategy_success(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        mock_preflight = MagicMock()
        mock_preflight.target_branch = "main"
        mock_preflight.errors = []

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._build_merge_preflight",
                return_value=mock_preflight,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._execute_lane_merge",
            ) as execute_merge,
        ):
            result = runner.invoke(
                app,
                [
                    "consolidate-mission",
                    "--mission",
                    mission_slug,
                    "--target",
                    "main",
                    "--strategy",
                    "rebase",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["strategy"] == "rebase"
        execute_merge.assert_called_once()
        assert execute_merge.call_args.kwargs["strategy"] == "rebase"

    def test_planning_only_merge_uses_hardened_closeout_without_stdout_noise(
        self,
        tmp_path,
    ):
        repo_root, mission_dir = _make_mission(tmp_path, "research-planning-only")
        mission_slug = "research-planning-only"
        meta_path = mission_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["mission_number"] = 99
        meta["mission_type"] = "research"
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        lane = MagicMock()
        lane.lane_id = "lane-planning"
        lane.wp_ids = ["WP01", "WP02"]
        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{mission_slug}"
        manifest.lanes = [lane]

        mock_preflight = MagicMock()
        mock_preflight.target_branch = "main"
        mock_preflight.errors = []

        def noisy_hardened_merge(**_kwargs):
            from specify_cli.cli.commands import consolidate as merge_command

            merge_command.console.print("this must not reach orchestrator stdout")

        with (
            patch(
                "specify_cli.orchestrator_api._common._get_main_repo_root",
                return_value=repo_root,
            ),
            patch(
                "specify_cli.orchestrator_api.consolidation._build_merge_preflight",
                return_value=mock_preflight,
            ),
            patch(
                "specify_cli.lanes.persistence.require_lanes_json",
                return_value=manifest,
            ),
            patch(
                "specify_cli.cli.commands.consolidate._run_lane_based_consolidation",
                side_effect=noisy_hardened_merge,
            ) as hardened_merge,
        ):
            result = runner.invoke(
                app,
                [
                    "consolidate-mission",
                    "--mission",
                    mission_slug,
                    "--target",
                    "main",
                    "--strategy",
                    "squash",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "this must not reach" not in result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["merged"] is True
        assert data["data"]["strategy"] == "squash"
        hardened_merge.assert_called_once()
        assert hardened_merge.call_args.kwargs["target_override"] == "main"
        assert hardened_merge.call_args.kwargs["strategy"].value == "squash"
        assert hardened_merge.call_args.kwargs["assume_yes"] is True

    def test_unsupported_strategy_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "consolidate-mission",
                    "--mission",
                    mission_slug,
                    "--target",
                    "main",
                    "--strategy",
                    "octopus",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "UNSUPPORTED_STRATEGY"
        assert data["data"]["strategy"] == "octopus"
        assert "merge" in data["data"]["supported"]


# ── contract-version (version mismatch) ───────────────────────────


class TestContractVersionMismatch:
    def test_compatible_provider_version_succeeds(self, tmp_path):
        from specify_cli.orchestrator_api.envelope import MIN_PROVIDER_VERSION

        result = runner.invoke(
            app,
            ["contract-version", "--provider-version", MIN_PROVIDER_VERSION],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["api_version"] is not None

    def test_below_min_provider_version_returns_mismatch(self, tmp_path):
        result = runner.invoke(
            app,
            ["contract-version", "--provider-version", "0.0.1"],
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "CONTRACT_VERSION_MISMATCH"
        assert "provider_version" in data["data"]
        assert "min_supported_provider_version" in data["data"]

    def test_invalid_provider_version_returns_mismatch(self, tmp_path):
        result = runner.invoke(
            app,
            ["contract-version", "--provider-version", "not-a-version"],
        )
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "CONTRACT_VERSION_MISMATCH"


# ── WP_NOT_FOUND for state-mutating commands ──────────────────────


class TestWPNotFound:
    def test_start_implementation_ghost_wp_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP99",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "WP_NOT_FOUND"

    def test_start_review_ghost_wp_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-review",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP99",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                    "--review-ref",
                    "ref-001",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "WP_NOT_FOUND"

    def test_transition_ghost_wp_rejected(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP99",
                    "--to",
                    "canceled",
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error_code"] == "WP_NOT_FOUND"


# ── mission-state with no events ──────────────────────────────────


class TestMissionStateNoEvents:
    def test_untouched_wps_appear_as_planned(self, tmp_path):
        """WPs with no events still appear in mission-state with lane=planned."""
        repo_root, mission_dir = _make_mission(tmp_path, "099-test-mission")
        mission_slug = "099-test-mission"

        # No events emitted at all
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--mission", mission_slug])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        wps = {wp["wp_id"]: wp for wp in data["data"]["work_packages"]}
        assert "WP01" in wps
        assert "WP02" in wps
        assert wps["WP01"]["lane"] == "planned"
        assert wps["WP02"]["lane"] == "planned"


# ── Suffixed WP filenames (P0 regression) ─────────────────────────


def _make_mission_with_suffixed_wps(tmp_path: Path, mission_slug: str = "040-test-mission") -> tuple[Path, Path]:
    """Create a mission directory whose WP files have hyphen-suffixed names.

    e.g. WP07-adapter-implementations.md instead of WP07.md
    """
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    (tasks_dir / "WP01-core-setup.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Core Setup\nlane: planned\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP07-adapter-implementations.md").write_text(
        "---\nwork_package_id: WP07\ntitle: Adapter Implementations\nlane: planned\ndependencies: []\nsubtasks: []\n---\n\n# WP07\n",
        encoding="utf-8",
    )
    # Also include a non-WP file to verify it is excluded
    (tasks_dir / "README.md").write_text("# Tasks\n", encoding="utf-8")

    # Top-level tasks.md index for the subtask-completeness gate (#2574).
    _write_tasks_index(mission_dir, {"WP01": 2, "WP07": 2})

    (mission_dir / "meta.json").write_text(json.dumps({"status_phase": 1}), encoding="utf-8")
    _seed_planned_events(mission_dir, mission_slug, ("WP01", "WP07"))
    return repo_root, mission_dir


class TestSuffixedWPFilenames:
    """Commands must accept WP IDs whose task files have hyphen-suffixed names."""

    def test_start_implementation_accepts_suffixed_file(self, tmp_path):
        repo_root, mission_dir = _make_mission_with_suffixed_wps(tmp_path)
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    "040-test-mission",
                    "--wp",
                    "WP07",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP07"
        # prompt_path must point to the real (suffixed) file
        assert "WP07-adapter-implementations" in data["data"]["prompt_path"]

    def test_transition_accepts_suffixed_file(self, tmp_path):
        from specify_cli.status.emit import emit_status_transition

        repo_root, mission_dir = _make_mission_with_suffixed_wps(tmp_path)
        # Put WP07 in_progress so we can cancel it
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug="040-test-mission", wp_id="WP07", to_lane="claimed", actor="claude"))
        emit_status_transition(TransitionRequest(feature_dir=mission_dir, mission_slug="040-test-mission", wp_id="WP07", to_lane="in_progress", actor="claude"))

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    "040-test-mission",
                    "--wp",
                    "WP07",
                    "--to",
                    "canceled",
                    "--actor",
                    "claude",
                ],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP07"
        assert data["data"]["to_lane"] == "canceled"

    def test_mission_state_emits_canonical_ids_only(self, tmp_path):
        """mission-state must not include raw filename stems like 'WP07-adapter-implementations'."""
        repo_root, _ = _make_mission_with_suffixed_wps(tmp_path)
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--mission", "040-test-mission"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["success"] is True
        wp_ids = {wp["wp_id"] for wp in data["data"]["work_packages"]}

        # Canonical IDs must be present
        assert "WP01" in wp_ids
        assert "WP07" in wp_ids

        # Raw stems must NOT appear
        assert "WP01-core-setup" not in wp_ids
        assert "WP07-adapter-implementations" not in wp_ids

        # Non-WP file must NOT appear
        assert "README" not in wp_ids


# ── JSON-only stdout contract ─────────────────────────────────────


class TestJsonOnlyStdoutContract:
    """Orchestrator-api commands must emit exactly one JSON object on stdout.

    Even when sync/event fan-out emits warnings (e.g. read-only filesystem),
    those warnings must go to stderr — never polluting stdout.  The
    ``sync/emitter.py`` console is ``Console(stderr=True)``, so in a real
    terminal warnings go to fd 2.  CliRunner merges both streams into
    ``result.output``, so these tests validate the contract by asserting
    the *last* line of output is valid JSON (the envelope) and confirming
    the envelope structure.
    """

    def test_start_implementation_last_line_is_valid_json(self, tmp_path):
        """Even if non-JSON diagnostic lines precede the envelope,
        the final line must be the JSON envelope."""
        repo_root, mission_dir = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "test-agent",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        # The canonical envelope is always the last non-empty line
        last_line = result.output.strip().rsplit("\n", 1)[-1]
        data = json.loads(last_line)
        assert data["success"] is True
        assert data["data"]["wp_id"] == "WP01"

    def test_stdout_is_single_json_object(self, tmp_path):
        """Under normal conditions, output must be exactly one JSON object."""
        repo_root, mission_dir = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(
                app,
                [
                    "start-implementation",
                    "--mission",
                    "099-test-mission",
                    "--wp",
                    "WP01",
                    "--actor",
                    "test-agent",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

        assert result.exit_code == 0, result.output
        stripped = result.output.strip()
        # Must parse as a single JSON object (no extra data)
        data = json.loads(stripped)
        assert isinstance(data, dict)
        assert data["command"] == "orchestrator-api.start-implementation"


# ── Old command names must fail ───────────────────────────────────


class TestOldCommandNamesFail:
    """Old feature-era command names must fail as unknown commands."""

    def test_feature_state_rejected(self):
        result = runner.invoke(app, ["feature-state", "--mission", "dummy"])
        assert result.exit_code != 0

    def test_accept_feature_rejected(self):
        result = runner.invoke(app, ["accept-feature", "--mission", "dummy"])
        assert result.exit_code != 0

    def test_merge_feature_rejected(self):
        result = runner.invoke(app, ["merge-feature", "--mission", "dummy"])
        assert result.exit_code != 0


# ── Old --feature flag must fail ──────────────────────────────────


class TestOldFeatureFlagFails:
    """The --feature flag must no longer be accepted on any command."""

    def test_mission_state_rejects_feature_flag(self, tmp_path):
        result = runner.invoke(app, ["mission-state", "--feature", "dummy"])
        assert result.exit_code != 0

    def test_list_ready_rejects_feature_flag(self, tmp_path):
        result = runner.invoke(app, ["list-ready", "--feature", "dummy"])
        assert result.exit_code != 0

    def test_start_implementation_rejects_feature_flag(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--feature",
                "dummy",
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )
        assert result.exit_code != 0


class TestResolveWorkspace:
    """#2337: read-only resolve-workspace for resuming a WP past implementation."""

    def test_resolve_workspace_returns_workspace_and_prompt(self, tmp_path):
        repo_root, mission_dir = _make_mission(tmp_path)
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["resolve-workspace", "--mission", "099-test-mission", "--wp", "WP01"])
        assert result.exit_code == 0, result.stdout
        data = json.loads(result.stdout)["data"]
        assert data["mission_slug"] == "099-test-mission"
        assert data["wp_id"] == "WP01"
        assert data["workspace_path"]
        assert data["prompt_path"].endswith("WP01.md")

    def test_resolve_workspace_is_read_only(self, tmp_path):
        """No lane transition, no worktree creation — unlike start-implementation."""
        repo_root, mission_dir = _make_mission(tmp_path)
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            runner.invoke(app, ["resolve-workspace", "--mission", "099-test-mission", "--wp", "WP01"])
        from specify_cli.status import read_events, reduce

        lanes = {k: v.get("lane") for k, v in reduce(read_events(mission_dir)).work_packages.items()}
        # WP01 stays planned (resolve-workspace emitted no transition).
        assert lanes.get("WP01") in ("planned", None), lanes
        assert not (repo_root / ".worktrees").exists(), "must not create a worktree"

    def test_resolve_workspace_wp_not_found(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["resolve-workspace", "--mission", "099-test-mission", "--wp", "WP99"])
        assert result.exit_code != 0
        payload = json.loads(result.stdout.strip().split("\n")[0])
        assert payload["error_code"] == "WP_NOT_FOUND"


class TestLaneAssignmentOrLegacy:
    """The shared resolver prologue: ONE lane-vs-legacy decision for the surface."""

    def test_legacy_arm_without_lanes_json(self, tmp_path):
        """No lanes.json ⇒ the legacy bare-path workspace ({mission}-{wp}, no mid8)."""
        from specify_cli.orchestrator_api.wp_lifecycle import _lane_assignment_or_legacy, _StartWorkspace

        repo_root, _ = _make_mission(tmp_path)
        result = _lane_assignment_or_legacy(repo_root, "099-test-mission", "WP01")
        assert isinstance(result, _StartWorkspace)
        assert result.workspace_path.endswith("099-test-mission-WP01")
        assert result.lane_id is None and result.lane_branch is None

    def test_lane_arm_returns_manifest_and_lane(self, tmp_path):
        """A lane-assigned WP ⇒ the (manifest, lane) pair, no fallback."""
        from specify_cli.lanes.models import ExecutionLane, LanesManifest
        from specify_cli.orchestrator_api.wp_lifecycle import _lane_assignment_or_legacy, _StartWorkspace

        repo_root, _ = _make_mission(tmp_path)
        lane = ExecutionLane(
            lane_id="lane-a",
            wp_ids=("WP01",),
            write_scope=(),
            predicted_surfaces=(),
            depends_on_lanes=(),
            parallel_group=0,
        )
        manifest = LanesManifest(
            version=1,
            mission_slug="099-test-mission",
            mission_id=None,
            mission_branch="kitty/mission-099-test-mission",
            target_branch="main",
            lanes=[lane],
            computed_at="2026-07-04T00:00:00+00:00",
            computed_from="test",
        )
        with patch("specify_cli.lanes.persistence.read_lanes_json", return_value=manifest):
            result = _lane_assignment_or_legacy(repo_root, "099-test-mission", "WP01")
        assert not isinstance(result, _StartWorkspace)
        got_manifest, got_lane = result
        assert got_manifest is manifest
        assert got_lane is lane

    def test_both_resolvers_share_the_legacy_grammar(self, tmp_path):
        """SSOT pin: start + existing resolvers emit the SAME legacy path."""
        from specify_cli.orchestrator_api.wp_lifecycle import _resolve_existing_workspace, _resolve_start_workspace

        repo_root, mission_dir = _make_mission(tmp_path)
        started = _resolve_start_workspace("start-implementation", repo_root, "099-test-mission", mission_dir, "WP01")
        resolved = _resolve_existing_workspace(repo_root, "099-test-mission", "WP01")
        assert started.workspace_path == resolved.workspace_path
