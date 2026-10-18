"""NFR-004 golden snapshot: the default in-force governance sets.

The golden (``fixtures/default_in_force_snapshot.json``) freezes what a bare
project (no activation keys, no org packs, no synthesized artifacts) delivers
per built-in software-dev action at depths 1 and 2, plus the project-level
governance resolution. Later work in the charter-governance-resolution Mission
must not change it. Regenerate only deliberately: ``UPDATE_SNAPSHOT=1``.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from charter.activation.action_governance_bundle import _load_action_governance_bundle
from charter.activation.pack_context import PackContext
from charter.activation.resolver import resolve_project_governance

pytestmark = [pytest.mark.unit]

_GOLDEN = Path(__file__).parent / "fixtures" / "default_in_force_snapshot.json"
_STEPS_DIR = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"
_ACTIONS = sorted(p.name for p in _STEPS_DIR.iterdir() if p.is_dir())
_DEPTHS = (1, 2)
_REQUIRED_NON_EMPTY = ("specify", "plan", "implement", "review")
_SLOTS = ("directive_ids", "tactic_ids", "styleguide_ids")


@pytest.fixture(scope="module")
def bare_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bare-project")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".kittify").mkdir()
    return root


def _delivered(root: Path, action: str, depth: int) -> dict[str, list[str]]:
    bundle = _load_action_governance_bundle(
        repo_root=root,
        action=action,
        effective_depth=depth,
        pack_context=PackContext.from_config(root),
        mission_type="software-dev",
    )
    return {slot.removesuffix("_ids"): sorted(getattr(bundle, slot)) for slot in _SLOTS}


def _snapshot(root: Path) -> dict[str, Any]:
    bundles = {action: {str(depth): _delivered(root, action, depth) for depth in _DEPTHS} for action in _ACTIONS}
    governance = json.loads(json.dumps(asdict(resolve_project_governance(root)), sort_keys=True, default=sorted))
    return {"bundles": bundles, "governance": governance}


def _dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def test_default_in_force_matches_golden(bare_project: Path) -> None:
    actual = _snapshot(bare_project)
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        _GOLDEN.write_text(_dump(actual), encoding="utf-8")
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert actual == golden


@pytest.mark.parametrize("action", _REQUIRED_NON_EMPTY)
def test_golden_is_non_vacuous(action: str) -> None:
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    for depth in _DEPTHS:
        assert golden["bundles"][action][str(depth)]["directive"], f"{action}@{depth} delivers no directives"


def test_actions_cover_every_step_directory() -> None:
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert _ACTIONS
    assert sorted(golden["bundles"]) == _ACTIONS
