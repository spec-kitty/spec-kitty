"""The three in-process migration writers and the two compatibility seams (#6722).

A migration seed now records ``{"tool": "migration:<id>", "role": "system",
"profile": null, "model": null}`` instead of a bare string. Three properties carry this
change, and each has its own family of tests here:

* **FR-007** every writer stores the structured actor, and nothing else about the seed
  changes (same deterministic ``event_id``, same lanes, same payload).
* **FR-009** the seed predicates stay shape-blind: the shared prefix predicate, and the
  per-backfill predicate in ``backfill_runtime_state`` that answers "is this *this*
  backfill's seed?".
* **FR-010** a corpus seeded by the pre-change code still verifies. Seed rows are
  immutable, so ``verify_backfill`` must accept a row whose only difference is the
  actor's shape — and must still refuse one whose *identity* differs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli
from specify_cli.migration import backfill_runtime_state as runtime_backfill
from specify_cli.migration import wp_status_backfill as wp_backfill
from specify_cli.status.actor import build_system_actor
from specify_cli.status.models import actor_identity_str, is_migration_actor
from specify_cli.status.store import read_event_stream
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.fast]

SRC_ROOT = Path(specify_cli.__file__).resolve().parent
SLUG = "042-system-actor-demo"
MISSION_ID = "01SYSTEMACTOR00000000000001"

_WP_STATUS_IDENTITY = "migration:backfill_wp_status"
_RUNTIME_IDENTITY = "migration:backfill_runtime_state"
_VERDICT_IDENTITY = "migration:verdict_provenance_backfill"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _wp_mission(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ID, "mission_slug": SLUG, "mission_type": "software-dev"}), encoding="utf-8")
    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}-demo.md").write_text(f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\n---\n\n# {wp_id}\n", encoding="utf-8")
    return feature_dir


def _verdict_mission(tmp_path: Path) -> Path:
    from specify_cli.review.artifacts import ReviewCycleArtifact

    feature_dir = tmp_path / SLUG
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ID, "mission_slug": SLUG}), encoding="utf-8")
    sub_dir = feature_dir / "tasks" / "WP01"
    artifact = ReviewCycleArtifact(cycle_number=1, wp_id="WP01", mission_slug=SLUG, reviewer_agent="reviewer-renata", reviewed_at="2026-01-01T00:00:00+00:00")
    path = sub_dir / "review-cycle-1.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(f"---\nverdict: approved\n{text[4:]}", encoding="utf-8")
    return feature_dir


def _write_rows(feature_dir: Path, rows: list[dict[str, object]]) -> None:
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _rewrite_seed_actor_to_the_pre_change_string(feature_dir: Path) -> int:
    """Rewrite every seed row's actor to the bare string the pre-#6722 code wrote.

    Simulates a corpus seeded by an older CLI: the rows are immutable in a real log,
    which is exactly why the readers (not a rewrite) must stay compatible.
    """
    path = feature_dir / "status.events.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rewritten = 0
    for row in rows:
        if is_migration_actor(row.get("actor")):
            row["actor"] = actor_identity_str(row["actor"])
            rewritten += 1
    _write_rows(feature_dir, rows)
    return rewritten


# ---------------------------------------------------------------------------
# FR-007 — the three writers
# ---------------------------------------------------------------------------


def test_wp_status_backfill_keeps_its_deterministic_event_id(tmp_path: Path) -> None:
    """The actor is not an id input: the same corpus must mint the same seed ids."""
    feature_dir = _wp_mission(tmp_path)
    plan = wp_backfill.plan_wp_status_backfill(feature_dir)
    assert plan.events
    for event in plan.events:
        # The id is keyed on (mission key, wp, to_lane, namespace) -- never on the actor.
        assert event.event_id == wp_backfill.seed_event_id(MISSION_ID, event.wp_id, str(event.to_lane)) or event.event_id == wp_backfill.seed_event_id(
            feature_dir.name, event.wp_id, str(event.to_lane)
        )


def _seeds(feature_dir: Path) -> list[object]:
    stream = read_event_stream(feature_dir)
    return [e for e in [*stream.transitions, *stream.annotations] if is_migration_actor(e.actor)]


def test_runtime_backfill_keeps_its_deterministic_seed_ids(tmp_path: Path) -> None:
    """`_seed_id` never hashed the actor, so a re-run mints byte-identical ids."""
    feature_dir = build_mission(tmp_path)
    runtime_backfill.backfill_runtime_state(feature_dir)
    before = {e.event_id for e in _seeds(feature_dir)}
    assert before

    assert runtime_backfill.backfill_runtime_state(feature_dir).seeded_count == 0
    assert {e.event_id for e in _seeds(feature_dir)} == before


# ---------------------------------------------------------------------------
# FR-009 — the two predicates are shape-blind
# ---------------------------------------------------------------------------


def test_shared_prefix_predicate_is_shape_blind() -> None:
    assert is_migration_actor(_RUNTIME_IDENTITY) is True
    assert is_migration_actor(build_system_actor(_RUNTIME_IDENTITY)) is True


def test_per_backfill_predicate_recognises_both_shapes() -> None:
    """Seam A: the narrow predicate answers "this backfill's seed" for either shape."""
    assert runtime_backfill._is_migration_actor(_RUNTIME_IDENTITY) is True
    assert runtime_backfill._is_migration_actor(build_system_actor(_RUNTIME_IDENTITY)) is True


def test_per_backfill_predicate_stays_narrower_than_the_shared_one() -> None:
    """Another migration's seed is a seed, but not *this* backfill's seed."""
    other = build_system_actor(_WP_STATUS_IDENTITY)
    assert is_migration_actor(other) is True
    assert runtime_backfill._is_migration_actor(other) is False
    assert runtime_backfill._is_migration_actor(_WP_STATUS_IDENTITY) is False
    assert runtime_backfill._is_migration_actor("claude") is False


def test_a_mixed_shape_log_still_separates_seeds_from_history(tmp_path: Path) -> None:
    """Seam A drives `_stream_without_migration`; a mixed log must classify both shapes as seeds."""
    feature_dir = build_mission(tmp_path)
    runtime_backfill.backfill_runtime_state(feature_dir)
    rewritten = _rewrite_seed_actor_to_the_pre_change_string(feature_dir)
    assert rewritten > 0
    stream = read_event_stream(feature_dir)
    without_migration = runtime_backfill._stream_without_migration(stream)
    assert [e for e in [*without_migration.transitions, *without_migration.annotations] if is_migration_actor(e.actor)] == []


# ---------------------------------------------------------------------------
# FR-010 — a pre-change corpus still verifies (Seam B), and only a shape differs
# ---------------------------------------------------------------------------


def test_a_pre_change_corpus_verifies_ok(tmp_path: Path) -> None:
    """The one user-visible risk: an upgrade must not report a healthy log as tampered."""
    feature_dir = build_mission(tmp_path)
    runtime_backfill.backfill_runtime_state(feature_dir)
    assert _rewrite_seed_actor_to_the_pre_change_string(feature_dir) > 0

    result = runtime_backfill.verify_backfill(feature_dir)
    assert result.ok is True, result.mismatches
    assert result.mismatches == ()


def test_the_tolerance_is_shape_only_not_identity_blind() -> None:
    """Seam B, at the comparison it changes: same identity in either shape is sound,
    a different identity is not, and the verdicts are decided on the same fixture."""
    from specify_cli.status.models import Lane, StatusEvent

    def _event(actor: object, to_lane: object = Lane.CLAIMED) -> StatusEvent:
        return StatusEvent(
            event_id="7SZJ4PZBVXFXQ9BPFN6QJH0HBJ",
            mission_slug=SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=to_lane,  # type: ignore[arg-type]
            at="2026-05-31T00:00:00+00:00",
            actor=actor,  # type: ignore[arg-type]
            force=False,
            execution_mode="worktree",
        )

    expected = _event(build_system_actor(_RUNTIME_IDENTITY))
    mismatched = runtime_backfill._seed_row_mismatch

    # (a) the shape-only difference is sound: the pre-change string row for this identity.
    assert mismatched(_event(_RUNTIME_IDENTITY), expected, "claim", {}, _empty_stream()) is None
    # (b) a different identity is still tampering.
    other_identity = mismatched(_event(build_system_actor(_WP_STATUS_IDENTITY)), expected, "claim", {}, _empty_stream())
    assert other_identity is not None and "diverged" in other_identity
    # (c) a different payload is still tampering.
    assert mismatched(_event(build_system_actor(_RUNTIME_IDENTITY), Lane.IN_PROGRESS), expected, "claim", {}, _empty_stream()) is not None


def _empty_stream() -> object:
    from specify_cli.status.models import EventStream

    return EventStream(transitions=[], annotations=[])


def test_a_corrupted_slot_is_still_a_mismatch(tmp_path: Path) -> None:
    """The tolerance must not become a blanket pass over a genuinely damaged seed."""
    from tests.unit.migration._backfill_fixture import corrupt_seed_value

    feature_dir = build_mission(tmp_path)
    runtime_backfill.backfill_runtime_state(feature_dir)
    _rewrite_seed_actor_to_the_pre_change_string(feature_dir)
    corrupt_seed_value(feature_dir, field_name="subtasks", slot_name="subtasks", value={"T001": "planned", "T002": "planned"})

    result = runtime_backfill.verify_backfill(feature_dir)
    assert result.ok is False
