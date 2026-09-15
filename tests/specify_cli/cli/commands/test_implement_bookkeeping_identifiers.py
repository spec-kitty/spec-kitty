"""WP02 (#2649) — characterization + consumer-contract tests for
``_resolve_bookkeeping_transaction_identifiers`` BEFORE/THROUGH its S3776
degod extraction.

C-006 (load-bearing): ``tasks_move_task.py`` imports
``_resolve_bookkeeping_transaction_identifiers``, ``_feature_dir_file_paths``,
``_planning_artifact_source_dir`` from ``cli/commands/implement.py`` and calls
the first with only ``[0]`` (``coord_branch``) read at the cross-lane call
site, while the in-module caller unpacks the full 5-tuple
``(coord_branch, mission_id, mid8, effective_mission_id, effective_mid8)``.
These tests pin that positional 5-tuple contract PLUS the value-level
cascade/fallback/precedence invariants that T008's extraction must preserve
byte-for-byte (DM-D brownfield / characterization-first discipline).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.implement import (
    _resolve_bookkeeping_transaction_identifiers,
)
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

pytestmark = pytest.mark.fast


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _seed_primary_mission(
    tmp_path: Path, *, slug: str, mission_id: str | None = None
) -> Path:
    """Seed a canonical ``kitty-specs/<slug>/meta.json`` (matches the pattern
    ``tests/specify_cli/missions/test_read_path_handle_resolution.py::_seed_mission``
    uses for identity-form ambiguity fixtures)."""
    mission_dir = tmp_path / "kitty-specs" / slug
    meta: dict[str, object] = {"mission_slug": slug}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    _write_meta(mission_dir, meta)
    return mission_dir


# ---------------------------------------------------------------------------
# T006.1 — cascade order: the PRIMARY-checkout dir's meta.json wins
# ---------------------------------------------------------------------------


def test_cascade_prefers_primary_dir_meta_over_passed_feature_dir(tmp_path: Path) -> None:
    """FR-003 cascade layer 1: the canonical primary-checkout meta.json is read
    FIRST, ahead of whatever ``feature_dir`` the caller passed in (e.g. an
    already-materialized coord worktree carrying a stale/different meta)."""
    slug = "cascade-mission"
    primary_dir = tmp_path / "kitty-specs" / slug
    _write_meta(
        primary_dir,
        {
            "mission_slug": slug,
            "coordination_branch": "kitty/mission-cascade-primary",
            "mission_id": "01KPRIMARYAAAAAAAAAAAAAAA",
            "mid8": "01KPRIMA",
        },
    )

    # A distinct dir (simulating a coord worktree's mission dir) carrying
    # DIFFERENT identifiers — must be ignored while the primary dir resolves.
    coord_feature_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        coord_feature_dir,
        {
            "mission_slug": slug,
            "coordination_branch": "kitty/mission-cascade-WRONG",
            "mission_id": "01KWRONGBBBBBBBBBBBBBBBBBB",
            "mid8": "01KWRONGB",
        },
    )

    result = _resolve_bookkeeping_transaction_identifiers(coord_feature_dir, slug, tmp_path)

    assert result[0] == "kitty/mission-cascade-primary"
    assert result[1] == "01KPRIMARYAAAAAAAAAAAAAAA"
    assert result[2] == "01KPRIMA"


def test_cascade_falls_back_to_feature_dir_when_no_primary_meta(tmp_path: Path) -> None:
    """When the primary-checkout dir has no ``meta.json`` at all, the cascade
    falls back to reading ``feature_dir`` directly (layer 2)."""
    slug = "fallback-mission"
    feature_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _write_meta(
        feature_dir,
        {
            "mission_slug": slug,
            "coordination_branch": "kitty/mission-fallback-only",
            "mission_id": "01KFALLBACKAAAAAAAAAAAAAA",
            "mid8": "01KFALLB",
        },
    )
    # No kitty-specs/<slug>/meta.json exists at tmp_path -- primary read misses.

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[0] == "kitty/mission-fallback-only"
    assert result[1] == "01KFALLBACKAAAAAAAAAAAAAA"


# ---------------------------------------------------------------------------
# T006.2 — ambiguous handle RAISEs (no silent pick)
# ---------------------------------------------------------------------------


def test_ambiguous_primary_handle_raises(tmp_path: Path) -> None:
    """C-CTX-4 / C-009: a handle matching >1 mission by numeric prefix raises
    :class:`MissionSelectorAmbiguous` rather than silently picking one.

    Mirrors ``test_read_path_handle_resolution.py::test_ambiguous_handle_raises_structured_error``.
    """
    _seed_primary_mission(
        tmp_path, slug="083-alpha", mission_id="01AAAAAAAAAAAAAAAAAAAAAAAA"
    )
    _seed_primary_mission(
        tmp_path, slug="083-beta", mission_id="01BBBBBBBBBBBBBBBBBBBBBBBB"
    )

    feature_dir = tmp_path / "kitty-specs" / "083-alpha"  # irrelevant: raise precedes fallback

    with pytest.raises(MissionSelectorAmbiguous):
        _resolve_bookkeeping_transaction_identifiers(feature_dir, "083", tmp_path)


# ---------------------------------------------------------------------------
# T006.3 — ``legacy-<slug>`` mission-id fallback (implement.py:411)
# ---------------------------------------------------------------------------


def test_legacy_slug_fallback_when_mission_id_absent(tmp_path: Path) -> None:
    slug = "legacy-fallback-mission"
    feature_dir = _seed_primary_mission(tmp_path, slug=slug)  # no mission_id

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[1] is None  # mission_id
    assert result[3] == f"legacy-{slug}"  # effective_mission_id


def test_legacy_slug_fallback_when_no_meta_at_all(tmp_path: Path) -> None:
    slug = "no-meta-mission"
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)  # no meta.json written

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[0] is None
    assert result[1] is None
    assert result[3] == f"legacy-{slug}"


# ---------------------------------------------------------------------------
# T006.4 — mid8 precedence: meta["mid8"] > resolve_mid8(...) > None
# ---------------------------------------------------------------------------


def test_mid8_meta_value_wins_over_derivation(tmp_path: Path) -> None:
    slug = "mid8-precedence-mission"
    mission_id = "01KDERIVEDXXXXXXXXXXXXXXXX"
    explicit_mid8 = "CUSTOM99"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(
        feature_dir,
        {"mission_slug": slug, "mission_id": mission_id, "mid8": explicit_mid8},
    )

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[2] == explicit_mid8
    assert result[2] != mission_id[:8]


def test_mid8_falls_back_to_resolve_mid8_when_meta_mid8_absent(tmp_path: Path) -> None:
    slug = "mid8-fallback-mission"
    mission_id = "01KDERIVEDYYYYYYYYYYYYYYYY"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(feature_dir, {"mission_slug": slug, "mission_id": mission_id})

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[2] == mission_id[:8]


def test_mid8_is_none_when_no_meta_mid8_and_no_mission_id(tmp_path: Path) -> None:
    slug = "mid8-none-mission"
    feature_dir = _seed_primary_mission(tmp_path, slug=slug)

    result = _resolve_bookkeeping_transaction_identifiers(feature_dir, slug, tmp_path)

    assert result[2] is None


# ---------------------------------------------------------------------------
# T007 — consumer-side import contract (freeze C-006)
# ---------------------------------------------------------------------------


def test_consumer_contract_five_tuple_positions_match_fixture(tmp_path: Path) -> None:
    """Import the three symbols the way ``tasks_move_task.py`` does and assert
    each POSITIONAL value of the 5-tuple against a known fixture -- a bare
    tuple has no field names, so positions (not ``inspect.signature``) are the
    contract WP07 (Lane B) depends on."""
    from specify_cli.cli.commands.implement import (
        _feature_dir_file_paths as consumer_feature_dir_file_paths,
        _planning_artifact_source_dir as consumer_planning_artifact_source_dir,
        _resolve_bookkeeping_transaction_identifiers as consumer_resolve_ids,
    )

    slug = "contract-mission"
    coord_branch = "kitty/mission-contract-mission"
    mission_id = "01KCONTRACTAAAAAAAAAAAAAAA"
    mid8 = "01KCONTR"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_meta(
        feature_dir,
        {
            "mission_slug": slug,
            "coordination_branch": coord_branch,
            "mission_id": mission_id,
            "mid8": mid8,
        },
    )

    result = consumer_resolve_ids(feature_dir, slug, tmp_path)

    assert isinstance(result, tuple)
    assert len(result) == 5  # (C-006 5-tuple arity)
    # tasks_move_task.py:1392 reads ONLY element [0] cross-lane.
    assert result[0] == coord_branch
    assert result[1] == mission_id
    assert result[2] == mid8
    assert result[3] == mission_id  # effective_mission_id
    assert result[4] == mid8  # effective_mid8

    # The two sibling C-006 symbols keep their current signatures.
    assert list(inspect.signature(consumer_feature_dir_file_paths).parameters) == [
        "repo_root",
        "feature_dir",
    ]
    assert list(
        inspect.signature(consumer_planning_artifact_source_dir).parameters
    ) == ["repo_root", "feature_dir", "mission_slug"]


def test_sibling_symbols_importable_and_callable_alongside_resolver(tmp_path: Path) -> None:
    """Smoke-check the exact import block ``tasks_move_task.py:1381-1385`` uses
    still resolves all three names from the same module."""
    from specify_cli.cli.commands.implement import (
        _feature_dir_file_paths,
        _planning_artifact_source_dir,
        _resolve_bookkeeping_transaction_identifiers,
    )

    assert callable(_feature_dir_file_paths)
    assert callable(_planning_artifact_source_dir)
    assert callable(_resolve_bookkeeping_transaction_identifiers)
