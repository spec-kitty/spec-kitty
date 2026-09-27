"""Corrupt-meta.json degradation-path coverage for FR-007's fail-closed sites.

Each site here routes through ``load_meta_fail_closed`` and deliberately
DEGRADES a corrupt/malformed meta.json to a safe default (an empty phase
string, an orphan-state record, ``None``) rather than propagating the typed
``MissionMetaReadError`` -- these are "phase probe" style callers, not the
meta-trust authority itself (that authority's own contract is pinned in
``tests/specify_cli/core/test_load_meta_fail_closed_authority.py``). This
file exercises exactly that degradation branch at each site, closing gaps
left by the mission's per-subsystem test suites (WP07/WP08/WP09).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.constants import KITTY_SPECS_DIR

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CORRUPT_JSON = '{"mission_id": "01CORRUPT000000000000000",'


def _seed_corrupt_meta(mission_dir: Path) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(_CORRUPT_JSON, encoding="utf-8")


def test_lifecycle_phase_baseline_probe_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    from mission_runtime.lifecycle_phase import _read_baseline_merge_commit

    mission_dir = tmp_path / KITTY_SPECS_DIR / "corrupt-lifecycle-phase-mission"
    _seed_corrupt_meta(mission_dir)

    assert _read_baseline_merge_commit(mission_dir) == ""


def test_mission_status_read_meta_fails_closed_on_corrupt_meta(tmp_path: Path) -> None:
    """Unlike the phase-probe sites above, ``_read_meta`` IS the meta-trust
    authority (per its own docstring) -- it must raise, not degrade."""
    from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

    slug = "corrupt-aggregate-mission"
    mission_dir = tmp_path / KITTY_SPECS_DIR / slug
    _seed_corrupt_meta(mission_dir)

    with pytest.raises(MissionMetadataUnavailable):
        MissionStatus._read_meta(tmp_path, slug)


def test_mission_status_read_meta_race_window_none_raises_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TOCTOU race: meta.json exists() at the precondition check but
    ``load_meta_fail_closed`` legitimately returns ``None`` (deleted between
    the two reads) -- covers the race-window branch alongside the corrupt
    and missing-file cases above."""
    from specify_cli.status import aggregate as aggregate_module
    from specify_cli.status.aggregate import MissionMetadataUnavailable, MissionStatus

    slug = "race-window-aggregate-mission"
    mission_dir = tmp_path / KITTY_SPECS_DIR / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(aggregate_module, "load_meta_fail_closed", lambda _path: None)

    with pytest.raises(MissionMetadataUnavailable):
        MissionStatus._read_meta(tmp_path, slug)


def test_classify_mission_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    from specify_cli.status.identity_audit import classify_mission

    mission_dir = tmp_path / KITTY_SPECS_DIR / "corrupt-identity-audit-mission"
    _seed_corrupt_meta(mission_dir)

    state = classify_mission(mission_dir)

    assert state.path == mission_dir
    assert state.mission_id is None
    assert state.error is not None


def test_slug_resolver_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    from specify_cli.status.store import _SlugResolver

    specs_root = tmp_path / KITTY_SPECS_DIR
    feature_dir = specs_root / "corrupt-store-owner-mission"
    feature_dir.mkdir(parents=True)
    other_slug = "corrupt-store-target-mission"
    _seed_corrupt_meta(specs_root / other_slug)

    resolver = _SlugResolver(feature_dir)

    assert resolver.resolve(other_slug) is None
    # Cached: a second call must not re-read the corrupt file.
    assert resolver.resolve(other_slug) is None


def test_merge_baseline_recorded_working_meta_degrades_on_corrupt_meta(tmp_path: Path) -> None:
    from specify_cli.consolidation.baseline import _recorded_baseline_from_working_meta

    mission_dir = tmp_path / KITTY_SPECS_DIR / "corrupt-merge-baseline-mission"
    _seed_corrupt_meta(mission_dir)

    assert _recorded_baseline_from_working_meta(mission_dir) == ""
    assert _recorded_baseline_from_working_meta(None) == ""
