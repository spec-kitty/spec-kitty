"""Unit tests for the shared mission-selection seam (WP01, FR-006/FR-012).

These cover the three building blocks WP02-WP06 reuse:

* :func:`list_missions_for_selection` -- the legacy-tolerant population helper
  that counts any ``kitty-specs/`` directory bearing ``spec.md`` **or**
  ``meta.json`` (the same rule the agent-layer ``_list_feature_spec_candidates``
  uses), so ``next`` and plan/tasks never disagree on the count. It deliberately
  includes legacy missions whose ``meta.json`` lacks a ``mission_id`` -- exactly
  the missions ``FsMissionResolver.all_missions()`` silently drops.
* :func:`sole_mission_for_selection` -- the FR-004 sole-mission convention
  (the slug when exactly one mission exists, else ``None``).
* :data:`MISSION_NOT_FOUND_MESSAGE` / :func:`mission_not_found_message` -- the
  single canonical capital-M not-found template the fixed commands adopt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.context.mission_resolver import (
    MISSION_NOT_FOUND_MESSAGE,
    MissionListing,
    list_missions_for_selection,
    mission_not_found_message,
    sole_mission_for_selection,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# 26-char ULID-shaped identities ([0-9A-Z]); mid8 is the first 8 chars.
_MISSION_ID_ALPHA = "01J8ALPHA000000000000000AA"
_MISSION_ID_BETA = "01J8BETA000000000000000BBB"


def _write_meta(mission_dir: Path, meta: dict[str, object]) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _normal_meta(mission_slug: str, mission_id: str, friendly_name: str) -> dict[str, object]:
    return {
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": friendly_name,
        "mission_id": mission_id,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-09-18T00:00:00+00:00",
    }


def _stage_three_missions(root: Path) -> None:
    """Two normal missions (with ``mission_id``) + one legacy (spec.md only).

    Also seeds noise the population rule must ignore: a directory bearing
    neither ``spec.md`` nor ``meta.json``, and a stray top-level file.
    """
    specs = root / "kitty-specs"
    _write_meta(specs / "001-alpha", _normal_meta("001-alpha", _MISSION_ID_ALPHA, "Alpha Mission"))
    _write_meta(specs / "002-beta", _normal_meta("002-beta", _MISSION_ID_BETA, "Beta Mission"))

    # Legacy mission: only spec.md, no meta.json at all.
    legacy = specs / "003-legacy"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# Legacy mission\n", encoding="utf-8")

    # Noise that must NOT be counted.
    (specs / "not-a-mission").mkdir()
    (specs / "README.md").write_text("index\n", encoding="utf-8")


def test_ulid_fixtures_are_well_formed() -> None:
    """Guard the fixtures: mid8 assertions below depend on 26-char ULIDs."""
    assert len(_MISSION_ID_ALPHA) == 26
    assert len(_MISSION_ID_BETA) == 26


def test_lists_three_including_legacy_in_slug_order(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    listings = list_missions_for_selection(tmp_path)

    assert [entry.mission_slug for entry in listings] == ["001-alpha", "002-beta", "003-legacy"]
    assert all(isinstance(entry, MissionListing) for entry in listings)


def test_normal_missions_expose_mid8_and_friendly_name(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    by_slug = {entry.mission_slug: entry for entry in list_missions_for_selection(tmp_path)}

    assert by_slug["001-alpha"].mid8 == _MISSION_ID_ALPHA[:8]
    assert by_slug["001-alpha"].friendly_name == "Alpha Mission"
    assert by_slug["002-beta"].mid8 == _MISSION_ID_BETA[:8]
    assert by_slug["002-beta"].friendly_name == "Beta Mission"


def test_legacy_spec_only_mission_has_none_mid8_and_slug_fallback(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    legacy = next(e for e in list_missions_for_selection(tmp_path) if e.mission_slug == "003-legacy")

    assert legacy.mid8 is None
    # friendly_name falls back to the slug so listings never blank.
    assert legacy.friendly_name == "003-legacy"


def test_meta_without_mission_id_is_counted_with_none_mid8(tmp_path: Path) -> None:
    """A ``meta.json`` present but lacking ``mission_id`` still counts (legacy)."""
    specs = tmp_path / "kitty-specs"
    _write_meta(
        specs / "004-unbackfilled",
        {
            "slug": "004-unbackfilled",
            "mission_slug": "004-unbackfilled",
            "friendly_name": "Unbackfilled Mission",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-09-18T00:00:00+00:00",
        },
    )

    listings = list_missions_for_selection(tmp_path)

    assert len(listings) == 1
    assert listings[0].mission_slug == "004-unbackfilled"
    assert listings[0].mid8 is None
    # friendly_name still read from meta when present.
    assert listings[0].friendly_name == "Unbackfilled Mission"


def test_non_string_mission_id_does_not_crash_discovery(tmp_path: Path) -> None:
    """A valid meta.json whose ``mission_id`` is not a string must not crash
    discovery (guards ``resolve_mid8``'s ``len()`` against a JSON number so one
    odd file cannot break selection for the whole repo)."""
    specs = tmp_path / "kitty-specs"
    _write_meta(
        specs / "005-bad-id",
        {
            "slug": "005-bad-id",
            "mission_slug": "005-bad-id",
            "mission_id": 12345678,  # non-string (JSON number) — must be tolerated
            "friendly_name": "Bad Id Mission",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-09-18T00:00:00+00:00",
        },
    )

    listings = list_missions_for_selection(tmp_path)

    assert len(listings) == 1
    assert listings[0].mission_slug == "005-bad-id"
    # Non-string mission_id is dropped -> treated as legacy (no mid8).
    assert listings[0].mid8 is None
    assert listings[0].friendly_name == "Bad Id Mission"


def test_excludes_dirs_without_spec_or_meta_and_stray_files(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    slugs = {entry.mission_slug for entry in list_missions_for_selection(tmp_path)}

    assert "not-a-mission" not in slugs
    assert "README.md" not in slugs


def test_missing_kitty_specs_returns_empty(tmp_path: Path) -> None:
    assert list_missions_for_selection(tmp_path) == []


def test_count_agrees_with_len(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    listings = list_missions_for_selection(tmp_path)

    # The population count is exposed via the listing length (T003): no second
    # scan, no divergent counter.
    assert len(listings) == 3


def test_sole_mission_returns_slug_for_exactly_one(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "001-only", _normal_meta("001-only", _MISSION_ID_ALPHA, "Only Mission"))

    assert sole_mission_for_selection(tmp_path) == "001-only"


def test_sole_mission_returns_none_for_zero(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs").mkdir()

    assert sole_mission_for_selection(tmp_path) is None


def test_sole_mission_returns_none_for_multiple(tmp_path: Path) -> None:
    _stage_three_missions(tmp_path)

    assert sole_mission_for_selection(tmp_path) is None


def test_canonical_not_found_message_is_capital_m_form() -> None:
    assert MISSION_NOT_FOUND_MESSAGE == "Mission not found: {handle}"
    assert MISSION_NOT_FOUND_MESSAGE.format(handle="zznope") == "Mission not found: zznope"
    assert mission_not_found_message("zznope") == "Mission not found: zznope"
