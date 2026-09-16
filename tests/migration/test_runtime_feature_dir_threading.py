"""#3866 — ``_runtime_feature_dir`` reuses the threaded OwnedMission value object.

The per-phase ``resolve_owned_mission`` re-derivation (ownership claim +
mission resolve + git branch probes) is gone: the caller-validated value
object is the authority, anchored by the exact-directory guard that still
refuses a foreign anchor.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mission_runtime import ActionContextError

from specify_cli.core.owned_mission import OwnedMission
from specify_cli.migration.backfill_runtime_state import _runtime_feature_dir

pytestmark = [pytest.mark.unit]


def _owned(tmp_path: Path) -> OwnedMission:
    return OwnedMission(
        primary=(tmp_path / "primary").resolve(),
        root=(tmp_path / "checkout").resolve(),
        directory=(tmp_path / "primary" / "kitty-specs" / "owned-mission").resolve(),
        slug="owned-mission",
        target="main",
    )


def test_threaded_owned_mission_is_not_rederived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _must_not_run(*_a: object, **_k: object) -> OwnedMission:
        raise AssertionError("threaded owned value object must not be re-derived per phase")

    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)
    owned = _owned(tmp_path)
    assert _runtime_feature_dir(owned.directory, owned) == owned.directory


def test_foreign_anchor_is_refused(tmp_path: Path) -> None:
    owned = _owned(tmp_path)
    foreign = tmp_path / "elsewhere"
    with pytest.raises(ActionContextError) as refused:
        _runtime_feature_dir(foreign, owned)
    assert refused.value.code == "OWNED_MISSION_PATH_REFUSED"
