"""The shared-package drift workflow's dependency-manifest paths are audit inputs (spec-kitty#6058, FR-009).

``check-spec-kitty-events-alignment.yml`` fires on the files that carry the reducer
(``spec-kitty-events``). Those same files change what ``doctor mission-state --audit`` reports, so the
router's ``mission_state`` group must match every one of them, or a reducer bump (commit 2e97550eb)
lands without the audit that its own drift check implies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.gate_selection import load_router, select_gates

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
ALIGNMENT = ROOT / ".github" / "workflows" / "check-spec-kitty-events-alignment.yml"
MANIFESTS = frozenset({"pyproject.toml", "uv.lock", ".kittify/release/shared-package-compatibility.json"})
GROUP = "mission_state"


def _trigger_paths(event: str) -> set[str]:
    workflow: dict[Any, Any] = yaml.safe_load(ALIGNMENT.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))  # YAML 1.1 parses the bare `on` key as boolean True
    return set(triggers[event]["paths"])


@pytest.mark.parametrize("event", ["pull_request", "push"])
def test_the_dependency_manifests_are_alignment_trigger_paths(event: str) -> None:
    assert _trigger_paths(event) >= MANIFESTS


@pytest.mark.parametrize("path", sorted(MANIFESTS))
def test_each_manifest_is_matched_by_the_mission_state_group(path: str) -> None:
    selection = select_gates([path], router=load_router())

    assert GROUP in selection.matched_groups
    assert "mission-state-audit" in selection.selected_jobs
