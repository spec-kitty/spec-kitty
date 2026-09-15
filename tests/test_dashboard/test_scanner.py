import json
from pathlib import Path

import pytest

from specify_cli.dashboard import scanner
from specify_cli.dashboard.charter_path import resolve_project_charter_path
from specify_cli.status.models import (
    NON_DISPLAY_LANES,
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_annotations_atomic_verified, append_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _set_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"TEST{wp_id}{lane.upper()}0000000000000000"[:26],
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-03-31T09:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    materialize(feature_dir)


def _set_wp_subtasks(feature_dir: Path, wp_id: str, subtasks: dict[str, Lane]) -> None:
    """Record subtask completion in the event log — the snapshot ``subtasks`` slot
    is the SOLE dashboard authority since #2816 IC-10 (FR-016 / SC-010)."""
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=("01KXANN" + wp_id).ljust(26, "0")[:26],
                wp_id=wp_id,
                at="2026-03-31T09:01:00+00:00",
                actor="test",
                delta=WPInnerStateDelta(subtasks=subtasks),
            )
        ],
    )
    materialize(feature_dir)


def _create_feature_at(feature_dir: Path, *, lane: str = "planned") -> Path:
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    prompt = """---
work_package_id: WP01
subtasks: ["T1"]
agent: codex
---
# Work Package Prompt: Demo

Body
    """
    (feature_dir / "tasks" / "WP01-demo.md").write_text(prompt, encoding="utf-8")
    _set_wp_lane(feature_dir, "WP01", lane)
    return feature_dir


def _create_feature(tmp_path: Path, slug: str = "001-demo-feature", *, lane: str = "planned") -> Path:
    return _create_feature_at(tmp_path / "kitty-specs" / slug, lane=lane)


def test_wp_cards_report_subtask_progress(tmp_path):
    """#2816 IC-10 (FR-016 / SC-010): WP cards carry done/total from the reduced
    event-log ``subtasks`` snapshot slot — the SOLE subtask authority. The card
    ignores the body's checkbox bytes entirely (the D-13 incoherence is gone)."""
    feature_dir = _create_feature(tmp_path)
    (feature_dir / "tasks" / "WP01-demo.md").write_text(
        """---
work_package_id: WP01
subtasks: ["T001", "T002", "T003"]
agent: codex
---
# Work Package Prompt: Demo

- [ ] T001 Build the thing
- [ ] T002 Verify the thing
- [ ] T003 Document the thing
- [ ] swift test
""",
        encoding="utf-8",
    )
    # The snapshot — not the (all-unchecked) body checkboxes — drives the badge.
    _set_wp_subtasks(
        feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.PLANNED, "T003": Lane.DONE}
    )

    lanes = scanner.scan_feature_kanban(tmp_path, feature_dir.name)
    task = next(t for lane in lanes.values() for t in lane)

    assert task["subtasks_done"] == 2
    assert task["subtasks_total"] == 3
    assert task["subtasks"] == ["T001", "T002", "T003"]  # frontmatter untouched


def test_wp_progress_ignores_tasks_md_checkboxes(tmp_path):
    """#2816 IC-10: the badge reads the snapshot only — canonical ``- [ ] T###``
    rows in tasks.md are noise (a raw checkbox edit cannot move the badge)."""
    feature_dir = _create_feature(tmp_path)
    # Fully-CHECKED tasks.md rows that would once have read as done=3 — now inert.
    (feature_dir / "tasks.md").write_text(
        """# Tasks

## WP01 — Demo (depends: none)
- [x] T001 Build the thing (WP01)
- [x] T002 Wire the thing (WP01)
- [x] T003 Verify the thing (WP01)
""",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01-demo.md").write_text(
        """---
work_package_id: WP01
subtasks: ["T001", "T002", "T003"]
agent: codex
---
# Work Package Prompt: Demo
""",
        encoding="utf-8",
    )
    # The snapshot records only 2 of 3 done; the fully-checked tasks.md is ignored.
    _set_wp_subtasks(
        feature_dir, "WP01", {"T001": Lane.DONE, "T002": Lane.DONE, "T003": Lane.PLANNED}
    )

    lanes = scanner.scan_feature_kanban(tmp_path, feature_dir.name)
    task = next(t for lane in lanes.values() for t in lane)

    assert task["subtasks_done"] == 2
    assert task["subtasks_total"] == 3


def test_wp_without_snapshot_subtasks_reports_authored_total(tmp_path):
    """An absent completion slot leaves every authored roster item unfinished."""
    feature_dir = _create_feature(tmp_path)  # no subtasks annotation seeded

    lanes = scanner.scan_feature_kanban(tmp_path, feature_dir.name)
    task = next(t for lane in lanes.values() for t in lane)

    assert task["subtasks_total"] == 1
    assert task["subtasks_done"] == 0
    assert task["subtasks"] == ["T1"]


def test_scan_all_features_detects_feature(tmp_path):
    feature_dir = _create_feature(tmp_path)
    features = scanner.scan_all_features(tmp_path)
    assert features, "Expected at least one feature"
    assert features[0]["id"] == feature_dir.name
    assert features[0]["artifacts"]["spec"]


def test_scan_all_features_reports_discarded_from_meta(tmp_path):
    """#704: a discarded mission still scans, but carries the discarded status."""
    feature_dir = _create_feature(tmp_path)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "slug": feature_dir.name,
                "mission_slug": feature_dir.name,
                "discarded_at": "2026-09-13T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert [f["mission_status"] for f in features] == ["discarded"]


def test_scan_all_features_tolerates_unreadable_event_log(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-demo-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (tasks_dir / "WP01-demo.md").write_text(
        """---
work_package_id: WP01
---
# Work Package Prompt: Demo
""",
        encoding="utf-8",
    )
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "TESTBAD00000000000000000000",
                "mission_slug": feature_dir.name,
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "doing",
                "at": "2026-04-05T12:00:00+00:00",
                "actor": "test-agent",
                "force": False,
                "execution_mode": "worktree",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert len(features) == 1
    assert features[0]["id"] == feature_dir.name
    assert features[0]["kanban_stats"]["total"] == 0
    assert "Event log unreadable" in features[0]["kanban_stats"]["error"]


def test_scan_all_features_builds_switcher_display_name(tmp_path):
    feature_dir = _create_feature(tmp_path)
    (feature_dir / "meta.json").write_text(
        json.dumps({"friendly_name": "Demo Feature"}),
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert features[0]["name"] == "Demo Feature"
    assert features[0]["display_name"] == "001 - Demo Feature"


def test_scan_all_features_display_name_avoids_duplicate_prefix(tmp_path):
    feature_dir = _create_feature(tmp_path)
    (feature_dir / "meta.json").write_text(
        json.dumps({"friendly_name": "001 - Demo Feature"}),
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert features[0]["display_name"] == "001 - Demo Feature"


def test_scan_all_features_orders_selector_rows_by_recency(tmp_path):
    older = _create_feature(tmp_path, "aaa-older-mission")
    newer = _create_feature(tmp_path, "zzz-newer-mission")
    (older / "meta.json").write_text(
        json.dumps(
            {
                "friendly_name": "Older Mission",
                "created_at": "2026-04-01T10:00:00+00:00",
                "mission_id": "01KOLDER000000000000000000",
            }
        ),
        encoding="utf-8",
    )
    (newer / "meta.json").write_text(
        json.dumps(
            {
                "friendly_name": "Newer Mission",
                "created_at": "2026-04-02T10:00:00+00:00",
                "mission_id": "01KNEWER000000000000000000",
            }
        ),
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert [feature["id"] for feature in features[:2]] == [
        "zzz-newer-mission",
        "aaa-older-mission",
    ]


def test_feature_recency_helpers_cover_timestamp_and_legacy_fallbacks():
    assert scanner._parse_created_at(None) is None
    assert scanner._parse_created_at("") is None
    assert scanner._parse_created_at("not-a-date") is None
    assert scanner._parse_created_at("2026-04-02T10:00:00Z") == scanner._parse_created_at("2026-04-02T10:00:00+00:00")
    assert scanner._parse_created_at("2026-04-02T10:00:00") == scanner._parse_created_at("2026-04-02T10:00:00+00:00")

    assert scanner._coerce_sort_mission_number(True) is None
    assert scanner._coerce_sort_mission_number(42) == 42
    assert scanner._coerce_sort_mission_number("042") == 42
    assert scanner._coerce_sort_mission_number("WP42") is None

    fallback_key = scanner._feature_recency_sort_key({"id": "legacy-mission", "meta": "not-a-dict"})
    assert fallback_key == (0, False, float("-inf"), False, "", False, -1, "legacy-mission")


def test_read_dashboard_feature_meta_ignores_malformed_and_non_object_json(tmp_path):
    invalid = tmp_path / "kitty-specs" / "001-invalid-meta"
    invalid.mkdir(parents=True)
    (invalid / "meta.json").write_text("{bad json", encoding="utf-8")

    assert scanner._read_dashboard_feature_meta(invalid) == ("001-invalid-meta", None)

    non_object = tmp_path / "kitty-specs" / "002-non-object-meta"
    non_object.mkdir(parents=True)
    (non_object / "meta.json").write_text('["not", "an", "object"]', encoding="utf-8")

    assert scanner._read_dashboard_feature_meta(non_object) == ("002-non-object-meta", None)


class TestDeriveMissionStatus:
    """_derive_mission_status returns the correct lifecycle bucket."""

    def _stats(self, **kwargs: int) -> dict:
        base = {"total": 0, "planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}
        base.update(kwargs)
        return base

    def test_draft_when_total_zero(self):
        assert scanner._derive_mission_status(self._stats()) == "draft"

    def test_draft_when_error_key_present(self):
        s = self._stats(total=3, planned=3)
        s["error"] = "Event log not found"
        assert scanner._derive_mission_status(s) == "draft"

    def test_active_when_doing(self):
        assert scanner._derive_mission_status(self._stats(total=2, doing=1, planned=1)) == "active"

    def test_active_when_for_review(self):
        assert scanner._derive_mission_status(self._stats(total=2, for_review=1, done=1)) == "active"

    def test_active_when_approved(self):
        assert scanner._derive_mission_status(self._stats(total=3, approved=1, done=2)) == "active"

    def test_planned_when_all_planned(self):
        assert scanner._derive_mission_status(self._stats(total=4, planned=4)) == "planned"

    def test_active_when_all_wps_done_but_not_accepted(self):
        # All WPs done but operator hasn't run spec-kitty accept — still needs attention
        meta = {"mission_slug": "042-foo"}
        assert scanner._derive_mission_status(self._stats(total=3, done=3), meta) == "active"

    def test_active_when_merged_but_not_accepted(self):
        meta = {"baseline_merge_commit": "abc123", "mission_slug": "042-foo"}
        assert scanner._derive_mission_status(self._stats(total=3, done=3), meta) == "active"

    def test_done_when_accepted(self):
        meta = {"accepted_at": "2026-07-12T00:00:00+00:00", "mission_slug": "042-foo"}
        assert scanner._derive_mission_status(self._stats(total=3, done=3), meta) == "done"

    def test_discarded_when_discarded_at_set(self):
        meta = {"discarded_at": "2026-09-13T00:00:00+00:00", "mission_slug": "042-foo"}
        assert scanner._derive_mission_status(self._stats(), meta) == "discarded"

    def test_discarded_wins_over_in_flight_lane_counts(self):
        # #704: `mission close --discard` abandons a mission mid-flight, so its
        # WPs are still sitting in doing/for_review. Deriving "active" from those
        # counts is exactly what kept discarded missions on the dashboard.
        meta = {"discarded_at": "2026-09-13T00:00:00+00:00", "mission_slug": "042-foo"}
        stats = self._stats(total=3, doing=2, planned=1)
        assert scanner._derive_mission_status(stats, meta) == "discarded"

    def test_discarded_wins_over_accepted(self):
        meta = {
            "accepted_at": "2026-07-12T00:00:00+00:00",
            "discarded_at": "2026-09-13T00:00:00+00:00",
            "mission_slug": "042-foo",
        }
        assert scanner._derive_mission_status(self._stats(total=3, done=3), meta) == "discarded"

    def test_discarded_sorts_below_draft(self):
        priority = scanner._MISSION_STATUS_PRIORITY
        assert priority["discarded"] < priority["draft"] < priority["done"]

    def test_done_when_no_meta(self):
        # Legacy missions with no meta.json fall through to done
        assert scanner._derive_mission_status(self._stats(total=3, done=3)) == "done"
        assert scanner._derive_mission_status(self._stats(total=3, done=3), None) == "done"

    def test_done_when_mix_of_done_and_canceled_and_accepted(self):
        # canceled WPs are not counted in total; total==done means mission is done
        meta = {"accepted_at": "2026-07-12T00:00:00+00:00"}
        assert scanner._derive_mission_status(self._stats(total=2, done=2), meta) == "done"


class TestDeriveNextAction:
    """_derive_next_action returns the right hint at each lifecycle stage."""

    def _stats(self, **kwargs: int) -> dict:
        base = {"total": 0, "planned": 0, "doing": 0, "for_review": 0, "approved": 0, "done": 0}
        base.update(kwargs)
        return base

    def test_none_when_accepted(self):
        meta = {"accepted_at": "2026-07-12T00:00:00+00:00", "baseline_merge_commit": "abc123", "mission_slug": "042-foo"}
        assert scanner._derive_next_action(meta, self._stats(total=2, done=2)) is None

    def test_review_and_accept_when_merged_not_accepted(self):
        meta = {"baseline_merge_commit": "abc123", "mission_slug": "042-foo"}
        result = scanner._derive_next_action(meta, self._stats(total=2, done=2))
        assert result is not None
        assert "spec-kitty.review" in result
        assert "spec-kitty accept" in result
        assert "042-foo" in result

    def test_merge_hint_when_all_wps_done_not_yet_merged(self):
        meta = {"mission_slug": "042-foo"}
        result = scanner._derive_next_action(meta, self._stats(total=4, done=4))
        assert result is not None
        assert "spec-kitty merge" in result
        assert "042-foo" in result

    def test_none_when_wps_still_in_flight(self):
        meta = {"mission_slug": "042-foo"}
        assert scanner._derive_next_action(meta, self._stats(total=4, done=2, doing=2)) is None

    def test_none_when_no_wps_yet(self):
        assert scanner._derive_next_action({}, self._stats()) is None

    def test_none_when_kanban_error(self):
        meta = {"mission_slug": "042-foo"}
        stats = self._stats(total=4, done=4)
        stats["error"] = "Event log not found"
        assert scanner._derive_next_action(meta, stats) is None

    def test_falls_back_to_slug_field(self):
        meta = {"slug": "042-bar"}
        result = scanner._derive_next_action(meta, self._stats(total=2, done=2))
        assert result is not None
        assert "042-bar" in result

    def test_none_when_no_slug_in_meta(self):
        assert scanner._derive_next_action({}, self._stats(total=1, done=1)) is None

    def test_none_when_slug_is_not_shell_safe(self):
        result = scanner._derive_next_action(
            {"mission_slug": "demo; rm -rf data"},
            self._stats(total=1, done=1),
        )
        assert result is None

    def test_none_when_meta_is_not_dict(self):
        assert scanner._derive_next_action(None, self._stats(total=2, done=2)) is None  # type: ignore[arg-type]


class TestFeatureStatusSortOrder:
    """Active missions sort before planned, planned before done/draft."""

    def _feature(self, status: str, created_at: str = "2026-01-01T00:00:00+00:00") -> dict:
        return {
            "id": f"mission-{status}",
            "mission_status": status,
            "meta": {"created_at": created_at},
        }

    def test_active_sorts_before_planned(self):
        features = [self._feature("planned"), self._feature("active")]
        features.sort(key=scanner._feature_recency_sort_key, reverse=True)
        assert features[0]["mission_status"] == "active"

    def test_planned_sorts_before_done(self):
        features = [self._feature("done"), self._feature("planned")]
        features.sort(key=scanner._feature_recency_sort_key, reverse=True)
        assert features[0]["mission_status"] == "planned"

    def test_done_sorts_before_draft(self):
        features = [self._feature("draft"), self._feature("done")]
        features.sort(key=scanner._feature_recency_sort_key, reverse=True)
        assert features[0]["mission_status"] == "done"

    def test_within_bucket_newest_first(self):
        features = [
            self._feature("active", "2026-01-01T00:00:00+00:00"),
            self._feature("active", "2026-06-01T00:00:00+00:00"),
        ]
        features[0]["id"] = "mission-a"
        features[1]["id"] = "mission-b"
        features.sort(key=scanner._feature_recency_sort_key, reverse=True)
        assert features[0]["id"] == "mission-b"  # newer


def test_build_legacy_kanban_stats_counts_lane_directories(tmp_path):
    tasks_dir = tmp_path / "tasks"
    (tasks_dir / "planned").mkdir(parents=True)
    (tasks_dir / "done" / "nested").mkdir(parents=True)
    (tasks_dir / "planned" / "WP01-demo.md").write_text("# WP01\n", encoding="utf-8")
    (tasks_dir / "done" / "nested" / "WP02-demo.md").write_text("# WP02\n", encoding="utf-8")

    stats = scanner._build_legacy_kanban_stats(tasks_dir)

    assert stats["planned"] == 1
    assert stats["done"] == 1
    assert stats["total"] == 2


def test_build_event_log_kanban_stats_surfaces_missing_event_log(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-missing-event-log"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\n---\n# Work Package Prompt: Demo\n",
        encoding="utf-8",
    )

    stats = scanner._build_event_log_kanban_stats(feature_dir, tasks_dir)

    assert stats["total"] == 0
    assert "Event log not found" in stats["error"]


def test_build_event_log_kanban_stats_tolerates_weighted_progress_failure(tmp_path, monkeypatch):
    import specify_cli.status as status_facade

    feature_dir = _create_feature(tmp_path, "001-progress-fallback")

    def fail_materialize(_feature_dir):
        raise RuntimeError("progress unavailable")

    # WP11: the dashboard read path resolves the *read-only* snapshot through
    # the status facade (`from specify_cli.status import materialize_snapshot`),
    # so patch the facade name it actually looks up — patching the reducer
    # submodule would not be seen.
    monkeypatch.setattr(status_facade, "materialize_snapshot", fail_materialize)

    stats = scanner._build_event_log_kanban_stats(feature_dir, feature_dir / "tasks")

    assert stats["total"] == 1
    assert stats["planned"] == 1
    assert "weighted_percentage" not in stats


def test_build_event_log_kanban_stats_excludes_unseeded_wps(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-unseeded"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text(
        """---
work_package_id: WP01
---
# Work Package Prompt: Demo
""",
        encoding="utf-8",
    )
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    stats = scanner._build_event_log_kanban_stats(feature_dir, tasks_dir)

    assert stats["total"] == 0
    assert stats["planned"] == 0


@pytest.mark.fast
def test_count_wps_by_lane_excludes_every_non_display_lane(tmp_path, monkeypatch):
    """Regression guard (#2675 harden): ``_count_wps_by_lane`` must route its
    exclusion check through :data:`NON_DISPLAY_LANES` — the single canonical
    authority — not an inline ``{Lane.GENESIS, ...}`` literal, so a WP whose
    read-time lane resolves to *any* member of ``NON_DISPLAY_LANES`` (today:
    ``GENESIS`` and ``UNINITIALIZED``) is excluded from kanban counts.

    ``UNINITIALIZED`` cannot arise naturally through this call path today
    (``get_all_wp_lanes`` only returns lanes for WPs with events, and the
    caller's own default is ``Lane.GENESIS``) — so this test injects it
    directly via the ``get_all_wp_lanes`` seam to pin the *filter's*
    behavior, not just today's reachable inputs.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-non-display-lanes"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    for wp_id in ("WP01", "WP02", "WP03"):
        (tasks_dir / f"{wp_id}-demo.md").write_text(
            f"---\nwork_package_id: {wp_id}\n---\n# Work Package Prompt: Demo\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "specify_cli.status.get_all_wp_lanes",
        lambda _feature_dir: {
            "WP01": Lane.UNINITIALIZED,
            "WP02": Lane.GENESIS,
            "WP03": Lane.PLANNED,
        },
    )

    counts = scanner._count_wps_by_lane(tasks_dir)

    assert counts == {"planned": 1, "doing": 0, "for_review": 0, "approved": 0, "done": 0}


@pytest.mark.fast
def test_process_wp_file_uses_frontmatter_title_without_prompt_header(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-frontmatter-title"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    prompt_file = tasks_dir / "WP01-demo.md"
    prompt_file.write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Frontmatter Demo Title\n"
        "---\n\n"
        "Body without a Work Package Prompt header.\n",
        encoding="utf-8",
    )
    _set_wp_lane(feature_dir, "WP01", "planned")

    task = scanner._process_wp_file(prompt_file, tmp_path, "planned")

    assert task is not None
    assert task["title"] == "Frontmatter Demo Title"


@pytest.mark.fast
def test_process_wp_file_falls_back_to_stem_without_title_or_prompt_header(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-stem-title"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    prompt_file = tasks_dir / "WP01-demo.md"
    prompt_file.write_text(
        "---\nwork_package_id: WP01\n---\n\nBody without a Work Package Prompt header.\n",
        encoding="utf-8",
    )
    _set_wp_lane(feature_dir, "WP01", "planned")

    task = scanner._process_wp_file(prompt_file, tmp_path, "planned")

    assert task is not None
    assert task["title"] == "WP01-demo"


def test_process_wp_file_raises_without_canonical_log_for_nonlegacy(tmp_path, monkeypatch):
    """A non-legacy WP with no canonical event log surfaces CanonicalStatusNotFoundError."""
    from specify_cli.status import CanonicalStatusNotFoundError

    feature_dir = tmp_path / "kitty-specs" / "001-no-canonical-log"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    prompt_file = tasks_dir / "WP01-demo.md"
    prompt_file.write_text(
        "---\nwork_package_id: WP01\n---\n# Work Package Prompt: Demo\n",
        encoding="utf-8",
    )
    # No status.events.jsonl anywhere; force the non-legacy branch.
    monkeypatch.setattr(scanner, "is_legacy_format", lambda _feature_dir: False)

    with pytest.raises(CanonicalStatusNotFoundError):
        scanner._process_wp_file(prompt_file, tmp_path, "planned")


def test_build_kanban_stats_handles_absent_and_legacy_paths(tmp_path, monkeypatch):
    feature_dir = tmp_path / "kitty-specs" / "001-legacy"
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / "doing").mkdir(parents=True)
    (tasks_dir / "doing" / "WP01-demo.md").write_text("# WP01\n", encoding="utf-8")

    assert scanner._build_kanban_stats(feature_dir, {"kanban": {}})["total"] == 0

    monkeypatch.setattr(scanner, "is_legacy_format", lambda _feature_dir: True)
    stats = scanner._build_kanban_stats(feature_dir, {"kanban": {"exists": True}})

    assert stats["doing"] == 1
    assert stats["total"] == 1


def test_scan_all_features_keeps_purpose_summary_in_meta_only(tmp_path):
    feature_dir = _create_feature(tmp_path)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "friendly_name": "Demo Feature",
                "purpose_tldr": "  Build   dashboard copy  ",
                "purpose_context": " Ship\nconsistent mission wording. ",
            }
        ),
        encoding="utf-8",
    )

    features = scanner.scan_all_features(tmp_path)

    assert "purpose_tldr" not in features[0]
    assert "purpose_context" not in features[0]
    assert features[0]["meta"]["purpose_tldr"] == "Build dashboard copy"
    assert features[0]["meta"]["purpose_context"] == "Ship consistent mission wording."


def test_scan_feature_kanban_returns_prompt(tmp_path):
    feature_dir = _create_feature(tmp_path)
    lanes = scanner.scan_feature_kanban(tmp_path, feature_dir.name)
    assert "planned" in lanes
    assert lanes["planned"], "planned lane should contain prompt data"
    task = lanes["planned"][0]
    assert task["id"] == "WP01"
    assert "prompt_markdown" in task


def test_resolve_active_feature_requires_explicit_selection(tmp_path):
    """resolve_active_feature returns None — auto-detection was removed.

    Since feature_detection was deleted (WP02), the dashboard no longer
    auto-detects the active feature.  Callers must provide an explicit
    --feature flag.  This test confirms the contract: without heuristics,
    resolve_active_feature always returns None.
    """
    resolved = scanner.resolve_active_feature(tmp_path)
    assert resolved is None, (
        "resolve_active_feature must return None after removal of auto-detection"
    )


def test_get_feature_artifacts_charter_present_when_only_yaml_exists(tmp_path):
    """#3150 regression: charter.yaml-only project reports the charter present.

    This is the reviewer's empirical repro for the WP02 rejection: prior to
    this fix, ``get_feature_artifacts`` drove the "charter" artifact's
    presence signal off ``resolve_project_charter_path`` (md-keyed), so a
    project with a compiled ``charter.yaml`` and no ``charter.md`` falsely
    reported ``exists: False``. FR-003/C-001 requires the presence probe to
    key on ``charter.yaml`` (the resolving authority) and survive
    ``charter.md`` deletion/absence.
    """
    feature_dir = _create_feature(tmp_path)
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")
    charter_md = charter_dir / "charter.md"
    assert not charter_md.exists(), "fixture must not seed charter.md (NFR-001)"

    result = scanner.get_feature_artifacts(feature_dir, project_dir=tmp_path)

    assert result["charter"]["exists"] is True


def test_project_charter_propagates_to_all_features(tmp_path):
    """Project-level charter presence propagates to every feature's artifacts.

    FR-003 (#3150): the "charter" artifact's exists/mtime/size signal keys
    on charter.yaml (the C-001 resolving authority), so this fixture seeds
    both files -- charter.yaml drives presence; charter.md stays the
    readable secondary prose companion served elsewhere.
    """
    _create_feature(tmp_path, "001-demo-feature")
    _create_feature(tmp_path, "002-another-feature")
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("schema_version: '2.0.0'\n", encoding="utf-8")
    (charter_dir / "charter.md").write_text("# Project Charter\n", encoding="utf-8")

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 2
    assert all(feature["artifacts"]["charter"]["exists"] for feature in features)


def test_feature_local_charter_is_ignored_without_project_charter(tmp_path):
    first = _create_feature(tmp_path, "001-demo-feature")
    _create_feature(tmp_path, "002-another-feature")
    (first / "charter.md").write_text("# Legacy Feature Charter\n", encoding="utf-8")

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 2
    assert all(not feature["artifacts"]["charter"]["exists"] for feature in features)


def test_legacy_memory_path_not_resolved(tmp_path):
    """Legacy .kittify/memory/ path is NOT resolved — user must run spec-kitty upgrade."""
    _create_feature(tmp_path, "001-demo-feature")
    _create_feature(tmp_path, "002-another-feature")
    legacy = tmp_path / ".kittify" / "memory" / "charter.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# Legacy Project Charter\n", encoding="utf-8")

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 2
    assert all(not feature["artifacts"]["charter"]["exists"] for feature in features)


def test_only_canonical_path_resolved(tmp_path):
    """Only .kittify/charter/charter.md is resolved."""
    _create_feature(tmp_path)
    new_path = tmp_path / ".kittify" / "charter" / "charter.md"
    new_path.parent.mkdir(parents=True)
    new_path.write_text("canonical", encoding="utf-8")

    resolved = resolve_project_charter_path(tmp_path)
    assert resolved == new_path


def test_scan_feature_kanban_approved_lane(tmp_path):
    """WPs with canonical lane approved should land in the approved column."""
    _create_feature(tmp_path, "001-demo", lane="approved")
    lanes = scanner.scan_feature_kanban(tmp_path, "001-demo")
    assert len(lanes["approved"]) == 1
    assert len(lanes["planned"]) == 0
    assert lanes["approved"][0]["id"] == "WP01"


def test_scan_feature_kanban_lane_mapping(tmp_path):
    """claimed and in_progress both map to doing."""
    feature_dir = tmp_path / "kitty-specs" / "001-demo"
    (feature_dir / "tasks").mkdir(parents=True)
    for wp_id, lane in [("WP01", "claimed"), ("WP02", "in_progress")]:
        (feature_dir / "tasks" / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\n---\n# Work Package Prompt: {wp_id}\n",
            encoding="utf-8",
        )
        _set_wp_lane(feature_dir, wp_id, lane)
    lanes = scanner.scan_feature_kanban(tmp_path, "001-demo")
    assert len(lanes["planned"]) == 0
    assert len(lanes["doing"]) == 2


@pytest.mark.fast
def test_scan_feature_kanban_structured_agent_metadata(tmp_path):
    feature_dir = tmp_path / "kitty-specs" / "001-demo"
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks" / "WP01-agent.md").write_text(
        """---
work_package_id: WP01
agent:
  tool: codex
  model: gpt-5.4
---
# Work Package Prompt: Agent Metadata
""",
        encoding="utf-8",
    )
    _set_wp_lane(feature_dir, "WP01", "planned")

    lanes = scanner.scan_feature_kanban(tmp_path, "001-demo")

    task = lanes["planned"][0]
    assert task["agent"] == ""
    assert task["model"] == ""
    assert task["authored_model"] == ""


def test_dashboard_scans_prefer_coord_worktree_over_root_checkout(tmp_path):
    slug = "001-demo-feature"

    # The coordination copy only outranks the primary checkout when it is a
    # *registered* git worktree — name proposes coord-ness, the git registry
    # disposes (C-SEAM-1). A bare ``-coord``-named directory is a husk and must
    # NOT shadow the primary surface. Register the worktree on a clean seed
    # commit so this exercises the real coord-preference path.
    #
    # #2430 refined WHAT the coord copy outranks for: the partitions split.
    # Live *status* (the event log) reads coord-first — the coord "approved"
    # lane must win over the primary's stale "planned". *Planning* artifacts
    # (spec/plan/tasks — PRIMARY-partition for every topology per
    # write-surface-coherence) read primary-first, so ``path`` anchors to the
    # primary surface, never a coord copy.
    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    _git(
        ["worktree", "add", "-q", "-b", f"kitty/mission-{slug}", str(coord_worktree)],
        tmp_path,
    )

    _create_feature(tmp_path, slug, lane="planned")

    coord_feature_dir = coord_worktree / "kitty-specs" / slug
    _create_feature_at(coord_feature_dir, lane="approved")

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 1
    feature = features[0]

    # Planning surface anchors to primary (#2430) …
    assert feature["path"] == f"kitty-specs/{slug}"
    assert feature["worktree"]["exists"] is True
    # … while live status still reads the coord worktree's event log.
    assert feature["kanban_stats"]["approved"] == 1
    assert feature["kanban_stats"]["planned"] == 0

    lanes = scanner.scan_feature_kanban(tmp_path, slug)
    assert len(lanes["approved"]) == 1
    assert len(lanes["planned"]) == 0
    assert lanes["approved"][0]["id"] == "WP01"


def test_status_only_coord_copy_does_not_hide_mission(tmp_path):
    """#2430: a PR-bound mission planned on a feature branch is scanned with a
    coord worktree copy holding ONLY status writes (``status.events.jsonl`` /
    ``status.json``) — no ``spec.md``, no ``tasks/``, no ``meta.json``, because
    ``spec-commit`` lands planning artifacts on the primary surface. The
    dashboard must still list the mission (planning from primary) with LIVE
    lanes (status from coord)."""
    slug = "cut-review-chunk-phase-01KWVYYG"  # post-083 slug: no numeric prefix

    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    _git(
        ["worktree", "add", "-q", "-b", f"kitty/mission-{slug}", str(coord_worktree)],
        tmp_path,
    )

    # PRIMARY: full planning artifacts + a STALE event log (lane: planned).
    primary_dir = _create_feature(tmp_path, slug, lane="planned")
    (primary_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KWVYYG0000000000000000ZZ", "mission_slug": slug}),
        encoding="utf-8",
    )

    # COORD copy: status partition ONLY — the live event log, nothing else.
    coord_feature_dir = coord_worktree / "kitty-specs" / slug
    coord_feature_dir.mkdir(parents=True)
    _set_wp_lane(coord_feature_dir, "WP01", "in_progress")
    assert not (coord_feature_dir / "tasks").exists()
    assert not (coord_feature_dir / "spec.md").exists()

    features = scanner.scan_all_features(tmp_path)
    ids = [f["id"] for f in features]
    assert slug in ids, f"mission invisible on dashboard (#2430); got {ids}"
    feature = next(f for f in features if f["id"] == slug)

    # Planning artifacts render from the primary surface …
    assert feature["path"] == f"kitty-specs/{slug}"
    assert feature["artifacts"]["spec"]["exists"] is True
    assert feature["artifacts"]["plan"]["exists"] is True
    assert feature["artifacts"]["tasks"]["exists"] is True
    # … and lane counts come from the coord worktree's LIVE event log, not the
    # primary's stale one.
    assert feature["kanban_stats"]["doing"] == 1
    assert feature["kanban_stats"]["planned"] == 0

    lanes = scanner.scan_feature_kanban(tmp_path, slug)
    assert [t["id"] for t in lanes["doing"]] == ["WP01"]
    assert lanes["planned"] == []


def test_coord_event_log_wins_when_stale_behind_primary(tmp_path):
    """#2430: coord event log is authoritative for status even when it lags behind primary.

    Scenario: primary has WP01 in ``approved`` (ahead); coord has WP01 in
    ``planned`` (stale/behind primary).  The dashboard must surface ``planned``
    (coord wins), not ``approved`` (primary).

    This is the inverse of ``test_dashboard_scans_prefer_coord_worktree_over_root_checkout``
    which tests coord-ahead.  Together they prove coord preference is unconditional
    — neither direction of lag overrides it.
    """
    slug = "coord-stale-primary-ahead-01KWST0A"

    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    _git(
        ["worktree", "add", "-q", "-b", f"kitty/mission-{slug}", str(coord_worktree)],
        tmp_path,
    )

    # PRIMARY: full planning artifacts + WP01 in ``approved`` (primary is ahead).
    primary_dir = _create_feature(tmp_path, slug, lane="approved")
    (primary_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01KWST0A0000000000000000ZZ", "mission_slug": slug}),
        encoding="utf-8",
    )

    # COORD copy: status partition ONLY — WP01 stale at ``planned``.
    coord_feature_dir = coord_worktree / "kitty-specs" / slug
    coord_feature_dir.mkdir(parents=True)
    _set_wp_lane(coord_feature_dir, "WP01", "planned")
    assert not (coord_feature_dir / "tasks").exists()

    features = scanner.scan_all_features(tmp_path)
    ids = [f["id"] for f in features]
    assert slug in ids, f"mission invisible on dashboard; got {ids}"
    feature = next(f for f in features if f["id"] == slug)

    # Planning artifacts anchor to the primary surface …
    assert feature["path"] == f"kitty-specs/{slug}"
    assert feature["artifacts"]["spec"]["exists"] is True
    assert feature["artifacts"]["plan"]["exists"] is True
    assert feature["artifacts"]["tasks"]["exists"] is True
    # … and lane counts come unconditionally from the coord event log (planned),
    # not the primary's ahead state (approved).
    assert feature["kanban_stats"]["planned"] == 1
    assert feature["kanban_stats"]["approved"] == 0

    lanes = scanner.scan_feature_kanban(tmp_path, slug)
    assert [t["id"] for t in lanes["planned"]] == ["WP01"]
    assert lanes["approved"] == []


def test_resolve_feature_planning_dir_reanchors_viewer_reads(tmp_path):
    """#2502: the artifact-viewer endpoints (spec/plan/research/contracts/
    checklists) resolve their feature dir coord-first, so an in-flight
    coordination mission's viewers rendered empty off the status-only husk.
    ``resolve_feature_planning_dir`` must re-anchor to the primary surface,
    while the plain resolver keeps returning the coord dir (status authority
    for the kanban's weighted-progress read)."""
    slug = "review-context-depth-01KX2EQ9"  # post-083 slug, live coord worktree

    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    _git(
        ["worktree", "add", "-q", "-b", f"kitty/mission-{slug}", str(coord_worktree)],
        tmp_path,
    )

    # PRIMARY: full planning artifacts, including the viewer content.
    primary_dir = _create_feature(tmp_path, slug, lane="in_progress")
    (primary_dir / "research.md").write_text("# Research\n", encoding="utf-8")

    # COORD copy: status partition only (the in-flight husk).
    coord_feature_dir = coord_worktree / "kitty-specs" / slug
    coord_feature_dir.mkdir(parents=True)
    _set_wp_lane(coord_feature_dir, "WP01", "in_progress")
    assert not (coord_feature_dir / "research.md").exists()

    coord_dir = scanner.resolve_feature_dir(tmp_path, slug)
    planning_dir = scanner.resolve_feature_planning_dir(tmp_path, slug)

    assert coord_dir == coord_feature_dir  # status authority unchanged
    assert planning_dir == primary_dir  # viewers re-anchored (#2502)
    assert (planning_dir / "research.md").exists()
    assert (planning_dir / "spec.md").exists()


def test_resolve_feature_planning_dir_unknown_feature_is_none(tmp_path):
    assert scanner.resolve_feature_planning_dir(tmp_path, "no-such-mission") is None


def test_registry_resolves_canonical_id_for_inflight_coord_mission(tmp_path):
    """#2331: a mid-orchestration mission (registered coord worktree, meta.json
    absent from the coord tree) must resolve to its canonical ULID in the
    registry — never ``orphan:<slug>`` — because identity is a PRIMARY artifact.

    Reproduces the reported split-brain: ``gather_feature_paths`` prefers the
    coord worktree (live status), but ``meta.json`` lives only on the primary
    checkout, so identity resolution must read the primary surface.
    """
    slug = "spec-kitty-moov-integration-01KWN9D0"
    ulid = "01KWN9D0MJ79NK1T90RWYY2Y7R"

    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    _git(
        ["worktree", "add", "-q", "-b", f"kitty/mission-{slug}", str(coord_worktree)],
        tmp_path,
    )

    # PRIMARY checkout: feature + canonical meta.json (the identity source).
    primary_dir = _create_feature(tmp_path, slug, lane="in_progress")
    (primary_dir / "meta.json").write_text(
        json.dumps({"mission_id": ulid, "mission_slug": slug}), encoding="utf-8"
    )

    # COORD worktree: live feature artifacts but NO meta.json (mid-orchestration).
    coord_feature_dir = coord_worktree / "kitty-specs" / slug
    _create_feature_at(coord_feature_dir, lane="in_progress")
    assert not (coord_feature_dir / "meta.json").exists()

    registry = scanner.build_mission_registry(tmp_path)

    assert ulid in registry, f"expected canonical ULID key; got {list(registry)}"
    assert not any(k.startswith("orphan:") for k in registry), f"unexpected orphan: {list(registry)}"
    assert registry[ulid]["mission_slug"] == slug
    assert registry[ulid]["mid8"] == ulid[:8]
    # And it is listed for display (not filtered as a pseudo-key).
    assert ulid in scanner.sort_missions_for_display(registry)


@pytest.mark.fast
def test_dashboard_husk_coord_dir_does_not_shadow_primary(tmp_path):
    """F-005 adversarial: a ``-coord``-NAMED directory that git does NOT
    register is a husk and must NOT outrank the primary checkout.

    Name proposes coord-ness; the git registry disposes (C-SEAM-1). Before the
    topology seam, the name-only ``endswith("-coord")`` predicate let this husk
    silently shadow the live primary surface — the split-brain this WP kills.
    """
    slug = "001-demo-feature"

    _git(["init", "--initial-branch=main"], tmp_path)
    _git(["config", "user.email", "scanner@example.com"], tmp_path)
    _git(["config", "user.name", "Scanner Test"], tmp_path)
    _git(["config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "README.md"], tmp_path)
    _git(["commit", "-q", "-m", "seed"], tmp_path)

    # Primary checkout: the authoritative, current state.
    _create_feature(tmp_path, slug, lane="planned")

    # A husk: a ``-coord``-named plain dir that was NEVER `git worktree add`-ed.
    husk_feature_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _create_feature_at(husk_feature_dir, lane="approved")

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 1
    feature = features[0]
    # The husk's stale "approved" must NOT win; the primary "planned" stands.
    assert feature["path"] == f"kitty-specs/{slug}"
    assert feature["kanban_stats"]["planned"] == 1
    assert feature["kanban_stats"]["approved"] == 0


@pytest.mark.no_git_tmp_path
def test_dashboard_scan_degrades_when_registry_unreadable_in_non_git_project(
    tmp_path: Path,
) -> None:
    """WP03 seam degradation: when ``.worktrees/`` exists but the project is NOT
    a git repo, ``read_worktree_registry`` fails closed with
    ``WorktreeRegistryUnavailable``. The scanner must degrade gracefully —
    treat every worktree dir as non-coord rather than crashing the whole
    dashboard scan (covers ``scanner.py`` lines 332/336).

    Behavioural contract: a ``-coord``-named directory has no readable registry
    to consult, so it cannot be classified as a coord worktree and therefore
    must NOT outrank/shadow the primary ``kitty-specs/`` surface. The scan
    succeeds and the primary copy wins.
    """
    slug = "001-demo-feature"

    # Deliberately NO `git init`: the project dir is not a git repo, so the
    # `git worktree list --porcelain` read inside `gather_feature_paths` raises
    # WorktreeRegistryUnavailable. This is the real trigger, not a mock.
    assert not (tmp_path / ".git").exists()

    # Primary checkout surface (authoritative when the registry is unreadable).
    _create_feature(tmp_path, slug, lane="planned")

    # A ``-coord``-named directory sitting under .worktrees/. With no registry
    # it cannot be promoted to coord topology.
    husk_feature_dir = tmp_path / ".worktrees" / f"{slug}-coord" / "kitty-specs" / slug
    _create_feature_at(husk_feature_dir, lane="approved")

    # The scan completes (no crash) despite the unreadable registry.
    paths = scanner.gather_feature_paths(tmp_path)

    # The husk did NOT win: the resolved path is the primary surface, not the
    # ``.worktrees/...-coord`` copy.
    assert paths[slug] == tmp_path / "kitty-specs" / slug
    assert paths[slug] != husk_feature_dir

    features = scanner.scan_all_features(tmp_path)
    assert len(features) == 1
    feature = features[0]
    assert feature["path"] == f"kitty-specs/{slug}"
    # Primary "planned" stands; the degraded coord dir's "approved" is ignored.
    assert feature["kanban_stats"]["planned"] == 1
    assert feature["kanban_stats"]["approved"] == 0


# ── scan_feature_kanban error-handling paths ───────────────────────────────


def test_scan_feature_kanban_canonical_status_not_found_returns_empty_lanes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CanonicalStatusNotFoundError aborts WP iteration and returns empty lanes.

    Covers scanner.py lines 872-877: the except-branch warning log and the
    early ``return lanes`` that short-circuits the rest of the loop when the
    feature's event log has not yet been seeded by finalize-tasks.
    """
    from specify_cli.status import CanonicalStatusNotFoundError

    feature_dir = tmp_path / "kitty-specs" / "001-no-event-log"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\n---\n# Work Package Prompt: Demo\n",
        encoding="utf-8",
    )

    def _raise_canonical(*_args: object, **_kwargs: object) -> None:
        raise CanonicalStatusNotFoundError("no event log seeded")

    monkeypatch.setattr(scanner, "_process_wp_file", _raise_canonical)

    lanes = scanner.scan_feature_kanban(tmp_path, "001-no-event-log")

    assert all(len(v) == 0 for v in lanes.values()), (
        "all lanes must be empty when CanonicalStatusNotFoundError is raised "
        "during WP processing"
    )


def test_scan_feature_kanban_generic_exception_is_logged_and_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generic Exception from _process_wp_file is logged and the WP is skipped.

    Covers scanner.py lines 878-880: the broad except-branch logger.error call
    and the ``continue`` that keeps the loop alive for subsequent WP files.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-bad-wp"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-broken.md").write_text(
        "---\nwork_package_id: WP01\n---\n# Work Package Prompt: Broken\n",
        encoding="utf-8",
    )

    def _raise_generic(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated unexpected processing error")

    monkeypatch.setattr(scanner, "_process_wp_file", _raise_generic)

    # Must not propagate — the broad except catches it and continues.
    lanes = scanner.scan_feature_kanban(tmp_path, "001-bad-wp")

    assert all(len(v) == 0 for v in lanes.values()), (
        "all lanes must be empty after a broken WP is skipped via the generic "
        "exception handler"
    )


# ── _resolve_planning_dir_primary_first fallback paths (#2430) ─────────────


@pytest.mark.fast
def test_resolve_planning_dir_primary_first_falls_back_on_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ValueError from resolve_planning_read_dir returns the scanned dir (#2430).

    Covers scanner.py lines 463-464: the except branch when the resolver
    declines because the mission slug contains an unsafe segment.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-bad-segment"
    feature_dir.mkdir(parents=True)

    def _raise_value_error(*_a: object, **_kw: object) -> Path:
        raise ValueError("unsafe segment in mission slug")

    monkeypatch.setattr(scanner, "resolve_planning_read_dir", _raise_value_error)

    result = scanner._resolve_planning_dir_primary_first(tmp_path, feature_dir)

    assert result == feature_dir


@pytest.mark.fast
def test_resolve_planning_dir_primary_first_falls_back_on_ambiguous_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MissionSelectorAmbiguous from the resolver returns the scanned dir (#2430).

    Covers scanner.py lines 463-464: the except branch when multiple missions
    share the same slug prefix and the resolver cannot disambiguate.
    """
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    feature_dir = tmp_path / "kitty-specs" / "01KW-ambiguous"
    feature_dir.mkdir(parents=True)

    def _raise_ambiguous(*_a: object, **_kw: object) -> Path:
        raise MissionSelectorAmbiguous(handle="01KW", candidates=["01KWN9D0", "01KWV531"])

    monkeypatch.setattr(scanner, "resolve_planning_read_dir", _raise_ambiguous)

    result = scanner._resolve_planning_dir_primary_first(tmp_path, feature_dir)

    assert result == feature_dir


@pytest.mark.fast
def test_resolve_planning_dir_primary_first_falls_back_when_candidate_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved primary path that does not exist on disk returns the scanned dir.

    Covers scanner.py line 467: the fallback when the resolver returns a
    candidate path that has not been checked out locally (e.g. lane-only
    worktree where the primary feature branch exists only in the registry).
    """
    feature_dir = tmp_path / "kitty-specs" / "001-remote-primary"
    feature_dir.mkdir(parents=True)
    absent = tmp_path / ".worktrees" / "001-remote-primary-lane-1" / "kitty-specs" / "001-remote-primary"
    # absent is never created — must not exist

    monkeypatch.setattr(scanner, "resolve_planning_read_dir", lambda *_a, **_kw: absent)

    result = scanner._resolve_planning_dir_primary_first(tmp_path, feature_dir)

    assert result == feature_dir
    assert not absent.exists()


@pytest.mark.fast
def test_resolve_planning_dir_primary_first_returns_candidate_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolver returns an existing primary dir → the candidate wins over feature_dir.

    Covers scanner.py lines 465-466: the happy-path branch where the resolved
    primary dir exists on disk and is returned in preference to the coord-resolved
    scanned dir. Also kills the mutation-blind gap in the three fallback tests: a
    stub that always returns ``feature_dir`` fails this test because
    ``result != feature_dir`` is asserted.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-has-primary"
    feature_dir.mkdir(parents=True)
    primary_dir = (
        tmp_path / ".worktrees" / "001-has-primary-lane-1" / "kitty-specs" / "001-has-primary"
    )
    primary_dir.mkdir(parents=True)  # exists — resolver found a live primary checkout

    monkeypatch.setattr(scanner, "resolve_planning_read_dir", lambda *_a, **_kw: primary_dir)

    result = scanner._resolve_planning_dir_primary_first(tmp_path, feature_dir)

    assert result == primary_dir
    assert result != feature_dir


# ── NFR-006: Dashboard kanban bucketing identity ───────────────────────────


@pytest.mark.fast
def test_display_category_matches_kanban_columns():
    """All lanes produce the expected dashboard kanban column labels (NFR-006).

    Verifies that WPState.display_category() returns the correct label for
    every canonical lane, ensuring the dashboard kanban bucketing is
    consistent with the WPState model.
    """
    from specify_cli.status import wp_state_for

    expected_mapping = {
        "planned": "Planned",
        "claimed": "In Progress",
        "in_progress": "In Progress",
        "for_review": "Review",
        "in_review": "In Progress",
        "approved": "Approved",
        "done": "Done",
        "blocked": "Blocked",
        "canceled": "Canceled",
    }
    for lane, expected_label in expected_mapping.items():
        state = wp_state_for(lane)
        assert state.display_category() == expected_label, (
            f"Lane {lane}: expected {expected_label!r}, got {state.display_category()!r}"
        )


@pytest.mark.fast
def test_kanban_column_map_covers_all_lanes():
    """_KANBAN_COLUMN_FOR_LANE covers every display Lane enum member (NFR-006).

    'genesis' and 'uninitialized' are non-display lanes: neither is ever the
    current lane of a materialized WP, and neither has a kanban column by
    design, so both are excluded from the column map (NON_DISPLAY_LANES).
    """
    from specify_cli.dashboard.scanner import _KANBAN_COLUMN_FOR_LANE

    for member in Lane:
        if member in NON_DISPLAY_LANES:
            assert member not in _KANBAN_COLUMN_FOR_LANE, (
                f"{member.value} is non-display and must not have a kanban column"
            )
            continue
        assert member in _KANBAN_COLUMN_FOR_LANE, (
            f"Lane.{member.name} missing from _KANBAN_COLUMN_FOR_LANE"
        )


# ---------------------------------------------------------------------------
# WP11 / FR-014(a) / SC-6a — dashboard reads are write-free, even during a git
# op. The dashboard MUST NOT clobber tracked status.json when serving a kanban
# request while a long-running git operation (e.g. rebase) is in progress.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_dashboard_read_does_not_write_status_json(tmp_path):
    """The dashboard read path never writes tracked status.json (FR-014a).

    Seed an event log but no status.json, then exercise the dashboard kanban
    read. The read-only snapshot must compute progress without materializing
    the tracked status.json artifact.
    """
    feature_dir = _create_feature(tmp_path, "001-readonly-no-write")
    status_json = feature_dir / "status.json"
    # _create_feature seeds via materialize(); remove the artifact so we can
    # prove the dashboard read path does NOT recreate it.
    if status_json.exists():
        status_json.unlink()

    stats = scanner._build_event_log_kanban_stats(feature_dir, feature_dir / "tasks")

    assert "weighted_percentage" in stats, "payload unchanged: progress still computed"
    assert not status_json.exists(), (
        "dashboard read wrote tracked status.json (FR-014a clobber)"
    )


@pytest.mark.fast
def test_read_only_weighted_percentage_matches_materialize_payload(tmp_path):
    """The read-only snapshot yields the same weighted % the writer would (C-004).

    Switching from materialize() to materialize_snapshot() must not change the
    rendered kanban payload — only remove the write side-effect.
    """
    from specify_cli.status import compute_weighted_progress

    feature_dir = _create_feature(tmp_path, "001-payload-parity")

    writer_snapshot = materialize(feature_dir)
    writer_pct = round(compute_weighted_progress(writer_snapshot).percentage, 1)

    read_only_pct = scanner.read_only_weighted_percentage(feature_dir)

    assert read_only_pct == writer_pct, (
        "read-only snapshot diverged from the writing materialize() payload"
    )


def _git(args, cwd) -> None:
    import subprocess

    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.fast
def test_sc6a_dashboard_no_status_clobber_during_real_rebase(tmp_path):
    """SC-6a: a real ``git rebase`` with the dashboard serving kanban does not
    clobber tracked status.json.

    Mirrors WP07's SC-5 style with a genuine (non-mocked) conflicted rebase.
    While the rebase is paused mid-operation, the dashboard kanban read path
    must NOT write tracked status — sharing WP07's single git-op detection
    (``git_operation_in_progress``) rather than duplicating it (C-005).
    """
    import subprocess

    from specify_cli.status import git_operation_in_progress

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    _git(["init", "--initial-branch=main"], repo_root)
    _git(["config", "user.email", "wp11@example.com"], repo_root)
    _git(["config", "user.name", "WP11 Test"], repo_root)
    _git(["config", "commit.gpgsign", "false"], repo_root)

    slug = "001-dashboard-rebase"
    feature_dir = repo_root / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "tasks" / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\nsubtasks: [\"T1\"]\n---\n# Work Package Prompt: Demo\n",
        encoding="utf-8",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="TESTWP01PLANNED00000000000"[:26],
            mission_slug=slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-03-31T09:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="direct_repo",
        ),
    )

    status_json = feature_dir / "status.json"
    # status.json is a tracked artifact; the dashboard must never write it.
    # .gitignore keeps the rebase replay clean of any derived noise.
    (repo_root / ".gitignore").write_text("", encoding="utf-8")

    _git(["add", "."], repo_root)
    _git(["commit", "-m", "chore: baseline"], repo_root)
    # Remove status.json so we can prove the dashboard read does not recreate it.
    if status_json.exists():
        status_json.unlink()
        _git(["add", "-A"], repo_root)
        _git(["commit", "-m", "chore: drop status.json"], repo_root)

    # Diverge main vs mission branch on the same file to force a conflicted,
    # paused rebase (the long-op window).
    conflict = repo_root / "conflict.txt"
    _git(["checkout", "-b", f"kitty/mission-{slug}"], repo_root)
    conflict.write_text("mission-line\n", encoding="utf-8")
    _git(["add", "conflict.txt"], repo_root)
    _git(["commit", "-m", "feat: mission change"], repo_root)

    _git(["checkout", "main"], repo_root)
    conflict.write_text("main-line\n", encoding="utf-8")
    _git(["add", "conflict.txt"], repo_root)
    _git(["commit", "-m", "feat: main change"], repo_root)

    _git(["checkout", f"kitty/mission-{slug}"], repo_root)

    rebase = subprocess.run(
        ["git", "rebase", "main"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert rebase.returncode != 0, "rebase should pause on conflict"
    assert git_operation_in_progress(repo_root) is True

    # The dashboard serves a kanban request mid-rebase.
    stats = scanner._build_event_log_kanban_stats(feature_dir, feature_dir / "tasks")

    assert "weighted_percentage" in stats, "payload unchanged: progress still served"
    assert not status_json.exists(), (
        "dashboard clobbered tracked status.json during an active rebase "
        "(FR-014a / SC-6a violation)"
    )

    # Clean up the rebase so the worktree is not left mid-operation.
    subprocess.run(
        ["git", "rebase", "--abort"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
