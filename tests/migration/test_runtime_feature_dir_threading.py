"""#3866 — ``_runtime_feature_dir`` reuses the threaded OwnedCheckout value object.

The per-phase ``resolve_owned_mission`` re-derivation (ownership claim +
mission resolve + git branch probes) is gone: the caller-validated value
object is the authority, anchored by the exact-directory guard that still
refuses a foreign anchor.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mission_runtime import ActionContextError, OwnedCheckout

from tests._owned_fixtures import mint_test_fact
from specify_cli.migration.backfill_runtime_state import _runtime_feature_dir

pytestmark = [pytest.mark.unit]


def _owned(tmp_path: Path) -> OwnedCheckout:
    # ``directory`` must live under ``root``/kitty-specs/<slug>
    # (OwnedCheckout.__post_init__ invariant), so it moves to the checkout
    # root here rather than the (distinct) repository root.
    return mint_test_fact(
        repository_root=(tmp_path / "primary").resolve(),
        owned_root=(tmp_path / "checkout").resolve(),
        mission_dir=(tmp_path / "checkout" / "kitty-specs" / "owned-mission").resolve(),
        mission_slug="owned-mission",
        write_branch="main",
    )


def test_threaded_owned_mission_is_not_rederived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _must_not_run(*_a: object, **_k: object) -> OwnedCheckout:
        raise AssertionError("threaded owned value object must not be re-derived per phase")

    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)
    owned = _owned(tmp_path)
    assert _runtime_feature_dir(owned.mission_dir, owned) == owned.mission_dir


def test_foreign_anchor_is_refused(tmp_path: Path) -> None:
    owned = _owned(tmp_path)
    foreign = tmp_path / "elsewhere"
    with pytest.raises(ActionContextError) as refused:
        _runtime_feature_dir(foreign, owned)
    assert refused.value.code == "OWNED_MISSION_PATH_REFUSED"
