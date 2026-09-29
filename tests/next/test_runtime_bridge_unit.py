"""Unit tests for the runtime bridge module.

This file imports runtime symbols only via ``runtime.next._internal_runtime``
following the WP02 cutover in mission ``shared-package-boundary-cutover-01KQ22DS``.
No quarantined ``spec_kitty_runtime`` references are needed; tests assert against
the internalized runtime surface, which is the authoritative production target.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._factories import provision_test_charter
from tests._perf_helpers import assert_timing_budget
from tests.lane_test_utils import write_single_lane_manifest
from runtime.next.decision import DecisionKind
from runtime.next._internal_runtime import DiscoveryContext

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a bare git repo at *path*."""
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_project(
    tmp_path: Path,
    mission_slug: str = "042-test-feature",
    mission_type: str = "software-dev",
) -> Path:
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    kittify = repo_root / ".kittify"
    kittify.mkdir()
    # WP04 fail-closed: mission-type resolution requires a provisioned
    # charter (activated mission types). Seed the default activation set
    # via the production provisioner, same shared helper used across the
    # mission-creation test harness.
    provision_test_charter(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": mission_type}),
        encoding="utf-8",
    )

    return repo_root


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a WP into a specific lane in the event log."""
    from specify_cli.status.store import append_event
    from specify_cli.status.models import StatusEvent, Lane

    # Map legacy aliases to canonical lane names
    _lane_alias = {"doing": "in_progress"}
    canonical_lane = _lane_alias.get(lane, lane)

    event = StatusEvent(
        event_id=f"test-{wp_id}-{canonical_lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(canonical_lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _add_wp_files(feature_dir: Path, wps: dict[str, str]) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    for wp_id, lane in wps.items():
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\nlane: {lane}\ntitle: {wp_id} task\n---\n# {wp_id}\nDo something.\n",
            encoding="utf-8",
        )
        # Always seed event log (canonical status is required)
        _seed_wp_lane(feature_dir, wp_id, lane)
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wps.keys()))


# ---------------------------------------------------------------------------
# Template precedence tests
# ---------------------------------------------------------------------------


class TestRuntimeTemplateKey:
    pytestmark = pytest.mark.git_repo

    def test_project_override_takes_precedence(self, tmp_path: Path) -> None:
        """Project-level mission-runtime.yaml shadows the built-in."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import _runtime_template_key

        # Create a project-level override at the canonical override tier
        project_dir = repo_root / ".kittify" / "overrides" / "missions" / "software-dev"
        project_dir.mkdir(parents=True)
        project_yaml = project_dir / "mission-runtime.yaml"
        project_yaml.write_text(
            "mission:\n  key: software-dev\n  name: software-dev\n  version: '9.9.9'\nsteps:\n  - id: x\n    title: x\n",
            encoding="utf-8",
        )

        result = _runtime_template_key("software-dev", repo_root)
        assert result == str(project_yaml), f"Project override must take precedence, got: {result}"

    def test_env_takes_precedence_over_project_override(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SPEC_KITTY_MISSION_PATHS outranks project override for runtime templates."""
        repo_root = _scaffold_project(tmp_path)
        from runtime.next.runtime_bridge import _runtime_template_key

        # Project override exists
        override_dir = repo_root / ".kittify" / "overrides" / "missions" / "software-dev"
        override_dir.mkdir(parents=True)
        (override_dir / "mission-runtime.yaml").write_text(
            "mission:\n  key: software-dev\n  name: override\n  version: '1.0.0'\nsteps:\n  - id: o\n    title: o\n",
            encoding="utf-8",
        )

        # Env mission path should win
        env_root = tmp_path / "env-missions"
        env_mission = env_root / "software-dev"
        env_mission.mkdir(parents=True)
        env_runtime = env_mission / "mission-runtime.yaml"
        env_runtime.write_text(
            "mission:\n  key: software-dev\n  name: env\n  version: '2.0.0'\nsteps:\n  - id: e\n    title: e\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("SPEC_KITTY_MISSION_PATHS", str(env_root))

        result = _runtime_template_key("software-dev", repo_root)
        assert result == str(env_runtime.resolve())

    def test_falls_back_to_builtin(self, tmp_path: Path, monkeypatch) -> None:
        """Without a project override, the built-in template is used."""
        repo_root = _scaffold_project(tmp_path)

        import runtime.next.runtime_bridge as runtime_bridge
        import runtime.next.runtime_bridge_io as runtime_bridge_io
        import specify_cli

        builtin_root = Path(specify_cli.__file__).resolve().parent / "missions"

        # Force deterministic discovery context for this test so user-global
        # ~/.kittify content cannot shadow the builtin fallback tier.
        monkeypatch.setattr(
            runtime_bridge_io,
            "_build_discovery_context",
            lambda root: DiscoveryContext(
                project_dir=root,
                builtin_roots=[builtin_root],
                user_home=tmp_path,
            ),
        )

        result = runtime_bridge._runtime_template_key("software-dev", repo_root)
        assert result == str((builtin_root / "software-dev" / "mission-runtime.yaml").resolve())


class TestWorkflowRuntimeTemplate:
    pytestmark = pytest.mark.git_repo

    def test_workflow_id_composes_frozen_runtime_template(self, tmp_path: Path) -> None:
        """meta.json::workflow_id affects the canonical run template used by `next`."""
        repo_root = _scaffold_project(tmp_path)
        mission_dir = repo_root / "kitty-specs" / "042-test-feature"
        (mission_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_type": "software-dev",
                    "workflow_id": "our-team-design-first",
                }
            ),
            encoding="utf-8",
        )

        from runtime.next._internal_runtime.engine import _load_frozen_template
        from runtime.next.runtime_bridge import get_or_start_run

        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        template = _load_frozen_template(Path(run_ref.run_dir))
        step_ids = [step.id for step in template.steps]

        assert step_ids == [
            "discovery",
            "specify",
            "plan",
            "design-review",
            "tasks",
            "implement",
            "review",
            "merge",
        ]

    def test_workflow_inserted_step_resolves_prompt_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A workflow-inserted step must not block on missing prompt resolution."""
        repo_root = _scaffold_project(tmp_path)
        mission_dir = repo_root / "kitty-specs" / "042-test-feature"
        (mission_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_type": "software-dev",
                    "workflow_id": "our-team-design-first",
                }
            ),
            encoding="utf-8",
        )

        from runtime.next import runtime_bridge
        from runtime.next.decision import DecisionKind

        monkeypatch.setattr(
            runtime_bridge,
            "runtime_emitter_for_mission",
            lambda **_: runtime_bridge._BufferingRuntimeEmitter(),
        )

        runtime_bridge.decide_next_via_runtime(
            "agent",
            "042-test-feature",
            "success",
            repo_root,
        )
        specify = runtime_bridge.decide_next_via_runtime(
            "agent",
            "042-test-feature",
            "success",
            repo_root,
        )
        assert specify.step_id == "specify"
        (mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

        plan = runtime_bridge.decide_next_via_runtime(
            "agent",
            "042-test-feature",
            "success",
            repo_root,
        )
        assert plan.step_id == "plan"
        (mission_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")

        design_review = runtime_bridge.decide_next_via_runtime(
            "agent",
            "042-test-feature",
            "success",
            repo_root,
        )

        assert design_review.kind == DecisionKind.step
        assert design_review.step_id == "design-review"
        assert design_review.action == "design-review"
        assert design_review.prompt_file is not None
        assert Path(design_review.prompt_file).is_file()

    def test_software_dev_builtin_outranks_stale_user_global(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A stale user-global software-dev runtime must not revive legacy tasks_*."""
        repo_root = _scaffold_project(tmp_path)

        import runtime.next.runtime_bridge as runtime_bridge
        import runtime.next.runtime_bridge_io as runtime_bridge_io
        import specify_cli

        builtin_root = Path(specify_cli.__file__).resolve().parent / "missions"
        user_home = tmp_path / "home"
        global_runtime = user_home / ".kittify" / "missions" / "software-dev" / "mission-runtime.yaml"
        global_runtime.parent.mkdir(parents=True)
        global_runtime.write_text(
            "mission:\n  key: software-dev\n  name: stale\n  version: '2.1.0'\n"
            "steps:\n"
            "  - id: tasks_outline\n    title: outline\n"
            "  - id: tasks_packages\n    title: packages\n    depends_on: [tasks_outline]\n"
            "  - id: tasks_finalize\n    title: finalize\n    depends_on: [tasks_packages]\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            runtime_bridge_io,
            "_build_discovery_context",
            lambda root: DiscoveryContext(
                project_dir=root,
                builtin_roots=[builtin_root],
                user_home=user_home,
            ),
        )

        result = runtime_bridge._runtime_template_key("software-dev", repo_root)
        assert result != str(global_runtime.resolve())
        assert result == str((builtin_root / "software-dev" / "mission-runtime.yaml").resolve())

    def test_project_legacy_used_when_override_absent(self, tmp_path: Path) -> None:
        """Legacy .kittify/missions path remains supported after override tier."""
        repo_root = _scaffold_project(tmp_path)
        from runtime.next.runtime_bridge import _runtime_template_key

        legacy_dir = repo_root / ".kittify" / "missions" / "software-dev"
        legacy_dir.mkdir(parents=True)
        legacy_runtime = legacy_dir / "mission-runtime.yaml"
        legacy_runtime.write_text(
            "mission:\n  key: software-dev\n  name: legacy\n  version: '3.0.0'\nsteps:\n  - id: l\n    title: l\n",
            encoding="utf-8",
        )

        result = _runtime_template_key("software-dev", repo_root)
        assert result == str(legacy_runtime.resolve())


# ---------------------------------------------------------------------------
# get_or_start_run tests
# ---------------------------------------------------------------------------


class TestGetOrStartRun:
    pytestmark = pytest.mark.git_repo

    def test_creates_new_run(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import get_or_start_run

        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        assert run_ref.run_id is not None
        assert len(run_ref.run_id) > 0
        assert getattr(run_ref, "mission_key", None) == "software-dev"
        assert Path(run_ref.run_dir).exists()
        assert (Path(run_ref.run_dir) / "state.json").exists()

    def test_loads_existing_run(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import get_or_start_run

        run1 = get_or_start_run("042-test-feature", repo_root, "software-dev")
        run2 = get_or_start_run("042-test-feature", repo_root, "software-dev")
        assert run1.run_id == run2.run_id
        assert run1.run_dir == run2.run_dir

    def test_different_features_get_different_runs(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        # Create second feature
        feature_dir2 = repo_root / "kitty-specs" / "043-other-feature"
        feature_dir2.mkdir(parents=True)
        (feature_dir2 / "meta.json").write_text('{"mission_type": "software-dev"}', encoding="utf-8")

        from runtime.next.runtime_bridge import get_or_start_run

        run1 = get_or_start_run("042-test-feature", repo_root, "software-dev")
        run2 = get_or_start_run("043-other-feature", repo_root, "software-dev")
        assert run1.run_id != run2.run_id

    def test_feature_runs_index_persisted(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import get_or_start_run, _load_feature_runs

        get_or_start_run("042-test-feature", repo_root, "software-dev")
        index = _load_feature_runs(repo_root)
        # WP05 / FR-016 (C-003): the index is keyed by mission_id; a mission
        # without one (this scaffold's meta.json) lands under ``legacy-<slug>``
        # and the bare slug is never a key.
        assert set(index) == {"legacy-042-test-feature"}
        assert "run_id" in index["legacy-042-test-feature"]

    def test_feature_runs_index_includes_mission_id_and_slug(self, tmp_path: Path) -> None:
        """FR-028: feature-runs.json entries must include mission_id and mission_slug (WP06)."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import get_or_start_run, _load_feature_runs

        get_or_start_run("042-test-feature", repo_root, "software-dev")
        index = _load_feature_runs(repo_root)
        entry = index["legacy-042-test-feature"]
        # mission_slug is display-only (WP05) but must always be present
        assert entry.get("mission_slug") == "042-test-feature"
        # mission_id may be None when no meta.json exists, but the key must be present
        assert "mission_id" in entry


class TestRuntimeBridgeCompatibilityHelpers:
    def test_mission_key_for_run_ref_prefers_mission_type(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _mission_key_for_run_ref

        run_ref = SimpleNamespace(mission_type="software-dev")
        assert _mission_key_for_run_ref(run_ref, "fallback") == "software-dev"

    def test_mission_key_for_run_ref_falls_back_to_default(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _mission_key_for_run_ref

        run_ref = SimpleNamespace(mission_type="")
        assert _mission_key_for_run_ref(run_ref, "fallback") == "fallback"

    def test_build_run_ref_falls_back_when_runtime_uses_mission_type(self, monkeypatch) -> None:
        import runtime.next.runtime_bridge as runtime_bridge

        class FakeRunRef:
            def __init__(self, *, run_id: str, run_dir: str, mission_type: str | None = None, mission_key: str | None = None):
                if mission_key is not None:
                    raise TypeError("legacy mission_key no longer accepted")
                self.run_id = run_id
                self.run_dir = run_dir
                self.mission_type = mission_type

        monkeypatch.setattr(runtime_bridge, "MissionRunRef", FakeRunRef)

        run_ref = runtime_bridge._build_run_ref(
            run_id="run-123",
            run_dir="/nonexistent/run-123",
            mission_type="software-dev",
        )

        assert run_ref.run_id == "run-123"
        assert run_ref.run_dir == "/nonexistent/run-123"
        assert run_ref.mission_type == "software-dev"


# ---------------------------------------------------------------------------
# WP iteration tests
# ---------------------------------------------------------------------------


class TestWPIteration:
    pytestmark = pytest.mark.git_repo

    def test_wp_iteration_does_not_advance_runtime(self, tmp_path: Path) -> None:
        """When WPs remain, runtime step should not advance."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "planned",
                "WP02": "planned",
            },
        )

        from runtime.next.runtime_bridge import (
            get_or_start_run,
            decide_next_via_runtime,
        )
        from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter
        from runtime.next._internal_runtime.engine import _read_snapshot

        # Advance runtime to implement step
        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        step_order = ["discovery", "specify", "plan", "tasks", "implement"]
        for _ in range(len(step_order)):
            snapshot = _read_snapshot(Path(run_ref.run_dir))
            if snapshot.issued_step_id == "implement":
                break
            runtime_next_step(run_ref, agent_id="test", result="success", emitter=NullEmitter())

        # Now decide_next should keep us in implement with WP01
        decision = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert decision.kind == DecisionKind.step
        assert decision.action == "implement"
        assert decision.wp_id == "WP01"

        # Call again — should still be in implement with same WP (not advanced)
        decision2 = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert decision2.step_id == "implement"

    def test_all_wps_done_advances_runtime(self, tmp_path: Path) -> None:
        """When all WPs are done, runtime should advance past implement."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(
            feature_dir,
            {
                "WP01": "done",
                "WP02": "done",
            },
        )

        from runtime.next.runtime_bridge import (
            get_or_start_run,
            decide_next_via_runtime,
        )
        from runtime.next._internal_runtime import next_step as runtime_next_step, NullEmitter
        from runtime.next._internal_runtime.engine import _read_snapshot

        # Advance runtime to implement step
        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        for _ in range(6):
            snapshot = _read_snapshot(Path(run_ref.run_dir))
            if snapshot.issued_step_id == "implement":
                break
            runtime_next_step(run_ref, agent_id="test", result="success", emitter=NullEmitter())

        # All WPs done — decide_next should advance past implement
        decision = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        # Should either be in review or later step (not implement)
        assert decision.step_id != "implement" or decision.kind != DecisionKind.step


# ---------------------------------------------------------------------------
# Runtime result flow tests
# ---------------------------------------------------------------------------


class TestRuntimeResultFlow:
    pytestmark = pytest.mark.git_repo

    @staticmethod
    def _read_run_events(run_dir: Path) -> list[dict]:
        event_file = run_dir / "run.events.jsonl"
        if not event_file.exists():
            return []
        events: list[dict] = []
        for line in event_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def test_failed_result_flows_through_runtime_event_log(self, tmp_path: Path) -> None:
        """A failed result must call runtime next_step and append canonical events."""
        repo_root = _scaffold_project(tmp_path)
        from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run

        # Issue a first step so runtime has a prior issued_step_id to complete.
        first = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert first.run_id is not None

        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        run_dir = Path(run_ref.run_dir)
        before = self._read_run_events(run_dir)

        failed = decide_next_via_runtime("test", "042-test-feature", "failed", repo_root)
        after = self._read_run_events(run_dir)

        assert failed.kind == DecisionKind.blocked
        assert failed.run_id == run_ref.run_id
        assert len(after) > len(before), "failed path must append runtime lifecycle event(s)"
        assert any(evt["event_type"] == "NextStepAutoCompleted" for evt in after[len(before) :])

    def test_blocked_result_flows_through_runtime_event_log(self, tmp_path: Path) -> None:
        """A blocked result must call runtime next_step and append canonical events."""
        repo_root = _scaffold_project(tmp_path)
        from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run

        # Issue a first step so runtime has a prior issued_step_id to complete.
        first = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert first.run_id is not None

        run_ref = get_or_start_run("042-test-feature", repo_root, "software-dev")
        run_dir = Path(run_ref.run_dir)
        before = self._read_run_events(run_dir)

        blocked = decide_next_via_runtime("test", "042-test-feature", "blocked", repo_root)
        after = self._read_run_events(run_dir)

        assert blocked.kind == DecisionKind.blocked
        assert blocked.run_id == run_ref.run_id
        assert len(after) > len(before), "blocked path must append runtime lifecycle event(s)"
        assert any(evt["event_type"] == "NextStepAutoCompleted" for evt in after[len(before) :])


class TestAnswerDecisionViaRuntime:
    def test_snapshot_read_failure_is_tolerated(self, monkeypatch, tmp_path: Path) -> None:
        """Decision answers should continue even when snapshot hydration fails."""
        from runtime.next import runtime_bridge
        import runtime.next._internal_runtime.engine as runtime_engine

        repo_root = tmp_path / "project"
        repo_root.mkdir()
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        feature_dir.mkdir(parents=True)

        fake_run_ref = SimpleNamespace(run_dir=str(tmp_path / "run"), run_id="run-001")
        emitter_calls: list[tuple[str, object]] = []

        class FakeEmitter:
            def seed_from_snapshot(self, snapshot) -> None:
                emitter_calls.append(("seed", snapshot))

        monkeypatch.setattr(runtime_bridge, "get_mission_type", lambda path: "software-dev")
        monkeypatch.setattr(runtime_bridge, "get_or_start_run", lambda mission_slug, repo_root, mission_type: fake_run_ref)
        monkeypatch.setattr(runtime_bridge, "runtime_emitter_for_mission", lambda **_: FakeEmitter())

        provided: list[tuple[object, str, str, object, object]] = []

        def fake_provide(run_ref, decision_id, answer, actor, *, emitter) -> None:
            provided.append((run_ref, decision_id, answer, actor, emitter))

        monkeypatch.setattr(runtime_bridge, "runtime_provide_decision_answer", fake_provide)
        monkeypatch.setattr(
            runtime_engine,
            "_read_snapshot",
            lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        runtime_bridge.answer_decision_via_runtime(
            "042-test-feature",
            "decision-001",
            "yes",
            "robert",
            repo_root,
        )

        assert emitter_calls == []
        assert len(provided) == 1
        _, decision_id, answer, actor, _ = provided[0]
        assert decision_id == "decision-001"
        assert answer == "yes"
        assert actor.actor_id == "robert"
        assert actor.actor_type == "human"


# ---------------------------------------------------------------------------
# Guard check tests
# ---------------------------------------------------------------------------


class TestGuardChecks:
    pytestmark = pytest.mark.git_repo

    def test_specify_guard_blocks_without_spec(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import _check_cli_guards

        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        failures = _check_cli_guards("specify", feature_dir)
        assert len(failures) == 1
        assert "spec.md" in failures[0]

    def test_specify_guard_passes_with_spec(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text("# Spec", encoding="utf-8")

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("specify", feature_dir)
        assert len(failures) == 0

    def test_plan_guard_blocks_without_artifacts(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("plan", feature_dir)
        assert len(failures) == 1  # plan.md only (tasks.md moved to tasks_outline guard)

    def test_implement_guard_blocks_with_planned_wps(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "planned", "WP02": "done"})

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("implement", feature_dir)
        assert len(failures) == 1

    def test_implement_guard_passes_all_done(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "done", "WP02": "done"})

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("implement", feature_dir)
        assert len(failures) == 0


class TestTasksMarkdownParsing:
    def test_parse_wp_sections_preserves_same_line_suffix(self) -> None:
        from runtime.next.runtime_bridge import _parse_wp_sections_from_tasks_md

        tasks_md = "## Work Package WP01: Build parser\nRequirements Refs: FR-001, NFR-002\n### WP02\nRequirements: FR-003\n"

        sections = _parse_wp_sections_from_tasks_md(tasks_md)

        assert sections["WP01"].startswith(": Build parser\n")
        assert "Requirements Refs: FR-001, NFR-002" in sections["WP01"]
        assert sections["WP02"] == "\nRequirements: FR-003\n"

    def test_parse_wp_sections_accepts_legacy_work_package_spacing(self) -> None:
        from runtime.next.runtime_bridge import _parse_requirement_refs_from_tasks_md

        tasks_md = "## Work Package    WP01: Build parser\nRequirements Refs: FR-001, NFR-002\n"

        assert _parse_requirement_refs_from_tasks_md(tasks_md) == {"WP01": ["FR-001", "NFR-002"]}

    def test_parse_requirement_refs_supports_heading_bullet_format(self) -> None:
        from runtime.next.runtime_bridge import _parse_requirement_refs_from_tasks_md

        tasks_md = "## Work Package WP01: Build parser\n### Requirement Refs\n- FR-001, nfr-002\n"

        assert _parse_requirement_refs_from_tasks_md(tasks_md) == {"WP01": ["FR-001", "NFR-002"]}

    def test_parse_requirement_refs_on_adversarial_input(self) -> None:
        """Functional half of the #4015 split: parses correctly under adversarial input."""
        from runtime.next.runtime_bridge import _parse_requirement_refs_from_tasks_md

        filler = "".join("#### Not a work package heading\n" for _ in range(100_000))
        tasks_md = f"{filler}## Work Package WP01: Harden parser\nRequirements Refs: FR-001, fr-002, C-003\n"

        refs = _parse_requirement_refs_from_tasks_md(tasks_md)

        assert refs == {"WP01": ["FR-001", "FR-002", "C-003"]}

    @pytest.mark.performance
    def test_parse_requirement_refs_completes_under_budget_on_adversarial_input(self) -> None:
        """#4015 split: regex/backtracking budget on adversarial tasks.md input."""
        from runtime.next.runtime_bridge import _parse_requirement_refs_from_tasks_md

        filler = "".join("#### Not a work package heading\n" for _ in range(100_000))
        tasks_md = f"{filler}## Work Package WP01: Harden parser\nRequirements Refs: FR-001, fr-002, C-003\n"

        start = time.perf_counter()
        _parse_requirement_refs_from_tasks_md(tasks_md)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 0.2, name="elapsed")


# ---------------------------------------------------------------------------
# Decision mapping tests
# ---------------------------------------------------------------------------


class TestMapRuntimeDecision:
    pytestmark = pytest.mark.git_repo

    def test_map_preserves_json_contract(self, tmp_path: Path) -> None:
        """Mapped decisions have all required JSON fields."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import decide_next_via_runtime

        decision = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        d = decision.to_dict()

        # Original fields
        assert "kind" in d
        assert "agent" in d
        assert "mission_slug" in d
        assert "mission" in d
        assert "mission_state" in d
        assert "timestamp" in d
        assert "guard_failures" in d
        assert "progress" in d
        assert "origin" in d

        # New runtime fields
        assert "run_id" in d
        assert "step_id" in d
        assert "decision_id" in d
        assert "input_key" in d


# ---------------------------------------------------------------------------
# Answer decision tests
# ---------------------------------------------------------------------------


class TestAnswerDecision:
    pytestmark = pytest.mark.git_repo

    def test_query_and_answer_paths_use_canonical_context_surfaces(self) -> None:
        """FR-032: runtime query/answer surfaces stay on canonical context APIs."""
        import inspect

        from runtime.next import runtime_bridge

        assert "mission_context_for" in inspect.getsource(runtime_bridge.query_current_state)
        assert "resolve_action_context" in inspect.getsource(runtime_bridge.answer_decision_via_runtime)

    def test_answer_missing_mission_raises(self, tmp_path: Path) -> None:
        """Missing mission must fail, not log and report a successful no-op answer.

        WP02 / C-IC02: the decision-answer path no longer collapses the resolver's
        typed ``ActionContextError`` into a generic ``MissionRuntimeError``; it
        preserves the typed code IDENTICALLY to the query path (FR-001). An
        unresolved handle still fails loudly — just with the typed error and its
        ``code`` intact — so the no-op regression this test guards stays closed.
        """
        repo_root = _scaffold_project(tmp_path)

        from mission_runtime import ActionContextError

        from runtime.next.runtime_bridge import answer_decision_via_runtime

        with pytest.raises(ActionContextError) as excinfo:
            answer_decision_via_runtime(
                "missing-feature",
                "decision-001",
                "yes",
                "test",
                repo_root,
            )
        # The typed code survives (no collapse to a generic "cannot answer
        # decision" string).
        assert excinfo.value.code

    def test_answer_without_pending_raises(self, tmp_path: Path) -> None:
        """Answering when no decisions pending raises error."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import answer_decision_via_runtime
        from runtime.next._internal_runtime.schema import MissionRuntimeError

        with pytest.raises(MissionRuntimeError, match="not found"):
            answer_decision_via_runtime(
                "042-test-feature",
                "nonexistent",
                "yes",
                "test",
                repo_root,
            )


# ---------------------------------------------------------------------------
# Full loop test
# ---------------------------------------------------------------------------


class TestFullLoop:
    pytestmark = pytest.mark.git_repo

    @pytest.fixture(autouse=True)
    def _disable_sync_emitter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.next import runtime_bridge
        from runtime.next._internal_runtime.events import NullEmitter

        monkeypatch.setattr(runtime_bridge, "runtime_emitter_for_mission", lambda **_: NullEmitter())

    def test_full_loop_step_to_terminal(self, tmp_path: Path) -> None:
        """Drive mission from start to terminal through all steps."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"

        # Create required artifacts so CLI guards pass
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        # Create WP files with explicit dependencies for tasks_finalize guard
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: done\ndependencies: []\nrequirement_refs: [FR-001]\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )
        # Seed event log so runtime bridge reads WP01 as done
        _seed_wp_lane(feature_dir, "WP01", "done")

        from runtime.next.runtime_bridge import decide_next_via_runtime

        seen_steps = []
        for _i in range(40):  # 9 steps need more iterations
            decision = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
            if decision.kind == DecisionKind.terminal:
                break
            if decision.step_id:
                seen_steps.append(decision.step_id)

        assert decision.kind == DecisionKind.terminal
        # Should have visited at least discovery and specify
        assert "discovery" in seen_steps

    def test_repeated_poll_idempotency(self, tmp_path: Path) -> None:
        """Polling the same state twice returns consistent results."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import decide_next_via_runtime

        decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        # Don't advance — poll again (simulating re-poll)
        # Note: this will advance because each call to decide_next advances
        # The bridge always advances, which is the expected behavior.
        # The important thing is that it produces valid decisions.
        d2 = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert d2.kind in ("step", "terminal", "blocked", "decision_required")

    def test_offline_no_network(self, tmp_path: Path) -> None:
        """Verify no network calls — NullEmitter used throughout."""
        repo_root = _scaffold_project(tmp_path)

        from runtime.next.runtime_bridge import decide_next_via_runtime

        # This should work without any network access
        decision = decide_next_via_runtime("test", "042-test-feature", "success", repo_root)
        assert decision.kind in ("step", "terminal", "blocked", "decision_required")


# ---------------------------------------------------------------------------
# WP step helpers
# ---------------------------------------------------------------------------


class TestWPStepHelpers:
    def test_is_wp_iteration_step(self) -> None:
        from runtime.next.runtime_bridge import _is_wp_iteration_step

        assert _is_wp_iteration_step("implement") is True
        assert _is_wp_iteration_step("review") is True
        assert _is_wp_iteration_step("specify") is False
        assert _is_wp_iteration_step("discovery") is False

    def test_should_advance_no_tasks_dir(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _should_advance_wp_step

        assert _should_advance_wp_step("implement", tmp_path) is True

    @pytest.mark.git_repo
    def test_should_advance_hardfails_without_canonical_status(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01 task\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _should_advance_wp_step
        from specify_cli.status.lane_reader import CanonicalStatusNotFoundError

        with pytest.raises(CanonicalStatusNotFoundError):
            _should_advance_wp_step("implement", feature_dir)

    @pytest.mark.git_repo
    def test_should_advance_all_done(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "done", "WP02": "done"})

        from runtime.next.runtime_bridge import _should_advance_wp_step

        assert _should_advance_wp_step("implement", feature_dir) is True
        assert _should_advance_wp_step("review", feature_dir) is True

    @pytest.mark.git_repo
    def test_should_not_advance_planned_remain(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "done", "WP02": "planned"})

        from runtime.next.runtime_bridge import _should_advance_wp_step

        assert _should_advance_wp_step("implement", feature_dir) is False

    @pytest.mark.git_repo
    def test_implement_allows_for_review(self, tmp_path: Path) -> None:
        """Implement step allows for_review WPs (they're in progress of review)."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "done", "WP02": "for_review"})

        from runtime.next.runtime_bridge import _should_advance_wp_step

        assert _should_advance_wp_step("implement", feature_dir) is True
        assert _should_advance_wp_step("review", feature_dir) is False

    @pytest.mark.git_repo
    def test_review_allows_approved(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "approved", "WP02": "done"})

        from runtime.next.runtime_bridge import _should_advance_wp_step

        assert _should_advance_wp_step("implement", feature_dir) is True
        assert _should_advance_wp_step("review", feature_dir) is True

    def test_unknown_reduced_lane_blocks_instead_of_raising(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = tmp_path / "feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01 task\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next import runtime_bridge
        from runtime.next import committed_authority

        monkeypatch.setattr(runtime_bridge, "get_all_wp_snapshots", lambda _: {"WP01": {"lane": "unknown"}})
        monkeypatch.setattr(
            committed_authority,
            "wp_ending",
            lambda *_: SimpleNamespace(lane="unknown", reason_source=None),
        )
        assert runtime_bridge._count_wp_endings(feature_dir)[1] == 0
        assert runtime_bridge._should_advance_wp_step("implement", feature_dir) is False


# ---------------------------------------------------------------------------
# Atomic task step tests
# ---------------------------------------------------------------------------


class TestAtomicTaskSteps:
    @pytest.mark.git_repo
    def test_tasks_outline_guard_blocks_without_tasks_md(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_outline", feature_dir)
        assert len(failures) == 1
        assert "tasks.md" in failures[0]

    @pytest.mark.git_repo
    def test_tasks_outline_guard_passes_with_tasks_md(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_outline", feature_dir)
        assert len(failures) == 0

    @pytest.mark.git_repo
    def test_tasks_packages_guard_blocks_without_wp_files(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert len(failures) == 1
        assert "WP*.md" in failures[0]

    @pytest.mark.git_repo
    def test_tasks_packages_guard_passes_with_wp_files(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        _add_wp_files(feature_dir, {"WP01": "planned"})

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert len(failures) == 0

    @pytest.mark.git_repo
    def test_tasks_packages_guard_blocks_unmapped_functional_requirements(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n"
            "| FR-002 | Second | Must be mapped before finalization. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs:\n  - FR-001\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert len(failures) == 1
        assert "Requirement mapping incomplete" in failures[0]
        assert "unmapped FRs: FR-002" in failures[0]
        assert "map-requirements" in failures[0]

    @pytest.mark.git_repo
    def test_composed_tasks_packages_guard_blocks_unmapped_functional_requirements(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n"
            "| FR-002 | Second | Must be mapped before finalization. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-001]\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_composed_action_guard

        failures = _check_composed_action_guard(
            "tasks",
            feature_dir,
            legacy_step_id="tasks_packages",
        )
        assert len(failures) == 1
        assert "Requirement mapping incomplete" in failures[0]
        assert "unmapped FRs: FR-002" in failures[0]

    # -----------------------------------------------------------------
    # #3396 Story 3 — the bare-prose signal actually reaches spec-kitty
    # next's advance-vs-stay decision, in BOTH Story 3 configurations
    # (zero WP files; >=1 WP file, none referencing the bare-prose ids),
    # driven through the CLI-native and composed integration entry points
    # (not only the pure evaluate_guards core in isolation — see
    # tests/runtime/test_bridge_cores.py for the pure-core teeth tests).
    # -----------------------------------------------------------------

    _BARE_PROSE_REPRO_SPEC = (
        "# Spec\n\n"
        "## Functional Requirements\n\n"
        "FR-001 the loader must reject bad input. FR-002 the error must name "
        "the offending path.\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| NFR-001 | Perf | Some criteria. | proposed |\n"
    )

    @pytest.mark.git_repo
    def test_tasks_packages_guard_blocks_bare_prose_requirements_zero_wp_files(self, tmp_path: Path) -> None:
        """Story 3 config (a): zero WP files materialized yet. Before this
        WP's wiring, `_check_cli_guards("tasks_packages", ...)` returned only
        the generic 'materialize WP packages first' message regardless of
        spec.md content -- this is the exact `_zero_declared_requirement_
        block` (3823f2b00) dead-path shape this mission exists to avoid
        repeating. The failure detail must be traceable to FR-001/FR-002
        specifically, not only the generic message that would fire
        regardless."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(self._BARE_PROSE_REPRO_SPEC, encoding="utf-8")

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert any("FR-001" in f and "FR-002" in f for f in failures), failures
        assert any("WP*.md" in f for f in failures), failures

    @pytest.mark.git_repo
    def test_composed_tasks_finalize_guard_blocks_bare_prose_requirements_with_unrelated_wp_files(self, tmp_path: Path) -> None:
        """Story 3 config (b): >=1 WP file exists, referencing only the
        correctly-declared NFR-001 -- NOT the bare-prose FR-001/FR-002 (those
        ids were never offered by map-requirements, since they are
        undeclared). The pre-existing missing/unknown/unmapped
        requirement-mapping check is clean here by construction
        (`functional_requirement_ids` is empty since no FR is declared in a
        recognized shape), proving this is not merely that pre-existing check
        incidentally catching the same case (spec.md Story 3 AC2)."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(self._BARE_PROSE_REPRO_SPEC, encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\ndependencies: []\nrequirement_refs: [NFR-001]\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_composed_action_guard, _check_requirement_mapping_ready

        # Sanity: the pre-existing requirement-mapping check is clean here --
        # the assertion below is not incidentally passing because of it.
        assert _check_requirement_mapping_ready(feature_dir) == []

        failures = _check_composed_action_guard("tasks", feature_dir, legacy_step_id="tasks_finalize")
        assert any("FR-001" in f and "FR-002" in f for f in failures), failures

    @pytest.mark.git_repo
    def test_tasks_packages_guard_passes_when_functional_requirements_are_mapped(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n"
            "| FR-002 | Second | Covered by WP02. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-001]\n---\n# WP01\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02.md").write_text(
            "---\nwork_package_id: WP02\ntitle: WP02\nrequirement_refs: [FR-002]\n---\n# WP02\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert failures == []

    @pytest.mark.git_repo
    def test_tasks_packages_guard_uses_legacy_tasks_md_refs_without_wps_yaml(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n\n**Requirement Refs**: FR-001\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert failures == []

    @pytest.mark.git_repo
    def test_tasks_packages_guard_rejects_indented_legacy_tasks_md_heading(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text(
            "  ## Work Package WP01\n\n**Requirement Refs**: FR-001\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert failures
        assert "missing refs for WPs: WP01" in failures[0]

    @pytest.mark.git_repo
    def test_tasks_packages_guard_accepts_tab_after_hashes_in_legacy_tasks_md_heading(self, tmp_path: Path) -> None:
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text(
            "##\tWork Package WP01\n\n**Requirement Refs**: FR-001\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert failures == []

    @pytest.mark.git_repo
    def test_tasks_packages_guard_blocks_missing_requirement_refs(self, tmp_path: Path) -> None:
        """WP has no requirement_refs at all → missing-refs branch."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert len(failures) == 1
        assert "missing refs for WPs: WP01" in failures[0]
        assert "map-requirements" in failures[0]

    @pytest.mark.git_repo
    def test_tasks_packages_guard_blocks_unknown_requirement_refs(self, tmp_path: Path) -> None:
        """WP references an FR that doesn't exist in spec.md → unknown-refs branch."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-999]\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert len(failures) == 1
        # WP04/FR-010: the "unknown refs: WP: ref" bucket is replaced, in the
        # same position, by "rejected refs: WP: ref (<reason>)" naming the
        # shared reason. WP01's only ref is rejected, so it has no accepted
        # ref and is also reported missing (T021 step 6).
        assert "missing refs for WPs: WP01" in failures[0]
        assert "rejected refs: WP01: FR-999 (unknown_spec_id)" in failures[0]

    @pytest.mark.git_repo
    def test_requirement_mapping_preflight_noop_when_no_tasks_dir(self, tmp_path: Path) -> None:
        """Helper returns [] when tasks/ does not exist even if spec.md does."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_requirement_mapping_ready

        assert _check_requirement_mapping_ready(feature_dir) == []

    @pytest.mark.git_repo
    def test_requirement_mapping_preflight_wraps_unexpected_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unexpected exceptions during preflight surface as a guard failure, not a crash."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-001]\n---\n",
            encoding="utf-8",
        )

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("simulated preflight crash")

        from specify_cli import requirement_mapping as rm

        monkeypatch.setattr(rm, "parse_requirement_ids_from_spec_md", _boom)

        from runtime.next.runtime_bridge import _check_requirement_mapping_ready

        failures = _check_requirement_mapping_ready(feature_dir)
        assert len(failures) == 1
        assert "Requirement mapping preflight failed" in failures[0]
        assert "simulated preflight crash" in failures[0]

    @pytest.mark.git_repo
    def test_requirement_mapping_advisory_computation_crash_does_not_reach_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """#3394 focused-review F3 (severity 2) fix: a crash in the advisory
        computation (``find_undeclared_requirement_citations``) must NOT
        propagate into ``_check_requirement_mapping_ready``'s broad
        ``except Exception`` -- unlike ``test_requirement_mapping_preflight_
        wraps_unexpected_errors`` above (which pins that a REAL extraction
        crash, e.g. in ``parse_requirement_ids_from_spec_md``, correctly
        fails closed), the advisory is purely diagnostic and must fail OPEN:
        swallowed and logged, never surfaced as a gate failure, even when its
        own computation raises. Before the F3 fix this test is RED (the
        exception reaches the outer handler and becomes a generic
        "Requirement mapping preflight failed" failure)."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-001]\n---\n# WP01\n",
            encoding="utf-8",
        )

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("simulated advisory crash")

        from specify_cli import requirement_mapping as rm

        monkeypatch.setattr(rm, "find_undeclared_requirement_citations", _boom)

        from runtime.next.runtime_bridge import _check_requirement_mapping_ready

        caplog.set_level("DEBUG")
        failures = _check_requirement_mapping_ready(feature_dir)

        # The real signal: no gate failure at all, and specifically not the
        # generic fail-closed message the advisory crash would otherwise
        # produce if it reached the outer except.
        assert failures == []
        assert not any("Requirement mapping preflight failed" in f for f in failures)
        assert not any("simulated advisory crash" in f for f in failures)

        # Swallowed-and-logged, not silently dropped: the crash is still
        # observable at DEBUG level.
        crash_records = [r for r in caplog.records if "advisory computation failed" in r.message]
        assert len(crash_records) == 1

    # -----------------------------------------------------------------
    # #3394 negative-space regression pins, plus the F1 advisory-logging
    # coverage, exercised end-to-end through the real spec.md/tasks parse
    # path (not just RequirementMappingFacts construction — see
    # tests/runtime/test_bridge_cores.py for the pure-core equivalents).
    # -----------------------------------------------------------------

    @pytest.mark.git_repo
    def test_requirement_mapping_zero_declared_logs_advisory_while_still_blocking_on_missing_refs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """spec.md declares NOTHING recognizable (bare, unbulleted, unbolded
        FR-001/FR-002 sentences) and WP01 has no requirement_refs at all --
        the pre-existing missing-refs check already blocks this
        unconditionally (WP01's refs are empty -> "missing"), so the F1
        advisory logs alongside that block rather than replacing or
        preventing it. Confirms the advisory fires on the same content that
        also happens to block via a pre-existing, unrelated path."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n## Functional Requirements\n\nFR-001 must hold. FR-002 too.\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_requirement_mapping_ready

        caplog.set_level("WARNING")
        failures = _check_requirement_mapping_ready(feature_dir)

        assert len(failures) == 1
        assert failures[0].startswith("Requirement mapping incomplete before finalize-tasks: ")
        assert "missing refs for WPs: WP01" in failures[0]

        advisory_records = [r for r in caplog.records if "mentions requirement-shaped token(s)" in r.message]
        assert len(advisory_records) == 1
        assert "spec.md mentions requirement-shaped token(s)" in advisory_records[0].message
        assert not advisory_records[0].message.startswith("Requirement mapping incomplete")

    @pytest.mark.git_repo
    def test_requirement_mapping_zero_declared_zero_raw_tokens_does_not_block(self, tmp_path: Path) -> None:
        """The genuinely empty case: a spec with no formal requirements at
        all (zero declared ids AND zero raw FR-/NFR-/C-NNN tokens anywhere)
        must NOT block -- there is nothing to be missing."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n## Overview\n\nThis mission has no formal functional requirements; it is a small documentation-only change.\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)  # exists, but deliberately no WP*.md files

        from runtime.next.runtime_bridge import _check_requirement_mapping_ready

        assert _check_requirement_mapping_ready(feature_dir) == []

    @pytest.mark.git_repo
    def test_requirement_mapping_foreign_citation_shape_now_blocks_per_3396(self, tmp_path: Path) -> None:
        """RE-PINNED (operator ruling 2026-08-14): #3396 supersedes #3395's
        advisory-only decision for this exact shape. #3394/#3395's repro --
        spec.md DECLARES three FRs in a table and merely CITES a foreign,
        already-shipped FR-021 in bare prose in that same section -- was
        pinned non-blocking under #3395's fix (`find_undeclared_requirement_
        citations` never fires here, since the section's declared set is
        non-empty). #3396's new, per-token, document-scoped detector
        (`find_bare_prose_requirement_ids`) cannot distinguish "this spec's
        own uncounted requirement" from "a bare-prose citation of a foreign
        id" -- both are simply a ref-shaped token, in a Requirements
        section, absent from the document-wide declared set -- and #3396 is
        chartered to block on that shape rather than stay silent
        (DIRECTIVE_041: the product decision this test pins changed, so the
        old non-blocking assertion was stale, not the wiring). The
        pre-#3396 requirement-mapping decision alone stays clean (every
        declared FR is still mapped to WP01); only the full guard path,
        which now also reads the bare-prose fact, blocks."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | First | Covered by WP01. | proposed |\n"
            "| FR-002 | Second | Covered by WP01. | proposed |\n"
            "| FR-003 | Third | Covered by WP01. | proposed |\n\n"
            "This mission is easy to miss without prior art -- see FR-021's "
            "default-pack materialization for the pattern this follows.\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs:\n  - FR-001\n  - FR-002\n  - FR-003\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards, _check_requirement_mapping_ready

        # The pre-#3396 requirement-mapping decision alone is still clean --
        # every declared FR is mapped to WP01.
        assert _check_requirement_mapping_ready(feature_dir) == []
        # But the full `spec-kitty next` guard path now blocks on the
        # bare-prose FR-021 citation (#3396 supersedes #3395's advisory-only
        # treatment of this shape).
        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert any("FR-021" in f for f in failures), failures

    @pytest.mark.git_repo
    def test_requirement_mapping_mixed_declared_and_bare_prose_now_blocks_per_3396(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """RE-PINNED (operator ruling 2026-08-14): #3396 supersedes #3395's
        advisory-only decision for this exact shape. The F4 finding's own
        repro fixture (bare-prose FR-001/FR-002 alongside a properly
        DECLARED table-row NFR-001, WP01 mapping only NFR-001) IS #3396's own
        target repro -- the mission's whole reason to exist (Story 1).
        Under #3395's fix it was pinned non-blocking-but-logged (the F1
        advisory surfaces the "why" without gating). #3396 deliberately
        supersedes that advisory-only decision for this shape and blocks
        instead (DIRECTIVE_041: the product decision this test pins
        changed, so the old non-blocking assertion was stale, not the
        wiring). The F1 advisory keeps logging alongside the new blocking
        failure -- both signals now coexist for this shape."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n"
            "## Functional Requirements\n\n"
            "FR-001 must hold. FR-002 too.\n\n"
            "## Non-Functional Requirements\n\n"
            "| ID | Requirement | Status |\n"
            "| --- | --- | --- |\n"
            "| NFR-001 | Latency under 200ms. | proposed |\n",
            encoding="utf-8",
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs:\n  - NFR-001\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards, _check_requirement_mapping_ready

        caplog.set_level("WARNING")
        # The pre-#3396 requirement-mapping decision alone is still clean --
        # NFR-001 is mapped, and #3394/#3395's own fix still does not count
        # bare FR-001/FR-002 as declared requirements.
        assert _check_requirement_mapping_ready(feature_dir) == []
        # But the full `spec-kitty next` guard path now blocks (#3396
        # supersedes #3395's advisory-only treatment of this shape):
        failures = _check_cli_guards("tasks_packages", feature_dir)
        assert any("FR-001" in f and "FR-002" in f for f in failures), failures

        # The pre-existing F1 advisory still logs alongside the new
        # blocking failure -- both signals coexist for this shape.
        advisory_records = [r for r in caplog.records if "mentions requirement-shaped token(s)" in r.message]
        assert len(advisory_records) >= 1
        assert "Functional Requirements" in advisory_records[0].message
        assert "FR-001, FR-002" in advisory_records[0].message

    @pytest.mark.git_repo
    def test_tasks_finalize_guard_blocks_without_raw_dependencies(self, tmp_path: Path) -> None:
        """WP files exist but no explicit dependencies: in raw frontmatter."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        # WP file WITHOUT dependencies field in raw frontmatter
        _add_wp_files(feature_dir, {"WP01": "planned"})

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert len(failures) == 1
        assert "dependencies" in failures[0]

    @pytest.mark.git_repo
    def test_tasks_finalize_guard_passes_with_raw_dependencies(self, tmp_path: Path) -> None:
        """WP files have dependencies: [...] explicitly written."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: planned\ndependencies: []\ntitle: WP01\n---\n# WP01\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert len(failures) == 0

    @pytest.mark.git_repo
    def test_tasks_finalize_guard_rejects_auto_injected_dependencies(self, tmp_path: Path) -> None:
        """WP file with NO dependencies line — read_frontmatter would inject [],
        but raw check correctly rejects."""
        repo_root = _scaffold_project(tmp_path)
        feature_dir = repo_root / "kitty-specs" / "042-test-feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        # Frontmatter without dependencies field
        (tasks_dir / "WP01.md").write_text(
            "---\nwork_package_id: WP01\nlane: planned\ntitle: WP01\n---\n# WP01\nContent.\n",
            encoding="utf-8",
        )

        from runtime.next.runtime_bridge import _check_cli_guards

        failures = _check_cli_guards("tasks_finalize", feature_dir)
        assert len(failures) == 1
        assert "dependencies" in failures[0]

    def test_has_raw_dependencies_field_positive(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _has_raw_dependencies_field

        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\ndependencies: []\n---\n# WP01\n",
            encoding="utf-8",
        )
        assert _has_raw_dependencies_field(wp_file) is True

    def test_has_raw_dependencies_field_negative(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _has_raw_dependencies_field

        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\nlane: planned\n---\n# WP01\n",
            encoding="utf-8",
        )
        assert _has_raw_dependencies_field(wp_file) is False

    def test_has_raw_dependencies_field_no_frontmatter(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _has_raw_dependencies_field

        wp_file = tmp_path / "WP01.md"
        wp_file.write_text("# WP01\nNo frontmatter here.\n", encoding="utf-8")
        assert _has_raw_dependencies_field(wp_file) is False

    def test_has_raw_dependencies_field_with_values(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _has_raw_dependencies_field

        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(
            '---\nwork_package_id: WP02\ndependencies: ["WP01"]\n---\n# WP02\n',
            encoding="utf-8",
        )
        assert _has_raw_dependencies_field(wp_file) is True


class TestQueryCurrentStateTypedErrorPassthrough:
    """FR-001 / C-IC02: ``query_current_state`` passes a *read-path* ActionContextError
    through verbatim (the #15 fix), and only collapses a genuinely-missing mission to
    ``MISSION_NOT_FOUND``. Covers the discriminator branch at runtime_bridge.py."""

    def test_read_path_error_reraised_verbatim(self, monkeypatch, tmp_path: Path) -> None:
        import mission_runtime
        from mission_runtime import ActionContextError
        from runtime.next.runtime_bridge import query_current_state

        def _raise_read_path(*_a: object, **_k: object) -> None:
            raise ActionContextError(
                "COORDINATION_BRANCH_DELETED",
                "coordination branch deleted; checked .worktrees/<slug>-coord and primary",
            )

        monkeypatch.setattr(mission_runtime, "mission_context_for", _raise_read_path)

        with pytest.raises(ActionContextError) as exc_info:
            query_current_state(
                agent="claude",
                mission_slug="read-path-error-fidelity-adoption-01KV8NPC",
                repo_root=tmp_path,
            )
        # The typed read-path code survives — NOT collapsed to MISSION_NOT_FOUND.
        assert exc_info.value.code == "COORDINATION_BRANCH_DELETED"

    def test_genuinely_missing_mission_collapses_to_mission_not_found(self, monkeypatch, tmp_path: Path) -> None:
        import mission_runtime
        from mission_runtime import ActionContextError
        from runtime.next.runtime_bridge import MissionNotFoundError, query_current_state

        def _raise_unresolved(*_a: object, **_k: object) -> None:
            raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "no mission directory at all")

        monkeypatch.setattr(mission_runtime, "mission_context_for", _raise_unresolved)

        with pytest.raises(MissionNotFoundError):
            query_current_state(agent="claude", mission_slug="no-such-mission", repo_root=tmp_path)


# ---------------------------------------------------------------------------
# Owned-checkout (``--owned-checkout`` / ``effective_root``) threading —
# checkout-ownership landing branch (#3328). These classes drive the exact
# branches the landing PR's acceptance proof
# (tests/e2e/test_worktree_owned_root_concurrency.py) exercises only through
# the INSTALLED CLI as a subprocess — invisible to pytest-cov, and that e2e
# module sits outside every coverage-collecting CI job's ``paths`` anyway
# (it is not under tests/next/ or tests/specify_cli/next/). Driving the same
# functions in-process here, in a module already wired into
# integration-tests-next's ``--cov=src/runtime/next`` collection, closes that
# visibility gap without touching product code.
# ---------------------------------------------------------------------------


class TestOwnedCoordWorkspaceRetry:
    """``_resolve_owned_coordination_workspace`` / ``_is_transient_git_
    worktree_contention``: the bounded-retry classifier for concurrent
    ``git worktree add`` shared-registry contention (two owned missions
    racing ``CoordinationWorkspace.resolve`` concurrently). Mirrors
    tests/e2e/test_worktree_owned_root_concurrency.py's in-process retry
    assertions, but from a module pytest-cov actually attributes to the
    diff-coverage critical-path gate."""

    def test_happy_path_returns_without_any_retry(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace

        expected = tmp_path / "coord"

        class _Workspace:
            calls = 0

            @classmethod
            def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
                cls.calls += 1
                return expected

        result = _resolve_owned_coordination_workspace(_Workspace, tmp_path, "happy-path-01KZTEST", "01KZTEST")

        assert result == expected
        assert _Workspace.calls == 1

    def test_permanent_git_error_reraises_immediately(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A permanent (non-lock) git failure is re-raised on the first
        attempt, never retry-masked."""
        from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace

        permanent = subprocess.CalledProcessError(128, ["git", "worktree", "add"], stderr="fatal: permanent worktree failure")

        class _PermanentlyBrokenWorkspace:
            calls = 0

            @classmethod
            def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
                cls.calls += 1
                raise permanent

        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        with pytest.raises(subprocess.CalledProcessError) as raised:
            _resolve_owned_coordination_workspace(_PermanentlyBrokenWorkspace, tmp_path, "permanent-failure-01KZTEST", "01KZTEST")
        assert raised.value is permanent
        assert _PermanentlyBrokenWorkspace.calls == 1

    def test_permission_denied_lock_wording_is_never_retried(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Lock wording alone cannot make a permanent permission error
        retryable — the classifier requires the SPECIFIC known contention
        diagnostics, not any mention of ``.lock``."""
        from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace

        permission_denied = subprocess.CalledProcessError(
            128,
            ["git", "worktree", "add"],
            stderr="fatal: could not lock config file .git/config: Permission denied",
        )

        class _PermissionDeniedWorkspace:
            calls = 0

            @classmethod
            def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
                cls.calls += 1
                raise permission_denied

        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        with pytest.raises(subprocess.CalledProcessError) as raised:
            _resolve_owned_coordination_workspace(_PermissionDeniedWorkspace, tmp_path, "permission-denied-01KZTEST", "01KZTEST")
        assert raised.value is permission_denied
        assert _PermissionDeniedWorkspace.calls == 1

    def test_known_git_lock_contention_recovers_within_bound(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Known ``config.lock`` contention retries and recovers within the
        fixed 20-attempt bound."""
        from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace

        expected = tmp_path / "coord"

        class _TransientWorkspace:
            calls = 0

            @classmethod
            def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
                cls.calls += 1
                if cls.calls < 3:
                    raise subprocess.CalledProcessError(
                        128,
                        ["git", "worktree", "add"],
                        stderr="fatal: Unable to create '/repo/.git/config.lock': File exists.",
                    )
                return expected

        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        result = _resolve_owned_coordination_workspace(_TransientWorkspace, tmp_path, "transient-contention-01KZTEST", "01KZTEST")

        assert result == expected
        assert _TransientWorkspace.calls == 3

    def test_persistent_contention_reraises_the_exact_error_after_bound(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Persistent recognized contention keeps its terminal exception
        identity after exhausting all 20 attempts — never silently swallowed."""
        from runtime.next.runtime_bridge import _resolve_owned_coordination_workspace

        terminal = subprocess.CalledProcessError(
            128,
            ["git", "worktree", "add"],
            stderr="fatal: could not lock config file .git/config: File exists",
        )

        class _PersistentlyContendedWorkspace:
            calls = 0

            @classmethod
            def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
                cls.calls += 1
                raise terminal

        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        with pytest.raises(subprocess.CalledProcessError) as raised:
            _resolve_owned_coordination_workspace(
                _PersistentlyContendedWorkspace,
                tmp_path,
                "persistent-contention-01KZTEST",
                "01KZTEST",
            )
        assert raised.value is terminal
        assert _PersistentlyContendedWorkspace.calls == 20


class TestIsTransientGitWorktreeContention:
    """Direct branch coverage for the lock-diagnostic classifier itself,
    independent of the retry loop above."""

    def test_non_128_returncode_is_never_transient(self) -> None:
        from runtime.next.runtime_bridge import _is_transient_git_worktree_contention

        exc = subprocess.CalledProcessError(1, ["git", "worktree", "add"], stderr="fatal: unrelated failure")
        assert _is_transient_git_worktree_contention(exc) is False

    @pytest.mark.parametrize(
        "stderr",
        [
            "fatal: Unable to create '/repo/.git/config.lock': File exists.",
            "fatal: could not lock config file .git/config: File exists",
            "fatal: another git process seems to be running in this repository; lock held",
        ],
        ids=[
            "config-lock-file-exists",
            "could-not-lock-file-exists",
            "another-git-process-lock",
        ],
    )
    def test_recognized_lock_wordings_are_transient(self, stderr: str) -> None:
        from runtime.next.runtime_bridge import _is_transient_git_worktree_contention

        exc = subprocess.CalledProcessError(128, ["git", "worktree", "add"], stderr=stderr)
        assert _is_transient_git_worktree_contention(exc) is True

    def test_returncode_128_with_unrelated_message_is_not_transient(self) -> None:
        from runtime.next.runtime_bridge import _is_transient_git_worktree_contention

        exc = subprocess.CalledProcessError(128, ["git", "worktree", "add"], stderr="fatal: not a git repository")
        assert _is_transient_git_worktree_contention(exc) is False


class TestMissionRoutesThroughCoordinationOwnedCheckout:
    """``_mission_routes_through_coordination``'s ``effective_root`` fork:
    reads the stored topology off ``mission_context_for(effective_root=...)``
    instead of the primary-folding ``placement_seam``."""

    def test_owned_checkout_reads_topology_via_mission_context_for(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        import mission_runtime
        from mission_runtime import MissionArtifactKind
        from runtime.next.runtime_bridge import _mission_routes_through_coordination

        feature_dir = tmp_path / "owned-feature"
        feature_dir.mkdir()
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_type": "software-dev",
                    "topology": "coord",
                    "coordination_branch": "kitty/mission-owned-x",
                }
            ),
            encoding="utf-8",
        )

        class _FakeArtifact:
            read_dir = feature_dir

        class _FakeMissionContext:
            def artifact(self, kind: object) -> _FakeArtifact:
                assert kind is MissionArtifactKind.PRIMARY_METADATA
                return _FakeArtifact()

        calls: list[tuple[Path, str, Path | None]] = []

        def _fake_mission_context_for(repo_root, mission_slug, *, effective_root=None):
            calls.append((repo_root, mission_slug, effective_root))
            return _FakeMissionContext()

        monkeypatch.setattr(mission_runtime, "mission_context_for", _fake_mission_context_for)

        owned_root = tmp_path / "owned-checkout"
        decoy_repo_root = tmp_path / "decoy-primary-never-read"

        result = _mission_routes_through_coordination("owned-mission", decoy_repo_root, effective_root=owned_root)

        assert result is True
        assert calls == [(decoy_repo_root, "owned-mission", owned_root)]


class TestWrapWithDecisionGitLogOwnedCheckout:
    """Owned-checkout fork of ``_wrap_with_decision_git_log`` (#3328): the
    coordination-branch/mission-id read forks through
    ``mission_context_for(effective_root=...)`` instead of the
    primary-folding helpers, and the coord ``worktree_root`` selection forks
    between the already-materialized ``.exists()`` fast path and the
    retry-guarded ``_resolve_owned_coordination_workspace`` composition
    path."""

    @staticmethod
    def _install_owned_mission_context(
        monkeypatch: pytest.MonkeyPatch,
        *,
        primary_metadata_dir: Path,
        coordination_branch: str,
        mission_id: str,
    ) -> None:
        import mission_runtime
        from mission_runtime import MissionArtifactKind

        class _FakeArtifact:
            def __init__(self, *, read_dir: Path | None = None, commit_target: object = None) -> None:
                self.read_dir = read_dir
                self.commit_target = commit_target

        class _FakeMissionContext:
            def artifact(self, kind: object) -> _FakeArtifact:
                if kind is MissionArtifactKind.STATUS_STATE:
                    return _FakeArtifact(commit_target=SimpleNamespace(ref=coordination_branch))
                assert kind is MissionArtifactKind.PRIMARY_METADATA
                return _FakeArtifact(read_dir=primary_metadata_dir)

        monkeypatch.setattr(mission_runtime, "mission_context_for", lambda *_a, **_k: _FakeMissionContext())
        monkeypatch.setattr(
            "specify_cli.mission_metadata.resolve_mission_identity",
            lambda _dir: SimpleNamespace(mission_id=mission_id),
        )

    def test_materialized_worktree_root_is_used_as_is(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """When the coord worktree candidate already exists on disk, the
        owned fork trusts it directly and never composes a fresh one."""
        from runtime.next import runtime_bridge
        from specify_cli.coordination.workspace import CoordinationWorkspace

        monkeypatch.setattr(runtime_bridge, "_mission_routes_through_coordination", lambda *_a, **_k: True)
        primary_metadata_dir = tmp_path / "primary-metadata"
        primary_metadata_dir.mkdir()
        mission_id = "01K3PW7QRSTVXYZ23456789ABC"
        mission_slug = "owned-materialized-mission"
        self._install_owned_mission_context(
            monkeypatch,
            primary_metadata_dir=primary_metadata_dir,
            coordination_branch="kitty/mission-owned-materialized",
            mission_id=mission_id,
        )
        worktree_root_candidate = CoordinationWorkspace.worktree_path(tmp_path, mission_slug, mission_id[:8])
        worktree_root_candidate.mkdir(parents=True)

        def _must_not_run(*_a: object, **_k: object) -> Path:
            raise AssertionError("_resolve_owned_coordination_workspace must not run when the candidate worktree already exists on disk")

        monkeypatch.setattr(runtime_bridge, "_resolve_owned_coordination_workspace", _must_not_run)

        emitter = SimpleNamespace()
        owned_root = tmp_path / "owned-checkout"
        wrapped = runtime_bridge._wrap_with_decision_git_log(emitter, mission_slug, tmp_path, effective_root=owned_root)

        assert wrapped._worktree_root == worktree_root_candidate

    def test_unmaterialized_worktree_root_resolves_via_owned_retry_helper(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """When the coord worktree candidate does NOT yet exist, the owned
        fork composes it through ``_resolve_owned_coordination_workspace``
        (the bounded-retry helper) instead of the non-owned
        ``CoordinationWorkspace.resolve`` call."""
        from runtime.next import runtime_bridge
        from specify_cli.coordination.workspace import CoordinationWorkspace

        monkeypatch.setattr(runtime_bridge, "_mission_routes_through_coordination", lambda *_a, **_k: True)
        primary_metadata_dir = tmp_path / "primary-metadata"
        primary_metadata_dir.mkdir()
        mission_id = "01K3PW7QRSTVXYZ23456789ABC"
        mission_slug = "owned-unmaterialized-mission"
        self._install_owned_mission_context(
            monkeypatch,
            primary_metadata_dir=primary_metadata_dir,
            coordination_branch="kitty/mission-owned-unmaterialized",
            mission_id=mission_id,
        )
        # Deliberately do NOT create the candidate worktree dir: .exists() is
        # False, so the owned fork must run the retry-guarded composer.
        resolved_via_retry_helper = tmp_path / "resolved-via-retry-helper"

        def _fake_resolve(_cls: object, _root: Path, _slug: str, _mid8: str) -> Path:
            return resolved_via_retry_helper

        monkeypatch.setattr(CoordinationWorkspace, "resolve", classmethod(_fake_resolve))

        emitter = SimpleNamespace()
        owned_root = tmp_path / "owned-checkout"
        wrapped = runtime_bridge._wrap_with_decision_git_log(emitter, mission_slug, tmp_path, effective_root=owned_root)

        assert wrapped._worktree_root == resolved_via_retry_helper

    def test_non_owned_unmaterialized_worktree_root_uses_plain_resolve(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Anti-vacuity / control: WITHOUT ``effective_root`` (the historical,
        non-owned call shape), an unmaterialized coord candidate still goes
        through the plain ``CoordinationWorkspace.resolve`` call -- never the
        owned retry-guarded composer. Proves the two branches genuinely
        diverge on ``effective_root``, not on ``coord_routing_topology``
        alone."""
        from runtime.next import runtime_bridge
        from specify_cli.coordination.workspace import CoordinationWorkspace

        monkeypatch.setattr(runtime_bridge, "_mission_routes_through_coordination", lambda *_a, **_k: True)
        mission_id = "01K3PW7QRSTVXYZ23456789ABC"
        mission_slug = "non-owned-unmaterialized-mission"
        monkeypatch.setattr(
            runtime_bridge,
            "_resolve_coordination_branch",
            lambda *_a, **_k: "kitty/mission-non-owned-unmaterialized",
        )
        monkeypatch.setattr(runtime_bridge, "_resolve_mission_ulid", lambda *_a, **_k: mission_id)

        def _must_not_run(*_a: object, **_k: object) -> Path:
            raise AssertionError("_resolve_owned_coordination_workspace must not run without effective_root -- that is the owned-checkout-only path")

        monkeypatch.setattr(runtime_bridge, "_resolve_owned_coordination_workspace", _must_not_run)
        resolved_via_plain_resolve = tmp_path / "resolved-via-plain-resolve"

        def _fake_resolve(_cls: object, _root: Path, _slug: str, _mid8: str) -> Path:
            return resolved_via_plain_resolve

        monkeypatch.setattr(CoordinationWorkspace, "resolve", classmethod(_fake_resolve))

        emitter = SimpleNamespace()
        wrapped = runtime_bridge._wrap_with_decision_git_log(emitter, mission_slug, tmp_path)

        assert wrapped._worktree_root == resolved_via_plain_resolve


class TestDecideNextViaRuntimeOwnedCheckout:
    """End-to-end owned-checkout thread through ``decide_next_via_runtime`` ->
    ``_dn_bootstrap`` -> ``_wrap_with_decision_git_log`` for a real
    (coord-less) scaffolded mission. Complements the narrower unit tests
    above by proving the ``effective_root`` fork composes across the whole
    bootstrap phase without mocking ``mission_context_for``."""

    @pytest.fixture(autouse=True)
    def _disable_sync_emitter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.next import runtime_bridge
        from runtime.next._internal_runtime.events import NullEmitter

        monkeypatch.setattr(runtime_bridge, "runtime_emitter_for_mission", lambda **_: NullEmitter())

    def test_owned_checkout_resolves_and_advances_the_mission(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import decide_next_via_runtime

        owned_root = _scaffold_project(tmp_path, mission_slug="042-owned-feature")
        decoy_repo_root = tmp_path / "decoy-primary-never-read"

        decision = decide_next_via_runtime(
            "claude",
            "042-owned-feature",
            "success",
            decoy_repo_root,
            effective_root=owned_root,
        )

        assert decision.mission_slug == "042-owned-feature"
        assert decision.kind in ("step", "terminal", "blocked", "decision_required")
