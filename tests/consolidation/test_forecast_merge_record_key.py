"""The ``--dry-run`` forecast reads the merge record under the executor's key (#7692 re-review LOW-3).

The executor keys the record by ``meta.json`` identity (``preflight_retarget.merge_record_key``). A legacy
``lanes.json`` without ``mission_id`` made the forecast's mission-branch check and its recorded
``--dependency-ref`` read key on the slug and miss the record.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.consolidation import forecast
from specify_cli.consolidation.state import ConsolidationState, save_state

pytestmark = pytest.mark.fast

_MISSION_ID = "01M7M5JA00000000000000000L"
_SLUG = "m"


def _legacy_manifest() -> Any:
    return SimpleNamespace(mission_id=None, mission_slug=_SLUG, mission_branch="kitty/mission-m", target_branch="main", lanes=[])


def _record(repo: Path) -> None:
    meta = repo / "kitty-specs" / _SLUG / "meta.json"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "target_branch": "main"}), encoding="utf-8")
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_SLUG, target_branch="main", wp_order=["WP01"])
    state.dependency_refs = ["dep"]
    state.dependency_ref_pins = {"dep": "a" * 40}
    save_state(state, repo)


def test_the_recorded_dependency_refs_are_read_under_the_meta_identity(tmp_path: Path) -> None:
    _record(tmp_path)
    refs, pins = forecast._declared_with_recorded(tmp_path, _SLUG, (), json_output=True)
    assert refs == ("dep",)
    assert pins == {"dep": "a" * 40}


def test_the_mission_branch_check_reads_the_record_under_the_meta_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(tmp_path)
    seen: list[object] = []

    def _required(_repo: Path, _manifest: object, state: object) -> bool:
        seen.append(state)
        return False

    monkeypatch.setattr(forecast, "mission_branch_check_required", _required)
    forecast._refuse_missing_mission_branch_in_forecast(tmp_path, _SLUG, _legacy_manifest(), json_output=True)
    assert len(seen) == 1 and isinstance(seen[0], ConsolidationState) and seen[0].mission_id == _MISSION_ID
