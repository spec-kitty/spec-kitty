"""Unit tests for the WP03 migration engine (T010–T014).

Covers the ``MUTABLE_FIELDS``/``STATIC_FIELDS`` reclassification (T010),
deterministic namespaced-ULID seeding + clamp honesty (T011), fail-closed verify
including the pre-strip ordering guard (T012), the ``history[]``/``progress``
zero-reader proof (T013), and the idempotency/determinism/precondition assertions
(T014).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli
from specify_cli.migration import backfill_runtime_state as b
from specify_cli.migration.strip_frontmatter import (
    MUTABLE_FIELDS,
    RETIRED_FIELDS,
    STATIC_FIELDS,
    strip_mutable_fields,
)
from specify_cli.status.models import Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.store import (
    append_annotations_atomic_verified,
    append_events_atomic_verified,
    read_event_stream,
)
from specify_cli.status.wp_view import reconstruct_wp_view
from tests.unit.migration._backfill_fixture import (
    AT_ENCODINGS,
    CLAIMED_AT,
    IN_PROGRESS_AT,
    build_mission,
    corrupt_seed_value,
    encode_at,
)

pytestmark = [pytest.mark.fast]

SRC_ROOT = Path(specify_cli.__file__).resolve().parent


@pytest.mark.parametrize("unsafe_slug", ["../outside", "nested/mission", ".", ".."])
def test_repo_backfill_rejects_unsafe_mission_selector(
    tmp_path: Path,
    unsafe_slug: str,
) -> None:
    """The write-capable library validates selectors at its own boundary."""
    (tmp_path / "kitty-specs").mkdir()

    with pytest.raises(ValueError, match="safe path segment"):
        b.backfill_runtime_state_repo(tmp_path, mission_slug=unsafe_slug)


def test_repo_backfill_rejects_selected_mission_symlink_escape(tmp_path: Path) -> None:
    kitty_specs = tmp_path / "kitty-specs"
    kitty_specs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (kitty_specs / "escaped").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside kitty-specs"):
        b.backfill_runtime_state_repo(tmp_path, mission_slug="escaped")


def test_repo_backfill_skips_enumerated_mission_symlink_escape(tmp_path: Path) -> None:
    kitty_specs = tmp_path / "kitty-specs"
    kitty_specs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (kitty_specs / "escaped").symlink_to(outside, target_is_directory=True)

    assert b.backfill_runtime_state_repo(tmp_path) == []


# ---------------------------------------------------------------------------
# T010 — MUTABLE_FIELDS / STATIC_FIELDS reclassification
# ---------------------------------------------------------------------------


def test_mutable_fields_gains_evicted_fields() -> None:
    for name in (
        "shell_pid_created_at",
        "review_artifact_override_at",
        "review_artifact_override_actor",
        "review_artifact_override_wp_id",
        "review_artifact_override_reason",
        "reviewer_shell_pid",
        "history",
    ):
        assert name in MUTABLE_FIELDS, name
    # Pre-existing members are untouched.
    for name in ("progress", "shell_pid", "agent", "assignee", "review_status", "reviewed_by", "review_feedback", "lane"):
        assert name in MUTABLE_FIELDS, name


def test_history_moved_out_of_static_and_into_mutable() -> None:
    assert "history" not in STATIC_FIELDS
    assert "history" in MUTABLE_FIELDS


def test_progress_retired_explicitly_not_silently_dropped() -> None:
    # Retired = documented + still stripped (member of MUTABLE_FIELDS).
    assert "progress" in RETIRED_FIELDS
    assert "history" in RETIRED_FIELDS
    assert "progress" in MUTABLE_FIELDS


def test_strip_removes_history_and_new_mutable_keys(tmp_path: Path) -> None:
    from specify_cli.frontmatter import FrontmatterManager

    feature_dir = build_mission(tmp_path)
    strip_mutable_fields(feature_dir)
    frontmatter, _ = FrontmatterManager().read(feature_dir / "tasks" / "WP01-demo.md")
    assert "history" not in frontmatter
    assert "shell_pid" not in frontmatter
    assert "shell_pid_created_at" not in frontmatter
    assert "agent" not in frontmatter
    assert "review_artifact_override_at" not in frontmatter
    # Static intent survives.
    assert frontmatter["work_package_id"] == "WP01"
    assert frontmatter["title"] == "Demo WP"


# ---------------------------------------------------------------------------
# T011 — backfill: seeds, determinism, clamp, idempotency
# ---------------------------------------------------------------------------


def test_seed_floor_precedes_transition_and_annotation_history(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    append_annotations_atomic_verified(
        feature_dir,
        [
            b.annotate(
                "WP01",
                WPInnerStateDelta(agent="later-agent"),
                actor={
                    "role": "implementer",
                    "profile": "python-pedro",
                    "tool": "codex",
                    "model": "gpt-5.6-sol",
                },
                at=CLAIMED_AT,
                event_id="01BBBBBBBBBBBBBBBBBBBBBBB1",
            )
        ],
    )
    stream_before = read_event_stream(feature_dir)
    legitimate_keys = [
        (event.at, event.event_id)
        for event in (*stream_before.transitions, *stream_before.annotations)
    ]

    result = b.backfill_runtime_state(feature_dir)

    assert result.seeded_count > 0
    stream_after = read_event_stream(feature_dir)
    seeds = [
        event
        for event in (*stream_after.transitions, *stream_after.annotations)
        if event.actor == b.BACKFILL_ACTOR
    ]
    assert seeds
    assert all(
        (seed.at, seed.event_id) < history_key
        for seed in seeds
        for history_key in legitimate_keys
    )


def test_seed_floor_uses_annotation_only_history(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path, with_transitions=False)
    append_annotations_atomic_verified(
        feature_dir,
        [
            b.annotate(
                "WP01",
                WPInnerStateDelta(assignee="later-assignee"),
                actor="legitimate-writer",
                at="2026-01-02T03:04:05+00:00",
                event_id="01BBBBBBBBBBBBBBBBBBBBBBB2",
            )
        ],
    )

    result = b.backfill_runtime_state(feature_dir)

    assert result.seeded_count > 0
    stream = read_event_stream(feature_dir)
    seed_keys = [
        (event.at, event.event_id)
        for event in (*stream.transitions, *stream.annotations)
        if event.actor == b.BACKFILL_ACTOR
    ]
    annotation_key = (
        "2026-01-02T03:04:05+00:00",
        "01BBBBBBBBBBBBBBBBBBBBBBB2",
    )
    assert seed_keys
    assert all(key < annotation_key for key in seed_keys)


@pytest.mark.parametrize(
    "bad_at",
    [
        "not-a-timestamp",
        "0001-01-01T00:00:00+00:00",
    ],
)
def test_unrepresentable_seed_floor_fails_before_append(
    tmp_path: Path,
    bad_at: str,
) -> None:
    feature_dir = build_mission(tmp_path)
    events_path = feature_dir / "status.events.jsonl"
    rows = events_path.read_text(encoding="utf-8").splitlines()
    rows[0] = rows[0].replace(CLAIMED_AT, bad_at)
    events_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    before = events_path.read_bytes()

    with pytest.raises(b.MigrationOrderingError, match="strict seed history floor"):
        b.backfill_runtime_state(feature_dir)

    assert events_path.read_bytes() == before


def test_claim_slot_witness_allows_later_legitimate_writer(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    append_annotations_atomic_verified(
        feature_dir,
        [
            b.annotate(
                "WP01",
                WPInnerStateDelta(agent="reviewer-renata"),
                actor="legitimate-writer",
                at="2026-01-03T00:00:00+00:00",
                event_id="01BBBBBBBBBBBBBBBBBBBBBBB3",
            )
        ],
    )

    first = b.backfill_runtime_state(feature_dir)
    assert first.seeded_count > 0
    assert b.verify_backfill(feature_dir).ok
    assert materialize_snapshot(feature_dir).work_packages["WP01"]["agent"] == "reviewer-renata"
    before = (feature_dir / "status.events.jsonl").read_bytes()

    second = b.backfill_runtime_state(feature_dir)

    assert second.seeded_count == 0
    assert (feature_dir / "status.events.jsonl").read_bytes() == before


def test_persisted_bad_claim_seed_repairs_lane_and_later_claim_slots(
    tmp_path: Path,
) -> None:
    feature_dir = build_mission(tmp_path)
    events_path = feature_dir / "status.events.jsonl"
    rows = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["policy_metadata"] = {
        "shell_pid": 991,
        "shell_pid_created_at": "later-claim-time",
        "agent": "later-legitimate-agent",
    }
    events_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id=b._seed_id(
                    b._mission_id(feature_dir),
                    "WP01",
                    "claim",
                ),
                mission_slug=feature_dir.name,
                mission_id=b._mission_id(feature_dir),
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-01-02T04:00:00+00:00",
                actor=b.BACKFILL_ACTOR,
                force=False,
                execution_mode="worktree",
                policy_metadata={
                    "shell_pid": 44821,
                    "shell_pid_created_at": "1784458183.44",
                    "agent": "claude:opus:pedro",
                },
            )
        ],
    )
    assert materialize_snapshot(feature_dir).work_packages["WP01"]["lane"] == "claimed"

    result = b.backfill_runtime_state(feature_dir)

    assert result.seeded_count > 0
    snapshot = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert snapshot["lane"] == "in_progress"
    assert snapshot["shell_pid"] == 991
    assert snapshot["shell_pid_created_at"] == "later-claim-time"
    assert snapshot["agent"] == "later-legitimate-agent"
    assert b.verify_backfill(feature_dir).ok
    repairs = [
        event
        for event in read_event_stream(feature_dir).annotations
        if event.actor == b.COMPATIBILITY_REPAIR_ACTOR
    ]
    # Exactly one repair row may be minted: the compatibility repair is
    # append-only and idempotent, so a second row would be a duplicate write.
    assert len(repairs) == 1
    assert repairs[0].delta.shell_pid == 991
    before = events_path.read_bytes()

    assert b.backfill_runtime_state(feature_dir).seeded_count == 0
    assert events_path.read_bytes() == before


def test_backfill_seeds_positive_then_snapshot_matches_old_reader(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    result = b.backfill_runtime_state(feature_dir)
    assert result.action == "wrote"
    assert result.seeded_count > 0

    snap = materialize_snapshot(feature_dir)
    wp = snap.work_packages["WP01"]
    # The lane history is preserved (claim seed slots BEFORE later transitions).
    assert wp["lane"] == str(Lane.IN_PROGRESS)
    # Claim state folded from the seed transition's policy_metadata.
    assert wp["shell_pid"] == 44821
    assert wp["agent"] == "claude:opus:pedro"
    # Annotation-sourced slots.
    assert wp["assignee"] == "pedro"
    assert sorted(wp["tracker_refs"]) == ["JIRA-1", "JIRA-2"]
    assert wp["subtasks"] == {"T001": "done", "T002": "planned"}
    assert wp["review"]["actor"] == "renata"


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    first = b.backfill_runtime_state(feature_dir)
    assert first.seeded_count > 0
    second = b.backfill_runtime_state(feature_dir)
    assert second.action == "skip"
    assert second.seeded_count == 0


def test_seed_ids_are_byte_identical_across_independent_runs(tmp_path: Path) -> None:
    fd_a = build_mission(tmp_path / "a")
    fd_b = build_mission(tmp_path / "b")
    b.backfill_runtime_state(fd_a)
    b.backfill_runtime_state(fd_b)

    def seed_annotation_ids(fd: Path) -> dict[str, str]:
        ids: dict[str, str] = {}
        for a in read_event_stream(fd).annotations:
            if a.actor == b.BACKFILL_ACTOR:
                key = next(iter(a.delta.to_dict().keys()))
                ids[key] = a.event_id
        return ids

    assert seed_annotation_ids(fd_a) == seed_annotation_ids(fd_b)
    # And the id is exactly deterministic_ulid over (mission_id|wp|field).
    assert b._seed_id(b._mission_id(fd_a), "WP01", "subtasks") == seed_annotation_ids(fd_a)["subtasks"]


def test_subtask_mark_at_clamps_before_existing_history(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    subtask_seeds = [a for a in read_event_stream(feature_dir).annotations if a.delta.subtasks]
    assert subtask_seeds, "expected a subtasks seed annotation"
    for seed in subtask_seeds:
        assert (seed.at, seed.event_id) < (
            CLAIMED_AT,
            "01AAAAAAAAAAAAAAAAAAAAAAA1",
        )


def test_never_claimed_wp_skips_runtime_seed(tmp_path: Path) -> None:
    # No transitions AND no frontmatter claim state at all → genuinely never
    # claimed → no claim anchor (real or synthesized) → runtime seed skipped,
    # warned. (Contrast with test_claim_anchor_synthesized_from_frontmatter_*
    # below: a WP WITH claim state but no event log gets a SYNTHESIZED anchor
    # instead of being skipped — #2848.)
    feature_dir = build_mission(tmp_path, with_transitions=False, with_claim=False)
    result = b.backfill_runtime_state(feature_dir)
    assert result.seeded_count == 0
    assert any("never-claimed" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# #2848 — claim-anchor synthesis for a missing/truncated event log
# ---------------------------------------------------------------------------


def test_claim_anchor_synthesized_from_frontmatter_when_event_log_missing(tmp_path: Path) -> None:
    """Regression for the live-proved defect (debugger-debbie, #2848).

    ``kitty-specs/merge-coord-rollback-transactionality-01KXTM59`` has 5 WPs
    whose frontmatter carries a real claim (``agent="claude"`` + ``shell_pid``)
    but NO ``status.events.jsonl`` at all. Pre-fix, ``_claim_anchors`` found no
    anchor, ``_build_seed_events`` skipped the WP as "never-claimed",
    ``verify_backfill`` returned a VACUOUS ``ok=True, wp_count=0``, and the
    mission flipped to snapshot authority with an EMPTY runtime —
    ``reconstruct_wp_view`` then silently lost the ``agent``/``shell_pid``.

    After the fix: the claim anchor is synthesized from
    ``shell_pid_created_at``, the claim IS seeded, verify is non-vacuous
    (``wp_count > 0``), and the recovered ``agent``/``shell_pid`` round-trip
    through the reduced snapshot and :func:`reconstruct_wp_view`.
    """
    feature_dir = build_mission(tmp_path, with_transitions=False)
    assert not (feature_dir / "status.events.jsonl").exists()

    result = b.backfill_runtime_state(feature_dir)
    assert result.action == "wrote"
    assert result.seeded_count > 0
    assert any("synthesized from frontmatter" in w for w in result.warnings)
    assert not any("never-claimed" in w for w in result.warnings)

    verify = b.verify_backfill(feature_dir)
    assert verify.ok is True
    assert verify.wp_count == 1  # non-vacuous: the pre-fix bug returned wp_count == 0

    snap = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert snap["agent"] == "claude:opus:pedro"
    assert snap["shell_pid"] == 44821

    view = reconstruct_wp_view(feature_dir, "WP01")
    assert view.resolved.agent == "claude:opus:pedro"
    assert view.resolved.shell_pid == "44821"

    # Idempotent: a second run seeds nothing new (deterministic seed ids).
    second = b.backfill_runtime_state(feature_dir)
    assert second.action == "skip"
    assert second.seeded_count == 0


def test_claim_anchor_falls_back_to_mission_created_at(tmp_path: Path) -> None:
    """When ``shell_pid_created_at`` itself is unparseable, fall back to the
    mission's ``meta.json`` ``created_at`` — still deterministic, still real."""
    feature_dir = build_mission(
        tmp_path,
        with_transitions=False,
        shell_pid_created_at="not-a-timestamp",
        meta_created_at="2026-01-01T00:00:00+00:00",
    )
    result = b.backfill_runtime_state(feature_dir)
    assert result.seeded_count > 0
    claim = next(e for e in read_event_stream(feature_dir).transitions if e.wp_id == "WP01")
    assert claim.at == "2026-01-01T00:00:00+00:00"


def test_claim_anchor_unresolvable_without_any_timestamp_stays_never_claimed(tmp_path: Path) -> None:
    """Claim *fields* (``agent``) with NO honest timestamp anywhere (neither a
    parseable ``shell_pid_created_at`` nor a ``meta.json`` ``created_at``) must
    NOT fabricate a time — fail-closed, same as the genuinely never-claimed case."""
    feature_dir = build_mission(tmp_path, with_transitions=False, shell_pid_created_at="not-a-timestamp")
    result = b.backfill_runtime_state(feature_dir)
    assert result.seeded_count == 0
    assert any("never-claimed" in w for w in result.warnings)


def test_malformed_wp_frontmatter_fails_closed(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    wp_file = feature_dir / "tasks" / "WP01-demo.md"
    wp_file.write_text(
        "---\nwork_package_id: WP01\nbroken: [\n---\n\n# WP01\n",
        encoding="utf-8",
    )

    with pytest.raises(b.LegacyRuntimeReadError, match="WP01-demo.md"):
        b.read_legacy_runtime(feature_dir)

    result = b.backfill_runtime_state(feature_dir)
    assert result.action == "error"
    assert "WP01-demo.md" in (result.reason or "")


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    before = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    result = b.backfill_runtime_state(feature_dir, dry_run=True)
    assert result.action == "wrote"
    assert result.seeded_count > 0
    after = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert before == after


def test_equal_at_transition_and_annotation_do_not_clobber(tmp_path: Path) -> None:
    # The claim seed transition and the annotations share the WP's claimed `at`.
    # The reducer's event-kind partition folds annotations AFTER transitions, so
    # neither clobbers the other at equal `at`.
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    wp = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert wp["shell_pid"] == 44821  # transition-sourced slot survived
    assert wp["subtasks"] == {"T001": "done", "T002": "planned"}  # annotation-sourced slot survived


# ---------------------------------------------------------------------------
# T012 — fail-closed verify
# ---------------------------------------------------------------------------


def test_clean_backfill_verifies_ok(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    assert b.verify_backfill(feature_dir).ok is True


def test_fault_injected_value_mismatch_aborts_with_count_match(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    # Corrupt a seed: flip T001 done→planned. Counts still match; value diverges.
    corrupt_seed_value(
        feature_dir,
        field_name="subtasks",
        slot_name="subtasks",
        value={"T001": "planned", "T002": "planned"},
    )
    result = b.verify_backfill(feature_dir)
    assert result.ok is False
    assert any("subtasks mismatch" in m for m in result.mismatches)


def test_later_legitimate_completion_supersedes_immutable_planned_seed(
    tmp_path: Path,
) -> None:
    feature_dir = build_mission(tmp_path)
    tasks_md = feature_dir / "tasks.md"
    tasks_md.write_text(
        "# Tasks\n\n## WP01 Demo\n- [ ] T001 first subtask\n- [ ] T002 second subtask\n",
        encoding="utf-8",
    )
    b.backfill_runtime_state(feature_dir)
    append_annotations_atomic_verified(
        feature_dir,
        [
            b.annotate(
                "WP01",
                WPInnerStateDelta(
                    subtasks={"T001": Lane.DONE, "T002": Lane.DONE}
                ),
                actor="user",
                at="2026-01-02T05:00:00+00:00",
                event_id="01BBBBBBBBBBBBBBBBBBBBBBB2",
            )
        ],
    )
    tasks_md.write_text(
        "# Tasks\n\n## WP01 Demo\n- [x] T001 first subtask\n- [x] T002 second subtask\n",
        encoding="utf-8",
    )

    assert b.verify_backfill(feature_dir).ok is True


def test_changed_checklist_without_later_history_remains_tamper_mismatch(
    tmp_path: Path,
) -> None:
    feature_dir = build_mission(tmp_path)
    tasks_md = feature_dir / "tasks.md"
    tasks_md.write_text(
        "# Tasks\n\n## WP01 Demo\n- [ ] T001 first subtask\n- [ ] T002 second subtask\n",
        encoding="utf-8",
    )
    b.backfill_runtime_state(feature_dir)
    tasks_md.write_text(
        "# Tasks\n\n## WP01 Demo\n- [x] T001 first subtask\n- [x] T002 second subtask\n",
        encoding="utf-8",
    )

    result = b.verify_backfill(feature_dir)
    assert result.ok is False
    assert any("subtasks mismatch" in mismatch for mismatch in result.mismatches)


def test_scalar_value_mismatch_aborts(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    corrupt_seed_value(
        feature_dir,
        field_name="claim",
        slot_name="shell_pid",
        value=999999,
    )
    result = b.verify_backfill(feature_dir)
    assert result.ok is False
    assert any("claim mismatch" in m for m in result.mismatches)


def test_missing_raw_claim_witness_cannot_be_masked_by_expected_event_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-disable proof: the claim witness must not share the builder's denominator.

    A ``_build_seed_events`` that emits annotations but suppresses claim
    transitions used to empty the witness denominator, so ``verify_backfill``
    returned a false green even with every raw claim seed deleted (review cycle
    1, plan IC-02 / C-002). The denominator now comes from
    ``read_legacy_runtime`` plus the independently resolved eligibility
    contract, so suppressing the builder cannot hide the loss.
    """
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    events_path = feature_dir / "status.events.jsonl"
    claim_seed_id = b._seed_id(
        b._mission_id(feature_dir),
        "WP01",
        "claim",
    )

    original_builder = b._build_seed_events

    def suppress_expected_claims(
        *args: object,
        **kwargs: object,
    ) -> tuple[list[StatusEvent], list[object]]:
        _transitions, annotations = original_builder(*args, **kwargs)
        return [], annotations

    monkeypatch.setattr(b, "_build_seed_events", suppress_expected_claims)

    # Control: the mutation alone must NOT make verify fail. Any red below is
    # therefore caused by the deleted claim seed, not by the monkeypatch.
    assert b.verify_backfill(feature_dir).ok is True

    rows = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    retained = [row for row in rows if row["event_id"] != claim_seed_id]
    assert len(retained) == len(rows) - 1
    # Annotation seeds survive, so the reduced snapshot still carries runtime
    # state and the coarse count-parity guard stays silent — only the
    # independent per-slot witness can catch this.
    surviving_migration_annotations = [
        row
        for row in retained
        if "delta" in row and row.get("actor") == b.BACKFILL_ACTOR
    ]
    assert surviving_migration_annotations
    events_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in retained) + "\n",
        encoding="utf-8",
    )
    assert b._has_snapshot_runtime(
        materialize_snapshot(feature_dir).work_packages["WP01"]
    )

    result = b.verify_backfill(feature_dir)

    assert result.ok is False
    missing = [
        mismatch
        for mismatch in result.mismatches
        if "raw claim-slot witness missing" in mismatch
    ]
    # Every non-null legacy claim slot is reported, not just the first.
    assert len(missing) == len(b._CLAIM_SLOTS)
    for slot in b._CLAIM_SLOTS:
        assert any(f"missing for {slot}" in mismatch for mismatch in missing)


def test_never_claimed_wp_absent_from_snapshot_warns_not_fails(tmp_path: Path) -> None:
    """Defect 1 (spec Edge Case, WP03 corpus): a never-claimed WP warns, not fails.

    WP02 carries evictable frontmatter runtime state but has no transitions, so it
    has no claim anchor: ``_build_seed_events`` correctly SKIPS its seeds ("no claim
    anchor — runtime seed skipped"), and ``verify_backfill`` must MIRROR that skip —
    an anchor-less WP is never a count mismatch. (The pre-fix code counted it and
    hard-failed 7 real dogfood missions, blocking the whole cutover.)"""
    feature_dir = build_mission(tmp_path)
    (feature_dir / "tasks" / "WP02-extra.md").write_text(
        "---\nwork_package_id: WP02\ntitle: Extra\nagent: ghost:model:profile\n---\n\n# WP02 body\n",
        encoding="utf-8",
    )
    b.backfill_runtime_state(feature_dir)
    result = b.verify_backfill(feature_dir)
    assert result.ok is True
    assert not any("WP02" in m for m in result.mismatches)


def test_phantom_snapshot_only_wp_with_no_wp_file_still_aborts(tmp_path: Path) -> None:
    """Fail-closed preserved: a snapshot WP with NO legacy WP row (phantom/injected).

    A claim seed for WP99 (which has no WP file / no legacy row at all) folds a
    ``shell_pid`` into the snapshot. Unlike an already-migrated WP whose file exists
    but whose runtime is now event-sourced (tolerated — Defect 3), a phantom WP with
    no file is an injected/corrupt entry and MUST still abort fail-closed."""
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id="01BBBBBBBBBBBBBBBBBBBBBBB9",
                mission_slug=feature_dir.name,
                wp_id="WP99",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at=CLAIMED_AT,
                actor="attacker",
                force=True,
                execution_mode="worktree",
                policy_metadata={"shell_pid": 12321, "agent": "ghost"},
            )
        ],
    )
    result = b.verify_backfill(feature_dir)
    assert result.ok is False
    assert any("phantom" in m for m in result.mismatches)


def test_verify_runs_pre_strip_inverting_order_is_caught(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    # Correct order verifies ok BEFORE any strip.
    assert b.verify_backfill(feature_dir).ok is True
    # Inverting the order (strip → verify) is caught fail-closed, not a false green.
    strip_mutable_fields(feature_dir)
    with pytest.raises(b.MigrationOrderingError):
        b.verify_backfill(feature_dir)


def test_unreadable_event_log_is_fail_closed(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    (feature_dir / "status.events.jsonl").write_text("{ not valid json", encoding="utf-8")
    result = b.verify_backfill(feature_dir)
    assert result.ok is False


def test_run_backfill_and_verify_raises_on_mismatch(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    corrupt_seed_value(
        feature_dir,
        field_name="claim",
        slot_name="agent",
        value="tampered",
    )
    with pytest.raises(b.BackfillVerificationError):
        b.run_backfill_and_verify(feature_dir)


def test_empty_mission_verifies_ok(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "099-empty"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"mission_id": "X", "mission_slug": "099-empty"}', encoding="utf-8")
    assert b.verify_backfill(feature_dir).ok is True


# ---------------------------------------------------------------------------
# T013 — zero-reader verification for history[] / progress
# ---------------------------------------------------------------------------


def test_progress_has_zero_live_readers_in_src() -> None:
    assert b.find_field_readers(SRC_ROOT, "progress") == []


def test_history_only_touched_by_known_writer_seams() -> None:
    # After excluding the WP07/T028-owned writer seams, history has no consumer.
    remaining = b.find_field_readers(SRC_ROOT, "history", exclude_basenames=b.HISTORY_WRITER_SEAMS)
    assert remaining == [], remaining
    # The exclusion is real (non-vacuous): the writer seams DO still touch history
    # (they are WP07/T028's to delete — this WP proves, it does not delete).
    unfiltered = b.find_field_readers(SRC_ROOT, "history")
    assert unfiltered, "expected the history writer seams to still exist pre-WP07"


def test_assert_zero_readers_passes_for_real_src() -> None:
    # Uses the default HISTORY_WRITER_SEAMS exclusion → both fields prove clean.
    b.assert_zero_readers(SRC_ROOT)


def test_zero_reader_check_is_non_vacuous(tmp_path: Path) -> None:
    stub = tmp_path / "src_stub"
    (stub / "pkg").mkdir(parents=True)
    (stub / "pkg" / "reader.py").write_text(
        "def read(meta):\n    return meta.get('progress')\n", encoding="utf-8"
    )
    assert b.find_field_readers(stub, "progress")
    with pytest.raises(AssertionError):
        b.assert_zero_readers(stub, fields=("progress",))


# ---------------------------------------------------------------------------
# T014 — honesty precondition assertions
# ---------------------------------------------------------------------------


def test_precondition_snapshot_carries_no_subtask_completion_time(tmp_path: Path) -> None:
    # "No data loss" holds only because no consumer reads subtask-completion time.
    # Prove the precondition: the reduced snapshot subtasks slot is a bare
    # id→status map — there is no completion-time field for anyone to read.
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    subtasks = materialize_snapshot(feature_dir).work_packages["WP01"]["subtasks"]
    assert set(subtasks.values()) <= {"done", "planned"}
    for value in subtasks.values():
        assert isinstance(value, str)  # a status string, never a {status, at} dict


def test_precondition_no_reliance_on_seed_ulid_chronology(tmp_path: Path) -> None:
    # Reversing the append order of the seed annotations must not change the
    # reduced snapshot — proving nothing relies on seed-ULID chronological order.
    fd_a = build_mission(tmp_path / "a")
    fd_b = build_mission(tmp_path / "b")

    b.backfill_runtime_state(fd_a)

    # Re-seed fd_b manually with the SAME events in reverse order.
    legacy = b.read_legacy_runtime(fd_b)
    anchors = b._claim_anchors(fd_b)
    transitions, annotations = b._build_seed_events(fd_b, fd_b, legacy, anchors, [])
    from specify_cli.status.store import append_events_atomic_verified

    append_events_atomic_verified(fd_b, transitions)
    append_annotations_atomic_verified(fd_b, list(reversed(annotations)))

    snap_a = materialize_snapshot(fd_a).work_packages["WP01"]
    snap_b = materialize_snapshot(fd_b).work_packages["WP01"]
    for slot in ("shell_pid", "agent", "assignee", "tracker_refs", "subtasks", "review"):
        assert snap_a.get(slot) == snap_b.get(slot), slot


# ---------------------------------------------------------------------------
# #2985 — the retroactive claim seed must never move a WP's lane backwards
# ---------------------------------------------------------------------------


def _terminal_only_mission(tmp_path: Path, *, terminal_at: str) -> Path:
    """A finished WP whose log holds ONE ``planned -> done`` and no ``claimed``.

    This is the real-corpus shape behind #2985: a force-jumped (or history-pruned)
    WP. ``_claim_anchors`` has no ``claimed`` event to anchor on and falls back to
    the WP's earliest transition — which for this WP IS its terminal one — so the
    seed collides with the terminal event on ``at`` and the reducer's
    ``(at, event_id)`` tiebreak decides the WP's lane by lexical luck.
    """
    feature_dir = build_mission(tmp_path, with_transitions=False)
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                # Sorts BEFORE the hash-derived seed id on the tiebreak, exactly
                # like the real ULIDs in the corpus (they all begin "01").
                event_id="01TERMINALDONEEVENT0000001",
                mission_slug=feature_dir.name,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.DONE,
                at=terminal_at,
                actor="test-agent",
                force=True,
                execution_mode="direct_repo",
            )
        ],
    )
    return feature_dir


def test_seed_claim_never_rewinds_a_finished_wp(tmp_path: Path) -> None:
    """#2985: backfilling a finished WP leaves its canonical lane at ``done``."""
    terminal_at = "2026-03-04T04:45:39.033459+00:00"
    feature_dir = _terminal_only_mission(tmp_path, terminal_at=terminal_at)

    result = b.backfill_runtime_state(feature_dir)
    assert result.action == "wrote"

    seeds = [e for e in read_event_stream(feature_dir).transitions if e.actor == b.BACKFILL_ACTOR]
    assert seeds, "expected the claim carrier to still be seeded (no data loss)"
    assert all(seed.at < terminal_at for seed in seeds), (
        "the retroactive claim seed must sort strictly before recorded history"
    )
    assert materialize_snapshot(feature_dir).work_packages["WP01"]["lane"] == Lane.DONE


def test_seed_claim_ordering_is_stable_across_reruns(tmp_path: Path) -> None:
    """The shifted anchor is derived from AUTHENTIC history, so it never drifts."""
    feature_dir = _terminal_only_mission(tmp_path, terminal_at="2026-03-04T04:45:39.033459+00:00")
    b.backfill_runtime_state(feature_dir)
    first = [e.to_dict() for e in read_event_stream(feature_dir).transitions]

    second_run = b.backfill_runtime_state(feature_dir)
    assert second_run.action == "skip"
    assert second_run.seeded_count == 0
    assert [e.to_dict() for e in read_event_stream(feature_dir).transitions] == first
    assert b.verify_backfill(feature_dir).ok is True


@pytest.mark.parametrize(
    ("anchor", "earliest", "expected"),
    [
        # Anchor genuinely predates recorded history — left verbatim.
        ("2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        # Collision — shifted one microsecond earlier so the fold order is decided.
        ("2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00", "2026-01-01T23:59:59.999999+00:00"),
        # Anchor AFTER recorded history — also pinned before it.
        ("2026-01-03T00:00:00+00:00", "2026-01-02T00:00:00+00:00", "2026-01-01T23:59:59.999999+00:00"),
        # No recorded history to order against — anchor kept verbatim.
        ("2026-01-02T00:00:00+00:00", None, "2026-01-02T00:00:00+00:00"),
        # Unparseable history timestamp — never raise, keep the anchor.
        ("2026-01-02T00:00:00+00:00", "not-a-timestamp", "2026-01-02T00:00:00+00:00"),
    ],
)
def test_retro_claim_at_pins_the_seed_before_history(
    anchor: str, earliest: str | None, expected: str
) -> None:
    assert b._retro_claim_at(anchor, earliest) == expected


def test_instant_before_returns_none_for_an_unparseable_timestamp() -> None:
    assert b._instant_before("not-a-timestamp") is None
    assert b._instant_before("2026-01-02T00:00:00Z") == "2026-01-01T23:59:59.999999+00:00"


# ---------------------------------------------------------------------------
# #2985 corroborating red — accept stays event-count neutral
# ---------------------------------------------------------------------------


def _mission_with_modern_claim(tmp_path: Path, *, policy_metadata: dict[str, object]) -> Path:
    """A mission whose AUTHENTIC ``planned -> claimed`` already carries a sidecar.

    ``policy_metadata`` on the claim transition is the modern write path
    (``reducer._claim_state``, FR-004) — the runtime slots it names are already
    in the canonical model, so the migration has nothing left to migrate for them.
    """
    feature_dir = build_mission(tmp_path, with_transitions=False)
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id="01AUTHENTICMODERNCLAIM0001",
                mission_slug=feature_dir.name,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at=CLAIMED_AT,
                actor="test-agent",
                force=False,
                execution_mode="worktree",
                policy_metadata=dict(policy_metadata),
            )
        ],
    )
    return feature_dir


def test_no_claim_carrier_when_authentic_history_already_carries_the_slots(
    tmp_path: Path,
) -> None:
    """Nothing left to migrate → no lane-shaped carrier is minted at all."""
    feature_dir = _mission_with_modern_claim(
        tmp_path,
        policy_metadata={
            "shell_pid": 44821,
            "shell_pid_created_at": "1784458183.44",
            "agent": "claude:opus:pedro",
        },
    )

    b.backfill_runtime_state(feature_dir)

    claim_seeds = [
        e
        for e in read_event_stream(feature_dir).transitions
        if e.actor == b.BACKFILL_ACTOR and e.to_lane == Lane.CLAIMED
    ]
    assert claim_seeds == [], "a fully-migrated claim must not be re-seeded as a transition"
    assert b.verify_backfill(feature_dir).ok is True


def test_claim_carrier_seeds_only_the_slots_still_missing(tmp_path: Path) -> None:
    """Partial coverage still migrates the remainder — no silent data loss."""
    feature_dir = _mission_with_modern_claim(
        tmp_path, policy_metadata={"agent": "claude:opus:pedro"}
    )

    b.backfill_runtime_state(feature_dir)

    claim_seeds = [
        e
        for e in read_event_stream(feature_dir).transitions
        if e.actor == b.BACKFILL_ACTOR and e.to_lane == Lane.CLAIMED
    ]
    assert [e.policy_metadata for e in claim_seeds] == [
        {"shell_pid": 44821, "shell_pid_created_at": "1784458183.44"}
    ], "exactly one carrier, seeding only the two slots authentic history lacked"
    snapshot = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert snapshot["shell_pid"] == 44821
    assert snapshot["agent"] == "claude:opus:pedro"


def test_unmigrated_claim_slots_drops_only_already_archived_values() -> None:
    """The helper suppresses on value equality, never on bare slot presence."""
    legacy = {
        "shell_pid": 44821,
        "shell_pid_created_at": "1784458183.44",
        "agent": "claude:opus:pedro",
    }
    runtime = b.LegacyWPRuntime(wp_id="WP01", **legacy)  # type: ignore[arg-type]

    assert b._unmigrated_claim_slots(runtime, {}) == legacy
    assert b._unmigrated_claim_slots(
        runtime, {"agent": "claude:opus:pedro"}
    ) == {
        "shell_pid": 44821,
        "shell_pid_created_at": "1784458183.44",
    }
    assert b._unmigrated_claim_slots(runtime, dict(legacy)) == {}
    # A DIVERGENT authentic value archives nothing, so the slot is still owed.
    assert b._unmigrated_claim_slots(runtime, {"agent": "codex:DIVERGENT"}) == legacy


# ---------------------------------------------------------------------------
# Ordering-seam encoding sensitivity (#2990 follow-up)
#
# ``reducer.reduce`` sorts on the RAW ``(at, event_id)`` string tuple, so the
# seed-ordering helpers compare ``at`` values lexically. Re-encoding a
# ``Z``-suffixed stamp as ``+00:00`` silently breaks that comparison because
# ``'.'`` (0x2E) sorts below ``'Z'`` (0x5A) — and only for WHOLE-SECOND stamps,
# which is why fixtures pinned to ``+00:00`` never saw it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "2025-11-02T16:58:36Z",
        "2025-11-02T16:58:36.123456Z",
        "2025-11-02T16:58:36+00:00",
        "2025-11-02T16:58:36.123456+00:00",
    ],
)
@pytest.mark.parametrize("direction", ["before", "after"])
def test_shift_ordering_timestamp_holds_its_lexical_postcondition(
    raw: str,
    direction: str,
) -> None:
    """The shifted stamp must compare correctly against its own input.

    That is the whole point of the helper: ``_wp_history_floor`` and
    ``_compatibility_repair_at`` both assert ``(shifted, "") < / > (at, id)``
    against the reducer's raw string keys. A shift that re-encodes the
    designator breaks the comparison without changing the instant.
    """
    shifted = b._shift_ordering_timestamp(raw, wp_id="WP01", direction=direction)  # type: ignore[arg-type]

    if direction == "before":
        assert shifted < raw, f"{shifted!r} must sort below {raw!r}"
    else:
        assert shifted > raw, f"{shifted!r} must sort above {raw!r}"


@pytest.mark.parametrize(
    ("raw", "suffix"),
    [
        ("2025-11-02T16:58:36Z", "Z"),
        ("2025-11-02T16:58:36.123456Z", "Z"),
        ("2025-11-02T16:58:36+00:00", "+00:00"),
        ("2025-11-02T16:58:36.123456+00:00", "+00:00"),
    ],
)
@pytest.mark.parametrize("direction", ["before", "after"])
def test_shift_ordering_timestamp_preserves_the_input_designator(
    raw: str,
    suffix: str,
    direction: str,
) -> None:
    """Encoding is preserved, so the lexical guard stays meaningful."""
    shifted = b._shift_ordering_timestamp(raw, wp_id="WP01", direction=direction)  # type: ignore[arg-type]

    assert shifted.endswith(suffix), f"{shifted!r} must keep the {suffix!r} designator"


@pytest.mark.parametrize("at_encoding", AT_ENCODINGS)
def test_seed_floor_precedes_history_under_either_at_encoding(
    tmp_path: Path,
    at_encoding: str,
) -> None:
    """T-P4: the history-floor seam must survive a ``Z``-encoded corpus."""
    feature_dir = build_mission(tmp_path, at_encoding=at_encoding)
    stream_before = read_event_stream(feature_dir)
    legitimate_keys = [
        (event.at, event.event_id)
        for event in (*stream_before.transitions, *stream_before.annotations)
    ]

    result = b.backfill_runtime_state(feature_dir)

    assert result.action == "wrote"
    seeds = [
        event
        for event in (*read_event_stream(feature_dir).transitions, *read_event_stream(feature_dir).annotations)
        if event.actor == b.BACKFILL_ACTOR
    ]
    assert seeds
    assert all(
        (seed.at, seed.event_id) < history_key
        for seed in seeds
        for history_key in legitimate_keys
    )
    assert b.verify_backfill(feature_dir).ok


@pytest.mark.parametrize("at_encoding", AT_ENCODINGS)
def test_compatibility_repair_lands_after_history_under_either_at_encoding(
    tmp_path: Path,
    at_encoding: str,
) -> None:
    """T-P4: the append-only repair seam must survive a ``Z``-encoded corpus.

    ``_compatibility_repair_at`` shifts the LATEST history stamp forward; on a
    whole-second ``Z`` stamp the re-encoded result sorts *below* its own input,
    so the fail-closed guard fires and the whole cutover aborts with
    ``MigrationOrderingError``.
    """
    feature_dir = build_mission(tmp_path, at_encoding=at_encoding)
    events_path = feature_dir / "status.events.jsonl"
    rows = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["policy_metadata"] = {
        "shell_pid": 991,
        "shell_pid_created_at": "later-claim-time",
        "agent": "later-legitimate-agent",
    }
    events_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id=b._seed_id(b._mission_id(feature_dir), "WP01", "claim"),
                mission_slug=feature_dir.name,
                mission_id=b._mission_id(feature_dir),
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at=encode_at(IN_PROGRESS_AT, at_encoding),
                actor=b.BACKFILL_ACTOR,
                force=False,
                execution_mode="worktree",
                policy_metadata={
                    "shell_pid": 44821,
                    "shell_pid_created_at": "1784458183.44",
                    "agent": "claude:opus:pedro",
                },
            )
        ],
    )

    assert b.backfill_runtime_state(feature_dir).seeded_count > 0

    stream = read_event_stream(feature_dir)
    repairs = [
        event
        for event in (*stream.transitions, *stream.annotations)
        if event.actor == b.COMPATIBILITY_REPAIR_ACTOR
    ]
    assert repairs
    pre_repair_keys = [
        (event.at, event.event_id)
        for event in (*stream.transitions, *stream.annotations)
        if event.actor != b.COMPATIBILITY_REPAIR_ACTOR
    ]
    assert all(
        (repair.at, repair.event_id) > key
        for repair in repairs
        for key in pre_repair_keys
    )
    assert b.verify_backfill(feature_dir).ok


# ---------------------------------------------------------------------------
# C-002 / contract invariant 5: suppression is keyed on the VALUE, not on mere
# slot presence. Authentic history holding a *different* value for a claim slot
# does not discharge the archival obligation — the legacy value would then be
# recorded nowhere, and the strip step later destroys the frontmatter it came
# from.
# ---------------------------------------------------------------------------


def test_claim_carrier_still_archives_a_slot_whose_authentic_value_diverges(
    tmp_path: Path,
) -> None:
    """A divergent authentic value must NOT suppress the legacy carrier.

    ``spec.md`` C-002 bars seed suppression that "discards claim-borne runtime
    slots", and ``contracts/birth-cutover-ordering.md`` invariant 5 requires each
    non-null legacy claim value to be *present in the raw seed evidence*. When
    authentic history carries ``agent='codex:DIVERGENT'`` and legacy frontmatter
    carries ``agent='claude:opus:pedro'``, presence-keyed suppression archives
    the legacy value nowhere at all.

    Invariant 5's second clause already anticipates the later writer winning the
    *reduced* fold, so archiving the legacy value in the raw log costs nothing:
    the reduced snapshot must still show the divergent authentic value.
    """
    feature_dir = _mission_with_modern_claim(
        tmp_path,
        policy_metadata={
            "shell_pid": 44821,
            "shell_pid_created_at": "1784458183.44",
            "agent": "codex:DIVERGENT",
        },
    )

    b.backfill_runtime_state(feature_dir)

    claim_seeds = [
        e
        for e in read_event_stream(feature_dir).transitions
        if e.actor == b.BACKFILL_ACTOR and e.to_lane == Lane.CLAIMED
    ]
    assert [e.policy_metadata for e in claim_seeds] == [
        {"agent": "claude:opus:pedro"}
    ], "the divergent legacy 'agent' must be archived in the raw seed evidence"
    # The later legitimate writer still owns the reduced slot (invariant 5's
    # second clause) — archival must not resurrect the legacy value.
    snapshot = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert snapshot["agent"] == "codex:DIVERGENT"
    assert snapshot["shell_pid"] == 44821
    assert b.verify_backfill(feature_dir).ok is True


def test_snapshot_claim_slots_reports_authentic_values_not_bare_presence(
    tmp_path: Path,
) -> None:
    """The probe must expose values, or callers cannot compare against legacy."""
    feature_dir = _mission_with_modern_claim(
        tmp_path, policy_metadata={"agent": "codex:DIVERGENT"}
    )

    present = b._snapshot_claim_slots(read_event_stream(feature_dir))

    assert present["WP01"] == {"agent": "codex:DIVERGENT"}


def _delete_claim_seed_and_strip_claim_frontmatter(feature_dir: Path) -> None:
    """Scenario E: remove BOTH halves of the claim-slot evidence for WP01."""
    from specify_cli.frontmatter import FrontmatterManager

    seed_id = b._seed_id(b._mission_id(feature_dir), "WP01", "claim")
    events_path = feature_dir / "status.events.jsonl"
    rows = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    kept = [row for row in rows if row.get("event_id") != seed_id]
    assert len(kept) == len(rows) - 1, "precondition: the claim seed must exist"
    events_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in kept) + "\n",
        encoding="utf-8",
    )

    wp_path = feature_dir / "tasks" / "WP01-demo.md"
    manager = FrontmatterManager()
    frontmatter, body = manager.read(wp_path)
    for key in b._CLAIM_SLOTS:
        assert key in frontmatter, f"precondition: {key} must be present pre-strip"
        del frontmatter[key]
    manager.write(wp_path, frontmatter, body)


def test_scenario_e_currently_returns_a_documented_silent_green(
    tmp_path: Path,
) -> None:
    """Characterise the hole exactly, so its blast radius cannot widen unseen.

    This executable characterization pins the *actual* behavior so a change
    that makes the hole wider (for example, new slots becoming silently
    droppable) still reds. The removed strict xfail described behavior that a
    read-only verifier cannot distinguish without an independent witness.
    """
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)

    _delete_claim_seed_and_strip_claim_frontmatter(feature_dir)

    result = b.verify_backfill(feature_dir)
    assert (result.ok, result.mismatches) == (True, ()), (
        "the documented silent-green hole changed shape — re-derive P7"
    )
    # Non-vacuity: deleting ONLY the seed row (leaving the frontmatter intact)
    # is still caught fail-closed, so the hole is specifically the *collusion*
    # of the two deletions, not a blanket blindness to a missing seed.
    intact = build_mission(tmp_path / "intact")
    b.backfill_runtime_state(intact)
    seed_id = b._seed_id(b._mission_id(intact), "WP01", "claim")
    events_path = intact / "status.events.jsonl"
    kept = [
        line
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("event_id") != seed_id
    ]
    events_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert b.verify_backfill(intact).ok is False
