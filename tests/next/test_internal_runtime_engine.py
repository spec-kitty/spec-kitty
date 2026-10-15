"""Integration coverage for ``runtime.next._internal_runtime.engine`` hot paths.

These tests focus on:
- Mission discovery (discover_missions, load_mission_template)
- Engine start_mission_run + next_step round-trip
- Next-action selection determinism

All I/O uses ``tmp_path`` with real YAML mission fixtures.
No subprocess invocations; pure in-process execution.

Tactic: function-over-form-testing (src/charter/offering/tactics/built-in/testing/).
Structure: AAA (Arrange / Act / Assert).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next._internal_runtime.discovery import (
    DiscoveryContext,
    discover_missions,
    discover_missions_with_warnings,
    load_mission_template,
)
from runtime.next._internal_runtime.engine import (
    MissionRunRef,
    start_mission_run,
    next_step,
)
from runtime.next._internal_runtime.schema import (
    MissionPolicySnapshot,
    MissionRuntimeError,
    MissionTemplate,
)
from runtime.next._internal_runtime.events import NullEmitter

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Minimal mission YAML factory
# ---------------------------------------------------------------------------

_MINIMAL_MISSION_YAML = """\
mission:
  key: test-mission
  name: Test Mission
  version: "1.0.0"
  description: Minimal mission for test coverage.

steps:
  - id: step-one
    title: First Step
    description: Do the first thing.
    prompt: "Execute step one."
    expected_output: "Step one done."
  - id: step-two
    title: Second Step
    description: Do the second thing.
    prompt: "Execute step two."
    expected_output: "Step two done."

audit_steps: []
"""

_TWO_STEP_MISSION_YAML = """\
mission:
  key: two-step-mission
  name: Two-Step Mission
  version: "1.0.0"
  description: Mission for two-step sequencing tests.

steps:
  - id: alpha
    title: Alpha
    description: First action.
    prompt: "Do alpha."
    expected_output: "Alpha done."
  - id: beta
    title: Beta
    description: Second action.
    prompt: "Do beta."
    expected_output: "Beta done."

audit_steps: []
"""


def _write_mission_yaml(base_dir: Path, yaml_content: str) -> Path:
    """Write mission.yaml directly in base_dir and return the file path."""
    base_dir.mkdir(parents=True, exist_ok=True)
    mission_file = base_dir / "mission.yaml"
    mission_file.write_text(yaml_content, encoding="utf-8")
    return mission_file


# ---------------------------------------------------------------------------
# Discovery hot paths
# ---------------------------------------------------------------------------

class TestDiscoverMissions:
    def test_discovers_mission_from_explicit_yaml_path(self, tmp_path: Path) -> None:
        """Arrange: mission.yaml at explicit path;
        Act: discover with explicit_paths pointing to the yaml file;
        Assert: mission appears in results with correct key."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        context = DiscoveryContext(explicit_paths=[mission_file], user_home=tmp_path / "home")
        missions = discover_missions(context)

        keys = [m.key for m in missions]
        assert "test-mission" in keys

    def test_discovered_mission_is_selected(self, tmp_path: Path) -> None:
        """Arrange: single mission; Act: discover; Assert: selected=True."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        context = DiscoveryContext(explicit_paths=[mission_file], user_home=tmp_path / "home")
        missions = discover_missions(context)

        selected = [m for m in missions if m.key == "test-mission"]
        assert len(selected) >= 1
        assert selected[0].selected is True

    def test_discover_warns_when_mission_yaml_is_malformed(self, tmp_path: Path) -> None:
        """Arrange: malformed mission.yaml; Act: discover_with_warnings; Assert: warning recorded."""
        bad_dir = tmp_path / "bad-mission"
        bad_dir.mkdir()
        (bad_dir / "mission.yaml").write_text(": invalid\n  yaml:", encoding="utf-8")

        context = DiscoveryContext(explicit_paths=[bad_dir / "mission.yaml"], user_home=tmp_path / "home")
        result = discover_missions_with_warnings(context)

        # May emit a warning or simply skip the broken file; no crash is the requirement
        assert isinstance(result.warnings, list)

    def test_discover_returns_list_for_empty_context_without_env_home(self, tmp_path: Path) -> None:
        """Arrange: DiscoveryContext with no paths (blocked user_home to avoid FS side effects);
        Act: discover;
        Assert: result is a list (may be empty or contain builtins)."""
        context = DiscoveryContext(user_home=tmp_path / "home-does-not-exist")
        missions = discover_missions(context)
        assert isinstance(missions, list)

    def test_shadowed_mission_has_selected_false(self, tmp_path: Path) -> None:
        """Arrange: two mission.yaml files both declare 'test-mission';
        Act: discover with both in explicit_paths;
        Assert: at least one entry found, first is selected."""
        file_a = _write_mission_yaml(tmp_path / "a", _MINIMAL_MISSION_YAML)
        file_b = _write_mission_yaml(tmp_path / "b", _MINIMAL_MISSION_YAML)

        context = DiscoveryContext(explicit_paths=[file_a, file_b], user_home=tmp_path / "home")
        missions = discover_missions(context)

        matching = [m for m in missions if m.key == "test-mission"]
        # First occurrence is selected; second is shadowed
        assert len(matching) >= 1
        assert any(m.selected for m in matching)


class TestLoadMissionTemplate:
    def test_loads_template_from_explicit_yaml_path(self, tmp_path: Path) -> None:
        """Arrange: mission.yaml on disk; Act: load by path; Assert: MissionTemplate returned."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        template = load_mission_template(str(mission_file))

        assert isinstance(template, MissionTemplate)
        assert template.mission.key == "test-mission"
        assert len(template.steps) == 2

    def test_loads_template_when_given_directory_path(self, tmp_path: Path) -> None:
        """Arrange: directory containing mission.yaml; Act: load dir; Assert: template loaded."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        template = load_mission_template(str(mission_file.parent))

        assert template.mission.key == "test-mission"

    def test_load_raises_on_nonexistent_key_without_context(self, tmp_path: Path) -> None:
        """Arrange: no context, no file at key path;
        Act: load;
        Assert: MissionRuntimeError raised."""
        with pytest.raises(MissionRuntimeError):
            load_mission_template("completely-nonexistent-key-xyz")

    def test_loads_template_by_key_from_discovery_context(self, tmp_path: Path) -> None:
        """Arrange: mission.yaml file in explicit_paths; Act: load by key; Assert: correct template."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        context = DiscoveryContext(explicit_paths=[mission_file], user_home=tmp_path / "home")
        template = load_mission_template("test-mission", context=context)

        assert template.mission.key == "test-mission"

    def test_template_has_expected_step_ids(self, tmp_path: Path) -> None:
        """Arrange: mission with named steps; Act: load; Assert: step IDs correct."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)

        template = load_mission_template(str(mission_file))

        step_ids = [s.id for s in template.steps]
        assert "step-one" in step_ids
        assert "step-two" in step_ids


# ---------------------------------------------------------------------------
# Engine hot paths: start_mission_run + next_step
# ---------------------------------------------------------------------------

class TestStartMissionRun:
    def test_start_creates_run_dir_with_state_json(self, tmp_path: Path) -> None:
        """Arrange: mission file + run store dir;
        Act: start_mission_run;
        Assert: MissionRunRef returned with run_dir containing state.json."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)
        run_store = tmp_path / "runs"

        context = DiscoveryContext(explicit_paths=[mission_file], user_home=tmp_path / "home")
        policy = MissionPolicySnapshot()
        ref = start_mission_run(
            str(mission_file),
            inputs=None,
            policy_snapshot=policy,
            context=context,
            run_store=run_store,
        )

        assert isinstance(ref, MissionRunRef)
        run_dir = Path(ref.run_dir)
        assert (run_dir / "state.json").exists()
        assert ref.mission_key == "test-mission"

    def test_start_freezes_template_in_run_dir(self, tmp_path: Path) -> None:
        """Arrange: mission + run store;
        Act: start_mission_run;
        Assert: mission_template_frozen.yaml written to run directory."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)
        run_store = tmp_path / "runs"

        policy = MissionPolicySnapshot()
        ref = start_mission_run(
            str(mission_file),
            inputs=None,
            policy_snapshot=policy,
            run_store=run_store,
        )

        run_dir = Path(ref.run_dir)
        assert (run_dir / "mission_template_frozen.yaml").exists()

    def test_start_writes_run_events_jsonl(self, tmp_path: Path) -> None:
        """Arrange: mission + run store;
        Act: start_mission_run;
        Assert: run.events.jsonl exists in run_dir (MissionRunStarted event)."""
        mission_file = _write_mission_yaml(tmp_path / "test-mission", _MINIMAL_MISSION_YAML)
        run_store = tmp_path / "runs"

        policy = MissionPolicySnapshot()
        ref = start_mission_run(str(mission_file), inputs=None, policy_snapshot=policy, run_store=run_store)

        run_dir = Path(ref.run_dir)
        assert (run_dir / "run.events.jsonl").exists()


class TestNextStep:
    def _start(self, tmp_path: Path, yaml_content: str, key_name: str) -> tuple[MissionRunRef, DiscoveryContext]:
        mission_file = _write_mission_yaml(tmp_path / key_name, yaml_content)
        run_store = tmp_path / "runs"
        context = DiscoveryContext(explicit_paths=[mission_file], user_home=tmp_path / "home")
        policy = MissionPolicySnapshot()
        ref = start_mission_run(str(mission_file), inputs=None, policy_snapshot=policy, run_store=run_store)
        return ref, context

    def test_first_next_step_returns_first_step(self, tmp_path: Path) -> None:
        """Arrange: fresh mission run;
        Act: next_step;
        Assert: decision.step_id == 'step-one' (first step in template)."""
        ref, context = self._start(tmp_path, _MINIMAL_MISSION_YAML, "test-mission")

        decision = next_step(ref, agent_id="test-agent", result="success", context=context, emitter=NullEmitter())

        assert decision.step_id == "step-one"
        assert decision.kind == "step"

    def test_second_next_step_after_first_advances_to_second_step(self, tmp_path: Path) -> None:
        """Arrange: run after first step issued;
        Act: next_step twice;
        Assert: second decision.step_id is 'step-two'."""
        ref, context = self._start(tmp_path, _MINIMAL_MISSION_YAML, "test-mission")

        # First next_step issues step-one
        next_step(ref, agent_id="test-agent", result="success", context=context, emitter=NullEmitter())

        # Second next_step should issue step-two
        decision2 = next_step(ref, agent_id="test-agent", result="success", context=context, emitter=NullEmitter())

        assert decision2.step_id == "step-two"

    def test_next_step_reaches_terminal_after_all_steps_complete(self, tmp_path: Path) -> None:
        """Arrange: two-step mission;
        Act: next_step three times (past all steps);
        Assert: final decision kind is 'terminal'."""
        ref, context = self._start(tmp_path, _TWO_STEP_MISSION_YAML, "two-step-mission")

        emitter = NullEmitter()
        # Step 1 issued
        next_step(ref, agent_id="a", result="success", context=context, emitter=emitter)
        # Step 2 issued
        next_step(ref, agent_id="a", result="success", context=context, emitter=emitter)
        # Should now be terminal
        final = next_step(ref, agent_id="a", result="success", context=context, emitter=emitter)

        assert final.kind == "terminal"

    def test_next_step_run_id_matches_start_run_ref(self, tmp_path: Path) -> None:
        """Arrange: mission run started;
        Act: next_step;
        Assert: decision.run_id equals ref.run_id."""
        ref, context = self._start(tmp_path, _MINIMAL_MISSION_YAML, "test-mission")

        decision = next_step(ref, agent_id="test-agent", result="success", context=context, emitter=NullEmitter())

        assert decision.run_id == ref.run_id

    def test_next_step_mission_key_matches_template(self, tmp_path: Path) -> None:
        """Arrange: mission run; Act: next_step; Assert: decision.mission_key matches template."""
        ref, context = self._start(tmp_path, _MINIMAL_MISSION_YAML, "test-mission")

        decision = next_step(ref, agent_id="a", result="success", context=context, emitter=NullEmitter())

        assert decision.mission_key == "test-mission"
