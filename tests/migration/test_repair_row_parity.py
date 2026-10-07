"""#5811 WP02: the mission-state repair is a byte-identical no-op on writer-shaped history.

The row shape comes from the live writer path (``StatusEvent.to_dict`` through
``serialize_event_line``), never from hand-written JSON, and the optional-field
subsets are derived from ``dataclasses.fields(StatusEvent)`` so a field added to
the model is exercised (or fails the coverage assertion) without anyone editing
a second list.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any

import pytest

from specify_cli.migration.mission_state import (
    STATUS_JSON_DRIFT_NOT_WRITTEN_ACTION,
    _canonicalize_status_rows,
    _RawJsonlRow,
    repair_repo,
)
from specify_cli.status import ANNOTATION_KIND, materialize_snapshot, materialize_to_json, serialize_event_line
from specify_cli.status.models import DoneEvidence, Lane, ReviewApproval, ReviewResult, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "001-parity"
_MISSION_ID = "01KQHRB8GCFJAX7HM4ZY52AQGR"
_STRUCTURED_ACTOR = {"role": "implementer", "profile": "python-pedro", "tool": "claude", "model": "opus"}

# One populated value per optional StatusEvent field. Non-ASCII and nested values pin
# ``ensure_ascii`` and key ordering of the serializer.
_OPTIONAL_VALUES: dict[str, Any] = {
    "reason": "Überprüfung abgeschlossen",
    "reason_source": "operator",
    "review_ref": "review-cycle://WP01/1",
    "evidence": DoneEvidence(review=ReviewApproval(reviewer="renata", verdict="approved", reference="ref")),
    "review_result": ReviewResult(reviewer="renata", verdict="approved", reference="ref", feedback_path="f.md"),
    "policy_metadata": {"zeta": {"b": 1, "a": "é"}, "alpha": [1, "ü"]},
    "mission_id": _MISSION_ID,
}


def _optional_field_names() -> list[str]:
    return [f.name for f in fields(StatusEvent) if f.default is not MISSING or f.default_factory is not MISSING]


def _event(*, optional: dict[str, Any], structured_actor: bool, event_id: str = "01KQHRB8GCFJAX7HM4ZY52AQGS") -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id="WP01",
        from_lane=Lane.IN_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-01-01T00:00:00+00:00",
        actor=_STRUCTURED_ACTOR if structured_actor else "Claude Code",
        force=False,
        execution_mode="worktree",
        **optional,
    )


def _line(event: StatusEvent) -> str:
    return str(serialize_event_line(event.to_dict()))


def _canonicalize(tmp_path: Path, lines: list[str]) -> tuple[list[str], list[Any], list[str], list[str]]:
    rows = [_RawJsonlRow(line_number=i, text=line, data=json.loads(line)) for i, line in enumerate(lines, start=1)]
    canonical, changes, quarantine, errors, _seen = _canonicalize_status_rows(
        tmp_path, tmp_path / "kitty-specs" / _SLUG, rows, mission_slug=_SLUG, mission_id=_MISSION_ID
    )
    return canonical, changes, quarantine, errors


def test_every_optional_status_event_field_is_covered() -> None:
    assert set(_optional_field_names()) == set(_OPTIONAL_VALUES), "StatusEvent gained or lost an optional field: update _OPTIONAL_VALUES"


# All absent, each optional field alone, all present: a field the serializer or a rule mishandles
# fails in isolation; the review pair and the full row pin their interaction.
_FIELD_SETS: dict[str, tuple[str, ...]] = {
    "none": (),
    **{f"only-{name}": (name,) for name in sorted(_OPTIONAL_VALUES)},
    "evidence-and-review_ref": ("evidence", "review_ref"),
    "all": tuple(sorted(_OPTIONAL_VALUES)),
}


@pytest.mark.parametrize("structured_actor", [False, True], ids=["string-actor", "structured-actor"])
@pytest.mark.parametrize("field_set", list(_FIELD_SETS))
def test_writer_shaped_rows_are_byte_identical_for_representative_optional_field_sets(tmp_path: Path, field_set: str, structured_actor: bool) -> None:
    names = _FIELD_SETS[field_set]
    line = _line(_event(optional={name: _OPTIONAL_VALUES[name] for name in names}, structured_actor=structured_actor))

    assert _canonicalize(tmp_path, [line]) == ([line], [], [], [])


def test_non_lane_and_annotation_rows_keep_their_original_text(tmp_path: Path) -> None:
    # Unsorted keys, non-default separators and non-ASCII text: any re-serialization changes the bytes.
    lifecycle = (
        '{"payload": {"decision_point_id": "DP01", "note": "café"},  "event_type": "DecisionPointOpened", '
        '"event_id": "01KQHRB8GCFJAX7HM4ZY52AQGT", "at": "2026-01-01T00:00:01+00:00"}'
    )
    annotation = (
        f'{{"kind": "{ANNOTATION_KIND}", "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGU", "wp_id": "WP01", "at": "2026-01-01T00:00:02+00:00", "delta": {{"note": "ü"}}}}'
    )

    canonical, changes, quarantine, errors = _canonicalize(tmp_path, [lifecycle, annotation])

    assert (canonical, changes, quarantine, errors) == ([lifecycle, annotation], [], [], [])


def test_rows_with_null_optional_keys_from_older_repairs_stay_verbatim(tmp_path: Path) -> None:
    # Earlier repair versions wrote reason_source/review_result as explicit nulls; they are
    # semantically canonical and must not be rewritten.
    row = {**_event(optional={}, structured_actor=False).to_dict(), "reason_source": None, "review_result": None}
    line = json.dumps(row, sort_keys=True)

    canonical, changes, _quarantine, errors = _canonicalize(tmp_path, [line])

    assert (canonical, changes, errors) == ([line], [], [])


def test_legacy_rows_are_still_normalized(tmp_path: Path) -> None:
    legacy = {
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "feature_slug": _SLUG,
        "work_package_id": "WP01",
        "from_lane": "doing",
        "to_lane": "in_review",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "codex",
        "force": False,
        "execution_mode": "worktree",
    }

    canonical, changes, _quarantine, errors = _canonicalize(tmp_path, [json.dumps(legacy)])

    assert errors == []
    row = json.loads(canonical[0])
    assert (row["mission_slug"], row["wp_id"], row["from_lane"], row["mission_id"]) == (_SLUG, "WP01", "in_progress", _MISSION_ID)
    assert "feature_slug" not in row
    assert {"mission_id_backfilled", "lane_alias:from_lane:doing->in_progress"} <= set(changes[0].actions)


def test_legacy_mistyped_scalars_are_coerced_with_manifest_actions(tmp_path: Path) -> None:
    legacy = {**_event(optional={}, structured_actor=False).to_dict(), "at": 20260101, "force": 1}

    canonical, changes, _quarantine, errors = _canonicalize(tmp_path, [json.dumps(legacy)])

    assert errors == []
    row = json.loads(canonical[0])
    assert (row["at"], row["force"]) == ("20260101", True)
    assert {"coerced_type:at", "coerced_type:force"} <= set(changes[0].actions)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _write_mission(repo: Path, lines: list[str], *, meta: dict[str, Any] | None = None) -> Path:
    from specify_cli.mission_metadata import write_meta

    mission = repo / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    write_meta(
        mission,
        meta
        or {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Parity",
            "mid8": _MISSION_ID[:8],
            "mission_id": _MISSION_ID,
            "mission_number": None,
            "mission_slug": _SLUG,
            "mission_type": "software-dev",
            "slug": _SLUG,
            "target_branch": "main",
        },
    )
    (mission / "status.events.jsonl").write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return mission


def _commit_all(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts}


def _out_of_order_lines() -> list[str]:
    stamps = ("2026-01-01T00:00:03+00:00", "2026-01-01T00:00:01+00:00", "2026-01-01T00:00:02+00:00")
    lanes = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"))
    lines = []
    for index, (at, (frm, to)) in enumerate(zip(stamps, lanes, strict=True)):
        event = StatusEvent(
            event_id=f"01KQHRB8GCFJAX7HM4ZY52AQG{index}",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane(frm),
            to_lane=Lane(to),
            at=at,
            actor="claude",
            force=False,
            execution_mode="worktree",
            mission_id=_MISSION_ID,
        )
        lines.append(_line(event))
    return lines


def test_repair_keeps_a_healthy_mission_byte_identical_and_preserves_order(tmp_path: Path) -> None:
    mission = _write_mission(tmp_path, _out_of_order_lines())
    _commit_all(tmp_path)
    before = _tree_bytes(tmp_path / "kitty-specs")
    snapshot_before = materialize_to_json(materialize_snapshot(mission))

    report = repair_repo(tmp_path)

    assert report.missions[0].status == "unchanged"
    assert report.missions[0].file_changes == []
    # Meta.json (the live writer's shape), the out-of-(at, event_id)-order log, and no new derived files.
    assert _tree_bytes(tmp_path / "kitty-specs") == before
    assert materialize_to_json(materialize_snapshot(mission)) == snapshot_before


def test_status_json_drift_without_a_log_change_is_reported_not_written(tmp_path: Path) -> None:
    mission = _write_mission(tmp_path, _out_of_order_lines())
    stale = materialize_to_json(materialize_snapshot(mission)).replace('"for_review"', '"claimed"', 1)
    (mission / "status.json").write_text(stale, encoding="utf-8")
    _commit_all(tmp_path)

    report = repair_repo(tmp_path)

    assert (mission / "status.json").read_text(encoding="utf-8") == stale
    assert STATUS_JSON_DRIFT_NOT_WRITTEN_ACTION in report.missions[0].meta_actions
    assert report.missions[0].status == "unchanged"


def test_changed_log_rewrites_a_tracked_status_json(tmp_path: Path) -> None:
    lines = _out_of_order_lines()
    legacy = json.loads(lines[0])
    legacy["work_package_id"] = legacy.pop("wp_id")
    mission = _write_mission(tmp_path, [json.dumps(legacy, sort_keys=True), *lines[1:]])
    (mission / "status.json").write_text("{}\n", encoding="utf-8")
    _commit_all(tmp_path)

    report = repair_repo(tmp_path)

    assert report.missions[0].status == "updated"
    written = (mission / "status.json").read_text(encoding="utf-8")
    assert written == materialize_to_json(materialize_snapshot(mission))
    assert written != "{}\n"


def test_derived_files_are_never_created_for_a_mission_without_them(tmp_path: Path) -> None:
    mission = _write_mission(tmp_path, _out_of_order_lines())
    _commit_all(tmp_path)

    repair_repo(tmp_path)

    assert not (mission / "status.json").exists()
    assert not (mission / "lanes.json").exists()


def test_untracked_status_json_is_not_rewritten_even_when_the_log_changed(tmp_path: Path) -> None:
    lines = _out_of_order_lines()
    legacy = json.loads(lines[0])
    legacy["work_package_id"] = legacy.pop("wp_id")
    mission = _write_mission(tmp_path, [json.dumps(legacy, sort_keys=True), *lines[1:]])
    _commit_all(tmp_path)
    (mission / "status.json").write_text("{}\n", encoding="utf-8")  # present on disk, never tracked

    report = repair_repo(tmp_path, allow_dirty=True)

    assert (mission / "status.json").read_text(encoding="utf-8") == "{}\n"
    assert STATUS_JSON_DRIFT_NOT_WRITTEN_ACTION in report.missions[0].meta_actions
