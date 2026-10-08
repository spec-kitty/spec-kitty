"""Pack runtime templates are what ``next`` runs (WP06, FR-017/FR-018/FR-023, NFR-006, SC-009).

``plan_for`` resolves the runtime template of each built-in mission type
through the production resolver and reduces it to the step sequence plus the
dispatch route of every step. ``tests/runtime/fixtures/runtime_template_baseline.json``
was recorded with this helper BEFORE the ``src`` copies were deleted, with the
user-global tier holding a copy of the pack (what ``ensure_runtime`` installs).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

BASELINE = Path(__file__).parent / "fixtures" / "runtime_template_baseline.json"
BUILTIN_TYPES = ("software-dev", "documentation", "research", "plan")
#: WP07 adds this software-dev step; it is the only allowed difference.
EXEMPT_STEPS = {"software-dev": {"analyze"}}


def _pack_missions_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions"


def plan_for(mission_type: str, home: Path, repo_root: Path) -> dict[str, Any]:
    """Resolve ``mission_type`` the way ``next`` does and reduce it to its plan."""
    from runtime.next import runtime_bridge_composition as composition
    from runtime.next import runtime_bridge_io as io_seam
    from runtime.next._internal_runtime.schema import load_mission_template_file

    global_missions = home / ".kittify" / "missions"
    if not global_missions.exists():
        shutil.copytree(_pack_missions_root(), global_missions)
    from unittest.mock import patch

    with patch("pathlib.Path.home", return_value=home):
        key = io_seam._runtime_template_key(mission_type, repo_root)
    template = load_mission_template_file(Path(key))
    steps = []
    for step in template.steps:
        profile = (step.agent_profile or "").strip()
        contract = (step.contract_ref or "").strip()
        charter_route = composition._should_dispatch_via_composition(mission_type, step.id, repo_root=repo_root)
        steps.append(
            {
                "id": step.id,
                "depends_on": list(step.depends_on or []),
                "agent_profile": profile or None,
                "contract_ref": contract or None,
                "route": "composition" if (charter_route or profile or contract) else "legacy",
            }
        )
    return {"steps": steps}



def _baseline() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return loaded


def _without_exempt(mission_type: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exempt = EXEMPT_STEPS.get(mission_type, set())
    return [dict(s, depends_on=[d for d in s["depends_on"] if d not in exempt]) for s in steps if s["id"] not in exempt]


@pytest.mark.parametrize("mission_type", BUILTIN_TYPES)
def test_resolved_plan_equals_baseline(mission_type: str, tmp_path: Path) -> None:
    """NFR-006/SC-009: the resolver plans today's step sequence and routes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    got = plan_for(mission_type, tmp_path / "home", repo)["steps"]
    want = _baseline()[mission_type]["steps"]
    assert _without_exempt(mission_type, got) == _without_exempt(mission_type, want)


@pytest.mark.parametrize("mission_type", BUILTIN_TYPES)
def test_pack_template_alone_equals_baseline(mission_type: str, tmp_path: Path) -> None:
    """The pack copy itself loads and plans what the CLI ran (FR-023, B2)."""
    from runtime.next import runtime_bridge_composition as composition
    from runtime.next._internal_runtime.schema import load_mission_template_file

    template = load_mission_template_file(_pack_missions_root() / mission_type / "mission-runtime.yaml")
    steps = []
    for step in template.steps:
        profile = (step.agent_profile or "").strip()
        contract = (step.contract_ref or "").strip()
        charter_route = composition._should_dispatch_via_composition(mission_type, step.id, repo_root=tmp_path)
        steps.append(
            {
                "id": step.id,
                "depends_on": list(step.depends_on or []),
                "agent_profile": profile or None,
                "contract_ref": contract or None,
                "route": "composition" if (charter_route or profile or contract) else "legacy",
            }
        )
    assert _without_exempt(mission_type, steps) == _without_exempt(mission_type, _baseline()[mission_type]["steps"])


#: B2: documentation and research resolve from the user-global copy of the pack,
#: so a byte change here would be re-copied there and trip the drift check of
#: in-flight runs. Digests taken at base 25f7f1b7f.
_UNCHANGED_PACK_DIGESTS = {
    "documentation": "sha256:c2f493e51d87feb0137ab6759239d73dbc9751441935c51e973bfade9e081835",
    "research": "sha256:841dddaed39f932e6be202b653da722a3272633f710a1ef3b9566d57b864f6dd",
}


@pytest.mark.parametrize("mission_type", sorted(_UNCHANGED_PACK_DIGESTS))
def test_documentation_and_research_pack_bytes_unchanged(mission_type: str) -> None:
    from charter.hasher import hash_content

    text = (_pack_missions_root() / mission_type / "mission-runtime.yaml").read_text(encoding="utf-8")
    assert hash_content(text) == _UNCHANGED_PACK_DIGESTS[mission_type]


def _start_two_step_run(tmp_path: Path) -> tuple[Any, Path]:
    """A real run whose recorded template path is a file the test can delete."""
    import yaml

    from runtime.next._internal_runtime import DiscoveryContext, MissionPolicySnapshot, NullEmitter, start_mission_run

    raw = {
        "mission": {"key": "frozen-order", "name": "Frozen order", "version": "1.0.0"},
        "steps": [
            {"id": "one", "title": "One", "description": "first", "prompt": "Do one."},
            {"id": "two", "title": "Two", "description": "second", "prompt": "Do two.", "depends_on": ["one"]},
        ],
    }
    template_dir = tmp_path / "gone" / "frozen-order"
    template_dir.mkdir(parents=True)
    yaml_path = template_dir / "mission.yaml"
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )
    return run_ref, yaml_path


def test_query_mode_reads_frozen_template_when_recorded_path_is_gone(tmp_path: Path) -> None:
    """B1/FR-017: a deleted recorded template path must not break a bare ``next``."""
    from runtime.next import runtime_bridge_query as query

    run_ref, recorded = _start_two_step_run(tmp_path)
    recorded.unlink()
    assert not recorded.exists()

    _ref, _store, snapshot, decision = query._query_read_runtime_plan(run_ref, "m", "frozen-order", tmp_path)

    assert snapshot.template_path == str(recorded)
    assert decision.step_id == "one"


def test_in_flight_run_keeps_frozen_order_when_recorded_path_is_gone(tmp_path: Path) -> None:
    """FR-017: the planner skips the drift check for a vanished live path and plans from the frozen copy."""
    from runtime.next._internal_runtime import NullEmitter, next_step

    run_ref, recorded = _start_two_step_run(tmp_path)
    first = next_step(run_ref, agent_id="a", result="success", emitter=NullEmitter())
    recorded.unlink()
    second = next_step(run_ref, agent_id="a", result="success", emitter=NullEmitter())
    assert (first.step_id, second.step_id) == ("one", "two")


if __name__ == "__main__":  # pragma: no cover - fixture recorder
    import sys
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        repo = tmp_path / "repo"
        repo.mkdir()
        recorded = {t: plan_for(t, tmp_path / "home", repo) for t in BUILTIN_TYPES}
    Path(sys.argv[1]).write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
