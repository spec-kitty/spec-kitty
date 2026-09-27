"""Regression: the one-time migration and the WP09 birth-cutover coexist.

Realises **NFR-006** / **IC-09** (plan.md — read the risk block, it is the
crux this WP10 mission closes): after FR-008's authoring retirement
(WP04/WP05) most missions never carry frontmatter runtime state, so their
``status_phase`` flip happens *forward*, live, at merge time via WP09's
``_run_birth_cutover`` hook (``specify_cli.consolidation.executor``). A legacy
deployment's pre-existing corpus still needs the *backward*, one-time
``spec-kitty migrate backfill-runtime-state`` cutover
(:class:`~specify_cli.upgrade.migrations.m_zz_runtime_state_backfill.RuntimeStateBackfillMigration`).

Both flows are thin callers of the SAME shared spine —
:func:`~specify_cli.migration.runtime_state_cutover.cutover_mission` (seed ->
fail-closed verify -> atomic ``status_phase`` flip) — so this suite proves
that spine is genuinely reentrant regardless of which caller reaches it first
and in what order:

* the migration alone still cuts over a legacy (frontmatter-authored, no
  seed events) corpus green (NFR-006's core backward-flow regression guard);
* a clean re-run of the migration seeds nothing (NFR-002 idempotency);
* birth-then-migration is byte-identical (a mission WP09 already reconciled
  at merge time is untouched by a later corpus-wide migration run);
* migration-then-birth is byte-identical (a mission the migration already
  cut over is untouched by a later, redundant birth-cutover call — e.g. a
  stray re-merge hook);
* a mixed corpus (one still-legacy mission + one already-birthed mission)
  proves the two flows coexist on one spine with zero cross-mission
  interference.

No production code under this WP's scope is modified: this is a test-only
regression over the SHARED, already-approved spine (WP01 ``cutover_mission``,
WP09 ``_run_birth_cutover``) and the standing migration
(``m_zz_runtime_state_backfill``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.backfill_runtime_state import verify_backfill
from specify_cli.migration.runtime_state_cutover import cutover_mission
from specify_cli.status import (
    Lane,
    StatusEvent,
    build_claim_policy_metadata,
)
from specify_cli.status._unsafe import append_events_atomic_verified
from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import (
    RuntimeStateBackfillMigration,
)
from tests.unit.migration._backfill_fixture import CLAIMED_AT, build_mission

pytestmark = [pytest.mark.fast]

_STATUS_PHASE = "status_phase"


def _build_born_mission(
    tmp_path: Path,
    *,
    slug: str = "born-coord-birth-01KZQ7MF",
    mission_id: str = "01KZQ7MFH8T2X6R4N9YV3D5C7A",
) -> Path:
    """A post-retirement "born" mission: no frontmatter runtime authoring at
    all (FR-008 / WP04-WP05 shape) — only a genuine live-emitted claim
    carrying real ``policy_metadata`` in the event log, exactly the shape
    WP09's birth-cutover reconciles at merge time. ``read_legacy_runtime``
    reports zero evictable state for this fixture on either frontmatter key.
    """
    feature_dir = tmp_path / "kitty-specs" / slug
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True)

    meta = {"mission_id": mission_id, "mission_slug": slug, "mission_type": "software-dev"}
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Authoring-retired WP frontmatter: no shell_pid/agent/assignee/tracker_refs,
    # and no tasks.md checkbox rows — subtask completion is entirely
    # event-sourced post-retirement (no legacy proxy to author).
    (tasks / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Born Demo\nexecution_mode: code_change\n---\n\n# WP01 body\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 Demo\n\n", encoding="utf-8")

    claim = StatusEvent(
        event_id="01BORNBORNBORNBORNBORNBOR",
        mission_slug=slug,
        mission_id=mission_id,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at=CLAIMED_AT,
        actor="claude:sonnet:pedro",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=91234,
            shell_pid_created_at="2026-07-25T09:00:00+00:00",
            agent="claude:sonnet:pedro",
        ),
    )
    append_events_atomic_verified(feature_dir, [claim])
    return feature_dir


# ---------------------------------------------------------------------------
# NFR-006 — backward flow: the one-time migration still cuts over a legacy corpus
# ---------------------------------------------------------------------------


def test_migration_cuts_over_legacy_corpus_green(tmp_path: Path) -> None:
    """A legacy (frontmatter-authored, no seed events) corpus cuts over green."""
    feature_dir = build_mission(tmp_path)  # frontmatter-authored, no seed events
    meta_before = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert _STATUS_PHASE not in meta_before, "fixture must start genuinely un-flipped"

    migration = RuntimeStateBackfillMigration()
    assert migration.detect(tmp_path) is True, "un-migrated legacy corpus must be detected"

    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made, "the migration must report the seed/flip it performed"
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert int(meta[_STATUS_PHASE]) >= 1
    verify_result = verify_backfill(feature_dir)
    assert verify_result.ok, verify_result.mismatches


def test_migration_rerun_seeds_nothing_idempotent(tmp_path: Path) -> None:
    """A clean re-run over an already-migrated corpus seeds/flips nothing (NFR-002)."""
    feature_dir = build_mission(tmp_path)
    migration = RuntimeStateBackfillMigration()
    migration.apply(tmp_path)
    meta_after_first = (feature_dir / "meta.json").read_bytes()
    events_after_first = (feature_dir / "status.events.jsonl").read_bytes()

    assert migration.detect(tmp_path) is False, "nothing should remain to migrate"
    second = migration.apply(tmp_path)

    assert second.success is True
    assert second.changes_made == []
    assert (feature_dir / "meta.json").read_bytes() == meta_after_first
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_after_first


# ---------------------------------------------------------------------------
# IC-09 — forward (birth) + backward (migration) coexistence on ONE spine
# ---------------------------------------------------------------------------


def test_birth_then_migration_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    """A born mission (birth-cutover already ran at merge) is untouched by a
    later corpus-wide migration run."""
    feature_dir = _build_born_mission(tmp_path)

    birth = cutover_mission(feature_dir)  # simulates the merge-time birth-cutover hook
    assert birth.flipped is True
    assert birth.error is None

    meta_after_birth = (feature_dir / "meta.json").read_bytes()
    events_after_birth = (feature_dir / "status.events.jsonl").read_bytes()

    migration = RuntimeStateBackfillMigration()
    assert migration.detect(tmp_path) is False, "an already-birthed mission needs no migration"
    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made == []
    assert (feature_dir / "meta.json").read_bytes() == meta_after_birth
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_after_birth


def test_migration_then_birth_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    """A legacy mission the migration already cut over is untouched by a
    later, redundant birth-cutover call — forward and backward flows share
    ONE idempotent spine (NFR-002 / IC-09)."""
    feature_dir = build_mission(tmp_path)

    migration = RuntimeStateBackfillMigration()
    first = migration.apply(tmp_path)
    assert first.success is True
    assert first.changes_made

    meta_after_migration = (feature_dir / "meta.json").read_bytes()
    events_after_migration = (feature_dir / "status.events.jsonl").read_bytes()

    birth = cutover_mission(feature_dir)  # simulates a redundant birth-cutover call

    assert birth.flipped is True
    assert birth.seeded_count == 0
    assert (feature_dir / "meta.json").read_bytes() == meta_after_migration
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_after_migration


def test_migration_over_mixed_corpus_leaves_born_mission_untouched(tmp_path: Path) -> None:
    """A corpus carrying BOTH a still-legacy mission AND an already-birthed
    mission: the corpus-wide migration cuts over the legacy one and leaves
    the birthed one byte-identical — the two flows coexist on one spine with
    zero cross-mission interference."""
    legacy_dir = build_mission(
        tmp_path, slug="legacy-042-demo", mission_id="01KZQ7MFLEGACY0000000001A"
    )
    legacy_meta_before = json.loads((legacy_dir / "meta.json").read_text(encoding="utf-8"))
    assert _STATUS_PHASE not in legacy_meta_before, "legacy fixture must start un-flipped"
    born_dir = _build_born_mission(tmp_path)

    cutover_mission(born_dir)  # birth-cutover already reconciled this one at merge
    born_meta_before = (born_dir / "meta.json").read_bytes()
    born_events_before = (born_dir / "status.events.jsonl").read_bytes()

    migration = RuntimeStateBackfillMigration()
    result = migration.apply(tmp_path)

    assert result.success is True
    legacy_meta = json.loads((legacy_dir / "meta.json").read_text(encoding="utf-8"))
    assert int(legacy_meta[_STATUS_PHASE]) >= 1
    legacy_verify = verify_backfill(legacy_dir)
    assert legacy_verify.ok, legacy_verify.mismatches
    assert (born_dir / "meta.json").read_bytes() == born_meta_before
    assert (born_dir / "status.events.jsonl").read_bytes() == born_events_before
