"""Unit tests for backfill_topology: the pure reader + backfill persist helpers.

Covers:
- WP09 read_topology PURE reader (#1814 read-only contract).
- T012 backfill persist path (backfill_mission_topology): present no-write,
  absent-field absorption (derive-and-persist, never None), idempotent second run,
  flattened-flag preservation (C-006), dry-run, corrupt-meta error arm, per-mission
  scoping, and the full 4-cell coord × lanes classification.

The compute-once-then-persist ``ensure_topology`` shim was removed in WP05 (FR-003,
zero production callers); its edge-cases — present-field no-write, absent-field
absorption to a concrete topology (never None), idempotent re-run, and existing
``flattened`` provenance-flag preservation — are preserved here re-pointed onto
:func:`read_topology` (the pure read seam) and :func:`backfill_mission_topology`
(the persist seam), per ``delete-the-assertion-not-the-test``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.migration.backfill_topology import (
    backfill_mission_topology,
    backfill_topology_repo,
    read_topology,
    stored_topology,
    topology_from_meta,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta_path


def _write_lanes(feature_dir: Path) -> None:
    """Write a minimal, parseable lanes.json so read_lanes_json returns a manifest."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "mission_slug": feature_dir.name,
        "mission_branch": f"kitty/mission-{feature_dir.name}",
        "target_branch": "feat/x",
        "lanes": [{"lane_id": "lane-a", "wp_ids": ["WP00"]}],
        "computed_at": "2026-06-22T00:00:00+00:00",
        "computed_from": "tasks.md",
    }
    (feature_dir / "lanes.json").write_text(json.dumps(manifest), encoding="utf-8")


def _bytes(path: Path) -> bytes:
    """Return raw file bytes — used to prove a call wrote nothing (no-write law)."""
    return path.read_bytes()


# ---------------------------------------------------------------------------
# WP09 — read_topology PURE reader (#1814 read-only contract)
# ---------------------------------------------------------------------------


def test_read_topology_present_field_no_write(tmp_path: Path) -> None:
    """A valid stored topology is returned with NO write (byte-identical file)."""
    feature_dir = tmp_path / "mission-present"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x", "topology": "coord"})
    before = _bytes(meta_path)

    result = read_topology(feature_dir)

    assert result is MissionTopology.COORD
    assert _bytes(meta_path) == before, "present field must not trigger a write"


def test_read_topology_unbackfilled_derives_WITHOUT_persisting(tmp_path: Path) -> None:
    """#1814: an un-backfilled mission is derived ONCE and NOT written back.

    The defining read-only contract of the pure reader: ``read_topology`` returns
    the derived shape for a mission whose ``meta.json`` carries no ``topology``
    key, but leaves the file BYTE-IDENTICAL — unlike ``ensure_topology``, which
    persists. A SEAM READ path wired to this reader therefore never mutates the
    tree (the finalize ``--validate-only`` / accept-readiness regression close).
    """
    feature_dir = tmp_path / "mission-unbackfilled"
    meta_path = _write_meta(feature_dir, {"coordination_branch": None})  # NO topology key
    before = _bytes(meta_path)

    result = read_topology(feature_dir)

    # #5100 FR-013 / #2602: the RUNTIME reader never derives ``single_branch``
    # for an unstamped mission -- only an explicitly stored value is honoured.
    assert result is MissionTopology.LANES
    assert _bytes(meta_path) == before, (
        "read_topology MUST NOT persist a derived topology (the #1814 read-only contract); only ensure_topology / backfill may write."
    )
    # And it really is absent — no incidental back-fill key sneaked in.
    assert "topology" not in json.loads(meta_path.read_text(encoding="utf-8"))


def test_read_topology_coord_branch_derives_coord_without_write(tmp_path: Path) -> None:
    """An un-backfilled coord mission derives COORD purely (no write)."""
    feature_dir = tmp_path / "mission-coord-legacy"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x-coord"})
    before = _bytes(meta_path)

    assert read_topology(feature_dir) is MissionTopology.COORD
    assert _bytes(meta_path) == before


def test_read_topology_missing_meta_raises(tmp_path: Path) -> None:
    """A missing ``meta.json`` raises FileNotFoundError (the bootstrap signal)."""
    with pytest.raises(FileNotFoundError):
        read_topology(tmp_path / "no-such-mission")


def test_read_topology_non_object_meta_raises(tmp_path: Path) -> None:
    """A non-object ``meta.json`` raises MissionMetaReadError (fail-closed, FR-007)."""
    feature_dir = tmp_path / "mission-bad"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("[]", encoding="utf-8")
    with pytest.raises(MissionMetaReadError):
        read_topology(feature_dir)


# ---------------------------------------------------------------------------
# WP05 — retargeted ensure_topology edge-cases (FR-003 shim removal).
# The removed compute-once-then-persist shim's contract is preserved here,
# re-pointed onto read_topology (present-field no-write) and
# backfill_mission_topology (absent-field absorption / idempotence /
# flattened-flag preservation), per delete-the-assertion-not-the-test.
# ---------------------------------------------------------------------------


def test_present_field_returns_stored_value_no_write_single_branch(tmp_path: Path) -> None:
    """Present-field edge: a stored ``single_branch`` is returned with NO write.

    Re-pointed from the removed ``ensure_topology`` present-no-write assertion onto
    the pure reader: a valid stored topology is returned byte-identically, never
    re-derived from the (disagreeing) coordination_branch signal.
    """
    feature_dir = tmp_path / "mission-present"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x", "topology": "single_branch"})
    before = _bytes(meta_path)

    result = read_topology(feature_dir)

    assert result is MissionTopology.SINGLE_BRANCH
    assert _bytes(meta_path) == before, "present field must not trigger a write"


def test_absent_field_absorbed_to_concrete_topology_never_none(tmp_path: Path) -> None:
    """Absent-field absorption (T013 DoD-b): no ``topology`` key → concrete topology.

    The core edge the removed ``ensure_topology`` guarded: a ``meta.json`` carrying
    no ``topology`` key must absorb into a CONCRETE derived :class:`MissionTopology`
    (here COORD from a coordination_branch), **never** ``None``, and persist with the
    default ``flattened: false`` provenance flag.
    """
    feature_dir = tmp_path / "mission-absent"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x"})
    assert "topology" not in json.loads(meta_path.read_text(encoding="utf-8"))

    result = backfill_mission_topology(feature_dir)

    # Absorbed to a concrete topology, never None.
    assert result.topology is not None, "absent topology must absorb to a concrete value"
    assert result.topology == "coord"
    assert result.action == "wrote"
    persisted = json.loads(meta_path.read_text(encoding="utf-8"))
    assert persisted["topology"] == "coord"
    assert persisted["flattened"] is False
    # And the pure reader agrees with the persisted concrete value.
    assert read_topology(feature_dir) is MissionTopology.COORD


def test_absent_field_absorbed_concrete_single_branch_coordless(tmp_path: Path) -> None:
    """Absent-field absorption for the coord-less cell → concrete SINGLE_BRANCH.

    Preserves the removed shim's coord-less arm: a mission with
    ``coordination_branch: null`` and no ``topology`` key absorbs to a concrete
    SINGLE_BRANCH (never None), not just the COORD arm above.
    """
    feature_dir = tmp_path / "mission-absent-coordless"
    meta_path = _write_meta(feature_dir, {"coordination_branch": None})

    result = backfill_mission_topology(feature_dir)

    assert result.topology is not None
    assert result.topology == "single_branch"
    assert read_topology(feature_dir) is MissionTopology.SINGLE_BRANCH
    assert json.loads(meta_path.read_text(encoding="utf-8"))["topology"] == "single_branch"


def test_second_persist_run_idempotent_no_rewrite(tmp_path: Path) -> None:
    """Compute-once law: a second persist run skips and does not re-write.

    Re-pointed from the removed ``ensure_topology`` second-read-idempotent edge onto
    the persist seam: after the first backfill writes the derived value, the second
    run is a no-op ``skip`` with a byte-identical file.
    """
    feature_dir = tmp_path / "mission-once"
    meta_path = _write_meta(feature_dir, {"coordination_branch": None})

    first = backfill_mission_topology(feature_dir)
    after_first = _bytes(meta_path)
    second = backfill_mission_topology(feature_dir)

    assert first.topology == "single_branch"
    assert first.action == "wrote"
    assert second.action == "skip"
    assert second.topology == "single_branch"
    assert _bytes(meta_path) == after_first, "second run must not re-write"


def test_existing_flattened_flag_preserved_on_backfill(tmp_path: Path) -> None:
    """C-006: an existing ``flattened: true`` provenance flag is preserved on backfill.

    Re-pointed from the removed ``ensure_topology`` flag-preservation edge: deriving a
    missing topology must NOT clobber a pre-existing ``flattened`` provenance flag —
    the meta-flag survives the topology backfill (C-006). Negative control for the
    ``flattened`` provenance flag's independence from the (retired) FLATTENED enum.
    """
    feature_dir = tmp_path / "mission-flat"
    meta_path = _write_meta(feature_dir, {"coordination_branch": None, "flattened": True})

    result = backfill_mission_topology(feature_dir)

    assert result.topology == "single_branch"
    persisted = json.loads(meta_path.read_text(encoding="utf-8"))
    assert persisted["topology"] == "single_branch"
    assert persisted["flattened"] is True, "existing flattened provenance flag must survive"


# ---------------------------------------------------------------------------
# T012 — backfill_mission_topology: 4-cell classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coord", "lanes", "expected"),
    [
        (None, False, "single_branch"),
        (None, True, "lanes"),
        ("kitty/mission-x", False, "coord"),
        ("kitty/mission-x", True, "lanes_with_coord"),
    ],
)
def test_backfill_covers_four_cells(tmp_path: Path, coord: str | None, lanes: bool, expected: str) -> None:
    """All four coord × lanes combinations backfill to the matching topology value."""
    feature_dir = tmp_path / "kitty-specs" / f"mission-{expected}"
    meta: dict[str, object] = {}
    if coord is not None:
        meta["coordination_branch"] = coord
    _write_meta(feature_dir, meta)
    if lanes:
        _write_lanes(feature_dir)

    result = backfill_mission_topology(feature_dir)

    assert result.action == "wrote"
    assert result.topology == expected
    persisted = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert persisted["topology"] == expected
    assert persisted["flattened"] is False


def test_backfill_idempotent_second_run_skips(tmp_path: Path) -> None:
    """Second backfill run is all-skip with a byte-identical meta.json."""
    feature_dir = tmp_path / "kitty-specs" / "mission-idem"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x"})

    first = backfill_mission_topology(feature_dir)
    assert first.action == "wrote"
    bytes_after_first = _bytes(meta_path)

    second = backfill_mission_topology(feature_dir)
    assert second.action == "skip"
    assert second.topology == "coord"
    assert _bytes(meta_path) == bytes_after_first, "second run must not modify the file"


def test_backfill_never_overwrites_existing_value(tmp_path: Path) -> None:
    """An existing topology is preserved even if it disagrees with current signals."""
    feature_dir = tmp_path / "kitty-specs" / "mission-keep"
    # coordination_branch present (would derive coord) but a value is already stored.
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x", "topology": "single_branch"})

    result = backfill_mission_topology(feature_dir)

    assert result.action == "skip"
    persisted = json.loads(meta_path.read_text(encoding="utf-8"))
    assert persisted["topology"] == "single_branch", "existing value must not be overwritten"


def test_backfill_dry_run_writes_nothing(tmp_path: Path) -> None:
    """--dry-run reports the would-write but does not touch the file."""
    feature_dir = tmp_path / "kitty-specs" / "mission-dry"
    meta_path = _write_meta(feature_dir, {"coordination_branch": "kitty/x"})
    before = _bytes(meta_path)

    result = backfill_mission_topology(feature_dir, dry_run=True)

    assert result.action == "wrote"
    assert result.topology == "coord"
    assert _bytes(meta_path) == before, "dry-run must not write"
    assert "topology" not in json.loads(meta_path.read_text(encoding="utf-8"))


def test_backfill_corrupt_meta_returns_error(tmp_path: Path) -> None:
    """Corrupt meta.json yields an error result, not an exception."""
    feature_dir = tmp_path / "kitty-specs" / "mission-corrupt"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not json", encoding="utf-8")

    result = backfill_mission_topology(feature_dir)

    assert result.action == "error"
    assert result.topology is None
    assert "corrupt json" in (result.reason or "")


def test_backfill_missing_meta_skips(tmp_path: Path) -> None:
    """A directory with no meta.json is skipped, not errored."""
    feature_dir = tmp_path / "kitty-specs" / "mission-nometa"
    feature_dir.mkdir(parents=True)

    result = backfill_mission_topology(feature_dir)

    assert result.action == "skip"
    assert result.reason == "meta.json not found"


# ---------------------------------------------------------------------------
# T012 — backfill_topology_repo: walk + scoping
# ---------------------------------------------------------------------------


def test_backfill_repo_walks_all_missions(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "mission-a", {"coordination_branch": "kitty/a"})
    _write_meta(specs / "mission-b", {"coordination_branch": None})

    results = backfill_topology_repo(tmp_path)

    by_slug = {r.slug: r for r in results}
    assert by_slug["mission-a"].topology == "coord"
    assert by_slug["mission-b"].topology == "single_branch"


def test_backfill_repo_scopes_to_single_mission(tmp_path: Path) -> None:
    specs = tmp_path / "kitty-specs"
    _write_meta(specs / "mission-a", {"coordination_branch": "kitty/a"})
    _write_meta(specs / "mission-b", {"coordination_branch": None})

    results = backfill_topology_repo(tmp_path, mission_slug="mission-b")

    assert len(results) == 1
    assert results[0].slug == "mission-b"
    assert "topology" not in json.loads((specs / "mission-a" / "meta.json").read_text())


def test_backfill_repo_no_kitty_specs_returns_empty(tmp_path: Path) -> None:
    assert backfill_topology_repo(tmp_path) == []


# ---------------------------------------------------------------------------
# Review cycle-1 nit 3 — topology_from_meta: tolerant sibling of read_topology
# ---------------------------------------------------------------------------


def test_topology_from_meta_stored_value_no_disk_read(tmp_path: Path) -> None:
    """A stored value is returned verbatim; feature_dir need not even exist."""
    result = topology_from_meta({"topology": "coord"}, tmp_path / "does-not-exist")
    assert result is MissionTopology.COORD


def test_topology_from_meta_empty_mapping_derives_lanes_never_single_branch(tmp_path: Path) -> None:
    """The tolerant caller contract: an EMPTY dict (never a raise) still derives
    a concrete topology -- mirrors what a missing/malformed meta.json degrades to
    via ``load_meta_or_empty`` at every one of this function's three real callers.
    """
    feature_dir = tmp_path / "kitty-specs" / "mission-empty-meta"
    feature_dir.mkdir(parents=True)

    result = topology_from_meta({}, feature_dir)

    # #5100 FR-013 / #2602: nothing stored => never a derived ``single_branch``.
    assert result is MissionTopology.LANES


def test_topology_from_meta_never_touches_meta_json_on_disk(tmp_path: Path) -> None:
    """No meta.json read: a corrupt on-disk meta.json is irrelevant -- only the
    in-hand mapping argument is consulted (the whole point of the tolerant seam).
    """
    feature_dir = tmp_path / "kitty-specs" / "mission-corrupt-on-disk"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not json", encoding="utf-8")

    result = topology_from_meta({"topology": "lanes"}, feature_dir)

    assert result is MissionTopology.LANES


def test_topology_from_meta_absent_field_derives_via_lanes_signal(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "mission-derive"
    feature_dir.mkdir(parents=True)
    _write_lanes(feature_dir)

    result = topology_from_meta({"coordination_branch": "kitty/x"}, feature_dir)

    assert result is MissionTopology.LANES_WITH_COORD


# ---------------------------------------------------------------------------
# #5100 WP05 cycle 2 (review Issue 3) — stored_topology: the stored-only,
# no-derive-fallback authority topology_from_meta layers its derive on top of.
# ---------------------------------------------------------------------------


def test_stored_topology_returns_explicit_valid_value() -> None:
    assert stored_topology({"topology": "single_branch"}) is MissionTopology.SINGLE_BRANCH


def test_stored_topology_returns_none_when_absent() -> None:
    """No derive fallback -- unlike topology_from_meta, an absent field is
    ``None``, never a classified topology."""
    assert stored_topology({}) is None
    assert stored_topology({"coordination_branch": "kitty/x"}) is None


def test_stored_topology_returns_none_for_invalid_value() -> None:
    assert stored_topology({"topology": "not-a-real-topology"}) is None
    assert stored_topology({"topology": 42}) is None


# ---------------------------------------------------------------------------
# #5100 FR-013 / #2602 (pre-PR squad N7) — an UNSTAMPED mission never derives
# ``single_branch`` at runtime; the explicit backfill writer keeps the 2x2 cell.
# ---------------------------------------------------------------------------


def test_unstamped_coordless_mission_derives_lanes_at_runtime_but_backfill_keeps_single_branch(
    tmp_path: Path,
) -> None:
    """The same unstamped, coord-less, lane-less mission reads ``LANES`` through
    every runtime reader (``topology_from_meta`` / ``read_topology``) -- so finalize
    groups its code WPs into lanes and no ``WRITE_CHECKOUT_*`` refusal arms -- while
    the explicit ``backfill_mission_topology`` writer still persists the
    origin/main ``single_branch`` classification an operator then owns.
    """
    feature_dir = tmp_path / "kitty-specs" / "legacy-unstamped"
    meta_path = _write_meta(feature_dir, {"mission_slug": "legacy-unstamped"})

    assert topology_from_meta({"mission_slug": "legacy-unstamped"}, feature_dir) is MissionTopology.LANES
    assert read_topology(feature_dir) is MissionTopology.LANES

    result = backfill_mission_topology(feature_dir)

    assert result.topology == "single_branch"
    assert json.loads(meta_path.read_text(encoding="utf-8"))["topology"] == "single_branch"
    # Once STORED (explicitly), single_branch is honoured verbatim.
    assert read_topology(feature_dir) is MissionTopology.SINGLE_BRANCH


@pytest.mark.parametrize(
    ("derived", "expected"),
    [
        (MissionTopology.SINGLE_BRANCH, MissionTopology.LANES),
        (MissionTopology.LANES, MissionTopology.LANES),
        (MissionTopology.COORD, MissionTopology.COORD),
        (MissionTopology.LANES_WITH_COORD, MissionTopology.LANES_WITH_COORD),
    ],
)
def test_unstamped_runtime_topology_never_returns_single_branch(derived: MissionTopology, expected: MissionTopology) -> None:
    from mission_runtime import unstamped_runtime_topology

    assert unstamped_runtime_topology(derived) is expected
