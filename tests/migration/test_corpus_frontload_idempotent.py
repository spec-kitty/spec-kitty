"""Permanent guard (WP01 / FR-007 / NFR-003): the corpus front-load is idempotent.

**Landing note (2026-08, `tests/regression/` campsite clean).** This is a
permanent regression guard, not a red-first reproduction, so it carries no
`regression` marker and lives with its sibling migration-cutover tests here
rather than in `tests/regression/`. FR-007/NFR-003 kept as history below.

Mission #2892-family ``coord-write-placement-closure`` WP01 runs the canonical
``spec-kitty migrate backfill-runtime-state`` cutover
(:func:`~specify_cli.migration.runtime_state_cutover.cutover_mission` /
:func:`~specify_cli.migration.runtime_state_cutover.cutover_repo`) over the
drifted dogfood corpus and commits the flips. NFR-003 requires that a *second*
run over an already-migrated mission is a genuine no-op: it seeds zero new
events and leaves ``status_phase`` and the event log byte-identical (the
deterministic seed ids are namespaced on the immutable ``mission_id``).

This guard proves that property on a **synthetic fixture corpus** built with
real, randomly-generated (:mod:`ulid`) 26-char ``mission_id`` values — not the
placeholder-shaped id the shared migration fixture defaults to — so the
seed-id namespacing (``deterministic_ulid(f"{mission_id}|{wp_id}|{field}")``)
is exercised the same way it is against the real ``kitty-specs/`` corpus,
across more than one mission at once (a mini corpus, walked via
``cutover_repo``), proving seed ids do not collide across missions either.

A companion sanity test proves the byte-identity assertions are not vacuous:
deliberately corrupting an already-seeded payload changes the on-disk bytes,
so a real regression would be caught, not silently accepted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import ulid

from specify_cli.migration.runtime_state_cutover import cutover_mission, cutover_repo
from tests.unit.migration._backfill_fixture import build_mission, corrupt_seed_value

pytestmark = [pytest.mark.fast]


def _snapshot(feature_dir: Path) -> tuple[bytes, bytes]:
    """Return the exact on-disk bytes of the two files the cutover writes to."""
    meta_bytes = (feature_dir / "meta.json").read_bytes()
    events_bytes = (feature_dir / "status.events.jsonl").read_bytes()
    return meta_bytes, events_bytes


def _real_mission_id() -> str:
    """A genuine, randomly-minted 26-char ULID — production-shaped, not a placeholder."""
    mission_id = str(ulid.ULID())
    assert len(mission_id) == 26, f"unexpected ULID length: {mission_id!r}"
    return mission_id


def test_second_cutover_run_seeds_nothing_and_is_byte_identical(tmp_path: Path) -> None:
    """A re-run over one already-migrated mission seeds 0 events, byte-stable."""
    mission_id = _real_mission_id()
    feature_dir = build_mission(tmp_path, mission_id=mission_id, slug="frontload-demo-a")

    first = cutover_mission(feature_dir)
    assert first.flipped is True
    assert first.seeded_count > 0
    assert first.verify is not None and first.verify.ok
    snapshot_after_first = _snapshot(feature_dir)

    second = cutover_mission(feature_dir)

    assert second.seeded_count == 0, "a re-run over a migrated mission must seed 0 events"
    assert second.verify is not None and second.verify.ok
    assert _snapshot(feature_dir) == snapshot_after_first, (
        "meta.json + status.events.jsonl must be byte-identical after the re-run"
    )


def test_second_corpus_walk_is_byte_identical_across_multiple_missions(tmp_path: Path) -> None:
    """``cutover_repo`` over a mini multi-mission corpus is idempotent for all of them.

    Two distinct real ULIDs prove the deterministic seed-id namespacing does not
    collide across missions: each mission's re-run independently seeds nothing.
    """
    feature_dirs = [
        build_mission(tmp_path, mission_id=_real_mission_id(), slug=slug)
        for slug in ("frontload-demo-b", "frontload-demo-c")
    ]

    first_results = cutover_repo(tmp_path)
    assert {r.slug for r in first_results} == {"frontload-demo-b", "frontload-demo-c"}
    assert all(r.flipped and r.seeded_count > 0 and r.verify is not None and r.verify.ok for r in first_results)
    snapshots_after_first = {fd.name: _snapshot(fd) for fd in feature_dirs}

    second_results = cutover_repo(tmp_path)

    assert all(r.seeded_count == 0 for r in second_results), (
        "corpus re-run must seed 0 events for every already-migrated mission"
    )
    assert all(r.verify is not None and r.verify.ok for r in second_results)
    for feature_dir in feature_dirs:
        assert _snapshot(feature_dir) == snapshots_after_first[feature_dir.name], (
            f"{feature_dir.name}: byte-identity broken by the corpus re-run"
        )


def test_second_run_does_not_reorder_the_event_log(tmp_path: Path) -> None:
    """The event log's line order (not just its total content) is stable on re-run."""
    feature_dir = build_mission(tmp_path, mission_id=_real_mission_id(), slug="frontload-demo-order")

    cutover_mission(feature_dir)
    events_path = feature_dir / "status.events.jsonl"
    lines_after_first = events_path.read_text(encoding="utf-8").splitlines()

    cutover_mission(feature_dir)
    lines_after_second = events_path.read_text(encoding="utf-8").splitlines()

    assert lines_after_second == lines_after_first


def test_byte_identity_assertion_detects_injected_drift(tmp_path: Path) -> None:
    """Sanity: the byte-identity check above is not vacuous.

    Corrupting an already-seeded deterministic payload in place must actually
    perturb the on-disk bytes — proving a genuine idempotency regression would
    be caught by the assertions in the tests above, not silently passed.
    """
    feature_dir = build_mission(tmp_path, mission_id=_real_mission_id(), slug="frontload-demo-drift")
    cutover_mission(feature_dir)
    snapshot_before_drift = _snapshot(feature_dir)

    corrupt_seed_value(feature_dir, field_name="assignee", slot_name="assignee", value="INJECTED-DRIFT")

    assert _snapshot(feature_dir) != snapshot_before_drift, (
        "the drift-injection fixture did not perturb the event log; "
        "the idempotency guard above would not catch a real regression"
    )
