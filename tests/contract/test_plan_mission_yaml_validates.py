"""Contract test: shipped mission runtime YAML files validate against the
runtime schema (FR-021, WP04/T024).

Loads each shipped mission's ``mission-runtime.yaml`` (or ``mission.yaml``
fallback) and asserts ``MissionTemplate`` model validation succeeds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next._internal_runtime.schema import (
    MissionRuntimeError,
    load_mission_template_file,
)

pytestmark = pytest.mark.fast


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MISSIONS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions"


# Missions whose `mission-runtime.yaml` MUST validate against the runtime
# schema. The plan mission is the regression target for FR-021. Other
# shipped missions are included as defense-in-depth so that a future schema
# change cannot silently break them.
_SHIPPED_RUNTIME_MISSIONS = ("plan", "software-dev")


@pytest.mark.parametrize("mission_key", _SHIPPED_RUNTIME_MISSIONS)
def test_shipped_mission_runtime_yaml_validates(mission_key: str) -> None:
    runtime_path = _MISSIONS_ROOT / mission_key / "mission-runtime.yaml"
    assert runtime_path.exists(), (
        f"Expected shipped runtime YAML at {runtime_path}"
    )

    template = load_mission_template_file(runtime_path)
    assert template.mission.key, "mission.key must be populated"
    assert template.mission.name, "mission.name must be populated"
    assert template.mission.version, "mission.version must be populated"
    assert template.steps, "mission must declare at least one step"


def test_plan_mission_runtime_steps_match_documented_workflow() -> None:
    """The plan mission's runtime YAML keeps its 4-step linear workflow."""
    runtime_path = _MISSIONS_ROOT / "plan" / "mission-runtime.yaml"
    template = load_mission_template_file(runtime_path)

    step_ids = [step.id for step in template.steps]
    assert step_ids == ["specify", "research", "plan", "review"], (
        f"Plan mission must keep the 4-step linear workflow; got {step_ids}"
    )


def test_software_dev_mission_runtime_yaml_validates() -> None:
    """Regression: software-dev mission YAML continues to validate."""
    runtime_path = _MISSIONS_ROOT / "software-dev" / "mission-runtime.yaml"
    template = load_mission_template_file(runtime_path)
    assert template.mission.key == "software-dev"
    assert len(template.steps) > 0


def test_invalid_runtime_yaml_raises_structured_error(tmp_path: Path) -> None:
    """Sanity: a malformed YAML triggers MissionRuntimeError, not a bare crash."""
    bad = tmp_path / "mission-runtime.yaml"
    bad.write_text(
        "mission:\n"
        "  key: bad\n"
        "  name: Bad\n"
        "  version: '1'\n"
        "# missing top-level steps\n",
        encoding="utf-8",
    )
    with pytest.raises(MissionRuntimeError):
        load_mission_template_file(bad)
