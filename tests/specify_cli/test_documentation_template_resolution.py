"""Regression tests for documentation mission-runtime.yaml resolution.

D1 of plan.md commits to coexistence of mission.yaml + mission-runtime.yaml.
The loader must resolve mission-runtime.yaml ahead of the legacy mission.yaml
for any documentation mission_type.
"""

from __future__ import annotations

from pathlib import Path

from runtime.next.runtime_bridge_io import _resolve_runtime_template_in_root


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_documentation_runtime_sidecar_wins_over_legacy_mission_yaml() -> None:
    """The package-level loader resolves mission-runtime.yaml for mission_type='documentation'."""
    package_root = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "missions"
    resolved = _resolve_runtime_template_in_root(package_root, "documentation")
    assert resolved is not None, "loader returned None for mission_type='documentation'"
    assert resolved.name == "mission-runtime.yaml", (
        f"expected mission-runtime.yaml; got {resolved.name}. "
        "If this fails, _resolve_runtime_template_in_root is no longer "
        "preferring the runtime sidecar over the legacy mission.yaml."
    )


def test_documentation_runtime_template_declares_correct_mission_key() -> None:
    """The runtime sidecar's mission.key must be 'documentation' for loader gate."""
    from runtime.next._internal_runtime.schema import load_mission_template_file

    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "specify_cli"
        / "missions"
        / "documentation"
        / "mission-runtime.yaml"
    )
    template = load_mission_template_file(path)
    assert template.mission.key == "documentation"
    assert len(template.steps) == 7  # 6 composed + accept
    step_ids = [step.id for step in template.steps]
    assert step_ids == ["discover", "audit", "design", "generate", "validate", "publish", "accept"]
