"""Tests for the WP05 profile-invocation lifecycle pairing surface (#843).

Covers:
- ProfileInvocationRecord serialisation round-trip
- Pair matching for started+completed and started+failed
- Orphan started observability via the doctor helper
- Append-only invariant (a second started for the same id does NOT silently
  overwrite the first)
- canonical_action_id matches the mission_step::action format produced at
  issuance and is propagated verbatim to the partner record
"""

from __future__ import annotations

from kernel.clock import UTC, datetime as _dt_datetime, timedelta as _dt_timedelta
from pathlib import Path

import pytest

from specify_cli.invocation.lifecycle import (
    LIFECYCLE_LOG_RELATIVE_PATH,
    append_lifecycle_record,
    compute_pairing_rate,
    doctor_orphan_report,
    find_latest_unpaired_started,
    find_orphans,
    group_by_action,
    lifecycle_log_path,
    lifecycle_records_dir,
    make_canonical_action_id,
    read_lifecycle_records,
    write_paired_completion,
    write_started,
)
from specify_cli.invocation.record import ProfileInvocationRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _at(seconds: int = 0) -> _dt_datetime:
    """Build a deterministic UTC timestamp offset by ``seconds``."""
    base = _dt_datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC)
    return base + _dt_timedelta(seconds=seconds)


def _started(
    *,
    canonical: str = "implement::do",
    agent: str = "claude",
    mission: str = "01HMISSION0000000000000000",
    wp_id: str | None = "WP01",
    seconds: int = 0,
) -> ProfileInvocationRecord:
    return ProfileInvocationRecord(
        canonical_action_id=canonical,
        phase="started",
        at=_at(seconds),
        agent=agent,
        mission_id=mission,
        wp_id=wp_id,
    )


# ---------------------------------------------------------------------------
# Record shape & serialisation
# ---------------------------------------------------------------------------


class TestProfileInvocationRecordShape:
    def test_to_dict_round_trip_preserves_fields(self) -> None:
        record = ProfileInvocationRecord(
            canonical_action_id="implement::do",
            phase="started",
            at=_at(),
            agent="claude",
            mission_id="01HMISSION0000000000000000",
            wp_id="WP01",
        )
        payload = record.to_dict()
        # Mandatory keys per data-model.md §4
        assert payload["canonical_action_id"] == "implement::do"
        assert payload["phase"] == "started"
        assert payload["agent"] == "claude"
        assert payload["mission_id"] == "01HMISSION0000000000000000"
        assert payload["wp_id"] == "WP01"
        assert payload["reason"] is None
        # Round-trip via from_dict reconstructs the same value
        rebuilt = ProfileInvocationRecord.from_dict(payload)
        assert rebuilt == record

    def test_from_dict_rejects_unknown_phase(self) -> None:
        with pytest.raises(ValueError):
            ProfileInvocationRecord.from_dict(
                {
                    "canonical_action_id": "x::y",
                    "phase": "bogus",
                    "at": _at().isoformat(),
                    "agent": "claude",
                    "mission_id": "m",
                    "wp_id": None,
                    "reason": None,
                }
            )

    def test_to_json_line_uses_sorted_keys(self) -> None:
        record = _started()
        line = record.to_json_line()
        # Sorted keys give us 'agent' before 'at' before 'canonical_action_id'.
        assert line.index('"agent"') < line.index('"canonical_action_id"')


# ---------------------------------------------------------------------------
# canonical_action_id
# ---------------------------------------------------------------------------


class TestCanonicalActionId:
    def test_canonical_action_id_matches_issued_format(self) -> None:
        cid = make_canonical_action_id("implement", "do")
        assert cid == "implement::do"

    def test_canonical_action_id_rejects_empty_step(self) -> None:
        with pytest.raises(ValueError):
            make_canonical_action_id("", "do")

    def test_canonical_action_id_rejects_empty_action(self) -> None:
        with pytest.raises(ValueError):
            make_canonical_action_id("implement", "")

    def test_canonical_action_id_trims_whitespace(self) -> None:
        assert make_canonical_action_id("  implement  ", " do ") == "implement::do"


# ---------------------------------------------------------------------------
# Append/read & pairing
# ---------------------------------------------------------------------------


class TestStartedThenCompletedPairs:
    def test_started_then_completed_produces_one_paired_group(
        self, tmp_path: Path
    ) -> None:
        started = write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            wp_id="WP01",
            at=_at(0),
        )
        write_paired_completion(
            tmp_path,
            started=started,
            phase="completed",
            at=_at(5),
        )
        records = read_lifecycle_records(tmp_path)
        groups = group_by_action(records)
        assert len(groups) == 1
        group = groups[0]
        assert group.canonical_action_id == "implement::do"
        assert len(group.started) == 1
        assert len(group.completions) == 1
        assert group.completions[0].phase == "completed"
        # Partner record carries the SAME canonical_action_id (no rewriting).
        assert group.completions[0].canonical_action_id == started.canonical_action_id


class TestStartedThenFailedPairs:
    def test_started_then_failed_records_pair_with_reason(self, tmp_path: Path) -> None:
        started = write_started(
            tmp_path,
            canonical_action_id="review::do",
            agent="claude",
            mission_id="m1",
            wp_id="WP02",
            at=_at(0),
        )
        write_paired_completion(
            tmp_path,
            started=started,
            phase="failed",
            reason="failed",
            at=_at(7),
        )
        records = read_lifecycle_records(tmp_path)
        groups = group_by_action(records)
        assert len(groups) == 1
        completion = groups[0].completions[0]
        assert completion.phase == "failed"
        assert completion.reason == "failed"
        assert completion.canonical_action_id == "review::do"
        assert not groups[0].is_orphan

    def test_write_paired_completion_rejects_started_phase(
        self, tmp_path: Path
    ) -> None:
        started = write_started(
            tmp_path,
            canonical_action_id="x::y",
            agent="claude",
            mission_id="m",
        )
        with pytest.raises(ValueError):
            write_paired_completion(tmp_path, started=started, phase="started")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Orphan observability
# ---------------------------------------------------------------------------


class TestOrphanStartedListed:
    def test_orphan_started_listed_by_doctor_helper(self, tmp_path: Path) -> None:
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            wp_id="WP01",
            at=_at(0),
        )
        report = doctor_orphan_report(tmp_path)
        assert report["orphan_count"] == 1
        orphans = report["orphans"]
        assert isinstance(orphans, list)
        assert orphans[0]["canonical_action_id"] == "implement::do"
        assert orphans[0]["agent"] == "claude"
        assert orphans[0]["mission_id"] == "m1"
        assert orphans[0]["wp_id"] == "WP01"
        assert report["pairing_rate"] == pytest.approx(0.0)

    def test_no_records_means_no_orphans_and_full_pairing(self, tmp_path: Path) -> None:
        report = doctor_orphan_report(tmp_path)
        assert report["orphan_count"] == 0
        assert report["pairing_rate"] == pytest.approx(1.0)
        assert report["total_groups"] == 0

    def test_find_orphans_returns_only_unpaired_groups(self, tmp_path: Path) -> None:
        s1 = write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            at=_at(0),
        )
        write_paired_completion(tmp_path, started=s1, phase="completed", at=_at(1))
        write_started(
            tmp_path,
            canonical_action_id="review::do",
            agent="claude",
            mission_id="m1",
            at=_at(2),
        )
        records = read_lifecycle_records(tmp_path)
        orphans = find_orphans(records)
        assert len(orphans) == 1
        assert orphans[0].canonical_action_id == "review::do"


# ---------------------------------------------------------------------------
# Append-only invariant
# ---------------------------------------------------------------------------


class TestStartedNotOverwrittenBySecondStarted:
    def test_two_starteds_for_same_id_both_persist_and_orphan_visible(
        self, tmp_path: Path
    ) -> None:
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            wp_id="WP01",
            at=_at(0),
        )
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            wp_id="WP01",
            at=_at(5),
        )

        records = read_lifecycle_records(tmp_path)
        # Both lines persist — append-only invariant (FR-012).
        assert len(records) == 2
        assert all(r.phase == "started" for r in records)

        # Both starteds remain visible as orphans (the original was not
        # silently overwritten).
        report = doctor_orphan_report(tmp_path)
        assert report["orphan_count"] == 2

    def test_pair_only_consumes_one_started_per_partner(
        self, tmp_path: Path
    ) -> None:
        # Two starteds, one completed: still one orphan.
        s1 = write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            at=_at(0),
        )
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            at=_at(1),
        )
        write_paired_completion(tmp_path, started=s1, phase="completed", at=_at(2))

        report = doctor_orphan_report(tmp_path)
        assert report["orphan_count"] == 1


# ---------------------------------------------------------------------------
# canonical_action_id propagation
# ---------------------------------------------------------------------------


class TestCanonicalActionIdMatchesIssued:
    def test_partner_canonical_action_id_equals_started(self, tmp_path: Path) -> None:
        canonical = make_canonical_action_id("plan", "do")
        started = write_started(
            tmp_path,
            canonical_action_id=canonical,
            agent="claude",
            mission_id="m1",
            wp_id=None,
            at=_at(0),
        )
        completion = write_paired_completion(
            tmp_path, started=started, phase="completed", at=_at(1)
        )
        # The partner record copies the SAME canonical id verbatim — no
        # rewriting at completion time.
        assert completion.canonical_action_id == started.canonical_action_id == canonical

    def test_lifecycle_log_path_names_the_legacy_log(self, tmp_path: Path) -> None:
        path = lifecycle_log_path(tmp_path)
        assert path == tmp_path / LIFECYCLE_LOG_RELATIVE_PATH


# ---------------------------------------------------------------------------
# find_latest_unpaired_started — used by next_cmd to pair the prior issuance
# ---------------------------------------------------------------------------


class TestFindLatestUnpairedStarted:
    def test_returns_latest_orphan_filtered_by_agent_and_mission(
        self, tmp_path: Path
    ) -> None:
        # An older orphan for a different mission and a newer orphan for
        # the same agent+mission.
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m1",
            at=_at(0),
        )
        newest = write_started(
            tmp_path,
            canonical_action_id="review::do",
            agent="claude",
            mission_id="m1",
            at=_at(10),
        )
        write_started(
            tmp_path,
            canonical_action_id="implement::do",
            agent="claude",
            mission_id="m2",
            at=_at(20),
        )
        records = read_lifecycle_records(tmp_path)
        chosen = find_latest_unpaired_started(
            records,
            agent="claude",
            mission_id="m1",
        )
        assert chosen is not None
        assert chosen.canonical_action_id == newest.canonical_action_id

    def test_returns_none_when_all_paired(self, tmp_path: Path) -> None:
        s1 = write_started(
            tmp_path,
            canonical_action_id="x::y",
            agent="claude",
            mission_id="m",
            at=_at(0),
        )
        write_paired_completion(tmp_path, started=s1, phase="completed", at=_at(1))
        records = read_lifecycle_records(tmp_path)
        assert find_latest_unpaired_started(records) is None


# ---------------------------------------------------------------------------
# pairing rate
# ---------------------------------------------------------------------------


def test_compute_pairing_rate_handles_partial_pairing() -> None:
    # 3 started, 2 completions -> 2/3 paired.
    records = [
        _started(canonical="a::1", seconds=0),
        ProfileInvocationRecord(
            canonical_action_id="a::1",
            phase="completed",
            at=_at(1),
            agent="claude",
            mission_id="01HMISSION0000000000000000",
            wp_id="WP01",
        ),
        _started(canonical="a::2", seconds=2),
        ProfileInvocationRecord(
            canonical_action_id="a::2",
            phase="failed",
            at=_at(3),
            agent="claude",
            mission_id="01HMISSION0000000000000000",
            wp_id="WP01",
            reason="failed",
        ),
        _started(canonical="a::3", seconds=4),
    ]
    rate = compute_pairing_rate(records)
    assert rate == pytest.approx(2 / 3)


def test_append_lifecycle_record_creates_parent_dir(tmp_path: Path) -> None:
    record = _started()
    target = tmp_path / "nested" / "project"
    written = append_lifecycle_record(target, record)
    assert written.parent == lifecycle_records_dir(target)
    assert written.read_text(encoding="utf-8").strip() != ""
    # #7003: the shared legacy log is never created again.
    assert not lifecycle_log_path(target).exists()


def test_read_lifecycle_records_skips_blank_and_corrupt_lines(tmp_path: Path) -> None:
    """Robustness: doctor surface should not crash on malformed legacy history."""
    record = _started()
    log_path = lifecycle_log_path(tmp_path)
    log_path.parent.mkdir(parents=True)
    log_path.write_text(record.to_json_line() + "\n", encoding="utf-8")
    # Append blank and corrupt content to the (read-only) legacy log.
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n")  # blank line
        fh.write("not json\n")  # corrupt
        fh.write('{"missing": "fields"}\n')  # JSON but missing required keys
    records = read_lifecycle_records(tmp_path)
    # Only the well-formed record survives; the bad lines are silently dropped.
    assert len(records) == 1
    assert records[0].canonical_action_id == record.canonical_action_id


def test_doctor_orphan_report_handles_naive_datetimes(tmp_path: Path) -> None:
    """A naive datetime gets formatted as UTC by the doctor surface."""
    naive = _dt_datetime(2026, 4, 28, 12, 0, 0)  # no tzinfo
    record = ProfileInvocationRecord(
        canonical_action_id="x::y",
        phase="started",
        at=naive,
        agent="claude",
        mission_id="m",
    )
    append_lifecycle_record(tmp_path, record)
    report = doctor_orphan_report(tmp_path)
    assert report["orphan_count"] == 1
    orphan_iter = report["orphans"]
    assert isinstance(orphan_iter, list)
    started_at_field = orphan_iter[0]["started_at"]
    assert isinstance(started_at_field, str)
    # naive datetime is stored normalised; the surface emits an ISO string.
    assert "2026-04-28T12:00:00" in started_at_field


# ---------------------------------------------------------------------------
# Cross-mission isolation (regression for #843 follow-up)
# ---------------------------------------------------------------------------


class TestCrossMissionIsolation:
    """Two missions issuing the same ``mission_state::action`` MUST NOT cross-pair.

    Group key includes ``mission_id`` so a started in mission ``m1`` and a
    completion in mission ``m2`` (same canonical_action_id) leave the m1
    started observably orphaned. Without mission-scoped grouping the global
    started/completion counts would balance and hide the orphan.
    """

    def test_same_canonical_id_in_two_missions_does_not_cross_pair(
        self, tmp_path: Path
    ) -> None:
        # Mission m1 issues a started, agent crashes (no completion).
        m1_started = ProfileInvocationRecord(
            canonical_action_id="implement::do",
            phase="started",
            at=_at(0),
            agent="claude",
            mission_id="m1",
            wp_id="WP01",
        )
        # Mission m2 (separate operator session) issues + completes the
        # SAME canonical_action_id string.
        m2_started = ProfileInvocationRecord(
            canonical_action_id="implement::do",
            phase="started",
            at=_at(10),
            agent="claude",
            mission_id="m2",
            wp_id="WP01",
        )
        m2_completed = ProfileInvocationRecord(
            canonical_action_id="implement::do",
            phase="completed",
            at=_at(15),
            agent="claude",
            mission_id="m2",
            wp_id="WP01",
        )
        for r in (m1_started, m2_started, m2_completed):
            append_lifecycle_record(tmp_path, r)

        records = read_lifecycle_records(tmp_path)
        groups = group_by_action(records)
        # Two distinct groups — one per mission_id.
        assert len(groups) == 2
        m1_group = next(g for g in groups if g.mission_id == "m1")
        m2_group = next(g for g in groups if g.mission_id == "m2")
        # m1 has an unpaired started; m2 is fully paired.
        assert m1_group.is_orphan is True
        assert m2_group.is_orphan is False

        orphans = find_orphans(records)
        assert len(orphans) == 1
        assert orphans[0].mission_id == "m1"

        # Doctor surface lists the m1 orphan and never silently absorbs it
        # into m2's completion.
        report = doctor_orphan_report(tmp_path)
        assert report["orphan_count"] == 1
        orphan_list = report["orphans"]
        assert isinstance(orphan_list, list)
        assert orphan_list[0]["mission_id"] == "m1"

    def test_find_latest_unpaired_started_filters_by_mission(
        self, tmp_path: Path
    ) -> None:
        for r in (
            ProfileInvocationRecord(
                canonical_action_id="implement::do",
                phase="started",
                at=_at(0),
                agent="claude",
                mission_id="m1",
            ),
            ProfileInvocationRecord(
                canonical_action_id="implement::do",
                phase="started",
                at=_at(10),
                agent="claude",
                mission_id="m2",
            ),
            ProfileInvocationRecord(
                canonical_action_id="implement::do",
                phase="completed",
                at=_at(15),
                agent="claude",
                mission_id="m2",
            ),
        ):
            append_lifecycle_record(tmp_path, r)

        records = read_lifecycle_records(tmp_path)
        # Asking for m1's orphan returns the m1 started (m2 is paired).
        m1_orphan = find_latest_unpaired_started(records, mission_id="m1")
        assert m1_orphan is not None
        assert m1_orphan.mission_id == "m1"
        # m2 has no orphan.
        m2_orphan = find_latest_unpaired_started(records, mission_id="m2")
        assert m2_orphan is None
