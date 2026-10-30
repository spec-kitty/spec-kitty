"""Unit tests for the ``events tail`` log-kind helper (mission #6611, WP01).

``src/specify_cli/cli/commands/_events_tail_logs.py`` is a PURE seam: it takes
the repo root, the resolved mission and (only for the COORD-partition kinds)
the resolved status-surface directory as parameters and returns paths/strings.
No CLI runner, no resolution mocking — the domain inputs are built directly
(per the test-scaffolding-as-design-smell tactic: the seam exists precisely so
these tests need neither CliRunner nor monkeypatching).

Marker/CI discipline: module-level ``pytestmark = [pytest.mark.fast]``,
collected by ``fast-tests-cli`` (``-m "fast and not windows_ci"``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specify_cli.cli.commands._events_tail_logs import (
    SUPPORTED_LOG_KINDS,
    RunLogUnavailable,
    latest_run_journal,
    render_event_line,
    resolve_log_path,
)
from specify_cli.context.mission_resolver import ResolvedMission

pytestmark = [pytest.mark.fast]

MISSION_ID = "01M66F8AMTK80VRVD0E17AAEVZ"
MISSION_SLUG = "events-tail-multi-log-and-json-01M66F8A"


def _resolved(tmp_path: Path) -> ResolvedMission:
    return ResolvedMission(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        feature_dir=tmp_path / "kitty-specs" / MISSION_SLUG,
        mid8=MISSION_ID[:8],
    )


# ---------------------------------------------------------------------------
# T001 — kind registry + per-kind path resolution
# ---------------------------------------------------------------------------


def test_supported_log_kinds_is_the_closed_seven_kind_set() -> None:
    """C-001: exactly the seven kinds, no more, no less."""
    assert SUPPORTED_LOG_KINDS == (
        "status",
        "decisions",
        "mission",
        "run",
        "glossary",
        "ops",
        "canonical",
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("status", Path("surface") / "status.events.jsonl"),
        ("decisions", Path("surface") / "decisions.events.jsonl"),
        ("mission", Path("kitty-specs") / MISSION_SLUG / "mission-events.jsonl"),
        ("glossary", Path(".kittify") / "events" / "glossary" / f"{MISSION_ID}.events.jsonl"),
        ("ops", Path("kitty-ops") / "lifecycle.jsonl"),
        ("canonical", Path(".kittify") / "canonical-events.jsonl"),
    ],
)
def test_resolve_log_path_per_kind(tmp_path: Path, kind: str, expected: Path) -> None:
    """Every kind resolves to its canonical path (data-model.md LogKind table)."""
    resolved = _resolved(tmp_path)
    surface_dir = tmp_path / "surface"
    assert resolve_log_path(tmp_path, resolved, kind, surface_dir) == tmp_path / expected


def test_resolve_log_path_status_uses_surface_dir_not_feature_dir(tmp_path: Path) -> None:
    """#5466: status/decisions live on the RESOLVED surface, not feature_dir."""
    resolved = _resolved(tmp_path)
    surface_dir = tmp_path / "coord-worktree" / "kitty-specs" / MISSION_SLUG
    assert resolve_log_path(tmp_path, resolved, "status", surface_dir) == surface_dir / "status.events.jsonl"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("mission", Path("kitty-specs") / MISSION_SLUG / "mission-events.jsonl"),
        ("glossary", Path(".kittify") / "events" / "glossary" / f"{MISSION_ID}.events.jsonl"),
        ("ops", Path("kitty-ops") / "lifecycle.jsonl"),
        ("canonical", Path(".kittify") / "canonical-events.jsonl"),
    ],
)
def test_project_scoped_kinds_do_not_require_a_surface(tmp_path: Path, kind: str, expected: Path) -> None:
    """Lazy surface resolution: only status/decisions consume ``surface_dir``."""
    resolved = _resolved(tmp_path)
    assert resolve_log_path(tmp_path, resolved, kind, None) == tmp_path / expected


def test_resolve_log_path_coord_kinds_require_surface(tmp_path: Path) -> None:
    """status/decisions without a resolved surface fail loudly (programming error)."""
    resolved = _resolved(tmp_path)
    with pytest.raises(ValueError, match="status surface"):
        resolve_log_path(tmp_path, resolved, "status", None)


def test_resolve_log_path_unknown_kind_raises(tmp_path: Path) -> None:
    """Defense in depth — the shell's Typer choice rejects it first (exit 2)."""
    resolved = _resolved(tmp_path)
    with pytest.raises(ValueError, match="unknown log kind"):
        resolve_log_path(tmp_path, resolved, "bogus", tmp_path)


# ---------------------------------------------------------------------------
# T002 — latest-run resolution
# ---------------------------------------------------------------------------


def _write_run(
    repo_root: Path,
    mission_id: str | None,
    mission_slug: str | None,
    *,
    mtime: float,
    run_id: str = "01M66RUN0000000000000000001",
    journal_rows: list[dict[str, object]] | None = None,
    state_json: str | None = None,
) -> Path:
    """Create a run dir under ``runs_root(repo_root)`` with a state.json + journal."""
    from runtime.next.run_index import runs_root

    run_dir = runs_root(repo_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if state_json is not None:
        (run_dir / "state.json").write_text(state_json, encoding="utf-8")
    else:
        snapshot = {"run_id": run_id, "mission_key": "software-dev"}
        if mission_id is not None:
            snapshot["mission_id"] = mission_id
        if mission_slug is not None:
            snapshot["mission_slug"] = mission_slug
        (run_dir / "state.json").write_text(json.dumps(snapshot), encoding="utf-8")
    journal = run_dir / "run.events.jsonl"
    journal.write_text(
        "".join(json.dumps(row) + "\n" for row in (journal_rows or [{"type": "step"}])),
        encoding="utf-8",
    )
    os.utime(journal, (mtime, mtime))
    return run_dir


def test_latest_run_journal_missing_runs_dir_refuses(tmp_path: Path) -> None:
    resolved = _resolved(tmp_path)
    with pytest.raises(RunLogUnavailable, match=MISSION_SLUG):
        latest_run_journal(tmp_path, resolved)


def test_latest_run_journal_empty_runs_dir_refuses(tmp_path: Path) -> None:
    from runtime.next.run_index import runs_root

    runs_root(tmp_path).mkdir(parents=True)
    resolved = _resolved(tmp_path)
    with pytest.raises(RunLogUnavailable):
        latest_run_journal(tmp_path, resolved)


def test_latest_run_journal_foreign_mission_only_refuses(tmp_path: Path) -> None:
    """FR-007: never tail another mission's run."""
    _write_run(tmp_path, "01MOTHERMISSION00000000000Y", "other-mission", mtime=2_000)
    resolved = _resolved(tmp_path)
    with pytest.raises(RunLogUnavailable):
        latest_run_journal(tmp_path, resolved)


def test_latest_run_journal_newest_mtime_wins(tmp_path: Path) -> None:
    older = _write_run(tmp_path, MISSION_ID, MISSION_SLUG, mtime=1_000, run_id="01M66RUNOLD00000000000000001")
    newer = _write_run(tmp_path, MISSION_ID, MISSION_SLUG, mtime=9_000, run_id="01M66RUNNEW00000000000000002")
    resolved = _resolved(tmp_path)
    assert latest_run_journal(tmp_path, resolved) == newer / "run.events.jsonl"
    assert latest_run_journal(tmp_path, resolved) != older / "run.events.jsonl"


def test_latest_run_journal_legacy_run_matched_by_slug(tmp_path: Path) -> None:
    """Legacy state.json rows carry no mission_id — match on mission_slug."""
    legacy = _write_run(
        tmp_path,
        None,
        MISSION_SLUG,
        mtime=5_000,
        run_id="01M66RUNLEGACY0000000000000003",
    )
    resolved = _resolved(tmp_path)
    assert latest_run_journal(tmp_path, resolved) == legacy / "run.events.jsonl"


def test_latest_run_journal_skips_unreadable_state_json(tmp_path: Path) -> None:
    from runtime.next.run_index import runs_root

    broken = runs_root(tmp_path) / "01M66RUNBROKEN0000000000000004"
    broken.mkdir(parents=True)
    (broken / "state.json").write_text("{not json", encoding="utf-8")
    (broken / "run.events.jsonl").write_text("{}\n", encoding="utf-8")
    good = _write_run(tmp_path, MISSION_ID, MISSION_SLUG, mtime=3_000, run_id="01M66RUNGOOD0000000000000005")
    resolved = _resolved(tmp_path)
    assert latest_run_journal(tmp_path, resolved) == good / "run.events.jsonl"


def test_latest_run_journal_skips_run_without_journal(tmp_path: Path) -> None:
    from runtime.next.run_index import runs_root

    journalless = runs_root(tmp_path) / "01M66RUNNOJOURNAL000000000006"
    journalless.mkdir(parents=True)
    (journalless / "state.json").write_text(json.dumps({"run_id": journalless.name, "mission_id": MISSION_ID}), encoding="utf-8")
    with pytest.raises(RunLogUnavailable):
        latest_run_journal(tmp_path, _resolved(tmp_path))


def test_resolve_log_path_run_kind_delegates_to_latest_run_journal(tmp_path: Path) -> None:
    newest = _write_run(tmp_path, MISSION_ID, MISSION_SLUG, mtime=9_000, run_id="01M66RUNA0000000000000000007")
    _write_run(tmp_path, MISSION_ID, MISSION_SLUG, mtime=1_000, run_id="01M66RUNB0000000000000000008")
    assert resolve_log_path(tmp_path, _resolved(tmp_path), "run", None) == newest / "run.events.jsonl"


# ---------------------------------------------------------------------------
# T003 — human renderer
# ---------------------------------------------------------------------------


def test_render_event_line_envelope_shape() -> None:
    event = {
        "event_type": "wp_status_changed",
        "timestamp": "2026-10-30T13:00:00Z",
        "payload": {"wp": "WP01", "status": "approved"},
        "tail_offset": 512,
        "tail_invariant": "abc123",
    }
    assert render_event_line(event) == ('2026-10-30T13:00:00Z wp_status_changed {"status": "approved", "wp": "WP01"}')


def test_render_event_line_status_shape_with_at_and_type() -> None:
    event = {"type": "mission_created", "at": "2026-10-30T14:00:00Z", "mission": "demo"}
    assert render_event_line(event) == '2026-10-30T14:00:00Z mission_created {"mission": "demo"}'


def test_render_event_line_missing_fields_render_placeholder() -> None:
    event = {"payload": {"k": "v"}}
    assert render_event_line(event) == '- - {"k": "v"}'


def test_render_event_line_non_mapping_payload_falls_back_to_remainder() -> None:
    event = {"event_type": "raw", "timestamp": "t0", "payload": "just-a-string"}
    assert render_event_line(event) == 't0 raw {"payload": "just-a-string"}'


def test_render_event_line_log_truncated_warning() -> None:
    event = {
        "type": "log_truncated",
        "reason": "size_shrink",
        "detected_at_offset": 128,
        "tail_offset": 0,
        "tail_invariant": "0" * 64,
    }
    assert render_event_line(event) == "log truncated (size_shrink) at offset 128 — resynced from offset 0"


def test_render_event_line_is_deterministic() -> None:
    event = {
        "event_type": "e",
        "timestamp": "t",
        "payload": {"b": 2, "a": 1, "c": [3, {"z": 1, "y": 2}]},
    }
    assert render_event_line(event) == render_event_line(dict(event))
    # NFR-003 names key-ORDER independence: a reversed-key copy of the same
    # event must render identically (sort_keys=True, not insertion order).
    reordered = {
        "payload": {"c": [3, {"z": 1, "y": 2}], "a": 1, "b": 2},
        "timestamp": "t",
        "event_type": "e",
    }
    assert render_event_line(event) == render_event_line(reordered)


def test_render_event_line_truncates_at_400_chars() -> None:
    event = {"event_type": "big", "timestamp": "t", "payload": {"blob": "x" * 2_000}}
    line = render_event_line(event)
    assert len(line) == 403  # 400 chars + "..."
    assert line.endswith("...")
